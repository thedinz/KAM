const IMPORT_ERRORS_PREFIX = 'kam.importErrors';

function normalizeLibrary(library) {
  return String(library || '').trim();
}

function storageKeyForLibrary(library) {
  return `${IMPORT_ERRORS_PREFIX}.${normalizeLibrary(library).toLowerCase() || 'latest'}`;
}

export function buildImportErrorsPath(library) {
  const normalized = normalizeLibrary(library);
  const encoded = encodeURIComponent(normalized || 'library');
  return `/libraries/${encoded}/import-errors`;
}

export function normalizeImportError(entry, index = 0) {
  const library = normalizeLibrary(entry?.library);
  const title = String(entry?.title || entry?.name || '').trim();
  const folder = String(entry?.folder || entry?.folderName || '').trim();
  const asset = String(entry?.asset || '').trim();
  const message = String(entry?.message || entry?.error || '').trim();
  const ratingKey = entry?.ratingKey ?? entry?.key ?? entry?.id ?? null;
  const type = String(entry?.type || '').trim();
  const year = entry?.year ?? null;
  const isShow = entry?.isShow === true;
  const resolved = entry?.resolved === true;
  const resolvedFolder = String(entry?.resolvedFolder || '').trim();
  const idParts = [
    library,
    ratingKey == null ? '' : String(ratingKey),
    title,
    folder,
    asset,
    message,
    String(index),
  ];

  return {
    id: String(entry?.id || idParts.join('|')),
    library,
    title,
    folder,
    asset,
    message,
    ratingKey: ratingKey == null ? null : String(ratingKey),
    type,
    year,
    isShow,
    resolved,
    resolvedFolder,
  };
}

export function formatImportError(entry) {
  if (!entry) return 'Unknown issue';
  const parts = [];
  if (entry.library) parts.push(`[${entry.library}]`);
  if (entry.title) parts.push(entry.title);
  if (entry.folder && entry.folder !== entry.title) parts.push(`(${entry.folder})`);
  let text = parts.join(' ');
  if (entry.asset) text = text ? `${text} - ${entry.asset}` : entry.asset;
  if (entry.message) text = text ? `${text}: ${entry.message}` : entry.message;
  return text || 'Unknown issue';
}

export function saveImportErrorReport(library, errors, receipt = null) {
  if (typeof localStorage === 'undefined') return null;
  const normalizedLibrary = normalizeLibrary(library);
  const normalizedErrors = Array.isArray(errors)
    ? errors.map((entry, index) => {
        const source = entry && typeof entry === 'object' ? entry : {};
        return normalizeImportError({ ...source, library: source.library || normalizedLibrary }, index);
      })
    : [];
  const report = {
    library: normalizedLibrary,
    savedAt: new Date().toISOString(),
    receipt: receipt && typeof receipt === 'object' ? { ...receipt } : null,
    errors: normalizedErrors,
  };
  localStorage.setItem(storageKeyForLibrary(normalizedLibrary), JSON.stringify(report));
  localStorage.setItem(`${IMPORT_ERRORS_PREFIX}.latestLibrary`, normalizedLibrary);
  return report;
}

export function loadImportErrorReport(library) {
  if (typeof localStorage === 'undefined') return null;
  const normalizedLibrary = normalizeLibrary(library);
  const raw = localStorage.getItem(storageKeyForLibrary(normalizedLibrary));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    const reportLibrary = normalizeLibrary(parsed?.library || normalizedLibrary);
    return {
      library: reportLibrary,
      savedAt: typeof parsed?.savedAt === 'string' ? parsed.savedAt : '',
      receipt: parsed?.receipt && typeof parsed.receipt === 'object' ? parsed.receipt : null,
      errors: Array.isArray(parsed?.errors)
        ? parsed.errors.map((entry, index) => {
            const source = entry && typeof entry === 'object' ? entry : {};
            return normalizeImportError({ ...source, library: source.library || reportLibrary }, index);
          })
        : [],
    };
  } catch {
    return null;
  }
}

export function clearImportErrorReport(library) {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(storageKeyForLibrary(library));
}

export function importErrorIsFolderIssue(entry) {
  const text = `${entry?.asset || ''} ${entry?.message || ''}`.toLowerCase();
  return text.includes('folder match') || text.includes('asset folder') || text.includes('folder missing');
}
