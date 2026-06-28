import { responseErrorMessage, safeJson } from './api.js';

const ASSIGN_BATCH_SIZE = 500;
const RELEASE_YEAR_PATTERN = '(?:18|19|20|21)\\d{2}';
const YEAR_SUFFIX_RE = new RegExp(
  `^(.*?)(?:\\s*[\\(\\[\\{]\\s*(${RELEASE_YEAR_PATTERN})\\s*[\\)\\]\\}]|\\s+(${RELEASE_YEAR_PATTERN}))\\s*$`
);
const YEAR_HINT_RE = new RegExp(
  `(?:[\\(\\[\\{]\\s*${RELEASE_YEAR_PATTERN}\\s*[\\)\\]\\}]|\\b${RELEASE_YEAR_PATTERN}\\b)`,
  'g'
);
const YEAR_HINT_TEST_RE = new RegExp(
  `(?:[\\(\\[\\{]\\s*${RELEASE_YEAR_PATTERN}\\s*[\\)\\]\\}]|\\b${RELEASE_YEAR_PATTERN}\\b)`
);
const BRACE_METADATA_RE = new RegExp(`\\{\\s*(?!${RELEASE_YEAR_PATTERN}\\s*\\})[^{}]*\\}`, 'g');
const SQUARE_BLOCK_RE = /\[[^\[\]]+\]/g;
const PAREN_BLOCK_RE = /\([^()]+\)/g;
const TRAILING_RELEASE_GROUP_RE = new RegExp(
  `(.*(?:[\\(\\[\\{]\\s*${RELEASE_YEAR_PATTERN}\\s*[\\)\\]\\}]|\\b${RELEASE_YEAR_PATTERN}\\b))\\s*-\\s*[A-Za-z0-9][A-Za-z0-9._-]{1,40}\\s*$`
);
const METADATA_CONTENT_RE =
  /\b(?:tmdb|tmdbid|imdb|imdbid|tvdb|tvdbid|tvmaze|tvmazeid|edition|custom|format|quality|proper|repack|remux|bluray|blu-ray|webdl|web-dl|webrip|hdtv|dvd|uhd|hdr|hdr10|hdr10plus|dolby\s*vision|dv|sdr|x264|x265|h264|h265|h\.264|h\.265|hevc|avc|aac|ac3|eac3|dts|truehd|atmos|ddp?|imax|criterion|director|directors|extended|alternate|theatrical|unrated|uncut|remaster|remastered|restored|special|nf|amzn|hulu|disney|hmax|pcok|release|group)\b|\btt\d+\b|\b\d{3,4}p\b|\b\d{1,2}bit\b|\b[57]\.1\b|\b3d\b|\bpg-?13\b|\bnc-?17\b|\btv-(?:y7?|g|pg|14|ma)\b/i;
const ID_LABEL_TOKENS = new Set(['imdb', 'imdbid', 'tmdb', 'tmdbid', 'tvdb', 'tvdbid', 'tvmaze', 'tvmazeid']);
const CERTIFICATION_TOKENS = new Set(['g', 'pg', 'r', 'nc', 'tv', 'y', 'y7', 'ma']);
const STOPWORDS = new Set(['the', 'a', 'an', 'movie', 'film']);
const RELAXED_VARIANT_SUFFIXES = new Set([
  'alternate',
  'anniversary',
  'collectors',
  'complete',
  'cut',
  'director',
  'directors',
  'edition',
  'edit',
  'extended',
  'final',
  'imax',
  'remaster',
  'remastered',
  'restored',
  'special',
  'theatrical',
  'ultimate',
  'uncut',
  'unrated',
  'version',
]);
const SEQUEL_MARKERS = new Set(['book', 'chapter', 'episode', 'part', 'vol', 'volume']);
const NUMBER_WORDS = new Map([
  ['one', '1'],
  ['two', '2'],
  ['three', '3'],
  ['four', '4'],
  ['five', '5'],
  ['six', '6'],
  ['seven', '7'],
  ['eight', '8'],
  ['nine', '9'],
  ['ten', '10'],
]);
const ROMAN_NUMERALS = new Map([
  ['i', '1'],
  ['ii', '2'],
  ['iii', '3'],
  ['iv', '4'],
  ['v', '5'],
  ['vi', '6'],
  ['vii', '7'],
  ['viii', '8'],
  ['ix', '9'],
  ['x', '10'],
]);

