from app.config import get_settings
import app.core.security.key_store as key_store
from app.core.database.connection_manager import DatabaseConnectionManager


def test_password_round_trips_across_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    key_store.reset_cipher_cache()
    # Avoid touching the real ~/.nlsql/databases.json
    monkeypatch.setattr(
        DatabaseConnectionManager, "_load_saved_databases", lambda self: None
    )

    mgr = DatabaseConnectionManager()
    token = mgr._encrypt_password("hunter2")

    # Simulate restart: new manager, cipher reloaded from the persisted key file
    key_store.reset_cipher_cache()
    mgr2 = DatabaseConnectionManager()
    assert mgr2._decrypt_password(token) == "hunter2"
