# app/routers/items.py
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

from ..services import folder_overrides
from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

PLEX_URL    = os.environ.get("PLEX_URL", "").rstrip("/")
PLEX_TOKEN  = os.environ.get("PLEX_TOKEN", "")
ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

# ---------- Plex helpers ----------

def _require_plex():
    if not PLEX_URL or not PLEX_TOKEN:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

def _plex_sections_raw():
    _require_plex()
    url = f"{PLEX_URL}/library/sections"
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
    r = requests.get(url, headers=headers, params={"X-Plex-Token": PLEX_TOKEN}, timeout=20)
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
    _require_plex()
    url = f"{PLEX_URL}{path}"
    params = dict(params or {})
    params["X-Plex-Token"] = PLEX_TOKEN
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
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
        })
    return out

def _to_int(x) -> Optional[int]:
    try: return int(str(x))
    except Exception: return None

# ---------- Local folder & poster helpers ----------

def _try_existing_asset_folder(library: str, title: Optional[str], year: Optional[int]) -> Optional[str]:
    """
    Use your resolver to find an actual, existing Kometa folder.
    Try 'Title (Year)' first, then 'Title'. Never create anything.
    """
    if not title:
        return None
    candidates: List[str] = []
    if year: candidates.append(f"{title} ({year})")
    candidates.append(title)
    for cand in candidates:
        try:
            full = resolve_existing_dir_or_422(library, cand)
            return os.path.basename(full.rstrip(os.sep))
        except Exception:
            continue
    return None

def _local_poster_exists(library: str, folder: str) -> bool:
    p = os.path.join(ASSETS_ROOT, library, folder, "poster.jpg")
    try:
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except Exception:
        return False

def _fileproxy_poster_url(library: str, folder: str) -> str:
    # Correct route: /fileproxy (no /api prefix)
    lib_enc = quote(library, safe="")
    fol_enc = quote(folder,  safe="")
    return f"/fileproxy?path=/assets/{lib_enc}/{fol_enc}/poster.jpg&t=0"

def _plex_poster_url(rating_key: Optional[str], thumb: Optional[str]) -> str:
    path = thumb or (f"/library/metadata/{rating_key}/thumb" if rating_key else None)
    if not path:
        return "/fallback.png"
    return f"{PLEX_URL}{path}?X-Plex-Token={PLEX_TOKEN}"

# ---------- API ----------

@router.get("/api/items")
def list_items(
    library: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=500),
    query: Optional[str] = Query(None),
):
    """
    Prefer local poster.jpg via fileproxy if it actually exists; otherwise fall back to Plex thumb.
    """
    section_key = _section_key_by_name(library)

    if query:
        movies = _plex_list(f"/library/sections/{section_key}/search", {"type": 1, "query": query})
        shows  = _plex_list(f"/library/sections/{section_key}/search", {"type": 2, "query": query})
        md = movies + shows
    else:
        movies = _plex_list(f"/library/sections/{section_key}/all", {"type": 1})
        shows  = _plex_list(f"/library/sections/{section_key}/all", {"type": 2})
        md = movies + shows

    # Normalize + sort
    rows: List[Dict[str, Any]] = []
    for it in md:
        rows.append({
            "title": (it.get("title") or "").strip(),
            "year": _to_int(it.get("year")),
            "ratingKey": str(it.get("ratingKey") or "").strip(),
            "type": (it.get("type") or "").strip(),
            "thumb": it.get("thumb"),
        })
    rows.sort(key=lambda x: x["title"].lower())

    total_count = len(rows)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    end = min(start + page_size, total_count)
    page_rows = rows[start:end]

    out: List[Dict[str, Any]] = []
    for it in page_rows:
        override = folder_overrides.get_override(library, it["ratingKey"])
        folder = override or _try_existing_asset_folder(library, it["title"], it["year"])
        asset_ready = True if override else bool(folder)
        if folder and _local_poster_exists(library, folder):
            poster = _fileproxy_poster_url(library, folder)   # <-- /fileproxy now
        else:
            poster = _plex_poster_url(it["ratingKey"], it["thumb"])
        out.append({
            "ratingKey": it["ratingKey"],
            "title": it["title"],
            "year": it["year"],
            "type": it["type"],
            "folder": folder,
            "folderName": folder,
            "assetReady": asset_ready,
            "posterUrl": poster,
        })

    return {
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "items": out,
    }
