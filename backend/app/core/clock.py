"""Commercial calendar date. Instants stay UTC integers; business dates are local days."""

from datetime import UTC, date, datetime, timedelta, timezone

# Brasília has had a fixed UTC-3 offset since DST was abolished in 2019; a fixed offset avoids
# depending on the tzdata package on Windows.
BUSINESS_TZ = timezone(timedelta(hours=-3))


def business_today() -> date:
    return datetime.now(UTC).astimezone(BUSINESS_TZ).date()
