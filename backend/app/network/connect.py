"""Connect a station to the store (P1-E): trust the main computer's CA only after authenticating it.

`LocaControl.exe conectar --servidor <endereço> --codigo <código>`, run by the installer option
"Conectar à loja" (as administrator):

1. downloads the CA and its proof from `https://<server>:8443/api/stations/ca` **without
   trusting this connection** (there is no trust yet);
2. accepts the CA only if `HMAC-SHA256(code, CA)` equals the proof — a person read the code on
   the main computer, so a machine in the middle cannot produce a valid proof for its own CA;
3. connects again **pinned to that CA** and checks the server's certificate and address;
4. installs the CA in the computer's "Trusted Root Certification Authorities" (Windows), replacing
   a CA it installed before for that store, and records what it did in `station.json`;
5. opens the browser on the pairing page with the code in the URL fragment (never sent to the
   server nor written to its logs).
"""

import json
import os
import ssl
import subprocess
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

from app.core.config import data_root
from app.core.durable import write_durably
from app.network.tls import fingerprint, normalise, verify_ca_proof

STATION_FILE = "station.json"
DEFAULT_PORT = 8443


class ConnectError(RuntimeError):
    pass


def fetch_ca(server: str, port: int, timeout: float = 15) -> dict:
    """The CA and its proof; this connection is deliberately not trusted (see step 2)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return get_json(f"https://{host(server)}:{port}/api/stations/ca", context, timeout)


def get_json(url: str, context, timeout: float) -> dict:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )
    request = urllib.request.Request(url, headers={"X-LocaControl-Request": "1"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read())
    except OSError as error:
        raise ConnectError(f"Não foi possível falar com o computador principal: {error}") from error


def host(server: str) -> str:
    return f"[{server}]" if ":" in server and not server.startswith("[") else server


def pem_to_der(pem: str) -> bytes:
    return ssl.PEM_cert_to_DER_cert(pem)


def authenticate(server: str, code: str, port: int = DEFAULT_PORT) -> dict:
    """Steps 1-3. Returns the authenticated CA; raises ConnectError otherwise (nothing trusted)."""
    data = fetch_ca(server, port)
    try:
        der = pem_to_der(data["ca_pem"])
    except (KeyError, ValueError, TypeError) as error:
        raise ConnectError("O computador principal respondeu sem um certificado válido.") from error
    if not data.get("proof"):
        raise ConnectError(
            "Não há código de pareamento válido no computador principal. Gere um novo código e "
            "tente de novo."
        )
    if not verify_ca_proof(der, data["proof"], code):
        raise ConnectError(
            "A identidade do computador principal NÃO confere com o código: nada foi instalado. "
            "Confira o código e o endereço; se persistir, pode haver interceptação na rede."
        )
    # Pinned to the authenticated CA: the server must present a certificate it issued.
    with tempfile.TemporaryDirectory() as folder:
        cafile = Path(folder) / "ca.pem"
        cafile.write_text(data["ca_pem"], encoding="ascii")
        context = ssl.create_default_context(cafile=str(cafile))
        get_json(f"https://{host(server)}:{port}/api/stations/ca", context, 15)
    return {"der": der, "pem": data["ca_pem"], "fingerprint": fingerprint(der)}


# ---- trust store -------------------------------------------------------------------------


def thumbprint(der: bytes) -> str:
    import hashlib

    return hashlib.sha1(der).hexdigest().upper()  # how certutil names a certificate


def windows_trust(der: bytes, previous: str | None):
    """Adds the CA to the machine's Root store (administrator) and removes the previous one."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "locacontrol-ca.cer"
        path.write_bytes(der)
        run(["certutil", "-f", "-addstore", "Root", str(path)])
    if previous and previous != thumbprint(der):
        run(["certutil", "-delstore", "Root", previous], check=False)


def windows_untrust(previous: str):
    run(["certutil", "-delstore", "Root", previous], check=False)


def run(command, check=True):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(command, capture_output=True, text=True, creationflags=flags)
    if check and result.returncode:
        raise ConnectError(
            "O Windows não aceitou instalar o certificado da loja (execute como administrador): "
            + (result.stdout + result.stderr).strip()[-300:]
        )
    return result


def station_file(root: Path | None = None) -> Path:
    return (root or data_root()) / STATION_FILE


def read_station(root: Path | None = None) -> dict:
    try:
        return json.loads(station_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pairing_url(server: str, port: int, code: str) -> str:
    grouped = "-".join(normalise(code)[i : i + 4] for i in range(0, len(normalise(code)), 4))
    return f"https://{host(server)}:{port}/#/parear?codigo={grouped}"


def connect(
    server: str,
    code: str,
    port: int = DEFAULT_PORT,
    root: Path | None = None,
    trust=None,
    open_browser: bool = True,
) -> dict:
    """Steps 1-5. `trust(der, previous_thumbprint)` installs the CA (Windows by default)."""
    authority = authenticate(server, code, port)
    previous = read_station(root).get("ca_thumbprint")
    if trust is None:
        if os.name != "nt":
            raise ConnectError("A instalação da confiança só é feita no Windows.")
        trust = windows_trust
    trust(authority["der"], previous)
    record = {
        "server": server,
        "port": port,
        "url": f"https://{host(server)}:{port}/",
        "ca_fingerprint": authority["fingerprint"],
        "ca_thumbprint": thumbprint(authority["der"]),
    }
    path = station_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_durably(path, json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
    if open_browser:
        webbrowser.open(pairing_url(server, port, code))
    return record


def disconnect(root: Path | None = None, untrust=None) -> bool:
    """Uninstalling a station: removes the CA it installed. Returns whether there was one."""
    previous = read_station(root).get("ca_thumbprint")
    if not previous:
        return False
    (untrust or (windows_untrust if os.name == "nt" else (lambda _p: None)))(previous)
    station_file(root).unlink(missing_ok=True)
    return True
