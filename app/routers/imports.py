# app/routers/imports.py
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Form, HTTPException, Query

from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

PLEX_URL        = os.environ.get("PLEX_URL", "").rstrip("/")
PLEX_TOKEN      = os.environ.get("PLEX_TOKEN", "")
# Allow opting out for self-signed Plex certs: export PLEX_VERIFY_SSL=false
PLEX_VERIFY_SSL = os.environ.get("PLEX_VERIFY_SSL", "true").lower() != "false"

logger = logging.getLogger(__name__)
TOKEN_MASK = "***"


def _mask_token(value: Optional[str]) -> Optional[str]:
    if not value or not PLEX_TOKEN:
        return value
    return value.replace(PLEX_TOKEN, TOKEN_MASK)


def _safe_url(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    return _mask_token(url)


def _safe_params(params: Optional[dict]) -> Optional[dict]:
    if not params:
        return params
    safe = dict(params)
    token_key = "X-Plex-Token"
    if token_key in safe and safe[token_key]:
        safe[token_key] = TOKEN_MASK
    return safe


def _safe_headers(headers: Optional[dict]) -> Optional[dict]:
    if not headers:
        return headers
    safe = dict(headers)
    token_key = "X-Plex-Token"
    if token_key in safe and safe[token_key]:
        safe[token_key] = TOKEN_MASK
    return safe

def _require_plex():
    if not PLEX_URL or not PLEX_TOKEN:
        logger.error("Plex configuration missing (PLEX_URL or PLEX_TOKEN)")
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

def _dest_dir_or_422(library: str, folderName: str) -> str:
    try:
        logger.debug(
            "Resolving destination directory for library=%s folderName=%s",
            library,
            folderName,
        )
        return resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        logger.warning(
            "Destination directory not found for library=%s folderName=%s: %s",
            library,
            folderName,
            e,
        )
        raise HTTPException(status_code=422, detail=str(e))

# ---------------- Plex helpers ----------------

def _get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
    try:
        logger.debug(
            "GET %s params=%s headers=%s",
            _safe_url(url),
            _safe_params(params),
            _safe_headers(headers),
        )
        r = requests.get(url, params=params, headers=headers, timeout=30, verify=PLEX_VERIFY_SSL)
        r.raise_for_status()
        return r
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        detail = f"Plex request failed [{status}] for {url}"
        logger.warning(
            "Plex HTTP error [%s] for %s: %s",
            status,
            _safe_url(url),
            e,
        )
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        logger.warning("Plex request error for %s: %s", _safe_url(url), e)
        raise HTTPException(status_code=502, detail=f"Plex request error for {url}: {e}")

def _download_to(path: str, url: str):
    try:
        logger.debug("Downloading %s to %s", _safe_url(url), path)
        with requests.get(url, timeout=60, stream=True, verify=PLEX_VERIFY_SSL) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        logger.debug("Download complete for %s", path)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        logger.warning(
            "Download failed [%s] for %s: %s", status, _safe_url(url), e
        )
        raise HTTPException(status_code=502, detail=f"Download failed [{status}] for {url}")
    except Exception as e:
        logger.warning("Download error for %s: %s", _safe_url(url), e)
        raise HTTPException(status_code=502, detail=f"Download error for {url}: {e}")

def _json_or_xml(path: str) -> Dict[str, Any] | str:
    """
    Return JSON dict if server answered JSON; otherwise return XML text.
    """
    _require_plex()
    url = f"{PLEX_URL}{path}"
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
    logger.debug("Requesting Plex metadata from %s", _safe_url(url))
    r = _get(url, params={"X-Plex-Token": PLEX_TOKEN}, headers=headers)
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        logger.debug("Received JSON metadata for %s", path)
        return r.json()
    logger.debug("Received XML metadata for %s", path)
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
        logger.debug(
            "Attempting direct poster URL for ratingKey=%s: %s",
            rating_key,
            _safe_url(direct),
        )
        _get(direct)
        return direct
    except HTTPException:
        logger.debug("Falling back to metadata poster lookup for ratingKey=%s", rating_key)
        thumb_path = _resolve_thumb_path_from_metadata(rating_key)
        if not thumb_path:
            logger.warning("Poster path resolution failed for ratingKey=%s", rating_key)
            raise HTTPException(status_code=502, detail=f"Could not resolve poster path for ratingKey={rating_key}")
        return f"{PLEX_URL}{thumb_path}?X-Plex-Token={PLEX_TOKEN}"

def _art_url_for_rating_key(rating_key: str) -> str:
    _require_plex()
    direct = f"{PLEX_URL}/library/metadata/{rating_key}/art?X-Plex-Token={PLEX_TOKEN}"
    try:
        logger.debug(
            "Attempting direct background URL for ratingKey=%s: %s",
            rating_key,
            _safe_url(direct),
        )
        _get(direct)
        return direct
    except HTTPException:
        logger.debug("Falling back to metadata background lookup for ratingKey=%s", rating_key)
        art_path = _resolve_art_path_from_metadata(rating_key)
        if not art_path:
            logger.warning("Background path resolution failed for ratingKey=%s", rating_key)
            raise HTTPException(status_code=502, detail=f"Could not resolve background path for ratingKey={rating_key}")
        return f"{PLEX_URL}{art_path}?X-Plex-Token={PLEX_TOKEN}"

def _children_for_show(rating_key: str) -> List[Dict[str, Any]]:
    logger.debug("Fetching seasons for show ratingKey=%s", rating_key)
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
    except Exception as e:
        logger.warning("Failed to parse season metadata for ratingKey=%s: %s", rating_key, e)
    return out

def _season_poster_url(show_rating_key: str, season_index: int) -> str:
    seasons = _children_for_show(show_rating_key)
    target = None
    for s in seasons:
        try:
            if int(str(s.get("index"))) == int(season_index):
                target = s
                break
        except Exception as e:
            logger.warning(
                "Invalid season index encountered for show %s: %s", show_rating_key, e
            )
            continue
    if not target:
        logger.warning(
            "Season %s not found in Plex metadata for show %s",
            season_index,
            show_rating_key,
        )
        raise HTTPException(status_code=404, detail=f"Season {season_index} not found in Plex")
    thumb = target.get("thumb")
    rk    = target.get("ratingKey")
    if thumb:
        return f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}"
    if rk:
        return f"{PLEX_URL}/library/metadata/{rk}/thumb?X-Plex-Token={PLEX_TOKEN}"
    logger.warning(
        "Season poster URL unavailable for show %s season %s", show_rating_key, season_index
    )
    raise HTTPException(status_code=502, detail="Season poster URL unavailable from Plex")

