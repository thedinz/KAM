from fastapi import APIRouter, HTTPException, Query
import os
from typing import Optional, Tuple

from ..services import folder_overrides
from ..services import plex_settings
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
    for ext in (".jpg",".jpeg",".png",".webp"):
        p = base_no_ext + ext
        if os.path.isfile(p):
            return p
    return None


def _resolve_existing_folder_basename(library: str, title: Optional[str], year: Optional[int]) -> Optional[str]:
    """Return the basename of an existing asset folder that best matches the title."""
    if not title:
        return None

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
            return os.path.basename(resolved.rstrip(os.sep))
    return None

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
    resolved_folder = _resolve_existing_folder_basename(library, title, year)
    if override_folder:
        folder = override_folder
    elif resolved_folder:
        folder = resolved_folder

    # Map to asset root for this library
    base = library_mappings_service.get_asset_path(library)
    poster_exists = False
    background_exists = False
    poster_url_local = None
    background_url_local = None
    folder_exists = bool(override_folder)

    if base:
        movie_folder = os.path.join(base, folder)
        actual_exists = os.path.isdir(movie_folder)
        folder_exists = folder_exists or actual_exists
        # poster
        p = _first_existing(os.path.join(movie_folder, "poster"))
        if p:
            poster_exists = True
            try:
                ts = int(os.path.getmtime(p))
            except Exception:
                ts = None
            poster_url_local = "/fileproxy?path=" + p + (("&t=" + str(ts)) if ts else "")
        # background
        b = _first_existing(os.path.join(movie_folder, "background"))
        if b:
            background_exists = True
            try:
                ts2 = int(os.path.getmtime(b))
            except Exception:
                ts2 = None
            background_url_local = "/fileproxy?path=" + b + (("&t=" + str(ts2)) if ts2 else "")

    plex_url, plex_token = _plex_url_parts()

    return {
        "library": library,
        "title": title,
        "year": year,
        "ratingKey": int(ratingKey),
        "folderName": folder,
        "folderExists": folder_exists,
        "posterExists": poster_exists,
        "backgroundExists": background_exists,
        "posterUrl": poster_url_local,
        "posterUrlPlex": f"{plex_url}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={plex_token}",
        "backgroundUrl": background_url_local,
        "backgroundUrlPlex": f"{plex_url}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={plex_token}",
    }

@router.get("/api/movie", summary="Single movie details (alias)")
def movie_api(library: str = Query(...), ratingKey: int = Query(...)):
    return movie(library=library, ratingKey=ratingKey)
