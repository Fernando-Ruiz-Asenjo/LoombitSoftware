"""
verifactu_store.py — el LIBRO VeriFactu persistente: registros de facturación INALTERABLES y ENCADENADOS.

`verifactu.py` calcula la huella encadenada en memoria; aquí la persistimos en disco como un libro
**append-only** (`.jsonl`, una línea por registro), que es justo lo que exige VeriFactu: un registro
inalterable cuya cadena de huellas hace detectable cualquier manipulación posterior. Cada alta toma la
huella del ÚLTIMO registro guardado como `huella_anterior` (continúa la cadena), y al cargar se VERIFICA
la integridad. Idempotente por número de factura: una factura ya registrada no se duplica.

Determinista; el LLM no interviene. Frontera DECLARADA (igual que `verifactu.py`): la PRESENTACIÓN a la
Sede AEAT (certificado/firma) queda FUERA — esto guarda el registro conforme, no lo presenta.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

from ..config import AppSettings, get_settings
from ..docs_intel import InvoiceFields
from .verifactu import GENESIS, RegistroVerifactu, registro_desde_factura, verificar_cadena


class CadenaCorrupta(RuntimeError):
    """El libro en disco no encadena (huella rota / registro alterado): no se sigue escribiendo a ciegas."""


class RegistroVerifactuStore:
    """Libro append-only de registros VeriFactu. La cadena de huellas es tamper-evident."""

    def __init__(self, path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.path = path or Path(active.agent_run_store_path).parent / "verifactu_registros.jsonl"
        self._items: list[RegistroVerifactu] = []
        self._numeros: set[str] = set()
        self._load()

    def _load(self) -> None:
        self._items = []
        self._numeros = set()
        try:
            lineas = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for ln in lineas:
            if not ln.strip():
                continue
            d = json.loads(ln)
            reg = RegistroVerifactu(
                nif_emisor=str(d["nif_emisor"]),
                numero=str(d["numero"]),
                fecha=str(d["fecha"]),
                importe_total=float(d["importe_total"]),
                huella_anterior=str(d.get("huella_anterior", GENESIS)),
                huella=str(d.get("huella", "")),
            )
            self._items.append(reg)
            self._numeros.add(reg.numero)

    def last_huella(self) -> str:
        """La huella del último registro guardado (o GENESIS si el libro está vacío). El eslabón al que
        se encadena el próximo alta."""
        return self._items[-1].huella if self._items else GENESIS

    def registrar(
        self, inv: InvoiceFields, nif_emisor: str
    ) -> tuple[RegistroVerifactu | None, list[str]]:
        """Da de alta una factura en el libro, encadenándola al último registro. Abstención honesta si
        faltan campos; idempotente (una factura ya registrada no se duplica). Verifica la cadena ANTES de
        escribir: si el libro está corrupto, lanza `CadenaCorrupta` en vez de apilar sobre algo roto.
        """
        numero = str(inv.numero or "")
        if numero and numero in self._numeros:
            return None, [f"Factura {numero}: ya registrada en VeriFactu (no se duplica)."]
        errores = self.verificar()
        if errores:
            raise CadenaCorrupta(f"el libro VeriFactu no encadena: {errores}")
        reg, avisos = registro_desde_factura(inv, nif_emisor, self.last_huella())
        if reg is None:
            return None, avisos
        self._append(reg)
        return reg, avisos

    def _append(self, reg: RegistroVerifactu) -> None:
        """Añade UNA línea al final (append-only: nunca reescribe lo anterior)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg.to_dict(), ensure_ascii=False) + "\n")
        self._items.append(reg)
        self._numeros.add(reg.numero)

    def list(self) -> builtins.list[RegistroVerifactu]:
        return list(self._items)

    def verificar(self) -> builtins.list[str]:
        """Comprueba la inalterabilidad del libro entero (vacío si íntegro)."""
        return verificar_cadena(self._items)
