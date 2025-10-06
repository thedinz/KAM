# app/services/resolve.py
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Optional

from . import library_mappings as library_mappings_service

ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

_ILLEGAL_CTRL = re.compile(r"[\u0000-\u001F]")

_STOPWORDS = {"the", "a", "an", "movie", "film"}


def _tokenize_title(s: str) -> list[str]:
    """Normalize *s* into lowercase word tokens without punctuation."""
    if not s:
        return []

    normalized = unicodedata.normalize("NFKC", str(s))
    normalized = _ILLEGAL_CTRL.sub("", normalized)
    normalized = normalized.casefold()

    tokens = [tok for tok in re.split(r"[^0-9a-z]+", normalized) if tok]
    tokens = [tok for tok in tokens if tok not in _STOPWORDS]

    # Drop trailing year tokens such as "(2023)" so alternate title suffixes
    # compare on the meaningful words only.
    while tokens and re.fullmatch(r"\d{4}", tokens[-1]):
        tokens.pop()

    return tokens


def _normalize(s: str) -> str:
    """
    Build a comparison key that ignores punctuation/spacing/case differences,
    and common stop-words/year suffixes so
    'Batman: The Caped Crusader (2023)' == 'Batman Caped Crusader'.
    """
    return "".join(_tokenize_title(s))

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

def _candidate_bases(library: str) -> Iterable[str]:
    """Yield possible asset roots for *library* in priority order."""
    if not library:
        return []

    candidates: list[str] = []
    if library == "Collections":
        coll_base = library_mappings_service.get_collections_path()
        if coll_base:
            candidates.append(coll_base)
    else:
        asset_base = library_mappings_service.get_asset_path(library)
        if asset_base:
            candidates.append(asset_base)

        coll_base = library_mappings_service.get_collections_path(library)
        if coll_base and coll_base not in candidates:
            candidates.append(coll_base)

    if ASSETS_ROOT:
        fallback = os.path.join(ASSETS_ROOT, library)
        if fallback not in candidates:
            candidates.append(fallback)
        if ASSETS_ROOT not in candidates:
            candidates.append(ASSETS_ROOT)

    return candidates


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

    bases = list(dict.fromkeys(_candidate_bases(library)))
    for base in bases:
        if not os.path.isdir(base):
            continue
        try:
            resolved = _resolve_within_base(base, library, folder_name)
        except FileNotFoundError:
            continue
        if resolved:
            return resolved

    last_base = bases[0] if bases else os.path.join(ASSETS_ROOT, library)
    raise FileNotFoundError(f"Assets library not found: {last_base}")


def _resolve_within_base(base: str, library: str, folder_name: str) -> Optional[str]:
    if not os.path.isdir(base):
        return None

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
    raise FileNotFoundError(
        f"No existing asset folder matches '{folder_name}' in '{library}'"
    )
