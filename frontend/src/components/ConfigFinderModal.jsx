import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const normalizeText = (value) => {
  if (value == null) return '';
  return String(value).trim();
};

const joinRootWithRelative = (root, relative) => {
  const base = normalizeText(root);
  const rel = normalizeText(relative);
  if (!rel) {
    return base;
  }
  if (rel.startsWith('/')) {
    return rel;
  }
  if (!base || base === '/') {
    return `/${rel}`.replace(/\/+/g, '/');
  }
  const cleanedBase = base.endsWith('/') ? base.slice(0, -1) : base;
  return `${cleanedBase}/${rel}`.replace(/\/+/g, '/');
};

const makeBreadcrumbs = (rootPath, parentPath, isSearching, term) => {
  const crumbs = [];
  const rootLabel = normalizeText(rootPath) || 'Root';
  crumbs.push({ label: rootLabel, path: '' });
  const relative = normalizeText(parentPath);
  if (relative) {
    const parts = relative.split('/').filter(Boolean);
    let acc = '';
    parts.forEach((part) => {
      acc = acc ? `${acc}/${part}` : part;
      crumbs.push({ label: part, path: acc });
    });
  }
  if (isSearching && term) {
    crumbs.push({ label: `Search: ${term}`, path: null, isSearch: true });
  }
  return crumbs;
};

