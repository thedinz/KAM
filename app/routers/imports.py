# app/routers/imports.py
from fastapi import APIRouter, Form, Query, HTTPException
from typing import Optional, Dict, Any, List
import os
import requests
import xml.etree.ElementTree as ET

from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

PLEX_URL        = os.environ.get("PLEX_URL", "").rstrip("/")
PLEX_TOKEN      = os.environ.get("PLEX_TOKEN", "")
# Allow opting out for self-signed Plex certs: export PLEX_VERIFY_SSL=false
PLEX_VERIFY_SSL = os.environ.get("PLEX_VERIFY_SSL", "true").lower() != "false"

def _require_plex():
    if not PLEX_URL or not PLEX_TOKEN:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

def _dest_dir_or_422(library: str, folderName: str) -> str:
    try:
        return resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

# ---------------- Plex helpers ----------------

def _get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30, verify=PLEX_VERIFY_SSL)
        r.raise_for_status()
        return r
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        detail = f"Plex request failed [{status}] for {url}"
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Plex request error for {url}: {e}")

def _download_to(path: str, url: str):
    try:
        with requests.get(url, timeout=60, stream=True, verify=PLEX_VERIFY_SSL) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        raise HTTPException(status_code=502, detail=f"Download failed [{status}] for {url}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download error for {url}: {e}")

def _json_or_xml(path: str) -> Dict[str, Any] | str:
    """
    Return JSON dict if server answered JSON; otherwise return XML text.
    """
    _require_plex()
    url = f"{PLEX_URL}{path}"
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
    r = _get(url, params={"X-Plex-Token": PLEX_TOKEN}, headers=headers)
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        return r.json()
    return r.text  # XML

def _resolve_thumb_path_from_metadata(rating_key: str) -> Optional[str]:
    data = _json_or_xml(f"/library/metadata/{rating_key}")
    if isinstance(data, dict):
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        if isinstance(md, dict):
            md = [md]
        if md:
            return md[0].get("thumb")
        return None
    try:
        root = ET.fromstring(data)
        node = root.find(".//Video")
        if node is not None:
            return node.attrib.get("thumb")
    except Exception:
        pass
    return None

def _resolve_art_path_from_metadata(rating_key: str) -> Optional[str]:
    data = _json_or_xml(f"/library/metadata/{rating_key}")
    if isinstance(data, dict):
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        if isinstance(md, dict):
            md = [md]
        if md:
            return md[0].get("art")
        return None
    try:
        root = ET.fromstring(data)
        node = root.find(".//Video")
        if node is not None:
            return node.attrib.get("art")
    except Exception:
        pass
    return None

def _poster_url_for_rating_key(rating_key: str) -> str:
    _require_plex()
    direct = f"{PLEX_URL}/library/metadata/{rating_key}/thumb?X-Plex-Token={PLEX_TOKEN}"
    try:
        _get(direct)
        return direct
    except HTTPException:
        thumb_path = _resolve_thumb_path_from_metadata(rating_key)
        if not thumb_path:
            raise HTTPException(status_code=502, detail=f"Could not resolve poster path for ratingKey={rating_key}")
        return f"{PLEX_URL}{thumb_path}?X-Plex-Token={PLEX_TOKEN}"

def _art_url_for_rating_key(rating_key: str) -> str:
    _require_plex()
    direct = f"{PLEX_URL}/library/metadata/{rating_key}/art?X-Plex-Token={PLEX_TOKEN}"
    try:
        _get(direct)
        return direct
    except HTTPException:
        art_path = _resolve_art_path_from_metadata(rating_key)
        if not art_path:
            raise HTTPException(status_code=502, detail=f"Could not resolve background path for ratingKey={rating_key}")
        return f"{PLEX_URL}{art_path}?X-Plex-Token={PLEX_TOKEN}"

