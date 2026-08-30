# app/routers/upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import Any, Dict, List, Optional, Tuple
import io
import os
import posixpath
import re
import shutil
from zipfile import BadZipFile, ZipFile

from PIL import Image

from ..services import plex_artwork as plex_artwork_service
from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ASSET_VARIANT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MEDIUX_EPISODE_RE = re.compile(
    r"(?<![A-Za-z0-9])S(?:eason)?\s*0*(\d{1,3})\s*[-_. ]*E(?:pisode)?\s*0*(\d{1,3})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
MEDIUX_SEASON_RE = re.compile(
    r"(?<![A-Za-z0-9])Season\s*0*(\d{1,3})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
MEDIUX_POSTER_RE = re.compile(r"(?<![A-Za-z0-9])Poster(?![A-Za-z0-9])", re.IGNORECASE)

def _write_file(dest_path: str, up: UploadFile) -> None:
    # ensure parent exists (we only ever write into an existing dir)
    parent = os.path.dirname(dest_path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=422, detail="Asset folder does not exist")

    try:
        up.file.seek(0)
    except Exception:
        # Some file-like objects (e.g., SpooledTemporaryFile) always support seek,
        # but if they don't we simply continue from the current position.
        pass

    first_chunk = up.file.read(1024 * 1024)
    if not first_chunk:
        raise HTTPException(status_code=422, detail="Empty file")

    with open(dest_path, "wb") as f:
        f.write(first_chunk)
        shutil.copyfileobj(up.file, f)

def _parse_positive_index(value: str, label: str) -> int:
    try:
        idx = int(str(value).strip())
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid {label}: {value!r}")
    if idx < 0:
        raise HTTPException(status_code=422, detail=f"Invalid {label}: {value!r}")
    return idx

def _existing_asset_variants(dest_dir: str, base_name: str) -> List[str]:
    return [
        os.path.join(dest_dir, f"{base_name}{ext}")
        for ext in ASSET_VARIANT_EXTENSIONS
        if os.path.isfile(os.path.join(dest_dir, f"{base_name}{ext}"))
    ]

def _remove_asset_variants(dest_dir: str, base_name: str) -> None:
    for path in _existing_asset_variants(dest_dir, base_name):
        try:
            os.remove(path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to replace existing asset {path}: {exc}")

def _save_image_bytes_as_jpg(data: bytes, dest_dir: str, base_name: str) -> Tuple[str, bool]:
    parent = os.path.abspath(dest_dir)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=422, detail="Asset folder does not exist")

    replaced = bool(_existing_asset_variants(parent, base_name))
    _remove_asset_variants(parent, base_name)
    dest_path = os.path.join(parent, f"{base_name}.jpg")
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(dest_path, format="JPEG", quality=92, optimize=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise ValueError(f"Invalid image: {exc}")
    return dest_path, replaced

def _asset_label(base_name: str, asset_kind: str) -> str:
    if asset_kind == "poster":
        return "Series poster"
    if asset_kind == "background":
        return "Series background"
    if asset_kind == "season_background":
        season = base_name.split("_", 1)[0]
        return f"{season} background"
    if asset_kind == "season":
        return f"{base_name} poster"
    return f"{base_name} title card"


async def _upload_response(
    path: str,
    *,
    rating_key: Optional[str],
    kind: str,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {"ok": True, "path": path}
    plex_result = await run_in_threadpool(
        plex_artwork_service.auto_apply_result,
        rating_key,
        path,
        kind,
    )
    if plex_result is not None:
        response["plex"] = plex_result
    return response

def _classify_mediux_asset(filename: str) -> Optional[Dict[str, str]]:
    basename = posixpath.basename(filename or "").strip()
    if not basename or basename.startswith(".") or basename.startswith("__MACOSX"):
        return None

    stem, ext = os.path.splitext(basename)
    if ext.lower() not in IMAGE_EXTENSIONS:
        return None

    normalized = re.sub(r"[_\s]+", " ", stem).strip()
    lower = normalized.lower()
    has_backdrop = any(token in lower for token in ("backdrop", "background", "fanart"))

    episode_match = MEDIUX_EPISODE_RE.search(normalized)
    if episode_match:
        season_idx = int(episode_match.group(1))
        episode_idx = int(episode_match.group(2))
        base_name = f"S{season_idx:02d}E{episode_idx:02d}"
        return {"baseName": base_name, "kind": "title_card", "label": _asset_label(base_name, "title_card")}

    season_match = MEDIUX_SEASON_RE.search(normalized)
    if season_match:
        season_idx = int(season_match.group(1))
        base_name = f"Season{season_idx:02d}"
        if has_backdrop:
            base_name = f"{base_name}_background"
            return {"baseName": base_name, "kind": "season_background", "label": _asset_label(base_name, "season_background")}
        return {"baseName": base_name, "kind": "season", "label": _asset_label(base_name, "season")}

    if has_backdrop:
        return {"baseName": "background", "kind": "background", "label": _asset_label("background", "background")}

    if " - " not in stem and " – " not in stem and " — " not in stem:
        return {"baseName": "poster", "kind": "poster", "label": _asset_label("poster", "poster")}

    if MEDIUX_POSTER_RE.search(normalized):
        return {"baseName": "poster", "kind": "poster", "label": _asset_label("poster", "poster")}

    return None

def _import_mediux_zip_file(dest_dir: str, upload: UploadFile) -> Dict[str, Any]:
    try:
        upload.file.seek(0)
    except Exception:
        pass

    try:
        archive = ZipFile(upload.file)
    except BadZipFile:
        raise HTTPException(status_code=422, detail="Invalid zip file")

    imported: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []
    seen_targets = set()

    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            original_name = info.filename
            classification = _classify_mediux_asset(original_name)
            if not classification:
                skipped.append({"filename": original_name, "reason": "Unrecognized Mediux asset name"})
                continue

            base_name = classification["baseName"]
            if base_name in seen_targets:
                skipped.append({"filename": original_name, "reason": f"Duplicate target {base_name}.jpg"})
                continue
            seen_targets.add(base_name)

            try:
                data = archive.read(info)
                if not data:
                    raise ValueError("Empty image file")
                path, replaced = _save_image_bytes_as_jpg(data, dest_dir, base_name)
                imported.append({
                    "filename": original_name,
                    "asset": classification["label"],
                    "kind": classification["kind"],
                    "path": path,
                    "replaced": replaced,
                })
            except Exception as exc:
                errors.append({"filename": original_name, "error": str(exc)})

    return {
        "ok": bool(imported) and not errors,
        "imported": imported,
        "importedCount": len(imported),
        "replacedCount": sum(1 for entry in imported if entry.get("replaced")),
        "skipped": skipped,
        "skippedCount": len(skipped),
        "errors": errors,
        "errorCount": len(errors),
    }

@router.post("/api/upload")
async def upload_movie_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    file: UploadFile = File(...),
    kind: Optional[str] = Form("poster"),  # "poster" or "background"
    ratingKey: Optional[str] = Form(None),
):
    """
    Movie upload: write ONLY into an existing Kometa folder.
    If the folder doesn't exist, return 422. Never create a new folder.
    """
    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    filename = "background.jpg" if (kind or "").lower() == "background" else "poster.jpg"
    dest_path = os.path.join(dest_dir, filename)
    await run_in_threadpool(_write_file, dest_path, file)
    normalized_kind = "background" if filename == "background.jpg" else "poster"
    return await _upload_response(
        dest_path,
        rating_key=ratingKey,
        kind=normalized_kind,
    )

@router.post("/api/upload_show")
async def upload_show_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    kind: str = Form(...),                  # "poster" | "background"
    file: UploadFile = File(...),
    ratingKey: Optional[str] = Form(None),
):
    """
    Series upload: write ONLY into an existing Kometa folder.
    """
    if kind not in ("poster", "background"):
        raise HTTPException(status_code=422, detail=f"Invalid kind: {kind}")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    normalized_kind = "poster" if kind == "poster" else "background"
    dest_name = "poster.jpg" if normalized_kind == "poster" else "background.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    await run_in_threadpool(_write_file, dest_path, file)
    return await _upload_response(
        dest_path,
        rating_key=ratingKey,
        kind=normalized_kind,
    )

@router.post("/api/upload_season")
async def upload_season_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    season: str = Form(...),                # numeric string (e.g., "1", "02")
    kind: Optional[str] = Form("poster"),   # "poster" | "background"
    file: UploadFile = File(...),
    ratingKey: Optional[str] = Form(None),
):
    """
    Season upload: write ONLY into an existing Kometa folder.
    """
    try:
        idx = int(str(season).strip())
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid season: {season!r}")

    normalized_kind = (kind or "poster").strip().lower()
    if normalized_kind not in ("poster", "background"):
        raise HTTPException(status_code=422, detail=f"Invalid kind: {kind}")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dest_name = (
        f"Season{idx:02d}_background.jpg"
        if normalized_kind == "background"
        else f"Season{idx:02d}.jpg"
    )
    dest_path = os.path.join(dest_dir, dest_name)
    await run_in_threadpool(_write_file, dest_path, file)
    return await _upload_response(
        dest_path,
        rating_key=ratingKey,
        kind=normalized_kind,
    )

@router.post("/api/upload_title_card")
async def upload_title_card_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    season: str = Form(...),
    episode: str = Form(...),
    file: UploadFile = File(...),
    ratingKey: Optional[str] = Form(None),
):
    """
    Episode title card upload: write SxxEyy.jpg into an existing Kometa show folder.
    """
    season_idx = _parse_positive_index(season, "season")
    episode_idx = _parse_positive_index(episode, "episode")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dest_name = f"S{season_idx:02d}E{episode_idx:02d}.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    await run_in_threadpool(_write_file, dest_path, file)
    return await _upload_response(dest_path, rating_key=ratingKey, kind="poster")

@router.post("/api/import/mediux-zip")
async def import_mediux_zip_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Import a Mediux series zip into an existing Kometa show asset folder.
    """
    filename = file.filename or ""
    if filename and not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="Mediux import requires a .zip file")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return await run_in_threadpool(_import_mediux_zip_file, dest_dir, file)
