from fastapi import APIRouter, HTTPException, Query
from math import ceil
from typing import Optional, List, Dict, Any, Tuple
from ..services.plex import get_plex
from ..services import exclusions, folder_overrides
from ..services import plex_settings
from ..services.plex_assets import build_plex_proxy_url
from ..services import library_mappings as library_mappings_service
from ..services.assets import sanitize_name
from ..services.resolve import find_existing_dir_in_base
from ..services.sanitize import kometa_sanitize_folder

import os
import re
from pathlib import Path
from urllib.parse import quote

router = APIRouter()

# Container paths (must match your docker-compose/Unraid volume mounts)
ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT") or os.environ.get("ASSETS_ROOT")
if not ASSETS_ROOT:
    collections_root = os.environ.get("COLLECTIONS_ROOT")
    ASSETS_ROOT = os.path.dirname(collections_root) if collections_root else "/assets"

# Try lots of common names (Kometa variants differ)
LOCAL_FILENAMES = (
    "poster.jpg", "poster.png", "poster.webp", "poster.jpeg",
    "folder.jpg", "cover.jpg", "cover.png", "cover.webp"
)

BACKGROUND_FILENAMES = (
    "background.jpg", "background.png", "background.webp", "background.jpeg",
    "art.jpg", "art.png", "art.webp", "fanart.jpg", "fanart.png"
)


def _candidate_exclusion_libraries(library: str | None) -> List[str]:
    """Yield possible library names for exclusion lookups."""

    candidates: List[str] = []
    primary = (library or "").strip()

    if primary:
        candidates.append(primary)

    # ``Collections`` used to be stored as the library name when excluding
    # collection items from the Collections view. Continue checking that alias
    # for backwards compatibility with existing exclusions.
    if "Collections" not in candidates:
        candidates.append("Collections")

    # Preserve the original order for deterministic behaviour while removing
    # duplicates.
    deduped: List[str] = []
    for name in candidates:
        if name and name not in deduped:
            deduped.append(name)

    return deduped


def _is_collection_excluded(library: str | None, rating_key: Any) -> bool:
    """Return ``True`` if the given collection should be excluded."""

    if rating_key in (None, ""):
        return False

    rating_text = str(rating_key).strip()
    if not rating_text:
        return False

    for candidate in _candidate_exclusion_libraries(library):
        if exclusions.is_excluded(candidate, rating_text):
            return True

    return False

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
    """Return the best-known collections root for *library*."""

    library = (library or "").strip() or None

    direct = library_mappings_service.get_collections_path(library)
    direct_path = Path(direct) if direct else None

    base_candidates: List[Path] = []
    if direct_path:
        base_candidates.append(direct_path)

    env_root = os.environ.get("COLLECTIONS_ROOT")
    if env_root:
        base_candidates.append(Path(env_root))

    global_root = library_mappings_service.get_collections_path(None)
    if global_root:
        candidate = Path(global_root)
        if candidate not in base_candidates:
            base_candidates.append(candidate)

    for base in base_candidates:
        if library:
            search_names = {
                library,
                sanitize_name(library),
                kometa_sanitize_folder(library),
            }
            for name in filter(None, search_names):
                candidate = base / name
                if candidate.is_dir():
                    return candidate

        if base.is_dir():
            return base

    if direct_path:
        return direct_path

    if library:
        fallback_asset = library_mappings_service.get_asset_path(library)
        if fallback_asset:
            return Path(fallback_asset)

    return None


def _strip_year_suffix(name: str) -> str:
    """Return *name* without a trailing ``(YYYY)`` suffix."""

    if not name:
        return ""

    stripped = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip()
    return stripped


def _strip_collection_suffix(name: str) -> str:
    """Return *name* without a trailing "collection" style suffix."""

    if not name:
        return ""

    stripped = re.sub(r"\s+(collection|collections|collection set)\s*$", "", name, flags=re.IGNORECASE).strip()
    return stripped


