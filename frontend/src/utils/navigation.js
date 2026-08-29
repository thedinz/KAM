export function buildLibraryBackLink(library) {
  const name = String(library || '').trim();
  return name ? `/libraries/${encodeURIComponent(name)}` : '/libraries';
}

export function currentPathWithSearch(location) {
  const pathname = location?.pathname || '/';
  const search = location?.search || '';
  const hash = location?.hash || '';
  return `${pathname}${search}${hash}`;
}

export function safeReturnPath(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed || !trimmed.startsWith('/') || trimmed.startsWith('//')) return null;
  return trimmed;
}

export function detailBackLink(location, fallback) {
  const state = location?.state;
  const returnTo =
    state && typeof state === 'object' && !Array.isArray(state)
      ? safeReturnPath(state.returnTo)
      : null;
  return returnTo || fallback;
}
