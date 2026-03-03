import { responseErrorMessage, safeJson } from './api.js';

const STOPWORDS = new Set(['the', 'a', 'an', 'movie', 'film']);

function normalizeTitle(value) {
  if (!value) return { key: '', year: null };
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
  return { key: tokens.join(''), year };
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
  const { key, year } = normalizeTitle(candidate);
  if (!key) return '';
  for (const entry of index) {
    if (entry.key !== key) continue;
    if (year && entry.year && entry.year !== year) continue;
    return entry.name;
  }
  for (const entry of index) {
    if (!(entry.key.startsWith(key) || key.startsWith(entry.key))) continue;
    if (year && entry.year && entry.year !== year) continue;
    return entry.name;
  }
  return '';
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

export async function runLibraryMappingScan({ library, fetchAllForLibrary, onProgress }) {
  const lib = String(library || '').trim();
  if (!lib) {
    throw new Error('Library is required');
  }

  onProgress?.({ percent: 0, label: 'Step 1/3: Scanning asset folders…' });
  const folderNames = await fetchFolderNames(lib);
  const collectionNames =
    lib.toLowerCase() === 'collections' ? [] : await fetchFolderNames('Collections', { optional: true });
  const folderIndex = buildFolderIndex([...folderNames, ...collectionNames]);

  onProgress?.({ percent: 33, label: 'Step 2/3: Scanning Plex library…' });
  const { items: allItems = [] } = await fetchAllForLibrary(lib, '', { notReadyOnly: false });

  onProgress?.({ percent: 66, label: 'Step 3/3: Matching media to folders…' });
  const entries = allItems.map((item) => {
    const title = String(item?.title || item?.name || '(Untitled)').trim();
    const folderName = String(item?.folderName || item?.folder || '').trim();
    const year = item?.year != null ? String(item.year).trim() : '';
    const ratingKey = String(item?.ratingKey ?? item?.key ?? item?.id ?? '');
    const candidates = [];
    if (folderName) {
      candidates.push(folderName);
    }
    if (title) {
      candidates.push(title);
      if (year) {
        candidates.push(`${title} (${year})`);
      }
    }
    let matchedFolder = '';
    for (const candidate of candidates) {
      const match = pickFolderMatch(candidate, folderIndex);
      if (match) {
        matchedFolder = match;
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

