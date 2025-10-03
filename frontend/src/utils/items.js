export function isShowItem(item, libraryName) {
  const lib = (libraryName || '').toLowerCase();
  const type = String(item?.type || '').toLowerCase();
  return lib.includes('tv') || type === 'show' || item?.isShow === true;
}

export function buildDetailUrl(item, libraryName) {
  const lib = (libraryName || '').trim();
  if (!lib) return null;
  if (lib.toLowerCase() === 'collections') return null;
  const ratingKey = item?.ratingKey ?? item?.key ?? item?.id;
  if (ratingKey == null) return null;
  const encodedLib = encodeURIComponent(lib);
  const encodedKey = encodeURIComponent(ratingKey);
  const dest = isShowItem(item, libraryName) ? 'show.html' : 'movie.html';
  return `${dest}?library=${encodedLib}&ratingKey=${encodedKey}`;
}

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
