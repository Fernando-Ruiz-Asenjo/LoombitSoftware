"""F3 — el lazo interno→reparar: una señal FIX de la 'herramienta de errores de código' trae un
diff VALIDADO a la cola, sin escribir. Determinista: el coder es un stub (sin LM Studio)."""

from __future__ import annotations

from types import SimpleNamespace

from loombit_operator.fabrica.mantenimiento import _archivo_de, proponer_reparaciones
from loombit_operator.fabrica.modelos import Necesidad, TipoNecesidad


def test_archivo_de_extrae_ruta_sin_linea():
    fix = Necesidad(titulo="bug", tipo=TipoNecesidad.FIX, procedencia=["loombit_operator/x.py:42"])
    assert _archivo_de(fix) == "loombit_operator/x.py"
    # una señal que no apunta a un fichero (tool que falla en bucle) no da ruta
    sin_fichero = Necesidad(titulo="tool falla", tipo=TipoNecesidad.FIX, procedencia=["run:r2"])
    assert _archivo_de(sin_fichero) == ""


def test_proponer_reparaciones_trae_diff_validado(tmp_path):
    (tmp_path / "mod.py").write_text("x=1\n", encoding="utf-8")  # sin formatear
    fix = Necesidad(titulo="formatea el módulo", tipo=TipoNecesidad.FIX, procedencia=["mod.py:1"])
    stub = SimpleNamespace(chat=lambda **kw: SimpleNamespace(content="x = 1\n"))
    out = proponer_reparaciones([fix], llm=stub, raiz_repo=tmp_path)
    assert len(out) == 1 and out[0]["ok"] is True
    assert "x = 1" in out[0]["diff"] and out[0]["necesidad"] == "formatea el módulo"
    # INVARIANTE: no escribe el fichero (sigue feo hasta el gate humano)
    assert (tmp_path / "mod.py").read_text(encoding="utf-8") == "x=1\n"


def test_no_repara_lo_que_no_es_fix(tmp_path):
    mejora = Necesidad(
        titulo="trocear UI", tipo=TipoNecesidad.MEJORA, procedencia=["static/index.html"]
    )
    out = proponer_reparaciones(
        [mejora], llm=SimpleNamespace(chat=lambda **kw: None), raiz_repo=tmp_path
    )
    assert out == []
