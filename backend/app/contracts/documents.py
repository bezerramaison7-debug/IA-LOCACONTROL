"""Contract templates with placeholders and versioned, immutable generated PDFs."""

import hashlib
import re
import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import HTTPException
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select

from app.contracts.models import ContractDocument, ContractTemplate
from app.contracts.service import ContractService, document_view
from app.core.clock import business_today
from app.quotes.pdf import BAND, INK, LINE, MUTED, PERIODS, brl, day, document, number

PLACEHOLDER = re.compile(r"\{\{\s*([a-z_.]+)\s*\}\}")
BLOCKS = {"items", "totals", "signatures"}
FIELDS = {
    "company.name",
    "company.document",
    "company.address",
    "company.contact",
    "contract.number",
    "contract.start_date",
    "contract.end_date",
    "contract.total",
    "contract.notes",
    "customer.legal_name",
    "customer.trade_name",
    "customer.document",
    "customer.address",
    "customer.contact",
    "today",
}
PROVISIONAL_NOTICE = (
    "MODELO PROVISÓRIO — texto de exemplo até a locadora fornecer o seu contrato oficial."
)


def validate_template(body: str):
    unknown = sorted(set(PLACEHOLDER.findall(body)) - FIELDS - BLOCKS)
    if unknown:
        raise HTTPException(422, "Campos desconhecidos no modelo: " + ", ".join(unknown) + ".")
    for line in body.splitlines():
        names = PLACEHOLDER.findall(line)
        if any(name in BLOCKS for name in names) and (
            len(names) != 1 or PLACEHOLDER.sub("", line).strip()
        ):
            raise HTTPException(
                422, "Os blocos items, totals e signatures devem ficar sozinhos na linha."
            )


def context(data: dict, settings) -> dict:
    customer = data["customer"]
    address = customer.get("address")
    contact = " · ".join(
        value
        for value in (
            customer.get("contact"),
            customer.get("phone"),
            customer.get("mobile"),
            customer.get("email"),
        )
        if value
    )
    return {
        "company.name": settings.company_name,
        "company.document": settings.company_document,
        "company.address": settings.company_address,
        "company.contact": settings.company_contact,
        "contract.number": data["number"],
        "contract.start_date": day(data["start_date"]),
        "contract.end_date": day(data["end_date"]),
        "contract.total": brl(data["total"]),
        "contract.notes": data["notes"] or "Sem observações.",
        "customer.legal_name": customer["legal_name"],
        "customer.trade_name": customer.get("trade_name") or customer["legal_name"],
        "customer.document": document(customer["document"]),
        "customer.address": (
            f"{address['street']}, {address['city']}/{address['state']}"
            if address
            else "endereço não informado"
        ),
        "customer.contact": contact or "contato não informado",
        "today": business_today().strftime("%d/%m/%Y"),
    }


