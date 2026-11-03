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
import os
import secrets
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from app.core.durable import write_durably

logger = logging.getLogger(__name__)

REGISTRY_FILE = "stations.json"
STATION_COOKIE = "locacontrol_station"
# Browsers keep a cookie for at most about 400 days; it is renewed at every new session.
STATION_COOKIE_DAYS = 400
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: read aloud without doubt
CODE_LENGTH = 26  # 130 bits; configurable down to 13 (65 bits) by pairing_code_length
CODE_MINUTES = 10
CODE_ATTEMPTS = 5
# Wrong codes from one address: after this many in the window, that address waits.
PEER_ATTEMPTS = 10
PEER_WINDOW_SECONDS = 15 * 60
EVENT_LIMIT = 500
# last_seen is written at most this often per station, not at every request.
SEEN_EVERY_SECONDS = 60
# Token rotation (A1): a new token is offered at a new session and after this long in use.
ROTATE_SECONDS = 15 * 60
# An offered token not used yet (its response may have been lost) makes the server offer another
# after this long; up to PENDING_KEPT offered tokens stay valid until one of them is used, so an
# idle browser holding an older offer is never locked out.
PENDING_SECONDS = 10 * 60
PENDING_KEPT = 3
# A retired token presented within this window is a request already in flight or another tab
# of the same browser, not a copy: accepted, never treated as reuse.
GRACE_SECONDS = 120
RETIRED_KEPT = 20
REUSE_REASON = "reuso de credencial detectado"
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
        and secure_request(request)
        and store_host(request)
        and request.headers.get("x-locacontrol-request") == "1"
        and (origin is None or same_origin(request))
    )


def group(code: str) -> str:
    """ABCD-EFGH-… for reading aloud and typing."""
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def secure_request(request: Request) -> bool:
    """Stations only talk HTTPS (P1-E): no credential crosses the store network in plain HTTP."""
    return request.url.scheme == "https"


def principal_only(request: Request):
    """Route guard after authentication: refuses a station (decision of the user).

    Declared after the user dependency, which records who is calling; if that has not run,
    it fails closed instead of treating the caller as the main computer.
    """
    if not hasattr(request.state, "station") or request.state.station:
        raise HTTPException(403, PRINCIPAL_ONLY)


@dataclass
class Check:
    """Result of presenting a station token: the station (or None), a new token to hand over
    (rotation) and, on detected reuse, the evidence to audit."""

    station: dict | None = None
    rotate: str | None = None
    reuse: dict | None = None


UNAVAILABLE = (
    "A lista de estações está ilegível: as estações estão bloqueadas até o reparo no computador "
    "principal (Gestão → Estações da rede). Os dados da loja não foram afetados."
)
RESET_PHRASE = "RECOMEÇAR ESTAÇÕES"


class RegistryUnavailable(HTTPException):
    def __init__(self):
        super().__init__(503, UNAVAILABLE)


