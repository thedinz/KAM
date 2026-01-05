import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/AuthProvider.jsx';

function LoginPage() {
  const navigate = useNavigate();
  const { enabled, authenticated, loading, login } = useAuth();
  const [password, setPassword] = useState('');
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
    setSubmitting(true);
    try {
      await login(password);
      navigate('/libraries', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card">
        <h1>KAM</h1>
        <p className="login-subtitle">Enter your password to continue.</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label className="login-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            autoComplete="current-password"
            required
          />
          {error ? <div className="login-error">{error}</div> : null}
          <button type="submit" className="btn" disabled={submitting || !password}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}

export default LoginPage;
