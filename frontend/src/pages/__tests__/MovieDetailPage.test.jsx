import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MovieDetailPage from '../MovieDetailPage.jsx';
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
  default: ({ label, onUpload }) => (
    <button type="button" onClick={() => onUpload(new File(['poster'], 'poster.jpg', { type: 'image/jpeg' }))}>
      Upload {label}
    </button>
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

const movieDetail = {
  title: 'Example Movie',
  year: 2024,
  ratingKey: '42',
  folderExists: true,
  folderName: 'Example Movie (2024)',
  posterUrl: '/fileproxy?path=poster.jpg&t=1',
};

function renderMovieDetailPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/movies/42']}>
      <Routes>
        <Route path="/libraries/:library/movies/:ratingKey" element={<MovieDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('MovieDetailPage library poster refresh', () => {
  let reload;

  beforeEach(() => {
    reload = vi.fn();
    useLibraryItemsContext.mockReturnValue({ reload });
    global.fetch = vi.fn((url) => {
      if (url === '/api/upload') {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      if (String(url).startsWith('/api/movie?')) {
        return Promise.resolve(jsonResponse(movieDetail));
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('refreshes the cached library items after a poster upload succeeds', async () => {
    renderMovieDetailPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Upload Poster' }));

    await waitFor(() => {
      expect(reload).toHaveBeenCalledTimes(1);
    });
  });
});