function foldDiacritics(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '');
}

function looksLikeMetadataContent(value) {
  const text = String(value || '')
    .normalize('NFKC')
    .toLowerCase()
    .trim();
  if (!text) return false;
  if (/^(?:tmdb|imdb|tvdb)\s*[-:]/i.test(text)) return true;
  if (/^tvmaze\s*[-:]/i.test(text)) return true;
  if (/^edition\s*[-:]/i.test(text)) return true;
  if (/^(?:g|pg|pg-?13|r|nc-?17|tv-(?:y7?|g|pg|14|ma))$/i.test(text)) return true;
  return METADATA_CONTENT_RE.test(text);
}

function hasReleaseYear(value) {
  return YEAR_HINT_TEST_RE.test(String(value || ''));
}

function metadataSuffixTokens(value) {
  return String(value || '')
    .toLowerCase()
    .split(/[^0-9a-z]+/)
    .filter(Boolean);
}

function isMetadataToken(token) {
  if (!token) return false;
  if (ID_LABEL_TOKENS.has(token) || CERTIFICATION_TOKENS.has(token)) return true;
  if (/^tt\d+$/.test(token)) return true;
  if (/^\d{3,4}p$/.test(token)) return true;
  if (/^\d{1,2}bit$/.test(token)) return true;
  if (/^(?:[xh]26[45]|h26[45]|hevc|avc)$/.test(token)) return true;
  if (/^(?:hdr10(?:plus)?|hdr|dv|sdr|3d)$/.test(token)) return true;
  if (/^(?:aac|ac3|eac3|dts|truehd|atmos|ddp?)$/.test(token)) return true;
  if (/^[57]1$/.test(token)) return true;
  return METADATA_CONTENT_RE.test(token);
}

function metadataSuffixOnly(value) {
  const raw = String(value || '');
  const cleaned = raw.replace(BRACE_METADATA_RE, ' ').replace(SQUARE_BLOCK_RE, ' ');
  const stripped = cleaned.trim().replace(/^[ ._-]+|[ ._-]+$/g, '');
  if (!stripped) return true;
  if (/^-\s*[A-Za-z0-9][A-Za-z0-9._-]{1,40}$/.test(cleaned.trim())) return true;

  const tokens = metadataSuffixTokens(stripped);
  if (!tokens.length) return true;

  const metadataCount = tokens.filter(isMetadataToken).length;
  if (metadataCount === 0) return false;

  return tokens.every((token, index) => {
    if (isMetadataToken(token)) return true;
    const previous = index > 0 ? tokens[index - 1] : '';
    if (/^\d+$/.test(token) && (metadataCount > 0 || ID_LABEL_TOKENS.has(previous) || token.length >= 3)) {
      return true;
    }
    return index === tokens.length - 1 && /^[a-z0-9][a-z0-9._-]{1,40}$/.test(token);
  });
}

function stripMetadataAfterYear(text) {
  const matches = Array.from(String(text || '').matchAll(YEAR_HINT_RE));
  for (let index = matches.length - 1; index >= 0; index -= 1) {
    const match = matches[index];
    const end = (match.index || 0) + match[0].length;
    const suffix = text.slice(end);
    if (suffix && metadataSuffixOnly(suffix)) {
      return text.slice(0, end).trim();
    }
  }
  return text;
}

