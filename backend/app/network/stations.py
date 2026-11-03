"""Stations of the store network (P1-D, ADR-025): pairing codes, station credentials, revocation.

The registry is a JSON file beside the database, outside the database and outside backup sets:
restoring a backup never brings back a revoked station nor disconnects one paired after it
(decision of the user, 2026-11-02). It also holds the identity of this server, distinct from the
identity of the database/store (`app_settings.installation`) and from each station's id.

Only hashes of codes and station tokens are stored. One process uses the file (the installation
lock guarantees it); a thread lock serialises changes inside it.
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

REGISTRY_FILE = "stations.json"
STATION_COOKIE = "locacontrol_station"
# Browsers keep a cookie for at most about 400 days; it is renewed at every new session.
STATION_COOKIE_DAYS = 400
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: read aloud without doubt
CODE_LENGTH = 8
CODE_MINUTES = 10
CODE_ATTEMPTS = 5
# Wrong codes from one address: after this many in the window, that address waits.
PEER_ATTEMPTS = 10
PEER_WINDOW_SECONDS = 15 * 60
EVENT_LIMIT = 500
# last_seen is written at most this often per station, not at every request.
SEEN_EVERY_SECONDS = 60
PRIVATE_NETWORKS = [
    ipaddress.ip_network(n)
    for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7", "fe80::/10")
]
NOT_PAIRED = "Este computador não tem acesso ao LocaControl desta loja."
PRINCIPAL_ONLY = "Disponível apenas no computador principal da loja."


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalise(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def peer_address(request: Request):
    try:
        return ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        return None


def station_networks(settings) -> list:
    extra = []
    for value in settings.station_networks:
        try:
            extra.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            logger.warning("Rede de estações inválida ignorada: %s", value)
    return PRIVATE_NETWORKS + extra


def from_store_network(request: Request) -> bool:
    """The peer is on the store network (never loopback: that is the main computer)."""
    settings = request.app.state.settings
    peer = peer_address(request)
    if not (settings.local_mode and settings.network_mode) or peer is None or peer.is_loopback:
        return False
    if peer.version == 6 and peer.ipv4_mapped:
        peer = peer.ipv4_mapped
    return any(peer in network for network in station_networks(settings))


def store_host(request: Request) -> bool:
    """The address typed in the station's browser: an IP literal on the store network or a name
    of this server. Any other name could be DNS rebinding and is refused."""
    settings = request.app.state.settings
    host = (request.url.hostname or "").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        names = {socket.gethostname().lower(), *(h.lower() for h in settings.station_hosts)}
        names |= {name + ".local" for name in list(names)}
        return host in names
    return any(address in network for network in station_networks(settings))


def same_origin(request: Request) -> bool:
    """Origin of a station's page: exactly the address it used to reach this server."""
    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    return bool(origin) and origin == f"{request.url.scheme}://{host}" and store_host(request)


def station_request(request: Request) -> bool:
    """A request from the store network that a browser page of this server sent."""
    origin = request.headers.get("origin")
    return (
        from_store_network(request)
        and store_host(request)
        and request.headers.get("x-locacontrol-request") == "1"
        and (origin is None or same_origin(request))
    )


def principal_only(request: Request):
    """Route guard after authentication: refuses a station (decision of the user).

    Declared after the user dependency, which records who is calling; if that has not run,
    it fails closed instead of treating the caller as the main computer.
    """
    if not hasattr(request.state, "station") or request.state.station:
        raise HTTPException(403, PRINCIPAL_ONLY)


class StationRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self._cache: dict | None = None

    # ---- storage -------------------------------------------------------------------

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError) as error:
            # Never start empty over an unreadable registry: that would drop revocations.
            raise HTTPException(503, "Lista de estações ilegível; nada foi alterado.") from error
        data.setdefault("server", {"id": str(uuid.uuid4()), "created_at": int(time.time())})
        data.setdefault("stations", [])
        data.setdefault("pairing", None)
        data.setdefault("failures", {})
        data.setdefault("events", [])
        self._cache = data
        return data

    def _save(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        part = self.path.with_name(f".{self.path.name}.part")
        part.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        part.replace(self.path)
        self._cache = data

    def _event(self, data: dict, action: str, station: dict | None = None, **extra):
        entry = {"at": int(time.time()), "action": action, **extra}
        if station:
            entry |= {"station_id": station["id"], "station_name": station["name"]}
        data["events"] = ([entry] + data["events"])[:EVENT_LIMIT]

    # ---- identity ------------------------------------------------------------------

    def server(self) -> dict:
        with self.lock:
            data = self._load()
            if not self.path.exists():
                self._save(data)
            return data["server"]

    # ---- pairing -------------------------------------------------------------------

    def start_pairing(self) -> dict:
        """A new code replaces any previous one; only its hash is kept."""
        with self.lock:
            data = self._load()
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            now = int(time.time())
            data["pairing"] = {
                "code_hash": digest(code),
                "created_at": now,
                "expires_at": now + CODE_MINUTES * 60,
                "attempts": 0,
            }
            self._event(data, "pairing.started")
            self._save(data)
            return {
                "code": code[:4] + "-" + code[4:],
                "expires_at": now + CODE_MINUTES * 60,
                "attempts_left": CODE_ATTEMPTS,
            }

    def cancel_pairing(self):
        with self.lock:
            data = self._load()
            if data["pairing"]:
                data["pairing"] = None
                self._event(data, "pairing.cancelled")
                self._save(data)

    def pairing(self) -> dict | None:
        with self.lock:
            current = self._load()["pairing"]
            if not current or current["expires_at"] <= time.time():
                return None
            return {
                "expires_at": current["expires_at"],
                "attempts_left": CODE_ATTEMPTS - current["attempts"],
            }

    def pair(self, code: str, name: str, peer: str) -> tuple[dict, str]:
        """Exchanges a valid code for a station and its own token (shown once, kept hashed)."""
        with self.lock:
            data = self._load()
            now = int(time.time())
            failures = {
                key: [t for t in times if now - t < PEER_WINDOW_SECONDS]
                for key, times in data["failures"].items()
            }
            data["failures"] = {key: times for key, times in failures.items() if times}
            if len(data["failures"].get(peer, [])) >= PEER_ATTEMPTS:
                raise HTTPException(
                    429, "Muitas tentativas deste computador. Aguarde 15 minutos e tente de novo."
                )
            current = data["pairing"]
            if not current or current["expires_at"] <= now:
                self._fail(data, peer, now, "sem código válido")
                raise HTTPException(
                    403,
                    "Não há código de pareamento válido. Gere um novo código no computador "
                    "principal.",
                )
            if not hmac.compare_digest(current["code_hash"], digest(normalise(code))):
                current["attempts"] += 1
                left = CODE_ATTEMPTS - current["attempts"]
                if left <= 0:
                    data["pairing"] = None
                    self._event(data, "pairing.exhausted", peer=peer)
                self._fail(data, peer, now, "código incorreto")
                raise HTTPException(
                    403,
                    "Código incorreto. "
                    + (
                        f"Restam {left} tentativas."
                        if left > 0
                        else "O código foi cancelado; gere um novo no computador principal."
                    ),
                )
            token = secrets.token_urlsafe(32)
            station = {
                "id": str(uuid.uuid4()),
                "name": name,
                "token_hash": digest(token),
                "paired_at": now,
                "paired_from": peer,
                "last_seen_at": now,
                "last_address": peer,
                "revoked_at": None,
            }
            data["stations"].append(station)
            data["pairing"] = None  # single use
            self._event(data, "station.paired", station, peer=peer)
            self._save(data)
            return public(station), token

    def _fail(self, data: dict, peer: str, now: int, reason: str):
        data["failures"].setdefault(peer, []).append(now)
        self._event(data, "pairing.failed", peer=peer, reason=reason)
        self._save(data)

    # ---- stations ------------------------------------------------------------------

    def authenticate(self, token: str | None, peer: str | None = None) -> dict | None:
        """The active station owning this token, or None (unknown, revoked, malformed)."""
        if not token or len(token) > 100:
            return None
        hashed = digest(token)
        with self.lock:
            data = self._load()
            for station in data["stations"]:
                if hmac.compare_digest(station["token_hash"], hashed):
                    if station["revoked_at"]:
                        return None
                    now = int(time.time())
                    if peer and (
                        now - station["last_seen_at"] >= SEEN_EVERY_SECONDS
                        or station["last_address"] != peer
                    ):
                        station["last_seen_at"], station["last_address"] = now, peer
                        try:
                            self._save(data)
                        except OSError:
                            logger.warning("Não foi possível registrar o acesso da estação.")
                    return public(station)
        return None

    def get(self, station_id: str) -> dict | None:
        with self.lock:
            for station in self._load()["stations"]:
                if station["id"] == station_id:
                    return public(station)
        return None

    def active(self, station_id: str) -> bool:
        station = self.get(station_id)
        return bool(station and not station["revoked_at"])

    def revoke(self, station_id: str) -> dict:
        with self.lock:
            data = self._load()
            for station in data["stations"]:
                if station["id"] == station_id:
                    if not station["revoked_at"]:
                        station["revoked_at"] = int(time.time())
                        self._event(data, "station.revoked", station)
                        self._save(data)
                    return public(station)
        raise HTTPException(404, "Estação não encontrada.")

    def listing(self) -> list[dict]:
        with self.lock:
            stations = [public(s) for s in self._load()["stations"]]
        return sorted(stations, key=lambda s: (s["revoked_at"] is not None, -s["paired_at"]))

    def events(self, station_id: str | None = None, limit: int = 50) -> list[dict]:
        with self.lock:
            events = self._load()["events"]
        if station_id:
            events = [e for e in events if e.get("station_id") == station_id]
        return events[:limit]


def public(station: dict) -> dict:
    return {key: value for key, value in station.items() if key != "token_hash"}


def station_label(station: dict) -> str:
    # Names the computer the action came from, never a person.
    return f"estação {station['name']} ({station['id'][:8]})"


def registry_for(settings) -> "StationRegistry":
    """Beside the database file (the data folder), never inside a backup set."""
    from app.core.config import data_root
    from app.persistence.database import resolve_database_url

    url = resolve_database_url(settings.database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        return StationRegistry(Path(url.database).parent / REGISTRY_FILE)
    return StationRegistry(data_root() / REGISTRY_FILE)
