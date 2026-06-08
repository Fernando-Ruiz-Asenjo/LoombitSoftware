"""
AgentMemory — memoria operativa persistente entre sesiones.

Como una secretaria real: recuerda con quién trabaja Fernando, qué hace
habitualmente, qué contactos tiene, cómo resolvió tareas similares antes,
y qué carencias ha detectado el propio agente en su funcionamiento.

Fichero: runtime/local/agent_memory.json

Secciones:
  owner       → datos del propietario (nombre, email, empresa, idioma)
  contacts    → directorio de personas conocidas — SIN LÍMITE
  preferences → cómo prefiere Fernando que se hagan las cosas
  tasks       → tareas recurrentes habituales
  procedures  → cómo resolver cada tipo de tarea (aprendido de runs exitosos)
  proposals   → carencias detectadas por el propio agente, con sugerencias
  history     → todas las ejecuciones completadas — SIN LÍMITE
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)

_DEFAULT_MEMORY: dict[str, Any] = {
    "version": 3,
    "owner": {
        "name": "Fernando",
        "email": "fernando.ruizasenjo@gmail.com",
        "company": "LoomBit Software Inc.",
        "language": "es",
        "timezone": "Europe/Madrid",
    },
    "contacts": [],  # ContactEntry[] — sin límite, deduplicado por email
    "preferences": {
        "email_tone": "profesional",
        "calendar_default_duration_min": 60,
        "always_cc": [],
        "notes": "",
    },
    "tasks": [],  # tareas recurrentes conocidas (strings)
    "procedures": {},  # {tipo_tarea: ProcedureEntry} — cómo hacerlo
    "proposals": [],  # ProposalEntry[] — carencias del agente
    "history": [],  # HistoryEntry[] — SIN LÍMITE
    "entities": {},  # {clave: EntityProfile} — memoria semántica por empresa
    "lessons": [],  # LessonEntry[] — aprendizaje GENERAL (Reflexion), agnóstico al dominio
}

# Lecciones fundacionales: el conocimiento destilado del análisis de error (F1-F8). Hacen que la
# memoria NO nazca vacía/tonta — es la aplicación retroactiva del aprendizaje (sin deuda).
_FOUNDATIONAL_LESSONS: list[dict[str, Any]] = [
    {
        "text": "Al enviar un correo, NUNCA inventes el email del destinatario: resuélvelo con "
        "contacts_find o pregunta al usuario. Mejor preguntar que acertar por suerte.",
        "tags": ["correo", "email", "destinatario", "contacto", "enviar", "jana"],
        "outcome": "fallo",
        "source": "analisis_error_F2",
    },
    {
        "text": "Para resolver el destinatario cuando hay varias direcciones para el mismo nombre, "
        "elige la que MÁS has usado en Enviados (frecuencia real). Si una destaca, úsala sin preguntar. "
        "Vale para CUALQUIER contacto, no solo Jana.",
        "tags": [
            "correo",
            "email",
            "destinatario",
            "contacto",
            "frecuencia",
            "enviados",
            "resolver",
        ],
        "outcome": "exito",
        "source": "metodo_resolucion_por_frecuencia",
    },
    {
        "text": "En un correo escribes COMO el usuario: no te presentes como IA, agente, bot ni "
        "'Loombit', ni digas que es automático. Fírmalo con el nombre del usuario.",
        "tags": ["correo", "email", "redactar", "presentar", "firma"],
        "outcome": "fallo",
        "source": "analisis_error_F4",
    },
    {
        "text": "El asunto y el cuerpo del correo los deduces TÚ del encargo; nunca se los preguntes al usuario.",
        "tags": ["correo", "email", "asunto", "cuerpo"],
        "outcome": "fallo",
        "source": "analisis_error_F1",
    },
    {
        "text": "No inventes datos del usuario (cargo, méritos, motivos) que no te haya dado: usa solo lo que sabes.",
        "tags": ["correo", "datos", "usuario", "presentar"],
        "outcome": "fallo",
        "source": "analisis_error_F4",
    },
    {
        "text": "Si una acción falla o no avanza, CAMBIA de estrategia; no repitas la misma llamada "
        "esperando otro resultado. Si la capacidad no existe, dilo honestamente y termina.",
        "tags": ["general", "bucle", "fallo", "estrategia"],
        "outcome": "fallo",
        "source": "analisis_error_F6",
    },
]


# ── Tipos de datos ────────────────────────────────────────────────────────────


class ContactEntry:
    """Contacto conocido por el agente."""

    def __init__(
        self,
        name: str,
        email: str,
        company: str = "",
        role: str = "",
        notes: str = "",
        last_contact: str = "",
        times_contacted: int = 0,
        source: str = "manual",
    ) -> None:
        self.name = name
        self.email = email
        self.company = company
        self.role = role
        self.notes = notes
        self.last_contact = last_contact or datetime.now(UTC).isoformat()
        self.times_contacted = times_contacted
        # Procedencia (F5 — no cristalizar datos falsos): "manual"/"google" = verdad confirmada;
        # "auto" = capturado de un envío pasado, NO se trata como fuente fiable de resolución.
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "company": self.company,
            "role": self.role,
            "notes": self.notes,
            "last_contact": self.last_contact,
            "times_contacted": self.times_contacted,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContactEntry":
        return cls(
            name=str(d.get("name", "")),
            email=str(d.get("email", "")),
            company=str(d.get("company", "")),
            role=str(d.get("role", "")),
            notes=str(d.get("notes", "")),
            last_contact=str(d.get("last_contact", "")),
            times_contacted=int(d.get("times_contacted", 0)),
            source=str(d.get("source", "manual")),
        )

    def __str__(self) -> str:
        parts = [f"{self.name} <{self.email}>"]
        if self.company:
            parts.append(self.company)
        if self.role:
            parts.append(f"({self.role})")
        if self.notes:
            parts.append(f"— {self.notes}")
        return " | ".join(parts)


class HistoryEntry:
    """Resumen de una ejecución completada."""

    def __init__(
        self,
        task: str,
        result: str,
        tools_used: list[str] | None = None,
        date: str = "",
        run_id: str = "",
    ) -> None:
        self.task = task[:300]
        self.result = result[:400]
        self.tools_used = tools_used or []
        self.date = date or datetime.now(UTC).strftime("%Y-%m-%d")
        self.run_id = run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "result": self.result,
            "tools_used": self.tools_used,
            "date": self.date,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HistoryEntry":
        return cls(
            task=str(d.get("task", "")),
            result=str(d.get("result", "")),
            tools_used=list(d.get("tools_used", [])),
            date=str(d.get("date", "")),
            run_id=str(d.get("run_id", "")),
        )

    def __str__(self) -> str:
        tools = f" [{', '.join(self.tools_used[:3])}]" if self.tools_used else ""
        return f"[{self.date}]{tools} {self.task[:80]} → {self.result[:80]}"


class ProcedureEntry:
    """Cómo hacer un tipo de tarea — aprendido de runs exitosos."""

    def __init__(
        self,
        task_type: str,
        steps: list[str],
        tools: list[str],
        notes: str = "",
        success_count: int = 1,
        last_used: str = "",
    ) -> None:
        self.task_type = task_type
        self.steps = steps  # pasos en lenguaje natural
        self.tools = tools  # tools que se usaron
        self.notes = notes
        self.success_count = success_count
        self.last_used = last_used or datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "steps": self.steps,
            "tools": self.tools,
            "notes": self.notes,
            "success_count": self.success_count,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProcedureEntry":
        return cls(
            task_type=str(d.get("task_type", "")),
            steps=list(d.get("steps", [])),
            tools=list(d.get("tools", [])),
            notes=str(d.get("notes", "")),
            success_count=int(d.get("success_count", 1)),
            last_used=str(d.get("last_used", "")),
        )

    def __str__(self) -> str:
        return f"{self.task_type} (×{self.success_count}):\n" + "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(self.steps[:6])
        )


class ProposalEntry:
    """Carencia o mejora detectada por el propio agente."""

    def __init__(
        self,
        issue: str,
        suggestion: str,
        category: str = "general",
        date: str = "",
        run_id: str = "",
    ) -> None:
        self.issue = issue[:300]
        self.suggestion = suggestion[:400]
        self.category = category  # tool_missing | behavior | memory | ui | integration
        self.date = date or datetime.now(UTC).strftime("%Y-%m-%d")
        self.run_id = run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue,
            "suggestion": self.suggestion,
            "category": self.category,
            "date": self.date,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProposalEntry":
        return cls(
            issue=str(d.get("issue", "")),
            suggestion=str(d.get("suggestion", "")),
            category=str(d.get("category", "general")),
            date=str(d.get("date", "")),
            run_id=str(d.get("run_id", "")),
        )

    def __str__(self) -> str:
        return f"[{self.category}] {self.issue} → {self.suggestion}"


class LessonEntry:
    """Una lección GENERAL aprendida (Reflexion). Agnóstica al dominio: vale para correos,
    facturas o lo que sea. Se recupera por relevancia a la tarea (no se vuelca todo: aviso de ExpeL).
    """

    def __init__(
        self,
        text: str,
        tags: list[str] | None = None,
        outcome: str = "",
        source: str = "reflexion",
        created: str = "",
        times_used: int = 0,
    ) -> None:
        self.text = text.strip()
        self.tags = [t.lower() for t in (tags or [])]
        self.outcome = outcome  # "exito" | "fallo" | "correccion_humana" | ""
        self.source = source
        self.created = created or datetime.now(UTC).strftime("%Y-%m-%d")
        self.times_used = times_used

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tags": self.tags,
            "outcome": self.outcome,
            "source": self.source,
            "created": self.created,
            "times_used": self.times_used,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LessonEntry":
        return cls(
            text=str(d.get("text", "")),
            tags=list(d.get("tags", [])),
            outcome=str(d.get("outcome", "")),
            source=str(d.get("source", "reflexion")),
            created=str(d.get("created", "")),
            times_used=int(d.get("times_used", 0)),
        )

    def tokens(self) -> set[str]:
        words = (self.text + " " + " ".join(self.tags)).lower()
        return {w for w in re.findall(r"[a-záéíóúñ0-9]+", words) if len(w) >= 4}


def _norm_iban(iban: str) -> str:
    """Normaliza un IBAN: sin espacios, en mayúsculas."""
    return "".join(iban.split()).upper()


class EntityProfile:
    """
    Memoria SEMÁNTICA por empresa (cliente/proveedor) — el "diferencial real".

    No es una lista de hechos sueltos: es lo que sabe un administrativo con oficio
    sobre cada empresa con la que trata: cómo paga, qué IBANs son suyos, qué
    incidencias ha habido, quién es el contacto. Alimenta el seguimiento de cobros
    y el gate antifraude (un IBAN nuevo en un proveedor conocido = alerta).
    """

    def __init__(
        self,
        name: str,
        nif: str = "",
        ibans: list[str] | None = None,
        contacts: list[str] | None = None,
        payments: list[int] | None = None,
        incidents: list[dict[str, str]] | None = None,
        notes: str = "",
        first_seen: str = "",
        last_seen: str = "",
        times_seen: int = 0,
    ) -> None:
        self.name = name
        self.nif = nif.upper().strip()
        self.ibans = [_norm_iban(i) for i in (ibans or []) if i.strip()]
        self.contacts = contacts or []
        self.payments = payments or []  # días de demora por pago (negativo = adelantado)
        self.incidents = incidents or []  # [{date, note}]
        self.notes = notes
        self.first_seen = first_seen or datetime.now(UTC).strftime("%Y-%m-%d")
        self.last_seen = last_seen or datetime.now(UTC).strftime("%Y-%m-%d")
        self.times_seen = times_seen

    @property
    def avg_days_late(self) -> float:
        return round(sum(self.payments) / len(self.payments), 1) if self.payments else 0.0

    @property
    def late_count(self) -> int:
        return sum(1 for d in self.payments if d > 0)

    @property
    def pays_late(self) -> bool:
        """Paga tarde de forma habitual (media > 5 días y mayoría de pagos tardíos)."""
        return (
            bool(self.payments)
            and self.avg_days_late > 5
            and self.late_count * 2 >= len(self.payments)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nif": self.nif,
            "ibans": self.ibans,
            "contacts": self.contacts,
            "payments": self.payments,
            "incidents": self.incidents,
            "notes": self.notes,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "times_seen": self.times_seen,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EntityProfile":
        return cls(
            name=str(d.get("name", "")),
            nif=str(d.get("nif", "")),
            ibans=list(d.get("ibans", [])),
            contacts=list(d.get("contacts", [])),
            payments=[int(x) for x in d.get("payments", [])],
            incidents=list(d.get("incidents", [])),
            notes=str(d.get("notes", "")),
            first_seen=str(d.get("first_seen", "")),
            last_seen=str(d.get("last_seen", "")),
            times_seen=int(d.get("times_seen", 0)),
        )

    def __str__(self) -> str:
        bits = [self.name]
        if self.nif:
            bits.append(f"NIF {self.nif}")
        if self.payments:
            tag = "paga tarde" if self.pays_late else "paga a tiempo"
            bits.append(f"{tag} (media {self.avg_days_late:+g}d)")
        if self.ibans:
            bits.append(f"{len(self.ibans)} IBAN(s) conocidos")
        if self.incidents:
            bits.append(f"{len(self.incidents)} incidencia(s)")
        return " | ".join(bits)


# ── AgentMemory ───────────────────────────────────────────────────────────────


class AgentMemory:
    """
    Memoria operativa del agente — persistente entre sesiones, sin límite.

    Uso:
        mem = AgentMemory()
        block = mem.to_context_block()         # inyectar en system prompt
        mem.add_contact("Jana Wall", "jana@acme.com", company="Acme")
        mem.add_history("Enviar informe a Jana", "✅ OK", run_id="abc")
        mem.add_procedure("enviar_correo", steps=[...], tools=["contacts_find","gmail_send"])
        mem.add_proposal("No sé buscar adjuntos", "Añadir tool file_attach", "tool_missing")
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or Path("runtime/local/agent_memory.json")
        self._data: dict[str, Any] = {}
        self._load()
        self._ensure_foundational_lessons()  # aplica retroactivamente el aprendizaje (F1-F8)

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def owner(self) -> dict[str, str]:
        return self._data.get("owner", {})

    @property
    def contacts(self) -> list[ContactEntry]:
        return [ContactEntry.from_dict(c) for c in self._data.get("contacts", [])]

    @property
    def preferences(self) -> dict[str, Any]:
        return self._data.get("preferences", {})

    @property
    def tasks(self) -> list[str]:
        return list(self._data.get("tasks", []))

    @property
    def history(self) -> list[HistoryEntry]:
        return [HistoryEntry.from_dict(h) for h in self._data.get("history", [])]

    @property
    def procedures(self) -> dict[str, ProcedureEntry]:
        return {k: ProcedureEntry.from_dict(v) for k, v in self._data.get("procedures", {}).items()}

    @property
    def proposals(self) -> list[ProposalEntry]:
        return [ProposalEntry.from_dict(p) for p in self._data.get("proposals", [])]

    # ── Mutadores — contactos ─────────────────────────────────────────────────

    def add_contact(
        self,
        name: str,
        email: str,
        company: str = "",
        role: str = "",
        notes: str = "",
        source: str = "manual",
    ) -> None:
        """Añade o actualiza un contacto. Deduplicado por email. Sin límite.

        `source` registra la procedencia (F5): "manual"/"google" = confirmado; "auto" = capturado
        de un envío. Un contacto NUNCA se degrada de confirmado a auto al re-verse."""
        contacts = self._data.setdefault("contacts", [])
        email_lower = email.lower().strip()
        for c in contacts:
            if c.get("email", "").lower() == email_lower:
                c["name"] = name or c.get("name", "")
                c["company"] = company or c.get("company", "")
                c["role"] = role or c.get("role", "")
                c["notes"] = notes or c.get("notes", "")
                c["last_contact"] = datetime.now(UTC).isoformat()
                c["times_contacted"] = c.get("times_contacted", 0) + 1
                if source != "auto":  # no degradar verdad confirmada
                    c["source"] = source
                self._save()
                return
        contacts.append(ContactEntry(name, email, company, role, notes, source=source).to_dict())
        self._save()

    def find_contact(self, query: str) -> list[ContactEntry]:
        """Busca contactos por nombre, email o empresa (case-insensitive)."""
        q = query.lower()
        return [
            c
            for c in self.contacts
            if q in c.name.lower() or q in c.email.lower() or q in c.company.lower()
        ]

    # ── Mutadores — historial (sin límite) ────────────────────────────────────

    def add_history(
        self,
        task: str,
        result: str,
        tools_used: list[str] | None = None,
        run_id: str = "",
    ) -> None:
        """Registra una ejecución. SIN LÍMITE — crece indefinidamente."""
        history = self._data.setdefault("history", [])
        history.insert(0, HistoryEntry(task, result, tools_used, run_id=run_id).to_dict())
        self._save()

    # ── Mutadores — procedimientos ────────────────────────────────────────────

    def add_procedure(
        self,
        task_type: str,
        steps: list[str],
        tools: list[str],
        notes: str = "",
    ) -> None:
        """
        Guarda o actualiza cómo hacer un tipo de tarea.
        Si ya existe, incrementa el contador de éxitos y actualiza los pasos.
        """
        procs = self._data.setdefault("procedures", {})
        key = task_type.lower().replace(" ", "_")
        if key in procs:
            procs[key]["success_count"] = procs[key].get("success_count", 1) + 1
            procs[key]["steps"] = steps  # actualizar con la versión más reciente
            procs[key]["tools"] = tools
            procs[key]["notes"] = notes or procs[key].get("notes", "")
            procs[key]["last_used"] = datetime.now(UTC).isoformat()
        else:
            procs[key] = ProcedureEntry(task_type, steps, tools, notes).to_dict()
        self._save()

    def find_procedure(self, task_description: str) -> ProcedureEntry | None:
        """Busca el procedimiento mas relevante para una descripcion de tarea."""
        desc_lower = task_description.lower()
        best: tuple[int, ProcedureEntry | None] = (0, None)
        for key, proc in self.procedures.items():
            words = set(key.replace("_", " ").split())
            task_words = set(desc_lower.split())
            score = len(words & task_words)
            if score > best[0]:
                best = (score, proc)
        return best[1]

    # ── Mutadores propuestas del agente ───────────────────────────────────────

    def add_proposal(
        self,
        issue: str,
        suggestion: str,
        category: str = "general",
        run_id: str = "",
    ) -> None:
        """El agente registra una carencia o mejora detectada."""
        proposals = self._data.setdefault("proposals", [])
        proposals.insert(0, ProposalEntry(issue, suggestion, category, run_id=run_id).to_dict())
        self._save()

    def set_preference(self, key: str, value: Any) -> None:
        self._data.setdefault("preferences", {})[key] = value
        self._save()

    def add_recurring_task(self, description: str) -> None:
        tasks = self._data.setdefault("tasks", [])
        if description not in tasks:
            tasks.append(description)
            self._save()

    # ── Mutadores — entidades (memoria de empresa) ────────────────────────────

    @property
    def entities(self) -> dict[str, EntityProfile]:
        return {k: EntityProfile.from_dict(v) for k, v in self._data.get("entities", {}).items()}

    @staticmethod
    def _entity_key(name: str, nif: str = "") -> str:
        if nif.strip():
            return "nif:" + "".join(nif.split()).upper()
        return "name:" + name.lower().strip()

    def _load_entity(self, name: str, nif: str = "") -> tuple[str, EntityProfile]:
        entities = self._data.setdefault("entities", {})
        key = self._entity_key(name, nif)
        if key in entities:
            return key, EntityProfile.from_dict(entities[key])
        # Si buscamos por nombre, reutiliza una entidad ya existente con ese nombre.
        if not nif.strip() and name:
            for k, raw in entities.items():
                if str(raw.get("name", "")).lower().strip() == name.lower().strip():
                    return k, EntityProfile.from_dict(raw)
        return key, EntityProfile(name=name, nif=nif)

    def _save_entity(self, key: str, prof: EntityProfile) -> EntityProfile:
        prof.last_seen = datetime.now(UTC).strftime("%Y-%m-%d")
        prof.times_seen += 1
        self._data.setdefault("entities", {})[key] = prof.to_dict()
        self._save()
        return prof

    def upsert_entity(
        self, name: str, nif: str = "", iban: str = "", contact: str = ""
    ) -> EntityProfile:
        """Crea o actualiza el perfil de una empresa (cliente/proveedor)."""
        key, prof = self._load_entity(name, nif)
        if name and not prof.name:
            prof.name = name
        if nif and not prof.nif:
            prof.nif = nif.upper().strip()
        if iban:
            ni = _norm_iban(iban)
            if ni and ni not in prof.ibans:
                prof.ibans.append(ni)
        if contact and contact not in prof.contacts:
            prof.contacts.append(contact)
        return self._save_entity(key, prof)

    def record_payment(self, name: str, days_late: int, nif: str = "") -> EntityProfile:
        """Registra un pago: días de demora (negativo = adelantado/a tiempo)."""
        key, prof = self._load_entity(name, nif)
        prof.payments.append(int(days_late))
        return self._save_entity(key, prof)

    def add_entity_incident(self, name: str, note: str, nif: str = "") -> EntityProfile:
        key, prof = self._load_entity(name, nif)
        prof.incidents.append({"date": datetime.now(UTC).strftime("%Y-%m-%d"), "note": note[:300]})
        return self._save_entity(key, prof)

    def is_known_iban(self, name: str, iban: str, nif: str = "") -> bool:
        _, prof = self._load_entity(name, nif)
        return _norm_iban(iban) in prof.ibans

    def iban_alert(self, name: str, iban: str, nif: str = "") -> dict[str, Any]:
        """
        Gate antifraude (supuestos S-05/S-15): marca si el IBAN es NUEVO para una
        empresa que YA tiene IBANs conocidos → el operador debe bloquear el pago y
        verificar por un canal alternativo antes de continuar.
        """
        _, prof = self._load_entity(name, nif)
        ni = _norm_iban(iban)
        return {
            "entity": prof.name or name,
            "iban": ni,
            "known_ibans": prof.ibans,
            "is_known": ni in prof.ibans,
            "is_new_for_known_entity": bool(prof.ibans) and ni not in prof.ibans,
        }

    def find_entity(self, query: str) -> list[EntityProfile]:
        q = query.lower()
        return [
            prof
            for prof in self.entities.values()
            if q in prof.name.lower()
            or q in prof.nif.lower()
            or any(q in c.lower() for c in prof.contacts)
        ]

    # ── Lecciones (aprendizaje general — Reflexion) ───────────────────────────

    @property
    def lessons(self) -> list[LessonEntry]:
        return [LessonEntry.from_dict(x) for x in self._data.get("lessons", [])]

    def add_lesson(
        self, text: str, tags: list[str] | None = None, outcome: str = "", source: str = "reflexion"
    ) -> None:
        """Guarda una lección general. Deduplicada por texto (refuerza la existente)."""
        text = (text or "").strip()
        if len(text) < 8:
            return
        lessons = self._data.setdefault("lessons", [])
        for x in lessons:
            if x.get("text", "").strip().lower() == text.lower():
                x["times_used"] = x.get("times_used", 0) + 1
                if tags:
                    x["tags"] = sorted({*x.get("tags", []), *[t.lower() for t in tags]})
                self._save()
                return
        lessons.append(LessonEntry(text, tags, outcome, source).to_dict())
        self._save()

    def relevant_lessons(self, task: str, k: int = 4) -> list[LessonEntry]:
        """Recupera las lecciones MÁS RELEVANTES a la tarea (no todas — aviso de ExpeL)."""
        task_tokens = {w for w in re.findall(r"[a-záéíóúñ0-9]+", task.lower()) if len(w) >= 4}
        if not task_tokens:
            return []
        puntuadas = [(len(le.tokens() & task_tokens), le) for le in self.lessons]
        puntuadas = [(s, le) for s, le in puntuadas if s > 0]
        puntuadas.sort(key=lambda p: (p[0], p[1].times_used), reverse=True)
        return [le for _, le in puntuadas[:k]]

    def _ensure_foundational_lessons(self) -> None:
        """Aplica retroactivamente el conocimiento del análisis de error (sin deuda)."""
        existentes = {x.get("text", "").strip().lower() for x in self._data.get("lessons", [])}
        faltan = [
            le for le in _FOUNDATIONAL_LESSONS if le["text"].strip().lower() not in existentes
        ]
        if faltan:
            self._data.setdefault("lessons", []).extend(
                LessonEntry(**le).to_dict() for le in faltan
            )
            self._save()

    def to_context_block(self, task_hint: str = "") -> str:
        """Genera el bloque de contexto para el system prompt."""
        lines: list[str] = []
        o = self.owner
        if o.get("name"):
            lines.append(
                "Trabajas para: "
                + o["name"]
                + " ("
                + o.get("email", "")
                + ")"
                + " — "
                + o.get("company", "")
                + "."
                + " Idioma: "
                + o.get("language", "es")
                + "."
                + " TZ: "
                + o.get("timezone", "Europe/Madrid")
                + "."
            )
        prefs = self.preferences
        if prefs.get("email_tone"):
            lines.append("Tono de correo: " + prefs["email_tone"] + ".")
        if prefs.get("always_cc"):
            lines.append("CC siempre a: " + ", ".join(prefs["always_cc"]) + ".")
        if prefs.get("notes"):
            lines.append("Nota: " + prefs["notes"])
        contacts = sorted(self.contacts, key=lambda c: c.times_contacted, reverse=True)
        if contacts:
            lines.append("Contactos:\n" + "\n".join("  • " + str(c) for c in contacts[:30]))
        if self.tasks:
            lines.append("Tareas habituales: " + "; ".join(self.tasks[:10]))
        if task_hint:
            proc = self.find_procedure(task_hint)
            if proc:
                lines.append("Procedimiento conocido para tarea similar:\n" + str(proc))
        entities = sorted(self.entities.values(), key=lambda e: e.times_seen, reverse=True)
        notable = [e for e in entities if e.pays_late or e.incidents][:10]
        if notable:
            lines.append("Empresas a vigilar:\n" + "\n".join("  • " + str(e) for e in notable))
        recent = self.history[:8]
        if recent:
            lines.append("Historial reciente:\n" + "\n".join("  • " + str(h) for h in recent))
        if task_hint:
            relevantes = self.relevant_lessons(task_hint)
            if relevantes:
                lines.append(
                    "LECCIONES APRENDIDAS (aplícalas):\n"
                    + "\n".join("  • " + le.text for le in relevantes)
                )
        if not lines:
            return ""
        return "\n\nMEMORIA OPERATIVA:\n" + "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        """Vista completa para el endpoint /agent/memory."""
        return {
            "store_path": str(self.store_path),
            "owner": self.owner,
            "contacts_count": len(self._data.get("contacts", [])),
            "contacts": [c.to_dict() for c in self.contacts],
            "preferences": self.preferences,
            "tasks": self.tasks,
            "procedures_count": len(self._data.get("procedures", {})),
            "procedures": {k: v.to_dict() for k, v in self.procedures.items()},
            "proposals_count": len(self._data.get("proposals", [])),
            "proposals": [p.to_dict() for p in self.proposals],
            "history_count": len(self._data.get("history", [])),
            "history_recent": [h.to_dict() for h in self.history[:20]],
            "entities_count": len(self._data.get("entities", {})),
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "lessons_count": len(self._data.get("lessons", [])),
            "lessons": [le.to_dict() for le in self.lessons],
        }

    def extract_contacts_from_steps(self, steps: list[Any]) -> int:
        """Extrae y guarda contactos detectados en los steps de un run."""
        added = 0
        for step in steps:
            tool_name = getattr(step, "tool_name", "")
            args = getattr(step, "arguments", {})
            if tool_name == "gmail_send" and args.get("to"):
                email = args["to"].strip()
                if "@" in email:
                    raw = args.get("to", "")
                    name = raw.split("<")[0].strip() if "<" in raw else email.split("@")[0]
                    # Capturado de un envío → procedencia "auto" (no es verdad confirmada): así no
                    # se cristaliza como contacto fiable (raíz del bug de `jana.espinal`).
                    self.add_contact(name=name, email=email, source="auto")
                    added += 1
            # NO se cachean los resultados de contacts_find en memoria: contacts_find ya mezcla
            # memoria + Google, así que re-ingerirlos "lavaría" un contacto dudoso a source="google"
            # y se reforzaría solo (el bucle que resucitaba `jana.espinal`). Google se consulta en vivo.
        return added

    def remove_contact(self, email: str) -> bool:
        """Elimina un contacto por email (p.ej. uno fabricado/erróneo). True si existía."""
        email_l = email.lower().strip()
        contacts = self._data.get("contacts", [])
        nuevos = [c for c in contacts if c.get("email", "").lower() != email_l]
        if len(nuevos) != len(contacts):
            self._data["contacts"] = nuevos
            self._save()
            return True
        return False

    def extract_procedure_from_run(self, run: Any) -> bool:
        """Guarda el procedimiento aprendido de un run exitoso."""
        try:
            if not run.steps or not run.result:
                return False
            tools_used = [s.tool_name for s in run.steps]
            if not tools_used:
                return False
            task_type = _classify_task_type(run.task, tools_used)
            if not task_type:
                return False
            # Un procedimiento es la SECUENCIA DE TOOLS (el "cómo"), NUNCA los argumentos literales:
            # guardar args memorizaría datos de un solo uso (un destinatario, un asunto) y los
            # reinyectaría como si fueran la receta — así se coló 'jana.espinal@…' como procedimiento.
            steps_desc = list(dict.fromkeys(tools_used))
            self.add_procedure(
                task_type=task_type,
                steps=steps_desc,
                tools=list(dict.fromkeys(tools_used)),
            )
            return True
        except Exception:
            return False

    def _load(self) -> None:
        if not self.store_path.exists():
            self._data = _deep_copy_default()
            return
        try:
            text = self.store_path.read_text(encoding="utf-8")
            loaded = json.loads(text) if text.strip() else _deep_copy_default()
            for key, default_val in _DEFAULT_MEMORY.items():
                if key not in loaded:
                    loaded[key] = default_val
            self._data = loaded
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo cargar agent_memory.json: %s", exc)
            self._data = _deep_copy_default()

    def _save(self) -> None:
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store_path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self.store_path)
        except OSError as exc:
            logger.error("No se pudo guardar agent_memory.json: %s", exc)

    save = _save


# ── Helpers internos ──────────────────────────────────────────────────────────


def _deep_copy_default() -> dict[str, Any]:
    import copy

    return copy.deepcopy(_DEFAULT_MEMORY)


_TASK_PATTERNS: list[tuple[list[str], str]] = [
    (["gmail_send"], "enviar_correo"),
    (["calendar_create"], "crear_evento_calendario"),
    (["contacts_find", "gmail_send"], "buscar_contacto_y_enviar_correo"),
    (["gmail_search"], "buscar_correos"),
    (["task_done"], "completar_tarea_simple"),
]


def _classify_task_type(task: str, tools: list[str]) -> str:
    tool_set = set(tools)
    for pattern_tools, label in _TASK_PATTERNS:
        if all(t in tool_set for t in pattern_tools):
            return label
    significant = [t for t in tools if t not in ("task_done", "ask_user")]
    return significant[0] if significant else ""


# ── Singleton global ──────────────────────────────────────────────────────────

_memory: AgentMemory | None = None


def get_memory(store_path: Path | None = None) -> AgentMemory:
    """Devuelve la instancia singleton de AgentMemory."""
    global _memory
    if _memory is None:
        _memory = AgentMemory(store_path)
    return _memory
