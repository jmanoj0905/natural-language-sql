from fastapi.testclient import TestClient

from app.config import get_settings
import app.core.security.key_store as key_store
import app.core.security.secret_store as secret_store
from app.main import app


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    monkeypatch.setattr(secret_store, "SETTINGS_FILE", tmp_path / "settings.json")
    key_store.reset_cipher_cache()


def test_get_defaults(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/v1/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "ollama"
    assert body["has_api_key"] is False
    assert body["api_key_masked"] == ""


def test_post_then_get_masks_key(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/settings",
            json={"provider": "openai", "model": "gpt-4o-mini",
                  "ollama_url": "", "api_key": "sk-abcdef1234"},
        )
        assert r.status_code == 200
        # Raw key never echoed back
        assert "sk-abcdef1234" not in r.text
        assert r.json()["api_key_masked"] == "…1234"
        assert r.json()["has_api_key"] is True
        # Re-save without key keeps it
        r2 = client.post(
            "/api/v1/settings",
            json={"provider": "openai", "model": "gpt-4o", "ollama_url": ""},
        )
        assert r2.json()["has_api_key"] is True
