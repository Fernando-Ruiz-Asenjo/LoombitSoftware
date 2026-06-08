"""
Destilador de contexto real (`galaxia_intel`): extracción DETERMINISTA de importes y referencias
del texto de los correos. El número NUNCA lo pone el LLM (D-09/D-14). Sin red.
"""

from loombit_operator.galaxia_intel import (
    _importes_de,
    _referencias_de,
    normalizar_importe,
)


def test_normalizar_importe_formato_espanol():
    assert normalizar_importe("1.250,00") == 1250.00  # punto=miles, coma=decimal
    assert normalizar_importe("1.250") == 1250.0  # punto de miles, 3 cifras detrás
    assert normalizar_importe("90,87") == 90.87
    assert normalizar_importe("70") == 70.0
    assert normalizar_importe("12.50") == 12.50  # punto decimal (2 cifras)
    assert normalizar_importe("abc") is None


def test_importes_solo_los_pegados_a_euro():
    texto = "Te paso la factura de 1.250,00 € y el envío costó 70€. Mi DNI 12345678 no es dinero."
    vals = sorted(v for _, v in _importes_de(texto))
    assert vals == [70.0, 1250.0]  # 12345678 (DNI) NO se cuela: no lleva € pegado


def test_importes_simbolo_delante():
    assert sorted(v for _, v in _importes_de("son €23,50 y EUR 350")) == [23.5, 350.0]


def test_importes_ignora_numeros_sin_moneda():
    # números sueltos (teléfono, código postal) sin € no son importes
    assert _importes_de("llámame al 600123456, CP 28013") == []


def test_referencias_exigen_digito_no_cuela_la_palabra_no():
    # El bug original: 'no sea', 'no obstante' colaban como 'nº'. Ya no.
    texto = "No obstante, no sea tarde. Adjunto factura F-2024-12 y el presupuesto 1043. nº 44."
    refs = _referencias_de(texto)
    assert "factura F-2024-12" in refs
    assert "presupuesto 1043" in refs
    assert "nº 44" in refs
    assert not any("sea" in r or "obstante" in r for r in refs)


def test_referencias_factura_sin_numero_no_cuela():
    # 'Factura de Sklum' / 'factura final' no tienen nº → no son referencia
    assert _referencias_de("Te mando la Factura de Sklum, es la factura final") == []
