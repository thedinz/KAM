import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
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
    kometaConfigPath: '',
    libraryMappings: [],
  },
  savedSettings: {
    theme: 'dark',
    plexUrl: '',
    plexToken: '',
    kometaConfigPath: '',
    libraryMappings: [],
  },
  theme: 'dark',
  savedTheme: 'dark',
  plexUrl: '',
  plexToken: '',
  savedPlexUrl: '',
  savedPlexToken: '',
  kometaConfigPath: '',
  savedKometaConfigPath: '',
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
});

const normalizeTheme = (value) => (value === 'light' ? 'light' : 'dark');

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
  const kometaConfigValue = raw.kometaConfigPath;

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
    kometaConfigPath: normalizePathValue(kometaConfigValue),
    libraryMappings: sanitizeLibraryMappings(raw.libraryMappings),
  };
};

export function ThemeProvider({ children }) {
  const [settings, setSettings] = useState(() => sanitizeSettings());
  const [savedSettings, setSavedSettings] = useState(() => sanitizeSettings());
  const [libraries, setLibraries] = useState([]);
  const [librariesLoading, setLibrariesLoading] = useState(false);
  const [librariesError, setLibrariesError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const isMountedRef = useRef(true);

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

  const refreshLibraries = useCallback(async () => {
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
  }, []);

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
        await refreshLibraries().catch(() => {});
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
    refreshSettings().catch(() => {});
  }, [refreshSettings]);

  useEffect(() => {
    refreshLibraries().catch(() => {});
  }, [refreshLibraries]);

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
      settings.kometaConfigPath !== savedSettings.kometaConfigPath,
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
      savedPlexUrl: savedSettings.plexUrl,
      savedPlexToken: savedSettings.plexToken,
      kometaConfigPath: settings.kometaConfigPath,
      savedKometaConfigPath: savedSettings.kometaConfigPath,
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
    ]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
