"""Pydantic models for database connections."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    database_id: str = Field(..., description="Unique identifier for this database")
    nickname: Optional[str] = Field(None, description="Friendly display name")
    db_type: str = Field(default="postgresql", description="Database type: postgresql or mysql")
    host: str = Field(..., description="Database host")
    port: int = Field(..., ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode (for PostgreSQL)")

    class Config:
        json_schema_extra = {
            "example": {
                "database_id": "prod-db",
                "nickname": "Production Database",
                "host": "localhost",
                "port": 5432,
                "database": "myapp",
                "username": "readonly_user",
                "password": "secure_password",
                "ssl_mode": "prefer"
            }
        }


class DatabaseConnectionTest(BaseModel):
    """Result of database connection test."""

    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class DatabaseInfo(BaseModel):
    """Information about a registered database."""

    database_id: str
    nickname: Optional[str]
    db_type: str
    host: str
    port: int
    database: str
    username: str
    is_connected: bool
    table_count: Optional[int] = None
    ssl_mode: str


class DatabaseListResponse(BaseModel):
    """Response for listing all databases."""

    success: bool
    databases: List[DatabaseInfo]
    default_database_id: Optional[str] = None
