"""Settings API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Literal
from urllib.parse import urlparse

from ..services import (
    auth as auth_service,
    health as health_service,
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
    """Settings as the UI saves them. A blank plexToken or authPassword keeps the saved one."""

    model_config = ConfigDict(extra="ignore")

    theme: Literal["light", "dark"]
    plexUrl: str = Field(default="")
    plexToken: str = Field(default="")
    autoApplyToPlex: bool = Field(default=False)
    authMode: Literal["builtin", "reverse_proxy"] = Field(default="builtin")
    authUsername: str = Field(default="", max_length=128)
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

    @field_validator("authMode", mode="before")
    @classmethod
    def _validate_auth_mode(cls, value: str | None) -> str:
        if value in (None, ""):
            return "builtin"
        if not isinstance(value, str):
            value = str(value)
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {"builtin", "built_in", "built-in"}:
            return "builtin"
        if normalized in {"reverse_proxy", "reverse-proxy", "proxy"}:
            return "reverse_proxy"
        raise ValueError("Invalid authentication mode")

    @field_validator("authPassword", mode="before")
    @classmethod
    def _validate_auth_password(cls, value: str | None) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.strip()

    @field_validator("authUsername", mode="before")
    @classmethod
    def _validate_auth_username(cls, value: str | None) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.strip()


class SettingsResponse(BaseModel):
    """Settings as the UI reads them: secrets are reported as set or not, never sent."""

    theme: Literal["light", "dark"]
    plexUrl: str = ""
    plexTokenSet: bool = False
    autoApplyToPlex: bool = False
    authMode: Literal["builtin", "reverse_proxy"] = "builtin"
    authUsername: str = ""
    authPasswordSet: bool = False
    libraryMappings: List[LibraryMappingPayload] = Field(default_factory=list)


def _settings_response(data: dict) -> SettingsResponse:
    # Validate through the payload model so stored values get the same cleanup.
    payload = SettingsPayload(**data)
    return SettingsResponse(
        **payload.model_dump(exclude={"plexToken", "authPassword"}),
        plexTokenSet=bool(payload.plexToken),
        authPasswordSet=bool(str(data.get("authPasswordHash") or "").strip()),
    )


def _reject_disallowed_paths(mappings: List[LibraryMappingPayload]) -> None:
    previous = settings_service.load_settings().get("libraryMappings") or []
    disallowed = library_mappings_service.disallowed_paths(
        [item.model_dump() for item in mappings],
        previous if isinstance(previous, list) else [],
    )
    if disallowed:
        roots = ", ".join(library_mappings_service.allowed_roots())
        raise HTTPException(
            status_code=422,
            detail=f"Library folders must be inside {roots}: {', '.join(disallowed)}",
        )


@router.get("/api/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return _settings_response(settings_service.load_settings())


@router.put("/api/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsPayload) -> SettingsResponse:
    saved = settings_service.load_settings()
    has_password = bool(payload.authPassword or str(saved.get("authPasswordHash") or "").strip())
    if not has_password and auth_service.password_required_for(payload.authMode):
        raise HTTPException(
            status_code=422,
            detail=(
                "A login password is required. To run KAM without a login, "
                "set KAM_AUTH_MODE=none on the container"
            ),
        )
    if payload.authMode == "builtin" and has_password and not payload.authUsername:
        raise HTTPException(
            status_code=422,
            detail="A login username is required when a login password is configured",
        )
    # The saved token stays with the server it was entered for.
    new_server = payload.plexUrl and payload.plexUrl != str(saved.get("plexUrl") or "").strip()
    if new_server and not payload.plexToken and saved.get("plexToken"):
        raise HTTPException(
            status_code=422,
            detail="Enter the Plex token again when changing the Plex URL",
        )
    _reject_disallowed_paths(payload.libraryMappings)
    stored = settings_service.save_settings(payload.model_dump())
    return _settings_response(stored)


@router.get("/api/settings/health")
def get_settings_health() -> dict:
    return health_service.get_health_report()


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
    _reject_disallowed_paths(payload.libraryMappings)
    stored = settings_service.save_library_mappings(
        [item.model_dump() for item in payload.libraryMappings]
    )
    mappings = stored.get("libraryMappings", [])
    return [LibraryMappingPayload(**item) for item in mappings]
