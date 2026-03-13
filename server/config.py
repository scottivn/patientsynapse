"""PatientBridge configuration via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    # eCW FHIR
    ecw_fhir_base_url: str = Field(default="https://localhost/fhir/r4/practice")
    ecw_client_id: str = Field(default="")
    ecw_jwks_url: str = Field(default="https://localhost:8443/.well-known/jwks.json")
    ecw_redirect_uri: str = Field(default="https://localhost:8443/auth/callback")
    ecw_token_url: str = Field(default="")
    ecw_authorize_url: str = Field(default="")

    # LLM
    llm_provider: Literal["grok", "openai", "anthropic", "ollama"] = "grok"
    xai_api_key: str = Field(default="")
    xai_model: str = "grok-3"
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # App
    app_secret_key: str = Field(default="change-me-in-production")
    app_host: str = "0.0.0.0"
    app_port: int = 8443
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Fax processing
    fax_poll_interval_seconds: int = 300
    fax_upload_dir: str = "./uploads"

    # Database
    database_url: str = "sqlite:///./patientbridge.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
