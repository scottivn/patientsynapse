"""Tests for AWS Secrets Manager integration."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

# Clear cached settings/secrets between tests
@pytest.fixture(autouse=True)
def clear_caches():
    from server.secrets import load_secrets
    from server.config import get_settings
    load_secrets.cache_clear()
    get_settings.cache_clear()
    yield
    load_secrets.cache_clear()
    get_settings.cache_clear()


class TestGetSecretId:
    """Test secret ID resolution logic."""

    def test_returns_none_in_development(self):
        from server.secrets import _get_secret_id
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            assert _get_secret_id() is None

    def test_returns_convention_name_in_staging(self):
        from server.secrets import _get_secret_id
        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            assert _get_secret_id() == "patientsynapse/staging"

    def test_returns_convention_name_in_production(self):
        from server.secrets import _get_secret_id
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            assert _get_secret_id() == "patientsynapse/production"

    def test_explicit_override_wins(self):
        from server.secrets import _get_secret_id
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "SECRETS_MANAGER_SECRET_ID": "custom/secret",
        }, clear=False):
            assert _get_secret_id() == "custom/secret"

    def test_defaults_to_development_when_unset(self):
        from server.secrets import _get_secret_id
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APP_ENV", None)
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            assert _get_secret_id() is None


class TestLoadSecrets:
    """Test secrets loading from Secrets Manager."""

    def test_returns_empty_dict_in_dev(self):
        from server.secrets import load_secrets
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            result = load_secrets()
            assert result == {}

    def test_fetches_from_sm_in_staging(self):
        from server.secrets import load_secrets
        mock_secrets = {"APP_SECRET_KEY": "super-secret", "XAI_API_KEY": "xai-123"}

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secrets),
        }

        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            with patch("boto3.client", return_value=mock_client):
                result = load_secrets()

        assert result == mock_secrets
        mock_client.get_secret_value.assert_called_once_with(
            SecretId="patientsynapse/staging"
        )

    def test_exits_on_missing_secret(self):
        from server.secrets import load_secrets

        mock_client = MagicMock()
        mock_client.exceptions.ResourceNotFoundException = type(
            "ResourceNotFoundException", (Exception,), {}
        )
        mock_client.get_secret_value.side_effect = (
            mock_client.exceptions.ResourceNotFoundException("not found")
        )

        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            with patch("boto3.client", return_value=mock_client):
                with pytest.raises(SystemExit):
                    load_secrets()


class TestConfigIntegration:
    """Test that config.py correctly injects SM secrets."""

    def test_dev_mode_ignores_sm(self):
        """In development, settings load from .env only, no SM call."""
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            from server.config import get_settings
            settings = get_settings()
            assert settings.app_env == "development"

    def test_sm_secrets_injected_into_env(self):
        """Secrets from SM are injected as env vars before Settings reads them."""
        mock_secrets = {"APP_SECRET_KEY": "from-secrets-manager"}

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secrets),
        }

        # Start with APP_SECRET_KEY not in env
        env = {k: v for k, v in os.environ.items() if k != "APP_SECRET_KEY"}
        env["APP_ENV"] = "staging"
        env.pop("SECRETS_MANAGER_SECRET_ID", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("boto3.client", return_value=mock_client):
                from server.config import get_settings
                settings = get_settings()
                assert settings.app_secret_key == "from-secrets-manager"

    def test_env_var_overrides_sm_secret(self):
        """Explicit env vars take precedence over SM values."""
        mock_secrets = {"APP_SECRET_KEY": "from-sm"}

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secrets),
        }

        with patch.dict(os.environ, {
            "APP_ENV": "staging",
            "APP_SECRET_KEY": "from-env-var",
        }, clear=False):
            os.environ.pop("SECRETS_MANAGER_SECRET_ID", None)
            with patch("boto3.client", return_value=mock_client):
                from server.config import get_settings
                settings = get_settings()
                assert settings.app_secret_key == "from-env-var"
