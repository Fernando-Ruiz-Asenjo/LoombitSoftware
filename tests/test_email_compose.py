"""Formato de correo: el contenido lo decide el modelo; solo se normaliza un glitch de saltos.

El 14B a veces emite los saltos de línea como texto literal '\\n'. normalize_email_text los
convierte en saltos reales para que el destinatario no vea '\\n' escrito. No toca el contenido.
"""

from loombit_operator.skill_blanca_gmail import normalize_email_text


def test_normaliza_saltos_literales_del_modelo():
    crudo = "Hola Jana,\\n\\nTe confirmo la reunión del martes.\\n\\nUn saludo,\\nFernando"
    out = normalize_email_text(crudo)
    assert "\\n" not in out
    assert out == "Hola Jana,\n\nTe confirmo la reunión del martes.\n\nUn saludo,\nFernando"


def test_respeta_saltos_reales_y_contenido():
    crudo = "Hola,\n\nAdjunto la factura.\n\nUn saludo,\nAna"
    assert normalize_email_text(crudo) == crudo
