# tests/test_provider_resolution.py
from types import SimpleNamespace

from app.config import get_settings
import app.core.security.key_store as key_store
import app.core.security.secret_store as secret_store
from app.core.security.provider_resolver import resolve_provider_config


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    monkeypatch.setattr(secret_store, "SETTINGS_FILE", tmp_path / "settings.json")
    key_store.reset_cipher_cache()


def _opts(provider="ollama", model="", api_key=""):
    return SimpleNamespace(provider=provider, model=model, api_key=api_key)


def test_falls_back_to_store(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("openai", "gpt-4o-mini", "", api_key="sk-stored")
    # Request carries only the default provider/no key -> stored wins
    provider, model, api_key, ollama_url = resolve_provider_config(_opts())
    assert (provider, model, api_key) == ("openai", "gpt-4o-mini", "sk-stored")


def test_request_overrides_store(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("openai", "gpt-4o-mini", "", api_key="sk-stored")
    provider, model, api_key, _ = resolve_provider_config(
        _opts(provider="groq", model="llama-3.1-8b-instant", api_key="gsk-req")
    )
    assert (provider, model, api_key) == ("groq", "llama-3.1-8b-instant", "gsk-req")


def test_ollama_url_always_from_store(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("ollama", "", "http://host.docker.internal:11434")
    _, _, _, ollama_url = resolve_provider_config(_opts())
    assert ollama_url == "http://host.docker.internal:11434"
