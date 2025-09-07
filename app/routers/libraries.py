# app/routers/libraries.py
from __future__ import annotations

from typing import List, Literal, Dict, Tuple
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Local config: expects PLEX_URL, PLEX_TOKEN, LIBRARY_MAPPINGS, COLLECTIONS_ROOT
from app import config  # assumes app/config.py defines the env parsing

# If you already have a shared Plex helper, feel free to swap this out.
try:
    from plexapi.server import PlexServer
except Exception as e:  # pragma: no cover
    PlexServer = None  # type: ignore

router = APIRouter(tags=["libraries"])


class LibraryObj(BaseModel):
    name: str
    assets_path: str | None = None


def _connect_plex():
    """Connect to Plex using env/config. Raises a clear 500 if misconfigured."""
    if PlexServer is None:
        raise HTTPException(500, "plexapi not available in environment")
    baseurl = getattr(config, "PLEX_URL", None) or os.getenv("PLEX_URL")
    token = getattr(config, "PLEX_TOKEN", None) or os.getenv("PLEX_TOKEN")
    if not baseurl or not token:
        raise HTTPException(500, "PLEX_URL or PLEX_TOKEN not configured")
    try:
        return PlexServer(baseurl, token)
    except Exception as exc:
        raise HTTPException(500, f"Failed to connect to Plex: {exc}")


def _parse_library_mappings() -> Dict[str, str]:
    """
    Returns mapping of Library Name -> assets path (container path), from config.
    Example: {"Movies": "/assets/Movies", "Kids Movies": "/assets/Kids Movies"}
    Any 'Collections' entry is filtered here; we manage Collections via env.
    """
    mapping = {}
    # Preferred: config.LIBRARY_MAPPINGS produced by your env parsing
    libmap = getattr(config, "LIBRARY_MAPPINGS", None)
    if isinstance(libmap, dict):
        mapping = {str(k): str(v) for k, v in libmap.items()}
    else:
        # Fallback: parse LIBRARIES env like "Movies:/assets/Movies,Kids:/assets/Kids"
        raw = os.getenv("LIBRARIES", "")
        parts: List[Tuple[str, str]] = []
        for chunk in [c.strip() for c in raw.split(",") if c.strip()]:
            if ":" in chunk:
                name, path = chunk.split(":", 1)
                parts.append((name.strip(), path.strip()))
        mapping = {k: v for k, v in parts}

    # Filter out any 'Collections' key here; we’ll inject via COLLECTIONS_ROOT
    mapping = {k: v for k, v in mapping.items() if k.lower() != "collections"}
    return mapping


def _collections_entry_if_configured() -> LibraryObj | None:
    """
    If COLLECTIONS_ROOT is set, return a LibraryObj for Collections.
    """
    coll_root = getattr(config, "COLLECTIONS_ROOT", None) or os.getenv("COLLECTIONS_ROOT")
    if coll_root:
        return LibraryObj(name="Collections", assets_path=str(coll_root))
    return None


@router.get("/libraries", response_model=List[LibraryObj] | List[str])
def get_libraries(
    format: Literal["objects", "names"] = Query("objects", description="Return 'objects' or 'names'")
):
    """
    Returns libraries from Plex, enriched with container asset paths from LIBRARIES mapping.
    Auto-includes a 'Collections' entry when COLLECTIONS_ROOT is set, without requiring
    it in LIBRARIES (and de-duplicates if present there).
    """
    # 1) Load Plex section names (for discovery)
    try:
        plex = _connect_plex()
        plex_sections = sorted([s.title for s in plex.library.sections()])
    except Exception as exc:  # FALLBACK_MAPPING_ONLY
        plex_sections = []  # degrade to mapping-only

    # 2) Map specific libraries to asset paths
    libmap = _parse_library_mappings()

    # 3) Build objects list aligned to Plex sections (keep only names that exist in Plex)
    objs: List[LibraryObj] = []
    plex_set = {n.lower() for n in plex_sections}
    for name, path in libmap.items():
        if name.lower() in plex_set:
            objs.append(LibraryObj(name=name, assets_path=path))

    # 4) If COLLECTIONS_ROOT is configured, inject 'Collections' (dedupe)
    coll = _collections_entry_if_configured()
    if coll:
        if all(o.name.lower() != "collections" for o in objs):
            objs.append(coll)

    
    # 4.5) If Plex discovery failed, return just the provided mappings (plus Collections if set)
    if not plex_sections:
        objs = [LibraryObj(name=n, assets_path=p) for n,p in libmap.items()]
        coll = _collections_entry_if_configured()
        if coll and all(o.name.lower() != "collections" for o in objs):
            objs.append(coll)
        if format == "names":
            return [o.name for o in objs]
        return objs
# 5) If no mappings provided at all, return just names discovered from Plex (+ Collections)
    if not objs:
        names = list(plex_sections)
        if coll and "collections" not in (n.lower() for n in names):
            names.append("Collections")
        names_sorted = sorted(names)

        if format == "names":
            return names_sorted

        # Convert to objects with assets_path=None (except Collections gets its path)
        out_objs = [LibraryObj(name=n, assets_path=None) for n in names_sorted]
        if coll:
            # set the assets_path only for Collections
            for o in out_objs:
                if o.name.lower() == "collections":
                    o.assets_path = coll.assets_path
        return out_objs

    # 6) We have explicit mappings. Return in requested format.
    if format == "names":
        return [o.name for o in objs]

    return objs
