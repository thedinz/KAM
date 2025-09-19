# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="KAM")

# CORS (adjust if you lock this down)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
# IMPORTANT: keep these imports AFTER FastAPI() is created
from .routers import libraries, items, collections, upload, tv, fileproxy, movie, imports

# Register all routers (order doesn’t usually matter, but keep them together)
app.include_router(libraries.router)
app.include_router(items.router)
app.include_router(collections.router)
app.include_router(upload.router)
app.include_router(tv.router)          # <-- /api/show lives here
app.include_router(movie.router)
app.include_router(imports.router)     # <-- /api/import/* lives here
app.include_router(fileproxy.router)

# ---- Static Web UI ----
# Serves files from app/web at /
app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
