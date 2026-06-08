"""
credentials.py — Skill W Administration Core: bóveda local de credenciales (gestor de contraseñas).

Fricción 0: el usuario da una credencial UNA vez; Loombit la guarda CIFRADA en reposo (Fernet con la
clave en el almacén del SO — DPAPI en Windows / Keychain en macOS, la misma que protege el token
OAuth) y la reutiliza para autocompletar logins vía Pilot, sin volver a pedirla. Local-first: nunca
sale de la máquina, nunca en texto plano en disco ni en logs.

Límite honesto: una bóveda es un objetivo de valor; el cifrado en reposo ayuda, pero si la máquina
está comprometida, está en riesgo (igual que cualquier gestor de contraseñas). El usuario puede
listar (sin ver el secreto), revocar y borrar. El secreto solo se descifra en el momento de usarlo.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ENC_PREFIX = "enc::"
_USAR_DEFECTO = object()  # sentinela: distingue "sin cifrador" (None) de "usa el por defecto"


def _default_cipher() -> Any:
    """Reutiliza el cifrador del store OAuth (clave en el almacén del SO)."""
    from .skill_blanca_oauth import _resolve_cipher

    return _resolve_cipher()


class CredentialVault:
    """Bóveda cifrada de credenciales por servicio. El secreto NUNCA se persiste en texto plano."""

    def __init__(self, path: Path | None = None, cipher: Any = _USAR_DEFECTO) -> None:
        self.path = Path(path) if path else Path("runtime/local/credentials.json")
        self._cipher = _default_cipher() if cipher is _USAR_DEFECTO else cipher
        self._data: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def set(self, service: str, username: str, secret: str, notes: str = "") -> None:
        """Guarda/actualiza una credencial. Se NIEGA a guardar el secreto sin cifrado disponible."""
        if self._cipher is None:
            raise RuntimeError(
                "no hay cifrado disponible (keyring/cryptography): NO se guarda un secreto en claro"
            )
        enc = _ENC_PREFIX + self._cipher.encrypt(secret.encode("utf-8")).decode("ascii")
        self._data[service.lower().strip()] = {
            "service": service,
            "username": username,
            "secret_enc": enc,
            "notes": notes,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._save()

    def get_secret(self, service: str) -> str | None:
        """Descifra el secreto (solo para usarlo en el momento; no lo registres en logs)."""
        entry = self._data.get(service.lower().strip())
        if not entry or self._cipher is None:
            return None
        enc = entry.get("secret_enc", "")
        if not enc.startswith(_ENC_PREFIX):
            return None
        try:
            return self._cipher.decrypt(enc[len(_ENC_PREFIX) :].encode("ascii")).decode("utf-8")
        except Exception:
            return None

    def get_username(self, service: str) -> str | None:
        entry = self._data.get(service.lower().strip())
        return entry.get("username") if entry else None

    def list(self) -> list[dict[str, str]]:
        """Lista las credenciales SIN el secreto (para auditoría/UI)."""
        return [
            {
                "service": e.get("service", ""),
                "username": e.get("username", ""),
                "notes": e.get("notes", ""),
                "updated_at": e.get("updated_at", ""),
            }
            for e in self._data.values()
        ]

    def delete(self, service: str) -> bool:
        key = service.lower().strip()
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False
