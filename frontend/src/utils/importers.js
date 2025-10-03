import { collectResultFailures, normalizeAssetResult, pushFailureEntry, responseErrorMessage, safeJson } from './api.js';

export async function importMovieAssets(library, ratingKey, folderName) {
  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  try {
    const response = await fetch('/api/import/movie', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const results = data && (data.results || data) ? data.results || data : {};
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = normalizeAssetResult(results.poster, message);
    const background = normalizeAssetResult(results.background, message);
    const ok = Boolean((data && typeof data.ok === 'boolean' ? data.ok : null) ?? (poster.ok || background.ok));
    return {
      ok: ok && response.ok,
      poster,
      background,
      seasons: [],
      error: message || (data && data.error) || null,
      endpoint: 'movie',
    };
  } catch (error) {
    const message = error?.message || String(error);
    return {
      ok: false,
      poster: normalizeAssetResult(null, message),
      background: normalizeAssetResult(null, message),
      seasons: [],
      error: message,
      endpoint: 'movie',
    };
  }
}

export async function importCollectionAssets(library, ratingKey, folderName) {
  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  try {
    const response = await fetch('/api/import/collection', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const results = data && (data.results || data) ? data.results || data : {};
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = normalizeAssetResult(results.poster, message);
    const background = normalizeAssetResult(results.background, message);
    const ok = Boolean((data && typeof data.ok === 'boolean' ? data.ok : null) ?? (poster.ok || background.ok));
    return {
      ok: ok && response.ok,
      poster,
      background,
      seasons: [],
      error: message || (data && data.error) || null,
      endpoint: 'collection',
    };
  } catch (error) {
    const message = error?.message || String(error);
    return {
      ok: false,
      poster: normalizeAssetResult(null, message),
      background: normalizeAssetResult(null, message),
      seasons: [],
      error: message,
      endpoint: 'collection',
    };
  }
}

export async function importShowPosterPreferShowEndpoint(library, ratingKey, folderName) {
  const fd = new FormData();
  fd.append('library', library);
  if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
  if (folderName) fd.append('folderName', folderName);
  try {
    const response = await fetch('/api/import/show', { method: 'POST', body: fd });
    const data = await safeJson(response);
    const message = response.ok ? null : responseErrorMessage(response, data);
    const poster = normalizeAssetResult(data && data.poster, message);
    const background = normalizeAssetResult(data && data.background, message);
    const seasonsRaw = Array.isArray(data && data.seasons) ? data.seasons : [];
    const seasons = seasonsRaw.map((season) => ({
      ok: Boolean(season && season.ok),
      index: season && (season.index ?? season.season ?? season.number ?? null),
      path: season && season.path ? season.path : null,
      src: season && season.src ? season.src : null,
      error: season && season.error ? season.error : null,
    }));
    const ok = Boolean((data && typeof data.ok === 'boolean' ? data.ok : null) ?? (poster.ok || background.ok || seasons.some((season) => season.ok)));
    const result = {
      ok: ok && response.ok,
      poster,
      background,
      seasons,
      error: message || (data && data.error) || null,
      endpoint: 'show',
    };
    if (response.ok) return result;
    if (response.status === 404 || response.status === 405) {
      const fallback = await importMovieAssets(library, ratingKey, folderName);
      fallback.fallbackReason = message;
      return fallback;
    }
    return result;
  } catch (error) {
    const fallback = await importMovieAssets(library, ratingKey, folderName);
    fallback.fallbackReason = error?.message || String(error);
    return fallback;
  }
}

export async function importAllSeasons(library, showFolder, seasons, ratingKey) {
  const results = [];
  let anyOk = false;
  for (const season of seasons || []) {
    const idxRaw = season && (season.index ?? season.season ?? season.number ?? null);
    const entry = { ok: false, index: idxRaw ?? null, path: null, src: null, error: null };
    const idx = Number(idxRaw);
    if (!Number.isFinite(idx)) {
      entry.error = `Invalid season index: ${idxRaw}`;
      results.push(entry);
      continue;
    }
    const fd = new FormData();
    fd.append('library', library);
    if (showFolder) fd.append('folderName', showFolder);
    fd.append('season', String(idx));
    if (ratingKey != null) fd.append('ratingKey', String(ratingKey));
    try {
      const response = await fetch('/api/import/season', { method: 'POST', body: fd });
      const data = await safeJson(response);
      if (!response.ok) {
        entry.error = responseErrorMessage(response, data);
      } else {
        entry.ok = Boolean((data && typeof data.ok === 'boolean' ? data.ok : null) ?? response.ok);
        entry.path = (data && data.path) || null;
        entry.src = (data && data.src) || null;
        if (!entry.ok) entry.error = (data && data.error) || null;
      }
    } catch (error) {
      entry.error = error?.message || String(error);
    }
    if (!entry.error && !entry.ok) entry.error = 'Unknown error';
    if (entry.ok) anyOk = true;
    results.push(entry);
  }
  return { ok: anyOk, seasons: results, endpoint: 'season' };
}

export function summarizeImportResult(failures) {
  const count = failures.length;
  if (!count) return 'Import complete.';
  return `Import completed with ${count} failure${count === 1 ? '' : 's'}.`;
}

export { collectResultFailures, pushFailureEntry };
