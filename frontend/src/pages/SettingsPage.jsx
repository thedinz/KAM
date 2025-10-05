import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../theme/ThemeProvider.jsx';

function SettingsPage() {
  const {
    theme,
    savedTheme,
    plexUrl,
    plexToken,
    savedSettings,
    loading,
    saving,
    error,
    applyTheme,
    updateSettings,
    saveSettings,
    revertSettings,
  } = useTheme();
  const [status, setStatus] = useState(null);
  const savedPlexUrl = savedSettings?.plexUrl || '';
  const savedPlexToken = savedSettings?.plexToken || '';

  useEffect(() => {
    if (error) {
      setStatus({ type: 'error', message: error });
    }
  }, [error]);

  const busy = loading || saving;
  const isDirty = useMemo(() => {
    return (
      theme !== savedTheme || plexUrl !== savedPlexUrl || plexToken !== savedPlexToken
    );
  }, [theme, savedTheme, plexUrl, savedPlexUrl, plexToken, savedPlexToken]);

  const handleThemeChange = (event) => {
    const next = event.target.value;
    applyTheme(next);
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

  const handleSubmit = async (event) => {
    event.preventDefault();
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
            <div className="settings-actions">
              <button type="submit" className="btn" disabled={busy || !isDirty}>
                Save Changes
              </button>
            </div>
          </form>
          {status ? (
            <div
              className={`settings-status ${status.type}`}
              role={status.type === 'error' ? 'alert' : 'status'}
              aria-live="polite"
            >
              {status.message}
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

export default SettingsPage;
