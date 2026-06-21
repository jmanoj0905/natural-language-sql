"""Test ollama_url threading through SQLGenerator.generate"""

import pytest
import app.core.ai.ollama_sql_generator as gen_mod


@pytest.mark.asyncio
async def test_generate_forwards_ollama_url(monkeypatch):
    captured = {}

    async def fake_generate_with_config(prompt, provider, model, api_key, ollama_url=""):
        captured["ollama_url"] = ollama_url
        return "SELECT 1;"

    # Patch the symbol as imported into the generator module
    monkeypatch.setattr(gen_mod, "generate_with_config", fake_generate_with_config)

    g = gen_mod.SQLGenerator()
    # Stub schema/context building so the test stays unit-level; match the
    # generator's actual internal helper names when wiring this stub.
    async def fake_get_relevant_schema_summary(*a, **k):
        return "schema"

    monkeypatch.setattr(
        g.schema_inspector,
        "get_relevant_schema_summary",
        fake_get_relevant_schema_summary,
        raising=False,
    )
    # Also stub intent detector to avoid setup
    monkeypatch.setattr(
        g.intent_detector,
        "detect_intent",
        lambda *a, **k: type("QueryPlan", (), {"intent": type("Intent", (), {"value": "SELECT"}), "database_refs": [], "needs_decomposition": False})(),
        raising=False,
    )

    result = await g.generate(
        question="show users",
        connection=None,
        db_id="db1",
        provider="ollama",
        model="llama3.2",
        api_key="",
        ollama_url="http://host.docker.internal:11434",
    )
    assert captured["ollama_url"] == "http://host.docker.internal:11434"
