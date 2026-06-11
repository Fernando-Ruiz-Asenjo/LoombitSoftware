"""
conducta.py — RECIBOS DE CONDUCTA: mecanizar lo "no mecanizable" exigiéndole evidencia cuantificable.

Las normas de conducta de la brújula (mejora lo que se te pide, INNOVACIÓN, veredicto con lectura…) no
las puede JUZGAR una máquina. Pero sí puede **exigir que cada acto de conducta deje un recibo con números
y un suelo de valor**, y RECHAZAR los de bajo valor o sin evidencia. Así la conducta deja de ser "confía en
mi palabra" y pasa a ser "enséñame el recibo cuantificable" — y el gate lo valida (§META-1, D-70).

Ejemplo (lo pidió Fernando): si mejoras un prompt, no vale "lo mejoré"; el recibo exige `antes_score`,
`despues_score`, el `eval` usado y `n_casos` — y se RECHAZA si no mejora de verdad.

Mismo patrón que `ui_spec.py`: vocabulario CERRADO de tipos de recibo + validador determinista. El LLM
PROPONE el recibo; el código DISPONE si cuenta. No juzga si la idea es "buena"; exige que sea **medible y
por encima de un suelo** — lo que filtra el ruido de bajo valor.
"""

from __future__ import annotations

from typing import Any

# Suelos (ratchet; el test de integridad vigila que no se bajen a escondidas).
VALOR_MIN = 2  # innovación: valor 1-5; por debajo = bajo valor, no cuenta
N_CASOS_MIN = 3  # mejora de prompt: el eval debe correr sobre >= 3 casos
MIN_TEXTO = 12  # un campo de texto por debajo de esto es humo, no evidencia

# Pistas de verificabilidad: «cómo se prueba» debe nombrar un mecanismo real, no una intención vaga.
_PISTAS_PRUEBA = (
    "test",
    "golden",
    "eval",
    "recibo",
    "auditor",
    "fuzz",
    "mutaci",
    "live",
    "/",
    ".py",
)

_TIPOS: dict[str, dict[str, set[str]]] = {
    "innovacion": {
        "required": {"tipo", "que", "por_que", "fase", "como_se_prueba", "valor"},
        "optional": {"fecha", "ref"},
    },
    "mejora_prompt": {
        "required": {"tipo", "antes_score", "despues_score", "eval", "n_casos"},
        "optional": {"fecha", "ref", "diff"},
    },
    "mejora_generica": {
        "required": {"tipo", "metrica", "antes", "despues"},
        "optional": {"fecha", "ref"},
    },
    "veredicto": {
        "required": {"tipo", "fuente", "leido_integro", "veredicto"},
        "optional": {"fecha", "nota"},
    },
    # NORTE / §EST: el foso y la estrategia dejan de ser "va bien" y pasan a un NÚMERO medido.
    "metrica_traccion": {
        "required": {"tipo", "metrica", "valor", "periodo"},
        "optional": {"cohorte", "fecha", "ref", "nota"},
    },
    # §META-2: retirar una norma no se hace en silencio — deja escrito qué, cuánto costaba y por qué.
    "retirada": {
        "required": {"tipo", "norma", "coste", "beneficio", "justificacion", "destino"},
        "optional": {"fecha", "ref"},
    },
}
TIPOS = frozenset(_TIPOS)
_VEREDICTOS = frozenset({"adopt", "learn", "avoid"})
_VEREDICTO_FUERTE = frozenset(
    {"adopt", "avoid"}
)  # un veredicto fuerte exige lectura íntegra (D-58)


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _texto_ok(x: Any) -> bool:
    return isinstance(x, str) and len(x.strip()) >= MIN_TEXTO