def _children_for_show(rating_key: str) -> List[Dict[str, Any]]:
    data = _json_or_xml(f"/library/metadata/{rating_key}/children")
    out: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        md = (data.get("MediaContainer", {}) or {}).get("Metadata") or []
        if isinstance(md, dict):
            md = [md]
        for it in md:
            if it.get("type") == "season":
                out.append({
                    "type": "season",
                    "index": it.get("index"),
                    "ratingKey": it.get("ratingKey"),
                    "thumb": it.get("thumb"),
                })
        return out
    try:
        root = ET.fromstring(data)
        for node in root.findall(".//Directory"):
            if node.attrib.get("type") == "season":
                out.append({
                    "type": "season",
                    "index": node.attrib.get("index"),
                    "ratingKey": node.attrib.get("ratingKey"),
                    "thumb": node.attrib.get("thumb"),
                })
        for node in root.findall(".//Video"):
            if node.attrib.get("type") == "season":
                out.append({
                    "type": "season",
                    "index": node.attrib.get("index"),
                    "ratingKey": node.attrib.get("ratingKey"),
                    "thumb": node.attrib.get("thumb"),
                })
    except Exception:
        pass
    return out

def _season_poster_url(show_rating_key: str, season_index: int) -> str:
    seasons = _children_for_show(show_rating_key)
    target = None
    for s in seasons:
        try:
            if int(str(s.get("index"))) == int(season_index):
                target = s
                break
        except Exception:
            continue
    if not target:
        raise HTTPException(status_code=404, detail=f"Season {season_index} not found in Plex")
    thumb = target.get("thumb")
    rk    = target.get("ratingKey")
    if thumb:
        return f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}"
    if rk:
        return f"{PLEX_URL}/library/metadata/{rk}/thumb?X-Plex-Token={PLEX_TOKEN}"
    raise HTTPException(status_code=502, detail="Season poster URL unavailable from Plex")

# ---------------- Endpoints ----------------

@router.post("/api/import/poster")
def import_poster_post(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    url: Optional[str] = Form(None),
):
    dest_dir = _dest_dir_or_422(library, folderName)
    path = os.path.join(dest_dir, "poster.jpg")
    src = url or _poster_url_for_rating_key(ratingKey)
    _download_to(path, src)
    return {"ok": True, "path": path, "src": src}

@router.get("/api/import/poster")
def import_poster_get(
    library: str = Query(...),
    folderName: str = Query(...),
    ratingKey: str = Query(...),
    url: Optional[str] = Query(None),
):
    return import_poster_post(library=library, folderName=folderName, ratingKey=ratingKey, url=url)

@router.post("/api/import/background")
def import_background_post(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    url: Optional[str] = Form(None),
):
    dest_dir = _dest_dir_or_422(library, folderName)
    path = os.path.join(dest_dir, "background.jpg")
    src = url or _art_url_for_rating_key(ratingKey)
    _download_to(path, src)
    return {"ok": True, "path": path, "src": src}

@router.get("/api/import/background")
def import_background_get(
    library: str = Query(...),
    folderName: str = Query(...),
    ratingKey: str = Query(...),
    url: Optional[str] = Query(None),
):
    return import_background_post(library=library, folderName=folderName, ratingKey=ratingKey, url=url)

@router.post("/api/import/season")
def import_season_post(
    library: str = Form(...),
    folderName: str = Form(...),
    season: str = Form(...),
    ratingKey: Optional[str] = Form(None),  # show ratingKey; required if url not supplied
    url: Optional[str] = Form(None),
):
    try:
        idx = int(str(season).strip())
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid season: {season!r}")

    dest_dir = _dest_dir_or_422(library, folderName)
    path = os.path.join(dest_dir, f"Season{idx:02d}.jpg")

    if url:
        src = url
    else:
        if not ratingKey:
            raise HTTPException(status_code=422, detail="ratingKey is required when url is not provided")
        src = _season_poster_url(ratingKey, idx)

    _download_to(path, src)
    return {"ok": True, "path": path, "src": src}

@router.get("/api/import/season")
def import_season_get(
    library: str = Query(...),
    folderName: str = Query(...),
    season: str = Query(...),
    ratingKey: Optional[str] = Query(None),
    url: Optional[str] = Query(None),
):
    return import_season_post(
        library=library,
        folderName=folderName,
        season=season,
        ratingKey=ratingKey,
        url=url,
    )

