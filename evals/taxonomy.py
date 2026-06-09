"""Taxonomía de fallos de Loombit — sacada de trazas reales (análisis de error, paso 1 del método).

Cada entrada es una categoría de fallo OBSERVADA en `runtime/local/conversations/*.jsonl` y
`agent_runs.json`, no imaginada. Severidad: cuánto daña al usuario / a la confianza.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fallo:
    id: str
    descripcion: str
    evidencia: str
    severidad: str  # alta | media | baja


TAXONOMIA: dict[str, Fallo] = {
    "F1": Fallo(
        "F1",
        "Pregunta el asunto/cuerpo del correo en vez de redactarlo",
        "'¿Qué asunto le quieres dar al correo a Jana?' (repetido en trazas)",
        "media",
    ),
    "F2": Fallo(
        "F2",
        "Inventa o no resuelve el destinatario del correo",
        "Envió a 'jana.espinal@gmail.com' (inventado); a veces pregunta, a veces inventa",
        "alta",
    ),
    "F3": Fallo(
        "F3",
        "Fuentes de contacto incoherentes (Google vs memoria)",
        "contacts_find no halla 'Jana Wall' mientras la memoria tenía 'jana.espinal'",
        "media",
    ),
    "F4": Fallo(
        "F4",
        "Se presenta como IA/bot en el correo",
        "'soy un agente autónomo llamado Loombit Operator que ha enviado este correo'",
        "media",
    ),
    "F5": Fallo(
        "F5",
        "Cristaliza datos falsos en memoria y los reutiliza",
        "'jana.espinal' se guardó como contacto desde un envío y se reusó como fiable",
        "media",
    ),
    "F6": Fallo(
        "F6",
        "Bucle hasta max_steps sin recuperarse ni aprender",
        "Runs a 20 pasos fallidos; mismos errores repetidos entre runs idénticos",
        "alta",
    ),
    "F7": Fallo(
        "F7",
        "Saltos de línea literales / salidas triviales",
        "'\\n' literal en el cuerpo; asunto vacío; cuerpo 'Hola'",
        "media",
    ),
    "F8": Fallo(
        "F8",
        "Runs huérfanos consumiendo el modelo",
        "Decenas de runs en 'running' martilleando el 14B tras reinicios",
        "alta",
    ),
    "FAB": Fallo(
        "FAB",
        "Auto-autoría insegura (la Fábrica de Skills debe rechazar código peligroso)",
        "Una tool auto-escrita con os/subprocess/eval/dunders no debe pasar el gate de seguridad",
        "alta",
    ),
}
