# app/services/resolve.py
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Optional

from . import library_mappings as library_mappings_service

ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

_ILLEGAL_CTRL = re.compile(r"[\u0000-\u001F]")
_YEAR_SUFFIX_RE = re.compile(
    r"^(?P<title>.*?)(?:\s*[\(\[\{]\s*(?P<bracket_year>(?:18|19|20|21)\d{2})\s*[\)\]\}]|\s+(?P<bare_year>(?:18|19|20|21)\d{2}))\s*$"
)

_STOPWORDS = {"the", "a", "an", "movie", "film"}
_RELAXED_VARIANT_SUFFIXES = {
    "alternate",
    "anniversary",
    "collectors",
    "complete",
    "cut",
    "director",
    "directors",
    "edition",
    "edit",
    "extended",
    "final",
    "imax",
    "remaster",
    "remastered",
    "restored",
    "special",
    "theatrical",
    "ultimate",
    "uncut",
    "unrated",
    "version",
}
_SEQUEL_MARKERS = {"book", "chapter", "episode", "part", "vol", "volume"}
_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_ROMAN_NUMERALS = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}


def _extract_trailing_year(s: str) -> tuple[str, Optional[str]]:
    """Split a folder/title into title text and a trailing release year."""

    text = unicodedata.normalize("NFKC", str(s or ""))
    text = _ILLEGAL_CTRL.sub("", text).strip()
    if not text:
        return "", None

    match = _YEAR_SUFFIX_RE.match(text)
    if not match:
        return text, None

    title = (match.group("title") or "").strip()
    year = match.group("bracket_year") or match.group("bare_year")
    if not title or not re.search(r"[0-9A-Za-z]", title):
        return text, None
    return title, year


def _tokenize_title(s: str) -> tuple[list[str], Optional[str]]:
    """Return normalized title tokens and an optional trailing year."""
    if not s:
        return [], None

    title_part, year = _extract_trailing_year(s)
    normalized = title_part.casefold()

    raw_tokens = [tok for tok in re.split(r"[^0-9a-z]+", normalized) if tok]
    filtered_tokens = [tok for tok in raw_tokens if tok not in _STOPWORDS]

    # Stop words help compare titles like "The Super Mario Bros. Movie" with
    # "Super Mario Bros. (2023)", but they should never erase the whole title
    # or leave only a sequel number behind.
    if filtered_tokens and not all(tok.isdigit() for tok in filtered_tokens):
        tokens = filtered_tokens
    else:
        tokens = raw_tokens

    return tokens, year


def _normalize(s: str) -> str:
    """
    Build a comparison key that ignores punctuation/spacing/case differences,
    and common stop-words/year suffixes so
    'Batman: The Caped Crusader (2023)' == 'Batman Caped Crusader'.
    """
    tokens, _ = _tokenize_title(s)
    return "".join(tokens)


def _comparison_parts(s: str) -> tuple[str, Optional[str], tuple[str, ...]]:
    tokens, year = _tokenize_title(s)
    return "".join(tokens), year, tuple(tokens)


def _normalize_with_year(s: str) -> tuple[str, Optional[str]]:
    """Return the normalized comparison key and trailing year (if any)."""

    normalized, year, _ = _comparison_parts(s)
    return normalized, year


