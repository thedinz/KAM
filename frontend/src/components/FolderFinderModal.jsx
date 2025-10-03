import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function normalizeFolderEntry(entry) {
  if (!entry) return null;
  const name = entry.name || entry.folderName || entry.label || entry.title;
  if (!name) return null;
  const path = entry.path ?? entry.folderPath ?? '';
  const hasChildren = entry.hasChildren !== false && entry.isDir !== false;
  return {
    name: String(name),
    path: path === '' ? '' : String(path),
    hasChildren,
  };
}

function makeBreadcrumbs(currentPath, query) {
  const crumbs = [];
  crumbs.push({ label: 'Root', path: '' });
  if (currentPath) {
    const parts = String(currentPath).split(/[\\/]+/).filter(Boolean);
    let acc = '';
    parts.forEach((part) => {
      acc = acc ? `${acc}/${part}` : part;
      crumbs.push({ label: part, path: acc });
    });
  }
  if (query) {
    crumbs.push({ label: `Search: ${query}`, path: null, isSearch: true });
  }
  return crumbs;
}

function FolderFinderModal({ isOpen, library, item, onClose, onFolderAssigned }) {
  const effectiveLibrary = item?.library || library;
  const [currentPath, setCurrentPath] = useState('');
  const [results, setResults] = useState([]);
  const [selection, setSelection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const debounceRef = useRef();

  useEffect(() => {
    if (!isOpen) return;
    setSearchInput('');
    setSearchTerm('');
    setSelection(null);
    setError('');
  }, [isOpen, effectiveLibrary]);

  const loadFolders = useCallback(
    async ({ path = '', query = '', preserveSelection = false } = {}) => {
      if (!effectiveLibrary) {
        setResults([]);
        setError('No library mapping available for this item.');
        return;
      }
      setLoading(true);
      if (!preserveSelection) {
        setSelection(null);
      }
      setError('');
      setIsSearching(Boolean(query));
      const params = new URLSearchParams();
      params.set('library', effectiveLibrary);
      if (path) params.set('parent', path);
      if (query) params.set('search', query);

      try {
        const response = await fetch(`/api/asset-folders?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) {
          const message = data?.detail || data?.error || `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const list = Array.isArray(data?.folders)
          ? data.folders
          : Array.isArray(data?.items)
          ? data.items
          : [];
        const normalized = list.map(normalizeFolderEntry).filter(Boolean);
        setResults(normalized);
        const parentPath = data?.parent ?? path ?? '';
        setCurrentPath(parentPath || '');
      } catch (err) {
        setResults([]);
        setError(err.message || 'Failed to load folders');
      } finally {
        setLoading(false);
      }
    },
    [effectiveLibrary]
  );

  useEffect(() => {
    if (!isOpen) return;
    loadFolders({ path: '', query: '' });
  }, [isOpen, loadFolders]);

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
    loadFolders({ path: currentPath, query: searchTerm, preserveSelection: false });
  }, [searchTerm, isOpen, currentPath, loadFolders]);

  const breadcrumbs = useMemo(() => makeBreadcrumbs(currentPath, isSearching ? searchTerm : ''), [currentPath, isSearching, searchTerm]);

  const contextLabel = useMemo(() => {
    const title = item?.title || item?.name || '(Untitled)';
    if (!effectiveLibrary) return title;
    return `Library: ${effectiveLibrary} • Item: ${title}`;
  }, [effectiveLibrary, item]);

  const handleSelect = (entry) => {
    setSelection(entry);
    setError('');
  };

  const handleOpen = (entry) => {
    if (!entry?.path) return;
    loadFolders({ path: entry.path, query: '', preserveSelection: false });
    setSearchInput('');
    setSearchTerm('');
  };

  const handleBreadcrumbClick = (crumb) => {
    loadFolders({ path: crumb.path || '', query: '', preserveSelection: false });
    setSearchInput('');
    setSearchTerm('');
  };

  const handleConfirm = async (event) => {
    event.preventDefault();
    if (!selection) {
      setError('Select a folder before confirming.');
      return;
    }
    if (!effectiveLibrary) {
      setError('Missing library context.');
      return;
    }
    const ratingKey = item?.ratingKey ?? item?.key ?? item?.id;
    const payload = {
      library: effectiveLibrary,
      folderName: selection.name,
    };
    if (ratingKey != null) {
      payload.ratingKey = String(ratingKey);
    }
    setAssigning(true);
    setError('');
    try {
      const response = await fetch('/api/items/assign-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        const message = data?.detail || data?.error || `${response.status} ${response.statusText}`;
        throw new Error(message);
      }
      const folderName = data?.folderName || selection.name;
      onFolderAssigned?.({ folderName, details: data, selection });
    } catch (err) {
      setError(err.message || 'Failed to assign folder');
    } finally {
      setAssigning(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="dialog-backdrop">
      <div className="dialog-panel folder-dlg" role="dialog" aria-modal="true" aria-labelledby="folderFinderHeading">
        <form onSubmit={handleConfirm}>
          <div className="dialog-body">
            <h2 id="folderFinderHeading">Select Asset Folder</h2>
            <p className="folder-context">{contextLabel}</p>
            <nav aria-label="Folder breadcrumbs">
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
              <label htmlFor="folderFinderSearch">Search folders</label>
              <input
                id="folderFinderSearch"
                type="search"
                placeholder="Search by folder name"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                autoComplete="off"
              />
            </div>
            <ul className="folder-results" role="listbox">
              {loading && <li className="folder-empty">Loading folders…</li>}
              {!loading && !results.length && (
                <li className="folder-empty">
                  {isSearching && searchTerm ? 'No folders matched your search.' : 'No folders available in this location.'}
                </li>
              )}
              {!loading &&
                results.map((entry) => {
                  const isSelected = selection?.path === entry.path && selection?.name === entry.name;
                  return (
                    <li
                      key={`${entry.path}-${entry.name}`}
                      className={`folder-row${isSelected ? ' is-selected' : ''}`}
                      role="option"
                      aria-selected={isSelected}
                    >
                      <button type="button" className="folder-option" onClick={() => handleSelect(entry)}>
                        {entry.name}
                      </button>
                      {entry.hasChildren !== false && (
                        <button type="button" className="folder-open" onClick={() => handleOpen(entry)}>
                          {isSearching ? 'Go' : 'Open'}
                        </button>
                      )}
                    </li>
                  );
                })}
            </ul>
            <p className="folder-alert" role="alert">
              {error}
            </p>
          </div>
          <div className="actions">
            <button type="button" onClick={onClose} disabled={assigning}>
              Cancel
            </button>
            <button type="submit" className="btn" disabled={!selection || assigning}>
              {assigning ? 'Assigning…' : 'Use This Folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default FolderFinderModal;
