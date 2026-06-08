"""
interno.py — fuente COGNICION: la Fábrica mira su PROPIO código en uso y marca qué mejorar.

"Lo de dentro" a nivel de implementación: escanea el código que ya está programado y funcionando y
**marca** señales reales y de alto valor (no ruido de estilo): posibles BUGS (ruff bugbear),
trabajo pendiente (TODO/FIXME), ficheros que rompen la regla de <400 líneas, prompts del sistema
auto-evolucionables, y huecos sin eval. Cada señal con su `file:line`. La REPARACIÓN la propone
`reparar.py` como diff con gate — aquí solo se detecta (marcar), de forma determinista.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from .modelos import Fuente, Necesidad, TipoNecesidad

_RAIZ_DEFECTO = Path(__file__).resolve().parent.parent  # loombit_operator/
_EXCLUIR = ("__pycache__", "fabrica/generadas", "static")
_TODO_RE = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)\b[:\s]?(.*)", re.IGNORECASE)
_PROMPT_RE = re.compile(
    r"^([A-Z_][A-Z0-9_]*(?:SYSTEM|SYS|PROMPT|SISTEMA)[A-Z0-9_]*)\s*=", re.MULTILINE
)
_MAX_LINEAS = 400


def _ficheros(raiz: Path) -> list[Path]:
    return [p for p in raiz.rglob("*.py") if not any(x in p.as_posix() for x in _EXCLUIR)]


def _rel(p: Path, raiz: Path) -> str:
    try:
        return p.relative_to(raiz.parent).as_posix()
    except ValueError:
        return p.name


# ── Detectores deterministas ────────────────────────────────────────────────────


def _bugs_ruff(raiz: Path, limite: int) -> list[Necesidad]:
    """Posibles BUGS (no estilo): ruff flake8-bugbear sobre el código en uso."""
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--select=B",
                "--output-format=json",
                str(raiz),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        issues = json.loads(proc.stdout or "[]")
    except Exception:  # noqa: BLE001 — sin ruff, este detector simplemente no aporta
        return []
    necesidades: list[Necesidad] = []
    for it in issues[:limite]:
        archivo = it.get("filename", "")
        linea = (it.get("location") or {}).get("row", "?")
        ref = f"{Path(archivo).name}:{linea}"
        necesidades.append(
            Necesidad(
                titulo=f"Posible bug ({it.get('code')}): {it.get('message', '')[:90]} [{ref}]",
                tipo=TipoNecesidad.FIX,
                fuente=Fuente.COGNICION,
                descripcion="Detectado por ruff bugbear en el código en uso. Revisar y reparar.",
                evidencia=[it.get("message", "")[:200]],
                prioridad=5,
                procedencia=[ref],
            )
        )
    return necesidades


def _todos(ficheros: list[Path], raiz: Path, limite: int) -> list[Necesidad]:
    necesidades: list[Necesidad] = []
    for p in ficheros:
        try:
            lineas = p.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001
            continue
        for i, linea in enumerate(lineas, 1):
            m = _TODO_RE.search(linea)
            if m:
                necesidades.append(
                    Necesidad(
                        titulo=f"{m.group(1).upper()} pendiente: {m.group(2).strip()[:80]} [{_rel(p, raiz)}:{i}]",
                        tipo=TipoNecesidad.FIX,
                        fuente=Fuente.COGNICION,
                        descripcion="Trabajo marcado en el código que sigue sin cerrar.",
                        prioridad=3,
                        procedencia=[f"{_rel(p, raiz)}:{i}"],
                    )
                )
                if len(necesidades) >= limite:
                    return necesidades
    return necesidades


def _oversize(ficheros: list[Path], raiz: Path) -> list[Necesidad]:
    necesidades: list[Necesidad] = []
    for p in ficheros:
        try:
            n = len(p.read_text(encoding="utf-8").splitlines())
        except Exception:  # noqa: BLE001
            continue
        if n > _MAX_LINEAS:
            necesidades.append(
                Necesidad(
                    titulo=f"Fichero >400 líneas ({n}): {_rel(p, raiz)} — partir (brújula)",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.COGNICION,
                    descripcion="La brújula pide ficheros < ~400 líneas. Proponer un troceo por dominio.",
                    prioridad=2,
                    procedencia=[_rel(p, raiz)],
                )
            )
    return necesidades


def _prompts(ficheros: list[Path], raiz: Path) -> list[Necesidad]:
    """Marca los prompts del sistema como candidatos a AUTO-EVOLUCIÓN (GEPA) contra los evals."""
    encontrados: list[str] = []
    for p in ficheros:
        try:
            texto = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        for m in _PROMPT_RE.finditer(texto):
            encontrados.append(f"{_rel(p, raiz)}::{m.group(1)}")
    if not encontrados:
        return []
    return [
        Necesidad(
            titulo=f"Auto-evolucionar {len(encontrados)} prompt(s) del sistema (GEPA) contra los evals",
            tipo=TipoNecesidad.MEJORA,
            fuente=Fuente.COGNICION,
            descripcion=(
                "Los prompts del sistema se pueden mejorar reflexionando sobre las trazas reales y "
                "validando contra los evals (GEPA/TextGrad). Candidatos: "
                + ", ".join(encontrados[:12])
            ),
            evidencia=encontrados[:12],
            prioridad=3,
            procedencia=["interno:prompts"],
        )
    ]


def _huecos_eval() -> list[Necesidad]:
    try:
        from ..selfcheck import run_selfcheck

        pend = run_selfcheck().get("pendientes_sin_eval") or []
    except Exception:  # noqa: BLE001
        return []
    if not pend:
        return []
    return [
        Necesidad(
            titulo=f"Cubrir {len(pend)} hueco(s) sin eval (subir cobertura de comportamiento)",
            tipo=TipoNecesidad.MEJORA,
            fuente=Fuente.COGNICION,
            descripcion="Capacidades sin eval: " + ", ".join(map(str, pend[:12])),
            evidencia=[str(x) for x in pend[:12]],
            prioridad=2,
            procedencia=["interno:evals"],
        )
    ]


def marcar(raiz: Path | None = None, max_items: int = 20) -> list[Necesidad]:
    """Escanea el código en uso y devuelve las señales de mejora más prioritarias (bugs primero)."""
    raiz = raiz or _RAIZ_DEFECTO
    ficheros = _ficheros(raiz)
    necesidades: list[Necesidad] = []
    necesidades += _bugs_ruff(raiz, limite=10)
    necesidades += _todos(ficheros, raiz, limite=10)
    necesidades += _oversize(ficheros, raiz)
    necesidades += _prompts(ficheros, raiz)
    necesidades += _huecos_eval()
    necesidades.sort(key=lambda n: n.prioridad, reverse=True)
    return necesidades[:max_items]
