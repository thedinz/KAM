import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../hooks/AuthProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import {
  areLibraryMappingsEqual,
  createLibraryMappingLookup,
  normalizeLibraryName,
  normalizePathValue,
  sanitizeCollectionSections,
  sanitizeLibraryMappings,
} from '../utils/libraryMappings.js';

const ThemeContext = createContext({
  settings: {
    theme: 'dark',
    plexUrl: '',
    plexToken: '',
    autoApplyToPlex: false,
    authMode: 'builtin',
    authPassword: '',
    libraryMappings: [],
  },
  savedSettings: {
    theme: 'dark',
    plexUrl: '',
    plexToken: '',
    autoApplyToPlex: false,
    authMode: 'builtin',
    authPassword: '',
    libraryMappings: [],
  },
  theme: 'dark',
  savedTheme: 'dark',
  plexUrl: '',
  plexToken: '',
  autoApplyToPlex: false,
  authMode: 'builtin',
  authPassword: '',
  savedPlexUrl: '',
  savedPlexToken: '',
  savedAutoApplyToPlex: false,
  savedAuthMode: 'builtin',
  savedAuthPassword: '',
  libraryMappings: [],
  savedLibraryMappings: [],
  libraries: [],
  librariesLoading: false,
  librariesError: null,
  loading: false,
  saving: false,
  error: null,
  settingsDirty: false,
  libraryMappingsDirty: false,
  hasUnsavedChanges: false,
  exclusions: [],
  exclusionsLoading: false,
  exclusionsError: null,
  applyTheme: () => {},
  updateSettings: () => {},
  saveSettings: async () => ({ theme: 'dark', plexUrl: '', plexToken: '' }),
  refreshSettings: async () => ({ theme: 'dark', plexUrl: '', plexToken: '' }),
  revertSettings: () => {},
  saveTheme: async () => 'dark',
  refreshTheme: async () => 'dark',
  revertTheme: () => {},
  refreshLibraries: async () => [],
  setLibraryMapping: () => {},
  setLibraryMappings: () => {},
  getLibraryMapping: () => null,
  revertLibraryMapping: () => {},
  revertLibraryMappings: () => {},
  refreshExclusions: async () => [],
  excludeItem: async () => ({}),
  includeItem: async () => {},
  isItemExcluded: () => false,
});

const normalizeTheme = (value) => (value === 'light' ? 'light' : 'dark');
const normalizeAuthMode = (value) => {
  const text = value == null ? '' : String(value).trim().toLowerCase().replace('-', '_');
  return text === 'reverse_proxy' || text === 'proxy' ? 'reverse_proxy' : 'builtin';
};

