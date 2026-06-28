# app/services/resolve.py
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Optional

from . import library_mappings as library_mappings_service

ASSETS_ROOT = os.environ.get("KAM_ASSETS_ROOT", "/assets")

_ILLEGAL_CTRL = re.compile(r"[\u0000-\u001F]")
_RELEASE_YEAR_PATTERN = r"(?:18|19|20|21)\d{2}"
_YEAR_SUFFIX_RE = re.compile(
    rf"^(?P<title>.*?)(?:\s*[\(\[\{{]\s*(?P<bracket_year>{_RELEASE_YEAR_PATTERN})\s*[\)\]\}}]|\s+(?P<bare_year>{_RELEASE_YEAR_PATTERN}))\s*$"
)
_YEAR_HINT_RE = re.compile(
    rf"(?:[\(\[\{{]\s*{_RELEASE_YEAR_PATTERN}\s*[\)\]\}}]|\b{_RELEASE_YEAR_PATTERN}\b)"
)
_BRACE_METADATA_RE = re.compile(
    rf"\{{\s*(?!{_RELEASE_YEAR_PATTERN}\s*\}})[^{{}}]*\}}"
)
_SQUARE_BLOCK_RE = re.compile(r"\[[^\[\]]+\]")
_PAREN_BLOCK_RE = re.compile(r"\([^()]+\)")
_TRAILING_RELEASE_GROUP_RE = re.compile(
    rf"(?P<title>.*(?:[\(\[\{{]\s*{_RELEASE_YEAR_PATTERN}\s*[\)\]\}}]|\b{_RELEASE_YEAR_PATTERN}\b))\s*-\s*[A-Za-z0-9][A-Za-z0-9._-]{{1,40}}\s*$"
)
_METADATA_CONTENT_RE = re.compile(
    r"\b(?:"
    r"tmdb|tmdbid|imdb|imdbid|tvdb|tvdbid|tvmaze|tvmazeid|edition|"
    r"custom|format|quality|proper|repack|remux|"
    r"bluray|blu-ray|webdl|web-dl|webrip|hdtv|dvd|uhd|hdr|hdr10|hdr10plus|"
    r"dolby\s*vision|dv|sdr|x264|x265|h264|h265|h\.264|h\.265|hevc|avc|"
    r"aac|ac3|eac3|dts|truehd|atmos|ddp?|imax|criterion|director|"
    r"directors|extended|alternate|theatrical|unrated|uncut|remaster|"
    r"remastered|restored|special|nf|amzn|hulu|"
    r"disney|hmax|pcok|release|group"
    r")\b|(?:\btt\d+\b)|(?:\b\d{3,4}p\b)|(?:\b\d{1,2}bit\b)|"
    r"(?:\b[57]\.1\b)|(?:\b3d\b)|(?:\bpg-?13\b)|(?:\bnc-?17\b)|"
    r"(?:\btv-(?:y7?|g|pg|14|ma)\b)",
    re.IGNORECASE,
)
_ID_LABEL_TOKENS = {"imdb", "imdbid", "tmdb", "tmdbid", "tvdb", "tvdbid", "tvmaze", "tvmazeid"}
_CERTIFICATION_TOKENS = {"g", "pg", "r", "nc", "tv", "y", "y7", "ma"}

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


def _looks_like_metadata_content(value: str) -> bool:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    if not text:
        return False
    if re.match(r"^(?:tmdb|imdb|tvdb)\s*[-:]", text):
        return True
    if re.match(r"^tvmaze\s*[-:]", text):
        return True
    if re.match(r"^edition\s*[-:]", text):
        return True
    if re.fullmatch(r"(?:g|pg|pg-?13|r|nc-?17|tv-(?:y7?|g|pg|14|ma))", text):
        return True
    return bool(_METADATA_CONTENT_RE.search(text))


def _has_release_year(value: str) -> bool:
    return bool(_YEAR_HINT_RE.search(str(value or "")))


