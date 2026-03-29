"""AWS Secrets Manager integration for PatientSynapse.

In production, secrets are stored in AWS Secrets Manager instead of .env files.
The secret is a single JSON blob keyed by `SECRETS_MANAGER_SECRET_ID` (env var)
or `patientsynapse/{APP_ENV}` by default.

Local development still uses .env — Secrets Manager is only queried when
`SECRETS_MANAGER_SECRET_ID` is set (or `APP_ENV` is not "development").

Requires:
  - boto3 (already a dependency)
  - AWS credentials available (IAM role on EC2, or local profile)
  - secretsmanager:GetSecretValue permission on the secret ARN
"""

import json
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


def _get_secret_id() -> Optional[str]:
    """Determine the Secrets Manager secret ID, if any.

    Returns None in local dev (no SM lookup), or the secret ID otherwise.
    """
    # Explicit override always wins
    explicit = os.environ.get("SECRETS_MANAGER_SECRET_ID")
    if explicit:
        return explicit

    # In development, skip SM entirely — use .env
    env = os.environ.get("APP_ENV", "development")
    if env == "development":
        return None

    # Non-development: use convention-based secret name
    return f"patientsynapse/{env}"


@lru_cache()
def load_secrets() -> dict:
    """Fetch secrets from AWS Secrets Manager.

    Returns a dict of key-value pairs (uppercased keys matching env var names),
    or an empty dict if SM is not configured.
    """
    secret_id = _get_secret_id()
    if not secret_id:
        logger.debug("Secrets Manager not configured — using .env")
        return {}

    try:
        import boto3
        from botocore.config import Config

        region = os.environ.get("AWS_REGION", os.environ.get("BEDROCK_REGION", "us-east-1"))
        client = boto3.client(
            "secretsmanager",
            config=Config(region_name=region, retries={"max_attempts": 2}),
        )
        response = client.get_secret_value(SecretId=secret_id)
        secret_string = response["SecretString"]
        secrets = json.loads(secret_string)

        logger.info(f"Loaded {len(secrets)} secrets from Secrets Manager ({secret_id})")
        return secrets

    except client.exceptions.ResourceNotFoundException:
        logger.error(f"Secret '{secret_id}' not found in Secrets Manager")
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Failed to fetch secrets from Secrets Manager: {e}")
        raise SystemExit(1)


# Keys that should be stored in Secrets Manager (actual secrets, not config)
SECRET_KEYS = [
    "APP_SECRET_KEY",
    "ADMIN_DEFAULT_PASSWORD",
    "ECW_CLIENT_ID",
    "ECW_JWKS_URL",
    "ECW_TOKEN_URL",
    "ECW_AUTHORIZE_URL",
    "ATHENA_CLIENT_ID",
    "ATHENA_CLIENT_SECRET",
    "ATHENA_PRACTICE_ID",
    "XAI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DATABASE_URL",
]
