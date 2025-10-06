# app/routers/libraries.py
"""
Libraries router: only expose libraries explicitly mapped in the environment.

Env format (in your .env):
  LIBRARIES=Movies:/assets/Movies,Kids Movies:/assets/Kids Movies,TV Shows:/assets/TV Shows
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from ..services import library_mappings as library_mappings_service

router = APIRouter()

# Section types that should be ignored when listing available libraries. Plex
# exposes music libraries with types like "artist"/"audio" which KAM cannot
# currently map.
IGNORED_SECTION_TYPES = {"artist", "audio"}


def _is_supported_section(section_type: Optional[str]) -> bool:
    if not section_type:
        return True
    return section_type.lower() not in IGNORED_SECTION_TYPES


# --- Load mappings -----------------------------------------------------------

def _asset_library_map() -> Dict[str, str]:
    """Return libraries that have an active asset mapping."""
    mappings = library_mappings_service.load_library_mappings()
    result: Dict[str, str] = {}
    for entry in mappings:
        name = str(entry.get("library") or "").strip()
        asset_path = library_mappings_service.normalize_path(entry.get("assetPath"))
        if name and asset_path:
            result[name] = asset_path
    return result


def _ensure_any_mapped() -> Dict[str, str]:
    mapping = _asset_library_map()
    if not mapping:
        raise HTTPException(
            status_code=500,
            detail=(
                "No mapped libraries were found. Set LIBRARIES=Name:/path,... "
                "in your environment (or ensure config.LIBRARY_MAPPINGS is populated)."
            ),
        )
    return mapping


# --- Endpoints ---------------------------------------------------------------

@router.get("/api/libraries", response_model=List[str])
def get_libraries() -> List[str]:
    """
    Return only the names of libraries that are explicitly mapped.
    This prevents showing unsupported sections like Music, etc.
    """
    mapping = _ensure_any_mapped()
    names = sorted(mapping.keys())
    # Surface "Collections" when any per-library collections path exists.
    collections_root = library_mappings_service.get_collections_path()
    if collections_root and "Collections" not in names:
        names.append("Collections")
        names.sort()
    return names


@router.get("/api/libraries/map", response_model=Dict[str, str])
def get_library_map() -> Dict[str, str]:
    """
    Return the full name -> path map (useful for uploads).
    """
    mapping = _ensure_any_mapped()
    return {name: mapping[name] for name in sorted(mapping.keys())}


@router.get("/api/library-path")
def get_library_path(name: str = Query(..., description="Mapped library name")) -> Dict[str, str]:
    """
    Resolve a single library name to its mapped path.
    """
    mapping = _ensure_any_mapped()
    path = mapping.get(name)
    if not path:
        raise HTTPException(status_code=404, detail=f"Library '{name}' is not mapped.")
    return {"name": name, "path": path}


class CollectionOverrideInfo(BaseModel):
    name: str
    collectionsPath: Optional[str] = None
    suggestionPaths: List[str] = Field(default_factory=list)


class LibrarySectionInfo(BaseModel):
    name: str
    type: Optional[str] = None
    key: Optional[str] = None
    assetPath: Optional[str] = None
    collectionsPath: Optional[str] = None
    collectionAssetPaths: List[str] = Field(default_factory=list)
    collectionOverrides: List[CollectionOverrideInfo] = Field(default_factory=list)


@router.get("/api/settings/libraries", response_model=List[LibrarySectionInfo])
def list_available_libraries() -> List[LibrarySectionInfo]:
    """Return Plex libraries alongside any stored mapping metadata."""
    from ..services import plex_settings
    from ..services.plex import get_plex

    plex_settings.get_plex_config()

    plex = get_plex()
    try:
        sections = plex.library.sections()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Unable to list Plex libraries: {exc}")

    stored = library_mappings_service.load_library_mappings()
    mappings = library_mappings_service.sanitize_library_mappings(stored)
    mapping_lookup = {item["library"]: item for item in mappings}

    results: List[LibrarySectionInfo] = []
    for section in sections:
        name = str(getattr(section, "title", "") or "")
        key_value = getattr(section, "key", None)
        key_str = str(key_value) if key_value not in (None, "") else None
        section_type = getattr(section, "type", None) or None

        if not _is_supported_section(section_type):
            continue

        entry = {
            "name": name,
            "type": section_type,
            "key": key_str,
            "assetPath": None,
            "collectionsPath": None,
            "collectionAssetPaths": [],
        }
        mapping = mapping_lookup.get(name)
        if mapping:
            entry["assetPath"] = mapping.get("assetPath") or None
            entry["collectionsPath"] = mapping.get("collectionsPath") or None

        overrides: Dict[str, Dict[str, Any]] = {}
        stored_sections = mapping.get("collectionSections") if mapping else []
        if isinstance(stored_sections, list):
            for section in stored_sections:
                if not isinstance(section, dict):
                    continue
                raw_name = section.get("name")
                if not raw_name:
                    continue
                name_key = str(raw_name).strip()
                if not name_key:
                    continue
                key_norm = name_key.casefold()
                current = overrides.setdefault(
                    key_norm,
                    {
                        "name": name_key,
                        "collectionsPath": None,
                        "suggestionPaths": [],
                    },
                )
                path = library_mappings_service.normalize_path(
                    section.get("collectionsPath")
                )
                if path:
                    current["collectionsPath"] = path
                if not current.get("name"):
                    current["name"] = name_key

        if overrides:
            entry["collectionOverrides"] = [
                CollectionOverrideInfo(
                    name=value.get("name") or key,
                    collectionsPath=value.get("collectionsPath"),
                    suggestionPaths=sorted(
                        [
                            path
                            for path in value.get("suggestionPaths", [])
                            if path
                        ]
                    ),
                )
                for key, value in sorted(
                    overrides.items(), key=lambda item: item[0]
                )
            ]

        results.append(LibrarySectionInfo(**entry))

    results.sort(key=lambda item: (item.name.lower(), item.key or ""))

    return results
