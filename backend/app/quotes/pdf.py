"""Printable quote built only from stored snapshots, never from the current price table."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PERIODS = {"DIARIA": "Diária", "SEMANAL": "Semanal", "QUINZENAL": "Quinzenal", "MENSAL": "Mensal"}
STATUSES = {
    "RASCUNHO": "Rascunho",
    "ENVIADO": "Enviado",
    "APROVADO": "Aprovado",
    "REJEITADO": "Rejeitado",
    "EXPIRADO": "Expirado",
    "CANCELADO": "Cancelado",
    "CONVERTIDO": "Convertido",
}
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#5B6577")
LINE = colors.HexColor("#D5DBE5")
BAND = colors.HexColor("#F1F4F9")


def brl(value: str) -> str:
    text = f"{Decimal(value):,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {text}"


def number(value: str) -> str:
    text = f"{Decimal(value).normalize():f}"
    return text.replace(".", ",")


def day(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def document(value: str) -> str:
    if len(value) == 11 and value.isdigit():
        return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
    if len(value) == 14:
        return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"
    return value


def quote_pdf(data: dict, settings) -> bytes:
    styles = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=styles["Normal"], fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("small", parent=base, fontSize=8.5, leading=11, textColor=MUTED)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    title = ParagraphStyle("title", parent=base, fontSize=16, leading=20, fontName="Helvetica-Bold")
    head = ParagraphStyle("head", parent=base, fontSize=10.5, fontName="Helvetica-Bold")

    def p(text, style=base):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    company = [p(settings.company_name, title)]
    for line in (settings.company_document, settings.company_address, settings.company_contact):
        if line:
            company.append(p(line, small))
    heading = [
        p("ORÇAMENTO", ParagraphStyle("kicker", parent=small, alignment=TA_RIGHT)),
        p(data["number"], ParagraphStyle("num", parent=title, alignment=TA_RIGHT)),
        p(f"Situação: {STATUSES[data['status']]}", right),
        p(f"Válido até {day(data['valid_until'])}", right),
    ]
    story = [
        Table(
            [[company, heading]],
            colWidths=[105 * mm, 69 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "TOP")],
        ),
        Spacer(1, 6 * mm),
    ]

    customer = data["customer"]
    lines = [customer["legal_name"]]
    if customer.get("trade_name"):
        lines.append(customer["trade_name"])
    lines.append(
        ("CPF: " if customer["person_type"] == "PF" else "CNPJ: ") + document(customer["document"])
    )
    address = customer.get("address")
    if address:
        lines.append(f"{address['street']} — {address['city']}/{address['state']}")
    contact = " · ".join(
        v
        for v in (
            customer.get("contact"),
            customer.get("phone"),
            customer.get("mobile"),
            customer.get("email"),
        )
        if v
    )
    if contact:
        lines.append(contact)
    story += [
        Table(
            [
                [p("CLIENTE", small), p("INÍCIO PREVISTO DA LOCAÇÃO", small)],
                [p("\n".join(lines)), p(day(data["start_date"]), head)],
            ],
            colWidths=[124 * mm, 50 * mm],
            style=[
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ],
        ),
        Spacer(1, 6 * mm),
    ]

    rows = [
        [
            p(h, small)
            for h in (
                "Código",
                "Descrição",
                "Qtd.",
                "Período",
                "Devolução",
                "Preço por período",
                "Total",
            )
        ]
    ]
    for item in data["items"]:
        price = p(brl(item["unit_price"]), right)
        if item["negotiated"]:
            price = [
                price,
                p(
                    f"Tabela: {brl(item['table_price'])}",
                    ParagraphStyle("t", parent=small, alignment=TA_RIGHT),
                ),
            ]
        rows.append(
            [
                p(item["product_code"]),
                p(item["product_name"]),
                p(f"{number(item['quantity'])} {item['unit']}", right),
                p(f"{item['period_count']} × {PERIODS[item['period']]}"),
                p(day(item["end_date"])),
                price,
                p(brl(item["total"]), right),
            ]
        )
    story.append(
        Table(
            rows,
            colWidths=[20 * mm, 50 * mm, 18 * mm, 26 * mm, 20 * mm, 22 * mm, 18 * mm],
            repeatRows=1,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BAND),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )
    )
    totals = []
    if Decimal(data["negotiated_difference"]) != 0:
        totals.append([p("Total pela tabela", right), p(brl(data["table_total"]), right)])
        label = (
            "Desconto negociado"
            if Decimal(data["negotiated_difference"]) > 0
            else "Acréscimo negociado"
        )
        totals.append(
            [p(label, right), p(brl(str(abs(Decimal(data["negotiated_difference"])))), right)]
        )
    totals.append(
        [
            p("TOTAL DO ORÇAMENTO", ParagraphStyle("tl", parent=head, alignment=TA_RIGHT)),
            p(brl(data["total"]), ParagraphStyle("tv", parent=head, alignment=TA_RIGHT)),
        ]
    )
    story += [
        Spacer(1, 4 * mm),
        Table(
            totals,
            colWidths=[134 * mm, 40 * mm],
            style=[("LINEABOVE", (0, -1), (-1, -1), 0.8, INK), ("TOPPADDING", (0, 0), (-1, -1), 3)],
        ),
    ]
    if data["notes"]:
        story += [Spacer(1, 6 * mm), p("OBSERVAÇÕES", small), p(data["notes"])]
    story += [
        Spacer(1, 8 * mm),
        p(
            "Valores calculados por quantidade × preço do período × número de períodos. "
            "Este orçamento não reserva equipamentos e não é documento fiscal. "
            "A disponibilidade é confirmada na contratação.",
            small,
        ),
    ]

    buffer = BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Orçamento {data['number']}",
        author=settings.company_name,
    ).build(story)
    return buffer.getvalue()
