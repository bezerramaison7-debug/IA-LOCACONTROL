"""Rede local com servidor real (ADR-025): o servidor de verdade (`python -m app.server`) escutando
na rede e clientes HTTP independentes, cada um com seus cookies, como duas estações e o
computador principal. Concorrência na mesma ficha, retirada concorrente da mesma unidade,
confirmação concorrente do contrato, backup durante o uso e queda e retorno do principal.

Precisa de um endereço de rede não loopback neste computador (a estação fala com ele); sem
isso o módulo é pulado.
"""

import http.cookiejar
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import PROJECT_ROOT


def own_address() -> str | None:
    """The address other computers of the network would use to reach this one."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") else address


ADDRESS = own_address()
pytestmark = pytest.mark.skipif(ADDRESS is None, reason="sem endereço de rede não loopback")
# Controlled time (M5): the server runs with this business date, whatever the machine's clock or
# time zone, so derived states ("vencendo", "vencido") never depend on when the suite runs.
FROZEN = date(2026, 11, 3)
TODAY = FROZEN.isoformat()
BOOT = (
    "import datetime, runpy, sys\n"
    "import app.core.clock as clock\n"
    f"clock.business_today = lambda: datetime.date({FROZEN.year}, {FROZEN.month}, {FROZEN.day})\n"
    "sys.argv = ['app.server', *sys.argv[1:]]\n"
    "runpy.run_module('app.server', run_name='__main__', alter_sys=True)\n"
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def cpf(seed: int) -> str:
    base = [int(d) for d in f"{seed:09d}"]
    for size in (9, 10):
        total = sum(v * (size + 1 - i) for i, v in enumerate(base[:size]))
        base.append((total * 10 % 11) % 10)
    return "".join(map(str, base))


class Browser:
    """An independent HTTP client: own cookie jar, own address, never the system proxy."""

    def __init__(self, base: str, cafile: Path | None = None):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar)]
        if cafile:
            # A real station: HTTPS verified against the store's CA, hostname/IP checked.
            context = ssl.create_default_context(cafile=str(cafile))
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = urllib.request.build_opener(*handlers)
        self.csrf = ""

    def call(self, method: str, path: str, body=None, timeout: float = 30):
        headers = {"X-LocaControl-Request": "1", "Origin": self.base}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data, headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else None

    def enter(self):
        status, body = self.call("GET", "/api/auth/me")
        assert status == 200, body
        self.csrf = body["csrf_token"]
        return body


class Server:
    def __init__(self, data: Path, port: int, **extra):
        self.data, self.port, self.process = data, port, None
        self.https_port = free_port()
        self.env = {
            **os.environ,
            "LOCACONTROL_DATA_DIR": str(data),
            "LOCACONTROL_LOCAL_MODE": "true",
            "LOCACONTROL_NETWORK_MODE": "true",
            # The test network may not be one of the private ranges: this address is.
            "LOCACONTROL_STATION_NETWORKS": json.dumps([f"{ADDRESS}/32"]),
            "LOCACONTROL_BACKUP_SCHEDULER": "false",
            "PYTHONPATH": str(PROJECT_ROOT / "backend"),
            **extra,
        }
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self.env.pop(key, None)

    def start(self):
        log = (self.data.parent / "server.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                BOOT,
                "--port",
                str(self.port),
                "--https-port",
                str(self.https_port),
            ],
            cwd=PROJECT_ROOT,
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        probe = Browser(f"http://127.0.0.1:{self.port}")
        for _ in range(300):
            if self.process.poll() is not None:
                raise RuntimeError("o servidor encerrou ao iniciar; veja server.log")
            try:
                if probe.call("GET", "/health", timeout=1)[0] == 200 and self.https_open():
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError("o servidor não respondeu")

    def https_open(self) -> bool:
        try:
            with socket.create_connection((ADDRESS, self.https_port), timeout=1):
                return True
        except OSError:
            return False

    @property
    def station_base(self) -> str:
        return f"https://{ADDRESS}:{self.https_port}"

    @property
    def cafile(self) -> Path:
        return self.data / "tls" / "ca.pem"

    def station(self) -> "Browser":
        return Browser(self.station_base, self.cafile)

    def stop(self, kill=False):
        if self.process and self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
            self.process.wait(timeout=20)


@pytest.fixture(scope="module")
def store():
    root = PROJECT_ROOT / ".test-tmp" / f"rede-{uuid4().hex}"
    root.mkdir(parents=True)
    server = Server(root / "dados", free_port())
    server.start()
    principal = Browser(f"http://127.0.0.1:{server.port}")
    principal.enter()
    # Temporary data only: this machine's disk may not keep the default reserve (A3).
    status, body = principal.call(
        "PUT",
        "/api/backups/config",
        {
            "enabled": False,
            "frequency": "20min",
            "time": "22:00",
            "keep": 14,
            "directory": "",
            "mirror_directory": "",
            "max_total_gb": 10,
            "min_free_gb": 1,
            "margin_percent": 0,
            "margin_max_gb": 0,
        },
    )
    assert status == 200, body
    stations = []
    for name in ("Balcão", "Depósito"):
        status, code = principal.call("POST", "/api/stations/pairing")
        assert status == 201, code
        station = server.station()
        status, body = station.call(
            "POST", "/api/stations/pair", {"code": code["code"], "name": name}
        )
        assert status == 201, body
        assert station.enter()["station"]["name"] == name
        stations.append(station)
    try:
        yield server, principal, stations
    finally:
        server.stop()
        shutil.rmtree(root, ignore_errors=True)


def together(*calls):
    """Runs the calls at the same instant from their own threads; returns their results."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        barrier.wait()
        results[index] = call()

    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    return results


