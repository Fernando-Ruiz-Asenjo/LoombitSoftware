"""
alias_resolver.py — Skill W Administration Core: resolver de alias de contraparte que aprende.

El "flywheel" de la conciliación bancaria, en su versión determinista y local. Un pagador
puede aparecer en el extracto con un nombre que NO coincide léxicamente con el de su factura
("TRANSFERENCIA DE J. LOPEZ" ↔ factura de "INMOBILIARIA COSTA SL"). Un humano resuelve ese
puente una vez; el sistema **no debería volver a preguntarlo**.

`AliasStore` aprende esos puentes **solo de los cobros que el humano confirma** (nunca de los
que el modelo adivina), con **procedencia** (quién y cuándo) y **revocación**. Es una tabla
determinista: el LLM no interviene, no hay fine-tuning. Aislada **por entidad** (un fichero por
tenant, como los Expedientes) → los alias de un cliente de la gestoría no contaminan a otro.

Salvaguardas frente a un alias mal aprendido (el riesgo natural del que aprende):
- Solo aprende de confirmaciones humanas (no de propuestas del propio matcher).
- El resolver solo puede **subir a MEDIA** un match; ALTA sigue exigiendo importe+referencia
  reales, y **ningún match marca cobro sin aprobación humana**. Un alias erróneo, en el peor
  caso, propone una MEDIA que el humano rechaza.
- Se puede **revocar** y queda **auditado** (procedencia append-only).

Implementa el protocolo `AliasResolver` de `conciliacion.py` (`canonico`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .conciliacion import tokens_contraparte
from .config import AppSettings, get_settings

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clave_tokens(concepto: str) -> list[str]:
    """Tokens de NOMBRE del concepto (excluye cualquier token con dígitos: son referencias —
    nº de factura, recibo— no el nombre estable del pagador). Vacío → nada nombrable que
    aprender, así el alias no se ata a una referencia de un solo uso."""
    return sorted({t for t in tokens_contraparte(concepto) if not any(ch.isdigit() for ch in t)})


@dataclass
class Alias:
    id: str
    clave_tokens: list[str]  # tokens de nombre del concepto bancario (la "llave")
    canonico: str  # nombre de contraparte al que apunta
    confirmaciones: int = 1
    revocado: bool = False
    creado: str = field(default_factory=_now)
    ultima_confirmacion: str = field(default_factory=_now)
    procedencia: list[dict] = field(default_factory=list)  # append-only: [{actor, ts, ...}]


class AliasStore:
    """Tabla de alias de contraparte de UNA entidad (aislamiento físico, como Expedientes).

    Persistencia: `runtime/local/entities/<entity_id>/aliases.json`. Implementa el protocolo
    `AliasResolver` (`canonico`) para inyectarse en el matcher de `conciliacion.py`.
    """

    def __init__(
        self,
        entity_id: str,
        base_dir: Path | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        if not entity_id or "/" in entity_id or "\\" in entity_id or entity_id in {".", ".."}:
            raise ValueError(f"entity_id inválido: {entity_id!r}")
        active = settings or get_settings()
        self.entity_id = entity_id
        root = base_dir or active.entities_dir
        self.path = Path(root) / entity_id / "aliases.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._aliases: list[Alias] = self._load()

    def _load(self) -> list[Alias]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
            return [Alias(**a) for a in raw]
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.warning("No se pudo cargar aliases.json (%s): %s", self.path, exc)
            return []

    def _save(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps([asdict(a) for a in self._aliases], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def aprender(
        self, concepto: str, contraparte: str, *, referencia: str = "", actor: str = "human"
    ) -> Alias | None:
        """Aprende (o refuerza) el puente concepto-bancario → contraparte de un cobro confirmado.

        Devuelve el `Alias` aprendido/reforzado, o `None` si el concepto no tiene tokens de
        nombre (nada estable que aprender) o falta la contraparte → no inventa.
        """
        clave = _clave_tokens(concepto)
        canon = contraparte.strip()
        if not clave or not canon:
            return None
        proc = {"actor": actor, "ts": _now(), "referencia": referencia, "accion": "aprendido"}
        for a in self._aliases:
            if a.clave_tokens == clave and a.canonico.lower() == canon.lower() and not a.revocado:
                a.confirmaciones += 1
                a.ultima_confirmacion = _now()
                a.procedencia.append(proc)
                self._save()
                return a
        alias = Alias(id=str(uuid4()), clave_tokens=clave, canonico=canon, procedencia=[proc])
        self._aliases.append(alias)
        self._save()
        return alias

    def revocar(self, alias_id: str, actor: str = "human") -> bool:
        """Revoca un alias (no lo borra: queda auditado). True si lo encontró activo."""
        for a in self._aliases:
            if a.id == alias_id and not a.revocado:
                a.revocado = True
                a.procedencia.append({"actor": actor, "ts": _now(), "accion": "revocado"})
                self._save()
                return True
        return False

    def aliases(self, incluir_revocados: bool = False) -> list[Alias]:
        return [a for a in self._aliases if incluir_revocados or not a.revocado]

    def canonico(self, texto: str) -> str | None:
        """Protocolo `AliasResolver`: nombre canónico de contraparte para un concepto, o None.

        Casa el alias **más específico** (más tokens de nombre) cuya llave esté contenida en el
        concepto; a igualdad, el más confirmado. Determinista, sin LLM."""
        texto_tokens = set(tokens_contraparte(texto))
        if not texto_tokens:
            return None
        candidatos = [
            a for a in self.aliases() if a.clave_tokens and set(a.clave_tokens) <= texto_tokens
        ]
        if not candidatos:
            return None
        candidatos.sort(key=lambda a: (len(a.clave_tokens), a.confirmaciones), reverse=True)
        return candidatos[0].canonico
