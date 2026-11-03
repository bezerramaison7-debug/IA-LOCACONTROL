"""Local certificate authority and HTTPS for the store network (P1-E, ADR-026).

One CA per installation, created on the main computer and never copied into backup sets:

- CA: ECDSA P-256, 10 years, path length 0, may only sign certificates, and **Name Constraints**
  restricting it to this computer's names and to private/loopback addresses — even a stolen CA
  key cannot vouch for other sites (as far as the verifier enforces constraints; see ADR-026);
- server certificate: ECDSA P-256, 397 days, the computer's names and its private addresses;
  reissued at start when 30 days or less remain or when the names/addresses changed;
- private keys: encrypted PEM (AES-256); the random password is protected by Windows DPAPI in
  the machine scope (files copied to another computer do not open). Elsewhere (development and
  Linux CI) the password sits in a file readable only by its owner — a weaker protection.

A station trusts the CA only after checking `ca_proof`: HMAC-SHA256 keyed with the pairing code
it was told by a person on the main computer (see `verify_ca_proof`).
"""

import datetime as dt
import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import socket
from pathlib import Path

from app.core.durable import write_durably

logger = logging.getLogger(__name__)

TLS_FOLDER = "tls"
CA_DAYS = 3650
SERVER_DAYS = 397
RENEW_DAYS = 30
# Addresses the CA may vouch for: loopback and private networks only.
PERMITTED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
]


class TlsUnavailable(RuntimeError):
    """The certificate material cannot be used; the store network must not open (fail closed)."""


# ---- protection of the key password ----------------------------------------------------------


class FileSecret:
    """Owner-only file. Weaker than DPAPI: anyone who copies the folder can read it."""

    kind = "arquivo restrito ao dono (fora do Windows)"

    def protect(self, data: bytes) -> bytes:
        return data

    def unprotect(self, data: bytes) -> bytes:
        return data


class DpapiSecret:
    """Windows DPAPI in the scope of the account that runs the server (SEC-P1E-01).

    Installed, that account is the service identity `NT SERVICE\\LocaControl`: another Windows user
    of the computer cannot unprotect the password even holding a copy of the file, and neither
    can a copy taken to another computer. (The machine scope used before let any local user
    decrypt it.) The files are also closed to other users by the data folder's ACL.
    """

    kind = "DPAPI do Windows (conta do serviço LocaControl)"
    UI_FORBIDDEN = 0x1

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        self.ctypes, self.Blob = ctypes, Blob
        self.crypt32 = ctypes.windll.crypt32
        self.kernel32 = ctypes.windll.kernel32

    def _call(self, function, data: bytes) -> bytes:
        ctypes = self.ctypes
        buffer = ctypes.create_string_buffer(data, len(data))
        source = self.Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        target = self.Blob()
        flags = self.UI_FORBIDDEN  # no CRYPTPROTECT_LOCAL_MACHINE: user (service) scope
        if not function(ctypes.byref(source), None, None, None, None, flags, ctypes.byref(target)):
            raise TlsUnavailable("O Windows recusou a proteção da chave (DPAPI).")
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            self.kernel32.LocalFree(target.pbData)

    def protect(self, data: bytes) -> bytes:
        return self._call(self.crypt32.CryptProtectData, data)

    def unprotect(self, data: bytes) -> bytes:
        return self._call(self.crypt32.CryptUnprotectData, data)


def default_secret():
    return DpapiSecret() if os.name == "nt" else FileSecret()


# ---- the station's side: authenticate the CA before trusting it ----------------------------