# NEW: combined import for movies (poster + background in one call)
@router.post("/api/import/movie")
def import_movie_both(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    includePoster: bool = Form(True),
    includeBackground: bool = Form(True),
    posterUrl: Optional[str] = Form(None),
    backgroundUrl: Optional[str] = Form(None),
):
    dest_dir = _dest_dir_or_422(library, folderName)

    results = {
        "poster": {"ok": False, "path": None, "src": None, "error": None},
        "background": {"ok": False, "path": None, "src": None, "error": None},
    }

    if includePoster:
        try:
            p_path = os.path.join(dest_dir, "poster.jpg")
            p_src = posterUrl or _poster_url_for_rating_key(ratingKey)
            _download_to(p_path, p_src)
            results["poster"] = {"ok": True, "path": p_path, "src": p_src, "error": None}
        except HTTPException as e:
            results["poster"]["error"] = e.detail
        except Exception as e:
            results["poster"]["error"] = str(e)

    if includeBackground:
        try:
            b_path = os.path.join(dest_dir, "background.jpg")
            b_src = backgroundUrl or _art_url_for_rating_key(ratingKey)
            _download_to(b_path, b_src)
            results["background"] = {"ok": True, "path": b_path, "src": b_src, "error": None}
        except HTTPException as e:
            results["background"]["error"] = e.detail
        except Exception as e:
            results["background"]["error"] = str(e)

    return {"ok": results["poster"]["ok"] or results["background"]["ok"], "results": results}

# NEW: combined import for TV shows (poster + background + all seasons)
@router.post("/api/import/show")
def import_show_all(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    includePoster: bool = Form(True),
    includeBackground: bool = Form(True),
    includeSeasons: bool = Form(True),
):
    """
    Import a show's poster, background, and all season posters in one call.
    """
    dest_dir = _dest_dir_or_422(library, folderName)
    results: Dict[str, Any] = {
        "poster": {"ok": False, "path": None, "src": None, "error": None},
        "background": {"ok": False, "path": None, "src": None, "error": None},
        "seasons": [],
    }

    # Series poster
    if includePoster:
        try:
            p_path = os.path.join(dest_dir, "poster.jpg")
            p_src = _poster_url_for_rating_key(ratingKey)
            _download_to(p_path, p_src)
            results["poster"] = {"ok": True, "path": p_path, "src": p_src, "error": None}
        except HTTPException as e:
            results["poster"]["error"] = e.detail
        except Exception as e:
            results["poster"]["error"] = str(e)

    # Series background
    if includeBackground:
        try:
            b_path = os.path.join(dest_dir, "background.jpg")
            b_src = _art_url_for_rating_key(ratingKey)
            _download_to(b_path, b_src)
            results["background"] = {"ok": True, "path": b_path, "src": b_src, "error": None}
        except HTTPException as e:
            results["background"]["error"] = e.detail
        except Exception as e:
            results["background"]["error"] = str(e)

    # Seasons
    if includeSeasons:
        try:
            seasons = _children_for_show(ratingKey)  # [{index, ratingKey, thumb}, ...]
            for s in seasons:
                idx_raw = s.get("index")
                ok_entry = {"index": idx_raw, "ok": False, "path": None, "src": None, "error": None}
                try:
                    idx = int(str(idx_raw))
                except Exception:
                    ok_entry["error"] = f"Invalid season index: {idx_raw!r}"
                    results["seasons"].append(ok_entry)
                    continue
                try:
                    sea_path = os.path.join(dest_dir, f"Season{idx:02d}.jpg")
                    sea_src = _season_poster_url(ratingKey, idx)
                    _download_to(sea_path, sea_src)
                    ok_entry.update({"ok": True, "path": sea_path, "src": sea_src})
                except HTTPException as e:
                    ok_entry["error"] = e.detail
                except Exception as e:
                    ok_entry["error"] = str(e)
                results["seasons"].append(ok_entry)
        except Exception as e:
            results["seasons"].append({"ok": False, "error": f"Failed to enumerate seasons: {e}"})

    results["ok"] = (
        results["poster"]["ok"]
        or results["background"]["ok"]
        or any(s.get("ok") for s in results["seasons"])
    )
    return results

@router.post("/api/import/library")
def import_library(library: str = Form(...)):
    # front-end loops items and calls /api/import/* per item
    return {"ok": True, "imported": True}
