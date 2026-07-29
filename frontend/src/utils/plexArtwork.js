import { responseErrorMessage, safeJson } from './api.js';

export function uploadStatusMessage(data) {
  const plex = data?.plex;
  if (!plex) return 'Upload complete.';
  if (plex.ok) return 'Upload complete and sent to Plex.';
  const reason = plex.error || 'Plex did not accept the artwork.';
  return `Upload complete. Plex update failed: ${reason}`;
}

export async function sendSavedArtworkToPlex({
  library,
  folderName,
  ratingKey,
  kind = 'poster',
  season = null,
  episode = null,
}) {
  const payload = {
    library,
    folderName,
    ratingKey,
    kind: kind === 'background' ? 'background' : 'poster',
  };
  if (season != null) payload.season = Number(season);
  if (episode != null) payload.episode = Number(episode);

  const response = await fetch('/api/plex/artwork', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data));
  }
  return data;
}
