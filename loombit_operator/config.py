from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOOMBIT_OPERATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "loombit-operator"
    environment: str = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    runtime_mode: Literal["development", "local", "jetson"] = "development"

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: Literal[
        "disabled", "llama_cpp", "ollama", "vllm", "sglang", "lm_studio", "openai_compatible"
    ] = "lm_studio"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model_name: str = "qwen2.5-14b-instruct"
    llm_request_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=512, gt=0)
    # Contexto cargado del modelo en LM Studio (n_ctx). El agente recorta para no pasarse y evitar
    # el 400 "n_keep >= n_ctx" (ALG-0.1). Debe coincidir con el modelo cargado (>=8192 recomendado).
    llm_context_length: int = Field(default=8192, gt=0)

    # Rol instructor
    llm_instructor_provider: str = ""
    llm_instructor_base_url: str = ""
    llm_instructor_model_name: str = ""

    # Rol coder
    llm_coder_provider: str = ""
    llm_coder_base_url: str = ""
    llm_coder_model_name: str = "qwen2.5-coder-7b-instruct"

    # Embeddings (RAG / índice semántico local) — mismo endpoint OpenAI-like, modelo de embeddings.
    llm_embeddings_model_name: str = "text-embedding-nomic-embed-text-v1.5"
    rag_index_path: Path = Path("runtime/local/rag_index.json")

    # ── Almacenamiento local ──────────────────────────────────────────────────
    lm_job_store_path: Path = Path("runtime/local/lm_jobs.json")
    agent_run_store_path: Path = Path("runtime/local/agent_runs.json")
    # «Loombit Decide» (LD-0): la cola de decisiones que sube al humano.
    decision_store_path: Path = Path("runtime/local/decisions.json")
    skill_manifest_dir: Path = Path("skills")

    # ── Fábrica de Skills (Skill X) — auto-autoría gobernada ───────────────────
    # Cargar al arrancar las tools que un humano APROBÓ (gate sagrado): off por defecto.
    # Solo se cargan propuestas en estado APROBADA, re-verificadas por el gate de seguridad.
    fabrica_autocargar_generadas: bool = False

    # ── Routines (agentes proactivos programados) ─────────────────────────────
    routine_store_path: Path = Path("runtime/local/routines.json")
    routine_receipt_dir: Path = Path("runtime/local/routine_receipts")
    routines_daemon_enabled: bool = False
    routines_daemon_interval_seconds: int = 60

    # Observador Pilot: aprendizaje SEMÁNTICO de la actividad (app/ventana), local y OPT-IN.
    # OFF por defecto. NUNCA captura teclas ni pantalla (no es un keylogger). Ver pilot/observer.py.
    observer_enabled: bool = False
    observer_interval_seconds: int = 30

    # ── Expedientes (Skill W Administration Core) — SQLite por entidad ────────
    entities_dir: Path = Path("runtime/local/entities")
    # Entidad por defecto que la UI usa para descubrir entregables (vacío = la pregunta). Blanco:
    # configurable por .env, nunca hardcodeado a un cliente.
    ui_default_entity_id: str = ""

    # ── Skill Blanca — OAuth ──────────────────────────────────────────────────
    skill_blanca_oauth_token_store_path: Path = Path("runtime/local/skill_blanca_oauth_tokens.json")
    skill_blanca_oauth_local_config_path: Path = Path(
        "runtime/local/skill_blanca_oauth_config.json"
    )

    # Google
    skill_blanca_google_oauth_enabled: bool = False
    skill_blanca_google_client_id: str = ""
    skill_blanca_google_client_secret: str = ""
    skill_blanca_google_redirect_uri: str = (
        "http://127.0.0.1:8787/skill-blanca/oauth/google/callback"
    )
    skill_blanca_google_scopes: str = (
        "https://www.googleapis.com/auth/gmail.send "
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/contacts.readonly "
        # "otros contactos": gente a la que has escrito (auto-guardada por Gmail), donde vive el
        # email de un destinatario habitual aunque no esté en la libreta. Requiere re-autorizar.
        "https://www.googleapis.com/auth/contacts.other.readonly"
    )

    # Microsoft
    skill_blanca_microsoft_oauth_enabled: bool = False
    skill_blanca_microsoft_tenant: str = "common"
    skill_blanca_microsoft_client_id: str = ""
    skill_blanca_microsoft_client_secret: str = ""
    skill_blanca_microsoft_redirect_uri: str = (
        "http://127.0.0.1:8787/skill-blanca/oauth/microsoft/callback"
    )
    skill_blanca_microsoft_scopes: str = "offline_access User.Read Mail.Send Calendars.ReadWrite"

    # ── Skill Blanca — ejecución de conectores ────────────────────────────────
    skill_blanca_connector_writes_enabled: bool = False
    skill_blanca_email_delivery_mode: Literal[
        "disabled", "local_outbox", "smtp", "google_oauth", "microsoft_graph"
    ] = "disabled"
    skill_blanca_calendar_delivery_mode: Literal[
        "disabled", "local_ics", "google_oauth", "microsoft_graph"
    ] = "disabled"
    skill_blanca_connector_outbox_path: Path = Path("runtime/local/skill_blanca_connector_outbox")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
