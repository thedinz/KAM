from fastapi import APIRouter, HTTPException, Query
from math import ceil
from typing import Optional, List, Dict, Any, Tuple
from ..services.plex import get_plex
from ..services import folder_overrides
from ..services import plex_settings
from ..services import library_mappings as library_mappings_service
from ..services.assets import sanitize_name

import os
from pathlib import Path
from urllib.parse import quote

router = APIRouter()

# Container paths (must match your docker-compose volume mounts)
ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT") or os.environ.get("ASSETS_ROOT") or ""

# Try lots of common names (Kometa variants differ)
LOCAL_FILENAMES = (
    "poster.jpg", "poster.png", "poster.webp", "poster.jpeg",
    "folder.jpg", "cover.jpg", "cover.png", "cover.webp"
)

BACKGROUND_FILENAMES = (
    "background.jpg", "background.png", "background.webp", "background.jpeg",
    "art.jpg", "art.png", "art.webp", "fanart.jpg", "fanart.png"
)

def _case_insensitive_dir(base: Path, want: str) -> Path | None:
    """
    Return an existing subdir in `base` whose name matches `want` case-insensitively.
    """
    if not want:
        return None
    want_l = want.lower()
    try:
        for child in base.iterdir():
            if child.is_dir() and child.name.lower() == want_l:
                return child
    except Exception:
        pass
    return None

def _first_existing_poster(dir_path: Path) -> Path | None:
    """Return the first existing poster file in the given directory."""
    for name in LOCAL_FILENAMES:
        p = dir_path / name
        if p.exists():
            return p
    return None


def _first_existing_background(dir_path: Path) -> Path | None:
    """Return the first existing background file in the given directory."""
    for name in BACKGROUND_FILENAMES:
        p = dir_path / name
        if p.exists():
            return p
    return None

def _collections_root_for_library(library: str | None) -> Path | None:
    path = library_mappings_service.get_collections_path(library)
    if not path:
        return None
    return Path(path)


def _local_poster_for_title(
    title: str, base: Path | None
) -> Tuple[Path | None, str | None, str, bool]:
    """
    Find a local poster for this collection title.

    Returns: (path_on_disk, public_url_or_None, folder_used, folder_exists)
    """
    if not title or not base:
        return None, None, "", False

    raw_folder = title
    sani_folder = sanitize_name(title)
    found_folder = ""
    found_exists = False

    # 1) exact raw
    d1 = base / raw_folder
    if d1.is_dir():
        found_folder = d1.name
        found_exists = True
        p = _first_existing_poster(d1)
        if p:
            return p, _url_for_local(base, d1.name, p), d1.name, True

    # 2) exact sanitized
    d2 = base / sani_folder
    if d2.is_dir():
        found_folder = d2.name
        found_exists = True
        p = _first_existing_poster(d2)
        if p:
            return p, _url_for_local(base, d2.name, p), d2.name, True

    # 3) case-insensitive match (raw)
    d3 = _case_insensitive_dir(base, raw_folder)
    if d3:
        found_folder = d3.name
        found_exists = True
        p = _first_existing_poster(d3)
        if p:
            return p, _url_for_local(base, d3.name, p), d3.name, True

    # 4) case-insensitive match (sanitized)
    d4 = _case_insensitive_dir(base, sani_folder)
    if d4:
        found_folder = d4.name
        found_exists = True
        p = _first_existing_poster(d4)
        if p:
            return p, _url_for_local(base, d4.name, p), d4.name, True

    if found_exists:
        return None, None, found_folder, True

    return None, None, "", False

def _url_for_local(base: Path, folder_name: str, file_path: Path) -> str:
    """
    Build the public URL for a local poster via the fileproxy.
    Adds cache-buster based on mtime so the UI flips immediately.
    """
    resolved = file_path
    try:
        resolved_base = base.resolve()
        resolved = file_path.resolve()
        resolved.relative_to(resolved_base)
    except Exception:
        try:
            resolved = file_path.resolve()
        except Exception:
            resolved = file_path
    url = f"/fileproxy?path={quote(str(resolved))}"
    try:
        ts = int(file_path.stat().st_mtime)
    except Exception:
        ts = 0
    if ts:
        url = f"{url}&t={ts}" if "?" in url else f"{url}?t={ts}"
    return url


