import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const normalizeFsPath = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  if (!text) return '';
  return text.replace(/\\+/g, '/');
};

const isAbsoluteFsPath = (value) => {
  const text = normalizeFsPath(value);
  if (!text) return false;
  return /^(?:[a-zA-Z]:\/|\/\/|\/)/.test(text);
};

const joinFsPath = (base, child) => {
  const childPath = normalizeFsPath(child);
  if (!childPath) return normalizeFsPath(base);
  if (isAbsoluteFsPath(childPath)) return childPath;
  const basePath = normalizeFsPath(base);
  if (!basePath) return childPath;
  const trimmedBase = basePath.replace(/\/+$/, '');
  const trimmedChild = childPath.replace(/^\/+/, '');
  return trimmedBase ? `${trimmedBase}/${trimmedChild}` : trimmedChild;
};

function normalizeFolderEntry(entry) {
  if (!entry) return null;
  const name = entry.name || entry.folderName || entry.label || entry.title;
  if (!name) return null;
  const path = entry.path ?? entry.folderPath ?? '';
  const absoluteCandidate =
    entry.absolutePath ?? entry.absolute_path ?? entry.fullPath ?? entry.absolute ?? '';
  const absolutePath = normalizeFsPath(absoluteCandidate);
  const hasChildren = entry.hasChildren !== false && entry.isDir !== false;
  return {
    name: String(name),
    path: path === '' ? '' : String(path),
    absolutePath,
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
  settingsContextNote = '',
  defaultTarget = 'asset',
  settingsIntent = 'asset',
  initialAssetPath = '',
  initialCollectionsPath = '',
  onSettingsConfirm,
  settingsCanClearAsset = false,
  settingsCanClearCollections = false,
}) {
  const isSettingsMode = context === 'settings';
  const normalizedInitialAsset = normalizeText(initialAssetPath);
  const normalizedInitialCollections = normalizeText(initialCollectionsPath);
  const normalizedInitialAssetAbsolute = normalizeFsPath(initialAssetPath);
  const normalizedInitialCollectionsAbsolute = normalizeFsPath(initialCollectionsPath);
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
  const [rootPath, setRootPath] = useState('');
  const [currentAbsolute, setCurrentAbsolute] = useState('');
  const debounceRef = useRef();
  const isAtRootRef = useRef(false);

  useEffect(() => {
    if (!isOpen) {
      setCurrentFolder('');
      setRootPath('');
      setCurrentAbsolute('');
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
      const fallbackCurrent = normalizeText(currentPath);
      const selectedOrInitial = assetSelection?.path ?? normalizedInitialAsset;
      const text = normalizeText(selectedOrInitial || fallbackCurrent);
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
    currentPath,
  ]);

  const loadFolders = useCallback(
    async ({ path = '', query = '', preserveSelection = false, explicitParent = false } = {}) => {
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
      const shouldUseExplicitParent = explicitParent || (path === '' && isAtRootRef.current);
      if (shouldUseExplicitParent || path) params.set('parent', path);
      if (query) params.set('search', query);
      if (isSettingsMode) params.set('settings', 'true');
      if (!isSettingsMode) params.set('allowBeyondMapping', 'true');

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
        let effectiveRoot = normalizeFsPath(data?.root);
        setRootPath((prev) => {
          if (effectiveRoot) {
            return effectiveRoot;
          }
          effectiveRoot = prev || '';
          return prev || '';
        });
        const parentPath = typeof data?.parent === 'string' ? data.parent : path ?? '';
        const parentAbsoluteRaw =
          data?.parentAbsolute ??
          (parentPath ? joinFsPath(effectiveRoot, parentPath) : effectiveRoot);
        const normalizedParentAbsolute = normalizeFsPath(parentAbsoluteRaw);
        isAtRootRef.current = !parentPath;
        setCurrentPath(parentPath || '');
        setCurrentAbsolute(normalizedParentAbsolute);
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
    let initialPath = '';
    if (isSettingsMode) {
      if (target === 'collections') {
        initialPath = normalizeText(collectionsSelection?.path || normalizedInitialCollections);
      } else {
        initialPath = normalizeText(assetSelection?.path || normalizedInitialAsset);
      }
    }
    loadFolders({ path: initialPath, query: '', preserveSelection: true });
  }, [
    isOpen,
    isSettingsMode,
    target,
    normalizedInitialAsset,
    normalizedInitialCollections,
    assetSelection,
    collectionsSelection,
    loadFolders,
  ]);

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
    const isSearchActive = Boolean(searchTerm);
    loadFolders({
      path: currentPath,
      query: searchTerm,
      preserveSelection: !isSearchActive,
    });
  }, [searchTerm, isOpen, currentPath, loadFolders]);

  const breadcrumbs = useMemo(
    () => makeBreadcrumbs(currentPath, isSearching ? searchTerm : ''),
    [currentPath, isSearching, searchTerm]
  );

  const contextLabel = useMemo(() => {
    if (isSettingsMode) {
      const base = `Libraries: ${formatLibraryList(settingsLibraries)}`;
      if (settingsContextNote) {
        return `${base} • ${settingsContextNote}`;
      }
      return base;
    }
    const title = item?.title || item?.name || '(Untitled)';
    if (!effectiveLibrary) return title;
    return `Library: ${effectiveLibrary} • Item: ${title}`;
  }, [isSettingsMode, settingsLibraries, settingsContextNote, item, effectiveLibrary]);

  const displayCurrentFolder = currentFolder ? currentFolder : '';

  const resolveEntryAbsolute = (entry) => {
    if (!entry) return '';
    const explicit = normalizeFsPath(entry.absolutePath);
    if (explicit) return explicit;
    const relative = normalizeFsPath(entry.path);
    if (!relative) return '';
    return joinFsPath(rootPath, relative);
  };

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
    const crumbPath = crumb.path ?? '';
    const isRoot = !crumb.path && !crumb.isSearch;
    loadFolders({ path: crumbPath, query: '', preserveSelection: false, explicitParent: isRoot });
    setSearchInput('');
    setSearchTerm('');
  };

  const resolvedAssetPath =
    resolveEntryAbsolute(assetSelection) ||
    normalizedInitialAssetAbsolute ||
    (isSettingsMode ? normalizeFsPath(currentAbsolute) : '');
  const resolvedCollectionsPath =
    resolveEntryAbsolute(collectionsSelection) || normalizedInitialCollectionsAbsolute;
  const requireAsset = settingsIntent !== 'collections';
  const requireCollections = settingsIntent === 'collections';
  const canConfirmSettings =
    (!requireAsset || Boolean(resolvedAssetPath)) &&
    (!requireCollections || Boolean(resolvedCollectionsPath));
  const canClearCurrent = isSettingsMode
    ? target === 'collections'
      ? settingsCanClearCollections
      : settingsCanClearAsset
    : false;

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
      if (requireAsset) {
        payload.assetPath = resolvedAssetPath;
      } else {
        const optionalAsset = resolveEntryAbsolute(assetSelection);
        if (optionalAsset) {
          payload.assetPath = optionalAsset;
        }
      }
      const collectionsAbsolute = resolveEntryAbsolute(collectionsSelection);
      if (collectionsAbsolute) {
        payload.collectionsPath = collectionsAbsolute;
      } else if (requireCollections && resolvedCollectionsPath) {
        payload.collectionsPath = resolvedCollectionsPath;
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

  const handleClear = () => {
    if (!isSettingsMode || !onSettingsConfirm) {
      return;
    }
    setError('');
    const clearTarget = target === 'collections' ? 'collections' : 'asset';
    const payload =
      clearTarget === 'collections'
        ? { collectionsPath: '' }
        : { assetPath: '', collectionsPath: '' };
    onSettingsConfirm(payload, { clearTarget });
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
            {isSettingsMode ? (
              <button type="button" onClick={handleClear} disabled={!canClearCurrent || assigning}>
                {target === 'collections' ? 'Clear collections folder' : 'Clear asset folder'}
              </button>
            ) : null}
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
