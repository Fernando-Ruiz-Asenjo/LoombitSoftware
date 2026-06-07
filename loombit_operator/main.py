"""Punto de entrada FastAPI. Solo crea la app y monta routers (anti-monolito)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import agent, computer, health, skill_blanca_actions, skill_blanca_oauth, ui

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Loombit Operator", version="0.1.0")

# Rutas API
app.include_router(health.router)
app.include_router(skill_blanca_oauth.router)
app.include_router(skill_blanca_actions.router)
app.include_router(agent.router)
app.include_router(computer.router)

# UI — sirve /static/* y / como home
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(ui.router)