const sanitizeLibrariesList = (raw) => {
  if (!raw) return [];
  const entries = Array.isArray(raw) ? raw : [];
  return entries
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const nameValue = entry.name ?? entry.library ?? '';
      const name = typeof nameValue === 'string' ? nameValue.trim() : '';
      if (!name) return null;
      const typeValue = entry.type ?? entry.libraryType ?? null;
      const keyValue = entry.key ?? entry.id ?? null;
      const assetPathValue = normalizePathValue(entry.assetPath);
      const collectionsPathValue = normalizePathValue(entry.collectionsPath);
      const collectionAssetPathsValue = Array.isArray(entry.collectionAssetPaths)
        ? entry.collectionAssetPaths.map((value) => normalizePathValue(value)).filter(Boolean)
        : [];
      const rawOverrides = Array.isArray(entry.collectionOverrides)
        ? entry.collectionOverrides
        : [];
      const collectionOverridesValue = rawOverrides
        .map((override) => {
          if (!override || typeof override !== 'object') return null;
          const nameValue = override.name ?? override.section ?? override.default;
          const name = typeof nameValue === 'string' ? nameValue.trim() : '';
          if (!name) return null;
          const collectionsOverridePath = normalizePathValue(override.collectionsPath);
          const suggestions = Array.isArray(override.suggestionPaths)
            ? override.suggestionPaths.map((value) => normalizePathValue(value)).filter(Boolean)
            : [];
          return {
            name,
            collectionsPath: collectionsOverridePath,
            suggestionPaths: Array.from(new Set(suggestions)),
          };
        })
        .filter(Boolean)
        .sort((a, b) => a.name.localeCompare(b.name));
      return {
        name,
        type: typeValue ? String(typeValue) : null,
        key: keyValue ? String(keyValue) : null,
        assetPath: assetPathValue,
        collectionsPath: collectionsPathValue,
        collectionAssetPaths: collectionAssetPathsValue,
        collectionOverrides: collectionOverridesValue,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
};

const sanitizeSettings = (raw = {}) => {
  const themeValue = normalizeTheme(raw.theme);
  const plexUrlValue = raw.plexUrl;
  const plexTokenValue = raw.plexToken;
  const autoApplyToPlexValue = raw.autoApplyToPlex;
  const authModeValue = normalizeAuthMode(raw.authMode);
  const authPasswordValue = raw.authPassword;

  return {
    theme: themeValue,
    plexUrl:
      typeof plexUrlValue === 'string'
        ? plexUrlValue.trim()
        : plexUrlValue
        ? String(plexUrlValue)
        : '',
    plexToken:
      typeof plexTokenValue === 'string'
        ? plexTokenValue.trim()
        : plexTokenValue
        ? String(plexTokenValue)
        : '',
    autoApplyToPlex: Boolean(autoApplyToPlexValue),
    authMode: authModeValue,
    authPassword:
      typeof authPasswordValue === 'string'
        ? authPasswordValue.trim()
        : authPasswordValue
        ? String(authPasswordValue)
        : '',
    libraryMappings: sanitizeLibraryMappings(raw.libraryMappings),
  };
};

const normalizeExclusionType = (value) => {
  if (value == null) return null;
  const text = String(value).trim().toLowerCase();
  if (!text) return null;
  if (['series', 'tv', 'tv show', 'television'].includes(text)) return 'show';
  if (text.startsWith('collection')) return 'collection';
  if (text === 'movie' || text === 'show' || text === 'collection') return text;
  return null;
};

const normalizeExclusionText = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  return text;
};

const normalizeExclusionYear = (value) => {
  if (value == null) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  const intVal = Math.trunc(num);
  if (intVal <= 0) return null;
  return intVal;
};

const sanitizeExclusionEntry = (entry) => {
  if (!entry || typeof entry !== 'object') return null;
  const library = normalizeExclusionText(entry.library);
  const ratingKey = normalizeExclusionText(entry.ratingKey);
  const type = normalizeExclusionType(entry.type);
  if (!library || !ratingKey || !type) return null;
  const title = normalizeExclusionText(entry.title);
  const year = normalizeExclusionYear(entry.year);
  const excludedAt = normalizeExclusionText(entry.excludedAt);
  const result = {
    library,
    ratingKey,
    type,
  };
  if (title) result.title = title;
  if (year) result.year = year;
  if (excludedAt) result.excludedAt = excludedAt;
  return result;
};

const sanitizeExclusions = (raw) => {
  if (!raw) return [];
  const entries = Array.isArray(raw) ? raw : [];
  const sanitized = entries
    .map((entry) => sanitizeExclusionEntry(entry))
    .filter(Boolean);
  sanitized.sort((a, b) => {
    const libraryCompare = a.library.localeCompare(b.library);
    if (libraryCompare !== 0) return libraryCompare;
    const typeCompare = a.type.localeCompare(b.type);
    if (typeCompare !== 0) return typeCompare;
    const titleA = a.title || '';
    const titleB = b.title || '';
    const titleCompare = titleA.localeCompare(titleB);
    if (titleCompare !== 0) return titleCompare;
    return a.ratingKey.localeCompare(b.ratingKey);
  });
  return sanitized;
};

