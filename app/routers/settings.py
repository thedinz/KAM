"""Settings API endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Literal
from urllib.parse import urlparse

from ..services import (
    library_mappings as library_mappings_service,
    settings as settings_service,
)

router = APIRouter()


class CollectionSectionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    collectionsPath: str

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, value: str | None) -> str:
        if value in (None, ""):
            raise ValueError("Collection name is required")
        text = str(value).strip()
        if not text:
            raise ValueError("Collection name is required")
        return text

    @field_validator("collectionsPath", mode="before")
    @classmethod
    def _validate_path(cls, value: str | None) -> str:
        normalized = library_mappings_service.normalize_path(value)
        if not normalized:
            raise ValueError("Collections path is required")
        return normalized


class LibraryMappingPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    library: str
    assetPath: str
    collectionsPath: str | None = None
    collectionSections: List[CollectionSectionPayload] = Field(default_factory=list)

    @field_validator("library", mode="before")
    @classmethod
    def _validate_library(cls, value: str | None) -> str:
        if value in (None, ""):
            raise ValueError("Library name is required")
        text = str(value).strip()
        if not text:
            raise ValueError("Library name is required")
        return text

    @field_validator("assetPath", mode="before")
    @classmethod
    def _validate_asset_path(cls, value: str | None) -> str:
        normalized = library_mappings_service.normalize_path(value)
        if not normalized:
            raise ValueError("Asset path is required")
        return normalized

    @field_validator("collectionsPath", mode="before")
    @classmethod
    def _validate_collections_path(cls, value: str | None) -> str | None:
        normalized = library_mappings_service.normalize_path(value)
        return normalized or None

    @field_validator("collectionSections", mode="after")
    @classmethod
    def _sanitize_sections(
        cls, value: List[CollectionSectionPayload]
    ) -> List[CollectionSectionPayload]:
        normalized = library_mappings_service.normalize_collection_sections(
            [item.model_dump() for item in value]
        )
        return [CollectionSectionPayload(**item) for item in normalized]


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    theme: Literal["light", "dark"]
    plexUrl: str = Field(default="")
    plexToken: str = Field(default="")
    authPassword: str = Field(default="")
    libraryMappings: List[LibraryMappingPayload] = Field(default_factory=list)

    @field_validator("libraryMappings", mode="after")
    @classmethod
    def _dedupe_mappings(cls, value: List[LibraryMappingPayload]) -> List[LibraryMappingPayload]:
        if not value:
            return []
        sanitized = library_mappings_service.sanitize_library_mappings(
            [item.model_dump() for item in value]
        )
        return [LibraryMappingPayload(**item) for item in sanitized]

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

    @field_validator("authPassword", mode="before")
    @classmethod
    def _validate_auth_password(cls, value: str | None) -> str:
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


class LibraryMappingsUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    libraryMappings: List[LibraryMappingPayload] = Field(default_factory=list)

    @field_validator("libraryMappings", mode="after")
    @classmethod
    def _dedupe(cls, value: List[LibraryMappingPayload]) -> List[LibraryMappingPayload]:
        if not value:
            return []
        sanitized = library_mappings_service.sanitize_library_mappings(
            [item.model_dump() for item in value]
        )
        return [LibraryMappingPayload(**item) for item in sanitized]


@router.put("/api/settings/library-mappings", response_model=List[LibraryMappingPayload])
def update_library_mappings(payload: LibraryMappingsUpdatePayload) -> List[LibraryMappingPayload]:
    stored = settings_service.save_library_mappings(
        [item.model_dump() for item in payload.libraryMappings]
    )
    mappings = stored.get("libraryMappings", [])
    return [LibraryMappingPayload(**item) for item in mappings]

