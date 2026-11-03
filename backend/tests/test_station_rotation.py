# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Rotação do token da estação e detecção de reuso (A1), com relógio controlado.

O que estes testes sustentam: uma cópia dos cookies de uma estação é detectada quando as duas
cópias são usadas depois de uma rotação, e então a estação é revogada e o fato auditado. O que
eles NÃO sustentam: que a cópia não funcione antes disso — o primeiro teste mostra que funciona.
"""

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_stations import CUSTOMER, Computer, make_app, network, paired  # noqa: F401

from app.auth.models import AuditLog
from app.network.stations import GRACE_SECONDS, PENDING_SECONDS, REUSE_REASON, STATION_COOKIE

ROTATE = 15 * 60


class Clock:
    def __init__(self, app):
        self.now = 1_800_000_000.0
        app.state.stations.clock = lambda: self.now

    def advance(self, seconds):
        self.now += seconds


def put(computer, name, value):
    """Replaces a cookie exactly as the server set it (same host and path), like a browser."""
    for cookie in list(computer.client.cookies.jar):
        if cookie.name == name:
            computer.client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
    computer.client.cookies.set(name, value, domain="192.168.0.10", path="/api")


def clone_of(app, station, peer):
    copy = Computer(app, peer)
    for name in ("locacontrol_session", STATION_COOKIE):
        put(copy, name, station.client.cookies[name])
    copy.csrf = station.csrf
    return copy


def overview(principal):
    response = principal.get("/api/stations")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_copy_works_until_a_rotation_then_reuse_revokes_and_is_audited(network):
    app, principal = network
    clock = Clock(app)
    legit = paired(app, principal, "192.168.0.21", "Balcão")
    station_id = legit.me().json()["station"]["id"]
    assert legit.client.get("/api/customers").status_code == 200  # usa o token novo da sessão
    clone = clone_of(app, legit, "192.168.0.99")
    # Honesto: antes de uma rotação a cópia funciona (lê e grava).
    assert clone.client.get("/api/customers").status_code == 200
    assert clone.write("POST", "/api/customers", CUSTOMER).status_code == 201

    clock.advance(ROTATE + 1)
    first = legit.client.get("/api/customers")
    assert first.status_code == 200 and STATION_COOKIE in first.cookies  # novo token oferecido
    assert legit.client.get("/api/customers").status_code == 200  # usado: o antigo se aposenta
    clock.advance(GRACE_SECONDS + 1)
    caught = clone.client.get("/api/customers")
    assert caught.status_code == 401
    # A estação inteira é revogada: quem tem o token legítimo também precisa parear de novo.
    assert legit.client.get("/api/customers").status_code == 401
    stations = overview(principal)["stations"]
    assert stations[0]["revoked_reason"] == REUSE_REASON
    event = next(
        e for e in overview(principal)["events"] if e["action"] == "station.reuse_detected"
    )
    assert event["station_id"] == station_id and event["peer"] == "192.168.0.99"
    with Session(app.state.engine) as db:
        audited = db.scalar(select(AuditLog).where(AuditLog.action == "station.reuse_detected"))
    assert audited is not None and audited.station_id == station_id
    assert audited.changes["peer"] == "192.168.0.99"


def test_reuse_is_detected_also_when_the_copy_rotates_first(network):
    app, principal = network
    clock = Clock(app)
    legit = paired(app, principal, "192.168.0.21", "Balcão")
    legit.client.get("/api/customers")
    clone = clone_of(app, legit, "192.168.0.99")
    clock.advance(ROTATE + 1)
    clone.client.get("/api/customers")  # a cópia recebe e usa o token novo
    clone.client.get("/api/customers")
    clock.advance(GRACE_SECONDS + 1)
    assert legit.client.get("/api/customers").status_code == 401  # o antigo reaparece: reuso
    assert clone.client.get("/api/customers").status_code == 401
    assert overview(principal)["stations"][0]["revoked_reason"] == REUSE_REASON


def test_no_false_positive_for_lost_responses_idle_browsers_or_parallel_tabs(network):
    app, principal = network
    clock = Clock(app)
    station = paired(app, principal, "192.168.0.21", "Balcão")
    station.client.get("/api/customers")
    # Resposta perdida: o token oferecido nunca chega ao navegador; o atual continua valendo.
    kept = station.client.cookies[STATION_COOKIE]
    clock.advance(ROTATE + 1)
    station.client.get("/api/customers")
    put(station, STATION_COOKIE, kept)  # descarta o novo, como se não tivesse vindo
    for _ in range(3):
        clock.advance(PENDING_SECONDS + 1)
        assert station.client.get("/api/customers").status_code == 200
        put(station, STATION_COOKIE, kept)
    # Navegador que guardou a oferta e ficou ocioso por um dia: a oferta continua aceita.
    clock.advance(PENDING_SECONDS + 1)
    offered = station.client.get("/api/customers").cookies.get(STATION_COOKIE)
    assert offered
    clock.advance(24 * 3600)
    put(station, STATION_COOKIE, offered)
    assert station.client.get("/api/customers").status_code == 200
    # Abas em paralelo no instante da troca: requisições com o token anterior, dentro da
    # tolerância, são aceitas.
    clock.advance(ROTATE + 1)
    station.client.get("/api/customers")
    previous = station.client.cookies[STATION_COOKIE]
    station.client.get("/api/customers")  # promove o novo
    tab = clone_of(app, station, "192.168.0.21")
    put(tab, STATION_COOKIE, previous)
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(tab.client.get("/api/customers").status_code)
        )
        for _ in range(5)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results == [200] * 5
    assert not overview(principal)["stations"][0]["revoked_at"]
    assert not [e for e in overview(principal)["events"] if e["action"] == "station.reuse_detected"]


def test_every_new_session_offers_a_new_token(network):
    from test_stations import new_code

    app, principal = network
    Clock(app)
    station = Computer(app, "192.168.0.21")
    paired_token = station.pair(new_code(principal), "Balcão").cookies[STATION_COOKIE]
    first = station.client.get("/api/auth/me", headers={"X-LocaControl-Request": "1"})
    offered = first.cookies.get(STATION_COOKIE)
    assert first.status_code == 200 and offered not in (None, paired_token)
    station.client.get("/api/customers")  # usa o novo: o do pareamento se aposenta
    station.client.cookies.delete("locacontrol_session")
    second = station.client.get("/api/auth/me", headers={"X-LocaControl-Request": "1"})
    assert second.status_code == 200
    assert second.cookies.get(STATION_COOKIE) not in (None, paired_token, offered)
