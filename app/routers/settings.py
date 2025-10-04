"""Settings API endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

from ..services import settings as settings_service

router = APIRouter()


class SettingsPayload(BaseModel):
    theme: Literal["light", "dark"]


@router.get("/api/settings", response_model=SettingsPayload)
def get_settings() -> SettingsPayload:
    data = settings_service.load_settings()
    return SettingsPayload(**data)


@router.put("/api/settings", response_model=SettingsPayload)
def update_settings(payload: SettingsPayload) -> SettingsPayload:
    stored = settings_service.save_settings(payload.model_dump())
    return SettingsPayload(**stored)