def _sequel_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Return title identity numbers such as the 2 or II in a sequel title."""

    sequel_tokens: list[str] = []
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else ""
        final_token = index == len(tokens) - 1

        if token.isdigit():
            sequel_tokens.append(token)
        elif token in _NUMBER_WORDS and (final_token or previous in _SEQUEL_MARKERS):
            sequel_tokens.append(_NUMBER_WORDS[token])
        elif token in _ROMAN_NUMERALS and (
            len(token) > 1 or final_token or previous in _SEQUEL_MARKERS
        ):
            sequel_tokens.append(_ROMAN_NUMERALS[token])

    return tuple(sequel_tokens)


def _sequel_tokens_compatible(
    want_tokens: tuple[str, ...], candidate_tokens: tuple[str, ...]
) -> bool:
    return _sequel_tokens(want_tokens) == _sequel_tokens(candidate_tokens)


def _relaxed_variant_tokens_compatible(
    want_tokens: tuple[str, ...], candidate_tokens: tuple[str, ...]
) -> bool:
    """Allow known edition suffixes, not arbitrary title prefix matches."""

    if len(want_tokens) == len(candidate_tokens):
        return False

    if len(want_tokens) < len(candidate_tokens):
        shorter, longer = want_tokens, candidate_tokens
    else:
        shorter, longer = candidate_tokens, want_tokens

    if tuple(longer[: len(shorter)]) != shorter:
        return False

    suffix = longer[len(shorter) :]
    return bool(suffix) and all(token in _RELAXED_VARIANT_SUFFIXES for token in suffix)


def _year_compatible(want_year: Optional[str], candidate_year: Optional[str]) -> bool:
    if want_year:
        return candidate_year == want_year
    return True


def _best_match(candidates, want: str) -> Optional[str]:
    """Return the safest existing folder match for a normalized target."""
    want_key, want_year, want_tokens = _comparison_parts(want)
    if not want_key:
        return None

    normalized_candidates = [
        (c, *_comparison_parts(c)) for c in candidates if c
    ]

    def usable(year: Optional[str], tokens: tuple[str, ...]) -> bool:
        return _year_compatible(want_year, year) and _sequel_tokens_compatible(
            want_tokens, tokens
        )

    # 1) Exact normalized match, but only when the year and sequel markers are
    # compatible. If a year-scoped Plex item cannot find the same year on disk,
    # leave it unmatched instead of borrowing a sibling movie's folder.
    exact_matches = [
        original
        for original, normalized, year, tokens in normalized_candidates
        if normalized == want_key and usable(year, tokens)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None

    # 2) Relaxed prefix match for legitimate suffixes such as "Extended
    # Edition", still requiring compatible years and sequel numbers.
    relaxed_matches = [
        original
        for original, normalized, year, tokens in normalized_candidates
        if normalized
        and (normalized.startswith(want_key) or want_key.startswith(normalized))
        and _relaxed_variant_tokens_compatible(want_tokens, tokens)
        and usable(year, tokens)
    ]
    if len(relaxed_matches) == 1:
        return relaxed_matches[0]
    if len(relaxed_matches) > 1:
        return None

    # 3) Fallback: closest fuzzy match when the similarity is very high and
    # there is a clear winner.
    scored_matches: list[tuple[float, str, float, tuple[int, int]]] = []
    for original, normalized, year, tokens in normalized_candidates:
        if not normalized or not usable(year, tokens):
            continue
        if (
            normalized.startswith(want_key) or want_key.startswith(normalized)
        ) and not _relaxed_variant_tokens_compatible(want_tokens, tokens):
            continue
        matcher = SequenceMatcher(a=normalized, b=want_key)
        base_ratio = matcher.ratio()
        score = base_ratio

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

        scored_matches.append((score, original, base_ratio, (len_norm, len_want)))

    scored_matches.sort(key=lambda item: item[0], reverse=True)
    if not scored_matches:
        return None

    best_score, best_candidate, best_base_ratio, best_lengths = scored_matches[0]
    if best_score < 0.86:
        return None

    # Similar candidates mean the resolver is guessing. Surface the item as
    # unmatched so the user can pair it manually.
    if len(scored_matches) > 1 and scored_matches[1][0] >= best_score - 0.03:
        return None

    len_norm, len_want = best_lengths
    shorter = min(len_norm, len_want)
    longer = max(len_norm, len_want)

    # Disallow fuzzy matches for extremely short titles or wildly
    # different-length strings so "It" does not match
    # "In association with Marvel".
    if shorter < 4:
        return None
    if longer and shorter and (longer / shorter) > 2.5:
        return None

    # Also require the overall ratio to be reasonably close; this ensures
    # we only accept near-identical titles.
    if best_base_ratio < 0.7:
        return None

    return best_candidate


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


def find_existing_dir_in_base(base: str, folder_name: str) -> Optional[str]:
    """Return the resolved directory within *base* if present."""

    if not base or not folder_name:
        return None

    try:
        return _resolve_within_base(base, "Collections", folder_name)
    except FileNotFoundError:
        return None
