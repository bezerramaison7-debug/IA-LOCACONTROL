"""Station management and pairing (network edition, ADR-025).

Pairing is the only route a computer of the store network reaches without a session: it
exchanges the temporary code shown on the main computer for the station's own credential.
Everything else here is for the main computer only (decision of the user, 2026-11-02).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.dependencies import DB, CurrentUser
from app.auth.local import installation
from app.auth.models import AuditLog, AuthSession
from app.auth.routes import set_station_cookie
from app.auth.service import IdentityService
from app.masters.schemas import Input
from app.network.stations import (
    NOT_PAIRED,
    RESET_PHRASE,
    peer_address,
    principal_only,
    station_label,
    station_request,
)

router = APIRouter(prefix="/api/stations", tags=["Rede local e estações"])


def record_reuse(engine, reuse: dict):
    """Audits a detected credential reuse (A1) in its own transaction: the request that revealed
    it was refused, so its transaction was rolled back."""
    station = reuse["station"]
    try:
        with Session(engine) as db:
            db.add(
                AuditLog(
                    actor_id=None,
                    actor_label=station_label(station),
                    action="station.reuse_detected",
                    entity="stations",
                    entity_id=station["id"],
                    changes={k: reuse[k] for k in ("peer", "agent", "last_address")},
                    station_id=station["id"],
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001 — the registry already holds the event
        logging.getLogger(__name__).exception("Falha ao auditar o reuso de credencial.")


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
    # Letters, digits, spaces and - _ . only (M4): no parentheses imitating another station's
    # code in the audit, no control characters. 40 keeps the audit label within 100 characters.
    name: str = Field(min_length=1, max_length=40, pattern=r"^[\w .\-]+$")


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
            station_id=station["id"],
        )
    )
    set_station_cookie(response, request.app.state.settings, token)
    return {"station": station}


@router.get("", dependencies=[Depends(local_only)])
def overview(request: Request, db: DB, user: CurrentUser, _: Principal):
    registry = request.app.state.stations
    state = registry.state()
    result = {
        # Three identities: the database/store, this server and each station.
        "installation_id": installation(db)["id"],
        "server": registry.server(),
        "network": request.app.state.settings.network_mode,
        "registry": state,
        "pairing": None,
        "stations": [],
        "events": [],
    }
    if not state["unavailable"]:
        result |= {
            "pairing": registry.pairing(),
            "stations": registry.listing(),
            "events": registry.events(limit=30),
        }
    return result


class ResetInput(Input):
    # Must be exactly RESET_PHRASE: every station will have to be paired again.
    confirmation: str = Field(max_length=40)


@router.post("/registry/reset", dependencies=[Depends(local_only)])
def reset_registry(payload: ResetInput, request: Request, db: DB, user: CurrentUser, _: Principal):
    """Repair of an unreadable station list (A2): files kept aside, a new list starts."""
    if payload.confirmation != RESET_PHRASE:
        raise HTTPException(422, f'Digite exatamente "{RESET_PHRASE}" para confirmar.')
    registry = request.app.state.stations
    before = registry.state()
    server = registry.reset()
    # No previous station keeps a session: all of them pair again.
    db.execute(delete(AuthSession).where(AuthSession.station_id.is_not(None)))
    IdentityService(db, user).audit(
        "station.registry_reset", "stations", None, {"before": before, "server_id": server["id"]}
    )
    return {"server": server, "registry": registry.state()}


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
    # By the structured station id (M4), never by the text of the label.
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.station_id == station_id)
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
