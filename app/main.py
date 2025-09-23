# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="KAM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import libraries, items, collections, upload, tv, fileproxy, movie, imports

app.include_router(libraries.router)
app.include_router(items.router)
app.include_router(collections.router)
app.include_router(upload.router)
app.include_router(tv.router)
app.include_router(movie.router)
app.include_router(imports.router)
app.include_router(fileproxy.router)

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
    print(f"[KAM] Skipping /assets mount. Not found in container: {ASSETS_ROOT!r}")

# ---- Static Web UI ----
app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
