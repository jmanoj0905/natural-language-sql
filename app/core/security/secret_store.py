"""Encrypted local settings store for provider config + cloud API key.

Persists to ~/.nlsql/settings.json. The API key is Fernet-encrypted with the
shared cipher (key_store); everything else is plaintext config.
"""

import json
from pathlib import Path

from app.core.security.key_store import get_cipher

SETTINGS_FILE = Path.home() / ".nlsql" / "settings.json"

_DEFAULTS = {"provider": "ollama", "model": "", "ollama_url": "", "api_key": ""}


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return dict(_DEFAULTS)
    raw = json.loads(SETTINGS_FILE.read_text())
    data = {k: raw.get(k, _DEFAULTS[k]) for k in ("provider", "model", "ollama_url")}
    enc = raw.get("api_key_encrypted", "")
    data["api_key"] = get_cipher().decrypt(enc.encode()).decode() if enc else ""
    return data


def save_settings(
    provider: str, model: str, ollama_url: str, api_key: str | None = None
) -> None:
    key = load_settings()["api_key"] if api_key is None else api_key
    out = {
        "provider": provider,
        "model": model,
        "ollama_url": ollama_url,
        "api_key_encrypted": get_cipher().encrypt(key.encode()).decode() if key else "",
    }
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(out, indent=2))


def mask_key(key: str) -> str:
    if not key:
        return ""
    return f"…{key[-4:]}" if len(key) >= 4 else "…"
