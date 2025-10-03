# app/routers/ui.py
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_SPA_INDEX = Path(__file__).resolve().parents[1] / "web" / "index.html"


@router.get("/libraries/{library}/shows/{ratingKey}")
async def show_details_page(library: str, ratingKey: str):
    """Serve the shared SPA shell so React can hydrate the route."""
    return FileResponse(_SPA_INDEX)
