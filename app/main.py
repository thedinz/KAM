# app/main.py
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .logging_config import configure_logging
from .services import auth as auth_service

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="KAM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import (
    assets,
    auth,
    collections,
    exclusions,
    fileproxy,
    imports,
    items,
    libraries,
    movie,
    plex_proxy,
    settings,
    tv,
    upload,
    ui,
)

app.include_router(libraries.router)
app.include_router(items.router)
app.include_router(collections.router)
app.include_router(exclusions.router)
app.include_router(upload.router)
app.include_router(tv.router)
app.include_router(movie.router)
app.include_router(settings.router)
app.include_router(imports.router)
app.include_router(fileproxy.router)
app.include_router(plex_proxy.router)
app.include_router(assets.router)
app.include_router(auth.router)
app.include_router(ui.router)

WEB_DIR = Path(__file__).resolve().parent / "web"
SPA_INDEX = WEB_DIR / "index.html"
SPA_ASSETS_DIR = WEB_DIR / "spa-assets"
MOVIE_PAGE = WEB_DIR / "movie.html"


@app.get("/libraries/{library}/movies/{ratingKey}", include_in_schema=False)
async def movie_details_page(library: str, ratingKey: str):
    """Serve the SPA shell for movie details when available."""
    if SPA_INDEX.exists():
        return FileResponse(SPA_INDEX)
    return FileResponse(MOVIE_PAGE)


@app.get("/libraries", include_in_schema=False)
async def libraries_page():
    """Serve the main SPA shell when navigating to /libraries."""
    return FileResponse(SPA_INDEX)


@app.middleware("http")
async def enforce_auth(request: Request, call_next):
    if not auth_service.is_enabled():
        return await call_next(request)

    path = request.url.path
    exempt_prefixes = ("/spa-assets", "/assets", "/auth/")
    exempt_exact = {"/login", "/favicon.ico", "/favicon.svg"}

    if path in exempt_exact or path.startswith(exempt_prefixes):
        return await call_next(request)

    token = request.cookies.get(auth_service.cookie_name())
    if token and auth_service.validate_session(token):
        return await call_next(request)

    accept = request.headers.get("accept", "")
    if request.method == "GET" and "text/html" in accept:
        return RedirectResponse(url="/login")
    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

# ---- SAFE assets mount ----
# Prefer explicit envs if you set them; otherwise infer from COLLECTIONS_ROOT
# or use the standard container mount.
ASSETS_ROOT = os.getenv("KAM_ASSETS_ROOT") or os.getenv("ASSETS_ROOT")
if not ASSETS_ROOT:
    cr = os.getenv("COLLECTIONS_ROOT")
    if cr:
        ASSETS_ROOT = os.path.dirname(cr)
ASSETS_ROOT = ASSETS_ROOT or "/assets"

if ASSETS_ROOT and os.path.isdir(ASSETS_ROOT):
    # Serve files at the URL path /assets (matches your .env paths)
    app.mount("/assets", StaticFiles(directory=ASSETS_ROOT), name="assets")
else:
    logger.warning("Skipping /assets mount. Not found in container: %r", ASSETS_ROOT)

# Serve SPA build assets separately so they don't rely on the user-configured mount
if SPA_ASSETS_DIR.exists():
    app.mount("/spa-assets", StaticFiles(directory=SPA_ASSETS_DIR), name="spa-assets")
else:
    logger.warning("Skipping /spa-assets mount. Directory not found: %s", SPA_ASSETS_DIR)

# ---- Static Web UI ----
app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