function ConfigFinderModal({
  isOpen,
  initialPath = '',
  onClose,
  onConfirm,
  onClear,
}) {
  const [rootPath, setRootPath] = useState('');
  const [parentPath, setParentPath] = useState('');
  const [items, setItems] = useState([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  const initialPathRef = useRef('');
  const selectedPathRef = useRef('');
  const selectedAbsoluteRef = useRef('');
  const debounceRef = useRef();

  const resetState = useCallback(() => {
    setItems([]);
    setSelectedPath('');
    setError('');
    setSearchInput('');
    setSearchTerm('');
    setIsSearching(false);
    selectedPathRef.current = '';
    selectedAbsoluteRef.current = '';
  }, []);

  const loadEntries = useCallback(
    async ({ parent = '', search = '', initial = false } = {}) => {
      if (!isOpen) {
        return;
      }
      setLoading(true);
      setError('');
      setIsSearching(Boolean(search));
      const params = new URLSearchParams();
      if (parent) params.set('parent', parent);
      if (search) params.set('search', search);

      const effectiveCurrent = initial
        ? normalizeText(initialPathRef.current)
        : normalizeText(selectedAbsoluteRef.current || initialPathRef.current);
      if (effectiveCurrent) {
        params.set('current', effectiveCurrent);
      }

      const query = params.toString();
      const url = query
        ? `/api/settings/kometa-config/browse?${query}`
        : '/api/settings/kometa-config/browse';

      try {
        const response = await fetch(url);
        const data = await response.json();
        if (!response.ok) {
          const message = data?.detail || data?.error || `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const normalizedRoot = normalizeText(data?.root);
        const normalizedParent = normalizeText(data?.parent);
        const normalizedSelection = normalizeText(data?.selection);
        const normalizedItems = Array.isArray(data?.items)
          ? data.items
              .map((entry) => ({
                name: normalizeText(entry?.name),
                path: normalizeText(entry?.path),
                isDir: Boolean(entry?.isDir),
                isFile: Boolean(entry?.isFile),
              }))
              .filter((entry) => entry.name)
          : [];

        setRootPath(normalizedRoot);
        setParentPath(normalizedParent);
        setItems(normalizedItems);

        let nextSelection = normalizedSelection || selectedPathRef.current;
        if (nextSelection && !normalizedItems.some((entry) => entry.path === nextSelection)) {
          // Preserve selection even if it's outside the current listing (e.g., different folder).
          nextSelection = normalizedSelection || selectedPathRef.current;
        }
        nextSelection = normalizeText(nextSelection);
        setSelectedPath(nextSelection);
        selectedPathRef.current = nextSelection;
        const absolute = nextSelection ? joinRootWithRelative(normalizedRoot, nextSelection) : '';
        selectedAbsoluteRef.current = absolute;
      } catch (err) {
        setItems([]);
        setError(err?.message || 'Failed to load Kometa config files.');
      } finally {
        setLoading(false);
      }
    },
    [isOpen]
  );

  useEffect(() => {
    if (!isOpen) {
      resetState();
      return;
    }
    initialPathRef.current = normalizeText(initialPath);
    selectedAbsoluteRef.current = normalizeText(initialPath);
    selectedPathRef.current = '';
    setError('');
    setSearchInput('');
    setSearchTerm('');
    setIsSearching(false);
    loadEntries({ parent: '', search: '', initial: true });
  }, [initialPath, isOpen, loadEntries, resetState]);

  useEffect(() => {
    if (!isOpen) return undefined;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchTerm(searchInput.trim());
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    loadEntries({ parent: parentPath, search: searchTerm });
  }, [searchTerm, parentPath, isOpen, loadEntries]);

  const breadcrumbs = useMemo(
    () => makeBreadcrumbs(rootPath, parentPath, isSearching, searchTerm),
    [rootPath, parentPath, isSearching, searchTerm]
  );

  const handleBreadcrumbClick = (crumb) => {
    if (crumb.isSearch) return;
    setSearchInput('');
    setSearchTerm('');
    loadEntries({ parent: crumb.path || '', search: '' });
  };

  const handleSelectEntry = (entry) => {
    if (!entry) return;
    setError('');
    if (entry.isDir) {
      setSelectedPath('');
      selectedPathRef.current = '';
      selectedAbsoluteRef.current = '';
      setSearchInput('');
      setSearchTerm('');
      loadEntries({ parent: entry.path || '', search: '' });
      return;
    }
    if (!entry.isFile) return;
    setSelectedPath(entry.path);
    selectedPathRef.current = entry.path;
    selectedAbsoluteRef.current = joinRootWithRelative(rootPath, entry.path);
  };

  const handleClearSelection = () => {
    setSelectedPath('');
    selectedPathRef.current = '';
    selectedAbsoluteRef.current = '';
    setError('');
    onClear?.();
  };

  const handleConfirm = (event) => {
    event.preventDefault();
    if (!selectedPathRef.current) {
      setError('Select a config file before confirming.');
      return;
    }
    const absolute = joinRootWithRelative(rootPath, selectedPathRef.current);
    if (!absolute) {
      setError('Unable to resolve the selected config file.');
      return;
    }
    onConfirm?.(absolute);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="dialog-backdrop">
      <div
        className="dialog-panel folder-dlg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="configFinderHeading"
      >
        <form onSubmit={handleConfirm}>
          <div className="dialog-body">
            <h2 id="configFinderHeading">Select Kometa Config File</h2>
            <nav aria-label="Config breadcrumbs">
              <ol className="breadcrumbs">
                {breadcrumbs.map((crumb, index) => (
                  <li key={`${crumb.label}-${index}`}>
                    {crumb.isSearch ? (
                      <span className="tag">{crumb.label}</span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleBreadcrumbClick(crumb)}
                        disabled={index === breadcrumbs.length - 1 && !isSearching}
                        aria-current={index === breadcrumbs.length - 1 && !isSearching ? 'location' : undefined}
                      >
                        {crumb.label}
                      </button>
                    )}
                    {index < breadcrumbs.length - 1 && !crumb.isSearch ? <span aria-hidden="true">/</span> : null}
                  </li>
                ))}
              </ol>
            </nav>
            <div className="folder-search">
              <label htmlFor="configFinderSearch">Search config files</label>
              <input
                id="configFinderSearch"
                type="search"
                placeholder="Search by name"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                autoComplete="off"
              />
            </div>
            <ul className="folder-results" role="listbox">
              {loading && <li className="folder-empty">Loading entries…</li>}
              {!loading && !items.length && (
                <li className="folder-empty">
                  {isSearching && searchTerm
                    ? 'No entries matched your search.'
                    : 'No files or folders available in this location.'}
                </li>
              )}
              {!loading &&
                items.map((entry) => {
                  const isSelected = !entry.isDir && entry.path === selectedPath;
                  return (
                    <li
                      key={`${entry.path}-${entry.name}`}
                      className={`folder-row${isSelected ? ' is-selected' : ''}`}
                      role="option"
                      aria-selected={isSelected}
                    >
                      <button
                        type="button"
                        className="folder-option"
                        onClick={() => handleSelectEntry(entry)}
                      >
                        {entry.name}
                      </button>
                      {entry.isDir ? (
                        <button
                          type="button"
                          className="folder-open"
                          onClick={() => handleSelectEntry(entry)}
                        >
                          {isSearching ? 'Go' : 'Open'}
                        </button>
                      ) : (
                        <span className="tag">File</span>
                      )}
                    </li>
                  );
                })}
            </ul>
            <p className="folder-alert" role="alert">
              {error}
            </p>
            {selectedPath ? (
              <p className="folder-selection" aria-live="polite">
                Selected: <code>{joinRootWithRelative(rootPath, selectedPath)}</code>
              </p>
            ) : null}
          </div>
          <div className="actions">
            {onClear ? (
              <button type="button" onClick={handleClearSelection} disabled={!selectedPath}>
                Clear config path
              </button>
            ) : null}
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn" disabled={!selectedPath}>
              Use this file
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ConfigFinderModal;
