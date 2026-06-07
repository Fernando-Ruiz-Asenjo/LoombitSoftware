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
    llm_model_name: str = "qwen2.5-7b-instruct-1m"
    llm_request_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=512, gt=0)

    # Rol instructor
    llm_instructor_provider: str = ""
    llm_instructor_base_url: str = ""
    llm_instructor_model_name: str = ""

    # Rol coder
    llm_coder_provider: str = ""
    llm_coder_base_url: str = ""
    llm_coder_model_name: str = "qwen2.5-coder-7b-instruct"

    # ── Almacenamiento local ──────────────────────────────────────────────────
    lm_job_store_path: Path = Path("runtime/local/lm_jobs.json")
    agent_run_store_path: Path = Path("runtime/local/agent_runs.json")
    skill_manifest_dir: Path = Path("skills")

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
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/contacts.readonly"
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
