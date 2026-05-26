# app/routers/items.py
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional, Tuple
import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

from ..services import exclusions, folder_overrides
from ..services import plex_settings
from ..services.plex_assets import build_plex_asset_url, build_plex_proxy_url
from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

# ---------- Plex helpers ----------

def _require_plex() -> Tuple[str, str]:
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")
    return cfg.url, cfg.token

def _plex_sections_raw():
    plex_url, plex_token = _require_plex()
    url = f"{plex_url}/library/sections"
    headers = {"Accept": "application/json", "X-Plex-Token": plex_token}
    r = requests.get(
        url,
        headers=headers,
        params={"X-Plex-Token": plex_token},
        timeout=20,
    )
    r.raise_for_status()
    return r

def _section_key_by_name(lib_name: str) -> str:
    r = _plex_sections_raw()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        data = r.json()
        dirs = (data.get("MediaContainer", {}) or {}).get("Directory") or []
        if isinstance(dirs, dict): dirs = [dirs]
        for d in dirs:
            if (d.get("title") or "").strip().lower() == (lib_name or "").strip().lower():
                key = d.get("key")
                if key: return str(key)
        raise HTTPException(status_code=404, detail=f"Plex library not found: {lib_name}")
    # XML fallback
    root = ET.fromstring(r.text)
    for node in root.findall(".//Directory"):
        if (node.attrib.get("title") or "").strip().lower() == (lib_name or "").strip().lower():
            key = node.attrib.get("key")
            if key: return str(key)
    raise HTTPException(status_code=404, detail=f"Plex library not found: {lib_name}")

