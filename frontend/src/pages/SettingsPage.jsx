import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../theme/ThemeProvider.jsx';

function SettingsPage() {
  const { theme, savedTheme, loading, error, applyTheme, saveTheme, revertTheme } = useTheme();
  const [selectedTheme, setSelectedTheme] = useState(theme);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSelectedTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (error) {
      setStatus({ type: 'error', message: error });
    }
  }, [error]);

  const busy = loading || saving;
  const isDirty = useMemo(() => selectedTheme !== savedTheme, [selectedTheme, savedTheme]);

  const handleThemeChange = (event) => {
    const next = event.target.value;
    setSelectedTheme(next);
    applyTheme(next);
    setStatus(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!isDirty) {
      setStatus({ type: 'success', message: 'Theme is already up to date.' });
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      await saveTheme(selectedTheme);
      setStatus({ type: 'success', message: 'Theme preference saved.' });
    } catch (err) {
      const message = err?.message || 'Failed to save theme preference.';
      revertTheme();
      setStatus({ type: 'error', message });
    } finally {
      setSaving(false);
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
                  checked={selectedTheme === 'dark'}
                  onChange={handleThemeChange}
                />
                <span>Dark</span>
              </label>
              <label className="settings-radio">
                <input
                  type="radio"
                  name="theme"
                  value="light"
                  checked={selectedTheme === 'light'}
                  onChange={handleThemeChange}
                />
                <span>Light</span>
              </label>
            </fieldset>
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
