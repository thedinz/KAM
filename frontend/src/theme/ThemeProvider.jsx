import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { responseErrorMessage, safeJson } from '../utils/api.js';

const ThemeContext = createContext({
  settings: { theme: 'dark', plexUrl: '', plexToken: '' },
  savedSettings: { theme: 'dark', plexUrl: '', plexToken: '' },
  theme: 'dark',
  savedTheme: 'dark',
  plexUrl: '',
  plexToken: '',
  savedPlexUrl: '',
  savedPlexToken: '',
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
});

const normalizeTheme = (value) => (value === 'light' ? 'light' : 'dark');

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
  };
};

export function ThemeProvider({ children }) {
  const [settings, setSettings] = useState(() => sanitizeSettings());
  const [savedSettings, setSavedSettings] = useState(() => sanitizeSettings());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const isMountedRef = useRef(true);

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
    [settings]
  );

  useEffect(() => {
    refreshSettings().catch(() => {});
  }, [refreshSettings]);

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
    }),
    [
      settings,
      savedSettings,
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
    ]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
