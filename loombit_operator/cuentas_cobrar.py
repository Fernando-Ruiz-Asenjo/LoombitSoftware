"""
cuentas_cobrar.py — Skill D Cobros: store persistente de cuentas a cobrar (cuentas por cobrar).

Lo que falta para la Fase 2 (Morning Brief con datos reales): un registro de facturas/importes
pendientes de cobro con su vencimiento. Neutro en cuanto a fuente — se alimenta a mano (router),
desde intake de facturas o desde conciliación. La lógica de vencimiento la pone `cobros.py`.

Persiste en `runtime/local/cuentas_cobrar.json`. Determinista; el LLM no interviene.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from .cobros import days_overdue
from .config import AppSettings, get_settings


def _norm(text: str) -> str:
    """minúsculas + sin acentos + espacios colapsados. Para casar nombres y tokens."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


def _ref_casa(referencia: str, concepto: str) -> bool:
    """La referencia casa como TOKEN delimitado dentro del concepto, no como subcadena.
    'F-7' NO casa con 'Factura F-70' (el siguiente carácter es alfanumérico)."""
    ref = _norm(referencia)
    if not ref:
        return False
    patron = r"(?<![0-9a-z])" + re.escape(ref) + r"(?![0-9a-z])"
    return re.search(patron, _norm(concepto)) is not None


def _cliente_casa(consulta: str, almacenado: str) -> bool:
    """Casa el nombre del cliente por CONJUNTO de tokens, no por subcadena.
    'Ana' NO casa 'Anabel SL'; 'Beta' SÍ casa 'Beta SL' (subconjunto de tokens)."""
    q = set(_norm(consulta).split())
    a = set(_norm(almacenado).split())
    if not q or not a:
        return False
    return q <= a or a <= q


def _dias_vencido(vencimiento: str, today: str | date | None) -> int | None:
    """Días vencidos, o None si la fecha es ilegible (NO revienta el listado entero)."""
    try:
        return days_overdue(vencimiento, today)
    except (ValueError, TypeError):
        return None


@dataclass
class CuentaCobrar:
    cliente: str
    importe: float
    vencimiento: str  # ISO date "YYYY-MM-DD"
    concepto: str = ""
    estado: str = "pendiente"  # pendiente | cobrada
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def __post_init__(self) -> None:
        # Invariante: una cuenta a cobrar tiene importe numérico y NO negativo
        # (te deben dinero, no al revés). ALG-1.4: rechaza lo imposible en origen.
        try:
            self.importe = float(self.importe)
        except (TypeError, ValueError):
            raise ValueError(f"importe no numérico: {self.importe!r}") from None
        if self.importe < 0:
            raise ValueError(f"importe negativo no permitido: {self.importe}")

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
        self._items = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for raw in data:
            try:
                cuenta = CuentaCobrar.from_dict(raw)
            except Exception:
                continue  # fila corrupta (importe negativo, etc.): se omite, no tumba el store
            self._items[cuenta.id] = cuenta

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
        """Pendientes cuyo vencimiento ya pasó (días vencidos > 0). Una fecha ilegible
        no se clasifica como vencida ni revienta el listado (sigue visible en pendientes)."""
        out = []
        for c in self.pendientes():
            dias = _dias_vencido(c.vencimiento, today)
            if dias is not None and dias > 0:
                out.append(c)
        return out

    def proximas(self, dias: int = 7, today: str | date | None = None) -> list[CuentaCobrar]:
        """Pendientes que vencen dentro de los próximos `dias` (aún no vencidas).
        Una fecha ilegible se omite sin reventar."""
        out = []
        for c in self.pendientes():
            vencido = _dias_vencido(c.vencimiento, today)
            if vencido is None:
                continue
            faltan = -vencido  # >0 = aún no vence
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
        if (referencia or "").strip():
            for c in pend:
                if _ref_casa(referencia, c.concepto):
                    self.marcar_cobrada(c.id)
                    return c.id
        if (cliente or "").strip() and importe is not None:
            for c in pend:
                if _cliente_casa(cliente, c.cliente) and abs(c.importe - float(importe)) <= tol:
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
    if sentido != "devengado" or not total or float(total) <= 0:
        return None
    venc = vencimiento or (date.today() + timedelta(days=plazo_dias)).isoformat()
    return CuentaCobrar(
        cliente=proveedor or "(sin nombre)",
        importe=float(total),
        vencimiento=venc,
        concepto=f"Factura {numero}".strip(),
    )
