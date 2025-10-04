import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { responseErrorMessage, safeJson } from '../utils/api.js';

const ThemeContext = createContext({
  theme: 'dark',
  savedTheme: 'dark',
  loading: false,
  error: null,
  applyTheme: () => {},
  saveTheme: async () => 'dark',
  refreshTheme: async () => 'dark',
  revertTheme: () => {},
});

const normalizeTheme = (value) => (value === 'light' ? 'light' : 'dark');

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('dark');
  const [savedTheme, setSavedTheme] = useState('dark');
  const [loading, setLoading] = useState(false);
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
    document.documentElement.setAttribute('data-theme', normalizeTheme(theme));
  }, [theme]);

  const applyTheme = useCallback((value) => {
    setTheme(normalizeTheme(value));
  }, []);

  const refreshTheme = useCallback(async () => {
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
      const nextTheme = normalizeTheme(data?.theme);
      if (isMountedRef.current) {
        setSavedTheme(nextTheme);
        setTheme(nextTheme);
      }
      return nextTheme;
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

  const saveTheme = useCallback(
    async (value) => {
      const nextTheme = normalizeTheme(value);
      if (isMountedRef.current) {
        setLoading(true);
        setError(null);
      }
      try {
        const response = await fetch('/api/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ theme: nextTheme }),
        });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        if (isMountedRef.current) {
          setSavedTheme(nextTheme);
          setTheme(nextTheme);
        }
        return nextTheme;
      } catch (err) {
        const message = err?.message || 'Failed to save settings';
        if (isMountedRef.current) {
          setError(message);
        }
        throw new Error(message);
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    refreshTheme().catch(() => {});
  }, [refreshTheme]);

  const revertTheme = useCallback(() => {
    if (!isMountedRef.current) return;
    setTheme(normalizeTheme(savedTheme));
  }, [savedTheme]);

  const value = useMemo(
    () => ({
      theme,
      savedTheme,
      loading,
      error,
      applyTheme,
      saveTheme,
      refreshTheme,
      revertTheme,
    }),
    [theme, savedTheme, loading, error, applyTheme, saveTheme, refreshTheme, revertTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
