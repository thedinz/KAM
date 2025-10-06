import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import { useTheme } from '../theme/ThemeProvider.jsx';
import {
  areLibraryMappingsEqual,
  createLibraryMappingLookup,
  normalizeLibraryName,
  normalizePathValue,
  normalizeSectionName,
} from '../utils/libraryMappings.js';

const initialModalState = {
  open: false,
  libraries: [],
  primaryLibrary: '',
  intent: 'asset',
  defaultTarget: 'asset',
  initialAssetPath: '',
  initialCollectionsPath: '',
  canClearAsset: false,
  canClearCollections: false,
  overrideName: '',
  overrideKey: '',
  overrideDisplayName: '',
  collectionSuggestions: [],
};

const normalizeText = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  return text;
};

function SettingsPage() {
  const {
    theme,
    savedTheme,
    plexUrl,
    plexToken,
    savedSettings,
    libraryMappings,
    savedLibraryMappings,
    libraries,
    librariesLoading,
    librariesError,
    loading,
    saving,
    error,
    libraryMappingsDirty,
    hasUnsavedChanges,
    applyTheme,
    updateSettings,
    saveSettings,
    revertSettings,
    refreshLibraries,
    setLibraryMappings,
    getLibraryMapping,
  } = useTheme();

  const [status, setStatus] = useState(null);
  const [selectedLibraries, setSelectedLibraries] = useState([]);
  const [modalState, setModalState] = useState(initialModalState);
  const selectAllRef = useRef(null);
  const previousLoadingFlagsRef = useRef({
    loading,
    saving,
    librariesLoading,
  });

  const savedPlexUrl = savedSettings?.plexUrl || '';
  const savedPlexToken = savedSettings?.plexToken || '';

  useEffect(() => {
    if (error) {
      setStatus({ type: 'error', message: error });
    }
  }, [error]);

  useEffect(() => {
    if (librariesError) {
      setStatus({ type: 'error', message: librariesError });
    }
  }, [librariesError]);

  const showInfoStatus = useCallback(
    (message) => {
      setStatus((prev) => {
        if (prev?.type === 'error') {
          return prev;
        }
        return { type: 'info', message };
      });
    },
    []
  );

  useEffect(() => {
    if (loading) {
      showInfoStatus('Loading settings…');
    }
  }, [loading, showInfoStatus]);

  useEffect(() => {
    if (saving) {
      showInfoStatus('Saving settings…');
    }
  }, [saving, showInfoStatus]);

  useEffect(() => {
    if (librariesLoading) {
      showInfoStatus('Loading Plex libraries…');
    }
  }, [librariesLoading, showInfoStatus]);

  useEffect(() => {
    const previous = previousLoadingFlagsRef.current;
    const infoMessages = [
      ['loading', loading, 'Loading settings…'],
      ['saving', saving, 'Saving settings…'],
      ['librariesLoading', librariesLoading, 'Loading Plex libraries…'],
    ];

    const shouldClearInfo =
      status?.type === 'info' &&
      infoMessages.some(([key, isActive, message]) => {
        const wasActive = previous[key];
        return wasActive && !isActive && status?.message === message;
      });

    if (shouldClearInfo) {
      setStatus(null);
    }

    previousLoadingFlagsRef.current = {
      loading,
      saving,
      librariesLoading,
    };
  }, [loading, saving, librariesLoading, status]);

  const busy = loading || saving;
  const combinedBusy = busy || librariesLoading;

  const libraryRows = useMemo(() => {
    const infoMap = new Map(
      (Array.isArray(libraries) ? libraries : []).map((entry) => {
        const name = normalizeLibraryName(entry?.name ?? entry?.library);
        return [
          name,
          {
            name: normalizeText(entry?.name ?? entry?.library ?? name),
            type: normalizeText(entry?.type ?? entry?.libraryType),
            key: normalizeText(entry?.key ?? entry?.id),
            assetPath: normalizePathValue(entry?.assetPath),
            collectionsPath: normalizePathValue(entry?.collectionsPath),
            collectionAssetPaths: Array.isArray(entry?.collectionAssetPaths)
              ? entry.collectionAssetPaths.map((value) => normalizePathValue(value)).filter(Boolean)
              : [],
          },
        ];
      })
    );
    const currentMap = createLibraryMappingLookup(libraryMappings);
    const savedMap = createLibraryMappingLookup(savedLibraryMappings);
    const names = new Set([...infoMap.keys(), ...currentMap.keys(), ...savedMap.keys()]);

    return Array.from(names)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b))
      .map((name) => {
        const info =
          infoMap.get(name) || {
            name,
            type: '',
            key: '',
            assetPath: '',
            collectionsPath: '',
            collectionAssetPaths: [],
          };
        const current = currentMap.get(name);
        const saved = savedMap.get(name);
        const assetPath = normalizePathValue(current?.assetPath ?? info.assetPath);
        const infoCollectionsPath = normalizePathValue(info.collectionsPath);
        const infoCollectionPaths = Array.isArray(info.collectionAssetPaths)
          ? info.collectionAssetPaths
          : [];
        const fallbackCollectionsPath = infoCollectionsPath || infoCollectionPaths[0] || '';
        const collectionsPath = normalizePathValue(
          current?.collectionsPath ?? fallbackCollectionsPath
        );
        const savedAssetPath = normalizePathValue(saved?.assetPath ?? info.assetPath);
        const savedCollectionsPath = normalizePathValue(
          saved?.collectionsPath ?? fallbackCollectionsPath
        );
        const collectionSuggestions = Array.from(
          new Set([collectionsPath, ...infoCollectionPaths].filter(Boolean))
        );
        const collectionSuggestionExtras = collectionSuggestions.filter(
          (value) => value !== collectionsPath
        );
        const infoOverrides = Array.isArray(info.collectionOverrides)
          ? info.collectionOverrides
          : [];
        const currentOverrides = Array.isArray(current?.collectionSections)
          ? current.collectionSections
          : [];
        const savedOverrides = Array.isArray(saved?.collectionSections)
          ? saved.collectionSections
          : [];
        const overrideMap = new Map();

        infoOverrides.forEach((override) => {
          const normalizedName = normalizeSectionName(override?.name);
          if (!normalizedName) return;
          const suggestions = Array.isArray(override?.suggestionPaths)
            ? override.suggestionPaths.map((value) => normalizePathValue(value)).filter(Boolean)
            : [];
          overrideMap.set(normalizedName, {
            key: normalizedName,
            name: override.name || normalizedName,
            collectionsPath: '',
            savedCollectionsPath: '',
            suggestions: Array.from(new Set(suggestions)),
          });
        });

        currentOverrides.forEach((override) => {
          const normalizedName = normalizeSectionName(override?.name);
          if (!normalizedName) return;
          const path = normalizePathValue(override?.collectionsPath);
          const existing = overrideMap.get(normalizedName) || {
            key: normalizedName,
            name: override?.name || normalizedName,
            collectionsPath: '',
            savedCollectionsPath: '',
            suggestions: [],
          };
          if (!existing.name) {
            existing.name = override?.name || normalizedName;
          }
          existing.collectionsPath = path;
          overrideMap.set(normalizedName, existing);
        });

        savedOverrides.forEach((override) => {
          const normalizedName = normalizeSectionName(override?.name);
          if (!normalizedName) return;
          const path = normalizePathValue(override?.collectionsPath);
          const existing = overrideMap.get(normalizedName) || {
            key: normalizedName,
            name: override?.name || normalizedName,
            collectionsPath: '',
            savedCollectionsPath: '',
            suggestions: [],
          };
          if (!existing.name) {
            existing.name = override?.name || normalizedName;
          }
          existing.savedCollectionsPath = path;
          overrideMap.set(normalizedName, existing);
        });

        const collectionOverrides = Array.from(overrideMap.values())
          .map((override) => {
            const currentPath = normalizePathValue(override.collectionsPath);
            const savedPath = normalizePathValue(override.savedCollectionsPath);
            const suggestions = Array.from(
              new Set([currentPath, ...(override.suggestions || [])].filter(Boolean))
            );
            const suggestionExtras = suggestions.filter((value) => value !== currentPath);
            return {
              key: override.key,
              name: override.name,
              collectionsPath: currentPath,
              savedCollectionsPath: savedPath,
              collectionSuggestions: suggestions,
              collectionSuggestionExtras: suggestionExtras,
              isDirty: currentPath !== savedPath,
            };
          })
          .sort((a, b) => a.name.localeCompare(b.name));

        const isDirty =
          assetPath !== savedAssetPath ||
          collectionsPath !== savedCollectionsPath ||
          collectionOverrides.some((override) => override.isDirty);
        return {
          name,
          type: info.type,
          key: info.key,
          assetPath,
          collectionsPath,
          savedAssetPath,
          savedCollectionsPath,
          isDirty,
          collectionSuggestions,
          collectionSuggestionExtras,
          collectionOverrides,
        };
      });
  }, [libraries, libraryMappings, savedLibraryMappings]);

  const libraryRowMap = useMemo(() => new Map(libraryRows.map((row) => [row.name, row])), [libraryRows]);

  useEffect(() => {
    if (!selectAllRef.current) return;
    const total = libraryRows.length;
    const selected = selectedLibraries.length;
    selectAllRef.current.indeterminate = selected > 0 && selected < total;
  }, [selectedLibraries, libraryRows.length]);

  useEffect(() => {
    const available = new Set(libraryRows.map((row) => row.name));
    setSelectedLibraries((prev) => {
      const filtered = prev.filter((name) => available.has(name));
      if (
        filtered.length === prev.length &&
        filtered.every((name, index) => name === prev[index])
      ) {
        return prev;
      }
      return filtered;
    });
  }, [libraryRows]);

  const mappingsDirty = useMemo(() => {
    if (libraryMappingsDirty != null) {
      return Boolean(libraryMappingsDirty);
    }
    return !areLibraryMappingsEqual(libraryMappings, savedLibraryMappings);
  }, [libraryMappingsDirty, libraryMappings, savedLibraryMappings]);

  const isDirty = useMemo(() => {
    if (typeof hasUnsavedChanges === 'boolean') {
      return hasUnsavedChanges;
    }
    const settingsChanged =
      theme !== savedTheme ||
      plexUrl !== savedPlexUrl ||
      plexToken !== savedPlexToken;
    return settingsChanged || mappingsDirty;
  }, [
    hasUnsavedChanges,
    theme,
    savedTheme,
    plexUrl,
    savedPlexUrl,
    plexToken,
    savedPlexToken,
    mappingsDirty,
  ]);

  const selectedRows = selectedLibraries
    .map((name) => libraryRowMap.get(name))
    .filter(Boolean);
  const selectionHasAsset = selectedRows.length > 0 && selectedRows.every((row) => row.assetPath);

  const handleThemeChange = (event) => {
    applyTheme(event.target.value);
    setStatus(null);
  };

  const handlePlexUrlChange = (event) => {
    updateSettings({ plexUrl: event.target.value });
    setStatus(null);
  };

  const handlePlexTokenChange = (event) => {
    updateSettings({ plexToken: event.target.value });
    setStatus(null);
  };

  const handleToggleLibrary = (libraryName) => {
    setStatus(null);
    setSelectedLibraries((prev) =>
      prev.includes(libraryName)
        ? prev.filter((item) => item !== libraryName)
        : [...prev, libraryName]
    );
  };

  const handleToggleAll = (event) => {
    setStatus(null);
    if (event.target.checked) {
      setSelectedLibraries(libraryRows.map((row) => row.name));
    } else {
      setSelectedLibraries([]);
    }
  };

  const closeModal = () => {
    setModalState(initialModalState);
  };

  const openModal = (librariesList, intent, defaultTarget, options = {}) => {
    const uniqueNames = Array.from(new Set(librariesList.map((name) => normalizeText(name)).filter(Boolean)));
    if (!uniqueNames.length) {
      setStatus({ type: 'error', message: 'Select at least one library first.' });
      return;
    }
    const primary = uniqueNames[0];
    const primaryRow = libraryRowMap.get(primary);
    const modalRows = uniqueNames.map((name) => libraryRowMap.get(name)).filter(Boolean);
    const canClearAsset = modalRows.some((row) => row.assetPath);
    const canClearCollections =
      options.canClearCollections !== undefined
        ? Boolean(options.canClearCollections)
        : modalRows.some((row) => row.collectionsPath);
    setStatus(null);
    setModalState({
      open: true,
      libraries: uniqueNames,
      primaryLibrary: primary,
      intent: intent || 'asset',
      defaultTarget: defaultTarget || (intent === 'collections' ? 'collections' : 'asset'),
      initialAssetPath: primaryRow?.assetPath || '',
      initialCollectionsPath:
        options.initialCollectionsPath !== undefined
          ? options.initialCollectionsPath
          : primaryRow?.collectionsPath || '',
      canClearAsset,
      canClearCollections,
      overrideName: options.overrideName || '',
      overrideKey: options.overrideKey || '',
      overrideDisplayName: options.overrideDisplayName || '',
      collectionSuggestions: Array.isArray(options.collectionSuggestions)
        ? options.collectionSuggestions.filter(Boolean)
        : primaryRow?.collectionSuggestions || [],
    });
  };

  const handleModalConfirm = (values, meta = {}) => {
    const target = modalState.intent || 'asset';
    const names = modalState.libraries;

    if (!names.length) {
      closeModal();
      return;
    }

    if (modalState.overrideKey) {
      const libraryName = modalState.primaryLibrary;
      if (!libraryName) {
        closeModal();
        return;
      }
      const mapping = getLibraryMapping(libraryName);
      const existingSections = Array.isArray(mapping?.collectionSections)
        ? mapping.collectionSections
        : [];
      const filteredSections = existingSections.filter(
        (section) => normalizeSectionName(section?.name) !== modalState.overrideKey
      );

      if (meta?.clearTarget === 'collections') {
        setLibraryMappings([libraryName], { collectionSections: filteredSections });
        const displayName = modalState.overrideDisplayName || modalState.overrideName || modalState.overrideKey;
        setStatus({
          type: 'success',
          message: `Cleared collections folder for ${displayName} in ${libraryName}.`,
        });
        closeModal();
        return;
      }

      let nextPath = values?.collectionsPath;
      if (nextPath === undefined) {
        nextPath = modalState.initialCollectionsPath;
      }
      nextPath = normalizePathValue(nextPath);
      if (!nextPath) {
        setStatus({ type: 'error', message: 'Select a collections folder before applying changes.' });
        return;
      }

      const displayName = modalState.overrideDisplayName || modalState.overrideName || modalState.overrideKey;
      const nextSections = [...filteredSections, { name: displayName, collectionsPath: nextPath }];
      setLibraryMappings([libraryName], { collectionSections: nextSections });
      setStatus({
        type: 'success',
        message: `Updated collections folder for ${displayName} in ${libraryName}.`,
      });
      closeModal();
      return;
    }

    if (meta?.clearTarget === 'asset') {
      const rowsToClear = names
        .map((name) => libraryRowMap.get(name))
        .filter((row) => row?.assetPath);
      if (!rowsToClear.length) {
        setStatus({ type: 'error', message: 'Select libraries with asset folders to clear mappings.' });
        return;
      }
      setLibraryMappings(names, { assetPath: '', collectionsPath: '' });
      setStatus({
        type: 'success',
        message:
          rowsToClear.length > 1
            ? `Cleared mappings for ${rowsToClear.length} libraries.`
            : `Cleared mapping for ${rowsToClear[0].name}.`,
      });
      closeModal();
      return;
    }

    if (meta?.clearTarget === 'collections') {
      const rowsToClear = names
        .map((name) => libraryRowMap.get(name))
        .filter((row) => row?.collectionsPath);
      if (!rowsToClear.length) {
        setStatus({ type: 'error', message: 'Select libraries with collections folders to clear.' });
        return;
      }
      setLibraryMappings(names, { collectionsPath: '' });
      setStatus({
        type: 'success',
        message:
          rowsToClear.length > 1
            ? `Cleared collections folders for ${rowsToClear.length} libraries.`
            : `Cleared collections folder for ${rowsToClear[0].name}.`,
      });
      closeModal();
      return;
    }

    const assetPath = normalizeText(values?.assetPath);
    const collectionsPath =
      values?.collectionsPath === undefined ? undefined : normalizeText(values.collectionsPath);

    if (target !== 'collections' && !assetPath) {
      setStatus({ type: 'error', message: 'Select an asset folder before applying changes.' });
      return;
    }
    if (target !== 'asset' && collectionsPath === undefined) {
      setStatus({ type: 'error', message: 'Select a collections folder before applying changes.' });
      return;
    }

    if (target === 'collections') {
      setLibraryMappings(names, { collectionsPath });
      setStatus({
        type: 'success',
        message:
          names.length > 1
            ? `Updated collections folders for ${names.length} libraries.`
            : `Updated collections folder for ${names[0]}.`,
      });
    } else {
      const updates = collectionsPath === undefined ? { assetPath } : { assetPath, collectionsPath };
      setLibraryMappings(names, updates);
      const folderName = meta?.assetSelection?.name || meta?.assetSelection?.path || assetPath;
      setStatus({
        type: 'success',
        message:
          names.length > 1
            ? `Applied ${folderName || 'selected folder'} to ${names.length} libraries.`
            : `Updated asset folder for ${names[0]}.`,
      });
    }

    closeModal();
  };

  const handleOpenAssetModal = (libraryName) => {
    openModal([libraryName], 'asset', 'asset');
  };

  const handleOpenCollectionsModal = (libraryName) => {
    const row = libraryRowMap.get(libraryName);
    if (!row?.assetPath) {
      setStatus({
        type: 'error',
        message: `${libraryName} needs an asset folder before setting a collections folder.`,
      });
      return;
    }
    openModal([libraryName], 'collections', 'collections', {
      collectionSuggestions: row.collectionSuggestions,
    });
  };

  const handleOpenCollectionOverrideModal = (libraryName, overrideKey) => {
    const row = libraryRowMap.get(libraryName);
    if (!row?.assetPath) {
      setStatus({
        type: 'error',
        message: `${libraryName} needs an asset folder before setting collections overrides.`,
      });
      return;
    }
    const override = row.collectionOverrides?.find((item) => item.key === overrideKey);
    if (!override) return;

    const suggestions = override.collectionSuggestions?.length
      ? override.collectionSuggestions
      : row.collectionSuggestions || [];
    const initialPath = override.collectionsPath || suggestions[0] || row.collectionsPath || '';

    openModal([libraryName], 'collections', 'collections', {
      overrideName: override.name,
      overrideDisplayName: override.name,
      overrideKey,
      initialCollectionsPath: initialPath,
      canClearCollections: Boolean(override.collectionsPath),
      collectionSuggestions: suggestions,
    });
  };

  const handleApplyAssetToSelection = () => {
    if (!selectedLibraries.length) {
      setStatus({ type: 'error', message: 'Select one or more libraries first.' });
      return;
    }
    openModal(selectedLibraries, 'asset', 'asset');
  };

  const handleApplyCollectionsToSelection = () => {
    if (!selectedLibraries.length) {
      setStatus({ type: 'error', message: 'Select one or more libraries first.' });
      return;
    }
    if (!selectionHasAsset) {
      setStatus({
        type: 'error',
        message: 'All selected libraries need asset folders before setting collections folders.',
      });
      return;
    }
    openModal(selectedLibraries, 'collections', 'collections');
  };

  const handleRefreshLibraries = async () => {
    setStatus(null);
    try {
      await refreshLibraries();
      setStatus({ type: 'success', message: 'Plex libraries refreshed.' });
    } catch (err) {
      setStatus({ type: 'error', message: err?.message || 'Failed to refresh libraries.' });
    }
  };

  const performSave = useCallback(async () => {
    if (!isDirty) {
      setStatus({ type: 'success', message: 'Settings are already up to date.' });
      return;
    }
    setStatus(null);
    try {
      await saveSettings();
      setStatus({ type: 'success', message: 'Settings saved successfully.' });
    } catch (err) {
      const message = err?.message || 'Failed to save settings.';
      revertSettings();
      setStatus({ type: 'error', message });
    }
  }, [isDirty, saveSettings, revertSettings, setStatus]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    await performSave();
  };

  const handleGlobalSave = useCallback(() => {
    void performSave();
  }, [performSave]);

  const handleRevert = () => {
    revertSettings();
    setSelectedLibraries([]);
    setStatus({ type: 'success', message: 'Changes reverted.' });
  };

  return (
    <div>
      <header>
        <Link className="btn" to="/libraries">
          ← Back
        </Link>
        <h1>Settings</h1>
      </header>
      <main className="settings-page">
        <div className="settings-actions settings-global-actions settings-global-actions-top">
          <button
            type="button"
            className="btn"
            onClick={handleGlobalSave}
            disabled={busy || !isDirty}
          >
            Save Changes
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleRevert}
            disabled={busy || !isDirty}
          >
            Revert
          </button>
        </div>
        <section className="settings-card">
          <h2>Theme</h2>
          <p className="settings-description">
            Choose how KAM looks. Changes are previewed immediately and applied once saved.
          </p>
          <form onSubmit={handleSubmit} className="settings-form">
            <fieldset disabled={busy}>
              <legend className="sr-only">Theme preference</legend>
              <label className="settings-radio">
                <input
                  type="radio"
                  name="theme"
                  value="dark"
                  checked={theme === 'dark'}
                  onChange={handleThemeChange}
                />
                <span>Dark</span>
              </label>
              <label className="settings-radio">
                <input
                  type="radio"
                  name="theme"
                  value="light"
                  checked={theme === 'light'}
                  onChange={handleThemeChange}
                />
                <span>Light</span>
              </label>
            </fieldset>
            <div className="settings-section">
              <h3>Plex</h3>
              <p className="settings-description">
                Provide your Plex URL and token to enable Plex integrations in KAM.
              </p>
              <label className="settings-input">
                <span>Plex URL</span>
                <input
                  type="url"
                  name="plexUrl"
                  value={plexUrl}
                  onChange={handlePlexUrlChange}
                  placeholder="http://plex.local:32400"
                  autoComplete="off"
                  disabled={busy}
                />
              </label>
              <label className="settings-input">
                <span>Plex Token (sensitive)</span>
                <input
                  type="password"
                  name="plexToken"
                  value={plexToken}
                  onChange={handlePlexTokenChange}
                  placeholder="Enter your Plex token"
                  autoComplete="new-password"
                  disabled={busy}
                />
              </label>
            </div>
          </form>
        </section>

        <section className="settings-card">
          <h2>Plex Libraries</h2>
          <p className="settings-description">
            Map Plex libraries to asset folders. Use the controls below to assign folders, apply paths to
            multiple libraries, and manage optional collections folders.
          </p>
          <div className="settings-libraries-toolbar">
            <div className="settings-libraries-group">
              <button
                type="button"
                onClick={handleApplyAssetToSelection}
                disabled={!selectedLibraries.length || combinedBusy}
              >
                Set asset folder for selected
              </button>
              <button
                type="button"
                onClick={handleApplyCollectionsToSelection}
                disabled={!selectedLibraries.length || !selectionHasAsset || combinedBusy}
              >
                Set collections folder for selected
              </button>
            </div>
            <div className="settings-libraries-group">
              <button type="button" onClick={handleRefreshLibraries} disabled={combinedBusy}>
                {librariesLoading ? 'Refreshing…' : 'Refresh libraries'}
              </button>
            </div>
          </div>
          <div className="settings-libraries-table-wrapper" aria-live="polite">
            {librariesLoading ? <p className="settings-libraries-status">Loading libraries…</p> : null}
            {!librariesLoading && !libraryRows.length ? (
              <p className="settings-libraries-status">No libraries are available. Configure Plex and refresh.</p>
            ) : null}
            {libraryRows.length ? (
              <table className="settings-libraries-table">
                <thead>
                  <tr>
                    <th scope="col" className="library-select">
                      <input
                        type="checkbox"
                        ref={selectAllRef}
                        checked={libraryRows.length > 0 && selectedLibraries.length === libraryRows.length}
                        onChange={handleToggleAll}
                        disabled={!libraryRows.length || combinedBusy}
                        aria-label="Select all libraries"
                      />
                    </th>
                    <th scope="col">Library</th>
                    <th scope="col">Asset folder</th>
                    <th scope="col">Collections folder</th>
                    <th scope="col">Status</th>
                    <th scope="col" className="library-actions">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {libraryRows.map((row) => {
                    const isSelected = selectedLibraries.includes(row.name);
                    return (
                      <Fragment key={row.name}>
                        <tr className={row.isDirty ? 'is-dirty' : undefined}>
                          <td className="library-select">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => handleToggleLibrary(row.name)}
                              disabled={combinedBusy}
                              aria-label={`Select ${row.name}`}
                            />
                          </td>
                          <th scope="row">
                            <div className="library-name">{row.name}</div>
                            <div className="library-meta">
                              {row.type ? <span className="library-tag">{row.type}</span> : null}
                              {row.key ? <span className="library-tag">Key {row.key}</span> : null}
                            </div>
                          </th>
                          <td>
                            {row.assetPath ? <code>{row.assetPath}</code> : <span className="placeholder">Not set</span>}
                          </td>
                          <td>
                            {row.collectionsPath ? (
                              <code>{row.collectionsPath}</code>
                            ) : (
                              <span className="placeholder">Not set</span>
                            )}
                            {row.collectionSuggestionExtras?.length ? (
                              <div className="collection-suggestions">
                                Suggested:{' '}
                                {row.collectionSuggestionExtras.map((value, index) => (
                                  <span key={value}>
                                    {index > 0 ? ', ' : ''}
                                    <code>{value}</code>
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </td>
                          <td>
                            {row.isDirty ? <span className="status-unsaved">Unsaved changes</span> : <span>Saved</span>}
                          </td>
                          <td className="library-actions">
                            <button
                              type="button"
                              onClick={() => handleOpenAssetModal(row.name)}
                              disabled={combinedBusy}
                            >
                              Set asset folder
                            </button>
                            <button
                              type="button"
                              onClick={() => handleOpenCollectionsModal(row.name)}
                              disabled={combinedBusy || !row.assetPath}
                            >
                              Set collections folder
                            </button>
                          </td>
                        </tr>
                        {row.collectionOverrides?.map((override) => (
                          <tr
                            key={`${row.name}::${override.key}`}
                            className={`library-override-row${override.isDirty ? ' is-dirty' : ''}`}
                          >
                            <td className="library-select" aria-hidden="true" />
                            <th scope="row">
                              <div className="library-name override-name">{override.name}</div>
                              <div className="library-meta">
                                <span className="library-tag">Collections override</span>
                              </div>
                            </th>
                            <td>
                              <span className="placeholder">Uses library asset folder</span>
                            </td>
                            <td>
                              {override.collectionsPath ? (
                                <code>{override.collectionsPath}</code>
                              ) : (
                                <span className="placeholder">Not set</span>
                              )}
                              {override.collectionSuggestionExtras?.length ? (
                                <div className="collection-suggestions">
                                  Suggested:{' '}
                                  {override.collectionSuggestionExtras.map((value, index) => (
                                    <span key={value}>
                                      {index > 0 ? ', ' : ''}
                                      <code>{value}</code>
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                            </td>
                            <td>
                              {override.isDirty ? (
                                <span className="status-unsaved">Unsaved changes</span>
                              ) : (
                                <span>Saved</span>
                              )}
                            </td>
                            <td className="library-actions">
                              <button
                                type="button"
                                onClick={() => handleOpenCollectionOverrideModal(row.name, override.key)}
                                disabled={combinedBusy || !row.assetPath}
                              >
                                Set collections folder
                              </button>
                            </td>
                          </tr>
                        ))}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            ) : null}
          </div>
        </section>

        {status ? (
          <div
            className={`settings-status ${status.type}`}
            role={status.type === 'error' ? 'alert' : 'status'}
            aria-live="polite"
          >
            {status.message}
          </div>
        ) : null}
        <div className="settings-actions settings-global-actions settings-global-actions-bottom">
          <button
            type="button"
            className="btn"
            onClick={handleGlobalSave}
            disabled={busy || !isDirty}
          >
            Save Changes
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleRevert}
            disabled={busy || !isDirty}
          >
            Revert
          </button>
        </div>
      </main>
      <FolderFinderModal
        isOpen={modalState.open}
        context="settings"
        library={modalState.primaryLibrary}
        settingsLibraries={modalState.libraries}
        settingsContextNote={
          modalState.overrideDisplayName
            ? `Override: ${modalState.overrideDisplayName}`
            : ''
        }
        defaultTarget={modalState.defaultTarget}
        settingsIntent={modalState.intent}
        initialAssetPath={modalState.initialAssetPath}
        initialCollectionsPath={modalState.initialCollectionsPath}
        settingsCanClearAsset={modalState.canClearAsset}
        settingsCanClearCollections={modalState.canClearCollections}
        onClose={closeModal}
        onSettingsConfirm={handleModalConfirm}
      />
    </div>
  );
}

export default SettingsPage;
