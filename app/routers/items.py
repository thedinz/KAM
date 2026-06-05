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
from ..services import resolve as resolve_service
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

def _section_info_by_name(lib_name: str) -> Tuple[str, Optional[str]]:
    r = _plex_sections_raw()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        data = r.json()
        dirs = (data.get("MediaContainer", {}) or {}).get("Directory") or []
        if isinstance(dirs, dict): dirs = [dirs]
        for d in dirs:
            if (d.get("title") or "").strip().lower() == (lib_name or "").strip().lower():
                key = d.get("key")
                if key:
                    return str(key), (d.get("type") or None)
        raise HTTPException(status_code=404, detail=f"Plex library not found: {lib_name}")
    # XML fallback
    root = ET.fromstring(r.text)
    for node in root.findall(".//Directory"):
        if (node.attrib.get("title") or "").strip().lower() == (lib_name or "").strip().lower():
            key = node.attrib.get("key")
            if key:
                return str(key), (node.attrib.get("type") or None)
    raise HTTPException(status_code=404, detail=f"Plex library not found: {lib_name}")


def _section_key_by_name(lib_name: str) -> str:
    key, _section_type = _section_info_by_name(lib_name)
    return key

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


def _plex_list_page(path: str, params: Optional[dict] = None) -> Tuple[List[Dict[str, Any]], int]:
    plex_url, plex_token = _require_plex()
    url = f"{plex_url}{path}"
    params = dict(params or {})
    params["X-Plex-Token"] = plex_token
    headers = {"Accept": "application/json", "X-Plex-Token": plex_token}
    r = requests.get(url, params=params, headers=headers, timeout=25)
    r.raise_for_status()
    if "application/json" in (r.headers.get("Content-Type") or "").lower():
        data = r.json()
        container = (data.get("MediaContainer", {}) or {})
        md = container.get("Metadata") or []
        if isinstance(md, dict):
            md = [md]
        total = _to_int(container.get("totalSize"))
        if total is None:
            total = _to_int(container.get("size"))
        if total is None:
            total = len(md)
        return md, total

    out: List[Dict[str, Any]] = []
    root = ET.fromstring(r.text)
    total = _to_int(root.attrib.get("totalSize")) or _to_int(root.attrib.get("size"))
    for node in root.findall(".//Video"):
        typ = node.attrib.get("type")
        if typ not in ("movie", "show"):
            continue
        out.append({
            "type": typ,
            "title": node.attrib.get("title"),
            "year": _to_int(node.attrib.get("year")),
            "ratingKey": node.attrib.get("ratingKey"),
            "thumb": node.attrib.get("thumb"),
            "addedAt": _to_int(node.attrib.get("addedAt")),
        })
    return out, (total if total is not None else len(out))

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


def _media_type_for_section(section_type: Optional[str]) -> Optional[int]:
    normalized = (section_type or "").strip().lower()
    if normalized == "movie":
        return 1
    if normalized == "show":
        return 2
    return None


def _plex_sort_param(sort_mode: Optional[str]) -> str:
    mode = (sort_mode or "title").strip().lower()
    if mode in {"newest", "newest_added", "added_desc", "added"}:
        return "addedAt:desc"
    return "titleSort:asc"


