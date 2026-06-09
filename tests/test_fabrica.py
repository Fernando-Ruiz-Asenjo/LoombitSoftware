"""Tests de la Fábrica de Skills (Skill X) — auto-autoría GOBERNADA.

Cubren las invariantes que la hacen segura y útil (no chorradas):
- el gate de seguridad bloquea el código peligroso ANTES de ejecutarlo,
- el arnés solo da por buena una tool que pasa las 7 puertas (incl. su propio eval),
- el ciclo propone PENDIENTE y NUNCA auto-aplica (la tool no se registra sin gate humano),
- aprobar → materializar → cargar registra una tool invocable de verdad.

Deterministas: el coder se sustituye por un stub (no necesitan LM Studio).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from loombit_operator.fabrica.ciclo import ejecutar_ciclo
from loombit_operator.fabrica.fuentes import FuenteRegistry
from loombit_operator.fabrica.materializar import cargar_tools_aprobadas, escribir_tool_aprobada
from loombit_operator.fabrica.meta import detectar_meta
from loombit_operator.fabrica.modelos import (
    BorradorTool,
    EstadoPropuesta,
    Fuente,
    Necesidad,
    PropuestaSkill,
    TipoNecesidad,
)
from loombit_operator.fabrica.interno import marcar
from loombit_operator.fabrica.necesidad import detectar_necesidades
from loombit_operator.fabrica.oportunidades import OportunidadStore
from loombit_operator.fabrica.reparar import proponer_parche, validar_comportamiento
from loombit_operator.fabrica.propuesta import PropuestaStore
from loombit_operator.fabrica.red import canal_github, canal_hackernews
from loombit_operator.fabrica.seguridad import analizar_seguridad, construir_namespace_seguro
from loombit_operator.fabrica.validacion import validar
from loombit_operator.tools.registry import tool_registry

# ── Material de prueba: una tool buena (cómputo puro) con su eval ────────────────

SOURCE_BUENA = (
    "import json\n"
    "from datetime import date\n\n\n"
    "def dias_habiles_entre(inicio: str, fin: str) -> str:\n"
    '    """Cuenta los días hábiles (lun-vie) entre dos fechas ISO, ambas inclusive."""\n'
    "    d0 = date.fromisoformat(inicio)\n"
    "    d1 = date.fromisoformat(fin)\n"
    "    if d1 < d0:\n"
    "        d0, d1 = d1, d0\n"
    "    dias = 0\n"
    "    actual = d0\n"
    "    while actual <= d1:\n"
    "        if actual.weekday() < 5:\n"
    "            dias += 1\n"
    "        actual = date.fromordinal(actual.toordinal() + 1)\n"
    '    return json.dumps({"ok": True, "dias_habiles": dias}, ensure_ascii=False)\n'
)
EVAL_BUENA = (
    "import json\n\n\n"
    "def check(fn):\n"
    '    r = json.loads(fn(inicio="2026-06-01", fin="2026-06-07"))\n'
    '    return r.get("dias_habiles") == 5, f"dias={r.get(\'dias_habiles\')}"\n'
)

PARAMS = {
    "type": "object",
    "properties": {
        "inicio": {"type": "string", "description": "fecha ISO inicio"},
        "fin": {"type": "string", "description": "fecha ISO fin"},
    },
    "required": ["inicio", "fin"],
}


def _borrador_bueno(nombre: str = "dias_habiles_entre") -> BorradorTool:
    source = SOURCE_BUENA.replace("dias_habiles_entre", nombre)
    return BorradorTool(
        nombre=nombre,
        descripcion="Cuenta los días hábiles (lun-vie) entre dos fechas ISO.",
        parametros=PARAMS,
        source=source,
        eval_source=EVAL_BUENA.replace("dias_habiles_entre", nombre),
    )


def _stub_llm(nombre: str = "dias_habiles_entre"):
    payload = json.dumps(
        {
            "nombre": nombre,
            "descripcion": "Cuenta los días hábiles entre dos fechas ISO.",
            "parametros": PARAMS,
            "source": SOURCE_BUENA.replace("dias_habiles_entre", nombre),
            "eval_source": EVAL_BUENA.replace("dias_habiles_entre", nombre),
        },
        ensure_ascii=False,
    )
    return SimpleNamespace(chat=lambda **kw: SimpleNamespace(content=payload))


# ── 1. Gate de seguridad (el linchpin) ──────────────────────────────────────────


@pytest.mark.parametrize(
    "src",
    [
        "import os\ndef t():\n    return os.system('echo x')\n",
        "def t(x):\n    return eval(x)\n",
        "from subprocess import run\ndef t():\n    return run(['ls'])\n",
        "def t():\n    return ().__class__.__bases__\n",
        "import socket\ndef t():\n    return socket.socket()\n",
    ],
)
def test_seguridad_bloquea_codigo_peligroso(src):
    assert analizar_seguridad(src).ok is False


def test_seguridad_acepta_computo_puro():
    assert analizar_seguridad(SOURCE_BUENA).ok is True


def test_namespace_seguro_sin_builtins_peligrosos():
    ns = construir_namespace_seguro()
    builtins = ns["__builtins__"]
    assert "open" not in builtins and "eval" not in builtins and "exec" not in builtins
    # el __import__ seguro bloquea os pero deja json
    with pytest.raises(ImportError):
        builtins["__import__"]("os")
    assert builtins["__import__"]("json") is not None


# ── 2. Arnés de validación ──────────────────────────────────────────────────────


def test_validacion_tool_buena_pasa_las_siete_puertas():
    v = validar(_borrador_bueno())
    assert v.ok is True
    assert set(v.puertas) == {
        "seguridad",
        "contrato",
        "formato",
        "lint",
        "importa",
        "eval",
        "sin_regresion",
    }


def test_validacion_rechaza_sin_eval():
    b = _borrador_bueno()
    b.eval_source = ""
    v = validar(b)
    assert v.ok is False
    assert "eval" in v.fallos


def test_validacion_rechaza_codigo_inseguro():
    b = _borrador_bueno()
    b.source = "import os\n\n\ndef dias_habiles_entre(inicio, fin):\n    return os.getcwd()\n"
    v = validar(b)
    assert v.ok is False
    assert "seguridad" in v.fallos


def test_validacion_rechaza_contrato_sin_funcion():
    b = _borrador_bueno(nombre="otra_cosa")
    b.source = SOURCE_BUENA  # define dias_habiles_entre, no 'otra_cosa'
    v = validar(b)
    assert v.ok is False
    assert "contrato" in v.fallos


# ── 3. Detección de necesidades ─────────────────────────────────────────────────


def test_deteccion_desde_propuestas_del_agente():
    memoria = SimpleNamespace(
        proposals=[
            SimpleNamespace(
                suggestion="tool para días hábiles",
                issue="no supe el plazo hábil",
                category="tool_missing",
                run_id="r1",
            )
        ]
    )
    runs = SimpleNamespace(list=lambda: [])
    necs = detectar_necesidades(memoria=memoria, store=runs)
    assert len(necs) == 1
    assert necs[0].tipo == TipoNecesidad.TOOL
    assert "agente:propose_improvement" in necs[0].procedencia[0]


def test_deteccion_tool_que_falla_en_bucle():
    paso = SimpleNamespace(tool_name="read_invoice", result="[SISTEMA] error al leer")
    run = SimpleNamespace(id="r2", status=SimpleNamespace(value="failed"), steps=[paso, paso])
    memoria = SimpleNamespace(proposals=[])
    necs = detectar_necesidades(memoria=memoria, store=SimpleNamespace(list=lambda: [run]))
    assert any(n.tipo == TipoNecesidad.FIX and "read_invoice" in n.titulo for n in necs)


# ── 4. Ciclo e2e + el gate (NUNCA auto-aplica) ──────────────────────────────────


def _memoria_con_necesidad():
    return SimpleNamespace(
        proposals=[
            SimpleNamespace(
                suggestion="una tool que cuente días hábiles entre dos fechas",
                issue="no supe calcular el plazo en días hábiles",
                category="tool_missing",
                run_id="run-1",
            )
        ]
    )


def test_ciclo_propone_pendiente_y_no_auto_aplica():
    nombre = "fab_demo_dias_habiles"
    # garantiza que la tool NO está registrada antes
    tool_registry._tools.pop(nombre, None)
    with tempfile.TemporaryDirectory() as d:
        store = PropuestaStore(store_path=Path(d) / "p.json")
        informe = ejecutar_ciclo(
            max_necesidades=1,
            max_intentos=1,
            llm=_stub_llm(nombre),
            memoria=_memoria_con_necesidad(),
            store_runs=SimpleNamespace(list=lambda: []),
            store_prop=store,
            store_op=OportunidadStore(store_path=Path(d) / "op.json"),
            fuentes=[Fuente.PROCESO],  # offline: solo la fuente interna (sin tocar la Red)
        )
        assert len(informe["tools"]["propuestas_pendientes_nuevas"]) == 1
        pend = store.list(EstadoPropuesta.PENDIENTE)
        assert len(pend) == 1 and pend[0].fitness == 7
        # INVARIANTE CLAVE: proponer NO registra la tool (no auto-aplica)
        assert nombre not in {t.name for t in tool_registry.list()}


# ── 5. Gate humano + materialización (aprobar → tool invocable) ─────────────────


def test_aprobar_materializa_y_registra_tool_invocable():
    nombre = "fab_demo_suma_dias"
    tool_registry._tools.pop(nombre, None)
    generada = (
        Path(__file__).resolve().parents[1]
        / "loombit_operator"
        / "fabrica"
        / "generadas"
        / f"{nombre}.py"
    )
    try:
        with tempfile.TemporaryDirectory() as d:
            store = PropuestaStore(store_path=Path(d) / "p.json")
            prop = store.add(
                PropuestaSkill(
                    necesidad=Necesidad(titulo="t"),
                    borrador=_borrador_bueno(nombre),
                    veredicto=validar(_borrador_bueno(nombre)),
                )
            )
            # materializar una propuesta NO aprobada debe fallar (gate sagrado)
            with pytest.raises(ValueError):
                escribir_tool_aprobada(prop)
            # gate humano
            store.aprobar(prop.id, nota="ok test")
            cargadas = cargar_tools_aprobadas(store=store)
            assert nombre in cargadas
            td = tool_registry.get(nombre)
            res = json.loads(td.execute(inicio="2026-06-01", fin="2026-06-07"))
            assert res["dias_habiles"] == 5
    finally:
        tool_registry._tools.pop(nombre, None)
        generada.unlink(missing_ok=True)


def test_store_no_redecide_una_propuesta_ya_decidida():
    with tempfile.TemporaryDirectory() as d:
        store = PropuestaStore(store_path=Path(d) / "p.json")
        prop = store.add(
            PropuestaSkill(
                necesidad=Necesidad(titulo="t"),
                borrador=_borrador_bueno("fab_demo_x"),
                veredicto=validar(_borrador_bueno("fab_demo_x")),
            )
        )
        store.descartar(prop.id, "no")
        with pytest.raises(ValueError):
            store.aprobar(prop.id, "sí")  # ya está descartada
        # persiste y recarga
        store2 = PropuestaStore(store_path=Path(d) / "p.json")
        assert store2.get(prop.id).estado == EstadoPropuesta.DESCARTADA


# ── 6. Motor MULTI-FUENTE: el abanico (dentro + fuera + meta) ────────────────────


class _Resp:
    """Respuesta HTTP de pega para no salir a la Red en los tests del radar."""

    def __init__(self, status: int = 200, data: dict | None = None, text: str = "") -> None:
        self.status_code = status
        self._data = data or {}
        self.text = text

    def json(self) -> dict:
        return self._data


def test_red_github_trae_proyectos_con_cita():
    def fake_get(url, **kw):
        return _Resp(
            data={
                "items": [
                    {
                        "full_name": "acme/agent",
                        "html_url": "https://github.com/acme/agent",
                        "description": "AI agent skills",
                        "stargazers_count": 1200,
                    }
                ]
            }
        )

    ops = canal_github(http_get=fake_get)
    assert ops and ops[0].fuente == Fuente.RED
    assert "github.com/acme/agent" in ops[0].procedencia[0]


def test_red_hackernews_trae_mercado_con_cita():
    def fake_get(url, **kw):
        return _Resp(
            data={
                "hits": [
                    {
                        "title": "Competidor X levanta ronda",
                        "url": "https://sifted.eu/x",
                        "points": 80,
                        "objectID": "1",
                    }
                ]
            }
        )

    ops = canal_hackernews(http_get=fake_get)
    assert ops and ops[0].fuente == Fuente.RED
    assert "sifted.eu/x" in ops[0].procedencia[0]


def test_meta_amplia_su_propio_abanico():
    # una fuente seca + el linaje → la Fábrica propone ampliar su abanico (con gate)
    props = detectar_meta(resultados_por_fuente={Fuente.RED: []})
    assert props and all(p.fuente == Fuente.META for p in props)
    assert any("ampliar" in p.titulo.lower() for p in props)
    assert any("canal de radar" in p.titulo.lower() for p in props)  # ensancha el radar


def test_fuentes_registry_es_expandible():
    reg = FuenteRegistry()
    reg.registrar(Fuente.PROCESO, lambda **k: [Necesidad(titulo="interno", fuente=Fuente.PROCESO)])
    reg.registrar(
        Fuente.RED,
        lambda **k: [Necesidad(titulo="externo", tipo=TipoNecesidad.MEJORA, fuente=Fuente.RED)],
    )
    out = reg.detectar(fuentes=[Fuente.PROCESO, Fuente.RED])
    assert {n.fuente for n in out} == {Fuente.PROCESO, Fuente.RED}


def test_oportunidades_store_persiste_y_dedup():
    with tempfile.TemporaryDirectory() as d:
        s = OportunidadStore(store_path=Path(d) / "op.json")
        n = Necesidad(titulo="hallazgo", fuente=Fuente.RED, procedencia=["https://u"])
        assert len(s.registrar([n])) == 1
        # el MISMO hallazgo no se vuelve a registrar (dedup por procedencia)
        repe = Necesidad(titulo="hallazgo", fuente=Fuente.RED, procedencia=["https://u"])
        assert len(s.registrar([repe])) == 0
        assert len(OportunidadStore(store_path=Path(d) / "op.json").list()) == 1


def test_ciclo_multifuente_autoria_tool_y_persiste_hallazgos_red():
    nombre = "fab_demo_iva_multi"
    tool_registry._tools.pop(nombre, None)

    def fake_get(url, **kw):
        if "github" in url:
            return _Resp(
                data={
                    "items": [
                        {
                            "full_name": "a/b",
                            "html_url": "https://gh/a",
                            "description": "d",
                            "stargazers_count": 10,
                        }
                    ]
                }
            )
        if "algolia" in url:
            return _Resp(
                data={
                    "hits": [
                        {
                            "title": "Noticia de mercado",
                            "url": "https://n",
                            "points": 5,
                            "objectID": "1",
                        }
                    ]
                }
            )
        return _Resp(status=404)  # arxiv/boe: sin datos en el test

    with tempfile.TemporaryDirectory() as d:
        store = PropuestaStore(store_path=Path(d) / "p.json")
        store_op = OportunidadStore(store_path=Path(d) / "op.json")
        informe = ejecutar_ciclo(
            llm=_stub_llm(nombre),
            memoria=_memoria_con_necesidad(),
            store_runs=SimpleNamespace(list=lambda: []),
            store_prop=store,
            store_op=store_op,
            fuentes=[Fuente.PROCESO, Fuente.RED, Fuente.META],
            http_get=fake_get,
            max_necesidades=1,
            max_intentos=1,
        )
        # DENTRO: la fuente interna autorizó una tool (PENDIENTE, gate)
        assert len(informe["tools"]["propuestas_pendientes_nuevas"]) == 1
        # FUERA + META: trajeron hallazgos citados, persistidos para revisión
        assert informe["hallazgos_red_meta"]["nuevos"] >= 1
        assert len(store_op.list()) >= 1
    tool_registry._tools.pop(nombre, None)


# ── 7. Automejora INTERNA: marcar el código en uso y proponer reparación ────────


def test_interno_marca_oversize_y_todo(tmp_path):
    big = tmp_path / "grande.py"
    big.write_text("\n".join(f"v{i} = {i}" for i in range(420)) + "\n", encoding="utf-8")
    (tmp_path / "pendiente.py").write_text("x = 1  # TODO: arreglar esto\n", encoding="utf-8")
    necs = marcar(raiz=tmp_path)
    assert any("grande.py" in n.titulo and ">400" in n.titulo for n in necs)
    assert any("TODO" in n.titulo for n in necs)
    assert all(n.fuente == Fuente.COGNICION for n in necs)


def test_reparar_propone_diff_validado(tmp_path):
    objetivo = tmp_path / "modulo.py"
    objetivo.write_text("x=1\n", encoding="utf-8")  # sin formatear
    stub = SimpleNamespace(chat=lambda **kw: SimpleNamespace(content="x = 1\n"))
    res = proponer_parche(objetivo, "formatea el módulo", llm=stub)
    assert res is not None and res["ok"] is True
    assert res["diff"] and "x = 1" in res["diff"]
    # INVARIANTE: el reparador NO escribe el fichero (sigue sin formatear)
    assert objetivo.read_text(encoding="utf-8") == "x=1\n"


def test_reparar_rechaza_diff_que_no_compila(tmp_path):
    objetivo = tmp_path / "modulo.py"
    objetivo.write_text("x = 1\n", encoding="utf-8")
    stub = SimpleNamespace(chat=lambda **kw: SimpleNamespace(content="def (:\n  roto\n"))
    res = proponer_parche(objetivo, "rómpelo", llm=stub)
    assert res is not None and res["ok"] is False
    assert "parse_black" in res["validacion"]  # rechazado: no compila


def test_reparar_rechaza_si_borra_api_en_uso(tmp_path):
    # El fallo clásico del modelo: "mejora el docstring" → devuelve medio fichero y borra la API.
    objetivo = tmp_path / "modulo.py"
    objetivo.write_text("CONFIG = 1\n\n\ndef publica():\n    return CONFIG\n", encoding="utf-8")
    stub = SimpleNamespace(chat=lambda **kw: SimpleNamespace(content='"""solo el docstring"""\n'))
    res = proponer_parche(objetivo, "mejora el docstring", llm=stub)
    assert res["ok"] is False
    assert "api" in res["validacion"]  # el guard de API en uso lo frena
    assert "CONFIG" in res["validacion"]["api"] and "publica" in res["validacion"]["api"]


def test_reparar_validacion_de_comportamiento(tmp_path):
    # Segundo cinturón: corre los tests contra el parche en un repo aislado (lo que el guard
    # estático NO ve). Repo de pega mínimo: un módulo + su test de comportamiento.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mymod.py").write_text("def suma(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "test_mymod.py").write_text(
        "from mymod import suma\n\n\ndef test_suma():\n    assert suma(2, 3) == 5\n",
        encoding="utf-8",
    )
    # parche que MANTIENE el comportamiento → tests verdes
    ok, _ = validar_comportamiento(
        "mymod.py", "def suma(a, b):\n    return b + a\n", raiz_repo=repo
    )
    assert ok is True
    # parche que ROMPE el comportamiento → tests rojos (lo que el estático no detecta)
    roto, detalle = validar_comportamiento(
        "mymod.py", "def suma(a, b):\n    return a - b\n", raiz_repo=repo
    )
    assert roto is False and "ROJOS" in detalle
