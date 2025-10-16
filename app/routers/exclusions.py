"""API endpoints for managing excluded items."""
from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services import exclusions as exclusions_service

router = APIRouter()


class ExclusionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    library: str = Field(..., description="Plex library name")
    ratingKey: str = Field(..., description="Plex rating key")
    type: Literal["movie", "show", "collection"]
    title: Optional[str] = Field(default=None, description="Item title for display")
    year: Optional[int] = Field(default=None, description="Release year")

    @field_validator("library", mode="before")
    @classmethod
    def _validate_library(cls, value: str | None) -> str:
        if value in (None, ""):
            raise ValueError("Library is required")
        text = str(value).strip()
        if not text:
            raise ValueError("Library is required")
        return text

    @field_validator("ratingKey", mode="before")
    @classmethod
    def _validate_rating_key(cls, value: str | None) -> str:
        if value in (None, ""):
            raise ValueError("ratingKey is required")
        text = str(value).strip()
        if not text:
            raise ValueError("ratingKey is required")
        return text

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: str | None) -> Optional[str]:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text or None


class ExclusionResponse(ExclusionPayload):
    excludedAt: str = Field(description="ISO 8601 timestamp when the exclusion was saved")


@router.get("/api/exclusions", response_model=List[ExclusionResponse])
def get_exclusions() -> List[ExclusionResponse]:
    entries = exclusions_service.list_exclusions()
    return [ExclusionResponse(**entry) for entry in entries]


@router.post("/api/exclusions", response_model=ExclusionResponse, status_code=201)
def create_exclusion(payload: ExclusionPayload) -> ExclusionResponse:
    stored = exclusions_service.add_exclusion(
        payload.library,
        payload.ratingKey,
        payload.type,
        title=payload.title,
        year=payload.year,
    )
    return ExclusionResponse(**stored)


@router.delete("/api/exclusions/{library}/{rating_key}", status_code=204)
def delete_exclusion(library: str, rating_key: str) -> Response:
    removed = exclusions_service.remove_exclusion(library, rating_key)
    if not removed:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    return Response(status_code=204)
