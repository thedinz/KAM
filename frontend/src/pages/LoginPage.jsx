import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BrandLockup from '../components/BrandLockup.jsx';
import { useAuth } from '../hooks/AuthProvider.jsx';

const MIN_SETUP_PASSWORD_LENGTH = 8;

function LoginPage() {
  const navigate = useNavigate();
  const { enabled, authenticated, loading, usernameRequired, setupRequired, login, setup } =
    useAuth();
  const [code, setCode] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && (!enabled || authenticated)) {
      navigate('/libraries', { replace: true });
    }
  }, [authenticated, enabled, loading, navigate]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (setupRequired) {
      if (password.trim().length < MIN_SETUP_PASSWORD_LENGTH) {
        setError(`Choose a password of at least ${MIN_SETUP_PASSWORD_LENGTH} characters.`);
        return;
      }
      if (password !== confirmPassword) {
        setError('The passwords do not match.');
        return;
      }
    }
    setSubmitting(true);
    try {
      if (setupRequired) {
        await setup(code.trim(), username.trim(), password);
      } else {
        await login(username.trim(), password);
      }
      navigate('/libraries', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  let subtitle = 'Enter your username and password to continue.';
  if (setupRequired) {
    subtitle =
      "Create KAM's login. Enter the setup code from KAM's container log (on Unraid: Docker tab, KAM icon, Logs).";
  } else if (usernameRequired) {
    subtitle = 'One-time update: create a username and enter your existing password.';
  }

  const missingFields =
    !username.trim() || !password || (setupRequired && (!code.trim() || !confirmPassword));

  return (
    <main className="login-page">
      <section className="login-card">
        <h1 className="login-brand-title">
          <BrandLockup compact />
        </h1>
        <p className="login-subtitle">{subtitle}</p>
        <form onSubmit={handleSubmit} className="login-form">
          {setupRequired ? (
            <>
              <label className="login-label" htmlFor="setup-code">
                Setup code
              </label>
              <input
                id="setup-code"
                type="text"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="XXXX-XXXX-XXXX"
                autoComplete="off"
                spellCheck={false}
                autoFocus
                required
              />
            </>
          ) : null}
          <label className="login-label" htmlFor="username">
            Username
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder={usernameRequired || setupRequired ? 'Create a username' : 'Username'}
            autoComplete="username"
            autoFocus={!setupRequired}
            required
          />
          <label className="login-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={setupRequired ? 'Create a password' : 'Password'}
            autoComplete={setupRequired ? 'new-password' : 'current-password'}
            required
          />
          {setupRequired ? (
            <>
              <label className="login-label" htmlFor="confirm-password">
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Enter the password again"
                autoComplete="new-password"
                required
              />
            </>
          ) : null}
          {error ? <div className="login-error">{error}</div> : null}
          <button type="submit" className="btn" disabled={submitting || missingFields}>
            {setupRequired
              ? submitting
                ? 'Creating login…'
                : 'Create login'
              : submitting
              ? 'Signing in…'
              : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}

export default LoginPage;
