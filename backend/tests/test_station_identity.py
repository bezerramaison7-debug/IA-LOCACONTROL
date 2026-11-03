# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
"""Identidade inequívoca da estação na auditoria (M4): o id da estação gravado como dado, filtros
por esse id, nomes sem imitação de outra estação e únicos entre as ativas."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_stations import CUSTOMER, Computer, make_app, network, new_code, paired  # noqa: F401

from app.auth.models import AuditLog


def test_station_names_cannot_imitate_another_station_or_repeat_an_active_one(network):
    app, principal = network
    real = paired(app, principal, "192.168.0.21", "Balcão")
    real_id = real.me().json()["station"]["id"]
    code = new_code(principal)
    impostor = Computer(app, "192.168.0.24")
    for name in (f"Falsa ({real_id[:8]})", "Nome\ncom quebra", "x" * 41, ""):
        assert impostor.pair(code, name).status_code == 422, name
    duplicate = impostor.pair(code, "balcão")  # maiúsculas e minúsculas não importam
    assert duplicate.status_code == 409 and "Já existe" in duplicate.json()["detail"]
    # O código continua valendo: a mesma estação tenta outro nome.
    assert impostor.pair(code, "Depósito 2").status_code == 201
    # Nome de estação revogada pode ser reaproveitado.
    assert principal.post(f"/api/stations/{real_id}/revoke").status_code == 200
    again = Computer(app, "192.168.0.25")
    assert again.pair(new_code(principal), "Balcão").status_code == 201


def test_audit_records_the_station_id_and_activity_is_filtered_by_it(network):
    app, principal = network
    first = paired(app, principal, "192.168.0.21", "A" * 40)
    second = paired(app, principal, "192.168.0.22", "Depósito")
    first_id = first.me().json()["station"]["id"]
    second_id = second.me().json()["station"]["id"]
    assert first.write("POST", "/api/customers", CUSTOMER).status_code == 201
    other = {**CUSTOMER, "document": "11144477735"}
    assert second.write("POST", "/api/customers", other).status_code == 201
    assert principal.post("/api/stations/pairing").status_code == 201
    with Session(app.state.engine) as db:
        rows = list(db.scalars(select(AuditLog)))
    created = {r.station_id for r in rows if r.action == "master.created"}
    assert created == {first_id, second_id}
    principal_rows = [r for r in rows if r.action == "station.pairing_started"]
    assert principal_rows and all(r.station_id is None for r in principal_rows)
    assert all(len(r.actor_label) <= 100 for r in rows)
    first_activity = principal.get(f"/api/stations/{first_id}/activity").json()["audit"]
    assert first_activity and all(
        db_row.station_id == first_id
        for db_row in rows
        if db_row.id in {entry["id"] for entry in first_activity}
    )
    filtered = principal.get("/api/audit-logs", params={"station_id": second_id, "limit": 100})
    body = filtered.json()
    assert body["total"] == len(body["items"]) > 0
    assert {item["station_id"] for item in body["items"]} == {second_id}
