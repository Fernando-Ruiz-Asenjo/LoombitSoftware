"""La bóveda de credenciales cifra en reposo, no expone secretos en listados ni en disco.

Privacidad por diseño: el secreto solo se descifra al pedirlo explícitamente; el listado y el
fichero NUNCA contienen el secreto en claro.
"""

from cryptography.fernet import Fernet

from loombit_operator.credentials import CredentialVault


def _vault(tmp_path) -> CredentialVault:
    return CredentialVault(path=tmp_path / "credentials.json", cipher=Fernet(Fernet.generate_key()))


def test_set_y_get_roundtrip(tmp_path):
    v = _vault(tmp_path)
    v.set("aeat", "12345678Z", "MiClaveSecreta!", notes="certificado")
    assert v.get_secret("aeat") == "MiClaveSecreta!"
    assert v.get_username("aeat") == "12345678Z"


def test_listado_no_expone_el_secreto(tmp_path):
    v = _vault(tmp_path)
    v.set("banco", "fernando", "superpassword")
    listado = v.list()
    assert listado[0]["service"] == "banco"
    assert "superpassword" not in str(listado)  # ni rastro del secreto
    assert "secret" not in str(listado).lower()


def test_el_fichero_en_disco_esta_cifrado(tmp_path):
    v = _vault(tmp_path)
    v.set("x", "u", "PLAINTEXT_SECRET")
    en_disco = (tmp_path / "credentials.json").read_text(encoding="utf-8")
    assert "PLAINTEXT_SECRET" not in en_disco  # cifrado en reposo
    assert "enc::" in en_disco


def test_delete(tmp_path):
    v = _vault(tmp_path)
    v.set("x", "u", "s")
    assert v.delete("x") is True
    assert v.get_secret("x") is None
    assert v.delete("x") is False


def test_se_niega_a_guardar_sin_cifrado(tmp_path):
    v = CredentialVault(path=tmp_path / "c.json", cipher=None)
    try:
        v.set("x", "u", "s")
        raise AssertionError("debería haberse negado a guardar sin cifrado")
    except RuntimeError:
        pass
