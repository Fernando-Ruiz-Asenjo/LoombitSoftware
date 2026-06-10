"""A1 — descomposición multi-intención: lógica DETERMINISTA (gate de claridad, umbrales, compose).
El LLM se inyecta FALSO (JSON canónico) → estos tests no tocan LM Studio. La clasificación real del
14B se cubre en el arnés de presión."""

from types import SimpleNamespace

from loombit_operator.agent import descomposicion as D
from loombit_operator.agent.descomposicion import Sub


class _FakeLLM:
    """Devuelve un content fijo por llamada (lista de respuestas en orden)."""

    def __init__(self, respuestas):
        self._r = list(respuestas)
        self.calls = []

    def chat(self, messages, temperature=None, **kw):
        self.calls.append(messages)
        content = self._r.pop(0) if self._r else "{}"
        return SimpleNamespace(content=content)


def test_parece_multi_intent_solo_cross_domain():
    # cross-domain (financiero + agenda / financiero + correo) con coordinación → SÍ
    assert D.parece_multi_intent("¿cuánto me deben y qué reuniones tengo esta semana?")
    assert D.parece_multi_intent("¿cuánto facturé y qué correos de Acme tengo?")
    # mono-dominio (financiero-puro, aunque compuesto) → NO (lo cubre resumen_financiero, no A1)
    assert not D.parece_multi_intent("¿cuánto he facturado y cuánto me deben?")
    # una sola intención → NO
    assert not D.parece_multi_intent("¿qué reuniones tengo esta semana?")


def test_claridad_ponderada():
    assert D.claridad([]) == 0.0
    assert D.claridad([Sub("financiero", 1.0), Sub("agenda", 1.0)]) == 1.0
    assert abs(D.claridad([Sub("financiero", 0.8), Sub("agenda", 0.4)]) - 0.6) < 1e-9
    assert D.claridad([Sub("inexistente", 0.9)]) == 0.0  # fuera del menú → no cuenta


def test_clasificar_umbrales():
    ejec, dudosas = D.clasificar(
        [Sub("financiero", 0.9), Sub("agenda", 0.5), Sub("buscar_correo", 0.2)]
    )
    assert [s.intencion for s in ejec] == ["financiero"]  # ≥ 0.6
    assert [s.intencion for s in dudosas] == ["agenda"]  # [0.35, 0.6)
    # buscar_correo 0.2 < 0.35 → se ignora (ni ejecuta ni re-destila)


def test_parse_json_robusto():
    assert D._parse_json('```json\n{"intenciones": []}\n```') == {"intenciones": []}
    assert D._parse_json('blah {"a": 1} cola') == {"a": 1}
    assert D._parse_json("sin json aquí") == {}


def test_resolver_multi_intent_ejecuta_dos():
    llm = _FakeLLM(
        ['{"intenciones":[{"id":"financiero","confianza":0.9},{"id":"agenda","confianza":0.8}]}']
    )
    subs = D.resolver("¿cuánto me deben y qué reuniones tengo esta semana?", llm)
    assert {s.intencion for s in subs} == {"financiero", "agenda"}
    assert len(llm.calls) == 1  # sin dudosas → no hay 2ª pasada


def test_resolver_redestila_las_dudosas():
    llm = _FakeLLM(
        [
            '{"intenciones":[{"id":"financiero","confianza":0.9},{"id":"agenda","confianza":0.45}]}',
            '{"intenciones":[{"id":"financiero","confianza":0.9},{"id":"agenda","confianza":0.8}]}',
        ]
    )
    subs = D.resolver("¿cuánto me deben y tengo algo en la agenda esta semana?", llm)
    assert {s.intencion for s in subs} == {"financiero", "agenda"}
    assert len(llm.calls) == 2  # hubo 2ª pasada (re-destilado de la dudosa)


def test_resolver_mono_metrica_no_aplica_ni_llama_llm():
    llm = _FakeLLM(['{"intenciones":[{"id":"financiero","confianza":0.9}]}'])
    assert D.resolver("¿cuánto he facturado este mes?", llm) == []
    assert len(llm.calls) == 0  # ni descompone (la señal barata lo descarta antes)


def test_resolver_buscar_correo_extrae_termino():
    llm = _FakeLLM(
        [
            '{"intenciones":[{"id":"financiero","confianza":0.8},'
            '{"id":"buscar_correo","confianza":0.8,"termino":"Acme"}]}'
        ]
    )
    subs = D.resolver("¿cuánto me debe Acme y qué correos suyos tengo?", llm)
    correo = next(s for s in subs if s.intencion == "buscar_correo")
    assert correo.args.get("query") == "Acme"