def readable(raw: bytes) -> dict | None:
    """A registry file that parses and has the expected shape, or None."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("stations", []), list):
        return None
    if any(
        not isinstance(s, dict) or "id" not in s or "token_hash" not in s
        for s in data.get("stations", [])
    ):
        return None
    return data


class StationRegistry:
    """Durable (fsync) and resilient (A2): the main file plus `.bak`, written after it.

    An unreadable main file falls back to the copy (and is kept aside for analysis). With both
    unreadable the registry is *unavailable*: stations are refused, the main computer keeps
    working, and only an explicit, audited reset on the main computer starts a new list. It
    never starts empty on its own, which would silently undo revocations.
    """

    def __init__(
        self,
        path: Path,
        rotate_seconds: int = ROTATE_SECONDS,
        grace_seconds: int = GRACE_SECONDS,
        clock=time.time,
    ):
        self.path = Path(path)
        self.backup = self.path.with_name(self.path.name + ".bak")
        self.rotate_seconds = rotate_seconds
        self.grace_seconds = grace_seconds
        self.clock = clock
        self.lock = threading.RLock()
        self._cache: dict | None = None
        self.unavailable = False
        self.recovered = False

    # ---- storage -------------------------------------------------------------------

    def _read(self, path: Path) -> tuple[bool, dict | None]:
        """(exists, data); data is None when the file exists but is unreadable."""
        try:
            return True, readable(path.read_bytes())
        except FileNotFoundError:
            return False, None
        except OSError:
            return True, None

    def _set_aside(self, path: Path):
        if path.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            os.replace(path, path.with_name(f"{path.name}.corrompido-{stamp}"))

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        if self.unavailable:
            raise RegistryUnavailable()
        exists, data = self._read(self.path)
        if data is None:
            backup_exists, backup = self._read(self.backup)
            if backup is not None:
                logger.error("stations.json ilegível ou ausente; usando a cópia %s", self.backup)
                self._set_aside(self.path)
                self.recovered = True
                data = backup
            elif exists or backup_exists:
                # Never start empty over an unreadable registry: that would drop revocations.
                logger.error("Lista de estações ilegível; estações bloqueadas até o reparo.")
                self.unavailable = True
                raise RegistryUnavailable()
            else:
                data = {}  # first run
        data.setdefault("server", {"id": str(uuid.uuid4()), "created_at": int(self.clock())})
        data.setdefault("stations", [])
        data.setdefault("pairing", None)
        data.setdefault("failures", {})
        data.setdefault("events", [])
        self._cache = data
        if self.recovered:
            self._event(data, "registry.recovered_from_backup")
            self._save(data)
        return data

    def _save(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
        # Main file first, then the copy: after a crash between the two, the main file (fsync'd
        # and renamed atomically) is the newer one and stays readable.
        write_durably(self.path, raw)
        write_durably(self.backup, raw)
        self._cache = data

    def state(self) -> dict:
        """For the main computer's screen: whether the list is readable and what happened."""
        try:
            self._load()
        except RegistryUnavailable:
            pass
        return {"unavailable": self.unavailable, "recovered_from_backup": self.recovered}

    def reset(self) -> dict:
        """Explicit repair from the main computer: the unreadable files are kept aside and a new,
        empty list starts. Every station must be paired again."""
        with self.lock:
            self._set_aside(self.path)
            self._set_aside(self.backup)
            self._cache, self.unavailable, self.recovered = None, False, False
            data = self._load()
            self._event(data, "registry.reset")
            self._save(data)
            return data["server"]

    def _event(self, data: dict, action: str, station: dict | None = None, **extra):
        entry = {"at": int(self.clock()), "action": action, **extra}
        if station:
            entry |= {"station_id": station["id"], "station_name": station["name"]}
        data["events"] = ([entry] + data["events"])[:EVENT_LIMIT]

    # ---- identity ------------------------------------------------------------------

    def server(self) -> dict | None:
        """This server's identity; None while the list is unavailable (the main computer keeps
        working without it)."""
        with self.lock:
            try:
                data = self._load()
            except RegistryUnavailable:
                return None
            if not self.path.exists():
                self._save(data)
            return data["server"]

    # ---- pairing -------------------------------------------------------------------

    def start_pairing(self, ca_der: bytes | None = None, length: int = CODE_LENGTH) -> dict:
        """A new code replaces any previous one. Kept: the code's hash and the proof of the CA
        (HMAC keyed with the code), which a station checks before trusting the CA (P1-E)."""
        from app.network.tls import ca_proof

        with self.lock:
            data = self._load()
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
            now = int(self.clock())
            data["pairing"] = {
                "code_hash": digest(code),
                "ca_proof": ca_proof(code, ca_der) if ca_der else None,
                "created_at": now,
                "expires_at": now + CODE_MINUTES * 60,
                "attempts": 0,
            }
            self._event(data, "pairing.started")
            self._save(data)
            return {
                "code": group(code),
                "expires_at": now + CODE_MINUTES * 60,
                "attempts_left": CODE_ATTEMPTS,
                "bits": length * 5,
            }

    def ca_proof(self) -> str | None:
        """Proof of the CA for the code in force, or None (no code, or it expired)."""
        with self.lock:
            current = self._load()["pairing"]
            if not current or current["expires_at"] <= self.clock():
                return None
            return current.get("ca_proof")

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
            if not current or current["expires_at"] <= self.clock():
                return None
            return {
                "expires_at": current["expires_at"],
                "attempts_left": CODE_ATTEMPTS - current["attempts"],
            }

    def pair(self, code: str, name: str, peer: str) -> tuple[dict, str]:
        """Exchanges a valid code for a station and its own token (shown once, kept hashed)."""
        with self.lock:
            data = self._load()
            now = int(self.clock())
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
            # Only with a valid code (no probing of names), and the code stays usable.
            if any(
                s["name"].casefold() == name.casefold() and not s["revoked_at"]
                for s in data["stations"]
            ):
                raise HTTPException(
                    409, f'Já existe uma estação ativa chamada "{name}". Escolha outro nome.'
                )
            token = secrets.token_urlsafe(32)
            station = {
                "id": str(uuid.uuid4()),
                "name": name,
                "token_hash": digest(token),
                "token_issued_at": now,
                "pending": [],
                "retired": [],
                "revoked_reason": None,
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

    def authenticate(
        self,
        token: str | None,
        peer: str | None = None,
        agent: str = "",
        rotate_now: bool = False,
    ) -> "Check":
        """Who owns this token, with token rotation and reuse detection (A1).

        - current token: accepted; a new *pending* token is offered at a new session
          (`rotate_now`) or when the current one is older than `rotate_seconds`;
        - pending token: accepted and promoted; the previous one is retired;
        - retired token within `grace_seconds`: accepted (in-flight request, another tab);
        - retired token after that: **reuse** — someone else holds a copy. The station is
          revoked ("reuso de credencial detectado") and the event recorded;
        - anything else, or a revoked station: refused.

        This detects a copied credential once both copies are used after a rotation; it does not
        prevent the copy from working until then.
        """
        if not token or len(token) > 100:
            return Check()
        hashed = digest(token)
        with self.lock:
            try:
                data = self._load()
            except RegistryUnavailable:
                return Check()  # fail closed: no station is accepted while the list is unreadable
            now = int(self.clock())
            for station in data["stations"]:
                match = self._match(station, hashed, now)
                if match is None:
                    continue
                if station["revoked_at"]:
                    return Check()
                changed, rotate = False, None
                if match == "reuse":
                    return self._reuse(data, station, now, peer, agent)
                if match == "pending":
                    # The browser stored the offered token: it becomes the current one; the
                    # previous current one and the other offers are retired.
                    offers = station.get("pending", [])
                    used = next(o for o in offers if hmac.compare_digest(o["hash"], hashed))
                    retired = [{"hash": station["token_hash"], "retired_at": now}] + [
                        {"hash": o["hash"], "retired_at": now} for o in offers if o is not used
                    ]
                    station["retired"] = (retired + station.get("retired", []))[:RETIRED_KEPT]
                    station["token_hash"], station["token_issued_at"] = used["hash"], used["at"]
                    station["pending"] = []
                    changed = True
                elif match == "current":
                    offers = station.setdefault("pending", [])
                    newest = max((o["at"] for o in offers), default=None)
                    age = now - station.get("token_issued_at", station["paired_at"])
                    due = (not offers and (rotate_now or age >= self.rotate_seconds)) or (
                        offers and now - newest >= PENDING_SECONDS
                    )
                    if due:
                        rotate = secrets.token_urlsafe(32)
                        offers.append({"hash": digest(rotate), "at": now})
                        station["pending"] = offers[-PENDING_KEPT:]
                        changed = True
                if peer and (
                    now - station["last_seen_at"] >= SEEN_EVERY_SECONDS
                    or station["last_address"] != peer
                ):
                    station["last_seen_at"], station["last_address"] = now, peer
                    changed = True
                if changed:
                    try:
                        self._save(data)
                    except OSError:
                        if rotate or match == "pending":
                            raise
                        logger.warning("Não foi possível registrar o acesso da estação.")
                return Check(station=public(station), rotate=rotate)
        return Check()

    def _match(self, station: dict, hashed: str, now: int) -> str | None:
        if hmac.compare_digest(station["token_hash"], hashed):
            return "current"
        if any(hmac.compare_digest(o["hash"], hashed) for o in station.get("pending", [])):
            return "pending"
        for retired in station.get("retired", []):
            if hmac.compare_digest(retired["hash"], hashed):
                return "grace" if now - retired["retired_at"] <= self.grace_seconds else "reuse"
        return None

    def _reuse(self, data, station, now, peer, agent) -> "Check":
        station["revoked_at"] = now
        station["revoked_reason"] = REUSE_REASON
        station["pending"] = []
        evidence = {"peer": peer, "agent": agent[:200], "last_address": station["last_address"]}
        self._event(data, "station.reuse_detected", station, **evidence)
        self._save(data)
        logger.error("Reuso de credencial da estação %s detectado (%s).", station["id"], peer)
        return Check(reuse={"station": public(station), **evidence})

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
                        station["revoked_at"] = int(self.clock())
                        station["revoked_reason"] = "revogada no computador principal"
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


SECRET_FIELDS = {"token_hash", "pending", "retired"}


def public(station: dict) -> dict:
    return {key: value for key, value in station.items() if key not in SECRET_FIELDS}


def station_label(station: dict) -> str:
    # Names the computer the action came from, never a person.
    return f"estação {station['name']} ({station['id'][:8]})"


def registry_for(settings) -> "StationRegistry":
    """Beside the database file (the data folder), never inside a backup set."""
    from app.core.config import data_root
    from app.persistence.database import resolve_database_url

    url = resolve_database_url(settings.database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        folder = Path(url.database).parent
    else:
        folder = data_root()
    return StationRegistry(
        folder / REGISTRY_FILE,
        rotate_seconds=settings.station_token_rotate_seconds,
        grace_seconds=settings.station_token_grace_seconds,
    )
