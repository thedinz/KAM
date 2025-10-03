# app/main.py
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .logging_config import configure_logging

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
    collections,
    fileproxy,
    imports,
    items,
    libraries,
    movie,
    tv,
    upload,
    ui,
)

app.include_router(libraries.router)
app.include_router(items.router)
app.include_router(collections.router)
app.include_router(upload.router)
app.include_router(tv.router)
app.include_router(movie.router)
app.include_router(imports.router)
app.include_router(fileproxy.router)
app.include_router(assets.router)
app.include_router(ui.router)

WEB_DIR = Path(__file__).resolve().parent / "web"
SPA_INDEX = WEB_DIR / "index.html"
SPA_ASSETS_DIR = WEB_DIR / "spa-assets"


@app.get("/libraries/{library}/movies/{ratingKey}", include_in_schema=False)
async def movie_details_page(library: str, ratingKey: str):
    """Serve the SPA shell so client-side routing can take over."""
    return FileResponse(SPA_INDEX)


@app.get("/libraries", include_in_schema=False)
async def libraries_page():
    """Serve the main SPA shell when navigating to /libraries."""
    return FileResponse(SPA_INDEX)

# ---- SAFE assets mount (env-driven) ----
# Prefer explicit envs if you set them; otherwise infer from COLLECTIONS_ROOT.
ASSETS_ROOT = os.getenv("KAM_ASSETS_ROOT") or os.getenv("ASSETS_ROOT")
if not ASSETS_ROOT:
    cr = os.getenv("COLLECTIONS_ROOT")
    if cr:
        ASSETS_ROOT = os.path.dirname(cr)

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
