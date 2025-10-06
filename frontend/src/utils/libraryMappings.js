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

const normalizeSectionName = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  return text;
};

const sanitizeCollectionSections = (raw = []) => {
  if (!raw) return [];
  let entries = [];
  if (Array.isArray(raw)) {
    entries = raw.filter((entry) => entry && typeof entry === 'object');
  } else if (raw && typeof raw === 'object') {
    entries = Object.entries(raw).map(([name, value]) =>
      value && typeof value === 'object'
        ? { name, ...value }
        : { name, collectionsPath: value }
    );
  } else {
    return [];
  }

  const byName = new Map();
  entries.forEach((entry) => {
    const name = normalizeSectionName(
      entry.name ?? entry.section ?? entry.default ?? entry.key
    );
    if (!name) return;
    const path = normalizePathValue(
      entry.collectionsPath ?? entry.path ?? entry.assetPath ?? entry.asset_directory
    );
    if (!path) return;
    byName.set(name, { name, collectionsPath: path });
  });

  return Array.from(byName.values()).sort((a, b) => a.name.localeCompare(b.name));
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
    const collectionSections = sanitizeCollectionSections(
      entry.collectionSections ?? entry.collectionOverrides
    );
    byLibrary.set(library, {
      library,
      assetPath,
      collectionsPath,
      collectionSections,
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
      normalizePathValue(entry.collectionsPath) ===
        normalizePathValue(b[index].collectionsPath) &&
      sanitizeCollectionSections(entry.collectionSections).every((section, sectionIndex) => {
        const other = sanitizeCollectionSections(b[index].collectionSections)[sectionIndex];
        if (!other) return false;
        return (
          normalizeSectionName(section.name) === normalizeSectionName(other.name) &&
          normalizePathValue(section.collectionsPath) === normalizePathValue(other.collectionsPath)
        );
      }) &&
      sanitizeCollectionSections(entry.collectionSections).length ===
        sanitizeCollectionSections(b[index].collectionSections).length
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
  normalizeSectionName,
  sanitizeCollectionSections,
  sanitizeLibraryMappings,
  areLibraryMappingsEqual,
  createLibraryMappingLookup,
};

