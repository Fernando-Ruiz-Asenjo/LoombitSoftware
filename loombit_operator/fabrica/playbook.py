"""
playbook.py — memoria de AUTORÍA de la Fábrica (ACE: Agentic Context Engineering).

La Fábrica ya sabe proponer y validar, pero hoy cada redacción/reparación nace de CERO. Este es el
"playbook" que aprende ENTRE ciclos: reglas accionables con contadores **helpful/harmful**, actualizadas
por **delta** (nunca se reescribe el todo), que el coder consulta antes de redactar.

Inspirado en ACE (Stanford) destilado de la newsletter Mafia IA (ver ../mafia-ia-destilado/). Respeta
las reglas duras del proyecto:
  - **Sin tocar pesos**: el aprendizaje vive aquí, en texto (memoria procedimental), no en fine-tuning.
  - **Recuperación por relevancia, no volcado** (patrón ExpeL, igual que `agent/memory.relevant_lessons`).
  - **Procedencia + honestidad**: cada regla sabe de dónde salió; las dañinas se deprecan, no se borran.
  - **Local**: persiste en runtime/local/, no sale de la máquina.

Fichero: runtime/local/fabrica_playbook.json
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UMBRAL_DEPRECADA = 3  # harmful ≥ esto y score < 0 → no se inyecta (queda en el archivo)


def _ahora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


# Stopwords de 3 letras: dejamos pasar términos cortos del dominio (iva, 303, 130, nif, irpf) pero
# filtramos las palabras vacías frecuentes que crearían solapes espurios.
_STOP = {
    "con",
    "los",
    "las",
    "una",
    "por",
    "del",
    "que",
    "para",
    "sin",
    "como",
    "este",
    "esta",
    "ese",
    "esa",
    "sus",
    "mas",
    "más",
    "dos",
    "uno",
    "fin",
    "han",
    "hay",
    "ser",
    "muy",
}


def _tokens(texto: str) -> set[str]:
    """Tokens significativos. Umbral ≥3 (no ≥4) para no perder los códigos cortos del oficio
    administrativo: IVA, 303, 130, NIF, IRPF, BOE. Se filtran las stopwords frecuentes."""
    return {
        w
        for w in re.findall(r"[a-záéíóúñ0-9_]+", (texto or "").lower())
        if len(w) >= 3 and w not in _STOP
    }


# Reglas fundacionales: el saber del arnés/brújula aplicado retroactivamente — la memoria NO nace tonta
# (mismo patrón que las lecciones fundacionales de agent/memory.py). Son verdad confirmada (helpful=1).
_REGLAS_FUNDACIONALES: list[dict[str, Any]] = [
    {
        "contenido": "Toda tool DEBE traer su eval determinista (un check). Sin eval, el arnés la "
        "rechaza en la puerta 'eval'.",
        "tags": ["autoria", "tool", "eval", "arnes"],
        "fuente": "arnes:eval",
    },
    {
        "contenido": "No uses os, subprocess, eval, exec, open ni socket: el gate de seguridad bloquea "
        "el código y la tool se descarta. Escribe cómputo puro (json, datetime, math, re).",
        "tags": ["seguridad", "autoria", "tool", "codigo"],
        "fuente": "arnes:seguridad",
    },
    {
        "contenido": "El nombre de la función del source debe COINCIDIR con el nombre de la tool, o "
        "falla la puerta 'contrato'.",
        "tags": ["autoria", "contrato", "tool", "nombre"],
        "fuente": "arnes:contrato",
    },
    {
        "contenido": "Al reparar un fichero, NO elimines símbolos públicos en uso (funciones/clases/"
        "constantes sin '_'): el guard de API frena el parche. Devuelve el fichero COMPLETO.",
        "tags": ["reparar", "api", "diff", "fichero"],
        "fuente": "reparar:guard_api",
    },
    {
        "contenido": "El dinero (IVA, totales, intereses) se calcula en CÓDIGO determinista; el LLM "
        "solo narra. Nunca cifres importes con el modelo.",
        "tags": ["dinero", "fiscal", "cobros", "determinista", "importe"],
        "fuente": "brujula:dinero",
    },
    {
        "contenido": "Ficheros < ~400 líneas; si el módulo crece, trocea por dominio (la brújula).",
        "tags": ["estilo", "tamaño", "refactor", "modulo"],
        "fuente": "brujula:tamano",
    },
]


@dataclass
class ReglaPlaybook:
    """Una regla accionable de autoría, con contadores de utilidad (ACE)."""

    contenido: str
    tags: list[str] = field(default_factory=list)
    helpful: int = 0
    harmful: int = 0
    fuente: str = "fabrica"
    created: str = field(default_factory=_ahora)

    @property
    def score(self) -> int:
        return self.helpful - self.harmful

    @property
    def deprecada(self) -> bool:
        """Hizo más daño que bien de forma sostenida → no se inyecta (pero se conserva en el archivo)."""
        return self.harmful >= _UMBRAL_DEPRECADA and self.score < 0

    def tokens(self) -> set[str]:
        return _tokens(self.contenido + " " + " ".join(self.tags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contenido": self.contenido,
            "tags": self.tags,
            "helpful": self.helpful,
            "harmful": self.harmful,
            "fuente": self.fuente,
            "created": self.created,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReglaPlaybook":
        return cls(
            contenido=str(d.get("contenido", "")),
            tags=[str(t).lower() for t in d.get("tags", [])],
            helpful=int(d.get("helpful", 0)),
            harmful=int(d.get("harmful", 0)),
            fuente=str(d.get("fuente", "fabrica")),
            created=str(d.get("created", _ahora())),
        )


class Playbook:
    """Memoria de autoría de la Fábrica — persistente, local, idempotente.

    Uso típico:
        pb = Playbook()
        pb.aprender("evita devolver medio fichero al reparar", tags=["reparar"], util=False)
        bloque = pb.como_contexto("crear tool de días hábiles")   # → inyectar en el prompt del coder
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or Path("runtime/local/fabrica_playbook.json")
        self._reglas: list[ReglaPlaybook] = []
        self._load()
        self._asegurar_fundacionales()

    # ── Lectura ────────────────────────────────────────────────────────────────
    @property
    def reglas(self) -> list[ReglaPlaybook]:
        return list(self._reglas)

    def relevantes(self, texto: str, k: int = 5) -> list[ReglaPlaybook]:
        """Las K reglas más relevantes a `texto`, priorizadas por (score, helpful). No vuelca todo
        (ExpeL) y excluye las depreciadas. Si no hay solape, devuelve las de mayor score (las verdades
        fundacionales valen para cualquier autoría)."""
        objetivo = _tokens(texto)
        vivas = [r for r in self._reglas if not r.deprecada]
        con_solape = [(len(r.tokens() & objetivo), r) for r in vivas]
        con_solape = [(s, r) for s, r in con_solape if s > 0]
        if con_solape:
            con_solape.sort(key=lambda p: (p[0], p[1].score, p[1].helpful), reverse=True)
            return [r for _, r in con_solape[:k]]
        # sin solape: las más fiables (score) como red de seguridad
        return sorted(vivas, key=lambda r: (r.score, r.helpful), reverse=True)[:k]

    def como_contexto(self, texto: str, k: int = 5) -> str:
        """Bloque de texto listo para inyectar en el prompt del coder (la inyección ACE)."""
        reglas = self.relevantes(texto, k)
        if not reglas:
            return ""
        return "REGLAS DE AUTORÍA APRENDIDAS (aplícalas):\n" + "\n".join(
            f"  • {r.contenido}" for r in reglas
        )

    # ── Escritura (delta, nunca reescribe el todo) ───────────────────────────────
    def aprender(
        self,
        contenido: str,
        tags: list[str] | None = None,
        util: bool = True,
        fuente: str = "fabrica",
    ) -> ReglaPlaybook:
        """Registra o refuerza una regla. Dedup por contenido (case-insensitive). `util=True` suma
        helpful (funcionó); `util=False` suma harmful (estorbó/se rechazó)."""
        clave = contenido.strip().lower()
        for r in self._reglas:
            if r.contenido.strip().lower() == clave:
                if util:
                    r.helpful += 1
                else:
                    r.harmful += 1
                if tags:
                    r.tags = sorted({*r.tags, *[t.lower() for t in tags]})
                self._save()
                return r
        regla = ReglaPlaybook(
            contenido=contenido.strip(),
            tags=[t.lower() for t in (tags or [])],
            helpful=1 if util else 0,
            harmful=0 if util else 1,
            fuente=fuente,
        )
        self._reglas.append(regla)
        self._save()
        return regla

    def reforzar_relevantes(self, texto: str, util: bool, k: int = 3) -> int:
        """Marca como útiles/dañinas las reglas que guiaron una autoría (señal del gate humano: una
        propuesta aprobada refuerza; una rechazada/rota penaliza). Devuelve cuántas tocó."""
        tocadas = self.relevantes(texto, k)
        for r in tocadas:
            if util:
                r.helpful += 1
            else:
                r.harmful += 1
        if tocadas:
            self._save()
        return len(tocadas)

    def snapshot(self) -> dict[str, Any]:
        return {
            "store_path": str(self.store_path),
            "total": len(self._reglas),
            "depreciadas": sum(1 for r in self._reglas if r.deprecada),
            "reglas": [
                r.to_dict() for r in sorted(self._reglas, key=lambda r: r.score, reverse=True)
            ],
        }

    # ── Persistencia ─────────────────────────────────────────────────────────────
    def _asegurar_fundacionales(self) -> None:
        existentes = {r.contenido.strip().lower() for r in self._reglas}
        faltan = [
            f for f in _REGLAS_FUNDACIONALES if f["contenido"].strip().lower() not in existentes
        ]
        if faltan:
            for f in faltan:
                self._reglas.append(
                    ReglaPlaybook(
                        contenido=f["contenido"], tags=f["tags"], helpful=1, fuente=f["fuente"]
                    )
                )
            self._save()

    def _load(self) -> None:
        if not self.store_path.exists():
            self._reglas = []
            return
        try:
            texto = self.store_path.read_text(encoding="utf-8")
            data = json.loads(texto) if texto.strip() else []
            self._reglas = [ReglaPlaybook.from_dict(d) for d in data]
        except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001 — archivo corrupto: no romper
            logger.warning("No se pudo cargar fabrica_playbook.json: %s", exc)
            self._reglas = []

    def _save(self) -> None:
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store_path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps([r.to_dict() for r in self._reglas], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self.store_path)
        except OSError as exc:  # noqa: BLE001
            logger.error("No se pudo guardar fabrica_playbook.json: %s", exc)