# ---------------- Endpoints ----------------

@router.post("/api/import/poster")
def import_poster_post(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    url: Optional[str] = Form(None),
):
    logger.debug(
        "Import poster POST library=%s folder=%s ratingKey=%s url=%s",
        library,
        folderName,
        ratingKey,
        _safe_url(url),
    )
    dest_dir = _dest_dir_or_422(library, folderName)
    path = os.path.join(dest_dir, "poster.jpg")
    src = url or _poster_url_for_rating_key(ratingKey)
    logger.debug(
        "Poster source resolved for library=%s folder=%s: %s",
        library,
        folderName,
        _safe_url(src),
    )
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
    logger.debug(
        "Import background POST library=%s folder=%s ratingKey=%s url=%s",
        library,
        folderName,
        ratingKey,
        _safe_url(url),
    )
    dest_dir = _dest_dir_or_422(library, folderName)
    path = os.path.join(dest_dir, "background.jpg")
    src = url or _art_url_for_rating_key(ratingKey)
    logger.debug(
        "Background source resolved for library=%s folder=%s: %s",
        library,
        folderName,
        _safe_url(src),
    )
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
    logger.debug(
        "Import season POST library=%s folder=%s season=%s ratingKey=%s url=%s",
        library,
        folderName,
        season,
        ratingKey,
        _safe_url(url),
    )
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

    logger.debug(
        "Season source resolved for library=%s folder=%s season=%s: %s",
        library,
        folderName,
        idx,
        _safe_url(src),
    )
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
    logger.debug(
        "Import movie POST library=%s folder=%s ratingKey=%s includePoster=%s includeBackground=%s",
        library,
        folderName,
        ratingKey,
        includePoster,
        includeBackground,
    )
    dest_dir = _dest_dir_or_422(library, folderName)

    results = {
        "poster": {"ok": False, "path": None, "src": None, "error": None},
        "background": {"ok": False, "path": None, "src": None, "error": None},
    }

    if includePoster:
        try:
            p_path = os.path.join(dest_dir, "poster.jpg")
            p_src = posterUrl or _poster_url_for_rating_key(ratingKey)
            logger.debug(
                "Movie poster source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(p_src),
            )
            _download_to(p_path, p_src)
            results["poster"] = {"ok": True, "path": p_path, "src": p_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Movie poster import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["poster"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Movie poster import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
            results["poster"]["error"] = str(e)

    if includeBackground:
        try:
            b_path = os.path.join(dest_dir, "background.jpg")
            b_src = backgroundUrl or _art_url_for_rating_key(ratingKey)
            logger.debug(
                "Movie background source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(b_src),
            )
            _download_to(b_path, b_src)
            results["background"] = {"ok": True, "path": b_path, "src": b_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Movie background import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["background"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Movie background import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
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
    logger.debug(
        "Import show POST library=%s folder=%s ratingKey=%s includePoster=%s includeBackground=%s includeSeasons=%s",
        library,
        folderName,
        ratingKey,
        includePoster,
        includeBackground,
        includeSeasons,
    )
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
            logger.debug(
                "Show poster source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(p_src),
            )
            _download_to(p_path, p_src)
            results["poster"] = {"ok": True, "path": p_path, "src": p_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Show poster import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["poster"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Show poster import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
            results["poster"]["error"] = str(e)

    # Series background
    if includeBackground:
        try:
            b_path = os.path.join(dest_dir, "background.jpg")
            b_src = _art_url_for_rating_key(ratingKey)
            logger.debug(
                "Show background source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(b_src),
            )
            _download_to(b_path, b_src)
            results["background"] = {"ok": True, "path": b_path, "src": b_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Show background import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["background"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Show background import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
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
                    logger.debug(
                        "Show season source resolved for library=%s folder=%s season=%s: %s",
                        library,
                        folderName,
                        idx,
                        _safe_url(sea_src),
                    )
                    _download_to(sea_path, sea_src)
                    ok_entry.update({"ok": True, "path": sea_path, "src": sea_src})
                except HTTPException as e:
                    logger.warning(
                        "Season import failed for library=%s folder=%s season=%s: %s",
                        library,
                        folderName,
                        idx,
                        e.detail,
                    )
                    ok_entry["error"] = e.detail
                except Exception as e:
                    logger.warning(
                        "Season import error for library=%s folder=%s season=%s: %s",
                        library,
                        folderName,
                        idx,
                        e,
                    )
                    ok_entry["error"] = str(e)
                results["seasons"].append(ok_entry)
        except Exception as e:
            logger.warning(
                "Failed to enumerate seasons for library=%s folder=%s ratingKey=%s: %s",
                library,
                folderName,
                ratingKey,
                e,
            )
            results["seasons"].append({"ok": False, "error": f"Failed to enumerate seasons: {e}"})

    results["ok"] = (
        results["poster"]["ok"]
        or results["background"]["ok"]
        or any(s.get("ok") for s in results["seasons"])
    )
    return results

# NEW: combined import for Collections (poster + background in one call)
@router.post("/api/import/collection")
def import_collection_both(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: str = Form(...),
    includePoster: bool = Form(True),
    includeBackground: bool = Form(True),
):
    """
    Import a collection's poster and background from Plex into the Kometa asset folder.
    """
    logger.debug(
        "Import collection POST library=%s folder=%s ratingKey=%s includePoster=%s includeBackground=%s",
        library,
        folderName,
        ratingKey,
        includePoster,
        includeBackground,
    )
    dest_dir = _dest_dir_or_422(library, folderName)

    results: Dict[str, Any] = {
        "poster": {"ok": False, "path": None, "src": None, "error": None},
        "background": {"ok": False, "path": None, "src": None, "error": None},
    }

    if includePoster:
        try:
            p_path = os.path.join(dest_dir, "poster.jpg")
            p_src = _poster_url_for_rating_key(ratingKey)
            logger.debug(
                "Collection poster source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(p_src),
            )
            _download_to(p_path, p_src)
            results["poster"] = {"ok": True, "path": p_path, "src": p_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Collection poster import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["poster"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Collection poster import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
            results["poster"]["error"] = str(e)

    if includeBackground:
        try:
            b_path = os.path.join(dest_dir, "background.jpg")
            b_src = _art_url_for_rating_key(ratingKey)
            logger.debug(
                "Collection background source resolved for library=%s folder=%s: %s",
                library,
                folderName,
                _safe_url(b_src),
            )
            _download_to(b_path, b_src)
            results["background"] = {"ok": True, "path": b_path, "src": b_src, "error": None}
        except HTTPException as e:
            logger.warning(
                "Collection background import failed for library=%s folder=%s: %s",
                library,
                folderName,
                e.detail,
            )
            results["background"]["error"] = e.detail
        except Exception as e:
            logger.warning(
                "Collection background import error for library=%s folder=%s: %s",
                library,
                folderName,
                e,
            )
            results["background"]["error"] = str(e)

    return {
        "ok": results["poster"]["ok"] or results["background"]["ok"],
        "results": results,
    }