def made(browser, path, body, expected=201):
    status, result = browser.call("POST", path, body)
    assert status == expected, result
    return result


def product(principal, code, individual=False):
    item = made(
        principal,
        "/api/products",
        {"code": code, "name": f"Produto {code}", "unit": "UN", "individual_tracking": individual},
    )
    made(
        principal,
        "/api/prices",
        {
            "product_id": item["id"],
            "period": "DIARIA",
            "effective_date": "2026-01-01",
            "amount": "90.00",
            "reason": "Tabela inicial",
        },
    )
    return item


def customer(browser, seed):
    return made(
        browser,
        "/api/customers",
        {
            "person_type": "PF",
            "legal_name": f"Cliente {seed}",
            "document": cpf(seed),
            "addresses": [
                {"street": "Rua Um", "city": "São Paulo", "state": "SP", "postal_code": "01001000"}
            ],
        },
    )


def contract(browser, person, item_id, quantity="1.000", days=10):
    draft = made(
        browser,
        "/api/contracts",
        {
            "customer_id": person["id"],
            "start_date": TODAY,
            "items": [
                {
                    "product_id": item_id,
                    "quantity": quantity,
                    "period": "DIARIA",
                    "period_count": days,
                    "unit_price": None,
                }
            ],
        },
    )
    return draft


def test_two_stations_edit_the_same_customer_at_once(store):
    _, principal, (first, second) = store
    person = customer(first, 100000001)
    status, current = second.call("GET", f"/api/customers/{person['id']}")
    assert status == 200

    def edit(browser, name):
        body = {**{k: current[k] for k in ("person_type", "document")}, "legal_name": name}
        body["addresses"] = [
            {k: a[k] for k in ("street", "city", "state", "postal_code")}
            for a in current["addresses"]
        ]
        return browser.call("PUT", f"/api/customers/{person['id']}", {**body, "version": 1})

    results = together(lambda: edit(first, "Nome do balcão"), lambda: edit(second, "Do depósito"))
    statuses = sorted(status for status, _ in results)
    assert statuses == [200, 409], results
    winner = next(body for status, body in results if status == 200)
    status, final = principal.call("GET", f"/api/customers/{person['id']}")
    assert final["legal_name"] == winner["legal_name"] and final["version"] == 2