def _local_poster_for_title(
    title: str, base: Path | None
) -> Tuple[Path | None, str | None, str, bool]:
    """Return poster info for *title* within the given collections base."""

    if not title or not base:
        return None, None, "", False

    candidates: List[str] = []
    base_candidates = (
        title,
        sanitize_name(title),
        _strip_year_suffix(title),
        _strip_year_suffix(sanitize_name(title)),
    )

    for candidate in base_candidates:
        candidate = (candidate or "").strip()
        if not candidate:
            continue
        if candidate not in candidates:
            candidates.append(candidate)

    # Collections commonly have folders without the "Collection" suffix.
    for candidate in list(candidates):
        stripped = _strip_collection_suffix(candidate)
        if stripped and stripped not in candidates:
            candidates.append(stripped)

    resolved: str | None = None
    for candidate in candidates:
        resolved = find_existing_dir_in_base(str(base), candidate)
        if resolved:
            break

    if not resolved:
        return None, None, "", False

    folder_path = Path(resolved)
    folder_name = folder_path.name
    poster_path = _first_existing_poster(folder_path)

    if poster_path:
        poster_url = _url_for_local(base, folder_name, poster_path)
    else:
        poster_url = None

    return poster_path, poster_url, folder_name, True

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
    exclusion_library = actual_library or library
    collections_base = _collections_root_for_library(actual_library)

    poster_plex = None
    background_plex = None
    poster_proxy = None
    background_proxy = None
    cfg = plex_settings.get_plex_config()
    if cfg.url and cfg.token:
        poster_plex = f"{cfg.url}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={cfg.token}"
        background_plex = f"{cfg.url}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={cfg.token}"
        poster_proxy = build_plex_proxy_url(None, str(ratingKey), "thumb")
        background_proxy = build_plex_proxy_url(None, str(ratingKey), "art")

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
        "posterUrl": poster_local or poster_proxy,
        "posterUrlLocal": poster_local,
        "posterUrlPlex": poster_plex,
        "backgroundUrl": background_local or background_proxy,
        "backgroundUrlLocal": background_local,
        "backgroundUrlPlex": background_plex,
        "excluded": _is_collection_excluded(exclusion_library, ratingKey),
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
    library: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    not_ready_only: bool = Query(False, alias="not_ready_only"),
):
    plex = get_plex()
    selected_library = library.strip() if isinstance(library, str) and library.strip() else None
    cfg = plex_settings.get_plex_config()
    plex_url = cfg.url
    plex_token = cfg.token
    rows: List[Dict[str, Any]] = []

    # Gather collections from all libraries
    for sec in plex.library.sections():
        try:
            name = str(getattr(sec, "title", "") or "")
            if selected_library and name.casefold() != selected_library.casefold():
                continue
            for coll in sec.collections():
                rk = getattr(coll, "ratingKey", None)
                title = (getattr(coll, "title", None) or "").strip()

                # Plex art
                poster_plex = None
                poster_proxy = None
                if plex_url and plex_token:
                    poster_plex = f"{plex_url}/library/metadata/{rk}/thumb?X-Plex-Token={plex_token}"
                    poster_proxy = build_plex_proxy_url(None, str(rk), "thumb")

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

                if _is_collection_excluded(library_name, rk):
                    # Skip collections that have been explicitly excluded.
                    continue

                item = {
                    "ratingKey": rk,
                    "library": library_name,
                    "type": "collection",
                    "title": title,
                    "year": None,
                    "folderName": folder_used or (sanitize_name(title) if title else ""),
                    "assetReady": asset_ready,
                    # ✅ prefer local for the primary image
                    "posterUrl": poster_local or poster_proxy or poster_plex,
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
        "library": selected_library or "Collections",
        "page": page,
        "page_size": page_size,
        "total_count": total,
        "total_pages": pages,
        "items": items[start:end],
        "not_ready_count": not_ready_count,
    }
