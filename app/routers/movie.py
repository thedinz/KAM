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

@router.get("/movie", summary="Single movie details")
def movie_detail(library: str = Query(...), ratingKey: int = Query(...)):
    section = _section_by_name(library)
    m = section.fetchItem(ratingKey)
    if not m or str(getattr(m, "type", "")) != "movie":
        raise HTTPException(404, "Movie not found")

    title = getattr(m, "title", None)
    year = getattr(m, "year", None)
    folder = folder_name_for(title or "", year)

    root = config.LIBRARY_MAPPINGS.get(library)
    poster_exists = background_exists = False
    poster_url_local = background_url_local = None
    if root:
        folder_path = os.path.join(root, folder)
        for base in ("poster", "background"):
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                p = os.path.join(folder_path, base + ext)
                if os.path.isfile(p):
                    if base == "poster":
                        poster_exists = True
                        poster_url_local = "/api/fileproxy?path=" + p
                    else:
                        background_exists = True
                        background_url_local = "/api/fileproxy?path=" + p
                    break

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
    }
