# app/routers/ui.py
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_WEB_DIR = Path(__file__).resolve().parents[1] / "web"
_SPA_INDEX = _WEB_DIR / "index.html"


@router.get("/libraries/{library}/shows/{ratingKey}")
async def show_details_page(library: str, ratingKey: str):
    """Serve the SPA shell for direct navigation to show details."""
    return FileResponse(_SPA_INDEX)


@router.get("/libraries/{library}/not-ready")
async def not_ready_page(library: str):
    """Serve the SPA shell for the not-ready view."""
    return FileResponse(_SPA_INDEX)


@router.get("/settings", include_in_schema=False)
async def settings_page():
    """Serve the SPA shell when navigating to /settings."""
    return FileResponse(_SPA_INDEX)


@router.get("/login", include_in_schema=False)
async def login_page():
    """Serve the SPA shell for the login route."""
    return FileResponse(_SPA_INDEX)
