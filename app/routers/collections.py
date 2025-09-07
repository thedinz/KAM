from fastapi import APIRouter, Query
from math import ceil
from typing import Optional, List, Dict, Any
from ..services.plex import get_plex
from ..services.assets import sanitize_name
from .. import config

router = APIRouter()

@router.get("/collections", summary="Collections")
def collections(
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
):
    plex = get_plex()
    items: List[Dict[str, Any]] = []
    # Gather collections from all libraries
    for sec in plex.library.sections():
        try:
            for coll in sec.collections():
                rk = getattr(coll, "ratingKey", None)
                title = getattr(coll, "title", None)
                posterUrl = f"{config.PLEX_URL}/library/metadata/{rk}/thumb?X-Plex-Token={config.PLEX_TOKEN}"
                items.append({
                    "ratingKey": rk,
                    "title": title,
                    "year": None,
                    "folderName": sanitize_name(title or "Unknown"),
                    "posterUrl": posterUrl,
                })
        except Exception:
            continue

    # De-duplicate by title
    dedup: Dict[str, Dict[str, Any]] = {}
    for it in items:
        name = (it.get("title") or "").strip()
        if name and name not in dedup:
            dedup[name] = it
    items = list(dedup.values())

    if query:
        q = query.lower()
        items = [i for i in items if q in (i.get("title") or "").lower()]

    total = len(items)
    pages = max(1, ceil(total / page_size))
    page = min(page, pages)
    start, end = (page-1)*page_size, (page-1)*page_size + page_size
    return {
        "library": "Collections",
        "page": page,
        "page_size": page_size,
        "total_count": total,
        "total_pages": pages,
        "items": items[start:end],
    }
