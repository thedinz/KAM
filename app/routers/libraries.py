# app/routers/libraries.py
"""
Libraries router: only expose libraries explicitly mapped in the environment.

Env format (in your .env):
  LIBRARIES=Movies:/assets/Movies,Kids Movies:/assets/Kids Movies,TV Shows:/assets/TV Shows
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
import os

router = APIRouter()

# --- Load mappings -----------------------------------------------------------

def _parse_env_mappings(raw: str) -> Dict[str, str]:
    """
    Parse "Name:/path,Other Name:/other/path" into {"Name": "/path", ...}
    Ignores empty items; trims whitespace; last duplicate wins.
    """
    mapping: Dict[str, str] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            # Skip malformed entry gracefully
            continue
        name, path = part.split(":", 1)
        name = name.strip()
        path = path.strip()
        if name and path:
            mapping[name] = path
    return mapping


def _load_mappings() -> Dict[str, str]:
    """
    Prefer importing from app.config if available (e.g., LIBRARY_MAPPINGS),
    otherwise parse LIBRARIES from the environment directly.
    """
    # Try to use central config if present
    try:
        # Expected in your codebase: app/config.py defines LIBRARY_MAPPINGS: Dict[str, str]
        from ..config import LIBRARY_MAPPINGS  # type: ignore
        if isinstance(LIBRARY_MAPPINGS, dict) and LIBRARY_MAPPINGS:
            # Normalize keys/values
            return {str(k).strip(): str(v).strip() for k, v in LIBRARY_MAPPINGS.items() if str(k).strip() and str(v).strip()}
    except Exception:
        pass

    # Fallback: parse from ENV
    env_raw = os.environ.get("LIBRARIES", "")
    return _parse_env_mappings(env_raw)


LIBRARY_MAPPINGS: Dict[str, str] = _load_mappings()


def _ensure_any_mapped() -> None:
    if not LIBRARY_MAPPINGS:
        raise HTTPException(
            status_code=500,
            detail=(
                "No mapped libraries were found. Set LIBRARIES=Name:/path,... "
                "in your environment (or ensure config.LIBRARY_MAPPINGS is populated)."
            ),
        )


# --- Endpoints ---------------------------------------------------------------

@router.get("/api/libraries", response_model=List[str])
def get_libraries() -> List[str]:
    """
    Return only the names of libraries that are explicitly mapped.
    This prevents showing unsupported sections like Music, etc.
    """
    _ensure_any_mapped()
    return sorted(LIBRARY_MAPPINGS.keys())


@router.get("/api/libraries/map", response_model=Dict[str, str])
def get_library_map() -> Dict[str, str]:
    """
    Return the full name -> path map (useful for uploads).
    """
    _ensure_any_mapped()
    # Return a stable ordering for deterministic diffs/tests (optional)
    return {name: LIBRARY_MAPPINGS[name] for name in sorted(LIBRARY_MAPPINGS.keys())}


@router.get("/api/library-path")
def get_library_path(name: str = Query(..., description="Mapped library name")) -> Dict[str, str]:
    """
    Resolve a single library name to its mapped path.
    """
    _ensure_any_mapped()
    path = LIBRARY_MAPPINGS.get(name)
    if not path:
        raise HTTPException(status_code=404, detail=f"Library '{name}' is not mapped.")
    return {"name": name, "path": path}
