"""Pure quote arithmetic. Decimal only; results are exact scaled integers."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Decisão comercial de 2026-10-11: dias corridos por período, sem fração de período.
PERIOD_DAYS = {"DIARIA": 1, "SEMANAL": 7, "QUINZENAL": 15, "MENSAL": 30}
MAX_CENTS = 99_999_999_999


def item_total_cents(quantity_milli: int, unit_price_cents: int, period_count: int) -> int:
    """Quantidade × preço unitário do período × número de períodos, meio centavo para cima."""
    exact = Decimal(quantity_milli) * Decimal(unit_price_cents) * Decimal(period_count) / 1000
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def end_date(start: date, period: str, period_count: int) -> date:
    return start + timedelta(days=PERIOD_DAYS[period] * period_count)


def money(cents: int) -> str:
    return format(Decimal(cents) / 100, ".2f")


def signed_money(cents: int) -> str:
    """Difference between two amounts; may be negative. Decimal, never float."""
    return format(Decimal(cents) / 100, ".2f")


def business_date(value: date) -> date:
    """Rejects dates far outside any rental; keeps date arithmetic away from overflow."""
    if not 2000 <= value.year <= 2100:
        raise ValueError("Data fora do intervalo aceito")
    return value


def quantity(milli: int) -> str:
    return format(Decimal(milli) / 1000, ".3f")
