"""Settings API endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from urllib.parse import urlparse

from ..services import settings as settings_service

router = APIRouter()


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    theme: Literal["light", "dark"]
    plexUrl: str = Field(default="")
    plexToken: str = Field(default="")

    @field_validator("plexUrl", mode="before")
    @classmethod
    def _validate_plex_url(cls, value: str | None) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            value = str(value)
        stripped = value.strip()
        if not stripped:
            return ""
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Invalid Plex URL")
        return stripped

    @field_validator("plexToken", mode="before")
    @classmethod
    def _validate_plex_token(cls, value: str | None) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.strip()


@router.get("/api/settings", response_model=SettingsPayload)
def get_settings() -> SettingsPayload:
    data = settings_service.load_settings()
    return SettingsPayload(**data)


@router.put("/api/settings", response_model=SettingsPayload)
def update_settings(payload: SettingsPayload) -> SettingsPayload:
    stored = settings_service.save_settings(payload.model_dump())
    return SettingsPayload(**stored)
