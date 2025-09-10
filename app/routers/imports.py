from fastapi import APIRouter, HTTPException, Form
from typing import Optional, List
import os, io, requests
from PIL import Image

from ..services.plex import get_plex
from ..services.assets import sanitize_name, ensure_dir, save_bytes_as_poster_jpg
from .. import config

router = APIRouter()

def _download_poster_bytes(item) -> Optional[bytes]:
    plex = item._server  # PlexServer
    url = getattr(item, "posterUrl", None) or getattr(item, "thumbUrl", None)
    if not url:
        thumb = getattr(item, "thumb", None) or getattr(item, "art", None)
        if thumb:
            try:
                url = plex.url(thumb)
            except Exception:
                base = getattr(plex, "baseurl", None) or getattr(plex, "_baseurl", "")
                url = f"{base}{thumb}" if base else None
    if not url:
        return None
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 401 and config.PLEX_TOKEN:
            r = requests.get(url, headers={"X-Plex-Token": config.PLEX_TOKEN}, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

def _show_folder_name(title: str, year: Optional[int]) -> str:
    t = sanitize_name(title or "")
    if year:
        return f"{t} ({year})" if "(" not in t and ")" not in t else t
    return t or "Unknown"

def _delete_variants(dest_folder: str, base_no_ext: str):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(dest_folder, base_no_ext + ext)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def _save_bytes_as_named_jpg(data: bytes, dest_folder: str, base_no_ext: str) -> str:
    """Save image bytes into dest_folder/base_no_ext.jpg, normalizing to JPEG and
    deleting any existing variants for that basename."""
    ensure_dir(dest_folder)
    _delete_variants(dest_folder, base_no_ext)
    # Try to normalize with Pillow
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L", "P"):
            img = img.convert("RGB")
        out_path = os.path.join(dest_folder, base_no_ext + ".jpg")
        img.save(out_path, format="JPEG", quality=92, optimize=True)
        return out_path
    except Exception:
        # Fallback raw write (still use .jpg name)
        out_path = os.path.join(dest_folder, base_no_ext + ".jpg")
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path

@router.post("/import/poster", summary="Import a single item's poster from Plex")
def import_one(
    library: str = Form(...),
    ratingKey: int = Form(...),
    folderName: Optional[str] = Form(None),
    seasonIndex: Optional[int] = Form(None),
):
    plex = get_plex()

    # Resolve base output folder
    if library.lower() == "collections":
        base = config.COLLECTIONS_ROOT or "/assets/Collections"
    else:
        base = config.LIBRARY_MAPPINGS.get(library)
    if not base:
        raise HTTPException(404, f"Library '{library}' not configured")

    # Fetch item
    try:
        item = plex.fetchItem(int(ratingKey))
    except Exception as e:
        raise HTTPException(404, f"Item {ratingKey} not found: {e}")

    # Determine target show/movie folder (no Season subfolders for seasons)
    if folderName:
        show_folder = os.path.join(base, folderName)
    else:
        t = getattr(item, "title", None) or getattr(item, "parentTitle", None)
        y = getattr(item, "year", None) or getattr(getattr(item, "parent", None), "year", None)
        show_folder = os.path.join(base, _show_folder_name(t, y))

    ensure_dir(show_folder)

    # Download bytes
    data = _download_poster_bytes(item)
    if not data:
        raise HTTPException(404, "No poster available on Plex for this item")

    # Save according to kind:
    # - Series/Movie: poster.jpg (use save_bytes_as_poster_jpg helper)
    # - Season: SeasonXX.jpg in the show folder (NO subfolder)
    if seasonIndex is not None:
        idx = int(seasonIndex)
        base_no_ext = f"Season{idx:02d}"
        out_path = _save_bytes_as_named_jpg(data, show_folder, base_no_ext)
    else:
        out_path = save_bytes_as_poster_jpg(data, show_folder)

    return {"ok": True, "path": out_path}

@router.post("/import/library", summary="Bulk import posters for a library/collections")
def import_library(library: str = Form(...)):
    plex = get_plex()

    if library.lower() == "collections":
        base = config.COLLECTIONS_ROOT or "/assets/Collections"
        if not base:
            raise HTTPException(400, "COLLECTIONS_ROOT not configured")
        imported = skipped = 0
        errors: List[str] = []
        for sec in plex.library.sections():
            try:
                for coll in sec.collections():
                    try:
                        data = _download_poster_bytes(coll)
                        if not data: skipped += 1; continue
                        folder = os.path.join(base, sanitize_name(coll.title) or "Unknown")
                        ensure_dir(folder)
                        save_bytes_as_poster_jpg(data, folder)
                        imported += 1
                    except Exception as e:
                        errors.append(f"{getattr(coll,'title','Unknown')}: {e}")
            except Exception:
                continue
        return {"ok": True, "imported": imported, "skipped": skipped, "errors": errors}

    # normal libraries
    base = config.LIBRARY_MAPPINGS.get(library)
    if not base:
        raise HTTPException(404, f"Library '{library}' not configured")

    # Find section
    sec = None
    for s in plex.library.sections():
        if s.title == library:
            sec = s; break
    if not sec:
        raise HTTPException(404, f"Plex library '{library}' not found")

    stype = getattr(sec, "type", None)
    imported = skipped = 0
    errors: List[str] = []

    if stype == "movie":
        for m in sec.all():
            try:
                data = _download_poster_bytes(m)
                if not data: skipped += 1; continue
                title = getattr(m, "title", None)
                year = getattr(m, "year", None)
                folder = os.path.join(base, _show_folder_name(title, year))
                ensure_dir(folder)
                save_bytes_as_poster_jpg(data, folder)
                imported += 1
            except Exception as e:
                errors.append(f"{getattr(m,'title','Unknown')}: {e}")
    elif stype == "show":
        for show in sec.all():
            try:
                # show-level
                sdata = _download_poster_bytes(show)
                title = getattr(show, "title", None)
                year = getattr(show, "year", None)
                show_folder = os.path.join(base, _show_folder_name(title, year))
                ensure_dir(show_folder)
                if sdata:
                    save_bytes_as_poster_jpg(sdata, show_folder)
                    imported += 1
                else:
                    skipped += 1
                # seasons -> save as SeasonXX.jpg inside show folder (NO subfolders)
                try:
                    for season in show.seasons():
                        d = _download_poster_bytes(season)
                        idx = getattr(season, "index", None)
                        if idx is None:
                            continue
                        if d:
                            base_no_ext = f"Season{int(idx):02d}"
                            _save_bytes_as_named_jpg(d, show_folder, base_no_ext)
                            imported += 1
                        else:
                            skipped += 1
                except Exception:
                    pass
            except Exception as e:
                errors.append(f"{getattr(show,'title','Unknown')}: {e}")
    else:
        raise HTTPException(400, f"Unsupported library type: {stype}")

    return {"ok": True, "imported": imported, "skipped": skipped, "errors": errors}