def contract_pdf(body: str, provisional: bool, data: dict, settings) -> bytes:
    """Render the template with this contract's stored snapshots only."""
    styles = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=styles["Normal"], fontSize=10, leading=14, textColor=INK)
    small = ParagraphStyle("small", parent=base, fontSize=8.5, leading=11, textColor=MUTED)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    head = ParagraphStyle("head", parent=base, fontSize=11.5, leading=15, fontName="Helvetica-Bold")
    center = ParagraphStyle("center", parent=small, alignment=TA_CENTER)
    values = context(data, settings)

    def p(text, style=base):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def items_block():
        rows = [
            [
                p(h, small)
                for h in ("Código", "Descrição", "Qtd.", "Período", "Devolução", "Preço", "Total")
            ]
        ]
        for item in data["items"]:
            rows.append(
                [
                    p(item["product_code"]),
                    p(item["product_name"]),
                    p(f"{number(item['quantity'])} {item['unit']}", right),
                    p(f"{item['period_count']} × {PERIODS[item['period']]}"),
                    p(day(item["end_date"])),
                    p(brl(item["unit_price"]), right),
                    p(brl(item["total"]), right),
                ]
            )
        return Table(
            rows,
            colWidths=[20 * mm, 50 * mm, 18 * mm, 26 * mm, 20 * mm, 21 * mm, 19 * mm],
            repeatRows=1,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BAND),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )

    def totals_block():
        return Table(
            [
                [
                    p(
                        "VALOR TOTAL DA LOCAÇÃO",
                        ParagraphStyle("tl", parent=head, alignment=TA_RIGHT),
                    ),
                    p(brl(data["total"]), ParagraphStyle("tv", parent=head, alignment=TA_RIGHT)),
                ]
            ],
            colWidths=[134 * mm, 40 * mm],
            style=[("LINEABOVE", (0, 0), (-1, 0), 0.8, INK), ("TOPPADDING", (0, 0), (-1, -1), 4)],
        )

    def signatures_block():
        line = "_" * 34
        return Table(
            [
                [p(line, center), p(line, center)],
                [p(values["company.name"], center), p(values["customer.legal_name"], center)],
                [p("LOCADORA", center), p("LOCATÁRIO(A)", center)],
            ],
            colWidths=[87 * mm, 87 * mm],
            style=[("TOPPADDING", (0, 0), (-1, 0), 30)],
        )

    blocks = {"items": items_block, "totals": totals_block, "signatures": signatures_block}
    story = []
    if provisional:
        story += [p(PROVISIONAL_NOTICE, center), Spacer(1, 4 * mm)]
    paragraph = []

    def flush():
        if paragraph:
            story.extend([p(" ".join(paragraph)), Spacer(1, 3 * mm)])
            paragraph.clear()

    for raw in body.splitlines():
        line = raw.strip()
        names = PLACEHOLDER.findall(line)
        if not line:
            flush()
        elif names and names[0] in BLOCKS:
            flush()
            story.extend([blocks[names[0]](), Spacer(1, 4 * mm)])
        else:
            text = PLACEHOLDER.sub(lambda match: values[match[1]], line)
            if line.startswith("# "):
                flush()
                story.extend([Spacer(1, 2 * mm), p(text[2:], head), Spacer(1, 2 * mm)])
            else:
                paragraph.append(text)
    flush()

    buffer = BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Contrato {data['number']}",
        author=settings.company_name,
    ).build(story)
    return buffer.getvalue()


def template_view(row: ContractTemplate, full=False) -> dict:
    data = {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "is_provisional": row.is_provisional,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "created_by": row.created_by,
    }
    if full:
        data["body"] = row.body
    return data


