"""Shared Fernet cipher backed by a persistent local key file.

If DB_ENCRYPTION_KEY is set in the environment it wins (operator-managed).
Otherwise a key is generated once and persisted to ~/.nlsql/.encryption_key
so encrypted data survives container/process restarts.
"""

from pathlib import Path

from cryptography.fernet import Fernet

from app.config import get_settings

NLSQL_DIR = Path.home() / ".nlsql"
KEY_FILE = NLSQL_DIR / ".encryption_key"

_cipher: Fernet | None = None


def _load_or_create_key() -> bytes:
    configured = get_settings().DB_ENCRYPTION_KEY
    if configured:
        return configured.encode()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(0o600)
    return key


def get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_load_or_create_key())
    return _cipher


def reset_cipher_cache() -> None:
    """Drop the cached cipher (used by tests and after key rotation)."""
    global _cipher
    _cipher = None
