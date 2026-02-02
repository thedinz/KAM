from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..services import plex_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/plex/image")
def plex_image(
    path: Optional[str] = Query(None, description="Plex image path or URL"),
    ratingKey: Optional[str] = Query(None),
    kind: str = Query("thumb"),
):
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

    if not path:
        if not ratingKey:
            raise HTTPException(status_code=422, detail="path or ratingKey is required")
        kind_normalized = "art" if kind.lower() in ("art", "background") else "thumb"
        path = f"/library/metadata/{ratingKey}/{kind_normalized}"

    if path.startswith("http://") or path.startswith("https://"):
        if not path.startswith(cfg.url):
            raise HTTPException(status_code=403, detail="URL not allowed")
        url = path
    else:
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{cfg.url}{path}"

    headers = {"X-Plex-Token": cfg.token}

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"X-Plex-Token": cfg.token},
            stream=True,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Plex image proxy failed for %s: %s", urlsplit(url).path, exc)
        raise HTTPException(status_code=502, detail="Plex image proxy failed") from exc

    content_type = response.headers.get("Content-Type") or "application/octet-stream"
    return StreamingResponse(response.iter_content(chunk_size=1024 * 128), media_type=content_type)