class DocumentService:
    def __init__(self, db, actor, settings):
        self.db = db
        self.actor = actor
        self.settings = settings
        self.contracts = ContractService(db, actor, settings.contract_due_soon_days)

    # ---- templates -----------------------------------------------------------------

    def templates(self) -> dict:
        rows = self.db.scalars(select(ContractTemplate).order_by(ContractTemplate.id.desc()))
        return {
            "items": [template_view(row, full=True) for row in rows],
            "fields": sorted(FIELDS),
            "blocks": sorted(BLOCKS),
        }

    def current_template(self) -> ContractTemplate:
        row = self.db.scalar(
            select(ContractTemplate)
            .where(ContractTemplate.is_active)
            .order_by(ContractTemplate.id.desc())
            .limit(1)
        )
        if row is None:
            raise HTTPException(409, "Não há modelo de contrato ativo.")
        return row

    def save_template(self, payload) -> dict:
        """A new version becomes the model in use; earlier versions stay for history."""
        validate_template(payload.body)
        version = (
            self.db.scalar(
                select(func.max(ContractTemplate.version)).where(
                    ContractTemplate.name == payload.name
                )
            )
            or 0
        ) + 1
        for old in self.db.scalars(select(ContractTemplate).where(ContractTemplate.is_active)):
            old.is_active = False
        row = ContractTemplate(
            name=payload.name,
            version=version,
            body=payload.body,
            is_provisional=payload.is_provisional,
            is_active=True,
            created_by=self.actor.id,
        )
        self.db.add(row)
        self.db.flush()
        self.contracts.identity.audit(
            "contract.template_published", "contract_templates", row.id, template_view(row)
        )
        self.db.flush()
        return template_view(row, full=True)

    # ---- documents -----------------------------------------------------------------

    def directory(self) -> Path:
        path = Path(self.settings.document_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def preview(self, contract_id: int) -> tuple[bytes, str]:
        data = self.contracts.detail(contract_id)
        template = self.current_template()
        pdf = contract_pdf(template.body, template.is_provisional, data, self.settings)
        return pdf, f"Contrato-{data['number']}-previa.pdf"

    def generate(self, contract_id: int, payload) -> dict:
        row = self.contracts.get(contract_id)
        if row.status in {"RASCUNHO", "CANCELADO"}:
            raise HTTPException(
                409, "Confirme o contrato antes de gerar o documento; use a prévia no rascunho."
            )
        template = (
            self.db.get(ContractTemplate, payload.template_id)
            if payload.template_id
            else self.current_template()
        )
        if template is None:
            raise HTTPException(404, "Modelo de contrato não encontrado.")
        existing = list(
            self.db.scalars(select(ContractDocument).where(ContractDocument.contract_id == row.id))
        )
        reason = payload.reason.strip()
        signed = any(doc.status == "ASSINADO" for doc in existing)
        if signed and len(reason) < 5:
            raise HTTPException(
                422,
                "Já existe documento assinado. Informe o motivo da nova versão; "
                "o assinado será preservado.",
            )
        data = self.contracts.view(row)
        pdf = contract_pdf(template.body, template.is_provisional, data, self.settings)
        # A signed document is never replaced; only unsigned drafts are superseded.
        for doc in existing:
            if doc.status == "GERADO":
                doc.status = "SUBSTITUIDO"
        document_row = ContractDocument(
            contract_id=row.id,
            template_id=template.id,
            version=max((doc.version for doc in existing), default=0) + 1,
            stored_name=f"{uuid4().hex}.pdf",
            checksum=hashlib.sha256(pdf).hexdigest(),
            size=len(pdf),
            status="GERADO",
            reason=reason,
            created_by=self.actor.id,
        )
        self.db.add(document_row)
        self.db.flush()
        self.contracts.event(
            row, "DOCUMENTO", f"Documento versão {document_row.version} gerado para {row.number}."
        )
        self.contracts.identity.audit(
            "contract.document_generated",
            "contract_documents",
            document_row.id,
            document_view(document_row),
        )
        self.db.flush()
        # Written last: a failed transaction leaves no document row pointing to a missing file.
        (self.directory() / document_row.stored_name).write_bytes(pdf)
        return document_view(document_row)

    def document(self, document_id: int) -> ContractDocument:
        row = self.db.get(ContractDocument, document_id)
        if row is None:
            raise HTTPException(404, "Documento não encontrado.")
        return row

    def sign(self, document_id: int, payload) -> dict:
        row = self.document(document_id)
        if row.status != "GERADO":
            raise HTTPException(
                409, "Somente a versão vigente e ainda não assinada pode ser marcada como assinada."
            )
        row.status = "ASSINADO"
        row.signed_at = int(time.time())
        row.signed_by = self.actor.id
        if payload.notes.strip():
            row.reason = payload.notes.strip()
        contract = self.contracts.get(row.contract_id)
        self.contracts.event(
            contract, "ASSINADO", f"Documento versão {row.version} de {contract.number} assinado."
        )
        self.contracts.identity.audit(
            "contract.document_signed", "contract_documents", row.id, document_view(row)
        )
        self.db.flush()
        return document_view(row)

    def download(self, document_id: int) -> tuple[bytes, str]:
        row = self.document(document_id)
        path = self.directory() / row.stored_name
        if not path.is_file():
            raise HTTPException(409, "Arquivo do documento não encontrado no armazenamento.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row.checksum:
            raise HTTPException(409, "O arquivo do documento foi alterado fora do sistema.")
        contract = self.contracts.get(row.contract_id)
        return content, f"Contrato-{contract.number}-v{row.version}.pdf"
