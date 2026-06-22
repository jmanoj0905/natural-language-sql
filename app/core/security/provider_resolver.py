"""Resolve the effective provider config for a query.

Precedence: explicit request option (non-empty) wins; otherwise the stored,
encrypted settings are used. The cloud API key and ollama_url come from the
store unless the request explicitly supplies a key.
"""

from app.core.security import secret_store

_DEFAULT_PROVIDER = "ollama"


def resolve_provider_config(options) -> tuple[str, str, str, str]:
    stored = secret_store.load_settings()
    req_provider = getattr(options, "provider", "") or ""
    req_model = getattr(options, "model", "") or ""
    req_key = getattr(options, "api_key", "") or ""

    # A request that left provider at the default ("ollama") and supplied no key
    # defers entirely to stored settings; an explicit non-default provider wins.
    if req_provider and req_provider != _DEFAULT_PROVIDER:
        provider = req_provider
        model = req_model
        api_key = req_key
    else:
        provider = stored["provider"] or _DEFAULT_PROVIDER
        model = req_model or stored["model"]
        api_key = req_key or stored["api_key"]

    return provider, model, api_key, stored["ollama_url"]
