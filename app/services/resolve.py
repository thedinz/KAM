# app/services/resolve.py
import os
import unicodedata
import re
from difflib import SequenceMatcher
from typing import Optional

ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

_ILLEGAL_CTRL = re.compile(r"[\u0000-\u001F]")

def _normalize(s: str) -> str:
    """
    Build a comparison key that ignores punctuation/spacing/case differences,
    so 'Batman: The Caped Crusader' == 'Batman The Caped Crusader'.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _ILLEGAL_CTRL.sub("", s)
    s = s.casefold()
    # drop all non-alphanumeric chars
    s = "".join(ch for ch in s if ch.isalnum())
    return s

def _best_match(candidates, want: str) -> Optional[str]:
    """Return the candidate whose normalized name equals the normalized target."""
    want_key = _normalize(want)
    if not want_key:
        return None

    normalized_candidates = [(c, _normalize(c)) for c in candidates]

    # exact normalized match first
    for original, normalized in normalized_candidates:
        if normalized == want_key:
            return original

    # relaxed: startswith normalized (helps with extra year suffixes, etc.)
    for original, normalized in normalized_candidates:
        if normalized.startswith(want_key) or want_key.startswith(normalized):
            return original

    # fallback: closest fuzzy match when the similarity is very high
    best_score = 0.0
    best_candidate = None
    for original, normalized in normalized_candidates:
        if not normalized:
            continue
        matcher = SequenceMatcher(a=normalized, b=want_key)
        score = matcher.ratio()

        # Evaluate how much of the shorter string aligns contiguously with the
        # longer one to tolerate small insertions like "Extended Edition".
        len_norm = len(normalized)
        len_want = len(want_key)
        if len_norm and len_want:
            if len_norm >= len_want:
                longer, shorter = normalized, want_key
            else:
                longer, shorter = want_key, normalized
            window_match = SequenceMatcher(a=longer, b=shorter).find_longest_match(
                0, len(longer), 0, len(shorter)
            )
            if shorter:
                score = max(score, window_match.size / len(shorter))

        if score > best_score:
            best_score = score
            best_candidate = original

    # require a conservative minimum similarity to avoid unrelated matches
    if best_score >= 0.86:
        return best_candidate
    return None

def resolve_existing_dir_or_422(library: str, folder_name: str) -> str:
    """
    Resolve the asset directory for (library, folder_name) to an EXISTING folder.
    - Never creates directories.
    - Matching is normalization-based (colon stripped among other punctuation)
      with an additional high-similarity fuzzy fallback for near-identical
      directory names.
    - Raises FileNotFoundError for caller to convert to 422.
    """
    if not library:
        raise FileNotFoundError("Missing library")
    base = os.path.join(ASSETS_ROOT, library)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Assets library not found: {base}")

    raw = (folder_name or "").strip()
    if not raw:
        raise FileNotFoundError("Empty folderName")

    # 1) Fast path: exact dir exists
    exact = os.path.join(base, raw)
    if os.path.isdir(exact):
        return exact

    # 2) Try normalized match among existing dirs
    try:
        entries = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    except Exception:
        entries = []
    match = _best_match(entries, raw)
    if match:
        return os.path.join(base, match)

    # Not found => caller should 422 (do not create)
    raise FileNotFoundError(f"No existing asset folder matches '{folder_name}' in '{library}'")
