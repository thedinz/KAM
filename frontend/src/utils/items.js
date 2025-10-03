export function isShowItem(item, libraryName) {
  const lib = (libraryName || '').toLowerCase();
  const type = String(item?.type || '').toLowerCase();
  return lib.includes('tv') || type === 'show' || item?.isShow === true;
}

export function buildDetailPath(item, libraryName) {
  const lib = (libraryName || '').trim();
  if (!lib) return null;
  if (lib.toLowerCase() === 'collections') return null;
  const ratingKey = item?.ratingKey ?? item?.key ?? item?.id;
  if (ratingKey == null) return null;
  const encodedLib = encodeURIComponent(lib);
  const encodedKey = encodeURIComponent(String(ratingKey));
  const segment = isShowItem(item, libraryName) ? 'shows' : 'movies';
  return `/libraries/${encodedLib}/${segment}/${encodedKey}`;
}

export const buildDetailUrl = buildDetailPath;

export function normalizePoster(item) {
  return (
    item?.posterUrl ||
    item?.posterUrlLocal ||
    item?.posterUrlPlex ||
    item?.thumb ||
    item?.background ||
    item?.art ||
    '/fallback.png'
  );
}
