# app/routers/ui.py
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_SHOW_HTML = Path("app/web/show-react.html").resolve()


@router.get("/libraries/{library}/shows/{ratingKey}")
async def show_details_page(library: str, ratingKey: str):
    """Serve the React show details experience for deep links."""
    return FileResponse(_SHOW_HTML)
