"""Shared fixtures for the test suite."""

import os
import pytest

# Ensure settings don't try to read a real .env during tests
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("DB_ENCRYPTION_KEY", "")


@pytest.fixture
def sample_schema():
    """A minimal schema context string for prompt-building tests."""
    return (
        "CREATE TABLE users (\n"
        "  id SERIAL PRIMARY KEY,\n"
        "  username VARCHAR(50) NOT NULL,\n"
        "  email VARCHAR(100),\n"
        "  created_at TIMESTAMP DEFAULT NOW()\n"
        ");\n\n"
        "CREATE TABLE orders (\n"
        "  id SERIAL PRIMARY KEY,\n"
        "  user_id INT REFERENCES users(id),\n"
        "  total DECIMAL(10,2),\n"
        "  created_at TIMESTAMP DEFAULT NOW()\n"
        ");"
    )
