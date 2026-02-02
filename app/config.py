"""Application configuration management using Pydantic settings."""

from functools import lru_cache
from typing import List
from pydantic import field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
from urllib.parse import urlparse


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    API_TITLE: str = "Natural Language SQL Engine"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False

    # AI Configuration - Ollama (Local, FREE, No API key needed!)
    OLLAMA_MODEL: str = "llama3.2"  # or codellama, mistral, llama3.1, etc.
    OLLAMA_TEMPERATURE: float = 0.1
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # Ollama API endpoint

    # Security Settings
    MAX_QUERY_RESULTS: int = 1000
    DEFAULT_QUERY_LIMIT: int = 100
    QUERY_TIMEOUT_SECONDS: int = 30
    API_RATE_LIMIT_PER_MINUTE: int = 60
    DB_ENCRYPTION_KEY: str = ""  # Fernet encryption key for database passwords
    STRICT_SQL_VALIDATION: bool = False  # If True, strict validation. If False, trusts users who know SQL

    # Database Connection Defaults
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_TIMEOUT: int = 30

    # Caching Configuration
    ENABLE_SCHEMA_CACHE: bool = True
    SCHEMA_CACHE_TTL_SECONDS: int = 3600  # 1 hour
    ENABLE_QUERY_CACHE: bool = True
    QUERY_CACHE_TTL_SECONDS: int = 300    # 5 minutes

    # Redis Configuration (Optional)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "logs/app.log"

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v_upper

    @field_validator("OLLAMA_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v):
        """Validate Ollama temperature is between 0 and 2."""
        if not 0 <= v <= 2:
            raise ValueError("OLLAMA_TEMPERATURE must be between 0 and 2")
        return v

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def validate_ollama_url(cls, v):
        """Validate Ollama base URL is a valid URL."""
        if not v:
            raise ValueError("OLLAMA_BASE_URL cannot be empty")

        try:
            parsed = urlparse(v)
            if not parsed.scheme:
                raise ValueError("OLLAMA_BASE_URL must include a scheme (http:// or https://)")
            if not parsed.netloc:
                raise ValueError("OLLAMA_BASE_URL must include a valid host")
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("OLLAMA_BASE_URL must use http or https scheme")
        except Exception as e:
            raise ValueError(f"Invalid OLLAMA_BASE_URL: {str(e)}")

        return v.rstrip("/")  # Remove trailing slash for consistency

    @field_validator("DB_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v):
        """Validate encryption key format if provided."""
        if not v:
            # Empty is allowed - will generate temp key at runtime
            return v

        # Check if it's a valid base64 Fernet key (44 characters)
        if len(v) != 44:
            raise ValueError(
                "DB_ENCRYPTION_KEY must be a valid Fernet key (44 characters). "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        # Try to validate it's base64
        try:
            import base64
            base64.urlsafe_b64decode(v.encode())
        except Exception:
            raise ValueError("DB_ENCRYPTION_KEY must be a valid base64-encoded Fernet key")

        return v

    @field_validator("API_RATE_LIMIT_PER_MINUTE")
    @classmethod
    def validate_rate_limit(cls, v):
        """Validate rate limit is reasonable."""
        if v <= 0:
            raise ValueError("API_RATE_LIMIT_PER_MINUTE must be greater than 0")
        if v > 10000:
            raise ValueError("API_RATE_LIMIT_PER_MINUTE seems unreasonably high (max 10000)")
        return v

    @field_validator("MAX_QUERY_RESULTS")
    @classmethod
    def validate_max_query_results(cls, v):
        """Validate maximum query results is reasonable."""
        if v <= 0:
            raise ValueError("MAX_QUERY_RESULTS must be greater than 0")
        if v > 100000:
            raise ValueError("MAX_QUERY_RESULTS is too high (max 100000 for memory safety)")
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration instance
    """
    return Settings()
