# app/routers/libraries.py
from fastapi import APIRouter, HTTPException
import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

router = APIRouter()

PLEX_URL   = os.environ.get("PLEX_URL", "").rstrip("/")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "")

def _plex_sections_json() -> Dict[str, Any]:
    if not PLEX_URL or not PLEX_TOKEN:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")
    url = f"{PLEX_URL}/library/sections"
    headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
    try:
        r = requests.get(url, headers=headers, params={"X-Plex-Token": PLEX_TOKEN}, timeout=15)
        # Plex may still return XML even if we ask for JSON; if so, we'll parse XML below.
        if r.headers.get("Content-Type", "").lower().startswith("application/json"):
            r.raise_for_status()
            return r.json()
        # fallthrough: treat as XML
        return {"_xml": r.text}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Plex sections request failed: {e}")

def _parse_sections_to_names(doc: Dict[str, Any]) -> List[str]:
    # JSON path: MediaContainer.Directory -> list of libs with {title, type}
    if "_xml" not in doc:
        mc = doc.get("MediaContainer") or {}
        dirs = mc.get("Directory") or []
        # some Plex servers return a single dict instead of list
        if isinstance(dirs, dict):
            dirs = [dirs]
        names: List[str] = []
        for d in dirs:
            title = d.get("title")
            if title:
                names.append(title)
        return sorted(names, key=lambda s: s.lower())

    # XML path:
    try:
        root = ET.fromstring(doc["_xml"])
        names: List[str] = []
        # The <Directory title="Movies" type="movie" ... /> elements are children of <MediaContainer>
        for node in root.findall(".//Directory"):
            title = node.attrib.get("title")
            if title:
                names.append(title)
        return sorted(names, key=lambda s: s.lower())
    except Exception:
        # If XML parse fails, fall back to empty (better than 500)
        return []

@router.get("/api/libraries")
def get_libraries() -> List[str]:
    """
    Return a simple array of library names.
    Your index.html already copes with either an array of strings or an array of objects with a 'name' field,
    but we'll keep it simple here and return names only.
    """
    data = _plex_sections_json()
    names = _parse_sections_to_names(data)
    if not names:
        # give a friendly error instead of empty 200 when Plex is reachable but nothing parsed
        raise HTTPException(status_code=404, detail="No libraries found from Plex")
    return names
