"""
modelos.py — tipos de datos de la Fábrica de Skills (Skill X, núcleo blanco).

El flujo: una `Necesidad` (hueco útil detectado) → un `BorradorTool` (la tool redactada por
el coder) → un `Veredicto` (qué puertas del arnés pasó) → una `PropuestaSkill` (lo que el
humano aprueba o descarta). Todo serializable a JSON para persistir el archivo/linaje.

Sin lógica: solo datos + serialización. La cognición vive en `necesidad`/`autoria`/`validacion`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def _ahora() -> str:
    return datetime.now(UTC).isoformat()


class TipoNecesidad(StrEnum):
    TOOL = "tool"  # falta una herramienta ejecutable (lo más útil y concreto)
    SKILL = "skill"  # falta una skill de dominio (manifest)
    MEJORA = "mejora"  # mejorar una skill/cognición existente (no crear de cero)
    FIX = "fix"  # un comportamiento roto que conviene arreglar


class Fuente(StrEnum):
    """De dónde nace la oportunidad. El abanico (los escenarios) es expandible: la propia Fábrica
    puede proponer fuentes nuevas (META). Cubre lo de DENTRO y lo de FUERA (la Red)."""

    PROCESO = "proceso"  # dentro: runs, propose_improvement, tools que fallan
    COGNICION = "cognicion"  # dentro: razonamiento mejorable (comprensión/cobros/fiscal)
    RED = "red"  # fuera: normativa/técnicas/competidores traídos de internet, con cita
    USUARIO = "usuario"  # dentro: aprobar/editar/rechazar del gate (señal de preferencia)
    META = "meta"  # la Fábrica amplía su propio abanico de escenarios


class EstadoPropuesta(StrEnum):
    PENDIENTE = "pendiente"  # validada, espera el gate humano
    APROBADA = "aprobada"  # Fernando la aceptó (se materializa el artefacto)
    DESCARTADA = "descartada"  # Fernando la rechazó (queda en el linaje)
    FALLIDA = "fallida"  # no pasó el arnés (queda en el linaje como peldaño)


@dataclass
class Necesidad:
    """Un hueco ÚTIL detectado (no un micro-tweak). Lleva su evidencia y procedencia."""

    titulo: str
    tipo: TipoNecesidad = TipoNecesidad.TOOL
    fuente: Fuente = Fuente.PROCESO
    descripcion: str = ""
    evidencia: list[str] = field(default_factory=list)
    prioridad: int = 1  # mayor = más urgente/valioso
    procedencia: list[str] = field(default_factory=list)  # de dónde salió (runs, radar, BOE…)
    id: str = field(default_factory=lambda: f"nec_{uuid4().hex[:10]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "tipo": self.tipo.value,
            "fuente": self.fuente.value,
            "descripcion": self.descripcion,
            "evidencia": list(self.evidencia),
            "prioridad": self.prioridad,
            "procedencia": list(self.procedencia),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Necesidad":
        return cls(
            titulo=str(d["titulo"]),
            tipo=TipoNecesidad(d.get("tipo", TipoNecesidad.TOOL)),
            fuente=Fuente(d.get("fuente", Fuente.PROCESO)),
            descripcion=str(d.get("descripcion", "")),
            evidencia=list(d.get("evidencia", [])),
            prioridad=int(d.get("prioridad", 1)),
            procedencia=list(d.get("procedencia", [])),
            id=str(d.get("id", f"nec_{uuid4().hex[:10]}")),
        )


@dataclass
class BorradorTool:
    """La tool redactada: su contrato (nombre/descr/JSON-schema) + el código + su eval propio."""

    nombre: str  # snake_case, identificador de la tool
    descripcion: str
    parametros: dict[str, Any]  # JSON Schema (type=object, properties, required)
    source: str  # código Python autocontenido de la función
    eval_source: str = ""  # opcional: código de un check determinista de la tool
    notas: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "parametros": self.parametros,
            "source": self.source,
            "eval_source": self.eval_source,
            "notas": self.notas,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BorradorTool":
        return cls(
            nombre=str(d["nombre"]),
            descripcion=str(d.get("descripcion", "")),
            parametros=dict(d.get("parametros", {})),
            source=str(d.get("source", "")),
            eval_source=str(d.get("eval_source", "")),
            notas=str(d.get("notas", "")),
        )


@dataclass
class Veredicto:
    """Resultado del arnés de validación: cada puerta con su (ok, detalle). `ok` = todas verdes."""

    puertas: dict[str, dict[str, Any]] = field(default_factory=dict)

    def añadir(self, nombre: str, ok: bool, detalle: str) -> None:
        self.puertas[nombre] = {"ok": ok, "detalle": detalle}

    @property
    def ok(self) -> bool:
        return bool(self.puertas) and all(p["ok"] for p in self.puertas.values())

    @property
    def fallos(self) -> list[str]:
        return [n for n, p in self.puertas.items() if not p["ok"]]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "puertas": self.puertas, "fallos": self.fallos}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Veredicto":
        v = cls()
        v.puertas = dict(d.get("puertas", {}))
        return v


@dataclass
class PropuestaSkill:
    """Lo que se le presenta a Fernando: la necesidad, el borrador, el veredicto y el estado.
    NUNCA se auto-aplica: `estado` solo pasa a APROBADA por acción humana explícita."""

    necesidad: Necesidad
    borrador: BorradorTool
    veredicto: Veredicto
    estado: EstadoPropuesta = EstadoPropuesta.PENDIENTE
    id: str = field(default_factory=lambda: f"prop_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=_ahora)
    updated_at: str = field(default_factory=_ahora)
    decision_humana: str = ""  # nota de Fernando al aprobar/descartar

    @property
    def fitness(self) -> int:
        """Score del intento (peldaño del linaje): nº de puertas verdes del arnés."""
        return sum(1 for p in self.veredicto.puertas.values() if p["ok"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "estado": self.estado.value,
            "fitness": self.fitness,
            "necesidad": self.necesidad.to_dict(),
            "borrador": self.borrador.to_dict(),
            "veredicto": self.veredicto.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision_humana": self.decision_humana,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PropuestaSkill":
        return cls(
            necesidad=Necesidad.from_dict(d["necesidad"]),
            borrador=BorradorTool.from_dict(d["borrador"]),
            veredicto=Veredicto.from_dict(d.get("veredicto", {})),
            estado=EstadoPropuesta(d.get("estado", EstadoPropuesta.PENDIENTE)),
            id=str(d.get("id", f"prop_{uuid4().hex[:10]}")),
            created_at=str(d.get("created_at", _ahora())),
            updated_at=str(d.get("updated_at", _ahora())),
            decision_humana=str(d.get("decision_humana", "")),
        )
