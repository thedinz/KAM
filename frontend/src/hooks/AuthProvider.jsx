import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState({
    mode: 'builtin',
    enabled: false,
    authenticated: true,
    usernameRequired: false,
    loading: true,
  });

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/auth/status', { credentials: 'same-origin' });
      if (!response.ok) {
        if (response.status === 404) {
          const nextState = {
            mode: 'builtin',
            enabled: false,
            authenticated: true,
            usernameRequired: false,
            loading: false,
          };
          setAuthState(nextState);
          return nextState;
        }
        throw new Error('Unable to check auth status');
      }
      const data = await response.json();
      const nextState = {
        mode: data.mode === 'reverse_proxy' ? 'reverse_proxy' : 'builtin',
        enabled: Boolean(data.enabled),
        authenticated: Boolean(data.authenticated),
        usernameRequired: Boolean(data.usernameRequired),
        loading: false,
      };
      setAuthState(nextState);
      return nextState;
    } catch (error) {
      const nextState = {
        mode: 'builtin',
        enabled: false,
        authenticated: true,
        usernameRequired: false,
        loading: false,
      };
      setAuthState(nextState);
      return nextState;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (username, password) => {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message = payload.detail || 'Login failed';
      throw new Error(message);
    }

    setAuthState({
      mode: 'builtin',
      enabled: true,
      authenticated: true,
      usernameRequired: false,
      loading: false,
    });
  }, []);

  const logout = useCallback(async () => {
    await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    setAuthState((prev) => ({
      mode: prev.mode,
      enabled: prev.enabled,
      authenticated: prev.mode === 'reverse_proxy' ? true : false,
      loading: false,
    }));
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
