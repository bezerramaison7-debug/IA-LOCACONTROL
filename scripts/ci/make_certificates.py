"""CI (Windows): certificates for checking the local CA with the Windows verifier.

Writes ca.cer and leaves signed by a fresh local CA (app.network.tls) whose store network is
192.168.50.0/24:
- permitted.cer: localhost / 127.0.0.1 / 192.168.50.20, serverAuth (must be accepted);
- forbidden.cer: a public name and a public address (Name Constraints, ADR-026);
- other-network.cer: 192.168.51.20, a private address of another network (SEC-P1E-04);
- codesign.cer: a permitted name with the code-signing usage (the CA's EKU, SEC-P1E-04).
Usage: python make_certificates.py <folder>
"""

import ipaddress
import sys
from pathlib import Path

from app.network.tls import LocalAuthority
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID


def main(folder: str):
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    authority = LocalAuthority(out / "tls")
    addresses = [ipaddress.ip_address(a) for a in ("127.0.0.1", "192.168.50.10")]
    authority.ensure(["localhost", "loja-ci"], addresses)
    (out / "ca.cer").write_bytes(authority.ca_der())
    for name, names, ips, usages in (
        ("permitted", ["localhost"], ["127.0.0.1", "192.168.50.20"], None),
        ("forbidden", ["banco.example.com"], ["8.8.8.8"], None),
        ("other-network", ["localhost"], ["192.168.51.20"], None),
        ("codesign", ["localhost"], [], [ExtendedKeyUsageOID.CODE_SIGNING]),
    ):
        certificate, _ = authority.sign(
            names, [ipaddress.ip_address(a) for a in ips], 30, usages=usages
        )
        (out / f"{name}.cer").write_bytes(
            certificate.public_bytes(serialization.Encoding.DER)
        )
    print(f"Certificados em {out}")


if __name__ == "__main__":
    main(sys.argv[1])
