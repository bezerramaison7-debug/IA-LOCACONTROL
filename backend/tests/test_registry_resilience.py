# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Resiliência do stations.json (A2): gravação durável com cópia `.bak`, recuperação pela cópia,
lista ilegível sem tirar o computador principal do ar e reparo explícito e auditado."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_stations import (  # noqa: F401
    APP,
    PRINCIPAL,
    Computer,
    make_app,
    network,
    new_code,
    paired,
)

from app.auth.models import AuditLog
from app.core import durable
from app.network.stations import RESET_PHRASE


def restart(app):
    """Forgets what the running server had in memory, as after a restart."""
    registry = app.state.stations
    registry._cache, registry.unavailable, registry.recovered = None, False, False
    return registry


def test_every_save_is_durable_and_kept_in_a_copy(network, monkeypatch):
    app, principal = network
    flushed = []
    real = durable.os.fsync
    monkeypatch.setattr(durable.os, "fsync", lambda fd: (flushed.append(fd), real(fd)))
    new_code(principal)
    registry = app.state.stations
    assert len(flushed) >= 2  # arquivo principal e cópia (mais as pastas, fora do Windows)
    assert registry.backup.read_bytes() == registry.path.read_bytes()
    assert not list(registry.path.parent.glob(".stations.json*.part"))


def test_unreadable_main_file_is_recovered_from_the_copy_with_revocations(network):
    app, principal = network
    kept = paired(app, principal, "192.168.0.21", "Balcão")
    gone = paired(app, principal, "192.168.0.22", "Depósito")
    gone_id = gone.me().json()["station"]["id"]
    assert principal.post(f"/api/stations/{gone_id}/revoke").status_code == 200
    registry = restart(app)
    registry.path.write_bytes(b"")  # como depois de uma queda sem fsync
    assert kept.client.get("/api/customers").status_code == 200
    assert gone.client.get("/api/customers").status_code == 401  # revogação preservada
    overview = principal.get("/api/stations").json()
    assert overview["registry"] == {"unavailable": False, "recovered_from_backup": True}
    assert any(e["action"] == "registry.recovered_from_backup" for e in overview["events"])
    assert list(registry.path.parent.glob("stations.json.corrompido-*"))  # guardado para análise
    assert json.loads(registry.path.read_text(encoding="utf-8"))["stations"]  # refeito


@pytest.mark.parametrize(
    "garbage",
    [b"", b'{"stations": [{"id": "x"', b'{"stations": "nao e lista"}', b"\xff\xfe"],
)
def test_both_files_unreadable_keep_the_main_computer_and_block_stations(network, garbage):
    app, principal = network
    station = paired(app, principal, "192.168.0.21", "Balcão")
    registry = restart(app)
    registry.path.write_bytes(garbage)
    registry.backup.write_bytes(garbage)
    principal.cookies.clear()
    me = principal.get("/api/auth/me", headers=APP)
    assert me.status_code == 200 and me.json()["server_id"] is None  # o principal continua
    principal.headers["X-CSRF-Token"] = me.json()["csrf_token"]
    assert principal.get("/api/customers").status_code == 200
    assert station.client.get("/api/customers").status_code == 401  # falha fechada
    assert station.me().status_code == 401
    overview = principal.get("/api/stations").json()
    assert overview["registry"]["unavailable"] is True and overview["stations"] == []
    assert principal.post("/api/stations/pairing").status_code == 503
    # Nada foi reescrito sozinho.
    assert registry.path.read_bytes() == garbage


def test_explicit_reset_starts_a_new_list_and_is_audited(network):
    app, principal = network
    station = paired(app, principal, "192.168.0.21", "Balcão")
    old_server = principal.get("/api/stations").json()["server"]["id"]
    registry = restart(app)
    registry.path.write_bytes(b"lixo")
    registry.backup.write_bytes(b"lixo")
    wrong = principal.post("/api/stations/registry/reset", json={"confirmation": "recomeçar"})
    assert wrong.status_code == 422
    done = principal.post("/api/stations/registry/reset", json={"confirmation": RESET_PHRASE})
    assert done.status_code == 200, done.text
    assert done.json()["server"]["id"] != old_server
    assert len(list(Path(registry.path.parent).glob("stations.json*.corrompido-*"))) == 2
    assert principal.get("/api/stations").json()["stations"] == []
    assert station.client.get("/api/customers").status_code == 401
    again = Computer(app, "192.168.0.21")
    assert again.pair(new_code(principal), "Balcão").status_code == 201
    with Session(app.state.engine) as db:
        actions = list(db.scalars(select(AuditLog.action)))
    assert "station.registry_reset" in actions


def test_station_screen_of_a_computer_without_network_mode_is_unaffected(make_app):
    app = make_app(network_mode=False)
    with TestClient(app, **PRINCIPAL) as principal:
        assert principal.get("/api/auth/me", headers=APP).status_code == 200
