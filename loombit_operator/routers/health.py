"""Router de salud."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

from .. import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "loombit-operator", "version": __version__}


@router.