function stripFolderMetadata(value) {
  let text = String(value || '')
    .normalize('NFKC')
    .replace(/[\u0000-\u001f]/g, '')
    .trim();
  if (!text) return '';

  text = text.replace(BRACE_METADATA_RE, ' ');
  text = text.replace(SQUARE_BLOCK_RE, (match, offset) => {
    const content = match.slice(1, -1);
    if (new RegExp(`^\\s*${RELEASE_YEAR_PATTERN}\\s*$`).test(content)) return match;
    if (offset === 0 && !looksLikeMetadataContent(content)) return match;
    return ' ';
  });
  text = text.replace(PAREN_BLOCK_RE, (match, offset) => {
    const content = match.slice(1, -1);
    const before = text.slice(0, offset);
    if (new RegExp(`^\\s*${RELEASE_YEAR_PATTERN}\\s*$`).test(content)) return match;
    if (hasReleaseYear(before) || looksLikeMetadataContent(content)) return ' ';
    return match;
  });
  text = text.replace(TRAILING_RELEASE_GROUP_RE, '$1');
  text = stripMetadataAfterYear(text);
  return text.replace(/\s+/g, ' ').replace(/^[ ._-]+|[ ._-]+$/g, '');
}

function normalizeTitle(value) {
  if (!value) return { key: '', year: null, tokens: [] };
  const normalized = stripFolderMetadata(value);
  const yearMatch = YEAR_SUFFIX_RE.exec(normalized);
  const titlePart = yearMatch ? String(yearMatch[1] || '').trim() : normalized;
  const year = yearMatch ? yearMatch[2] || yearMatch[3] || null : null;
  const tokens = normalized
    ? foldDiacritics(titlePart)
        .toLowerCase()
        .split(/[^0-9a-z]+/)
        .filter(Boolean)
    : [];
  const filteredTokens = tokens.filter((token) => !STOPWORDS.has(token));
  const finalTokens =
    filteredTokens.length && !filteredTokens.every((token) => /^\d+$/.test(token))
      ? filteredTokens
      : tokens;
  return { key: finalTokens.join(''), year, tokens: finalTokens };
}

function buildFolderIndex(names = []) {
  return names
    .map((name) => {
      const normalizedName = String(name || '').trim();
      if (!normalizedName) return null;
      return { name: normalizedName, ...normalizeTitle(normalizedName) };
    })
    .filter((entry) => entry?.key);
}

