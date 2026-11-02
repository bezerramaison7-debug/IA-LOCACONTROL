from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.services.health import check_health

router = APIRouter(tags=["technical"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ok", "unhealthy", "maintenance"]
    database: Literal["ok", "unavailable"]
    schema_status: Literal["ok", "outdated", "unknown"] = Field(alias="schema")
    version: str


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(request: Request, response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    if request.app.state.gate.maintenance:
        # The database is being replaced: do not touch it.
        response.status_code = 503
        return HealthResponse(
            status="maintenance",
            database="unavailable",
            schema_status="unknown",
            version=__version__,
        )
    report = check_health(request.app.state.engine, request.app.state.expected_heads)
    if report.status != "ok":
        response.status_code = 503
    return HealthResponse(
        status=report.status,
        database=report.database,
        schema_status=report.schema,
        version=__version__,
    )
