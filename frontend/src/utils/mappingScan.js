import { responseErrorMessage, safeJson } from './api.js';

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

function normalizeTitle(value) {
  if (!value) return { key: '', year: null, tokens: [] };
  const normalized = String(value).normalize('NFKC').replace(/[\u0000-\u001f]/g, '');
  const tokens = normalized
    .toLowerCase()
    .split(/[^0-9a-z]+/)
    .filter(Boolean)
    .filter((token) => !STOPWORDS.has(token));
  let year = null;
  if (tokens.length > 1 && /^\d{4}$/.test(tokens[tokens.length - 1])) {
    year = tokens.pop();
  }
  return { key: tokens.join(''), year, tokens };
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

  for (const entry of index) {
    if (entry.key !== key) continue;
    if (!isUsable(entry)) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!(entry.key.startsWith(key) || key.startsWith(entry.key))) continue;
    if (!hasEditionSuffix(tokens, entry.tokens)) continue;
    if (!isUsable(entry)) continue;
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
  if (folderName && (assetReady || !(year && type === 'movie') || normalizeTitle(folderName).year)) {
    candidates.push({ value: folderName, source: 'currentFolder' });
  }
  if (title) {
    if (year) {
      candidates.push({ value: `${title} (${year})`, source: 'titleYear' });
    }
    if (!(year && type === 'movie')) {
      candidates.push({ value: title, source: 'title' });
    }
  }
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

export async function runLibraryMappingScan({ library, fetchAllForLibrary, onProgress }) {
  const lib = String(library || '').trim();
  if (!lib) {
    throw new Error('Library is required');
  }

  onProgress?.({ percent: 0, label: 'Step 1/3: Scanning asset folders…' });
  const folderNames = await fetchFolderNames(lib);
  const folderIndex = buildFolderIndex(folderNames);

  onProgress?.({ percent: 33, label: 'Step 2/3: Scanning Plex library…' });
  const { items: allItems = [] } = await fetchAllForLibrary(lib, '', { notReadyOnly: false });

  onProgress?.({ percent: 66, label: 'Step 3/3: Matching media to folders…' });
  const entries = allItems.map((item) => {
    const title = String(item?.title || item?.name || '(Untitled)').trim();
    const folderName = String(item?.folderName || item?.folder || '').trim();
    const year = item?.year != null ? String(item.year).trim() : '';
    const ratingKey = String(item?.ratingKey ?? item?.key ?? item?.id ?? '');
    const candidates = buildMatchCandidates(item);
    const assetReady = item?.assetReady !== false;
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
