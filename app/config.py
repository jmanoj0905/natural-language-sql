"""Application configuration management using Pydantic settings."""

from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


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


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration instance
    """
    return Settings()
