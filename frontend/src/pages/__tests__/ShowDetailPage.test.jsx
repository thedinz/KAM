import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ShowDetailPage from '../ShowDetailPage.jsx';
import { useLibraryItemsContext } from '../../hooks/LibraryItemsProvider.jsx';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: vi.fn(),
}));

vi.mock('../../theme/ThemeProvider.jsx', () => ({
  useTheme: () => ({
    excludeItem: vi.fn(),
    includeItem: vi.fn(),
    isItemExcluded: vi.fn(() => false),
    exclusionsLoading: false,
  }),
}));

vi.mock('../../components/ArtworkCard.jsx', () => ({
  default: ({ label, onImport }) => (
    <div>
      <span>{label}</span>
      {onImport ? (
        <button type="button" onClick={onImport}>
          Import {label}
        </button>
      ) : null}
    </div>
  ),
}));

function jsonResponse(payload, { ok = true, status = 200, statusText = 'OK' } = {}) {
  return {
    ok,
    status,
    statusText,
    json: () => Promise.resolve(payload),
  };
}

const showDetail = {
  title: 'Example Show',
  year: 2024,
  ratingKey: '101',
  folderExists: true,
  folderName: 'Example Show (2024)',
  posterUrl: '/fileproxy?path=poster.jpg&t=1',
  backgroundUrl: '/fileproxy?path=background.jpg&t=1',
  plexPosterUrl: 'http://plex.test/show/thumb',
  plexBackgroundUrl: 'http://plex.test/show/art',
  seasons: [
    {
      index: 1,
      title: 'Season 1',
      ratingKey: '201',
      posterUrl: '/fileproxy?path=Season01.jpg&t=1',
      plexPosterUrl: 'http://plex.test/season/thumb',
      posterExists: true,
      backgroundUrl: '/fileproxy?path=Season01_background.jpg&t=1',
      plexBackgroundUrl: 'http://plex.test/season/art',
      backgroundExists: true,
      episodes: [
        {
          seasonIndex: 1,
          index: 1,
          title: 'Pilot',
          ratingKey: '301',
          titleCardUrl: 'http://plex.test/proxy/episode/thumb',
          plexTitleCardUrl: 'http://plex.test/episode/thumb',
          titleCardExists: false,
        },
      ],
    },
  ],
};

let currentShowDetail = showDetail;

function renderShowDetailPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/TV%20Shows/shows/101']}>
      <Routes>
        <Route path="/libraries/:library/shows/:ratingKey" element={<ShowDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ShowDetailPage title cards', () => {
  beforeEach(() => {
    currentShowDetail = showDetail;
    useLibraryItemsContext.mockReturnValue({ reload: vi.fn() });
    global.fetch = vi.fn((url, options = {}) => {
      if (String(url).startsWith('/api/show?')) {
        return Promise.resolve(jsonResponse(currentShowDetail));
      }
      if (url === '/api/import/title-card') {
        return Promise.resolve(jsonResponse({ ok: true, path: '/assets/TV Shows/Example Show (2024)/S01E01.jpg' }));
      }
      if (url === '/api/import/mediux-zip') {
        return Promise.resolve(jsonResponse({ ok: true, importedCount: 4, replacedCount: 1, skippedCount: 1, errorCount: 0 }));
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('reveals title cards when a season poster is expanded and imports the episode card', async () => {
    renderShowDetailPage();

    expect(await screen.findByRole('button', { name: /Expand Season 1 assets/i })).toBeInTheDocument();
    expect(screen.queryByText('S01E01 - Pilot')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Expand Season 1 assets/i }));

    expect(await screen.findByText('S01E01 - Pilot')).toBeInTheDocument();
    expect(screen.getByText('Season 1 Background')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Import S01E01 - Pilot' }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/import/title-card',
        expect.objectContaining({ method: 'POST', body: expect.any(FormData) })
      );
    });

    const importCall = global.fetch.mock.calls.find(([url]) => url === '/api/import/title-card');
    const body = importCall[1].body;
    expect(body.get('season')).toBe('1');
    expect(body.get('episode')).toBe('1');
    expect(body.get('ratingKey')).toBe('301');
    expect(body.get('url')).toBe('http://plex.test/episode/thumb');
  });

  it('uploads a Mediux zip for the current series folder', async () => {
    const { container } = renderShowDetailPage();

    expect(await screen.findByRole('button', { name: 'Import Mediux zip' })).toBeInTheDocument();

    const zipInput = container.querySelector('input[accept*=".zip"]');
    const zipFile = new File(['zip-bytes'], 'Agatha All Along (2024).zip', { type: 'application/zip' });
    fireEvent.change(zipInput, { target: { files: [zipFile] } });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/import/mediux-zip',
        expect.objectContaining({ method: 'POST', body: expect.any(FormData) })
      );
    });

    const importCall = global.fetch.mock.calls.find(([url]) => url === '/api/import/mediux-zip');
    const body = importCall[1].body;
    expect(body.get('library')).toBe('TV Shows');
    expect(body.get('folderName')).toBe('Example Show (2024)');
    expect(body.get('file')).toBe(zipFile);
    expect(await screen.findByText('Imported 4 Mediux assets, replaced 1, skipped 1.')).toBeInTheDocument();
  });

  it('hides a missing season background for single-season shows', async () => {
    currentShowDetail = {
      ...showDetail,
      seasons: [
        {
          ...showDetail.seasons[0],
          backgroundExists: false,
          backgroundUrl: showDetail.backgroundUrl,
        },
      ],
    };

    renderShowDetailPage();

    fireEvent.click(await screen.findByRole('button', { name: /Expand Season 1 assets/i }));

    expect(screen.getByText('Season 1 Poster')).toBeInTheDocument();
    expect(screen.queryByText('Season 1 Background')).not.toBeInTheDocument();
    expect(screen.getByText('S01E01 - Pilot')).toBeInTheDocument();
  });
});