def _metadata_suffix_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^0-9a-z]+", value.casefold())
        if token
    ]


def _is_metadata_token(token: str) -> bool:
    if not token:
        return False
    if token in _ID_LABEL_TOKENS or token in _CERTIFICATION_TOKENS:
        return True
    if re.fullmatch(r"tt\d+", token):
        return True
    if re.fullmatch(r"\d{3,4}p", token):
        return True
    if re.fullmatch(r"\d{1,2}bit", token):
        return True
    if re.fullmatch(r"[xh]26[45]|h26[45]|hevc|avc", token):
        return True
    if re.fullmatch(r"hdr10(?:plus)?|hdr|dv|sdr|3d", token):
        return True
    if re.fullmatch(r"aac|ac3|eac3|dts|truehd|atmos|ddp?", token):
        return True
    if re.fullmatch(r"[57]1", token):
        return True
    return bool(_METADATA_CONTENT_RE.search(token))


def _metadata_suffix_only(value: str) -> bool:
    raw = str(value or "")
    cleaned = _BRACE_METADATA_RE.sub(" ", raw)
    cleaned = _SQUARE_BLOCK_RE.sub(" ", cleaned)
    stripped = cleaned.strip(" ._-")
    if not stripped:
        return True

    if re.fullmatch(r"-\s*[A-Za-z0-9][A-Za-z0-9._-]{1,40}", cleaned.strip()):
        return True

    tokens = _metadata_suffix_tokens(stripped)
    if not tokens:
        return True

    metadata_count = sum(1 for token in tokens if _is_metadata_token(token))
    if metadata_count == 0:
        return False

    for index, token in enumerate(tokens):
        if _is_metadata_token(token):
            continue
        previous = tokens[index - 1] if index else ""
        if token.isdigit() and (
            metadata_count > 0 or previous in _ID_LABEL_TOKENS or len(token) >= 3
        ):
            continue
        # Release groups are often a final plain token after quality/media
        # metadata, for example "2160p BluRay x265 RARBG".
        if index == len(tokens) - 1 and re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,40}", token):
            continue
        return False
    return True


def _strip_metadata_after_year(text: str) -> str:
    matches = list(_YEAR_HINT_RE.finditer(text))
    for match in reversed(matches):
        suffix = text[match.end() :]
        if suffix and _metadata_suffix_only(suffix):
            return text[: match.end()].strip()
    return text