export function ThemeProvider({ children }) {
  const { enabled: authEnabled, authenticated, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState(() => sanitizeSettings());
  const [savedSettings, setSavedSettings] = useState(() => sanitizeSettings());
  const [libraries, setLibraries] = useState([]);
  const [librariesLoading, setLibrariesLoading] = useState(false);
  const [librariesError, setLibrariesError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [exclusions, setExclusions] = useState(() => sanitizeExclusions());
  const [exclusionsLoading, setExclusionsLoading] = useState(false);
  const [exclusionsError, setExclusionsError] = useState(null);
  const isMountedRef = useRef(true);
  const canFetch = !authLoading && (!authEnabled || authenticated);

  const getExclusionKey = useCallback((libraryName, ratingKeyValue) => {
    const libraryText = normalizeExclusionText(libraryName);
    const ratingKeyText = normalizeExclusionText(ratingKeyValue);
    if (!libraryText || !ratingKeyText) return '';
    return `${libraryText}:::${ratingKeyText}`;
  }, []);

  const applyLibraryMappingUpdates = useCallback((libraryNames, updates) => {
    const names = Array.isArray(libraryNames) ? libraryNames : [libraryNames];
    if (!names.length) return;
    const normalized = names
      .map((name) => normalizeLibraryName(name))
      .filter(Boolean);
    if (!normalized.length) return;
    const payload = updates && typeof updates === 'object' ? updates : {};
    setSettings((prev) => {
      const base = sanitizeSettings(prev);
      const nextMappings = normalized.reduce((acc, library) => {
        const list = Array.isArray(acc) ? [...acc] : [];
        const index = list.findIndex((entry) => entry.library === library);
        const existing = index >= 0 ? list[index] : null;
        const assetUpdate =
          payload.assetPath === undefined
            ? existing?.assetPath ?? ''
            : normalizePathValue(payload.assetPath);
        const collectionsUpdate =
          payload.collectionsPath === undefined
            ? existing?.collectionsPath ?? ''
            : normalizePathValue(payload.collectionsPath);
        const sectionsUpdate =
          payload.collectionSections === undefined
            ? existing?.collectionSections ?? []
            : sanitizeCollectionSections(payload.collectionSections);
        if (!assetUpdate) {
          if (index >= 0) {
            list.splice(index, 1);
          }
          return sanitizeLibraryMappings(list);
        }
        const nextEntry = {
          library,
          assetPath: assetUpdate,
          collectionsPath: collectionsUpdate,
        };
        if (sectionsUpdate.length) {
          nextEntry.collectionSections = sectionsUpdate;
        }
        if (index >= 0) {
          list[index] = nextEntry;
        } else {
          list.push(nextEntry);
        }
        return sanitizeLibraryMappings(list);
      }, base.libraryMappings);
      return sanitizeSettings({ ...base, libraryMappings: nextMappings });
    });
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const refreshExclusions = useCallback(async () => {
    if (isMountedRef.current) {
      setExclusionsLoading(true);
      setExclusionsError(null);
    }
    try {
      const response = await fetch('/api/exclusions');
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      const next = sanitizeExclusions(data);
      if (isMountedRef.current) {
        setExclusions(next);
      }
      return next;
    } catch (err) {
      const message = err?.message || 'Failed to load exclusions';
      if (isMountedRef.current) {
        setExclusions([]);
        setExclusionsError(message);
      }
      throw new Error(message);
    } finally {
      if (isMountedRef.current) {
        setExclusionsLoading(false);
      }
    }
  }, []);

  const excludeItem = useCallback(
    async (payload) => {
      const base = payload && typeof payload === 'object' ? payload : {};
      const libraryName = normalizeExclusionText(base.library);
      const ratingKeyValue = normalizeExclusionText(base.ratingKey);
      const typeValue = normalizeExclusionType(base.type);
      if (!libraryName || !ratingKeyValue || !typeValue) {
        throw new Error('Library, rating key, and type are required to exclude an item.');
      }
      const body = {
        library: libraryName,
        ratingKey: ratingKeyValue,
        type: typeValue,
      };
      const titleValue = normalizeExclusionText(base.title);
      if (titleValue) {
        body.title = titleValue;
      }
      const yearValue = normalizeExclusionYear(base.year);
      if (yearValue) {
        body.year = yearValue;
      }

      const response = await fetch('/api/exclusions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }

      const stored = sanitizeExclusionEntry(data) || {
        library: libraryName,
        ratingKey: ratingKeyValue,
        type: typeValue,
      };
      if (isMountedRef.current) {
        setExclusions((prev) => {
          const list = Array.isArray(prev) ? [...prev] : [];
          const key = getExclusionKey(libraryName, ratingKeyValue);
          const index = list.findIndex(
            (entry) => getExclusionKey(entry.library, entry.ratingKey) === key
          );
          if (index >= 0) {
            list[index] = stored;
          } else {
            list.push(stored);
          }
          return sanitizeExclusions(list);
        });
        setExclusionsError(null);
      }

      return stored;
    },
    [getExclusionKey]
  );

  const includeItem = useCallback(
    async (libraryName, ratingKeyValue) => {
      const libraryText = normalizeExclusionText(libraryName);
      const ratingKeyText = normalizeExclusionText(ratingKeyValue);
      if (!libraryText || !ratingKeyText) {
        throw new Error('Library and rating key are required to include an item.');
      }
      const url = `/api/exclusions/${encodeURIComponent(libraryText)}/${encodeURIComponent(
        ratingKeyText
      )}`;
      const response = await fetch(url, { method: 'DELETE' });
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      if (isMountedRef.current) {
        setExclusions((prev) => {
          const list = Array.isArray(prev) ? prev : [];
          const key = getExclusionKey(libraryText, ratingKeyText);
          const next = list.filter(
            (entry) => getExclusionKey(entry.library, entry.ratingKey) !== key
          );
          return sanitizeExclusions(next);
        });
        setExclusionsError(null);
      }
    },
    [getExclusionKey]
  );

  const isItemExcluded = useCallback(
    (libraryName, ratingKeyValue) => {
      const key = getExclusionKey(libraryName, ratingKeyValue);
      if (!key) return false;
      return exclusions.some(
        (entry) => getExclusionKey(entry.library, entry.ratingKey) === key
      );
    },
    [exclusions, getExclusionKey]
  );

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.setAttribute('data-theme', normalizeTheme(settings.theme));
  }, [settings.theme]);

  const updateSettings = useCallback((updates) => {
    if (!isMountedRef.current) return;
    setSettings((prev) => sanitizeSettings({ ...prev, ...updates }));
  }, []);

  const applyTheme = useCallback((value) => {
    updateSettings({ theme: value });
  }, [updateSettings]);

  const refreshSettings = useCallback(async () => {
    if (isMountedRef.current) {
      setLoading(true);
      setError(null);
    }
    try {
      const response = await fetch('/api/settings');
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      const next = sanitizeSettings(data);
      if (isMountedRef.current) {
        setSavedSettings(next);
        setSettings(next);
      }
      return next;
    } catch (err) {
      const message = err?.message || 'Failed to load settings';
      if (isMountedRef.current) {
        setError(message);
      }
      throw new Error(message);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const hasPlexCredentials = useMemo(
    () => Boolean(settings.plexUrl && settings.plexToken),
    [settings.plexUrl, settings.plexToken]
  );

  const refreshLibraries = useCallback(
    async (options = {}) => {
      const force = Boolean(options?.force);
      if (!hasPlexCredentials && !force) {
        if (isMountedRef.current) {
          setLibraries([]);
          setLibrariesError(null);
        }
        return [];
      }
      if (isMountedRef.current) {
        setLibrariesLoading(true);
        setLibrariesError(null);
      }
      try {
        const response = await fetch('/api/settings/libraries');
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        const next = sanitizeLibrariesList(data);
        if (isMountedRef.current) {
          setLibraries(next);
        }
        return next;
      } catch (err) {
        const message = err?.message || 'Failed to load libraries';
        if (isMountedRef.current) {
          setLibraries([]);
          setLibrariesError(message);
        }
        throw new Error(message);
      } finally {
        if (isMountedRef.current) {
          setLibrariesLoading(false);
        }
      }
    },
    [hasPlexCredentials]
  );

  const saveSettings = useCallback(
    async (overrides = null) => {
      const payload = sanitizeSettings({ ...settings, ...(overrides ?? {}) });
      if (isMountedRef.current) {
        setSaving(true);
        setError(null);
      }
      try {
        const response = await fetch('/api/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        const next = sanitizeSettings(data);
        if (isMountedRef.current) {
          setSavedSettings(next);
          setSettings(next);
        }
        const nextHasCredentials = Boolean(next.plexUrl && next.plexToken);
        await refreshLibraries({ force: nextHasCredentials }).catch(() => {});
        return next;
      } catch (err) {
        const message = err?.message || 'Failed to save settings';
        if (isMountedRef.current) {
          setError(message);
        }
        throw new Error(message);
      } finally {
        if (isMountedRef.current) {
          setSaving(false);
        }
      }
    },
    [settings, refreshLibraries]
  );

  useEffect(() => {
    if (!canFetch) return;
    refreshSettings().catch(() => {});
  }, [canFetch, refreshSettings]);

  useEffect(() => {
    if (!canFetch) return;
    refreshExclusions().catch(() => {});
  }, [canFetch, refreshExclusions]);

  const revertSettings = useCallback(() => {
    if (!isMountedRef.current) return;
    setSettings(sanitizeSettings(savedSettings));
  }, [savedSettings]);

  const libraryMappingLookup = useMemo(
    () => createLibraryMappingLookup(settings.libraryMappings),
    [settings.libraryMappings]
  );

  const savedLibraryMappingLookup = useMemo(
    () => createLibraryMappingLookup(savedSettings.libraryMappings),
    [savedSettings.libraryMappings]
  );

  const libraryMappingsDirty = useMemo(
    () => !areLibraryMappingsEqual(settings.libraryMappings, savedSettings.libraryMappings),
    [settings.libraryMappings, savedSettings.libraryMappings]
  );

  const settingsDirty = useMemo(
    () =>
      settings.theme !== savedSettings.theme ||
      settings.plexUrl !== savedSettings.plexUrl ||
      settings.plexToken !== savedSettings.plexToken ||
      settings.autoApplyToPlex !== savedSettings.autoApplyToPlex ||
      settings.authMode !== savedSettings.authMode ||
      settings.authPassword !== savedSettings.authPassword,
    [settings, savedSettings]
  );

  const hasUnsavedChanges = settingsDirty || libraryMappingsDirty;

  const saveTheme = useCallback(
    async (value) => {
      const result = await saveSettings({ theme: value });
      return result.theme;
    },
    [saveSettings]
  );

  const refreshTheme = useCallback(async () => {
    const result = await refreshSettings();
    return result.theme;
  }, [refreshSettings]);

  const revertTheme = useCallback(() => {
    revertSettings();
  }, [revertSettings]);

  const setLibraryMapping = useCallback(
    (libraryName, updates = {}) => {
      applyLibraryMappingUpdates(libraryName, updates);
    },
    [applyLibraryMappingUpdates]
  );

  const setLibraryMappings = useCallback(
    (libraryNames, updates = {}) => {
      applyLibraryMappingUpdates(libraryNames, updates);
    },
    [applyLibraryMappingUpdates]
  );

  const getLibraryMapping = useCallback(
    (libraryName) => {
      const name = normalizeLibraryName(libraryName);
      if (!name) return null;
      const entry = libraryMappingLookup.get(name);
      return entry ? { ...entry } : null;
    },
    [libraryMappingLookup]
  );

  const revertLibraryMappings = useCallback(
    (libraryNames) => {
      const names = Array.isArray(libraryNames) ? libraryNames : [libraryNames];
      const normalized = names.map((name) => normalizeLibraryName(name)).filter(Boolean);
      if (!normalized.length) return;
      setSettings((prev) => {
        const base = sanitizeSettings(prev);
        let nextMappings = sanitizeLibraryMappings(base.libraryMappings);
        let changed = false;
        normalized.forEach((name) => {
          const saved = savedLibraryMappingLookup.get(name);
          const index = nextMappings.findIndex((entry) => entry.library === name);
          if (saved) {
            if (index >= 0) {
              const existing = nextMappings[index];
              if (
                existing.assetPath !== saved.assetPath ||
                existing.collectionsPath !== saved.collectionsPath
              ) {
                nextMappings[index] = { ...saved };
                changed = true;
              }
            } else {
              nextMappings.push({ ...saved });
              changed = true;
            }
          } else if (index >= 0) {
            nextMappings.splice(index, 1);
            changed = true;
          }
        });
        if (!changed) {
          return base;
        }
        return sanitizeSettings({ ...base, libraryMappings: nextMappings });
      });
    },
    [savedLibraryMappingLookup]
  );

  const revertLibraryMapping = useCallback(
    (libraryName) => {
      if (!libraryName) return;
      revertLibraryMappings([libraryName]);
    },
    [revertLibraryMappings]
  );

  const value = useMemo(
    () => ({
      settings,
      savedSettings,
      theme: settings.theme,
      savedTheme: savedSettings.theme,
      plexUrl: settings.plexUrl,
      plexToken: settings.plexToken,
      autoApplyToPlex: settings.autoApplyToPlex,
      authMode: settings.authMode,
      authPassword: settings.authPassword,
      savedPlexUrl: savedSettings.plexUrl,
      savedPlexToken: savedSettings.plexToken,
      savedAutoApplyToPlex: savedSettings.autoApplyToPlex,
      savedAuthMode: savedSettings.authMode,
      savedAuthPassword: savedSettings.authPassword,
      libraryMappings: settings.libraryMappings,
      savedLibraryMappings: savedSettings.libraryMappings,
      libraries,
      librariesLoading,
      librariesError,
      loading,
      saving,
      error,
      settingsDirty,
      libraryMappingsDirty,
      hasUnsavedChanges,
      exclusions,
      exclusionsLoading,
      exclusionsError,
      applyTheme,
      updateSettings,
      saveSettings,
      refreshSettings,
      revertSettings,
      saveTheme,
      refreshTheme,
      revertTheme,
      refreshLibraries,
      setLibraryMapping,
      setLibraryMappings,
      getLibraryMapping,
      revertLibraryMapping,
      revertLibraryMappings,
      refreshExclusions,
      excludeItem,
      includeItem,
      isItemExcluded,
    }),
    [
      settings,
      savedSettings,
      libraries,
      librariesLoading,
      librariesError,
      loading,
      saving,
      error,
      settingsDirty,
      libraryMappingsDirty,
      hasUnsavedChanges,
      exclusions,
      exclusionsLoading,
      exclusionsError,
      applyTheme,
      updateSettings,
      saveSettings,
      refreshSettings,
      revertSettings,
      saveTheme,
      refreshTheme,
      revertTheme,
      refreshLibraries,
      setLibraryMapping,
      setLibraryMappings,
      getLibraryMapping,
      revertLibraryMapping,
      revertLibraryMappings,
      refreshExclusions,
      excludeItem,
      includeItem,
      isItemExcluded,
    ]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
