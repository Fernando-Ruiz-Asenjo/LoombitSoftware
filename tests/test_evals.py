"""El eval-set determinista es parte de CI: cada cambio se mide contra él (método de evals).

Si tocas el agente y rompes un comportamiento de la taxonomía F1-F8, este test lo caza.
"""

import pytest

from evals.cases import CASES

_DETERMINISTAS = [e for e in CASES if e.check is not None and not e.needs_llm]


@pytest.mark.parametrize("ev", _DETERMINISTAS, ids=[e.id for e in _DETERMINISTAS])
def test_eval_case(ev):
    ok, detalle = ev.check()
    assert ok, f"[{ev.taxon}] {ev.id}: {detalle}"
