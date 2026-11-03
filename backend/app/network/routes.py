"""Station management and pairing (network edition, ADR-025).

Pairing is the only route a computer of the store network reaches without a session: it
exchanges the temporary code shown on the main computer for the station's own credential.
Everything else here is for the main computer only (decision of the user, 2026-11-02).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import delete, select

from app.auth.dependencies import DB, CurrentUser
from app.auth.local import installation
from app.auth.models import AuditLog, AuthSession
from app.auth.routes import set_station_cookie
from app.auth.service import IdentityService
from app.masters.schemas import Input
from app.network.stations import (
    NOT_PAIRED,
    peer_address,
    principal_only,
    station_label,
    station_request,
)

router = APIRouter(prefix="/api/stations", tags=["Rede local e estações"])


def local_only(request: Request):
    if not request.app.state.settings.local_mode:
        raise HTTPException(404, "Recurso indisponível nesta edição.")


def network_on(request: Request):
    if not request.app.state.settings.network_mode:
        raise HTTPException(
            409,
            "A rede da loja está desativada neste computador. Ative o modo rede na instalação "
            "do computador principal.",
        )


Principal = Annotated[None, Depends(principal_only)]


class PairInput(Input):
    code: str = Field(min_length=4, max_length=20)
    name: str = Field(min_length=1, max_length=60)


@router.post("/pair", status_code=201, dependencies=[Depends(local_only), Depends(network_on)])
def pair(payload: PairInput, request: Request, response: Response, db: DB):
    """A computer of the store network presents the code; it receives its own credential."""
    if not station_request(request):
        raise HTTPException(403, NOT_PAIRED)
    peer = str(peer_address(request))
    station, token = request.app.state.stations.pair(payload.code, payload.name.strip(), peer)
    db.add(
        AuditLog(
            actor_id=None,
            actor_label=station_label(station),
            action="station.paired",
            entity="stations",
            entity_id=station["id"],
            changes={"name": station["name"], "address": peer},
        )
    )
    set_station_cookie(response, request.app.state.settings, token)
    return {"station": station}


@router.get("", dependencies=[Depends(local_only)])
def overview(request: Request, db: DB, user: CurrentUser, _: Principal):
    registry = request.app.state.stations
    return {
        # Three identities: the database/store, this server and each station.
        "installation_id": installation(db)["id"],
        "server": registry.server(),
        "network": request.app.state.settings.network_mode,
        "pairing": registry.pairing(),
        "stations": registry.listing(),
        "events": registry.events(limit=30),
    }


@router.post("/pairing", status_code=201, dependencies=[Depends(local_only), Depends(network_on)])
def start_pairing(request: Request, db: DB, user: CurrentUser, _: Principal):
    code = request.app.state.stations.start_pairing()
    IdentityService(db, user).audit("station.pairing_started", "stations", None, {})
    return code


@router.delete("/pairing", status_code=204, dependencies=[Depends(local_only)])
def cancel_pairing(request: Request, db: DB, user: CurrentUser, _: Principal):
    request.app.state.stations.cancel_pairing()
    IdentityService(db, user).audit("station.pairing_cancelled", "stations", None, {})
    return Response(status_code=204)


@router.post("/{station_id}/revoke", dependencies=[Depends(local_only)])
def revoke(station_id: str, request: Request, db: DB, user: CurrentUser, _: Principal):
    station = request.app.state.stations.revoke(station_id)
    # Its open sessions end now; any other copy (from a backup) is refused at every request.
    db.execute(delete(AuthSession).where(AuthSession.station_id == station_id))
    IdentityService(db, user).audit(
        "station.revoked", "stations", station_id, {"name": station["name"]}
    )
    return {"station": station}


@router.get("/{station_id}/activity", dependencies=[Depends(local_only)])
def activity(station_id: str, request: Request, db: DB, user: CurrentUser, _: Principal):
    """Audit per station: registry events (kept across restores) and audited operations."""
    registry = request.app.state.stations
    station = registry.get(station_id)
    if station is None:
        raise HTTPException(404, "Estação não encontrada.")
    marker = f"({station_id[:8]})"
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.actor_label.contains(marker))
        .order_by(AuditLog.id.desc())
        .limit(100)
    )
    return {
        "station": station,
        "events": registry.events(station_id),
        "audit": [
            {
                "id": row.id,
                "occurred_at": row.occurred_at,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
            }
            for row in rows
        ],
    }