def _plex_list(path: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
    plex_url, plex_token = _require_plex()
    url = f"{plex_url}{path}"
    params = dict(params or {})
    params["X-Plex-Token"] = plex_token
    headers = {"Accept": "application/json", "X-Plex-Token": plex_token}
    r = requests.get(url, params=params, headers=headers, timeout=25)
    r.raise_for_status()
    if (r.headers.get("Content-Type") or "").lower().startswith("application/json"):
        data = r.json()
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        if isinstance(md, dict): md = [md]
        return md
    # XML fallback (movies and shows are <Video>)
    out: List[Dict[str, Any]] = []
    root = ET.fromstring(r.text)
    for node in root.findall(".//Video"):
        typ = node.attrib.get("type")
        if typ not in ("movie", "show"): continue
        out.append({
            "type": typ,
            "title": node.attrib.get("title"),
            "year": _to_int(node.attrib.get("year")),
            "ratingKey": node.attrib.get("ratingKey"),
            "thumb": node.attrib.get("thumb"),
            "addedAt": _to_int(node.attrib.get("addedAt")),
        })
    return out

def _to_int(x) -> Optional[int]:
    try: return int(str(x))
    except Exception: return None

def _sort_item_rows(rows: List[Dict[str, Any]], sort_mode: Optional[str] = None) -> None:
    mode = sort_mode if isinstance(sort_mode, str) else "title"
    mode = mode.strip().lower()
    if mode in {"newest", "newest_added", "added_desc", "added"}:
        rows.sort(
            key=lambda x: (
                x.get("addedAt") is None,
                -(_to_int(x.get("addedAt")) or _to_int(x.get("year")) or 0),
                (x.get("title") or "").lower(),
            )
        )
        return

    rows.sort(key=lambda x: (x.get("title") or "").lower())

def _library_rows(
    library: str,
    query: Optional[str] = None,
    sort: Optional[str] = None,
) -> List[Dict[str, Any]]:
    section_key = _section_key_by_name(library)

    if query:
        movies = _plex_list(f"/library/sections/{section_key}/search", {"type": 1, "query": query})
        shows  = _plex_list(f"/library/sections/{section_key}/search", {"type": 2, "query": query})
        md = movies + shows
    else:
        movies = _plex_list(f"/library/sections/{section_key}/all", {"type": 1})
        shows  = _plex_list(f"/library/sections/{section_key}/all", {"type": 2})
        md = movies + shows

    rows: List[Dict[str, Any]] = []
    for it in md:
        rows.append({
            "title": (it.get("title") or "").strip(),
            "year": _to_int(it.get("year")),
            "ratingKey": str(it.get("ratingKey") or "").strip(),
            "type": (it.get("type") or "").strip(),
            "thumb": it.get("thumb"),
            "addedAt": _to_int(it.get("addedAt")),
        })
    _sort_item_rows(rows, sort)
    return rows

# ---------- Local folder & poster helpers ----------

def _try_existing_asset_folder(
    library: str,
    title: Optional[str],
    year: Optional[int],
    item_type: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Use your resolver to find an actual, existing Kometa folder.
    Movies with a Plex year only try 'Title (Year)' automatically. If that
    cannot be resolved, leave them unmatched instead of guessing from 'Title'.
    """
    if not title:
        return None, None
    candidates: List[str] = []
    if year:
        candidates.append(f"{title} ({year})")
    if not (year and (item_type or "").casefold() == "movie"):
        candidates.append(title)
    candidates = list(dict.fromkeys(candidates))
    for cand in candidates:
        try:
            full = resolve_existing_dir_or_422(library, cand)
            return os.path.basename(full.rstrip(os.sep)), full
        except Exception:
            continue
    return None, None

def _resolve_override_folder(library: str, folder: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not folder:
        return None, None
    try:
        full = resolve_existing_dir_or_422(library, folder)
    except Exception:
        return folder, None
    name = os.path.basename(full.rstrip(os.sep))
    return name, full

def _local_poster_path(folder_path: Optional[str]) -> Optional[str]:
    if not folder_path:
        return None
    poster_path = os.path.join(folder_path, "poster.jpg")
    try:
        if os.path.isfile(poster_path) and os.path.getsize(poster_path) > 0:
            return poster_path
    except Exception:
        return None
    return None

def _fileproxy_poster_url(poster_path: str) -> str:
    url = f"/fileproxy?path={quote(poster_path, safe='')}"
    try:
        ts = int(os.path.getmtime(poster_path))
    except Exception:
        ts = 0
    if ts:
        url = f"{url}&t={ts}" if "?" in url else f"{url}?t={ts}"
    return url

def _plex_poster_url(rating_key: Optional[str], thumb: Optional[str]) -> Optional[str]:
    return build_plex_asset_url(thumb, rating_key, "thumb")


def _plex_poster_proxy_url(rating_key: Optional[str], thumb: Optional[str]) -> Optional[str]:
    return build_plex_proxy_url(thumb, rating_key, "thumb")

# ---------- API ----------

@router.get("/api/items")
def list_items(
    library: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=500),
    query: Optional[str] = Query(None),
    sort: str = Query("title"),
    not_ready_only: bool = Query(False, alias="not_ready_only"),
):
    """
    Prefer local poster.jpg via fileproxy if it actually exists; otherwise fall back to Plex thumb.
    """
    rows = _library_rows(library, query, sort)
    overrides_for_library = folder_overrides.get_library_overrides(library)

    enriched: List[Dict[str, Any]] = []
    not_ready_count = 0
    for it in rows:
        if exclusions.is_excluded(library, it["ratingKey"]):
            continue

        override = overrides_for_library.get(it["ratingKey"])

        folder_name, folder_path = _resolve_override_folder(library, override)
        if not folder_path:
            auto_name, auto_path = _try_existing_asset_folder(
                library, it["title"], it["year"], it["type"]
            )
            if auto_name:
                folder_name = folder_name or auto_name
            if auto_path:
                folder_path = folder_path or auto_path

        asset_ready = bool(folder_path)
        if not asset_ready:
            not_ready_count += 1

        local_poster = _local_poster_path(folder_path)
        poster_local = _fileproxy_poster_url(local_poster) if local_poster else None
        poster_plex = _plex_poster_url(it["ratingKey"], it["thumb"])
        poster_proxy = _plex_poster_proxy_url(it["ratingKey"], it["thumb"])
        poster = poster_local or poster_proxy or poster_plex
        enriched.append({
            "ratingKey": it["ratingKey"],
            "title": it["title"],
            "year": it["year"],
            "type": it["type"],
            "addedAt": it.get("addedAt"),
            "folder": folder_name,
            "folderName": folder_name,
            "assetReady": asset_ready,
            "posterUrl": poster,
            "posterUrlLocal": poster_local,
            "posterUrlPlex": poster_plex,
        })

    if not_ready_only:
        filtered_rows = [it for it in enriched if not it.get("assetReady")]
    else:
        filtered_rows = enriched

    total_count = len(filtered_rows)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    end = min(start + page_size, total_count)
    page_rows = filtered_rows[start:end]

    return {
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "items": page_rows,
        "not_ready_count": not_ready_count,
    }


@router.get("/api/items/mapping-source")
def list_items_for_mapping_scan(
    library: str = Query(...),
    query: Optional[str] = Query(None),
):
    """Return lightweight Plex item metadata for large mapping scans."""

    rows = _library_rows(library, query)
    overrides_for_library = folder_overrides.get_library_overrides(library)
    items: List[Dict[str, Any]] = []

    for it in rows:
        rating_key = it["ratingKey"]
        if exclusions.is_excluded(library, rating_key):
            continue

        override = overrides_for_library.get(rating_key)
        items.append({
            "ratingKey": rating_key,
            "title": it["title"],
            "year": it["year"],
            "type": it["type"],
            "folder": override or "",
            "folderName": override or "",
            "assetReady": bool(override),
        })

    return {
        "library": library,
        "total_count": len(items),
        "items": items,
    }
