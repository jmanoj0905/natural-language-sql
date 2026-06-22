"""Provider/credential settings endpoints (local, encrypted at rest)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import secret_store

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsIn(BaseModel):
    provider: str = "ollama"
    model: str = ""
    ollama_url: str = ""
    api_key: str | None = None  # None = leave existing key unchanged


class SettingsOut(BaseModel):
    provider: str
    model: str
    ollama_url: str
    api_key_masked: str
    has_api_key: bool


def _current() -> SettingsOut:
    s = secret_store.load_settings()
    return SettingsOut(
        provider=s["provider"],
        model=s["model"],
        ollama_url=s["ollama_url"],
        api_key_masked=secret_store.mask_key(s["api_key"]),
        has_api_key=bool(s["api_key"]),
    )


@router.get("", response_model=SettingsOut)
def read_settings() -> SettingsOut:
    return _current()


@router.post("", response_model=SettingsOut)
def write_settings(body: SettingsIn) -> SettingsOut:
    secret_store.save_settings(body.provider, body.model, body.ollama_url, body.api_key)
    return _current()
