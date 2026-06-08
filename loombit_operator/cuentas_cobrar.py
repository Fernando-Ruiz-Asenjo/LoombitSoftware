"""
cuentas_cobrar.py — Skill D Cobros: store persistente de cuentas a cobrar (cuentas por cobrar).

Lo que falta para la Fase 2 (Morning Brief con datos reales): un registro de facturas/importes
pendientes de cobro con su vencimiento. Neutro en cuanto a fuente — se alimenta a mano (router),
desde intake de facturas o desde conciliación. La lógica de vencimiento la pone `cobros.py`.

Persiste en `runtime/local/cuentas_cobrar.json`. Determinista; el LLM no interviene.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from .cobros import days_overdue
from .config import AppSettings, get_settings


@dataclass
class CuentaCobrar:
    cliente: str
    importe: float
    vencimiento: str  # ISO date "YYYY-MM-DD"
    concepto: str = ""
    estado: str = "pendiente"  # pendiente | cobrada
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cliente": self.cliente,
            "importe": self.importe,
            "vencimiento": self.vencimiento,
            "concepto": self.concepto,
            "estado": self.estado,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CuentaCobrar":
        return cls(
            id=str(d.get("id", uuid4().hex[:8])),
            cliente=str(d.get("cliente", "")),
            importe=float(d.get("importe", 0) or 0),
            vencimiento=str(d.get("vencimiento", "")),
            concepto=str(d.get("concepto", "")),
            estado=str(d.get("estado", "pendiente")),
        )


class CuentasCobrarStore:
    """Store JSON de cuentas a cobrar. Sin límite; deduplicado por id."""

    def __init__(self, path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.path = path or Path(active.agent_run_store_path).parent / "cuentas_cobrar.json"
        self._items: dict[str, CuentaCobrar] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = {c["id"]: CuentaCobrar.from_dict(c) for c in data}
        except Exception:
            self._items = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([c.to_dict() for c in self._items.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, cuenta: CuentaCobrar) -> CuentaCobrar:
        self._items[cuenta.id] = cuenta
        self._save()
        return cuenta

    def list(self) -> list[CuentaCobrar]:
        return sorted(self._items.values(), key=lambda c: c.vencimiento)

    def pendientes(self) -> list[CuentaCobrar]:
        return [c for c in self.list() if c.estado == "pendiente"]

    def vencidas(self, today: str | date | None = None) -> list[CuentaCobrar]:
        """Pendientes cuyo vencimiento ya pasó (días vencidos > 0)."""
        return [c for c in self.pendientes() if days_overdue(c.vencimiento, today) > 0]

    def proximas(self, dias: int = 7, today: str | date | None = None) -> list[CuentaCobrar]:
        """Pendientes que vencen dentro de los próximos `dias` (aún no vencidas)."""
        out = []
        for c in self.pendientes():
            faltan = -days_overdue(c.vencimiento, today)  # >0 = aún no vence
            if 0 <= faltan <= dias:
                out.append(c)
        return out

    def marcar_cobrada(self, cuenta_id: str) -> bool:
        c = self._items.get(cuenta_id)
        if not c:
            return False
        c.estado = "cobrada"
        self._save()
        return True

    def conciliar_cobro(
        self,
        *,
        referencia: str = "",
        cliente: str = "",
        importe: float | None = None,
        tol: float = 0.01,
    ) -> str | None:
        """Marca cobrada la cuenta pendiente que case con un cobro conciliado. Empareja por
        referencia (en el concepto) o, si no, por cliente + importe. Devuelve el id o None."""
        pend = self.pendientes()
        ref = (referencia or "").strip().lower()
        if ref:
            for c in pend:
                if ref in c.concepto.lower():
                    self.marcar_cobrada(c.id)
                    return c.id
        cl = (cliente or "").strip().lower()
        if cl and importe is not None:
            for c in pend:
                if cl in c.cliente.lower() and abs(c.importe - float(importe)) <= tol:
                    self.marcar_cobrada(c.id)
                    return c.id
        return None


def cuenta_desde_factura(
    *,
    proveedor: str | None,
    total: float | None,
    sentido: str,
    numero: str = "",
    vencimiento: str | None = None,
    plazo_dias: int = 30,
) -> CuentaCobrar | None:
    """Crea una cuenta a cobrar SOLO si la factura es EMITIDA (sentido='devengado'=venta) y
    tiene importe. Una factura recibida (compra) no se cobra. Si no hay vencimiento, plazo estándar.
    """
    if sentido != "devengado" or not total:
        return None
    venc = vencimiento or (date.today() + timedelta(days=plazo_dias)).isoformat()
    return CuentaCobrar(
        cliente=proveedor or "(sin nombre)",
        importe=float(total),
        vencimiento=venc,
        concepto=f"Factura {numero}".strip(),
    )
