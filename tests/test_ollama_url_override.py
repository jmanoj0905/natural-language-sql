"""Tests for Ollama base-URL override in get_ollama_client and generate_with_config."""

import pytest

import app.core.ai.ollama_client as oc


def test_get_ollama_client_override_builds_transient(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    from app.config import get_settings
    get_settings.cache_clear()
    default = oc.get_ollama_client()
    overridden = oc.get_ollama_client(base_url="http://host.docker.internal:11434")
    assert overridden.base_url == "http://host.docker.internal:11434"
    # Override does not mutate the cached singleton
    assert oc.get_ollama_client().base_url == default.base_url


@pytest.mark.asyncio
async def test_generate_with_config_passes_url(monkeypatch):
    captured = {}

    class FakeClient:
        base_url = "http://x"
        async def generate_content(self, prompt, model_override=None):
            captured["url"] = self.base_url
            captured["model"] = model_override
            return "SELECT 1;"

    def fake_get(base_url=None):
        captured["asked"] = base_url
        return FakeClient()

    monkeypatch.setattr(oc, "get_ollama_client", fake_get)
    out = await oc.generate_with_config(
        "p", provider="ollama", model="llama3.2",
        api_key="", ollama_url="http://host.docker.internal:11434",
    )
    assert out == "SELECT 1;"
    assert captured["asked"] == "http://host.docker.internal:11434"
    assert captured["model"] == "llama3.2"
