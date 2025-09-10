
from fastapi import APIRouter, HTTPException, Query, Form, File, UploadFile
from math import ceil
from typing import Optional, List, Dict, Any
import os

from ..services.plex import get_plex
from ..services.assets import sanitize_name, save_as_named_jpg
from .. import config

router = APIRouter()

def _section_by_name(name: str):
    plex = get_plex()
    for s in plex.library.sections():
        if s.title == name:
            return s
    raise HTTPException(404, f"Library '{name}' not found in Plex")


def _find_first_existing(base: str):
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        p = base + ext
        if os.path.isfile(p):
            return p
    return None

def _folder_name_for_show(title: str, year: Optional[int]) -> str:
    # Keep simple for now to match Kometa style: Title or Title (YYYY)
    t = sanitize_name(title or "")
    if year:
        # Some shows use Title (YYYY). We won't attempt to detect collisions yet.
        return f"{t} ({year})" if "(" not in t and ")" not in t else t
    return t

@router.get("/shows", summary="List TV shows")
def shows(library: str = Query(...),
          query: Optional[str] = Query(None),
          page: int = Query(1, ge=1),
          page_size: int = Query(60, ge=1, le=200)):
    section = _section_by_name(library)
    # Fetch shows
    items = section.search(libtype='show', sort='titleSort:asc')
    out = []
    q = (query or "").strip().lower()
    for it in items:
        title = getattr(it, 'title', None)
        year = getattr(it, 'year', None)
        if q and q not in (title or "").lower():
            continue
        ratingKey = int(getattr(it, 'ratingKey', 0))
        folder = _folder_name_for_show(title, year)
        # Asset poster if present
        assets_root = config.LIBRARY_MAPPINGS.get(library)
        poster = None
        if assets_root:
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                p = os.path.join(assets_root, folder, 'poster' + ext)
                if os.path.isfile(p):
                    poster = '/api/fileproxy?path=' + p  # simple passthrough if you add such route later
                    break
        out.append({
            "type": "show",
            "title": title,
            "year": year,
            "ratingKey": ratingKey,
            "folderName": folder,
            "posterUrl": poster,  # UI should fallback if None
        })
    total = len(out)
    pages = max(1, ceil(total / page_size))
    page = min(page, pages)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "library": library,
        "page": page,
        "page_size": page_size,
        "total_count": total,
        "total_pages": pages,
        "items": out[start:end],
    }

@router.get("/show", summary="Single TV show details")
def show_detail(library: str = Query(...), ratingKey: int = Query(...)):
    section = _section_by_name(library)
    show = section.fetchItem(ratingKey)
    if not show or str(getattr(show, 'type', '')) != 'show':
        raise HTTPException(404, "Show not found")
    title = getattr(show, 'title', None)
    year = getattr(show, 'year', None)
    folder = _folder_name_for_show(title, year)
    seasons = []
    for s in show.seasons():
        try:
            num = int(getattr(s, 'index', 0))
        except Exception:
            num = 0
        seasons.append({ "index": num, "title": getattr(s, 'title', f"Season {num}"), "ratingKey": int(getattr(s, "ratingKey", 0)) })
    seasons = sorted(seasons, key=lambda x: x['index'])
    # Check which asset files exist
    root = config.LIBRARY_MAPPINGS.get(library)
    poster_exists = background_exists = False
    poster_url_local = None
    background_url_local = None
    season_assets = []
    if root:
        folder_path = os.path.join(root, folder)
        poster_exists = any(os.path.isfile(os.path.join(folder_path, "poster"+ext)) for ext in (".jpg",".jpeg",".png",".webp"))
        background_exists = any(os.path.isfile(os.path.join(folder_path, "background"+ext)) for ext in (".jpg",".jpeg",".png",".webp"))
        if poster_exists:
            for ext in (".jpg",".jpeg",".png",".webp"):
                p = os.path.join(folder_path, "poster"+ext)
                if os.path.isfile(p):
                    ts = None
                    try:
                        ts = int(os.path.getmtime(p))
                    except Exception:
                        ts = None
                    poster_url_local = "/api/fileproxy?path=" + p + (("&t=" + str(ts)) if ts else "")
                    break
        if background_exists:
            for ext in (".jpg",".jpeg",".png",".webp"):
                p = os.path.join(folder_path, "background"+ext)
                if os.path.isfile(p):
                    ts2 = None
                    try:
                        ts2 = int(os.path.getmtime(p))
                    except Exception:
                        ts2 = None
                    background_url_local = "/api/fileproxy?path=" + p + (("&t=" + str(ts2)) if ts2 else "")
                    break
        for s in seasons:
            idx = s['index']
            base = f"Season{idx:02d}"
            local_url = None
            exists = False
            for ext in (".jpg",".jpeg",".png",".webp"):
                sp = os.path.join(folder_path, base+ext)
                if os.path.isfile(sp):
                    exists = True
                    ts3 = None
                    try:
                        ts3 = int(os.path.getmtime(sp))
                    except Exception:
                        ts3 = None
                    local_url = '/api/fileproxy?path=' + sp + (('&t=' + str(ts3)) if ts3 else '')
                    break
            rk_season = int(s.get('ratingKey') or 0)
            plex_url = (f"{config.PLEX_URL}/library/metadata/{rk_season}/thumb?X-Plex-Token={config.PLEX_TOKEN}" if rk_season else None)
            season_assets.append({ "index": idx, "exists": exists, "url": local_url, "urlPlex": plex_url, "ratingKey": int(s.get("ratingKey") or 0) })
    return {
        "library": library,
        "title": title,
        "year": year,
        "ratingKey": int(ratingKey),
        "folderName": folder,
        "posterExists": poster_exists,
        "backgroundExists": background_exists,
        "posterUrl": poster_url_local,
        "posterUrlPlex": f"{config.PLEX_URL}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={config.PLEX_TOKEN}",
        "backgroundUrl": background_url_local,
        "backgroundUrlPlex": f"{config.PLEX_URL}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={config.PLEX_TOKEN}",
        "seasons": season_assets,
    }

@router.post("/upload_show", summary="Upload series poster/background")
def upload_show(library: str = Form(...), folderName: str = Form(...),
                kind: str = Form(...), file: UploadFile = File(...)):
    if kind not in ("poster", "background"):
        raise HTTPException(400, "kind must be 'poster' or 'background'")
    if library not in config.LIBRARY_MAPPINGS:
        raise HTTPException(404, f"Library '{library}' not configured")
    if any(c in folderName for c in ('/', '\\')):
        raise HTTPException(400, "Invalid folder name")
    dest_folder = os.path.join(config.LIBRARY_MAPPINGS[library], folderName)
    path = save_as_named_jpg(file, dest_folder, kind)
    return {"ok": True, "path": path}

@router.post("/upload_season", summary="Upload a season poster")
def upload_season(library: str = Form(...), folderName: str = Form(...),
                  season: str = Form(...), file: UploadFile = File(...)):
    if library not in config.LIBRARY_MAPPINGS:
        raise HTTPException(404, f"Library '{library}' not configured")
    if any(c in folderName for c in ('/', '\\')):
        raise HTTPException(400, "Invalid folder name")
    try:
        n = int(season)
    except Exception:
        raise HTTPException(400, "season must be an integer like 0,1,2,10")
    base = f"Season{n:02d}"
    dest_folder = os.path.join(config.LIBRARY_MAPPINGS[library], folderName)
    path = save_as_named_jpg(file, dest_folder, base)
    return {"ok": True, "path": path}
