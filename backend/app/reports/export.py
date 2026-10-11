"""Report exports built in memory: Excel keeps numbers and dates typed, PDF is for printing."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.clock import business_today
from app.quotes.pdf import BAND, INK, LINE, MUTED, brl, day, number

LABELS = {
    "DISPONIVEL": "Disponível",
    "RESERVADO": "Reservado",
    "LOCADO": "Locado",
    "MANUTENCAO": "Manutenção",
    "INDISPONIVEL": "Indisponível",
    "BAIXADO": "Baixado",
    "RASCUNHO": "Rascunho",
    "AGUARDANDO_RETIRADA": "Aguardando retirada",
    "ATIVO": "Ativo",
    "VENCENDO": "Vencendo",
    "VENCIDO": "Vencido",
    "ENCERRADO": "Encerrado",
    "CANCELADO": "Cancelado",
    "ANTERIORES": "Anteriores mantidos",
    "ATUAIS": "Tabela atual",
    "NEGOCIADOS": "Negociados",
    "BOM": "Bom",
    "AVARIADO": "Avariado",
}
FORMATS = {"money": "#,##0.00", "quantity": "#,##0.###", "date": "DD/MM/YYYY", "int": "0"}


def typed(value, kind):
    if value in (None, ""):
        return None
    if kind in {"money", "quantity"}:
        return Decimal(value)
    if kind == "date":
        return date.fromisoformat(value)
    if kind == "status":
        return LABELS.get(value, value)
    return value


def printed(value, kind) -> str:
    if value in (None, ""):
        return ""
    if kind == "money":
        return brl(value)
    if kind == "quantity":
        return number(value)
    if kind == "date":
        return day(value)
    if kind == "status":
        return LABELS.get(value, value)
    return str(value)


def xlsx(report: dict) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = report["title"][:31]
    columns = report["columns"]
    sheet.append([c["label"] for c in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in report["rows"]:
        sheet.append([typed(row.get(c["key"]), c["type"]) for c in columns])
        for cell in sheet[sheet.max_row]:
            # openpyxl turns any text starting with "=" into a formula.
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.data_type = "s"
    for index, c in enumerate(columns, 1):
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = 18 if c["type"] != "text" else 34
        if c["type"] in FORMATS:
            for cell in sheet[letter][1:]:
                cell.number_format = FORMATS[c["type"]]
    sheet.freeze_panes = "A2"
    if report["note"]:
        sheet.append([])
        sheet.append([report["note"]])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def pdf(report: dict, company: str) -> bytes:
    styles = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=styles["Normal"], fontSize=8, leading=10, textColor=INK)
    small = ParagraphStyle("small", parent=base, textColor=MUTED)
    title = ParagraphStyle("title", parent=base, fontSize=14, leading=18, fontName="Helvetica-Bold")
    columns = report["columns"]
    rows = [[Paragraph(escape(c["label"]), small) for c in columns]]
    for row in report["rows"]:
        rows.append(
            [Paragraph(escape(printed(row.get(c["key"]), c["type"])), base) for c in columns]
        )
    story = [
        Paragraph(escape(report["title"]), title),
        Paragraph(
            escape(
                f"{company} · emitido em {business_today().strftime('%d/%m/%Y')} · "
                f"{len(report['rows'])} linha(s)"
            ),
            small,
        ),
        Spacer(1, 4 * mm),
        Table(
            rows,
            repeatRows=1,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BAND),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            ),
        ),
    ]
    if report["note"]:
        story += [Spacer(1, 4 * mm), Paragraph(escape(report["note"]), small)]
    buffer = BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=report["title"],
        author=company,
    ).build(story)
    return buffer.getvalue()
