"""PatientSynapse configuration via environment variables.

In production, secrets are loaded from AWS Secrets Manager and injected
into the environment before Pydantic reads them. Non-secret config
(APP_ENV, LLM_PROVIDER, etc.) still comes from the environment or .env.

Precedence: env vars > Secrets Manager > .env file defaults.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


def _inject_secrets():
    """Load secrets from AWS Secrets Manager and set them as env vars.

    Only injects keys that are NOT already set in the environment,
    so explicit env vars always win. This runs once before Settings
    is instantiated.
    """
    from server.secrets import load_secrets
    secrets = load_secrets()
    injected = 0
    for key, value in secrets.items():
        upper_key = key.upper()
        if upper_key not in os.environ:
            os.environ[upper_key] = str(value)
            injected += 1
    if injected:
        import logging
        logging.getLogger(__name__).info(
            f"Injected {injected} secrets from Secrets Manager into environment"
        )


class Settings(BaseSettings):
    # EMR provider selector: ecw | athena
    emr_provider: Literal["ecw", "athena"] = "ecw"
    emr_redirect_uri: str = Field(default="https://localhost:8443/api/auth/callback")

    # eCW-specific settings (used when emr_provider=ecw)
    ecw_fhir_base_url: str = Field(default="https://localhost/fhir/r4/practice")
    ecw_client_id: str = Field(default="")
    ecw_jwks_url: str = Field(default="https://localhost:8443/.well-known/jwks.json")
    ecw_token_url: str = Field(default="")
    ecw_authorize_url: str = Field(default="")

    # Athena-specific settings (used when emr_provider=athena)
    # Set ATHENA_SANDBOX=true to point at preview.platform.athenahealth.com instead of production
    athena_sandbox: bool = Field(default=False)
    athena_fhir_base_url: str = Field(default="https://api.platform.athenahealth.com")
    athena_client_id: str = Field(default="")
    athena_client_secret: str = Field(default="")
    athena_authorize_url: str = Field(default="https://api.platform.athenahealth.com/oauth2/v1/authorize")
    athena_token_url: str = Field(default="https://api.platform.athenahealth.com/oauth2/v1/token")
    athena_practice_id: str = Field(default="")
    athena_brand_id: str = Field(default="1")
    athena_csg_id: str = Field(default="1")

    @property
    def athena_effective_fhir_base_url(self) -> str:
        # Athena FHIR R4 base — practice routing via ah-practice search param
        base = "https://api.preview.platform.athenahealth.com" if self.athena_sandbox else self.athena_fhir_base_url
        return f"{base}/fhir/r4"

    @property
    def athena_effective_token_url(self) -> str:
        if self.athena_sandbox:
            return "https://api.preview.platform.athenahealth.com/oauth2/v1/token"
        return self.athena_token_url

    @property
    def athena_effective_authorize_url(self) -> str:
        if self.athena_sandbox:
            return "https://api.preview.platform.athenahealth.com/oauth2/v1/authorize"
        return self.athena_authorize_url

    # Stub FHIR — use in-memory store instead of live EMR (no OAuth needed)
    use_stub_fhir: bool = Field(default=False)

    # LLM
    llm_provider: Literal["grok", "openai", "anthropic", "ollama", "bedrock"] = "grok"
    xai_api_key: str = Field(default="")
    xai_model: str = "grok-4-1-fast-non-reasoning"
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-6-20250929-v1:0"
    bedrock_region: str = "us-east-1"

    # App
    app_secret_key: str = Field(default="change-me-in-production")
    app_host: str = "0.0.0.0"
    app_port: int = 8443
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Admin auth
    admin_default_username: str = "admin"
    admin_default_password: str = Field(default="")
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    session_inactivity_timeout_minutes: int = 15

    # Fax processing
    # fax_poll_interval_seconds: int = 300  # Enable when ready for prod auto-polling
    fax_upload_dir: str = "./uploads"

    # Database
    database_url: str = "sqlite:///./patientsynapse.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    # Inject secrets from AWS SM before Pydantic reads the env
    _inject_secrets()
    return Settings()