@router.get("/collection", summary="Collection details")
def collection(
    library: str = Query(...),
    ratingKey: int = Query(...),
    sourceLibrary: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    plex = get_plex()
    try:
        item = plex.fetchItem(int(ratingKey))
    except Exception as exc:
        raise HTTPException(404, f"Collection {ratingKey} not found: {exc}")

    title = (getattr(item, "title", None) or "").strip() or "Untitled"
    year = getattr(item, "year", None)

    actual_library = sourceLibrary or source or getattr(item, "librarySectionTitle", None) or None
    collections_base = _collections_root_for_library(actual_library)

    poster_plex = None
    background_plex = None
    cfg = plex_settings.get_plex_config()
    if cfg.url and cfg.token:
        poster_plex = f"{cfg.url}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={cfg.token}"
        background_plex = f"{cfg.url}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={cfg.token}"

    override_folder = folder_overrides.get_override(actual_library or library, str(ratingKey))
    folder_name = override_folder or sanitize_name(title)
    folder_exists = False
    poster_local = None
    background_local = None

    if collections_base and override_folder:
        override_path = collections_base / override_folder
        if override_path.is_dir():
            folder_exists = True
            poster_path = _first_existing_poster(override_path)
            if poster_path:
                poster_local = _url_for_local(collections_base, override_path.name, poster_path)
            background_path = _first_existing_background(override_path)
            if background_path:
                background_local = _url_for_local(collections_base, override_path.name, background_path)
    elif collections_base:
        poster_path, poster_url, detected_folder, detected_exists = _local_poster_for_title(
            title,
            collections_base,
        )
        if detected_folder:
            folder_name = detected_folder
        folder_exists = detected_exists
        if poster_url:
            poster_local = poster_url
        elif poster_path and folder_name:
            poster_local = _url_for_local(collections_base, folder_name, poster_path)

    if collections_base and folder_name:
        folder_path = collections_base / folder_name
        if folder_path.is_dir():
            folder_exists = True
            if not poster_local:
                poster_path = _first_existing_poster(folder_path)
                if poster_path:
                    poster_local = _url_for_local(collections_base, folder_path.name, poster_path)
            background_path = _first_existing_background(folder_path)
            if background_path:
                background_local = _url_for_local(collections_base, folder_path.name, background_path)

    poster_exists = bool(poster_local)
    background_exists = bool(background_local)

    return {
        "library": library,
        "sourceLibrary": actual_library,
        "title": title,
        "year": year,
        "ratingKey": int(ratingKey),
        "folderName": folder_name or "",
        "folderExists": folder_exists,
        "posterExists": poster_exists,
        "backgroundExists": background_exists,
        "posterUrl": poster_local,
        "posterUrlLocal": poster_local,
        "posterUrlPlex": poster_plex,
        "backgroundUrl": background_local,
        "backgroundUrlLocal": background_local,
        "backgroundUrlPlex": background_plex,
    }


@router.get("/api/collection", summary="Collection details (alias)")
def collection_alias(
    library: str = Query(...),
    ratingKey: int = Query(...),
    sourceLibrary: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    return collection(
        library=library,
        ratingKey=ratingKey,
        sourceLibrary=sourceLibrary,
        source=source,
    )


@router.get("/collections", summary="Collections")
def collections(
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    not_ready_only: bool = Query(False, alias="not_ready_only"),
):
    plex = get_plex()
    cfg = plex_settings.get_plex_config()
    plex_url = cfg.url
    plex_token = cfg.token
    rows: List[Dict[str, Any]] = []

    # Gather collections from all libraries
    for sec in plex.library.sections():
        try:
            name = str(getattr(sec, "title", "") or "")
            for coll in sec.collections():
                rk = getattr(coll, "ratingKey", None)
                title = (getattr(coll, "title", None) or "").strip()

                # Plex art
                poster_plex = None
                if plex_url and plex_token:
                    poster_plex = f"{plex_url}/library/metadata/{rk}/thumb?X-Plex-Token={plex_token}"

                library_name = name
                collections_base = _collections_root_for_library(library_name)
                override_folder = (
                    folder_overrides.get_override(library_name, str(rk)) if rk else None
                )

                poster_local = None
                folder_used = sanitize_name(title) if title else ""
                asset_ready = False
                folder_exists = False

                if override_folder:
                    folder_used = override_folder
                    asset_ready = True
                    folder_exists = True
                    if collections_base:
                        override_path = collections_base / override_folder
                        poster_path = (
                            _first_existing_poster(override_path)
                            if override_path.is_dir()
                            else None
                        )
                        if poster_path:
                            poster_local = _url_for_local(collections_base, override_folder, poster_path)
                else:
                    (
                        _poster_path,
                        poster_local,
                        folder_used,
                        folder_exists,
                    ) = _local_poster_for_title(title, collections_base)
                    asset_ready = folder_exists

                item = {
                    "ratingKey": rk,
                    "library": library_name,
                    "title": title,
                    "year": None,
                    "folderName": folder_used or (sanitize_name(title) if title else ""),
                    "assetReady": asset_ready,
                    # ✅ prefer local for the primary image
                    "posterUrl": poster_local or poster_plex,
                    # also expose both explicitly
                    "posterUrlLocal": poster_local,
                    "posterUrlPlex": poster_plex,
                }

                # Optional debug breadcrumb you can see in JSON while testing
                # Remove this once you're happy:
                if poster_local is None:
                    item["_debug"] = {
                        "collections_root": str(collections_base) if collections_base else None,
                        "tried_titles": [title, sanitize_name(title)],
                        "folder_used": folder_used,
                        "asset_ready": folder_exists,
                        "assets_root": ASSETS_ROOT,
                    }

                rows.append(item)

        except Exception:
            # tolerate sections that error (permissions, etc.)
            continue

    # De-duplicate by title (first seen wins)
    dedup: Dict[str, Dict[str, Any]] = {}
    for it in rows:
        name = (it.get("title") or "").strip()
        if name and name not in dedup:
            dedup[name] = it
    items = list(dedup.values())

    # Filter
    if query:
        q = query.lower()
        items = [i for i in items if q in (i.get("title") or "").lower()]

    not_ready_count = sum(1 for i in items if not i.get("assetReady"))

    if not_ready_only:
        items = [i for i in items if not i.get("assetReady")]

    # Paginate
    total = len(items)
    pages = max(1, ceil(total / page_size))
    page = min(page, pages)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "library": "Collections",
        "page": page,
        "page_size": page_size,
        "total_count": total,
        "total_pages": pages,
        "items": items[start:end],
        "not_ready_count": not_ready_count,
    }
