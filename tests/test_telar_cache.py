"""Caché del telar: servido al instante desde caché (memoria→disco) + refresco en 2º plano.

Mata la pantalla en blanco al abrir Loombit (auditoría UX P0-3): el telar ya no espera a Google en
cada request. A diferencia de la galaxia, persiste en disco → tras reiniciar sirve el último bueno.
"""

from __future__ import annotations

import time

from loombit_operator import telar_cache


class _Counter:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> dict:
        self.n += 1
        return {"saludo": "Hola", "hilos": [], "meta": {"gen": self.n}}


def _isolate(monkeypatch, tmp_path) -> None:
    telar_cache._reset_para_tests()
    monkeypatch.setattr(telar_cache, "_cache_path", lambda: tmp_path / "telar_cache.json")


def test_frio_computa_una_vez_y_anota_cache(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    c = _Counter()
    d = telar_cache.get_telar(tejer=c)
    assert c.n == 1
    assert d["meta"]["cache"]["edad_s"] == 0
    assert d["hilos"] == []


def test_caliente_sirve_cacheado_sin_recomputar(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    c = _Counter()
    telar_cache.get_telar(tejer=c)  # frío → computa (n=1)
    d = telar_cache.get_telar(tejer=c)  # fresco (<_REFRESH_AFTER) → cacheado, sin recomputar
    assert c.n == 1
    assert d["meta"]["gen"] == 1


def test_sirve_desde_disco_tras_reinicio(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    c = _Counter()
    telar_cache.get_telar(tejer=c)  # escribe el caché a disco
    telar_cache._reset_para_tests()  # "reinicio": memoria vacía, disco intacto
    d = telar_cache.get_telar(tejer=c)
    assert d["meta"]["gen"] == 1  # vino del disco
    assert c.n == 1  # no recomputó síncrono


def test_viejo_se_sirve_al_instante_y_refresca_detras(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    c = _Counter()
    telar_cache.get_telar(tejer=c)  # n=1
    telar_cache._mem["ts"] = time.time() - (telar_cache._REFRESH_AFTER + 5)  # envejece
    d = telar_cache.get_telar(tejer=c)  # sirve el viejo YA + dispara refresco de fondo
    assert d["meta"]["gen"] == 1  # instantáneo: el viejo
    for _ in range(200):
        if c.n >= 2:
            break
        time.sleep(0.01)
    assert c.n == 2  # refrescó por detrás


def test_warm_calienta_sin_bloquear(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    c = _Counter()
    telar_cache.warm(tejer=c)
    for _ in range(200):
        if telar_cache._mem is not None:
            break
        time.sleep(0.01)
    assert telar_cache._mem is not None
    assert c.n == 1
