"""§GOB-1 — Capability Policy Plane: la superficie única de autoridad de Loombit.

Aquí vive "quién puede decidir qué". El LLM PROPONE una tool-call; el plano —código determinista—
DISPONE: ejecutar, exigir el gate humano, corregir o rehusar. Implementa la Ley Fundacional
(Separación de Autoridades): el LLM nunca está en el camino de control de confianza para nada
consecuente. Ver docs/BRUJULA.md §GOB-1.
"""

from .authority_plane import AUTHORITY_PLANE, Accion, AuthorityPlane, Decision

__all__ = ["AUTHORITY_PLANE", "Accion", "AuthorityPlane", "Decision"]