def normalise(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def ca_proof(code: str, ca_der: bytes) -> str:
    return hmac.new(normalise(code).encode(), ca_der, hashlib.sha256).hexdigest()


def verify_ca_proof(ca_der: bytes, proof: str, code: str) -> bool:
    """True only when the CA is the one the main computer showed the code for."""
    return hmac.compare_digest(ca_proof(code, ca_der), proof or "")


def fingerprint(der: bytes) -> str:
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


# ---- names and addresses of this computer ----------------------------------------------------


def local_names(extra: list[str] | None = None) -> list[str]:
    host = socket.gethostname().lower()
    names = ["localhost", host, host + ".local", *(n.lower() for n in extra or [])]
    return sorted({n for n in names if n})


def private_addresses(extra_networks: list | None = None) -> list:
    """This computer's loopback and private addresses (what stations may type)."""
    found = {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}
    candidates = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            candidates.add(info[4][0])
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            candidates.add(probe.getsockname()[0])
        except OSError:
            pass
    networks = PERMITTED_NETWORKS + list(extra_networks or [])
    for value in candidates:
        try:
            address = ipaddress.ip_address(value.split("%")[0])
        except ValueError:
            continue
        if any(address in network for network in networks if network.version == address.version):
            found.add(address)
    return sorted(found, key=lambda a: (a.version, int(a)))


# ---- the authority ---------------------------------------------------------------------------


class LocalAuthority:
    """CA and server certificate in `<data>/tls`, outside every backup set."""

    def __init__(self, folder: Path, secret=None):
        self.folder = Path(folder)
        self.secret = secret or default_secret()

    # files
    @property
    def ca_cert_path(self):
        return self.folder / "ca.pem"

    @property
    def ca_key_path(self):
        return self.folder / "ca.key"

    @property
    def cert_path(self):
        return self.folder / "server.pem"

    @property
    def key_path(self):
        return self.folder / "server.key"

    @property
    def password_path(self):
        return self.folder / "chave.protegida"

    def _write(self, path: Path, data: bytes):
        self.folder.mkdir(parents=True, exist_ok=True)
        write_durably(path, data)
        if os.name != "nt":
            os.chmod(path, 0o600)

    def _password(self, create: bool) -> bytes:
        if self.password_path.exists():
            try:
                return self.secret.unprotect(self.password_path.read_bytes())
            except (OSError, TlsUnavailable) as error:
                raise TlsUnavailable("A senha das chaves TLS não pôde ser lida.") from error
        if not create:
            raise TlsUnavailable("A senha das chaves TLS não existe.")
        password = secrets.token_urlsafe(32).encode()
        self._write(self.password_path, self.secret.protect(password))
        return password

    def _key(self, path: Path, password: bytes):
        from cryptography.hazmat.primitives import serialization

        try:
            return serialization.load_pem_private_key(path.read_bytes(), password)
        except (OSError, ValueError, TypeError) as error:
            raise TlsUnavailable(f"A chave {path.name} está ilegível ou foi alterada.") from error

    def _save_key(self, path: Path, key, password: bytes):
        from cryptography.hazmat.primitives import serialization

        self._write(
            path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(password),
            ),
        )

    # certificate authority
    def ca_certificate(self):
        from cryptography import x509

        try:
            return x509.load_pem_x509_certificate(self.ca_cert_path.read_bytes())
        except (OSError, ValueError) as error:
            raise TlsUnavailable("O certificado da autoridade local está ilegível.") from error

    def ca_der(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return self.ca_certificate().public_bytes(serialization.Encoding.DER)

    def ca_pem(self) -> bytes:
        return self.ca_cert_path.read_bytes()

    def _create_ca(
        self, names: list[str], label: str, password: bytes, now: dt.datetime, networks=()
    ):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LocaControl"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"LocaControl — autoridade local {label}"),
            ]
        )
        constraints = x509.NameConstraints(
            permitted_subtrees=[x509.DNSName(n) for n in names]
            + [x509.IPAddress(network) for network in [*PERMITTED_NETWORKS, *networks]],
            excluded_subtrees=None,
        )
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(constraints, critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .sign(key, hashes.SHA256())
        )
        self._save_key(self.ca_key_path, key, password)
        from cryptography.hazmat.primitives import serialization

        self._write(self.ca_cert_path, certificate.public_bytes(serialization.Encoding.PEM))
        logger.warning("Autoridade certificadora local criada: %s", fingerprint(self.ca_der()))

    def sign(self, names: list[str], addresses: list, days: int, now: dt.datetime | None = None):
        """Issues a server certificate with the CA (also used by tests to probe constraints)."""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

        now = now or dt.datetime.now(dt.UTC)
        password = self._password(create=False)
        ca_key = self._key(self.ca_key_path, password)
        ca = self.ca_certificate()
        key = ec.generate_private_key(ec.SECP256R1())
        certificate = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=days))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName(n) for n in names] + [x509.IPAddress(a) for a in addresses]
                ),
                critical=False,
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.public_key()), False
            )
            .sign(ca_key, hashes.SHA256())
        )
        return certificate, key

    # server certificate
    def ensure(
        self,
        names: list[str] | None = None,
        addresses: list | None = None,
        label: str = "",
        now: dt.datetime | None = None,
        networks: list | None = None,
    ) -> dict:
        """Creates what is missing and renews the server certificate when due. Fails closed."""
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        now = now or dt.datetime.now(dt.UTC)
        names = names or local_names()
        addresses = addresses or private_addresses()
        creating = not self.ca_cert_path.exists()
        if creating and (self.ca_key_path.exists() or self.password_path.exists()):
            raise TlsUnavailable("Arquivos TLS incompletos: falta o certificado da autoridade.")
        password = self._password(create=creating)
        if creating:
            # Extra store networks declared in the settings are vouched for too (ADR-026).
            self._create_ca(names, label, password, now, networks or [])
        ca = self.ca_certificate()
        permitted = {
            n.value
            for n in ca.extensions.get_extension_for_class(
                x509.NameConstraints
            ).value.permitted_subtrees
            if isinstance(n, x509.DNSName)
        }
        # A computer renamed after the CA was made: its new name is outside the CA (ADR-026);
        # the certificate keeps the permitted names and the addresses.
        usable = [n for n in names if n in permitted] or ["localhost"]
        reason = self._renewal_reason(usable, addresses, now)
        if reason:
            certificate, key = self.sign(usable, addresses, SERVER_DAYS, now)
            self._save_key(self.key_path, key, password)
            chain = certificate.public_bytes(serialization.Encoding.PEM) + self.ca_pem()
            self._write(self.cert_path, chain)
            logger.warning("Certificado do servidor emitido (%s).", reason)
        current = x509.load_pem_x509_certificate(self.cert_path.read_bytes())
        self._key(self.key_path, password)  # fails closed if the key was altered
        return {
            "ca_fingerprint": fingerprint(self.ca_der()),
            "ca_expires": ca.not_valid_after_utc.isoformat(),
            "server_expires": current.not_valid_after_utc.isoformat(),
            "server_names": usable,
            "server_addresses": [str(a) for a in addresses],
            "renamed_outside_ca": [n for n in names if n not in permitted],
            "protection": self.secret.kind,
            "issued": reason or None,
        }

    def _renewal_reason(self, names, addresses, now) -> str:
        from cryptography import x509

        if not self.cert_path.exists() or not self.key_path.exists():
            return "novo"
        try:
            current = x509.load_pem_x509_certificate(self.cert_path.read_bytes())
        except ValueError:
            return "certificado ilegível"
        if current.not_valid_after_utc - now <= dt.timedelta(days=RENEW_DAYS):
            return "renovação por prazo"
        san = current.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have = (
            set(san.get_values_for_type(x509.DNSName)),
            set(san.get_values_for_type(x509.IPAddress)),
        )
        if have != (set(names), set(addresses)):
            return "nomes ou endereços mudaram"
        return ""

    def server_files(self) -> tuple[str, str, str]:
        """(certificate chain, encrypted key, key password) for the HTTPS listener."""
        return str(self.cert_path), str(self.key_path), self._password(create=False).decode()