function pickFolderMatch(candidate, index) {
  const { key, year, tokens } = normalizeTitle(candidate);
  if (!key) return '';

  const sequelTokens = getSequelTokens(tokens);
  const isUsable = (entry) =>
    (!year || entry.year === year) && equalTokens(sequelTokens, getSequelTokens(entry.tokens));
  const hasExplicitYearConflict = (entry, comparisonTokens = entry.tokens) =>
    Boolean(year) &&
    index.some(
      (other) =>
        (other.key === entry.key || other.key === key) &&
        other.year &&
        other.year !== year &&
        equalTokens(getSequelTokens(comparisonTokens), getSequelTokens(other.tokens))
    );
  const isUsableYearless = (entry) =>
    Boolean(year) &&
    !entry.year &&
    equalTokens(sequelTokens, getSequelTokens(entry.tokens)) &&
    !hasExplicitYearConflict(entry);
  const isUsableTokenSubset = (entry) => !year || entry.year === year;
  const isUsableYearlessTokenSubset = (entry) =>
    Boolean(year) && !entry.year && !hasExplicitYearConflict(entry, tokens);

  for (const entry of index) {
    if (entry.key !== key) continue;
    if (!isUsable(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (entry.key !== key) continue;
    if (!isUsableYearless(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!(entry.key.startsWith(key) || key.startsWith(entry.key))) continue;
    if (!hasEditionSuffix(tokens, entry.tokens)) continue;
    if (!isUsable(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!(entry.key.startsWith(key) || key.startsWith(entry.key))) continue;
    if (!hasEditionSuffix(tokens, entry.tokens)) continue;
    if (!isUsableYearless(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!tokensContainTitleWithIgnorableExtras(tokens, entry.tokens)) continue;
    if (!isUsableTokenSubset(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!tokensContainTitleWithIgnorableExtras(tokens, entry.tokens)) continue;
    if (!isUsableYearlessTokenSubset(entry)) continue;
    return entry.name;
  }
  return '';
}

function getSequelTokens(tokens = []) {
  return tokens.reduce((result, token, index) => {
    const previous = index > 0 ? tokens[index - 1] : '';
    const finalToken = index === tokens.length - 1;

    if (/^\d+$/.test(token)) {
      result.push(token);
    } else if (NUMBER_WORDS.has(token) && (finalToken || SEQUEL_MARKERS.has(previous))) {
      result.push(NUMBER_WORDS.get(token));
    } else if (
      ROMAN_NUMERALS.has(token) &&
      (token.length > 1 || finalToken || SEQUEL_MARKERS.has(previous))
    ) {
      result.push(ROMAN_NUMERALS.get(token));
    }

    return result;
  }, []);
}

function equalTokens(first = [], second = []) {
  return first.length === second.length && first.every((token, index) => token === second[index]);
}

function isIgnorableMatchExtra(token, index, tokens = []) {
  if (isMetadataToken(token)) return true;
  if (/^\d+$/.test(token) && token.length >= 3) return true;
  if (index === 0 && token.length === 1 && tokens.length > 1) return true;
  return false;
}

function tokensContainTitleWithIgnorableExtras(wantTokens = [], candidateTokens = []) {
  if (!wantTokens.length || !candidateTokens.length) return false;
  if (candidateTokens.length <= wantTokens.length) return false;

  const span = wantTokens.length;
  for (let start = 0; start <= candidateTokens.length - span; start += 1) {
    const slice = candidateTokens.slice(start, start + span);
    if (!equalTokens(slice, wantTokens)) continue;
    const extras = candidateTokens
      .map((token, index) => ({ token, index }))
      .filter(({ index }) => index < start || index >= start + span);
    if (extras.length && extras.every(({ token, index }) => isIgnorableMatchExtra(token, index, candidateTokens))) {
      return true;
    }
  }

  return false;
}

function hasEditionSuffix(first = [], second = []) {
  if (first.length === second.length) return false;
  const shorter = first.length < second.length ? first : second;
  const longer = first.length < second.length ? second : first;
  if (!shorter.every((token, index) => token === longer[index])) return false;
  const suffix = longer.slice(shorter.length);
  return suffix.length > 0 && suffix.every((token) => RELAXED_VARIANT_SUFFIXES.has(token));
}

function buildMatchCandidates(item) {
  const title = String(item?.title || item?.name || '(Untitled)').trim();
  const folderName = String(item?.folderName || item?.folder || '').trim();
  const year = item?.year != null ? String(item.year).trim() : '';
  const type = String(item?.type || '').trim().toLowerCase();
  const assetReady = item?.assetReady !== false;
  const candidates = [];
  const seen = new Set();
  const addCandidate = (value, source) => {
    const cleanValue = String(value || '').trim();
    if (!cleanValue) return;
    const key = cleanValue.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    candidates.push({ value: cleanValue, source });
  };
  const addTitleCandidates = (value, source) => {
    const cleanTitle = String(value || '').trim();
    if (!cleanTitle) return;
    const candidateHasYear = Boolean(normalizeTitle(cleanTitle).year);
    if (year && !candidateHasYear) {
      addCandidate(`${cleanTitle} (${year})`, source === 'title' ? 'titleYear' : `${source}Year`);
    }
    if (!(year && type === 'movie' && !candidateHasYear)) {
      addCandidate(cleanTitle, source);
    }
  };

  if (folderName && (assetReady || !(year && type === 'movie') || normalizeTitle(folderName).year)) {
    addCandidate(folderName, 'currentFolder');
  }
  addTitleCandidates(title, 'title');
  const alternateTitles = Array.isArray(item?.titleCandidates) ? item.titleCandidates : [];
  alternateTitles.forEach((candidate) => addTitleCandidates(candidate, 'alternateTitle'));
  return candidates;
}

export function isCertainItemFolderMatch(item, folderName) {
  const selectedFolder = String(folderName || '').trim();
  if (!selectedFolder) return false;

  const folderIndex = buildFolderIndex([selectedFolder]);
  const titleCandidates = buildMatchCandidates({
    ...item,
    folder: '',
    folderName: '',
    assetReady: false,
  });

  return titleCandidates.some((candidate) => pickFolderMatch(candidate.value, folderIndex) === selectedFolder);
}

async function fetchFolderNames(targetLibrary, { optional = false } = {}) {
  const response = await fetch(`/api/asset-folders?library=${encodeURIComponent(targetLibrary)}`);
  const data = await safeJson(response);
  if (!response.ok) {
    if (optional && response.status === 404) {
      return [];
    }
    throw new Error(responseErrorMessage(response, data));
  }
  return Array.isArray(data?.items)
    ? data.items
        .filter((entry) => entry?.isDir)
        .map((entry) => String(entry?.name || '').trim())
        .filter(Boolean)
    : [];
}

async function fetchMappingScanItems(targetLibrary) {
  const response = await fetch(`/api/items/mapping-source?library=${encodeURIComponent(targetLibrary)}`);
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data));
  }
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    totalCount: Number(data?.total_count) || 0,
  };
}

async function assignFolder({ library, ratingKey, folderName }) {
  const response = await fetch('/api/items/assign-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ library, ratingKey, folderName }),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data));
  }
  return data || {};
}

async function assignFolderBatch({ library, assignments }) {
  const response = await fetch('/api/items/assign-folders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ library, assignments }),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data));
  }
  return data || {};
}

export async function runLibraryMappingScan({ library, fetchAllForLibrary, fetchItemsForMappingScan, onProgress }) {
  const lib = String(library || '').trim();
  if (!lib) {
    throw new Error('Library is required');
  }

  onProgress?.({ percent: 0, label: 'Step 1/3: Scanning asset folders…' });
  const folderNames = await fetchFolderNames(lib);
  const folderIndex = buildFolderIndex(folderNames);
  const folderNameSet = new Set(folderNames);

  onProgress?.({ percent: 33, label: 'Step 2/3: Scanning Plex library…' });
  const fetchItems =
    fetchItemsForMappingScan ||
    (fetchAllForLibrary
      ? (targetLibrary) => fetchAllForLibrary(targetLibrary, '', { notReadyOnly: false })
      : fetchMappingScanItems);
  const { items: allItems = [] } = await fetchItems(lib);

  onProgress?.({ percent: 66, label: 'Step 3/3: Matching media to folders…' });
  const entries = allItems.map((item) => {
    const title = String(item?.title || item?.name || '(Untitled)').trim();
    const folderName = String(item?.folderName || item?.folder || '').trim();
    const year = item?.year != null ? String(item.year).trim() : '';
    const ratingKey = String(item?.ratingKey ?? item?.key ?? item?.id ?? '');
    const candidates = buildMatchCandidates(item);
    const currentFolderExists = folderName ? folderNameSet.has(folderName) : false;
    const assetReady = item?.assetReady !== false && (!folderName || currentFolderExists);
    let matchedFolder = '';
    let matchedFrom = '';
    for (const candidate of candidates) {
      const match = pickFolderMatch(candidate.value, folderIndex);
      if (match) {
        matchedFolder = match;
        matchedFrom = candidate.source;
        break;
      }
    }
    return {
      ratingKey,
      title,
      year,
      currentFolder: folderName,
      matchedFolder,
      matched: Boolean(matchedFolder),
      matchedFrom,
      assetReady,
      type: item?.type || '',
      library: lib,
    };
  });

  onProgress?.({
    percent: 100,
    label: `Scan complete. ${entries.filter((entry) => !entry.matched).length} unmatched item${
      entries.filter((entry) => !entry.matched).length === 1 ? '' : 's'
    }.`,
  });

  return {
    library: lib,
    scannedAt: new Date().toISOString(),
    entries,
  };
}

async function assignMatchedFoldersLegacy({ library, entries, onProgress }) {
  const lib = String(library || '').trim();
  if (!lib) {
    throw new Error('Library is required');
  }

  const updatedEntries = Array.isArray(entries) ? entries.map((entry) => ({ ...entry })) : [];
  const assignableIndexes = updatedEntries
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => entry?.matched && entry.assetReady === false && entry.ratingKey && entry.matchedFolder);
  const errors = [];
  let assignedCount = 0;

  for (let i = 0; i < assignableIndexes.length; i += 1) {
    const { entry, index } = assignableIndexes[i];
    onProgress?.({
      assigned: assignedCount,
      total: assignableIndexes.length,
      current: i + 1,
      label: `Applying folder matches ${i + 1}/${assignableIndexes.length}…`,
    });
    try {
      const data = await assignFolder({
        library: lib,
        ratingKey: String(entry.ratingKey),
        folderName: entry.matchedFolder,
      });
      const folderName = data?.folderName || entry.matchedFolder;
      updatedEntries[index] = {
        ...entry,
        assigned: true,
        assignmentError: '',
        assetReady: true,
        currentFolder: folderName,
        matchedFolder: folderName,
        matched: true,
      };
      assignedCount += 1;
    } catch (err) {
      const message = err?.message || String(err);
      updatedEntries[index] = {
        ...entry,
        assignmentError: message,
      };
      errors.push({
        library: lib,
        title: entry.title,
        folder: entry.matchedFolder,
        asset: 'Folder assignment',
        message,
      });
    }
  }

  return {
    entries: updatedEntries,
    assignedCount,
    errors,
  };
}

export async function assignMatchedFolders({ library, entries, onProgress }) {
  const lib = String(library || '').trim();
  if (!lib) {
    throw new Error('Library is required');
  }

  const updatedEntries = Array.isArray(entries) ? entries.map((entry) => ({ ...entry })) : [];
  const assignableIndexes = updatedEntries
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => entry?.matched && entry.assetReady === false && entry.ratingKey && entry.matchedFolder);
  const errors = [];
  let assignedCount = 0;

  for (let start = 0; start < assignableIndexes.length; start += ASSIGN_BATCH_SIZE) {
    const batch = assignableIndexes.slice(start, start + ASSIGN_BATCH_SIZE);
    const current = Math.min(start + batch.length, assignableIndexes.length);
    onProgress?.({
      assigned: assignedCount,
      total: assignableIndexes.length,
      current,
      label: `Applying folder matches ${current}/${assignableIndexes.length}...`,
    });

    try {
      const data = await assignFolderBatch({
        library: lib,
        assignments: batch.map(({ entry }) => ({
          ratingKey: String(entry.ratingKey),
          folderName: entry.matchedFolder,
        })),
      });
      const resultByKey = new Map(
        (Array.isArray(data?.items) ? data.items : []).map((item) => [String(item?.ratingKey || ''), item])
      );
      const errorByKey = new Map(
        (Array.isArray(data?.errors) ? data.errors : []).map((item) => [String(item?.ratingKey || ''), item])
      );

      batch.forEach(({ entry, index }) => {
        const key = String(entry.ratingKey);
        const result = resultByKey.get(key);
        if (result) {
          const folderName = result?.folderName || entry.matchedFolder;
          updatedEntries[index] = {
            ...entry,
            assigned: true,
            assignmentError: '',
            assetReady: true,
            currentFolder: folderName,
            matchedFolder: folderName,
            matched: true,
          };
          assignedCount += 1;
          return;
        }

        const failure = errorByKey.get(key);
        if (failure) {
          const message = failure?.error || 'Failed to assign folder';
          updatedEntries[index] = {
            ...entry,
            assignmentError: message,
          };
          errors.push({
            library: lib,
            title: entry.title,
            folder: entry.matchedFolder,
            asset: 'Folder assignment',
            message,
          });
        }
      });
    } catch (err) {
      const message = err?.message || String(err);
      batch.forEach(({ entry, index }) => {
        updatedEntries[index] = {
          ...entry,
          assignmentError: message,
        };
        errors.push({
          library: lib,
          title: entry.title,
          folder: entry.matchedFolder,
          asset: 'Folder assignment',
          message,
        });
      });
    }
  }

  return {
    entries: updatedEntries,
    assignedCount,
    errors,
  };
}
