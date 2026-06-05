import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  LibraryItemsProvider,
  useLibraryItemsContext,
} from '../LibraryItemsProvider.jsx';

vi.mock('../AuthProvider.jsx', () => ({
  useAuth: () => ({
    enabled: false,
    authenticated: true,
    loading: false,
  }),
}));

vi.mock('../../theme/ThemeProvider.jsx', () => ({
  useTheme: () => ({
    savedPlexUrl: 'http://plex.local',
    savedPlexToken: 'token',
    savedLibraryMappings: [{ library: 'Movies', assetPath: '/assets/Movies' }],
    exclusions: [],
    isItemExcluded: () => false,
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
  const { library, libraries } = useLibraryItemsContext();
  return (
    <div>
      <span data-testid="library">{library}</span>
      <span data-testid="libraries">{libraries.join('|')}</span>
    </div>
  );
}

describe('LibraryItemsProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not load library grid data on non-grid routes', async () => {
    global.fetch = vi.fn();

    render(
      <MemoryRouter initialEntries={['/settings']}>
        <LibraryItemsProvider>
          <Probe />
        </LibraryItemsProvider>
      </MemoryRouter>
    );

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('prefers mapped libraries over Collections for the default grid library', async () => {
    global.fetch = vi.fn((url) => {
      const text = String(url);
      if (text === '/api/libraries') {
        return Promise.resolve(jsonResponse(['Collections', 'Movies', 'TV Shows']));
      }
      if (text.startsWith('/api/items?')) {
        return Promise.resolve(
          jsonResponse({
            page: 1,
            total_pages: 1,
            total_count: 0,
            not_ready_count: 0,
            items: [],
          })
        );
      }
      throw new Error(`Unexpected fetch: ${text}`);
    });

    render(
      <MemoryRouter initialEntries={['/libraries']}>
        <LibraryItemsProvider>
          <Probe />
        </LibraryItemsProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('library')).toHaveTextContent('Movies');
    });

    const urls = global.fetch.mock.calls.map(([url]) => String(url));
    expect(screen.getByTestId('libraries')).toHaveTextContent('Movies|TV Shows|Collections');
    expect(urls.some((url) => url.startsWith('/collections'))).toBe(false);
    expect(urls.some((url) => url.startsWith('/api/items?library=Movies'))).toBe(true);
  });
});
