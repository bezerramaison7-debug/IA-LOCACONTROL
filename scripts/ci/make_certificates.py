"""CI (Windows): certificates for checking Name Constraints with the Windows verifier.

Writes ca.cer, permitted.cer (localhost / 127.0.0.1) and forbidden.cer (a public name and a public
address) signed by a fresh local CA (app.network.tls). Usage: python make_certificates.py <folder>
"""

import ipaddress
import sys
from pathlib import Path

from app.network.tls import LocalAuthority
from cryptography.hazmat.primitives import serialization


def main(folder: str):
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    authority = LocalAuthority(out / "tls")
    authority.ensure(["localhost", "loja-ci"], [ipaddress.ip_address("127.0.0.1")])
    (out / "ca.cer").write_bytes(authority.ca_der())
    for name, names, addresses in (
        ("permitted", ["localhost"], ["127.0.0.1"]),
        ("forbidden", ["banco.example.com"], ["8.8.8.8"]),
    ):
        certificate, _ = authority.sign(
            names, [ipaddress.ip_address(a) for a in addresses], 30
        )
        (out / f"{name}.cer").write_bytes(
            certificate.public_bytes(serialization.Encoding.DER)
        )
    print(f"Certificados em {out}")


if __name__ == "__main__":
    main(sys.argv[1])