def test_two_stations_withdraw_the_same_unit_at_once(store):
    _, principal, (first, second) = store
    generator = product(principal, "GER-REDE", individual=True)
    unit = made(principal, "/api/equipment", {"product_id": generator["id"], "code": "GER-R1"})
    person = customer(principal, 100000002)
    confirmed = []
    for _ in range(2):
        draft = contract(principal, person, generator["id"])
        confirmed.append(
            made(
                principal,
                f"/api/contracts/{draft['id']}/confirm",
                {"version": draft["version"], "reason": ""},
                expected=200,
            )
        )

    def withdraw(browser, target):
        return browser.call(
            "POST",
            f"/api/contracts/{target['id']}/withdrawals",
            {
                "occurred_on": TODAY,
                "request_key": str(uuid4()),
                "items": [
                    {
                        "contract_item_id": target["items"][0]["id"],
                        "quantity": "1.000",
                        "equipment_ids": [unit["id"]],
                    }
                ],
            },
        )

    results = together(
        lambda: withdraw(first, confirmed[0]), lambda: withdraw(second, confirmed[1])
    )
    statuses = sorted(status for status, _ in results)
    assert statuses == [201, 409], results
    status, equipment = principal.call("GET", f"/api/equipment/{unit['id']}")
    assert equipment["status"] == "LOCADO"
    states = []
    for target in confirmed:
        _, detail = principal.call("GET", f"/api/contracts/{target['id']}")
        states.append(detail["status"])
    assert sorted(states) == ["AGUARDANDO_RETIRADA", "ATIVO"]


def test_two_stations_confirm_the_same_contract_at_once(store):
    _, principal, (first, second) = store
    scaffold = product(principal, "AND-REDE")
    person = customer(principal, 100000003)
    draft = contract(first, person, scaffold["id"])

    def confirm(browser):
        return browser.call(
            "POST",
            f"/api/contracts/{draft['id']}/confirm",
            {"version": draft["version"], "reason": ""},
        )

    results = together(lambda: confirm(first), lambda: confirm(second))
    assert sorted(status for status, _ in results) == [200, 409], results
    _, detail = principal.call("GET", f"/api/contracts/{draft['id']}")
    assert detail["status"] == "AGUARDANDO_RETIRADA"
    confirmations = [e for e in detail["events"] if e["kind"] == "CONFIRMADO"]
    assert len(confirmations) == 1


def test_backup_while_both_stations_are_writing(store):
    server, principal, stations = store
    scaffold = product(principal, "EST-REDE")
    errors, done = [], []

    def work(browser, prefix):
        for n in range(15):
            status, body = browser.call(
                "POST",
                "/api/stock/movements",
                {
                    "product_id": scaffold["id"],
                    "quantity": "1.000",
                    "from_status": None,
                    "to_status": "DISPONIVEL",
                    "reason": f"Entrada {prefix} {n}",
                    "request_key": str(uuid4()),
                },
            )
            (done if status == 201 else errors).append((status, body))

    workers = [threading.Thread(target=work, args=(s, i)) for i, s in enumerate(stations)]
    for worker in workers:
        worker.start()
    backups = [principal.call("POST", "/api/backups", timeout=60) for _ in range(2)]
    for worker in workers:
        worker.join(120)
    assert not errors, errors
    assert len(done) == 30
    assert [status for status, _ in backups] == [201, 201], backups
    for _, created in backups:
        status, report = principal.call("POST", f"/api/backups/{created['name']}/verify")
        assert status == 200 and report["ok"], report
        with zipfile.ZipFile(server.data / "backups" / created["name"]) as archive:
            assert "locacontrol.db" in archive.namelist()
    status, page = principal.call("GET", f"/api/stock?q={scaffold['code']}")
    row = next(r for r in page["items"] if r["code"] == scaffold["code"])
    assert row["balances"]["DISPONIVEL"] == "30.000"


def test_main_computer_goes_down_and_comes_back(store):
    server, principal, (first, second) = store
    person = customer(first, 100000004)
    server.stop(kill=True)  # queda: sem encerramento ordenado
    with pytest.raises(OSError):
        first.call("GET", "/api/customers", timeout=3)
    server.start()
    # As estações continuam pareadas e as sessões continuam válidas; os dados ficaram.
    status, body = first.call("GET", f"/api/customers/{person['id']}")
    assert status == 200 and body["document"] == person["document"]
    assert second.call("GET", "/api/customers")[0] == 200
    assert second.enter()["station"]["name"] == "Depósito"
    customer(second, 100000005)