def _rows_from_metadata(md: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    return rows


def _excluded_rating_keys(library: str) -> set[str]:
    keys: set[str] = set()
    for entry in exclusions.list_exclusions():
        if entry.get("library") != library:
            continue
        key = str(entry.get("ratingKey") or "").strip()
        if key:
            keys.add(key)
    return keys


def _library_rows_page(
    library: str,
    page: int,
    page_size: int,
    query: Optional[str] = None,
    sort: Optional[str] = None,
) -> Optional[Tuple[List[Dict[str, Any]], int]]:
    section_key, section_type = _section_info_by_name(library)
    media_type = _media_type_for_section(section_type)
    if media_type is None:
        return None

    excluded_keys = _excluded_rating_keys(library)
    desired_end = max(1, page) * page_size
    desired_start = desired_end - page_size
    visible_rows: List[Dict[str, Any]] = []
    total_raw = 0
    offset = 0
    chunk_size = page_size if not excluded_keys else max(page_size, 200)
    path = (
        f"/library/sections/{section_key}/search"
        if query
        else f"/library/sections/{section_key}/all"
    )

    if not excluded_keys:
        params: Dict[str, Any] = {
            "type": media_type,
            "X-Plex-Container-Start": desired_start,
            "X-Plex-Container-Size": page_size,
            "sort": _plex_sort_param(sort),
        }
        if query:
            params["query"] = query
        md, total_raw = _plex_list_page(path, params)
        return _rows_from_metadata(md), total_raw

    while len(visible_rows) < desired_end:
        params: Dict[str, Any] = {
            "type": media_type,
            "X-Plex-Container-Start": offset,
            "X-Plex-Container-Size": chunk_size,
            "sort": _plex_sort_param(sort),
        }
        if query:
            params["query"] = query

        md, total_raw = _plex_list_page(path, params)
        if not md:
            break

        for row in _rows_from_metadata(md):
            if row["ratingKey"] in excluded_keys:
                continue
            visible_rows.append(row)

        offset += len(md)
        if offset >= total_raw:
            break

    total_count = max(0, total_raw - len(excluded_keys))
    return visible_rows[desired_start:desired_end], total_count

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


class _RequestDirectoryResolver:
    def __init__(self, library: str):
        self.library = library
        self.bases = list(dict.fromkeys(resolve_service._candidate_bases(library)))
        self.entries_by_base: Dict[str, List[str]] = {}

    def _entries(self, base: str) -> List[str]:
        if base in self.entries_by_base:
            return self.entries_by_base[base]
        try:
            entries = [
                d
                for d in os.listdir(base)
                if os.path.isdir(os.path.join(base, d))
            ]
        except Exception:
            entries = []
        self.entries_by_base[base] = entries
        return entries

    def resolve(self, folder_name: str) -> str:
        raw = (folder_name or "").strip()
        if not raw:
            raise FileNotFoundError("Empty folderName")

        for base in self.bases:
            if not os.path.isdir(base):
                continue
            exact = os.path.join(base, raw)
            if os.path.isdir(exact):
                return exact
            match = resolve_service._best_match(self._entries(base), raw)
            if match:
                return os.path.join(base, match)

        last_base = self.bases[0] if self.bases else os.path.join(resolve_service.ASSETS_ROOT, self.library)
        raise FileNotFoundError(f"Assets library not found: {last_base}")

def _try_existing_asset_folder(
    library: str,
    title: Optional[str],
    year: Optional[int],
    item_type: Optional[str] = None,
    resolver: Optional[_RequestDirectoryResolver] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Use the resolver to find an actual, existing Kometa folder.
    Movies with a Plex year resolve through 'Title (Year)' so the shared
    resolver can enforce safe year-aware matching without a bare-title guess.
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
            full = resolver.resolve(cand) if resolver else resolve_existing_dir_or_422(library, cand)
            return os.path.basename(full.rstrip(os.sep)), full
        except Exception:
            continue
    return None, None

def _resolve_override_folder(
    library: str,
    folder: Optional[str],
    resolver: Optional[_RequestDirectoryResolver] = None,
) -> Tuple[Optional[str], Optional[str]]:
    if not folder:
        return None, None
    try:
        full = resolver.resolve(folder) if resolver else resolve_existing_dir_or_422(library, folder)
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


def _enrich_item(
    library: str,
    it: Dict[str, Any],
    overrides_for_library: Dict[str, str],
    resolver: _RequestDirectoryResolver,
    *,
    include_posters: bool = True,
) -> Dict[str, Any]:
    override = overrides_for_library.get(it["ratingKey"])

    folder_name, folder_path = _resolve_override_folder(library, override, resolver)
    if not folder_path:
        auto_name, auto_path = _try_existing_asset_folder(
            library, it["title"], it["year"], it["type"], resolver
        )
        if auto_name:
            folder_name = folder_name or auto_name
        if auto_path:
            folder_path = folder_path or auto_path

    asset_ready = bool(folder_path)
    poster_local = None
    if include_posters:
        local_poster = _local_poster_path(folder_path)
        poster_local = _fileproxy_poster_url(local_poster) if local_poster else None
    poster_plex = _plex_poster_url(it["ratingKey"], it["thumb"]) if include_posters else None
    poster_proxy = _plex_poster_proxy_url(it["ratingKey"], it["thumb"]) if include_posters else None
    poster = poster_local or poster_proxy or poster_plex
    return {
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
    }

# ---------- API ----------

@router.get("/api/items")
def list_items(
    library: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=500),
    query: Optional[str] = Query(None),
    sort: str = Query("title"),
    not_ready_only: bool = Query(False, alias="not_ready_only"),
    include_counts: bool = Query(True, alias="include_counts"),
    counts_only: bool = Query(False, alias="counts_only"),
):
    """
    Prefer local poster.jpg via fileproxy if it actually exists; otherwise fall back to Plex thumb.
    """
    overrides_for_library = folder_overrides.get_library_overrides(library)
    resolver = _RequestDirectoryResolver(library)

    if counts_only:
        rows = _library_rows(library, query, sort)
        excluded_keys = _excluded_rating_keys(library)
        not_ready_count = 0
        total_count = 0
        for it in rows:
            if it["ratingKey"] in excluded_keys:
                continue
            total_count += 1
            enriched = _enrich_item(
                library,
                it,
                overrides_for_library,
                resolver,
                include_posters=False,
            )
            if not enriched.get("assetReady"):
                not_ready_count += 1
        return {
            "page": 1,
            "total_pages": 1,
            "total_count": total_count,
            "items": [],
            "not_ready_count": not_ready_count,
        }

    if not include_counts and not not_ready_only:
        try:
            page_result = _library_rows_page(library, page, page_size, query, sort)
        except HTTPException:
            raise
        except Exception:
            page_result = None
        if page_result is not None:
            page_rows_raw, total_count = page_result
            page_rows = [
                _enrich_item(library, it, overrides_for_library, resolver)
                for it in page_rows_raw
            ]
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            page = min(max(1, page), total_pages)
            return {
                "page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "items": page_rows,
                "not_ready_count": None,
            }

        rows = _library_rows(library, query, sort)
        excluded_keys = _excluded_rating_keys(library)
        visible_rows = [it for it in rows if it["ratingKey"] not in excluded_keys]
        total_count = len(visible_rows)
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page = min(max(1, page), total_pages)
        start = (page - 1) * page_size
        end = min(start + page_size, total_count)
        page_rows = [
            _enrich_item(library, it, overrides_for_library, resolver)
            for it in visible_rows[start:end]
        ]
        return {
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "items": page_rows,
            "not_ready_count": None,
        }

    rows = _library_rows(library, query, sort)
    excluded_keys = _excluded_rating_keys(library)

    enriched: List[Dict[str, Any]] = []
    not_ready_count = 0
    for it in rows:
        if it["ratingKey"] in excluded_keys:
            continue

        item = _enrich_item(library, it, overrides_for_library, resolver)
        if not item.get("assetReady"):
            not_ready_count += 1
        enriched.append(item)

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
