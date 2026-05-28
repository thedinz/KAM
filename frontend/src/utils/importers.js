import { collectResultFailures, normalizeAssetResult, pushFailureEntry, responseErrorMessage, safeJson } from './api.js';

function boolFormValue(value) {
  return value ? 'true' : 'false';
}

function hasSelectedPrimaryAsset(includePoster, includeBackground) {
  return Boolean(includePoster || includeBackground);
}

function normalizePrimaryImportOptions(options = {}) {
  return {
    includePoster: options.poster ?? options.includePoster ?? true,
    includeBackground: options.background ?? options.includeBackground ?? true,
  };
}

function normalizeShowImportOptions(options = {}) {
  return {
    includePoster: options.seriesPoster ?? options.poster ?? options.includePoster ?? true,
    includeBackground: options.seriesBackground ?? options.background ?? options.includeBackground ?? true,
    includeSeasons: options.seasonPosters ?? options.seasons ?? options.includeSeasons ?? true,
    includeSeasonBackgrounds:
      options.seasonBackgrounds ?? options.includeSeasonBackgrounds ?? true,
  };
}

function normalizeSeasonImportOptions(options = {}) {
  return {
    includePosters: options.posters ?? options.seasonPosters ?? true,
    includeBackgrounds: options.backgrounds ?? options.seasonBackgrounds ?? true,
  };
}

function emptyImportResult(endpoint) {
  return {
    ok: true,
    poster: null,
    background: null,
    seasons: [],
    seasonBackgrounds: [],
    error: null,
    endpoint,
  };
}

