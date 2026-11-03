"""Rede local e pareamento (ADR-025): código temporário, credencial própria por estação, limite de
tentativas, revogação, funções só do computador principal, origem/CSRF preservados e o efeito
de uma restauração de backup sobre pareamentos e revogações."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, AuthSession
from app.core.config import Settings
from app.main import create_app
from app.network.stations import CODE_ATTEMPTS, PEER_ATTEMPTS, STATION_COOKIE

APP = {"X-LocaControl-Request": "1"}
PRINCIPAL = {"base_url": "http://127.0.0.1:8000", "client": ("127.0.0.1", 50000)}
SERVER = "https://192.168.0.10:8443"  # stations only over HTTPS (P1-E)
CUSTOMER = {
    "person_type": "PF",
    "legal_name": "Cliente da rede",
    "document": "52998224725",
    "addresses": [
        {"street": "Rua Um, 20", "city": "São Paulo", "state": "SP", "postal_code": "01001000"}
    ],
}


@pytest.fixture
def make_app(migrated_config, tmp_path):
    def build(**values):
        values = {"network_mode": True, **values}
        settings = Settings(
            _env_file=None,
            local_mode=True,
            database_url=migrated_config.attributes["database_url"],
            document_directory=tmp_path / "documents",
            fiscal_directory=tmp_path / "fiscal",
            import_directory=tmp_path / "imports",
            backup_directory=tmp_path / "backups",
            backup_scheduler=False,
            **values,
        )
        return create_app(settings)

    return build


class Computer:
    """One browser on one computer: its own cookies, address and the page origin it sends."""

    def __init__(self, app, peer: str, server: str = SERVER):
        self.client = TestClient(app, base_url=server, client=(peer, 50000))
        self.origin = {"Origin": server, **APP}
        self.csrf = ""

    def me(self):
        response = self.client.get("/api/auth/me", headers=APP)
        if response.status_code == 200:
            self.csrf = response.json()["csrf_token"]
        return response

    def write(self, method: str, path: str, body=None, **headers):
        return self.client.request(
            method,
            path,
            json=body,
            headers={**self.origin, "X-CSRF-Token": self.csrf, **headers},
        )

    def pair(self, code: str, name: str):
        return self.client.post(
            "/api/stations/pair", json={"code": code, "name": name}, headers=self.origin
        )


@pytest.fixture
def network(make_app):
    app = make_app()
    with TestClient(app, **PRINCIPAL) as principal:
        me = principal.get("/api/auth/me", headers=APP)
        assert me.status_code == 200, me.text
        principal.headers.update(
            {"Origin": "http://127.0.0.1:8000", **APP, "X-CSRF-Token": me.json()["csrf_token"]}
        )
        yield app, principal


def new_code(principal) -> str:
    response = principal.post("/api/stations/pairing")
    assert response.status_code == 201, response.text
    return response.json()["code"]


def paired(app, principal, peer: str, name: str) -> Computer:
    computer = Computer(app, peer)
    response = computer.pair(new_code(principal), name)
    assert response.status_code == 201, response.text
    assert computer.me().status_code == 200
    return computer


def test_station_pairs_with_the_temporary_code_and_gets_its_own_credential(network):
    app, principal = network
    station = Computer(app, "192.168.0.21")
    refused = station.me()
    assert refused.status_code == 401
    assert refused.headers["X-LocaControl-Pairing"] == "available"
    assert refused.headers["X-LocaControl-Edition"] == "local"
    # Uma estação sem pareamento não gera códigos para si mesma.
    assert station.write("POST", "/api/stations/pairing").status_code == 401

    code = new_code(principal)
    # 26 caracteres de 32 símbolos (130 bits), em grupos de 4.
    assert len(code.replace("-", "")) == 26 and code[4] == "-"
    wrong = station.pair("AAAA-AAAA", "Balcão 1")
    assert wrong.status_code == 403 and f"Restam {CODE_ATTEMPTS - 1}" in wrong.json()["detail"]
    done = station.pair(code.lower().replace("-", " "), "Balcão 1")  # digitação tolerante
    assert done.status_code == 201, done.text
    assert done.cookies.get(STATION_COOKIE)
    assert done.cookies.get(STATION_COOKIE) not in json.dumps(done.json())
    assert "token_hash" not in json.dumps(done.json())
    assert station.pair(code, "Balcão 2").status_code == 403  # código de uso único

    me = station.me()
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["station"]["name"] == "Balcão 1" and body["network"] is True
    principal_me = principal.get("/api/auth/me").json()
    assert principal_me["station"] is None
    # Três identidades distintas: base/loja, servidor e estação.
    ids = {body["installation_id"], body["server_id"], body["station"]["id"]}
    assert len(ids) == 3 and principal_me["installation_id"] == body["installation_id"]
    assert principal_me["server_id"] == body["server_id"]

    created = station.write("POST", "/api/customers", CUSTOMER)
    assert created.status_code == 201, created.text
    with Session(app.state.engine) as db:
        label = db.scalar(
            select(AuditLog.actor_label).where(AuditLog.action == "customers.create")
        ) or db.scalar(select(AuditLog.actor_label).order_by(AuditLog.id.desc()))
    assert "estação Balcão 1 (" in label and "instalação" in label
    # O registro guarda só hashes.
    registry = Path(app.state.stations.path).read_text(encoding="utf-8")
    assert (
        done.cookies.get(STATION_COOKIE) not in registry and code.replace("-", "") not in registry
    )
    activity = principal.get(f"/api/stations/{body['station']['id']}/activity").json()
    assert {e["action"] for e in activity["events"]} == {"station.paired"}
    assert activity["audit"]


def test_attempt_limits_per_code_and_per_computer(network):
    app, principal = network
    station = Computer(app, "192.168.0.22")
    code = new_code(principal)
    for _ in range(CODE_ATTEMPTS):
        assert station.pair("ZZZZ-ZZZZ", "Balcão").status_code == 403
    # Esgotadas as tentativas, o código foi cancelado: nem o certo vale mais.
    assert station.pair(code, "Balcão").status_code == 403
    assert principal.get("/api/stations").json()["pairing"] is None
    for _ in range(PEER_ATTEMPTS):
        station.pair("ZZZZ-ZZZZ", "Balcão")
    new_code(principal)
    blocked = station.pair("ZZZZ-ZZZZ", "Balcão")
    assert blocked.status_code == 429
    # Outro computador da rede continua podendo parear.
    other = Computer(app, "192.168.0.23")
    assert other.pair(new_code(principal), "Depósito").status_code == 201


def test_only_the_store_network_and_this_server_address_can_pair(network, make_app):
    app, principal = network
    code = new_code(principal)
    outsider = Computer(app, "8.8.8.8")
    response = outsider.me()
    assert response.status_code == 401 and "X-LocaControl-Pairing" not in response.headers
    assert outsider.pair(code, "Fora").status_code == 403
    # Nome estranho que aponta para este servidor (DNS rebinding): recusado.
    rebinding = Computer(app, "192.168.0.30", server="https://loja.exemplo.com:8443")
    assert rebinding.me().status_code == 401
    assert rebinding.pair(code, "Rebinding").status_code == 403
    # Página de outro site tentando parear pela estação.
    foreign = Computer(app, "192.168.0.31")
    foreign.origin = {"Origin": "http://outro-site.exemplo", **APP}
    assert foreign.pair(code, "Outro site").status_code == 403
    # Sem o cabeçalho do aplicativo também não.
    bare = TestClient(app, base_url=SERVER, client=("192.168.0.32", 50000))
    assert bare.post("/api/stations/pair", json={"code": code, "name": "x"}).status_code == 403
    # Rede desligada: nada de pareamento nem sessão para outros computadores.
    closed = make_app(network_mode=False)
    with TestClient(closed, **PRINCIPAL):
        station = Computer(closed, "192.168.0.21")
        response = station.me()
        assert response.status_code == 401 and "X-LocaControl-Pairing" not in response.headers
        assert station.pair("AAAA-AAAA", "Balcão").status_code == 409


def test_station_keeps_origin_and_csrf_checks(network):
    app, principal = network
    station = paired(app, principal, "192.168.0.21", "Balcão")
    assert (
        station.write("POST", "/api/customers", CUSTOMER, **{"X-CSRF-Token": ""}).status_code == 403
    )
    foreign = station.client.post(
        "/api/customers",
        json=CUSTOMER,
        headers={"Origin": "http://outro-site.exemplo", **APP, "X-CSRF-Token": station.csrf},
    )
    assert foreign.status_code == 403
    assert station.write("POST", "/api/customers", CUSTOMER).status_code == 201


def test_sensitive_functions_stay_on_the_main_computer(network):
    app, principal = network
    station = paired(app, principal, "192.168.0.21", "Balcão")
    made = station.write("POST", "/api/backups")  # backup manual: permitido
    assert made.status_code == 201, made.text
    name = made.json()["name"]
    assert station.client.get("/api/backups").status_code == 200
    config = {
        "enabled": True,
        "frequency": "20min",
        "time": "22:00",
        "keep": 14,
        "directory": "",
        "mirror_directory": "",
    }
    denied = [
        station.write("PUT", "/api/backups/config", config),
        station.client.get(f"/api/backups/{name}/download"),
        station.write(
            "POST", f"/api/backups/{name}/restore", {"confirmation": f"RESTAURAR {name}"}
        ),
        station.client.post(
            "/api/backups/import",
            files={"file": ("x.zip", b"PK", "application/zip")},
            headers={**station.origin, "X-CSRF-Token": station.csrf},
        ),
        station.client.get("/api/stations"),
        station.write("POST", "/api/stations/pairing"),
        station.write("POST", f"/api/stations/{station.me().json()['station']['id']}/revoke"),
    ]
    for response in denied:
        assert response.status_code == 403, response.text
        assert "computador principal" in response.json()["detail"]
    assert principal.get(f"/api/backups/{name}/download").status_code == 200


def test_revocation_ends_the_station_at_once_and_keeps_the_others(network):
    app, principal = network
    first = paired(app, principal, "192.168.0.21", "Balcão")
    second = paired(app, principal, "192.168.0.22", "Depósito")
    station_id = first.me().json()["station"]["id"]
    response = principal.post(f"/api/stations/{station_id}/revoke")
    assert response.status_code == 200 and response.json()["station"]["revoked_at"]
    assert first.client.get("/api/customers").status_code == 401
    again = first.me()
    assert again.status_code == 401 and again.headers["X-LocaControl-Pairing"] == "available"
    with Session(app.state.engine) as db:
        left = db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.station_id == station_id)
        )
    assert left == 0
    assert second.client.get("/api/customers").status_code == 200
    listing = principal.get("/api/stations").json()
    assert [s["name"] for s in listing["stations"]] == ["Depósito", "Balcão"]
    assert all("token_hash" not in s for s in listing["stations"])


def test_stolen_cookies_do_not_work_from_another_computer(network):
    app, principal = network
    station = paired(app, principal, "192.168.0.21", "Balcão")
    # O cookie de sessão sem o cookie da estação não vale.
    thief = Computer(app, "192.168.0.40")
    thief.client.cookies.set("locacontrol_session", station.client.cookies["locacontrol_session"])
    assert thief.client.get("/api/customers").status_code == 401
    # A sessão do computador principal não vale vinda da rede.
    copy = Computer(app, "192.168.0.41")
    copy.client.cookies.set("locacontrol_session", principal.cookies["locacontrol_session"])
    assert copy.client.get("/api/customers").status_code == 401
    # Os cookies da estação de outro endereço fora da rede da loja também não.
    outside = Computer(app, "8.8.4.4")
    for name in ("locacontrol_session", STATION_COOKIE):
        outside.client.cookies.set(name, station.client.cookies[name])
    assert outside.client.get("/api/customers").status_code == 401


def test_drafts_of_each_station_are_kept_apart(network):
    app, principal = network
    first = paired(app, principal, "192.168.0.21", "Balcão")
    second = paired(app, principal, "192.168.0.22", "Depósito")
    for computer, note in ((first, "balcão"), (second, "depósito")):
        saved = computer.write("PUT", "/api/drafts/quote/new", {"payload": {"notes": note}})
        assert saved.status_code == 200, saved.text
    assert first.client.get("/api/drafts/quote/new").json()["draft"]["payload"]["notes"] == "balcão"
    assert second.client.get("/api/drafts/quote/new").json()["draft"]["payload"]["notes"] == (
        "depósito"
    )
    assert principal.get("/api/drafts/quote/new").json()["draft"] is None


def test_restoring_a_backup_does_not_change_pairings_or_revocations(network):
    app, principal = network
    kept = paired(app, principal, "192.168.0.21", "Balcão")
    revoked = paired(app, principal, "192.168.0.22", "Depósito")
    made = principal.post("/api/backups")
    assert made.status_code == 201, made.text
    name = made.json()["name"]
    revoked_id = revoked.me().json()["station"]["id"]
    assert principal.post(f"/api/stations/{revoked_id}/revoke").status_code == 200
    later = paired(app, principal, "192.168.0.23", "Escritório")

    done = principal.post(
        f"/api/backups/{name}/restore", json={"confirmation": f"RESTAURAR {name}"}
    )
    assert done.status_code == 200, done.text
    # A base voltou ao backup (que tinha a sessão da estação revogada), mas a revogação vale.
    assert revoked.client.get("/api/customers").status_code == 401
    assert revoked.me().status_code == 401
    # A estação pareada depois do backup continua pareada: abre uma sessão nova sozinha.
    assert later.client.get("/api/customers").status_code == 401  # a sessão sumiu com a base
    assert later.me().status_code == 200
    assert later.client.get("/api/customers").status_code == 200
    assert kept.me().status_code == 200
    names = {s["name"]: s["revoked_at"] for s in principal_overview(principal)["stations"]}
    assert names["Depósito"] and not names["Balcão"] and not names["Escritório"]


def principal_overview(principal):
    me = principal.get("/api/auth/me")
    principal.headers["X-CSRF-Token"] = me.json()["csrf_token"]
    response = principal.get("/api/stations")
    assert response.status_code == 200, response.text
    return response.json()


def test_server_listens_on_the_network_only_over_https_in_the_network_mode():
    from app.server import listeners

    def hosts(tls=("cert", "key", "senha"), **values):
        found = listeners(Settings(_env_file=None, **values), 8000, 8443, tls)
        return [(e["host"], e["port"], "ssl_certfile" in e) for e in found]

    assert hosts() == [("127.0.0.1", 8000, False)]
    assert hosts(local_mode=True) == [("127.0.0.1", 8000, False)]
    assert hosts(network_mode=True) == [("127.0.0.1", 8000, False)]  # exige a edição local
    network = hosts(local_mode=True, network_mode=True)
    # HTTP só neste computador; a rede só por HTTPS.
    assert network == [("127.0.0.1", 8000, False), ("0.0.0.0", 8443, True)]
    # Sem certificado utilizável a rede não abre (falha fechada).
    assert hosts(None, local_mode=True, network_mode=True) == [("127.0.0.1", 8000, False)]


def test_stations_are_refused_over_plain_http(network):
    app, principal = network
    plain = Computer(app, "192.168.0.21", server="http://192.168.0.10:8000")
    refused = plain.pair(new_code(principal), "Balcão")
    assert refused.status_code == 403  # pareamento nunca por HTTP
    station = paired(app, principal, "192.168.0.22", "Depósito")
    copy = Computer(app, "192.168.0.22", server="http://192.168.0.10:8000")
    for name in ("locacontrol_session", STATION_COOKIE):
        copy.client.cookies.set(name, station.client.cookies[name])
    assert copy.client.get("/api/customers").status_code == 401  # credencial por HTTP: recusada


def test_station_cookies_are_secure_over_https(network):
    app, principal = network
    station = Computer(app, "192.168.0.21")
    done = station.pair(new_code(principal), "Balcão")
    assert "secure" in done.headers["set-cookie"].lower()
    me = station.client.get("/api/auth/me", headers=APP)
    assert all("secure" in v.lower() for k, v in me.headers.items() if k == "set-cookie")
