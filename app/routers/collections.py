from fastapi import APIRouter, Query
from math import ceil
from typing import Optional, List, Dict, Any, Tuple
from ..services.plex import get_plex
from ..services import folder_overrides
from ..services import plex_settings
from ..services.assets import sanitize_name
from .. import config

import os
from pathlib import Path
from urllib.parse import quote

router = APIRouter()

# Container paths (must match your docker-compose volume mounts)
ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT") or os.environ.get("ASSETS_ROOT") or ""
COLLECTIONS_ROOT = (
    os.environ.get("COLLECTIONS_ROOT")
    or (os.path.join(ASSETS_ROOT, "Collections") if ASSETS_ROOT else "")
)

# Try lots of common names (Kometa variants differ)
LOCAL_FILENAMES = (
    "poster.jpg", "poster.png", "poster.webp", "poster.jpeg",
    "folder.jpg", "cover.jpg", "cover.png", "cover.webp"
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

def _local_poster_for_title(title: str) -> Tuple[Path | None, str | None, str, bool]:
    """
    Find a local poster for this collection title.

    Returns: (path_on_disk, public_url_or_None, folder_used, folder_exists)
    """
    if not title or not COLLECTIONS_ROOT:
        return None, None, "", False

    base = Path(COLLECTIONS_ROOT)
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
            return p, _url_for_local(d1.name, p), d1.name, True

    # 2) exact sanitized
    d2 = base / sani_folder
    if d2.is_dir():
        found_folder = d2.name
        found_exists = True
        p = _first_existing_poster(d2)
        if p:
            return p, _url_for_local(d2.name, p), d2.name, True

    # 3) case-insensitive match (raw)
    d3 = _case_insensitive_dir(base, raw_folder)
    if d3:
        found_folder = d3.name
        found_exists = True
        p = _first_existing_poster(d3)
        if p:
            return p, _url_for_local(d3.name, p), d3.name, True

    # 4) case-insensitive match (sanitized)
    d4 = _case_insensitive_dir(base, sani_folder)
    if d4:
        found_folder = d4.name
        found_exists = True
        p = _first_existing_poster(d4)
        if p:
            return p, _url_for_local(d4.name, p), d4.name, True

    if found_exists:
        return None, None, found_folder, True

    return None, None, "", False

def _url_for_local(folder_name: str, file_path: Path) -> str:
    """
    Build the public URL for a local poster. Requires /assets to be mounted to ASSETS_ROOT in main.py.
    Adds cache-buster based on mtime so the UI flips immediately.
    """
    url = f"/assets/Collections/{quote(folder_name)}/{file_path.name}"
    try:
        ts = int(file_path.stat().st_mtime)
    except Exception:
        ts = 0
    if ts:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}t={ts}"
    return url


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
            for coll in sec.collections():
                rk = getattr(coll, "ratingKey", None)
                title = (getattr(coll, "title", None) or "").strip()

                # Plex art
                poster_plex = None
                if plex_url and plex_token:
                    poster_plex = f"{plex_url}/library/metadata/{rk}/thumb?X-Plex-Token={plex_token}"

                override_folder = folder_overrides.get_override("Collections", str(rk)) if rk else None

                poster_local = None
                folder_used = sanitize_name(title) if title else ""
                asset_ready = False
                folder_exists = False

                if override_folder:
                    folder_used = override_folder
                    asset_ready = True
                    folder_exists = True
                    if COLLECTIONS_ROOT:
                        override_path = Path(COLLECTIONS_ROOT) / override_folder
                        poster_path = _first_existing_poster(override_path) if override_path.is_dir() else None
                        if poster_path:
                            poster_local = _url_for_local(override_folder, poster_path)
                else:
                    _poster_path, poster_local, folder_used, folder_exists = _local_poster_for_title(title)
                    asset_ready = folder_exists

                item = {
                    "ratingKey": rk,
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
                        "collections_root": COLLECTIONS_ROOT,
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