def test_the_server_uses_the_controlled_business_date(store):
    """Regression for M5: a contract due within the warning window is "vencendo" and one due
    later is "ativo", decided by the frozen date, not by the machine's clock."""
    _, principal, _ = store
    item = product(principal, "REL-REDE")
    made(
        principal,
        "/api/stock/movements",
        {
            "product_id": item["id"],
            "quantity": "2.000",
            "from_status": None,
            "to_status": "DISPONIVEL",
            "reason": "Entrada",
            "request_key": str(uuid4()),
        },
    )
    person = customer(principal, 100000006)
    states = {}
    for days in (2, 10):
        draft = contract(principal, person, item["id"], days=days)
        confirmed = made(
            principal,
            f"/api/contracts/{draft['id']}/confirm",
            {"version": draft["version"], "reason": ""},
            expected=200,
        )
        status, body = principal.call(
            "POST",
            f"/api/contracts/{confirmed['id']}/withdrawals",
            {
                "occurred_on": TODAY,
                "request_key": str(uuid4()),
                "items": [{"contract_item_id": confirmed["items"][0]["id"], "quantity": "1.000"}],
            },
        )
        assert status == 201, body
        states[days] = principal.call("GET", f"/api/contracts/{confirmed['id']}")[1]["status"]
    assert states == {2: "VENCENDO", 10: "ATIVO"}


def pair_station(principal, server, name):
    status, code = principal.call("POST", "/api/stations/pairing")
    assert status == 201, code
    station = server.station()
    status, body = station.call("POST", "/api/stations/pair", {"code": code["code"], "name": name})
    assert status == 201, body
    station.enter()
    return station


def test_a_copied_credential_is_detected_on_the_real_server():
    """A1 end to end: real server, independent clients, real cookies. Short rotation and grace
    (1 s) instead of 15 min and 2 min, so the test runs in seconds."""
    root = PROJECT_ROOT / ".test-tmp" / f"rede-clone-{uuid4().hex}"
    root.mkdir(parents=True)
    server = Server(
        root / "dados",
        free_port(),
        LOCACONTROL_STATION_TOKEN_ROTATE_SECONDS="1",
        LOCACONTROL_STATION_TOKEN_GRACE_SECONDS="1",
    )
    server.start()
    try:
        principal = Browser(f"http://127.0.0.1:{server.port}")
        principal.enter()
        legit = pair_station(principal, server, "Balcão")
        assert legit.call("GET", "/api/customers")[0] == 200
        clone = Browser(legit.base, server.cafile)
        for cookie in legit.jar:
            clone.jar.set_cookie(cookie)
        clone.csrf = legit.csrf
        assert clone.call("GET", "/api/customers")[0] == 200  # antes da rotação, funciona
        # Both copies keep being used; whichever presents a retired token after the grace
        # period reveals the copy (the order depends on who receives the new token first).
        for _ in range(4):
            time.sleep(1.2)
            legit.call("GET", "/api/customers")
            clone.call("GET", "/api/customers")
        assert legit.call("GET", "/api/customers")[0] == 401
        assert clone.call("GET", "/api/customers")[0] == 401
        status, stations = principal.call("GET", "/api/stations")
        assert stations["stations"][0]["revoked_reason"] == "reuso de credencial detectado"
        station_id = stations["stations"][0]["id"]
        status, audit = principal.call("GET", f"/api/audit-logs?station_id={station_id}&limit=100")
        assert "station.reuse_detected" in [item["action"] for item in audit["items"]]
    finally:
        server.stop()
        shutil.rmtree(root, ignore_errors=True)


# ---- "Conectar à loja": the station authenticates the CA before trusting it (P1-E) -----------


