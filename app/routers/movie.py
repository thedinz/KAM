from fastapi import APIRouter, HTTPException, Query
import os

from ..services.plex import get_plex
from ..services.assets import folder_name_for
from .. import config

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

    # Map to asset root for this library
    base = config.LIBRARY_MAPPINGS.get(library)
    poster_exists = False
    background_exists = False
    poster_url_local = None
    background_url_local = None
    folder_exists = False

    if base:
        movie_folder = os.path.join(base, folder)
        folder_exists = os.path.isdir(movie_folder)
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
        "posterUrlPlex": f"{config.PLEX_URL}/library/metadata/{int(ratingKey)}/thumb?X-Plex-Token={config.PLEX_TOKEN}",
        "backgroundUrl": background_url_local,
        "backgroundUrlPlex": f"{config.PLEX_URL}/library/metadata/{int(ratingKey)}/art?X-Plex-Token={config.PLEX_TOKEN}",
    }

@router.get("/api/movie", summary="Single movie details (alias)")
def movie_api(library: str = Query(...), ratingKey: int = Query(...)):
    return movie(library=library, ratingKey=ratingKey)
