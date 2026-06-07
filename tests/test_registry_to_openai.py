"""
Regresión: to_openai debe aceptar `profile` (el AgentLoop lo llama con
profile=run.profile). Antes lanzaba TypeError y dejaba el run colgado en
'running' para siempre.
"""

from loombit_operator.tools.registry import ToolDefinition, ToolRegistry


def _reg():
    r = ToolRegistry()
    r.register(
        ToolDefinition(
            name="t1",
            description="d",
            parameters={"type": "object", "properties": {}},
            fn=lambda: 1,
        )
    )
    return r


def test_to_openai_accepts_profile():
    r = _reg()
    schema = r.to_openai(profile="administrativo")
    assert isinstance(schema, list) and len(schema) == 1
    assert schema[0]["function"]["name"] == "t1"


def test_to_openai_accepts_category_and_profile_together():
    r = _reg()
    assert r.to_openai(category="base", profile="contabilidad")  # no lanza
    assert r.to_openai() == r.to_openai(profile=None)


def test_global_registry_to_openai_with_profile():
    # El registro real (con todas las tools) también debe responder al profile.
    from loombit_operator.tools import tool_registry

    schema = tool_registry.to_openai(profile="administrativo")
    assert isinstance(schema, list) and len(schema) > 0