def _strip_folder_metadata(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _ILLEGAL_CTRL.sub("", text).strip()
    if not text:
        return ""

    text = _BRACE_METADATA_RE.sub(" ", text)

    def replace_square_block(match: re.Match[str]) -> str:
        content = match.group(0)[1:-1]
        before = text[: match.start()]
        if re.fullmatch(rf"\s*{_RELEASE_YEAR_PATTERN}\s*", content):
            return match.group(0)
        if match.start() == 0 and not _looks_like_metadata_content(content):
            return match.group(0)
        return " "

    def replace_paren_block(match: re.Match[str]) -> str:
        content = match.group(0)[1:-1]
        before = text[: match.start()]
        if re.fullmatch(rf"\s*{_RELEASE_YEAR_PATTERN}\s*", content):
            return match.group(0)
        if _has_release_year(before) or _looks_like_metadata_content(content):
            return " "
        return match.group(0)

    text = _SQUARE_BLOCK_RE.sub(replace_square_block, text)
    text = _PAREN_BLOCK_RE.sub(replace_paren_block, text)
    text = _TRAILING_RELEASE_GROUP_RE.sub(lambda match: match.group("title"), text)
    text = _strip_metadata_after_year(text)
    text = re.sub(r"\s+", " ", text).strip(" ._-")
    return text


def _fold_diacritics(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _extract_trailing_year(s: str) -> tuple[str, Optional[str]]:
    """Split a folder/title into title text and a trailing release year."""

    text = _strip_folder_metadata(s)
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
    normalized = _fold_diacritics(title_part).casefold()

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


def _is_ignorable_match_extra(token: str, index: int, tokens: tuple[str, ...]) -> bool:
    if _is_metadata_token(token):
        return True
    if token.isdigit() and len(token) >= 3:
        return True
    if index == 0 and len(token) == 1 and len(tokens) > 1:
        return True
    return False


def _tokens_contain_title_with_ignorable_extras(
    want_tokens: tuple[str, ...], candidate_tokens: tuple[str, ...]
) -> bool:
    if not want_tokens or not candidate_tokens:
        return False
    if len(candidate_tokens) <= len(want_tokens):
        return False

    span = len(want_tokens)
    for start in range(0, len(candidate_tokens) - span + 1):
        if tuple(candidate_tokens[start : start + span]) != want_tokens:
            continue
        extras = [
            (index, token)
            for index, token in enumerate(candidate_tokens)
            if index < start or index >= start + span
        ]
        if extras and all(
            _is_ignorable_match_extra(token, index, candidate_tokens)
            for index, token in extras
        ):
            return True
    return False


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

    def usable_token_subset(year: Optional[str]) -> bool:
        return _year_compatible(want_year, year)

    def has_explicit_year_conflict(
        normalized: str, tokens: tuple[str, ...]
    ) -> bool:
        if not want_year:
            return False
        for _, other_normalized, other_year, other_tokens in normalized_candidates:
            if other_normalized not in {normalized, want_key}:
                continue
            if not other_year or other_year == want_year:
                continue
            if _sequel_tokens_compatible(tokens, other_tokens):
                return True
        return False

    def usable_yearless(normalized: str, year: Optional[str], tokens: tuple[str, ...]) -> bool:
        return (
            bool(want_year)
            and year is None
            and _sequel_tokens_compatible(want_tokens, tokens)
            and not has_explicit_year_conflict(normalized, tokens)
        )

    def usable_yearless_token_subset(year: Optional[str]) -> bool:
        return (
            bool(want_year)
            and year is None
            and not has_explicit_year_conflict(want_key, want_tokens)
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

    # Existing Kometa libraries may use yearless folders even when Plex reports
    # a year. Accept that only for exact, unambiguous title matches and only
    # when another explicit-year sibling would not make the choice risky.
    yearless_exact_matches = [
        original
        for original, normalized, year, tokens in normalized_candidates
        if normalized == want_key and usable_yearless(normalized, year, tokens)
    ]
    if len(yearless_exact_matches) == 1:
        return yearless_exact_matches[0]
    if len(yearless_exact_matches) > 1:
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

    yearless_relaxed_matches = [
        original
        for original, normalized, year, tokens in normalized_candidates
        if normalized
        and (normalized.startswith(want_key) or want_key.startswith(normalized))
        and _relaxed_variant_tokens_compatible(want_tokens, tokens)
        and usable_yearless(normalized, year, tokens)
    ]
    if len(yearless_relaxed_matches) == 1:
        return yearless_relaxed_matches[0]
    if len(yearless_relaxed_matches) > 1:
        return None

    # 3) Allow official folder-token extras such as leading IDs,
    # certification, or TitleFirstCharacter when the actual title tokens remain
    # intact and contiguous.
    token_subset_matches = [
        original
        for original, _, year, tokens in normalized_candidates
        if _tokens_contain_title_with_ignorable_extras(want_tokens, tokens)
        and usable_token_subset(year)
    ]
    if len(token_subset_matches) == 1:
        return token_subset_matches[0]
    if len(token_subset_matches) > 1:
        return None

    yearless_token_subset_matches = [
        original
        for original, _, year, tokens in normalized_candidates
        if _tokens_contain_title_with_ignorable_extras(want_tokens, tokens)
        and usable_yearless_token_subset(year)
    ]
    if len(yearless_token_subset_matches) == 1:
        return yearless_token_subset_matches[0]
    if len(yearless_token_subset_matches) > 1:
        return None

    # 4) Fallback: closest fuzzy match when the similarity is very high and
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
