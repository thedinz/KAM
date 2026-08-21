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
  });
});
