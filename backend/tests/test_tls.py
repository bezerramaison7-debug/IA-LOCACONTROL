"""Autoridade certificadora local e certificado do servidor (P1-E): criação, proteção das chaves,
renovação, falha fechada, prova da CA e Name Constraints verificadas pelo verificador X.509 da
biblioteca `cryptography` (no Windows, a CI repete com o verificador do sistema)."""

import datetime as dt
import ipaddress
import os

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID
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


@pytest.fixture
def data_dir_with_tls(tmp_path, monkeypatch):
    """A pasta de dados cujo tls/ é o da fixture `authority` (sem servidor rodando)."""
    monkeypatch.setenv("LOCACONTROL_DATA_DIR", str(tmp_path))
    for name in ("DATABASE_URL", "BACKUP_DIRECTORY"):
        monkeypatch.delenv(f"LOCACONTROL_{name}", raising=False)
    return tmp_path


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
    networks = {n.value for n in permitted if isinstance(n, x509.IPAddress)}
    # SEC-P1E-04: só a rede da loja (a /24 do endereço) e o próprio computador, não toda faixa
    # privada.
    assert networks == {
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("192.168.0.0/24"),
    }
    eku = ca.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(eku) == [ExtendedKeyUsageOID.SERVER_AUTH]
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
    # Outras redes privadas também ficam de fora (o roteador, um NAS, outra rede da empresa).
    for other in ("192.168.1.1", "10.0.0.1", "172.16.0.1"):
        address = ipaddress.ip_address(other)
        certificate, _ = authority.sign(["localhost"], [address], 30, NOW)
        with pytest.raises(VerificationError):
            verify(authority, certificate, x509.IPAddress(address))
    same_network = ipaddress.ip_address("192.168.0.200")
    certificate, _ = authority.sign(["localhost"], [same_network], 30, NOW)
    assert verify(authority, certificate, x509.IPAddress(same_network))
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
    # Mudou de rede (SEC-P1E-04): o endereço novo fica fora do certificado e é informado.
    assert moved["addresses_outside_ca"] == ["10.0.0.7"]
    assert "10.0.0.7" not in moved["server_addresses"]
    same = authority.ensure(NAMES, [*ADDRESSES[:2], ipaddress.ip_address("192.168.0.77")], now=NOW)
    assert same["addresses_outside_ca"] == [] and "192.168.0.77" in same["server_addresses"]
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


def test_no_store_address_yet_means_no_authority_yet(tmp_path):
    """Sem endereço na rede local, uma CA criada agora ficaria presa ao loopback: a rede fica
    fechada e nada é criado (SEC-P1E-04)."""
    loopback = [ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")]
    authority = LocalAuthority(tmp_path / "tls")
    with pytest.raises(TlsUnavailable, match="ainda não tem endereço"):
        authority.ensure(NAMES, loopback, now=NOW)
    assert not authority.folder.exists()
    # Uma rede declarada nas configurações basta.
    declared = authority.ensure(NAMES, loopback, now=NOW, networks=["100.64.0.0/10"])
    assert "100.64.0.0/10" in declared["ca_networks"]


def test_a_new_authority_for_a_new_network(authority, data_dir_with_tls):
    """`LocaControl.exe nova-autoridade --confirmar`: a CA anterior é guardada, não apagada, e a
    próxima é outra; sem --confirmar nada acontece."""
    from app import launcher

    before = fingerprint(authority.ca_der())
    assert launcher.main(["nova-autoridade"]) == 64
    assert authority.folder.exists()
    assert launcher.main(["nova-autoridade", "--confirmar"]) == 0
    assert not authority.folder.exists()
    kept = list(authority.folder.parent.glob("tls-anterior-*"))
    assert len(kept) == 1 and (kept[0] / "ca.key").exists()
    fresh = LocalAuthority(authority.folder)
    fresh.ensure(NAMES, ADDRESSES, now=NOW)
    assert fingerprint(fresh.ca_der()) != before
