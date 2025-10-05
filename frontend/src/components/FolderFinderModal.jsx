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

const normalizeText = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  return text;
};

const formatLibraryList = (libraries) => {
  if (!libraries?.length) return 'No libraries selected';
  if (libraries.length === 1) return libraries[0];
  if (libraries.length === 2) return `${libraries[0]} and ${libraries[1]}`;
  const [first, second, ...rest] = libraries;
  return `${first}, ${second}, +${rest.length} more`;
};

function FolderFinderModal({
  isOpen,
  library,
  item,
  onClose,
  onFolderAssigned,
  context = 'library',
  settingsLibraries = [],
  defaultTarget = 'asset',
  settingsIntent = 'asset',
  initialAssetPath = '',
  initialCollectionsPath = '',
  onSettingsConfirm,
}) {
  const isSettingsMode = context === 'settings';
  const normalizedInitialAsset = normalizeText(initialAssetPath);
  const normalizedInitialCollections = normalizeText(initialCollectionsPath);
  const effectiveLibrary = useMemo(() => {
    if (isSettingsMode) {
      const provided = normalizeText(library);
      if (provided) return provided;
      const first = settingsLibraries.map(normalizeText).find((name) => name);
      if (first) return first;
    }
    const fromItem = normalizeText(item?.library);
    if (fromItem) return fromItem;
    return normalizeText(library);
  }, [isSettingsMode, library, settingsLibraries, item]);
  const [currentPath, setCurrentPath] = useState('');
  const [results, setResults] = useState([]);
  const [selection, setSelection] = useState(null);
  const [assetSelection, setAssetSelection] = useState(null);
  const [collectionsSelection, setCollectionsSelection] = useState(null);
  const [target, setTarget] = useState(defaultTarget === 'collections' ? 'collections' : 'asset');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [currentFolder, setCurrentFolder] = useState('');
  const debounceRef = useRef();

  useEffect(() => {
    if (!isOpen) {
      setCurrentFolder('');
      return;
    }
    setSearchInput('');
    setSearchTerm('');
    setSelection(null);
    setAssetSelection(null);
    setCollectionsSelection(null);
    setError('');
    if (isSettingsMode) {
      const initial =
        defaultTarget === 'collections'
          ? normalizedInitialCollections
          : normalizedInitialAsset;
      setCurrentFolder(initial || '');
    } else {
      const initialFolder = item?.folderName || item?.folder || '';
      setCurrentFolder(normalizeText(initialFolder));
    }
  }, [
    isOpen,
    effectiveLibrary,
    item,
    isSettingsMode,
    defaultTarget,
    normalizedInitialAsset,
    normalizedInitialCollections,
  ]);

  useEffect(() => {
    if (!isOpen) return;
    setTarget(defaultTarget === 'collections' ? 'collections' : 'asset');
  }, [isOpen, defaultTarget]);

  useEffect(() => {
    if (!isOpen || !isSettingsMode) return;
    if (target === 'collections') {
      const text = normalizeText(collectionsSelection?.path ?? normalizedInitialCollections);
      setCurrentFolder(text || '');
    } else {
      const text = normalizeText(assetSelection?.path ?? normalizedInitialAsset);
      setCurrentFolder(text || '');
    }
  }, [
    isOpen,
    isSettingsMode,
    target,
    assetSelection,
    collectionsSelection,
    normalizedInitialAsset,
    normalizedInitialCollections,
  ]);

  const loadFolders = useCallback(
    async ({ path = '', query = '', preserveSelection = false } = {}) => {
      if (!effectiveLibrary) {
        setResults([]);
        setError(isSettingsMode ? 'Select a library before browsing folders.' : 'No library mapping available for this item.');
        return;
      }
      setLoading(true);
      if (!preserveSelection) {
        if (isSettingsMode) {
          if (target === 'collections') {
            setCollectionsSelection(null);
          } else {
            setAssetSelection(null);
          }
        } else {
          setSelection(null);
        }
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
    [effectiveLibrary, isSettingsMode, target]
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

  const breadcrumbs = useMemo(
    () => makeBreadcrumbs(currentPath, isSearching ? searchTerm : ''),
    [currentPath, isSearching, searchTerm]
  );

  const contextLabel = useMemo(() => {
    if (isSettingsMode) {
      return `Libraries: ${formatLibraryList(settingsLibraries)}`;
    }
    const title = item?.title || item?.name || '(Untitled)';
    if (!effectiveLibrary) return title;
    return `Library: ${effectiveLibrary} • Item: ${title}`;
  }, [isSettingsMode, settingsLibraries, item, effectiveLibrary]);

  const displayCurrentFolder = currentFolder ? currentFolder : '';

  const handleSelect = (entry) => {
    if (isSettingsMode) {
      if (target === 'collections') {
        setCollectionsSelection(entry);
      } else {
        setAssetSelection(entry);
      }
    } else {
      setSelection(entry);
    }
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

  const resolvedAssetPath = assetSelection?.path || normalizedInitialAsset;
  const resolvedCollectionsPath = collectionsSelection?.path || normalizedInitialCollections;
  const requireAsset = settingsIntent !== 'collections';
  const requireCollections = settingsIntent === 'collections';
  const canConfirmSettings = (
    (!requireAsset || Boolean(resolvedAssetPath)) &&
    (!requireCollections || Boolean(resolvedCollectionsPath))
  );

  const activeSelection = isSettingsMode
    ? target === 'collections'
      ? collectionsSelection
      : assetSelection
    : selection;

  const handleConfirm = async (event) => {
    event.preventDefault();
    if (isSettingsMode) {
      if (!onSettingsConfirm) {
        onClose?.();
        return;
      }
      if (requireAsset && !resolvedAssetPath) {
        setError('Select an asset folder before confirming.');
        return;
      }
      if (requireCollections && !resolvedCollectionsPath) {
        setError('Select a collections folder before confirming.');
        return;
      }
      const payload = {};
      if (requireAsset && resolvedAssetPath) {
        payload.assetPath = resolvedAssetPath;
      } else if (!requireAsset && assetSelection?.path) {
        payload.assetPath = assetSelection.path;
      }
      if (settingsIntent !== 'asset') {
        if (requireCollections && resolvedCollectionsPath) {
          payload.collectionsPath = resolvedCollectionsPath;
        } else if (!requireCollections && collectionsSelection?.path) {
          payload.collectionsPath = collectionsSelection.path;
        }
      }
      onSettingsConfirm(payload, { assetSelection, collectionsSelection });
      return;
    }
    if (!activeSelection) {
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
      folderName: activeSelection.name,
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
      const folderName = data?.folderName || activeSelection.name;
      onFolderAssigned?.({ folderName, details: data, selection: activeSelection });
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
            <h2 id="folderFinderHeading">
              {isSettingsMode ? 'Select Library Folder' : 'Select Asset Folder'}
            </h2>
            <p className="folder-context">{contextLabel}</p>
            <p className="folder-current" aria-live="polite">
              {isSettingsMode ? (
                <>
                  Current {target === 'collections' ? 'collections' : 'asset'} folder:{' '}
                  {displayCurrentFolder ? <strong>{displayCurrentFolder}</strong> : <span>Not assigned</span>}
                </>
              ) : (
                <>
                  Current folder:{' '}
                  {displayCurrentFolder ? <strong>{displayCurrentFolder}</strong> : <span>Not assigned</span>}
                </>
              )}
            </p>
            {isSettingsMode ? (
              <div className="folder-targets" role="group" aria-label="Folder type">
                <button
                  type="button"
                  className={target === 'asset' ? 'is-active' : ''}
                  onClick={() => setTarget('asset')}
                >
                  Asset folder
                </button>
                <button
                  type="button"
                  className={target === 'collections' ? 'is-active' : ''}
                  onClick={() => setTarget('collections')}
                >
                  Collections folder
                </button>
              </div>
            ) : null}
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
                  {isSearching && searchTerm
                    ? 'No folders matched your search.'
                    : 'No folders available in this location.'}
                </li>
              )}
              {!loading &&
                results.map((entry) => {
                  const isSelected =
                    activeSelection?.path === entry.path && activeSelection?.name === entry.name;
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
            <button
              type="submit"
              className="btn"
              disabled={isSettingsMode ? !canConfirmSettings : !activeSelection || assigning}
            >
              {isSettingsMode ? 'Apply selection' : assigning ? 'Assigning…' : 'Use This Folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default FolderFinderModal;
