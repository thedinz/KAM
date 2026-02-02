from fastapi import APIRouter, HTTPException, Query
import os
from typing import Optional, Tuple
from urllib.parse import quote

from ..services import exclusions, folder_overrides
from ..services import plex_settings
from ..services.plex_assets import build_plex_asset_url, build_plex_proxy_url
from ..services import library_mappings as library_mappings_service
from ..services.plex import get_plex
from ..services.assets import folder_name_for
from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

def _section_by_name(name: str):
    plex = get_plex()
    for s in plex.library.sections():
        if s.title == name:
            return s
    raise HTTPException(404, f"Library '{name}' not found in Plex")

def _first_existing(base_no_ext: str):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = base_no_ext + ext
        if os.path.isfile(p):
            return p
    return None


def _fileproxy_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None

    url = f"/fileproxy?path={quote(path, safe='')}"
    try:
        ts = int(os.path.getmtime(path))
    except Exception:
        ts = 0
    if ts:
        url = f"{url}&t={ts}"
    return url


def _resolve_existing_folder(
    library: str, title: Optional[str], year: Optional[int]
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(basename, full_path)`` for the best matching existing asset folder."""

    if not title:
        return None, None

    candidates = []
    if year:
        candidates.append(f"{title} ({year})")
    candidates.append(title)

    for cand in candidates:
        try:
            resolved = resolve_existing_dir_or_422(library, cand)
        except Exception:
            continue
        if resolved:
            basename = os.path.basename(resolved.rstrip(os.sep))
            return basename, resolved

    return None, None

def _plex_url_parts() -> Tuple[str, str]:
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")
    return cfg.url, cfg.token


@router.get("/movie", summary="Single movie details")
def movie(library: str = Query(...), ratingKey: int = Query(...)):
    # Find the library section and the item
    sec = _section_by_name(library)
    plex = get_plex()
    try:
        item = plex.fetchItem(int(ratingKey))
    except Exception as e:
        raise HTTPException(404, f"Movie {ratingKey} not found: {e}")

    # Compute folder name using existing helper
    title = getattr(item, "title", None) or "Untitled"
    year = getattr(item, "year", None)
    folder = folder_name_for(title, year)
    override_folder = folder_overrides.get_override(library, str(ratingKey))
    auto_folder, auto_path = _resolve_existing_folder(library, title, year)

    if override_folder:
        folder = override_folder
    elif auto_folder:
        folder = auto_folder

    # Determine which folder (if any) truly exists so status messaging matches
    # the library overview page.
    folder_path = None
    if override_folder:
        try:
            folder_path = resolve_existing_dir_or_422(library, override_folder)
        except Exception:
            folder_path = None
    if folder_path is None and auto_path:
        folder_path = auto_path

    if folder_path is None:
        base = library_mappings_service.get_asset_path(library)
        if base and folder:
            candidate = os.path.join(base, folder)
            if os.path.isdir(candidate):
                folder_path = candidate

    poster_exists = False
    background_exists = False
    poster_url_local = None
    background_url_local = None
    folder_exists = folder_path is not None

    if folder_path:
        p = _first_existing(os.path.join(folder_path, "poster"))
        if p:
            poster_exists = True
            poster_url_local = _fileproxy_url(p)
        b = _first_existing(os.path.join(folder_path, "background"))
        if b:
            background_exists = True
            background_url_local = _fileproxy_url(b)

    plex_url, plex_token = _plex_url_parts()

    poster_proxy = build_plex_proxy_url(None, str(ratingKey), "thumb")
    background_proxy = build_plex_proxy_url(None, str(ratingKey), "art")

    return {
        "library": library,
        "title": title,
        "year": year,
        "ratingKey": int(ratingKey),
        "folderName": folder,
        "folderExists": folder_exists,
        "posterExists": poster_exists,
        "backgroundExists": background_exists,
        "posterUrl": poster_url_local or poster_proxy,
        "posterUrlPlex": f"{plex_url}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={plex_token}",
        "plexPosterUrl": build_plex_asset_url(None, str(ratingKey), "thumb"),
        "backgroundUrl": background_url_local or background_proxy,
        "backgroundUrlPlex": f"{plex_url}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={plex_token}",
        "plexBackgroundUrl": build_plex_asset_url(None, str(ratingKey), "art"),
        "excluded": exclusions.is_excluded(library, str(ratingKey)),
    }

@router.get("/api/movie", summary="Single movie details (alias)")
def movie_api(library: str = Query(...), ratingKey: int = Query(...)):
    return movie(library=library, ratingKey=ratingKey)
