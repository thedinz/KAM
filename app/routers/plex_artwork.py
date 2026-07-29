"""Endpoints for applying saved KAM artwork directly to Plex."""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services import plex_artwork as plex_artwork_service
from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

ASSET_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


class ApplyPlexArtworkPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    library: str = Field(min_length=1)
    folderName: str = Field(min_length=1)
    ratingKey: str = Field(min_length=1)
    kind: Literal["poster", "background"] = "poster"
    season: int | None = Field(default=None, ge=0)
    episode: int | None = Field(default=None, ge=0)

    @field_validator("library", "folderName", "ratingKey", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Value is required")
        return text


def _asset_base_name(payload: ApplyPlexArtworkPayload) -> str:
    if payload.episode is not None:
        if payload.season is None:
            raise HTTPException(status_code=422, detail="Season is required for a title card")
        if payload.kind != "poster":
            raise HTTPException(status_code=422, detail="Episode backgrounds are not supported")
        return f"S{payload.season:02d}E{payload.episode:02d}"

    if payload.season is not None:
        base = f"Season{payload.season:02d}"
        return f"{base}_background" if payload.kind == "background" else base

    return "background" if payload.kind == "background" else "poster"


def _resolve_asset_path(payload: ApplyPlexArtworkPayload) -> str:
    try:
        folder = resolve_existing_dir_or_422(payload.library, payload.folderName)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    base_name = _asset_base_name(payload)
    for extension in ASSET_EXTENSIONS:
        candidate = os.path.join(folder, f"{base_name}{extension}")
        if os.path.isfile(candidate):
            return candidate
    raise HTTPException(status_code=404, detail=f"Saved artwork not found: {base_name}")


@router.post("/api/plex/artwork")
async def apply_saved_artwork(payload: ApplyPlexArtworkPayload) -> dict:
    path = _resolve_asset_path(payload)
    try:
        return await run_in_threadpool(
            plex_artwork_service.apply_artwork_file,
            payload.ratingKey,
            path,
            payload.kind,
        )
    except plex_artwork_service.PlexArtworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
