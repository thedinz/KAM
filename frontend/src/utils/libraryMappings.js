const normalizeLibraryName = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  return text;
};

const normalizePathValue = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  if (!text) return '';
  return text.replace(/\\+/g, '/');
};

const sanitizeLibraryMappings = (raw = []) => {
  if (!raw) return [];
  const entries = Array.isArray(raw) ? raw : [];
  const byLibrary = new Map();
  entries.forEach((entry) => {
    if (!entry || typeof entry !== 'object') return;
    const library = normalizeLibraryName(entry.library ?? entry.name);
    if (!library) return;
    const assetPath = normalizePathValue(entry.assetPath ?? entry.path ?? entry.assetFolder);
    if (!assetPath) return;
    const collectionsValue = entry.collectionsPath ?? entry.collectionPath ?? entry.collectionsFolder;
    const collectionsPath = collectionsValue === undefined ? '' : normalizePathValue(collectionsValue);
    byLibrary.set(library, {
      library,
      assetPath,
      collectionsPath,
    });
  });
  return Array.from(byLibrary.values()).sort((a, b) => a.library.localeCompare(b.library));
};

const areLibraryMappingsEqual = (left, right) => {
  const a = sanitizeLibraryMappings(left);
  const b = sanitizeLibraryMappings(right);
  if (a.length !== b.length) return false;
  return a.every(
    (entry, index) =>
      entry.library === b[index].library &&
      entry.assetPath === b[index].assetPath &&
      normalizePathValue(entry.collectionsPath) === normalizePathValue(b[index].collectionsPath)
  );
};

const createLibraryMappingLookup = (raw = []) => {
  const map = new Map();
  sanitizeLibraryMappings(raw).forEach((entry) => {
    map.set(entry.library, { ...entry });
  });
  return map;
};

export {
  normalizeLibraryName,
  normalizePathValue,
  sanitizeLibraryMappings,
  areLibraryMappingsEqual,
  createLibraryMappingLookup,
};

