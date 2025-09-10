from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# ⬇️ Added `imports` here
from .routers import libraries, items, collections, upload, tv, fileproxy, movie, imports

app = FastAPI(title="KAM")
app.include_router(libraries.router,   prefix="/api")
app.include_router(items.router,       prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(upload.router,      prefix="/api")
app.include_router(tv.router,          prefix="/api")
app.include_router(movie.router,       prefix="/api")
app.include_router(fileproxy.router,   prefix="/api")
# ⬇️ Added this line so POST /api/import/poster works
app.include_router(imports.router,     prefix="/api")

# Serve UI
WEB_DIR = Path(__file__).parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
