"""
COBERTURA DEL GOBIERNO — «díselo a GitHub: toda la brújula y todo el gobierno» (§GOB-2 + §META-1, D-69).

No se puede hacer que una máquina "pase" las normas de CONDUCTA (mejora lo que se te pide, cognición no
extracción…). Pretenderlo sería mentir. Lo que SÍ se puede —y es lo máximo honesto— es que el gate
**contabilice la brújula ENTERA**: cada norma queda mapeada a uno de cuatro estados, y un meta-check se
pone ROJO si **una sola norma de la brújula queda sin contabilizar** (punto ciego) o si se afirma un check
automático cuyo arnés no existe (enforcement de mentira).

Estados:
  AUTOMÁTICO → un check del gate lo verifica (se nombra el arnés y se comprueba que EXISTE).
  PARCIAL    → parte se verifica por máquina; el resto se declara.
  HUMANO     → norma de conducta/juicio: NINGUNA máquina puede verificarla; la verifica una persona.
  PENDIENTE  → debería mecanizarse y aún no está (deuda declarada, no fingida).

Así "se lo decimos a GitHub": GitHub no juzga conducta, pero **garantiza que nada queda en un punto ciego**.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRUJULA = (ROOT / "docs" / "BRUJULA.md").read_text(encoding="utf-8")

AUTOMATICO, PARCIAL, HUMANO, PENDIENTE = "AUTOMÁTICO", "PARCIAL", "HUMANO", "PENDIENTE"
# RECIBO: norma de conducta vuelta contabilizable — no se juzga la conducta, se EXIGE un recibo
# cuantificable que el gate valida (D-70, `loombit_operator/conducta.py`). Transforma HUMANO en checkable.
RECIBO = "RECIBO"

# Manifiesto: TODA norma de la brújula (Partes I-III) → (estado, arnés/evidencia o motivo).
# La clave es el nombre de la sección `###` tal cual aparece en BRUJULA.md (antes del «—»).
MANIFIESTO: dict[str, tuple[str, str]] = {
    # ── Parte I · Constitución ────────────────────────────────────────────────
    "Ley 0": (
        RECIBO,
        "«Mejora lo que se te pide» → recibo de conducta CUANTIFICABLE (`loombit_operator/conducta.py`: "
        "mejora_prompt / mejora_generica con antes/después medibles), validado en `tests/test_conducta.py`. "
        "El juicio fino lo da Fernando, pero el bajo valor sin números ya NO cuenta.",
    ),
    "Ley FUNDACIONAL": (
        PARCIAL,
        "El plano de autoridad (§GOB-1) tiene golden `tests/test_gob1_authority_plane.py`; el resto (que el "
        "LLM no esté en NINGÚN camino de confianza) es de diseño/conducta → humano.",
    ),
    "NORTE": (
        HUMANO,
        "Foso/north-star = métrica de retención en Fase 4, no un unit test (§EST-1).",
    ),
    "PRODUCTO": (
        PARCIAL,
        "«Cifras por código» lo cazan `scripts/auditoria_cobro.py` + `fuzz_invariantes.py`; «cognición, "
        "acierta al 100%, UX cálida» son conducta → humano.",
    ),
    "INGENIERÍA": (
        AUTOMATICO,
        "Gate canónico `scripts/verify.py` (black+ruff+pytest) + tamaño <400 en "
        "`tests/test_brujula_cumplimiento.py`. «Rama por cambio / verifica en vivo» = proceso/humano.",
    ),
    "INNOVACIÓN": (
        RECIBO,
        "→ recibo de conducta (`conducta.py`): tipo `innovacion` exige QUÉ/POR QUÉ/fase/CÓMO-se-prueba + "
        "`valor` >= suelo (rechaza bajo valor); tipo `veredicto` mecaniza D-58 (veredicto fuerte exige "
        "lectura íntegra). Validado en `tests/test_conducta.py` + recibos en `docs/RECIBOS_CONDUCTA.jsonl`.",
    ),
    # ── Parte II · Gobierno ───────────────────────────────────────────────────
    "§GOB-1": (
        AUTOMATICO,
        "golden `tests/test_gob1_authority_plane.py` (10) + plano en `policy/authority_plane.py`.",
    ),
    "§GOB-2": (
        AUTOMATICO,
        "gate canónico único (`scripts/verify.py`, hook+CI sin drift) + integridad "
        "`tests/test_gate_integridad.py` + ESTA contabilidad. §GOB-2b: el CI corre `--strict --live`.",
    ),
    "§GOB-3": (
        PARCIAL,
        "Auditor≠constructor: `.github/CODEOWNERS` nombra a Fernando dueño de los ficheros del gate y la "
        "constitución → tocarlos pide SU review (el constructor no se aprueba a sí mismo). La mutación "
        "mitiga (dientes). Residuo: el enforcement duro exige «Require review from Code Owners» en la "
        "protección de rama (ajuste del repo, de Fernando).",
    ),
    "§GOB-4": (
        PARCIAL,
        "Mutación en el gate ✅ `scripts/mutation_test.py` (dientes). Held-out + gap Δ: pendiente.",
    ),
    "§SEG": (
        PARCIAL,
        "§SEG-2 datos≠órdenes con golden `tests/test_seg_inyeccion.py` (7) ✅. §SEG-1/3/4/5/6/7 "
        "(suite de inyección ampliada, memoria firmada, red-team): pendiente/declarado.",
    ),
    "§DATOS": (
        PARCIAL,
        "datos≠órdenes (§SEG-2) cubre la frontera de lectura; el gobierno de datos completo, pendiente.",
    ),
    "§CONC": (
        HUMANO,
        "Concurrencia multiagente (worktree, no tocar WIP ajeno): disciplina de proceso — no unit-testeable.",
    ),
    "§14B": (
        PENDIENTE,
        "Gobierno dimensionado al 14B (parser POST-LLM de cifras, goldens de presión): sin construir.",
    ),
    "§EST": (
        HUMANO,
        "Estrategia/tracción: coste de cambio, DAU/churn/NPS en Fase 4 — métricas de negocio, no unit tests.",
    ),
    # ── Parte III · Meta-gobierno ─────────────────────────────────────────────
    "§META-1": (
        PARCIAL,
        "Sensor de drift: ESTA contabilidad + `tests/test_brujula_cumplimiento.py` son el primer sensor "
        "(cazan punto ciego y deuda de tamaño). El sensor completo (`verify_brujula.py` + DEUDA_NORMATIVA): pendiente.",
    ),
    "§META-2": (
        HUMANO,
        "Retirada honorable de una norma: decisión de proceso (PR de Fernando) — no mecanizable.",
    ),
    "§META-3": (
        PARCIAL,
        "Sync de la cabecera `CLAUDE.md` con la norma canónica: `tests/test_brujula_cumplimiento.py`. El "
        "procedimiento (rama+PR+DECISIONES+OK) es proceso/humano.",
    ),
    "§META-4": (
        AUTOMATICO,
        "Estado fuera de la constitución: `tests/test_brujula_cumplimiento.py` (tabla §GOB-2 sin huecos) + "
        "el estado volátil vive en `ESTADO_Y_ROADMAP.md`.",
    ),
    "§META-5": (
        HUMANO,
        "El techo (gobierno mínimo y honesto, Tier 3): filosofía/criterio — no mecanizable.",
    ),
}

# Arneses nombrados que DEBEN existir si se afirma AUTOMÁTICO/PARCIAL (no se afirma enforcement de mentira).
_ARNESES = [
    "tests/test_gob1_authority_plane.py",
    "tests/test_seg_inyeccion.py",
    "tests/test_gate_integridad.py",
    "tests/test_brujula_cumplimiento.py",
    "loombit_operator/conducta.py",
    "tests/test_conducta.py",
    ".github/CODEOWNERS",
    "scripts/verify.py",
    "scripts/mutation_test.py",
    "scripts/auditoria_cobro.py",
    "scripts/fuzz_invariantes.py",
    "loombit_operator/policy/authority_plane.py",
]


def _secciones_norma() -> set[str]:
    """Las normas de la brújula = encabezados `### ` de las Partes I-III (hasta la tabla Parte IV)."""
    out: set[str] = set()
    for ln in BRUJULA.splitlines():
        if ln.startswith("## PARTE IV"):
            break
        if ln.startswith("### "):
            nombre = ln[4:].split("—")[0].strip()
            out.add(nombre)
    return out


def test_toda_norma_de_la_brujula_esta_contabilizada():
    """Ni un punto ciego: cada norma `###` de la brújula tiene entrada en el manifiesto, y al revés."""
    secciones = _secciones_norma()
    manifiesto = set(MANIFIESTO)
    sin_contabilizar = secciones - manifiesto
    assert not sin_contabilizar, (
        "NORMAS DE LA BRÚJULA SIN CONTABILIZAR (punto ciego — añádelas al manifiesto):\n  "
        + "\n  ".join(sorted(sin_contabilizar))
    )
    fantasma = manifiesto - secciones
    assert not fantasma, (
        "Entradas del manifiesto que ya no son normas de la brújula (¿renombrada/eliminada?):\n  "
        + "\n  ".join(sorted(fantasma))
    )


def test_lo_marcado_automatico_o_parcial_tiene_arnes_real():
    """Si una norma se declara AUTOMÁTICO o PARCIAL, su arnés debe EXISTIR (no enforcement de mentira)."""
    faltan = [a for a in _ARNESES if not (ROOT / a).exists()]
    assert (
        not faltan
    ), "Se afirma un check cuyo arnés NO existe (enforcement de mentira):\n  " + "\n  ".join(faltan)


def test_los_estados_son_validos():
    """Cada norma tiene un estado del vocabulario cerrado y una evidencia/motivo no vacío."""
    validos = {AUTOMATICO, PARCIAL, HUMANO, PENDIENTE, RECIBO}
    for norma, (estado, evidencia) in MANIFIESTO.items():
        assert estado in validos, f"{norma}: estado inválido «{estado}»"
        assert (
            evidencia.strip()
        ), f"{norma}: sin evidencia/motivo (una norma sin mecanismo es decoración)"
