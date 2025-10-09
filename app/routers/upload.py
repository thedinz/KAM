# app/routers/upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import inspect
import os

from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _write_file(dest_path: str, up: UploadFile) -> None:
    # ensure parent exists (we only ever write into an existing dir)
    parent = os.path.dirname(dest_path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=422, detail="Asset folder does not exist")

    # FastAPI's UploadFile exposes async helpers that always work regardless of
    # whether the underlying stream is spooled to disk or kept in memory.
    try:
        await _maybe_await(up.seek(0))
    except Exception:
        try:
            up.file.seek(0)
        except Exception:
            pass

    try:
        first_chunk = await _maybe_await(up.read(1024 * 1024))
        if not first_chunk:
            raise HTTPException(status_code=422, detail="Empty file")

        with open(dest_path, "wb") as f:
            f.write(first_chunk)
            while True:
                chunk = await _maybe_await(up.read(1024 * 1024))
                if not chunk:
                    break
                f.write(chunk)
    finally:
        try:
            await _maybe_await(up.close())
        except Exception:
            try:
                up.file.close()
            except Exception:
                pass

@router.post("/api/upload")
async def upload_movie_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    file: UploadFile = File(...),
    kind: Optional[str] = Form("poster"),  # "poster" or "background"
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
    await _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}

@router.post("/api/upload_show")
async def upload_show_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    kind: str = Form(...),                  # "poster" | "background"
    file: UploadFile = File(...),
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

    dest_name = "poster.jpg" if kind == "poster" else "background.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    await _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}

@router.post("/api/upload_season")
async def upload_season_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    season: str = Form(...),                # numeric string (e.g., "1", "02")
    file: UploadFile = File(...),
):
    """
    Season upload: write ONLY into an existing Kometa folder.
    """
    try:
        idx = int(str(season).strip())
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid season: {season!r}")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dest_name = f"Season{idx:02d}.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    await _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}
