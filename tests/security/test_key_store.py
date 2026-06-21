import importlib
from cryptography.fernet import Fernet
from app.config import get_settings
import app.core.security.key_store as key_store


def _fresh(monkeypatch, tmp_path):
    """Point the key store at a temp dir with no configured key."""
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "NLSQL_DIR", tmp_path)
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    key_store.reset_cipher_cache()


def test_generates_and_persists_key_when_unset(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    cipher = key_store.get_cipher()
    token = cipher.encrypt(b"secret")
    # File created with the generated key
    assert (tmp_path / ".encryption_key").exists()
    # Simulate a restart: drop the in-memory cipher, reload from disk
    key_store.reset_cipher_cache()
    assert key_store.get_cipher().decrypt(token) == b"secret"


def test_uses_configured_key_when_set(monkeypatch, tmp_path):
    configured = Fernet.generate_key().decode()
    monkeypatch.setenv("DB_ENCRYPTION_KEY", configured)
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    key_store.reset_cipher_cache()
    cipher = key_store.get_cipher()
    # Configured key wins; no file is written
    assert not (tmp_path / ".encryption_key").exists()
    assert Fernet(configured.encode()).decrypt(cipher.encrypt(b"x")) == b"x"
