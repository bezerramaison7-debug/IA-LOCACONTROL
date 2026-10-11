"""Provider contract. Domain rules depend on this interface, never on a vendor."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from fastapi import HTTPException

ProviderStatus = Literal["PROCESSANDO", "EMITIDO", "ERRO", "CANCELADO"]


@dataclass(frozen=True)
class EmissionRequest:
    # Stable across retries: the provider must treat a repeated key as the same document.
    request_key: str
    customer: dict
    contract_number: str | None
    period_start: str
    period_end: str
    amount_cents: int
    description: str


@dataclass
class ProviderResult:
    status: ProviderStatus
    provider_ref: str | None = None
    number: str | None = None
    series: str | None = None
    access_key: str | None = None
    message: str = ""
    # Stored verbatim for conciliation; adapters must strip credentials before returning it.
    raw: dict = field(default_factory=dict)


class FiscalProvider(Protocol):
    name: str
    environment: str

    def emit(self, request: EmissionRequest) -> ProviderResult: ...

    def status(self, provider_ref: str) -> ProviderResult: ...

    def cancel(self, provider_ref: str, reason: str) -> ProviderResult: ...

    def get_pdf(self, provider_ref: str) -> bytes: ...

    def get_xml(self, provider_ref: str) -> bytes: ...


def build_provider(settings) -> FiscalProvider:
    """Adapters for real vendors (Nuvem Fiscal, Focus NFe, eNotas...) register here.

    None is implemented: each needs the vendor's sandbox credentials and the tax rules
    confirmed with the accountant. Until then only the simulation is available.
    """
    from app.fiscal.fake import FakeFiscalProvider

    if settings.fiscal_provider == "fake":
        return FakeFiscalProvider()
    raise HTTPException(
        409,
        "Provedor fiscal não configurado. A integração real depende de credenciais de teste "
        "do provedor escolhido e das regras definidas com a contabilidade.",
    )
