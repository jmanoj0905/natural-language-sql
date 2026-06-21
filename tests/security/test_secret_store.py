from app.config import get_settings
import app.core.security.key_store as key_store
import app.core.security.secret_store as secret_store


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    monkeypatch.setattr(secret_store, "SETTINGS_FILE", tmp_path / "settings.json")
    key_store.reset_cipher_cache()


def test_defaults_when_no_file(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    s = secret_store.load_settings()
    assert s == {"provider": "ollama", "model": "", "ollama_url": "", "api_key": ""}


def test_save_and_load_round_trip(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("openai", "gpt-4o-mini", "", api_key="sk-secret-123")
    s = secret_store.load_settings()
    assert s["provider"] == "openai"
    assert s["model"] == "gpt-4o-mini"
    assert s["api_key"] == "sk-secret-123"
    # Key is encrypted at rest — plaintext must not be in the file
    assert "sk-secret-123" not in (tmp_path / "settings.json").read_text()


def test_none_api_key_keeps_existing(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("openai", "gpt-4o-mini", "", api_key="sk-keep")
    secret_store.save_settings("openai", "gpt-4o", "", api_key=None)
    s = secret_store.load_settings()
    assert s["model"] == "gpt-4o"
    assert s["api_key"] == "sk-keep"


def test_mask_key():
    assert secret_store.mask_key("") == ""
    assert secret_store.mask_key("sk-abcdef1234") == "…1234"
    assert secret_store.mask_key("ab") == "…"
