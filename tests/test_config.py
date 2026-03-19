"""Tests for app.config — Settings validation."""

import pytest
from pydantic import ValidationError
from app.config import Settings


def _settings(**overrides):
    """Create a Settings instance with test defaults + overrides.

    We override _env_file to prevent reading the user's real .env,
    so we only test code defaults and explicit overrides.
    """
    defaults = {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "DB_ENCRYPTION_KEY": "",
    }
    defaults.update(overrides)

    class TestSettings(Settings):
        model_config = Settings.model_config.copy()
        model_config["env_file"] = None  # don't read real .env

    return TestSettings(**defaults)


class TestOllamaSettings:
    def test_default_model(self):
        s = _settings()
        assert s.OLLAMA_MODEL == "mannix/defog-llama3-sqlcoder-8b"

    def test_default_temperature(self):
        s = _settings()
        assert s.OLLAMA_TEMPERATURE == 0.1

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            _settings(OLLAMA_TEMPERATURE=3.0)

    def test_temperature_negative(self):
        with pytest.raises(ValidationError):
            _settings(OLLAMA_TEMPERATURE=-0.1)

    def test_base_url_strips_trailing_slash(self):
        s = _settings(OLLAMA_BASE_URL="http://localhost:11434/")
        assert not s.OLLAMA_BASE_URL.endswith("/")

    def test_base_url_requires_scheme(self):
        with pytest.raises(ValidationError):
            _settings(OLLAMA_BASE_URL="localhost:11434")

    def test_base_url_rejects_ftp(self):
        with pytest.raises(ValidationError):
            _settings(OLLAMA_BASE_URL="ftp://localhost:11434")


class TestQueryLimits:
    def test_defaults(self):
        s = _settings()
        assert s.MAX_QUERY_RESULTS == 1000
        assert s.DEFAULT_QUERY_LIMIT == 100
        assert s.QUERY_TIMEOUT_SECONDS == 30

    def test_max_query_results_zero(self):
        with pytest.raises(ValidationError):
            _settings(MAX_QUERY_RESULTS=0)

    def test_max_query_results_too_high(self):
        with pytest.raises(ValidationError):
            _settings(MAX_QUERY_RESULTS=999999)

    def test_rate_limit_zero(self):
        with pytest.raises(ValidationError):
            _settings(API_RATE_LIMIT_PER_MINUTE=0)

    def test_rate_limit_too_high(self):
        with pytest.raises(ValidationError):
            _settings(API_RATE_LIMIT_PER_MINUTE=99999)


class TestCorsOrigins:
    def test_default(self):
        s = _settings()
        assert s.CORS_ORIGINS == ["http://localhost:3000"]

    def test_json_string(self):
        s = _settings(CORS_ORIGINS='["http://a.com","http://b.com"]')
        assert len(s.CORS_ORIGINS) == 2

    def test_comma_separated(self):
        s = _settings(CORS_ORIGINS="http://a.com,http://b.com")
        assert len(s.CORS_ORIGINS) == 2


class TestLogLevel:
    def test_valid_levels(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            s = _settings(LOG_LEVEL=level)
            assert s.LOG_LEVEL == level

    def test_case_insensitive(self):
        s = _settings(LOG_LEVEL="debug")
        assert s.LOG_LEVEL == "DEBUG"

    def test_invalid_level(self):
        with pytest.raises(ValidationError):
            _settings(LOG_LEVEL="TRACE")


class TestEncryptionKey:
    def test_empty_allowed(self):
        s = _settings(DB_ENCRYPTION_KEY="")
        assert s.DB_ENCRYPTION_KEY == ""

    def test_wrong_length_rejected(self):
        with pytest.raises(ValidationError):
            _settings(DB_ENCRYPTION_KEY="tooshort")
