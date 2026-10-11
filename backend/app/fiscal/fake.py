"""Simulation provider: validates the architecture and issues nothing with fiscal value.

Behaviour is driven by the description so tests and demonstrations can reach every state:
"[ERRO]" is rejected, "[PROCESSANDO]" stays in processing until the next status query.
"""

import hashlib
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.fiscal.provider import EmissionRequest, ProviderResult

NOTICE = "SIMULAÇÃO — documento sem valor fiscal"


class FakeFiscalProvider:
    name = "fake"
    environment = "SIMULACAO"

    def reference(self, request_key: str) -> str:
        return "SIM-" + hashlib.sha256(request_key.encode()).hexdigest()[:16].upper()

    def emit(self, request: EmissionRequest) -> ProviderResult:
        reference = self.reference(request.request_key)
        raw = {"simulacao": True, "referencia": reference, "valor_centavos": request.amount_cents}
        if "[ERRO]" in request.description:
            return ProviderResult(
                "ERRO", reference, message="Rejeição simulada pelo provedor.", raw=raw
            )
        if "[PROCESSANDO]" in request.description:
            return ProviderResult("PROCESSANDO", reference, raw=raw)
        return self.issued(reference, raw)

    def issued(self, reference: str, raw: dict) -> ProviderResult:
        digits = str(int(reference[4:12], 16) % 1_000_000).zfill(6)
        return ProviderResult(
            "EMITIDO",
            reference,
            number=digits,
            series="SIM",
            access_key=None,
            raw={**raw, "numero": digits, "serie": "SIM"},
        )

    def status(self, provider_ref: str) -> ProviderResult:
        return self.issued(provider_ref, {"simulacao": True, "referencia": provider_ref})

    def cancel(self, provider_ref: str, reason: str) -> ProviderResult:
        return ProviderResult(
            "CANCELADO",
            provider_ref,
            raw={"simulacao": True, "referencia": provider_ref, "motivo": reason},
        )

    def get_pdf(self, provider_ref: str) -> bytes:
        styles = getSampleStyleSheet()
        buffer = BytesIO()
        SimpleDocTemplate(buffer, pagesize=A4, title=NOTICE).build(
            [
                Paragraph(NOTICE, styles["Title"]),
                Spacer(1, 12),
                Paragraph(f"Referência {escape(provider_ref)}", styles["Normal"]),
                Paragraph(
                    "Gerado pelo provedor de simulação do LocaControl para validar o fluxo. "
                    "Não foi transmitido a nenhum órgão ou provedor fiscal.",
                    styles["Normal"],
                ),
            ]
        )
        return buffer.getvalue()

    def get_xml(self, provider_ref: str) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<simulacao referencia="{escape(provider_ref)}">{NOTICE}</simulacao>\n'
        ).encode()
