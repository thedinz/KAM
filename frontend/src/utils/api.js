export async function safeJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

export function responseErrorMessage(response, data) {
  if (!response) return 'Unknown error';
  return (
    (data && (data.detail || data.error || data.message)) || `${response.status} ${response.statusText}`
  );
}

export function normalizeAssetResult(part, fallbackError = null) {
  return {
    ok: Boolean(part && part.ok),
    path: (part && part.path) || null,
    src: (part && part.src) || null,
    error: (part && part.error) || fallbackError || null,
    replaced: Boolean(part && part.replaced),
  };
}

export function pushFailureEntry(list, context, asset, message) {
  list.push({
    library: context?.library || '',
    title: context?.title || '',
    folder: context?.folder || '',
    asset,
    message: message || 'Unknown error',
  });
}

export function collectResultFailures(list, context, result) {
  if (!result) return;
  const hasPoster = result.poster && typeof result.poster === 'object';
  const hasBackground = result.background && typeof result.background === 'object';
  const seasons = Array.isArray(result.seasons) ? result.seasons : [];
  const seasonBackgrounds = Array.isArray(result.seasonBackgrounds) ? result.seasonBackgrounds : [];
  if (hasPoster && !result.poster.ok) {
    pushFailureEntry(list, context, 'Poster', result.poster.error || 'Failed to import poster');
  }
  if (hasBackground && !result.background.ok) {
    pushFailureEntry(list, context, 'Background', result.background.error || 'Failed to import background');
  }
  seasons.forEach((season) => {
    if (season && season.ok) return;
    const idx = season && season.index;
    let label = 'Season';
    if (idx !== undefined && idx !== null) {
      const idxNum = Number(idx);
      if (Number.isFinite(idxNum)) {
        label = `Season ${String(idxNum).padStart(2, '0')}`;
      } else {
        label = `Season ${idx}`;
      }
    }
    pushFailureEntry(list, context, label, (season && season.error) || 'Failed to import season poster');
  });
  seasonBackgrounds.forEach((season) => {
    if (season && season.ok) return;
    const idx = season && season.index;
    let label = 'Season Background';
    if (idx !== undefined && idx !== null) {
      const idxNum = Number(idx);
      if (Number.isFinite(idxNum)) {
        label = `Season ${String(idxNum).padStart(2, '0')} Background`;
      } else {
        label = `Season ${idx} Background`;
      }
    }
    pushFailureEntry(list, context, label, (season && season.error) || 'Failed to import season background');
  });
  if (!result.ok) {
    const hasSpecific =
      (hasPoster && result.poster && result.poster.error) ||
      (hasBackground && result.background && result.background.error) ||
      seasons.some((season) => season && (!season.ok || season.error)) ||
      seasonBackgrounds.some((season) => season && (!season.ok || season.error));
    if (!hasSpecific && result.error) {
      pushFailureEntry(list, context, 'Import', result.error);
    }
  }
}
