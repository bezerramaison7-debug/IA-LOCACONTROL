from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.reports import export
from app.reports.service import REPORTS, Filters, ReportService

router = APIRouter(prefix="/api", tags=["Dashboard e relatórios"])
ContractsRead = Annotated[User, Depends(require("contracts.read"))]
ReportsRead = Annotated[User, Depends(require("reports.read"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=200)]
Search = Annotated[str, Query(max_length=160)]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def service(request: Request, db, user) -> ReportService:
    return ReportService(db, user, request.app.state.settings.contract_due_soon_days)


def filters(
    date_from: date | None = None,
    date_to: date | None = None,
    customer_id: int | None = None,
    product_id: int | None = None,
    q: Search = "",
) -> Filters:
    return Filters(date_from, date_to, customer_id, product_id, q.strip())


ReportFilters = Annotated[Filters, Depends(filters)]


@router.get("/dashboard")
def dashboard(request: Request, db: DB, user: ContractsRead):
    return service(request, db, user).dashboard()


@router.get("/customers/{customer_id}/summary")
def customer_summary(request: Request, customer_id: int, db: DB, user: ContractsRead):
    return service(request, db, user).customer(customer_id)


@router.get("/reports")
def catalog(user: ReportsRead):
    return {"items": [{"key": key, "title": item["title"]} for key, item in REPORTS.items()]}


@router.get("/reports/{key}")
def report(
    request: Request,
    key: str,
    f: ReportFilters,
    db: DB,
    user: ReportsRead,
    offset: Offset = 0,
    limit: Limit = 50,
):
    result = service(request, db, user).run(key, f)
    rows = result.pop("rows")
    return {**result, "total": len(rows), "rows": rows[offset : offset + limit]}


@router.get("/reports/{key}/export")
def export_report(
    request: Request,
    key: str,
    f: ReportFilters,
    db: DB,
    user: ReportsRead,
    format: Literal["xlsx", "pdf"] = "xlsx",
):
    result = service(request, db, user).run(key, f)
    if format == "pdf":
        content, media = (
            export.pdf(result, request.app.state.settings.company_name),
            "application/pdf",
        )
    else:
        content, media = export.xlsx(result), XLSX
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="relatorio-{key}.{format}"'},
    )
