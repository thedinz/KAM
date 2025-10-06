export function isShowItem(item, libraryName) {
  const lib = (libraryName || '').toLowerCase();
  const type = String(item?.type || '').toLowerCase();
  return lib.includes('tv') || type === 'show' || item?.isShow === true;
}

export function buildDetailPath(item, libraryName) {
  const lib = (libraryName || '').trim();
  if (!lib) return null;
  const ratingKey = item?.ratingKey ?? item?.key ?? item?.id;
  if (ratingKey == null) return null;
  const encodedLib = encodeURIComponent(lib);
  const encodedKey = encodeURIComponent(ratingKey);
  if (lib.toLowerCase() === 'collections') {
    const sourceLibrary = item?.library ? String(item.library).trim() : '';
    const sourceParam = sourceLibrary ? `?source=${encodeURIComponent(sourceLibrary)}` : '';
    return `/libraries/${encodedLib}/collections/${encodedKey}${sourceParam}`;
  }
  if (isShowItem(item, libraryName)) {
    return `/libraries/${encodedLib}/shows/${encodedKey}`;
  }
  return `/libraries/${encodedLib}/movies/${encodedKey}`;
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
