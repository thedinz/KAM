# app/routers/libraries.py
"""
Libraries router: only expose libraries explicitly mapped in the environment.

Env format (in your .env):
  LIBRARIES=Movies:/assets/Movies,Kids Movies:/assets/Kids Movies,TV Shows:/assets/TV Shows
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Optional

from ..services import library_mappings as library_mappings_service

router = APIRouter()

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


class LibrarySectionInfo(BaseModel):
    name: str
    type: Optional[str] = None
    key: Optional[str] = None
    assetPath: Optional[str] = None
    collectionsPath: Optional[str] = None


@router.get("/api/settings/libraries", response_model=List[LibrarySectionInfo])
def list_available_libraries() -> List[LibrarySectionInfo]:
    """Return Plex libraries alongside any stored mapping metadata."""
    from ..services import (
        library_mappings as library_mappings_service,
        plex_settings,
    )
    from ..services.plex import get_plex

    # Ensure Plex credentials are available (raises HTTPException when invalid)
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
        entry = {
            "name": name,
            "type": getattr(section, "type", None) or None,
            "key": key_str,
            "assetPath": None,
            "collectionsPath": None,
        }
        mapping = mapping_lookup.get(name)
        if mapping:
            entry["assetPath"] = mapping.get("assetPath") or None
            entry["collectionsPath"] = mapping.get("collectionsPath") or None
        results.append(LibrarySectionInfo(**entry))

    return results