def validate_recibo(recibo: Any) -> tuple[bool, list[str]]:
    """Valida un recibo de conducta contra el vocabulario cerrado + suelos cuantificables. (ok, errores).
    No juzga si la conducta es "buena"; exige que sea MEDIBLE y por encima del suelo (filtra bajo valor).
    """
    errores: list[str] = []
    if not isinstance(recibo, dict):
        return False, ["el recibo debe ser un objeto"]
    tipo = recibo.get("tipo")
    if tipo not in TIPOS:
        return False, [f"tipo no permitido «{tipo}» (vocabulario: {sorted(TIPOS)})"]
    schema = _TIPOS[tipo]
    claves = set(recibo)
    faltan = schema["required"] - claves
    if faltan:
        errores.append(f"faltan campos requeridos {sorted(faltan)}")
    extra = claves - schema["required"] - schema["optional"]
    if extra:
        errores.append(f"campos no permitidos {sorted(extra)}")

    if tipo == "innovacion":
        v = recibo.get("valor")
        if not (isinstance(v, int) and 1 <= v <= 5):
            errores.append("valor debe ser entero 1-5")
        elif v < VALOR_MIN:
            errores.append(f"valor {v} < suelo {VALOR_MIN}: propuesta de BAJO VALOR (no cuenta)")
        for campo in ("que", "por_que", "fase", "como_se_prueba"):
            if not _texto_ok(recibo.get(campo)):
                errores.append(
                    f"«{campo}» vacío o trivial (>= {MIN_TEXTO} caracteres de evidencia)"
                )
        cmp_ = str(recibo.get("como_se_prueba", "")).lower()
        if _texto_ok(recibo.get("como_se_prueba")) and not any(p in cmp_ for p in _PISTAS_PRUEBA):
            errores.append(
                "«como_se_prueba» no nombra un mecanismo verificable (test/eval/golden/…)"
            )
    elif tipo == "mejora_prompt":
        a, d = recibo.get("antes_score"), recibo.get("despues_score")
        if not (_num(a) and _num(d)):
            errores.append("antes_score y despues_score deben ser números")
        elif isinstance(d, (int, float)) and isinstance(a, (int, float)) and d <= a:
            errores.append(f"despues_score ({d}) <= antes_score ({a}): NO es una mejora")
        n = recibo.get("n_casos")
        if not (isinstance(n, int) and n >= N_CASOS_MIN):
            errores.append(
                f"n_casos debe ser entero >= {N_CASOS_MIN} (un eval serio, no anecdótico)"
            )
        if not _texto_ok(recibo.get("eval")):
            errores.append("«eval» (qué eval se usó) vacío o trivial")
    elif tipo == "mejora_generica":
        a, d = recibo.get("antes"), recibo.get("despues")
        if not (_num(a) and _num(d)):
            errores.append("antes y despues deben ser números (medible)")
        elif a == d:
            errores.append("antes == despues: no hay mejora MEDIBLE")
        if not _texto_ok(recibo.get("metrica")):
            errores.append("«metrica» (qué se mide y en qué unidad) vacío o trivial")
    elif tipo == "veredicto":
        if not isinstance(recibo.get("leido_integro"), bool):
            errores.append("leido_integro debe ser booleano")
        ver = recibo.get("veredicto")
        if ver not in _VEREDICTOS:
            errores.append(f"veredicto debe ser uno de {sorted(_VEREDICTOS)}")
        elif ver in _VEREDICTO_FUERTE and recibo.get("leido_integro") is not True:
            errores.append(f"veredicto fuerte «{ver}» exige leido_integro=True (D-58)")
        if not _texto_ok(recibo.get("fuente")):
            errores.append("«fuente» vacía o trivial")
    elif tipo == "metrica_traccion":
        if not _num(recibo.get("valor")):
            errores.append("«valor» debe ser un NÚMERO medido (no «va bien»)")
        if not _texto_ok(recibo.get("metrica")):
            errores.append("«metrica» (qué se mide y en qué unidad) vacía o trivial")
        if not _texto_ok(recibo.get("periodo")):
            errores.append("«periodo» (cuándo/sobre qué se midió) vacío o trivial")
    elif tipo == "retirada":
        for campo in ("norma", "coste", "beneficio", "justificacion", "destino"):
            if not _texto_ok(recibo.get(campo)):
                errores.append(
                    f"«{campo}» vacío o trivial (retirar una norma exige justificación a la vista)"
                )

    return (not errores, errores)


class ReciboInvalido(ValueError):
    def __init__(self, errores: list[str]) -> None:
        super().__init__("; ".join(errores))
        self.errores = errores


def exigir_recibo(recibo: Any) -> dict[str, Any]:
    """Devuelve el recibo si es válido; si no, lanza `ReciboInvalido`. Un acto de conducta sin recibo
    válido NO cuenta — esa es la transformación de HUMANO a contabilizable."""
    ok, errores = validate_recibo(recibo)
    if not ok:
        raise ReciboInvalido(errores)
    return recibo
