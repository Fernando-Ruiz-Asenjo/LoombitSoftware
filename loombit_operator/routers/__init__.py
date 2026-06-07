"""Routers FastAPI por dominio.

Regla anti-monolito: main.py solo crea la app y monta routers. Cada dominio
(skill_blanca, llm, telemetry, desktop_observer, industrial, safety...) es un
APIRouter independiente y testeable. Ningún fichero debe superar ~400 líneas.
"""
