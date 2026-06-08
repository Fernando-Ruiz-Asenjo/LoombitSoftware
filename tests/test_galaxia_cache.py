"""Pre-carga de la Galaxia: stale-while-revalidate (instantáneo + frescura)."""

from __future__ import annotations

from loombit_operator import galaxia_cache


def _reset() -> None:
    galaxia_cache._snap = None
    galaxia_cache._ts = 0.0
    galaxia_cache._refreshing = False


class _Counter:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> dict:
        self.n += 1
        return {"sol": {}, "nodos": [], "aristas": [], "meta": {"gen": self.n}}


def test_frio_construye_una_vez_y_anota_edad(monkeypatch) -> None:
    _reset()
    c = _Counter()
    monkeypatch.setattr(galaxia_cache, "build_galaxia", c)
    d = galaxia_cache.get()
    assert c.n == 1
    assert "edad_seg" in d["meta"]


def test_caliente_y_fresco_no_reconstruye(monkeypatch) -> None:
    _reset()
    c = _Counter()
    monkeypatch.setattr(galaxia_cache, "build_galaxia", c)
    galaxia_cache.get()  # frío → construye (n=1)
    galaxia_cache.get(max_age=999)  # fresco → sirve cacheado, sin reconstruir
    assert c.n == 1


def test_force_reconstruye(monkeypatch) -> None:
    _reset()
    c = _Counter()
    monkeypatch.setattr(galaxia_cache, "build_galaxia", c)
    galaxia_cache.get()
    galaxia_cache.get(force=True)
    assert c.n == 2


def test_prewarm_no_bloquea_y_calienta(monkeypatch) -> None:
    _reset()
    c = _Counter()
    monkeypatch.setattr(galaxia_cache, "build_galaxia", c)
    galaxia_cache.prewarm()
    # prewarm lanza un hilo daemon; esperamos un pelín a que construya.
    import time

    for _ in range(50):
        if galaxia_cache._snap is not None:
            break
        time.sleep(0.01)
    assert galaxia_cache._snap is not None
