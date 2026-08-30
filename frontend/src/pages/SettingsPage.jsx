import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import { useAuth } from '../hooks/AuthProvider.jsx';
import { useTheme } from '../theme/ThemeProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
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
  const navigate = useNavigate();
  const { refresh: refreshAuth } = useAuth();
  const {
    theme,
    savedTheme,
    plexUrl,
    plexToken,
    autoApplyToPlex,
    authMode,
    authUsername,
    authPassword,
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
    exclusions,
    exclusionsLoading,
    exclusionsError,
    refreshExclusions,
    includeItem,
  } = useTheme();

  const [status, setStatus] = useState(null);
  const [selectedLibraries, setSelectedLibraries] = useState([]);
  const [modalState, setModalState] = useState(initialModalState);
  const [includingKeys, setIncludingKeys] = useState([]);
  const [healthReport, setHealthReport] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState('');
  const selectAllRef = useRef(null);
  const previousLoadingFlagsRef = useRef({
    loading,
    saving,
    librariesLoading,
    exclusionsLoading,
  });

  const savedPlexUrl = savedSettings?.plexUrl || '';
  const savedPlexToken = savedSettings?.plexToken || '';
  const savedAutoApplyToPlex = Boolean(savedSettings?.autoApplyToPlex);
  const savedAuthMode = savedSettings?.authMode || 'builtin';
  const savedAuthUsername = savedSettings?.authUsername || '';
  const savedAuthPassword = savedSettings?.authPassword || '';
  const effectiveAuthMode = authMode === 'reverse_proxy' ? 'reverse_proxy' : 'builtin';
  const effectiveAuthUsername = authUsername ?? '';
  const effectiveAuthPassword = authPassword ?? '';
  const normalizedPlexUrl = normalizeText(plexUrl);
  const normalizedPlexToken = normalizeText(plexToken);
  const normalizedAuthUsername = normalizeText(effectiveAuthUsername);
  const normalizedAuthPassword = normalizeText(effectiveAuthPassword);
  const hasPlexCredentials = Boolean(normalizedPlexUrl && normalizedPlexToken);
  const hasAuthPassword = Boolean(normalizedAuthPassword);
  const hasAuthUsername = Boolean(normalizedAuthUsername);
  const reverseProxyAuth = effectiveAuthMode === 'reverse_proxy';

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

  useEffect(() => {
    if (exclusionsError) {
      setStatus({ type: 'error', message: exclusionsError });
    }
  }, [exclusionsError]);

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
    if (exclusionsLoading) {
      showInfoStatus('Loading exclusions…');
    }
  }, [exclusionsLoading, showInfoStatus]);

  useEffect(() => {
    const previous = previousLoadingFlagsRef.current;
    const infoMessages = [
      ['loading', loading, 'Loading settings…'],
      ['saving', saving, 'Saving settings…'],
      ['librariesLoading', librariesLoading, 'Loading Plex libraries…'],
      ['exclusionsLoading', exclusionsLoading, 'Loading exclusions…'],
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
      exclusionsLoading,
    };
  }, [loading, saving, librariesLoading, exclusionsLoading, status]);

  const busy = loading || saving;
  const combinedBusy = busy || librariesLoading;
  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError('');
    try {
      const response = await fetch('/api/settings/health');
      const data = await safeJson(response);
      if (!response?.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      setHealthReport(data || null);
    } catch (err) {
      setHealthReport(null);
      setHealthError(err?.message || 'Unable to run setup check.');
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  const includingSet = useMemo(() => new Set(includingKeys), [includingKeys]);

  const libraryRows = useMemo(() => {
    if (!hasPlexCredentials) {
      return [];
    }
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
  }, [hasPlexCredentials, libraries, libraryMappings, savedLibraryMappings]);

  const libraryRowMap = useMemo(() => new Map(libraryRows.map((row) => [row.name, row])), [libraryRows]);

  const exclusionRows = useMemo(() => {
    return (Array.isArray(exclusions) ? exclusions : []).map((entry) => {
      const typeValue = typeof entry?.type === 'string' ? entry.type.toLowerCase() : '';
      const typeLabel =
        typeValue === 'movie' ? 'Movie' : typeValue === 'show' ? 'TV Show' : 'Collection';
      const titleParts = [];
      const titleText = typeof entry?.title === 'string' ? entry.title.trim() : '';
      if (titleText) {
        titleParts.push(titleText);
      }
      const yearNumber = entry?.year != null ? Number(entry.year) : null;
      if (Number.isFinite(yearNumber) && yearNumber > 0) {
        titleParts.push(`(${Math.trunc(yearNumber)})`);
      }
      const displayTitle = titleParts.length
        ? titleParts.join(' ')
        : titleText || entry?.ratingKey || 'Excluded item';
      return {
        ...entry,
        typeLabel,
        displayTitle,
      };
    });
  }, [exclusions]);

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

  useEffect(() => {
    const activeKeys = new Set(
      exclusionRows.map((row) => `${row.library}:::${row.ratingKey}`)
    );
    setIncludingKeys((prev) => prev.filter((key) => activeKeys.has(key)));
  }, [exclusionRows]);

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
      plexToken !== savedPlexToken ||
      Boolean(autoApplyToPlex) !== savedAutoApplyToPlex ||
      effectiveAuthMode !== savedAuthMode ||
      effectiveAuthUsername !== savedAuthUsername ||
      effectiveAuthPassword !== savedAuthPassword;
    return settingsChanged || mappingsDirty;
  }, [
    hasUnsavedChanges,
    theme,
    savedTheme,
    plexUrl,
    savedPlexUrl,
    plexToken,
    savedPlexToken,
    autoApplyToPlex,
    savedAutoApplyToPlex,
    effectiveAuthMode,
    savedAuthMode,
    effectiveAuthUsername,
    savedAuthUsername,
    effectiveAuthPassword,
    savedAuthPassword,
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

  const handleAutoApplyToPlexChange = (event) => {
    updateSettings({ autoApplyToPlex: event.target.checked });
    setStatus(null);
  };

  const handleAuthModeChange = (event) => {
    updateSettings({ authMode: event.target.value });
    setStatus(null);
  };

  const handleAuthUsernameChange = (event) => {
    updateSettings({ authUsername: event.target.value });
    setStatus(null);
  };

  const handleAuthPasswordChange = (event) => {
    updateSettings({ authPassword: event.target.value });
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

  const markIncluding = useCallback((key, active) => {
    setIncludingKeys((prev) => {
      if (active) {
        if (prev.includes(key)) {
          return prev;
        }
        return [...prev, key];
      }
      if (!prev.length) {
        return prev;
      }
      const next = prev.filter((item) => item !== key);
      return next.length === prev.length ? prev : next;
    });
  }, []);

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
    if (!hasPlexCredentials) {
      setStatus({
        type: 'error',
        message: 'Enter your Plex URL and token before refreshing libraries.',
      });
      return;
    }
    try {
      await refreshLibraries();
      setStatus({ type: 'success', message: 'Plex libraries refreshed.' });
    } catch (err) {
      setStatus({ type: 'error', message: err?.message || 'Failed to refresh libraries.' });
    }
  };

  const handleRefreshExclusions = useCallback(async () => {
    setStatus(null);
    try {
      await refreshExclusions();
      setStatus({ type: 'success', message: 'Exclusions refreshed.' });
    } catch (err) {
      setStatus({
        type: 'error',
        message: err?.message || 'Failed to refresh exclusions.',
      });
    }
  }, [refreshExclusions]);

  const handleIncludeExclusion = useCallback(
    async (entry) => {
      if (!entry) return;
      const key = `${entry.library}:::${entry.ratingKey}`;
      markIncluding(key, true);
      setStatus(null);
      try {
        await includeItem(entry.library, entry.ratingKey);
        const label = entry.title || entry.displayTitle || entry.ratingKey;
        setStatus({
          type: 'success',
          message: `${label} included again.`,
        });
      } catch (err) {
        const message = err?.message || 'Failed to include item.';
        setStatus({ type: 'error', message });
      } finally {
        markIncluding(key, false);
      }
    },
    [includeItem, markIncluding]
  );

  const performSave = useCallback(async () => {
    if (effectiveAuthMode === 'builtin' && hasAuthPassword && !hasAuthUsername) {
      setStatus({ type: 'error', message: 'Enter a login username before saving.' });
      return;
    }
    if (!isDirty) {
      setStatus({ type: 'success', message: 'Settings are already up to date.' });
      return;
    }
    setStatus(null);
    try {
      await saveSettings();
      await refreshHealth();
      const authState = await refreshAuth();
      if (authState?.enabled && !authState?.authenticated) {
        navigate('/login', { replace: true });
        return;
      }
      setStatus({ type: 'success', message: 'Settings saved successfully.' });
    } catch (err) {
      const message = err?.message || 'Failed to save settings.';
      revertSettings();
      setStatus({ type: 'error', message });
    }
  }, [
    effectiveAuthMode,
    hasAuthPassword,
    hasAuthUsername,
    isDirty,
    navigate,
    refreshAuth,
    refreshHealth,
    saveSettings,
    revertSettings,
    setStatus,
  ]);

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
        <div className="detail-heading">
          <span className="page-eyebrow">Configuration</span>
          <div className="detail-heading-title">
            <h1>Settings</h1>
          </div>
        </div>
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
        <section className="settings-card settings-card--health">
          <div className="settings-health-heading">
            <div>
              <h2>Setup Check</h2>
              <p className="settings-description">
                Checks saved Plex settings and the folders KAM can see from inside the container.
              </p>
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void refreshHealth()}
              disabled={healthLoading}
            >
              {healthLoading ? 'Checking...' : 'Run check'}
            </button>
          </div>
          {healthError ? (
            <div className="settings-health-error" role="alert">
              {healthError}
            </div>
          ) : null}
          {healthLoading && !healthReport ? (
            <div className="settings-health-empty" aria-live="polite">
              Running setup checks...
            </div>
          ) : null}
          {healthReport?.checks?.length ? (
            <div className="settings-health-grid" aria-live="polite">
              {healthReport.checks.map((check) => (
                <article key={check.key} className={`settings-health-check is-${check.status}`}>
                  <div className="settings-health-check-top">
                    <h3>{check.label}</h3>
                    <span>{check.status === 'ok' ? 'Ready' : check.status === 'error' ? 'Needs attention' : 'Review'}</span>
                  </div>
                  <p>{check.detail}</p>
                  {check.path ? <code>{check.path}</code> : null}
                </article>
              ))}
            </div>
          ) : null}
          {healthReport?.assetMappings?.length ? (
            <div className="settings-health-section">
              <h3>Mapped asset folders</h3>
              <ul className="settings-health-paths">
                {healthReport.assetMappings.map((check) => (
                  <li key={`${check.library}:${check.path}`} className={`is-${check.status}`}>
                    <strong>{check.library || check.label}</strong>
                    <span>{check.detail}</span>
                    {check.path ? <code>{check.path}</code> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="settings-health-empty">Map a Plex library to see folder checks here.</div>
          )}
          {healthReport?.collectionPaths?.length ? (
            <div className="settings-health-section">
              <h3>Collection folders</h3>
              <ul className="settings-health-paths">
                {healthReport.collectionPaths.map((check) => (
                  <li key={`${check.library}:${check.path}:${check.label}`} className={`is-${check.status}`}>
                    <strong>{check.label}</strong>
                    <span>{check.detail}</span>
                    {check.path ? <code>{check.path}</code> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
        <form onSubmit={handleSubmit} className="settings-form settings-foundation-grid">
          <section className="settings-card settings-card--theme">
            <h2>Theme</h2>
            <p className="settings-description">
              Choose how KAM looks. Changes are previewed immediately and applied once saved.
            </p>
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
          </section>

          <section className="settings-card settings-card--login">
            <h2>Login</h2>
            <p className="settings-description">
              Choose whether KAM uses its own login screen or trusts authentication from a reverse
              proxy.
            </p>
            <div className="settings-auth-mode" role="group" aria-label="Authentication mode">
              <label className="settings-radio">
                <input
                  type="radio"
                  name="authMode"
                  value="builtin"
                  checked={effectiveAuthMode === 'builtin'}
                  onChange={handleAuthModeChange}
                  disabled={busy}
                />
                <span>Built-in auth</span>
              </label>
              <label className="settings-radio">
                <input
                  type="radio"
                  name="authMode"
                  value="reverse_proxy"
                  checked={effectiveAuthMode === 'reverse_proxy'}
                  onChange={handleAuthModeChange}
                  disabled={busy}
                />
                <span>Reverse proxy auth</span>
              </label>
            </div>
            {!reverseProxyAuth ? (
              <>
                <label className="settings-input">
                  <span>Login username</span>
                  <input
                    type="text"
                    name="authUsername"
                    value={effectiveAuthUsername}
                    onChange={handleAuthUsernameChange}
                    placeholder="Enter a username"
                    autoComplete="username"
                    required={hasAuthPassword}
                    disabled={busy}
                  />
                </label>
                <label className="settings-input">
                  <span>Login password</span>
                  <input
                    type="password"
                    name="authPassword"
                    value={effectiveAuthPassword}
                    onChange={handleAuthPasswordChange}
                    placeholder={
                      savedAuthPassword
                        ? 'Saved password (leave blank to clear)'
                        : 'Enter a password'
                    }
                    autoComplete="new-password"
                    disabled={busy}
                  />
                </label>
              </>
            ) : null}
            <p className="settings-help">
              {reverseProxyAuth
                ? 'KAM will skip built-in login and trust the upstream proxy.'
                : hasAuthPassword && !hasAuthUsername
                ? 'Choose a username before saving. Password-only installs can also create one at their next login.'
                : hasAuthPassword
                ? 'Login is currently enabled. Save changes to update the username or password.'
                : 'Login is currently disabled.'}
            </p>
          </section>

          <section className="settings-card settings-card--plex">
            <h2>Plex</h2>
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
            <label className="settings-radio">
              <input
                type="checkbox"
                name="autoApplyToPlex"
                checked={Boolean(autoApplyToPlex)}
                onChange={handleAutoApplyToPlexChange}
                disabled={busy}
              />
              <span>Send artwork to Plex automatically after uploads</span>
            </label>
            <p className="settings-help">
              KAM always keeps the Kometa asset file. When enabled, it also sends direct uploads
              to Plex immediately using the URL and token above; Kometa can reapply overlays
              during its next run.
            </p>
          </section>
        </form>

        <div className="settings-management-grid">
          <section className="settings-card settings-card--libraries">
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
                <button
                  type="button"
                  onClick={handleRefreshLibraries}
                  disabled={combinedBusy || !hasPlexCredentials}
                >
                  {librariesLoading ? 'Refreshing…' : 'Refresh libraries'}
                </button>
              </div>
            </div>
            <div className="settings-libraries-table-wrapper" aria-live="polite">
              {librariesLoading ? <p className="settings-libraries-status">Loading libraries…</p> : null}
              {!librariesLoading && !libraryRows.length ? (
                <p className="settings-libraries-status">
                  {hasPlexCredentials
                    ? 'No libraries are available. Configure Plex and refresh.'
                    : 'Enter your Plex URL and token, then save and refresh to load Plex libraries.'}
                </p>
              ) : null}
              {libraryRows.length ? (
                <table className="settings-libraries-table">
                  <colgroup>
                    <col className="library-select-col" />
                    <col className="library-name-col" />
                    <col className="library-path-col" />
                    <col className="library-path-col" />
                    <col className="library-status-col" />
                    <col className="library-actions-col" />
                  </colgroup>
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
                              <div className="library-action-buttons">
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
                              </div>
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
                                <div className="library-action-buttons">
                                  <button
                                    type="button"
                                    onClick={() => handleOpenCollectionOverrideModal(row.name, override.key)}
                                    disabled={combinedBusy || !row.assetPath}
                                  >
                                    Set collections folder
                                  </button>
                                </div>
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

          <section className="settings-card settings-card--exclusions">
            <h2>Exclusions</h2>
            <p className="settings-description">
              Items excluded from KAM appear here. Include them to show them again in library views.
            </p>
            <div className="settings-exclusions-toolbar">
              <button
                type="button"
                onClick={handleRefreshExclusions}
                disabled={exclusionsLoading}
              >
                {exclusionsLoading ? 'Refreshing…' : 'Refresh exclusions'}
              </button>
            </div>
            {exclusionsLoading ? (
              <div className="settings-exclusions-empty" role="status">
                Loading exclusions…
              </div>
            ) : exclusionRows.length === 0 ? (
              <div className="settings-exclusions-empty">
                No items are currently excluded.
              </div>
            ) : (
              <ul className="settings-exclusions-list" aria-label="Excluded items">
                {exclusionRows.map((row) => {
                  const key = `${row.library}:::${row.ratingKey}`;
                  const buttonBusy = includingSet.has(key);
                  return (
                    <li key={key} className="settings-exclusion-row">
                      <div className="settings-exclusion-meta">
                        <div className="settings-exclusion-title">{row.displayTitle}</div>
                        <div className="settings-exclusion-details">
                          <span className="settings-exclusion-type">{row.typeLabel}</span>
                          <span aria-hidden="true">•</span>
                          <span>{row.library}</span>
                          {row.year ? (
                            <>
                              <span aria-hidden="true">•</span>
                              <span>{row.year}</span>
                            </>
                          ) : null}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary settings-exclusion-include"
                        onClick={() => handleIncludeExclusion(row)}
                        disabled={buttonBusy || exclusionsLoading}
                      >
                        {buttonBusy ? 'Including…' : 'Include'}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

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
