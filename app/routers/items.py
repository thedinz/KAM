FALLBACK_URL = "/fallback.png"

from fastapi import APIRouter, HTTPException, Query
from math import ceil
from typing import Optional, List, Dict, Any
from ..services.plex import get_plex
from ..services.assets import folder_name_for, sanitize_name
from .. import config

router = APIRouter()

def _get_section_map():
    plex = get_plex()
    return {s.title: s for s in plex.library.sections()}

@router.get("/items", summary="Items")
def items(
    library: str = Query(..., description="Plex library name, or 'Collections'"),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
):
    plex = get_plex()
    sections = _get_section_map()

    out: List[Dict[str, Any]] = []
    q_norm = (query or "").strip().lower() or None

    if library.lower() == "collections":
        # Gather collections from all sections
        for sec in sections.values():
            try:
                for coll in sec.collections():
                    title = getattr(coll, "title", "") or ""
                    if q_norm and q_norm not in title.lower():
                        continue
                    rk = getattr(coll, "ratingKey", None)
                    posterUrl = (
                        f"{config.PLEX_URL}/library/metadata/{rk}/thumb?X-Plex-Token={config.PLEX_TOKEN}"
                        if rk else FALLBACK_URL
                    )
                    out.append({
                        "ratingKey": rk,
                        "title": title,
                        "year": None,
                        "folderName": sanitize_name(title) or "Unknown",
                        "posterUrl": posterUrl,
                        "type": "collection",
                    })
            except Exception:
                continue
    else:
        sec = sections.get(library)
        if not sec:
            raise HTTPException(404, f"Library '{library}' not found in Plex")

        # Prefer Plex-side search when possible
        if q_norm:
            try:
                y = int(query)  # type: ignore[arg-type]
                items = sec.search(year=y)
            except Exception:
                items = sec.search(title=query)
        else:
            items = sec.all()

        for m in items:
            title = getattr(m, "title", None)
            year = getattr(m, "year", None)
            rk = getattr(m, "ratingKey", None)
            folderName = folder_name_for(title, year)
            posterUrl = (
                f"{config.PLEX_URL}/library/metadata/{rk}/thumb?X-Plex-Token={config.PLEX_TOKEN}"
                if rk else FALLBACK_URL
            )
            out.append({
                "ratingKey": rk,
                "title": title,
                "year": year,
                "folderName": folderName,
                "posterUrl": posterUrl,
                "type": "item",
            })

        # Extra substring filter to refine Plex results if needed
        if q_norm:
            out = [i for i in out if q_norm in (i.get("title") or "").lower()]

    total = len(out)
    pages = max(1, ceil(total / page_size))
    page = min(page, pages)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "library": library,
        "page": page,
        "page_size": page_size,
        "total_count": total,
        "total_pages": pages,
        "items": out[start:end],
    }
