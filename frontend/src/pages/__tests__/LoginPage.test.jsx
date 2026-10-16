import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../LoginPage.jsx';
import { useAuth } from '../../hooks/AuthProvider.jsx';

vi.mock('../../hooks/AuthProvider.jsx', () => ({
  useAuth: vi.fn(),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('guides password-only installs through choosing a username', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    useAuth.mockReturnValue({
      enabled: true,
      authenticated: false,
      loading: false,
      usernameRequired: true,
      login,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText('One-time update: create a username and enter your existing password.')
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: ' admin ' } });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'existing-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('admin', 'existing-password');
    });
  });

  it('asks configured installs for both credentials', () => {
    useAuth.mockReturnValue({
      enabled: true,
      authenticated: false,
      loading: false,
      usernameRequired: false,
      login: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Enter your username and password to continue.')).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText('Password')).toHaveAttribute(
      'autocomplete',
      'current-password'
    );
    expect(screen.queryByLabelText('Setup code')).not.toBeInTheDocument();
  });

  it('creates the first login with the setup code', async () => {
    const setup = vi.fn().mockResolvedValue(undefined);
    useAuth.mockReturnValue({
      enabled: true,
      authenticated: false,
      loading: false,
      usernameRequired: false,
      setupRequired: true,
      login: vi.fn(),
      setup,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText('Setup code'), { target: { value: ' ABCD-EFGH-JKMN ' } });
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: ' admin ' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'long-secret' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), {
      target: { value: 'long-secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create login' }));

    await waitFor(() => {
      expect(setup).toHaveBeenCalledWith('ABCD-EFGH-JKMN', 'admin', 'long-secret');
    });
  });

  it('checks the new password before sending the setup', () => {
    const setup = vi.fn();
    useAuth.mockReturnValue({
      enabled: true,
      authenticated: false,
      loading: false,
      setupRequired: true,
      login: vi.fn(),
      setup,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText('Setup code'), { target: { value: 'ABCD-EFGH-JKMN' } });
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'long-secret' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), {
      target: { value: 'other-secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create login' }));

    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument();
    expect(setup).not.toHaveBeenCalled();
  });
});
