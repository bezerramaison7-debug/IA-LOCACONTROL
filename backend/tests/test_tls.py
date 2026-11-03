"""Autoridade certificadora local e certificado do servidor (P1-E): criação, proteção das chaves,
renovação, falha fechada, prova da CA e Name Constraints verificadas pelo verificador X.509 da
biblioteca `cryptography` (no Windows, a CI repete com o verificador do sistema)."""

import datetime as dt
import ipaddress
import os

import pytest
from cryptography import x509
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from app.network.tls import (
    RENEW_DAYS,
    LocalAuthority,
    TlsUnavailable,
    ca_proof,
    fingerprint,
    verify_ca_proof,
)

NAMES = ["localhost", "loja-pc", "loja-pc.local"]
ADDRESSES = [ipaddress.ip_address(a) for a in ("127.0.0.1", "::1", "192.168.0.10")]
NOW = dt.datetime(2026, 11, 3, 12, tzinfo=dt.UTC)


@pytest.fixture
def authority(tmp_path):
    ca = LocalAuthority(tmp_path / "tls")
    ca.ensure(NAMES, ADDRESSES, label="(teste)", now=NOW)
    return ca


def verify(ca: LocalAuthority, leaf, name, now=NOW):
    store = Store([ca.ca_certificate()])
    verifier = PolicyBuilder().store(store).time(now).build_server_verifier(name)
    return verifier.verify(leaf, [])


def leaf(ca: LocalAuthority):
    return x509.load_pem_x509_certificates(ca.cert_path.read_bytes())[0]


def test_creates_a_constrained_ca_and_a_server_certificate_with_encrypted_keys(authority):
    ca = authority.ca_certificate()
    basic = ca.extensions.get_extension_for_class(x509.BasicConstraints)
    assert basic.critical and basic.value.ca and basic.value.path_length == 0
    usage = ca.extensions.get_extension_for_class(x509.KeyUsage).value
    assert usage.key_cert_sign and not usage.digital_signature
    constraints = ca.extensions.get_extension_for_class(x509.NameConstraints)
    assert constraints.critical
    permitted = constraints.value.permitted_subtrees
    assert {n.value for n in permitted if isinstance(n, x509.DNSName)} == set(NAMES)
    assert ipaddress.ip_network("192.168.0.0/16") in {
        n.value for n in permitted if isinstance(n, x509.IPAddress)
    }
    assert (ca.not_valid_after_utc - NOW).days >= 3649
    for key in (authority.ca_key_path, authority.key_path):
        assert b"ENCRYPTED PRIVATE KEY" in key.read_bytes()
    assert authority.ca_key_path.read_bytes().count(b"BEGIN") == 1
    if os.name != "nt":
        for path in (authority.ca_key_path, authority.key_path, authority.password_path):
            assert oct(path.stat().st_mode & 0o777) == "0o600"
    server = leaf(authority)
    assert (server.not_valid_after_utc - NOW).days == 397
    for name in (x509.DNSName("localhost"), x509.DNSName("loja-pc"), x509.IPAddress(ADDRESSES[2])):
        assert verify(authority, server, name)


def test_name_constraints_refuse_certificates_for_other_sites(authority):
    for names, addresses, subject in (
        (["exemplo-banco.com.br"], [], x509.DNSName("exemplo-banco.com.br")),
        (["loja-pc.evil.example"], [], x509.DNSName("loja-pc.evil.example")),
        (
            ["localhost"],
            [ipaddress.ip_address("8.8.8.8")],
            x509.IPAddress(ipaddress.ip_address("8.8.8.8")),
        ),
    ):
        certificate, _ = authority.sign(names, addresses, 30, NOW)
        with pytest.raises(VerificationError):
            verify(authority, certificate, subject)
    # Subdomínios de nomes permitidos continuam permitidos (comportamento das Name Constraints).
    certificate, _ = authority.sign(["x.localhost"], [], 30, NOW)
    assert verify(authority, certificate, x509.DNSName("x.localhost"))


def test_reuses_the_ca_and_renews_the_server_certificate_only_when_due(authority):
    ca_before, serial = fingerprint(authority.ca_der()), leaf(authority).serial_number
    again = authority.ensure(NAMES, ADDRESSES, now=NOW + dt.timedelta(days=10))
    assert again["issued"] is None and leaf(authority).serial_number == serial
    near_end = leaf(authority).not_valid_after_utc - dt.timedelta(days=RENEW_DAYS - 1)
    renewed = authority.ensure(NAMES, ADDRESSES, now=near_end)
    assert renewed["issued"] == "renovação por prazo" and leaf(authority).serial_number != serial
    moved = authority.ensure(NAMES, [*ADDRESSES[:2], ipaddress.ip_address("10.0.0.7")], now=NOW)
    assert moved["issued"] == "nomes ou endereços mudaram"
    assert fingerprint(authority.ca_der()) == ca_before  # a CA nunca muda sozinha
    # Computador renomeado depois da CA: o nome novo fica de fora e é informado.
    renamed = authority.ensure(["localhost", "outro-pc"], ADDRESSES, now=NOW)
    assert (
        renamed["renamed_outside_ca"] == ["outro-pc"] and "outro-pc" not in renamed["server_names"]
    )


def test_fails_closed_when_the_material_is_damaged(authority, tmp_path):
    authority.key_path.write_bytes(authority.key_path.read_bytes().replace(b"A", b"B", 5))
    with pytest.raises(TlsUnavailable):
        authority.ensure(NAMES, ADDRESSES, now=NOW)
    broken = LocalAuthority(tmp_path / "tls")
    broken.password_path.write_bytes(b"outra senha")
    with pytest.raises(TlsUnavailable):
        broken.ensure(NAMES, ADDRESSES, now=NOW)
    half = LocalAuthority(tmp_path / "metade")
    half.folder.mkdir()
    half.ca_key_path.write_bytes(b"sobrou a chave")
    with pytest.raises(TlsUnavailable):  # nunca recria uma CA por cima de restos
        half.ensure(NAMES, ADDRESSES, now=NOW)


def test_the_station_trusts_the_ca_only_with_the_right_code(authority, tmp_path):
    code = "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-23"
    der = authority.ca_der()
    proof = ca_proof(code, der)
    assert verify_ca_proof(der, proof, code)
    assert verify_ca_proof(der, proof, code.lower().replace("-", " "))  # digitação tolerante
    assert not verify_ca_proof(der, proof, "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-24")
    impostor = LocalAuthority(tmp_path / "atacante")
    impostor.ensure(NAMES, ADDRESSES, now=NOW)
    assert not verify_ca_proof(impostor.ca_der(), proof, code)  # CA trocada no meio
    assert not verify_ca_proof(der, "", code)


@pytest.mark.skipif(os.name != "nt", reason="DPAPI do Windows")
def test_dpapi_protects_the_key_password(tmp_path):
    from app.network.tls import DpapiSecret

    secret = DpapiSecret()
    sealed = secret.protect(b"segredo")
    assert sealed != b"segredo" and secret.unprotect(sealed) == b"segredo"
    ca = LocalAuthority(tmp_path / "tls", secret)
    ca.ensure(NAMES, ADDRESSES, now=NOW)
    assert b"segredo" not in ca.password_path.read_bytes()
