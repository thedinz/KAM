import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { responseErrorMessage, safeJson } from '../utils/api.js';

const ThemeContext = createContext({
  settings: { theme: 'dark', plexUrl: '', plexToken: '', libraryMappings: [] },
  savedSettings: { theme: 'dark', plexUrl: '', plexToken: '', libraryMappings: [] },
  theme: 'dark',
  savedTheme: 'dark',
  plexUrl: '',
  plexToken: '',
  savedPlexUrl: '',
  savedPlexToken: '',
  libraryMappings: [],
  savedLibraryMappings: [],
  libraries: [],
  librariesLoading: false,
  librariesError: null,
  loading: false,
  saving: false,
  error: null,
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
});

const normalizeTheme = (value) => (value === 'light' ? 'light' : 'dark');

const normalizePath = (value) => {
  if (value == null) return '';
  const text = String(value).trim();
  if (!text) return '';
  return text.replace(/\\+/g, '/');
};

const sanitizeLibraryMappings = (raw = []) => {
  if (!raw) return [];
  const entries = Array.isArray(raw) ? raw : [];
  const byLibrary = new Map();
  entries.forEach((entry) => {
    if (!entry || typeof entry !== 'object') return;
    const libraryValue = entry.library ?? entry.name ?? '';
    const library = typeof libraryValue === 'string' ? libraryValue.trim() : '';
    if (!library) return;
    const assetPathValue = normalizePath(entry.assetPath ?? entry.path ?? entry.assetFolder);
    if (!assetPathValue) return;
    const collectionsPathValue = normalizePath(entry.collectionsPath ?? entry.collectionPath);
    byLibrary.set(library, {
      library,
      assetPath: assetPathValue,
      collectionsPath: collectionsPathValue,
    });
  });
  return Array.from(byLibrary.values()).sort((a, b) => a.library.localeCompare(b.library));
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
      const assetPathValue = normalizePath(entry.assetPath);
      const collectionsPathValue = normalizePath(entry.collectionsPath);
      return {
        name,
        type: typeValue ? String(typeValue) : null,
        key: keyValue ? String(keyValue) : null,
        assetPath: assetPathValue,
        collectionsPath: collectionsPathValue,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
};

const sanitizeSettings = (raw = {}) => {
  const themeValue = normalizeTheme(raw.theme);
  const plexUrlValue = raw.plexUrl;
  const plexTokenValue = raw.plexToken;

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
      .map((name) => (typeof name === 'string' ? name.trim() : ''))
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
            : normalizePath(payload.assetPath);
        const collectionsUpdate =
          payload.collectionsPath === undefined
            ? existing?.collectionsPath ?? ''
            : normalizePath(payload.collectionsPath);
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
      libraryMappings: settings.libraryMappings,
      savedLibraryMappings: savedSettings.libraryMappings,
      libraries,
      librariesLoading,
      librariesError,
      loading,
      saving,
      error,
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
    ]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
