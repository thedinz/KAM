# app/routers/tv.py
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

from ..services import folder_overrides
from ..services.resolve import resolve_existing_dir_or_422
from ..services.sanitize import kometa_sanitize_folder

router = APIRouter()

PLEX_URL    = os.environ.get("PLEX_URL", "").rstrip("/")
PLEX_TOKEN  = os.environ.get("PLEX_TOKEN", "")
ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

def _require_plex():
    if not PLEX_URL or not PLEX_TOKEN:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

def _plex_json_or_xml(path: str):
    _require_plex()
    url = f"{PLEX_URL}{path}"
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
    r = requests.get(url, headers=headers, params={"X-Plex-Token": PLEX_TOKEN}, timeout=25)
    r.raise_for_status()
    return r

def _show_meta(rk: str) -> Dict[str, Any]:
    r = _plex_json_or_xml(f"/library/metadata/{rk}")
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        data = r.json()
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        md = md[0] if isinstance(md, list) and md else (md if isinstance(md, dict) else {})
        if not md or md.get("type") not in ("show", "series"):
            raise HTTPException(status_code=404, detail="Show not found")
        return {
            "title": md.get("title") or "",
            "year": md.get("year"),
            "thumb": md.get("thumb"),
            "art": md.get("art"),
        }
    root = ET.fromstring(r.text)
    md = root.find(".//Video")
    if md is None or md.attrib.get("type") not in ("show", "series"):
        raise HTTPException(status_code=404, detail="Show not found")
    return {
        "title": md.attrib.get("title") or "",
        "year": _to_int(md.attrib.get("year")),
        "thumb": md.attrib.get("thumb"),
        "art": md.attrib.get("art"),
    }

def _seasons(rk: str) -> List[Dict[str, Any]]:
    r = _plex_json_or_xml(f"/library/metadata/{rk}/children")
    ctype = (r.headers.get("Content-Type") or "").lower()
    out: List[Dict[str, Any]] = []
    if "application/json" in ctype:
        data = r.json()
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        if isinstance(md, dict): md = [md]
        for it in md:
            if it.get("type") == "season":
                out.append({
                    "index": _to_int(it.get("index")),
                    "title": it.get("title") or f"Season {it.get('index')}",
                    "ratingKey": it.get("ratingKey"),
                    "thumb": it.get("thumb"),
                })
        return sorted([s for s in out if s["index"] is not None], key=lambda x: x["index"])
    root = ET.fromstring(r.text)
    for node in root.findall(".//Directory"):
        if node.attrib.get("type") == "season":
            out.append({
                "index": _to_int(node.attrib.get("index")),
                "title": node.attrib.get("title") or f"Season {node.attrib.get('index')}",
                "ratingKey": node.attrib.get("ratingKey"),
                "thumb": node.attrib.get("thumb"),
            })
    return sorted([s for s in out if s["index"] is not None], key=lambda x: x["index"])

def _to_int(x) -> Optional[int]:
    try: return int(str(x))
    except Exception: return None

def _existing_folder_name(library: str, title: str, year: Optional[int]) -> Optional[str]:
    candidates: List[str] = []
    if year: candidates.append(f"{title} ({year})")
    candidates.append(title)
    for cand in candidates:
        try:
            path = resolve_existing_dir_or_422(library, cand)
            return os.path.basename(path.rstrip(os.sep))
        except Exception:
            continue
    return None

def _local_exists(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except Exception:
        return False

def _mtime(path: str) -> int:
    try:
        return int(os.path.getmtime(path))
    except Exception:
        return 0

def _fileproxy_abs_path(library: str, folder: str, filename: str, bust: int = 0) -> str:
    lib_enc = quote(library, safe="")
    fol_enc = quote(folder,  safe="")
    fn_enc  = quote(filename, safe="")
    t = f"&t={bust}" if bust else ""
    return f"/fileproxy?path=/assets/{lib_enc}/{fol_enc}/{fn_enc}{t}"

def _plex_thumb_url(thumb: Optional[str], rk: Optional[str]) -> Optional[str]:
    path = thumb or (f"/library/metadata/{rk}/thumb" if rk else None)
    if not path: return None
    return f"{PLEX_URL}{path}?X-Plex-Token={PLEX_TOKEN}"

def _plex_art_url(art: Optional[str], rk: Optional[str]) -> Optional[str]:
    path = art or (f"/library/metadata/{rk}/art" if rk else None)
    if not path: return None
    return f"{PLEX_URL}{path}?X-Plex-Token={PLEX_TOKEN}"

@router.get("/api/show")
def get_show(library: str = Query(...), ratingKey: str = Query(...)):
    """
    Returns:
      {
        title, year, folderName,
        posterUrl, backgroundUrl,
        plexPosterUrl, plexBackgroundUrl,
        seasons: [{index, title, posterUrl, plexPosterUrl, ratingKey}]
      }
    Prefers local assets for poster/background/season; includes plex* URLs so the UI can pass
    them to /api/import/* (eliminates fragile server-side discovery).
    """
    meta = _show_meta(ratingKey)
    title, year, thumb, art = meta["title"], meta["year"], meta["thumb"], meta["art"]
    all_seasons = _seasons(ratingKey)

    override_folder = folder_overrides.get_override(library, ratingKey)
    folder_exists = False
    folder = override_folder
    if folder:
        folder_exists = True
    else:
        folder = _existing_folder_name(library, title, year)
        folder_exists = folder is not None
        if not folder:
            folder = kometa_sanitize_folder(f"{title} ({year})" if year else title)

    series_dir_fs = os.path.join(ASSETS_ROOT, library, folder)

    # Local-first with cache-busting
    poster_local = os.path.join(series_dir_fs, "poster.jpg")
    if _local_exists(poster_local):
        poster_url = _fileproxy_abs_path(library, folder, "poster.jpg", _mtime(poster_local))
    else:
        poster_url = _plex_thumb_url(thumb, ratingKey)
    plex_poster_url = _plex_thumb_url(thumb, ratingKey)

    bg_local = os.path.join(series_dir_fs, "background.jpg")
    if _local_exists(bg_local):
        background_url = _fileproxy_abs_path(library, folder, "background.jpg", _mtime(bg_local))
    else:
        background_url = _plex_art_url(art, ratingKey)
    plex_background_url = _plex_art_url(art, ratingKey)

    seasons_out: List[Dict[str, Any]] = []
    for s in all_seasons:
        idx = s["index"]
        sea_name = f"Season{idx:02d}.jpg"
        sea_local = os.path.join(series_dir_fs, sea_name)
        if _local_exists(sea_local):
            sea_url = _fileproxy_abs_path(library, folder, sea_name, _mtime(sea_local))
        else:
            sea_url = _plex_thumb_url(s.get("thumb"), s.get("ratingKey"))
        seasons_out.append({
            "index": idx,
            "title": s["title"],
            "posterUrl": sea_url,
            "plexPosterUrl": _plex_thumb_url(s.get("thumb"), s.get("ratingKey")),
            "ratingKey": s.get("ratingKey"),  # added for convenience
        })

    return {
        "title": title,
        "year": year,
        "folderName": folder,
        "folderExists": folder_exists,
        "posterUrl": poster_url,
        "backgroundUrl": background_url,
        "plexPosterUrl": plex_poster_url,
        "plexBackgroundUrl": plex_background_url,
        "seasons": seasons_out,
    }