def test_connect_trusts_the_ca_only_with_the_right_code_and_a_matching_server(store, tmp_path):
    from app.network import connect as station_setup

    server, principal, _ = store
    status, code = principal.call("POST", "/api/stations/pairing")
    assert status == 201
    trusted = []

    def record_trust(der, previous):
        trusted.append((der, previous))

    with pytest.raises(station_setup.ConnectError, match="NÃO confere"):
        station_setup.connect(
            ADDRESS,
            "AAAA-" + code["code"][5:],
            server.https_port,
            root=tmp_path,
            trust=record_trust,
            open_browser=False,
        )
    assert trusted == [] and not (tmp_path / "station.json").exists()
    record = station_setup.connect(
        ADDRESS,
        code["code"],
        server.https_port,
        root=tmp_path,
        trust=record_trust,
        open_browser=False,
    )
    assert len(trusted) == 1 and trusted[0][0] == ssl.PEM_cert_to_DER_cert(
        server.cafile.read_text()
    )
    assert record["ca_fingerprint"].count(":") == 31
    url = station_setup.pairing_url(ADDRESS, server.https_port, code["code"])
    assert url.startswith(f"https://{ADDRESS}:{server.https_port}/#/parear?codigo=")
    # O código continua válido para o pareamento no navegador (só a CA foi conferida).
    station = server.station()
    paired = station.call("POST", "/api/stations/pair", {"code": code["code"], "name": "Conectada"})
    assert paired[0] == 201
    # Reconectar substitui a CA registrada antes (o anterior é informado para ser removido).
    status, again = principal.call("POST", "/api/stations/pairing")
    station_setup.connect(
        ADDRESS,
        again["code"],
        server.https_port,
        root=tmp_path,
        trust=record_trust,
        open_browser=False,
    )
    assert trusted[-1][1] == record["ca_thumbprint"]
    removed = []
    assert station_setup.disconnect(root=tmp_path, untrust=removed.append)
    assert removed == [record["ca_thumbprint"]] and not (tmp_path / "station.json").exists()


def tls_impostor(tmp_path, handler_body):
    """A machine in the middle: its own CA and certificate, answering /api/stations/ca."""
    import datetime as dt
    import http.server
    import ipaddress

    from app.network.tls import LocalAuthority

    impostor = LocalAuthority(tmp_path / "atacante")
    impostor.ensure(
        ["localhost"],
        [ipaddress.ip_address("127.0.0.1")],
        now=dt.datetime.now(dt.UTC),
        networks=[ipaddress.ip_network(f"{ADDRESS}/32")],
    )
    certificate, key = impostor.sign(
        ["localhost"], [ipaddress.ip_address(ADDRESS)], 30, dt.datetime.now(dt.UTC)
    )
    from cryptography.hazmat.primitives import serialization

    certfile, keyfile = tmp_path / "mitm.pem", tmp_path / "mitm.key"
    certfile.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    body = json.dumps(handler_body(impostor)).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer((ADDRESS, 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile, keyfile)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_connect_refuses_a_machine_in_the_middle(store, tmp_path):
    from app.network import connect as station_setup

    server, principal, _ = store
    status, code = principal.call("POST", "/api/stations/pairing")
    real_pem = server.cafile.read_text()
    real = station_setup.fetch_ca(ADDRESS, server.https_port)
    # 1) O intermediário oferece a própria CA com a prova verdadeira: a prova não confere.
    own = tls_impostor(
        tmp_path / "a", lambda ca: {"ca_pem": ca.ca_pem().decode(), "proof": real["proof"]}
    )
    # 2) O intermediário repassa a CA e a prova verdadeiras, mas apresenta o próprio certificado:
    #    a conexão fixada na CA autenticada falha.
    relay = tls_impostor(tmp_path / "b", lambda ca: {"ca_pem": real_pem, "proof": real["proof"]})
    try:
        for mitm, expected in ((own, "NÃO confere"), (relay, "Não foi possível falar")):
            with pytest.raises(station_setup.ConnectError, match=expected):
                station_setup.connect(
                    ADDRESS,
                    code["code"],
                    mitm.server_address[1],
                    root=tmp_path,
                    trust=lambda *_: pytest.fail("confiou numa CA não autenticada"),
                    open_browser=False,
                )
    finally:
        own.shutdown()
        relay.shutdown()
    assert not (tmp_path / "station.json").exists()