export async function importMovieAssets(library, ratingKey, folderName, options = {}) {
  const { includePoster, includeBackground } = normalizePrimaryImportOptions(options);
  if (!hasSelectedPrimaryAsset(includePoster, includeBackground)) {
    return emptyImportResult('movie');
  }

  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  fd.append('includePoster', boolFormValue(includePoster));
  fd.append('includeBackground', boolFormValue(includeBackground));

  try {
    const response = await fetch('/api/import/movie', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const results = data && (data.results || data) ? data.results || data : {};
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = includePoster ? normalizeAssetResult(results.poster, message) : null;
    const background = includeBackground ? normalizeAssetResult(results.background, message) : null;
    const ok = Boolean(
      (data && typeof data.ok === 'boolean' ? data.ok : null) ?? (poster?.ok || background?.ok)
    );

    return {
      ok: ok && response.ok,
      poster,
      background,
      seasons: [],
      seasonBackgrounds: [],
      error: message || (data && data.error) || null,
      endpoint: 'movie',
    };
  } catch (error) {
    const message = error?.message || String(error);
    return {
      ok: false,
      poster: includePoster ? normalizeAssetResult(null, message) : null,
      background: includeBackground ? normalizeAssetResult(null, message) : null,
      seasons: [],
      seasonBackgrounds: [],
      error: message,
      endpoint: 'movie',
    };
  }
}

export async function importCollectionAssets(library, ratingKey, folderName, options = {}) {
  const { includePoster, includeBackground } = normalizePrimaryImportOptions(options);
  if (!hasSelectedPrimaryAsset(includePoster, includeBackground)) {
    return emptyImportResult('collection');
  }

  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  fd.append('includePoster', boolFormValue(includePoster));
  fd.append('includeBackground', boolFormValue(includeBackground));

  try {
    const response = await fetch('/api/import/collection', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const results = data && (data.results || data) ? data.results || data : {};
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = includePoster ? normalizeAssetResult(results.poster, message) : null;
    const background = includeBackground ? normalizeAssetResult(results.background, message) : null;
    const ok = Boolean(
      (data && typeof data.ok === 'boolean' ? data.ok : null) ?? (poster?.ok || background?.ok)
    );

    return {
      ok: ok && response.ok,
      poster,
      background,
      seasons: [],
      seasonBackgrounds: [],
      error: message || (data && data.error) || null,
      endpoint: 'collection',
    };
  } catch (error) {
    const message = error?.message || String(error);
    return {
      ok: false,
      poster: includePoster ? normalizeAssetResult(null, message) : null,
      background: includeBackground ? normalizeAssetResult(null, message) : null,
      seasons: [],
      seasonBackgrounds: [],
      error: message,
      endpoint: 'collection',
    };
  }
}

export async function importShowPosterPreferShowEndpoint(library, ratingKey, folderName, options = {}) {
  const {
    includePoster,
    includeBackground,
    includeSeasons,
    includeSeasonBackgrounds,
  } = normalizeShowImportOptions(options);

  if (!includePoster && !includeBackground && !includeSeasons && !includeSeasonBackgrounds) {
    return emptyImportResult('show');
  }

  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  fd.append('includePoster', boolFormValue(includePoster));
  fd.append('includeBackground', boolFormValue(includeBackground));
  fd.append('includeSeasons', boolFormValue(includeSeasons));
  fd.append('includeSeasonBackgrounds', boolFormValue(includeSeasonBackgrounds));

  try {
    const response = await fetch('/api/import/show', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = includePoster ? normalizeAssetResult(data && data.poster, message) : null;
    const background = includeBackground ? normalizeAssetResult(data && data.background, message) : null;
    const seasonsRaw = includeSeasons && Array.isArray(data && data.seasons) ? data.seasons : [];
    const seasons = seasonsRaw.map((season) => ({
      ok: Boolean(season && season.ok),
      index: season && (season.index ?? season.season ?? season.number ?? null),
      path: season && season.path ? season.path : null,
      src: season && season.src ? season.src : null,
      error: season && season.error ? season.error : null,
      replaced: Boolean(season && season.replaced),
    }));
    const seasonBackgroundsRaw =
      includeSeasonBackgrounds && Array.isArray(data && data.seasonBackgrounds)
        ? data.seasonBackgrounds
        : [];
    const seasonBackgrounds = seasonBackgroundsRaw.map((season) => ({
      ok: Boolean(season && season.ok),
      index: season && (season.index ?? season.season ?? season.number ?? null),
      path: season && season.path ? season.path : null,
      src: season && season.src ? season.src : null,
      error: season && season.error ? season.error : null,
      replaced: Boolean(season && season.replaced),
    }));
    const ok = Boolean(
      (data && typeof data.ok === 'boolean' ? data.ok : null) ??
        (poster?.ok ||
          background?.ok ||
          seasons.some((season) => season.ok) ||
          seasonBackgrounds.some((season) => season.ok))
    );
    const result = {
      ok: ok && response.ok,
      poster,
      background,
      seasons,
      seasonBackgrounds,
      error: message || (data && data.error) || null,
      endpoint: 'show',
    };

    if (response.ok) return result;
    if (response.status === 404 || response.status === 405) {
      const fallback = await importMovieAssets(library, ratingKey, folderName, {
        poster: includePoster,
        background: includeBackground,
      });
      fallback.fallbackReason = message;
      return fallback;
    }
    return result;
  } catch (error) {
    const fallback = await importMovieAssets(library, ratingKey, folderName, {
      poster: includePoster,
      background: includeBackground,
    });
    fallback.fallbackReason = error?.message || String(error);
    return fallback;
  }
}

export async function importAllSeasons(library, showFolder, seasons, ratingKey, options = {}) {
  const { includePosters, includeBackgrounds } = normalizeSeasonImportOptions(options);
  if (!includePosters && !includeBackgrounds) {
    return { ok: true, seasons: [], seasonBackgrounds: [], endpoint: 'season' };
  }

  const results = [];
  const backgroundResults = [];
  let anyOk = false;

  for (const season of seasons || []) {
    const idxRaw = season && (season.index ?? season.season ?? season.number ?? null);
    const entry = { ok: false, index: idxRaw ?? null, path: null, src: null, error: null };
    const backgroundEntry = { ok: false, index: idxRaw ?? null, path: null, src: null, error: null };
    const idx = Number(idxRaw);

    if (!Number.isFinite(idx)) {
      entry.error = `Invalid season index: ${idxRaw}`;
      backgroundEntry.error = `Invalid season index: ${idxRaw}`;
      if (includePosters) results.push(entry);
      if (includeBackgrounds) backgroundResults.push(backgroundEntry);
      continue;
    }

    const imports = [];
    if (includePosters) {
      imports.push({
        kind: 'poster',
        plexUrl: season?.plexPosterUrl || null,
        entry,
      });
    }
    if (includeBackgrounds) {
      imports.push({
        kind: 'background',
        plexUrl: season?.plexBackgroundUrl || null,
        entry: backgroundEntry,
      });
    }

    for (const importSpec of imports) {
      const fd = new FormData();
      fd.append('library', library);
      if (showFolder) fd.append('folderName', showFolder);
      fd.append('season', String(idx));
      fd.append('kind', importSpec.kind);
      if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
      if (importSpec.plexUrl) fd.append('url', importSpec.plexUrl);

      try {
        const response = await fetch('/api/import/season', { method: 'POST', body: fd });
        const data = await safeJson(response);
        if (!response.ok) {
          importSpec.entry.error = responseErrorMessage(response, data);
        } else {
          importSpec.entry.ok = Boolean((data && typeof data.ok === 'boolean' ? data.ok : null) ?? response.ok);
          importSpec.entry.path = (data && data.path) || null;
          importSpec.entry.src = (data && data.src) || null;
          importSpec.entry.replaced = Boolean(data && data.replaced);
          if (!importSpec.entry.ok) importSpec.entry.error = (data && data.error) || null;
        }
      } catch (error) {
        importSpec.entry.error = error?.message || String(error);
      }
      if (!importSpec.entry.error && !importSpec.entry.ok) importSpec.entry.error = 'Unknown error';
      if (importSpec.entry.ok) anyOk = true;
    }

    if (includePosters) results.push(entry);
    if (includeBackgrounds) backgroundResults.push(backgroundEntry);
  }

  return { ok: anyOk, seasons: results, seasonBackgrounds: backgroundResults, endpoint: 'season' };
}

export function summarizeImportResult(failures) {
  const count = failures.length;
  if (!count) return 'Import complete.';
  return `Import completed with ${count} failure${count === 1 ? '' : 's'}.`;
}

export function createImportReceipt() {
  return {
    imported: 0,
    overwritten: 0,
    skipped: 0,
    failed: 0,
  };
}

export function addImportResultToReceipt(receipt, result) {
  if (!receipt || !result) return receipt;
  const entries = [
    result.poster,
    result.background,
    ...(Array.isArray(result.seasons) ? result.seasons : []),
    ...(Array.isArray(result.seasonBackgrounds) ? result.seasonBackgrounds : []),
  ].filter((entry) => entry && typeof entry === 'object');

  if (!entries.length && !result.ok) {
    receipt.failed += 1;
    return receipt;
  }

  entries.forEach((entry) => {
    if (entry.ok) {
      receipt.imported += 1;
      if (entry.replaced) receipt.overwritten += 1;
    } else {
      receipt.failed += 1;
    }
  });

  return receipt;
}

export { collectResultFailures, pushFailureEntry };
