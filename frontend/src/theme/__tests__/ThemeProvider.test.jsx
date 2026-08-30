import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider, useTheme } from '../ThemeProvider.jsx';

vi.mock('../../hooks/AuthProvider.jsx', () => ({
  useAuth: () => ({
    enabled: false,
    authenticated: true,
    loading: false,
  }),
}));

function jsonResponse(data) {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: () => Promise.resolve(data),
  };
}

function Probe() {
  const { libraries } = useTheme();
  return <span data-testid="libraries">{libraries.map((entry) => entry.name).join('|')}</span>;
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      const text = String(url);
      if (text === '/api/settings') {
        return Promise.resolve(
          jsonResponse({
            theme: 'dark',
            plexUrl: 'http://plex.local',
            plexToken: 'token',
            libraryMappings: [
              { library: 'Movies', assetPath: '/assets/Movies', collectionsPath: '' },
            ],
          })
        );
      }
      if (text === '/api/settings/libraries') {
        return Promise.resolve(
          jsonResponse([
            {
              name: 'Movies',
              type: 'movie',
              key: '1',
              assetPath: '/assets/Movies',
              collectionsPath: null,
            },
          ])
        );
      }
      if (text === '/api/exclusions') {
        return Promise.resolve(jsonResponse([]));
      }
      throw new Error(`Unexpected fetch: ${text}`);
    });
  });

  it('loads sidebar library metadata without visiting Settings', async () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('libraries')).toHaveTextContent('Movies');
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/settings/libraries');
  });
});
