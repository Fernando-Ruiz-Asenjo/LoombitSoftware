#!/usr/bin/env python3
"""Hook PreToolUse: corta EN VIVO un par de violaciones claras (fail-open).

Lee el JSON del hook por stdin. Bloquea (exit 2) solo en casos inequivocos;
ante cualquier duda, PERMITE (exit 0) para no romper el flujo de trabajo.

Casos que bloquea:
  1. Escribir lenguaje de exito absoluto ("0 bugs", "perfecto", "5-cero", ...)
     en un documento .md  -> obliga a reportar con recibo (PASO D5).

Es la capa de feedback inmediato; el gate DURO e infalsificable es el CI.
"""

from __future__ import annotations

import json
import re
import sys

BANNED = re.compile(
    r"\b(0\s*bugs|cero\s*bugs|sin\s+bugs|0\s*fallos|cero\s*fallos|perfecto|perfecta|"
    r"5[\s-]*cero|100\s*%\s*verde|todo\s+(en\s+)?verde|funciona\s+de\s+maravilla)\b",
    re.IGNORECASE,
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # fail-open: si no entendemos la entrada, permitimos

    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0

    ti = data.get("tool_input", {}) or {}
    path = str(ti.get("file_path", ""))
    content = " ".join(str(ti.get(k, "")) for k in ("content", "new_string"))

    if path.endswith(".md"):
        for line in content.splitlines():
            if "verify-allow" in line:  # exencion explicita por linea (igual que el gate)
                continue
            m = BANNED.search(line)
            if m:
                sys.stderr.write(
                    f"BLOQUEADO por Loombit Verify: '{m.group(0)}' es lenguaje de exito "
                    f"absoluto sin recibo (PASO D5). Reporta COBERTURA + lo NO probado + "
                    f"link al run de CI en su lugar.\n"
                )
                return 2  # exit 2 -> el hook bloquea la accion

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
