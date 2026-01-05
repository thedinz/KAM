import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState({
    enabled: false,
    authenticated: true,
    loading: true,
  });

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/auth/status', { credentials: 'same-origin' });
      if (!response.ok) {
        if (response.status === 404) {
          setAuthState({ enabled: false, authenticated: true, loading: false });
          return;
        }
        throw new Error('Unable to check auth status');
      }
      const data = await response.json();
      setAuthState({
        enabled: Boolean(data.enabled),
        authenticated: Boolean(data.authenticated),
        loading: false,
      });
    } catch (error) {
      setAuthState({ enabled: false, authenticated: true, loading: false });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (password) => {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message = payload.detail || 'Login failed';
      throw new Error(message);
    }

    setAuthState({ enabled: true, authenticated: true, loading: false });
  }, []);

  const logout = useCallback(async () => {
    await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    setAuthState({ enabled: true, authenticated: false, loading: false });
  }, []);

  const value = useMemo(
    () => ({
      ...authState,
      refresh,
      login,
      logout,
    }),
    [authState, refresh, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
