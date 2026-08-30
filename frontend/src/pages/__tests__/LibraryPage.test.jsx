import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import LibraryPage from '../LibraryPage.jsx';
import { useLibraryItemsContext } from '../../hooks/LibraryItemsProvider.jsx';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: vi.fn(),
}));

function mockLibraryContext(overrides = {}) {
  const context = {
    libraries: ['Movies'],
    library: 'Movies',
    setLibrary: vi.fn(),
    page: 1,
    setPage: vi.fn(),
    totalPages: 1,
    totalCount: 1,
    notReadyCount: 1,
    items: [],
    query: '',
    setQuery: vi.fn(),
    sortMode: 'title',
    setSortMode: vi.fn(),
    notReadyOnly: false,
    loading: false,
    error: null,
    reload: vi.fn(),
    refreshNotReadyCount: vi.fn().mockResolvedValue(0),
    fetchAllForLibrary: vi.fn(),
    updateItem: vi.fn(),
    ...overrides,
  };
  useLibraryItemsContext.mockReturnValue(context);
  return context;
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

describe('LibraryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('refreshes the not-ready count when the library route is entered', async () => {
    const context = mockLibraryContext();

    render(
      <MemoryRouter initialEntries={['/libraries?lib=Movies']}>
        <LibraryPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(context.refreshNotReadyCount).toHaveBeenCalledWith('Movies');
    });
    expect(context.refreshNotReadyCount).toHaveBeenCalledTimes(1);
  });

  it('honors the URL library when cached state still has another library selected', async () => {
    const context = mockLibraryContext({
      libraries: ['Kids Movies', 'TV Shows'],
      library: 'Kids Movies',
    });

    render(
      <MemoryRouter initialEntries={['/libraries?lib=TV%20Shows']}>
        <LibraryPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(context.setLibrary).toHaveBeenCalledWith('TV Shows');
    });
  });

  it('uses the route library instead of a stale legacy query parameter', async () => {
    const context = mockLibraryContext({
      libraries: ['Kids Movies', 'Movies'],
      library: 'Kids Movies',
    });

    render(
      <MemoryRouter initialEntries={['/libraries/Movies?lib=Kids+Movies']}>
        <Routes>
          <Route path="/libraries/:library" element={<LibraryPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(context.setLibrary).toHaveBeenCalledWith('Movies');
    });
  });

  it('removes the legacy query parameter from canonical library routes', async () => {
    mockLibraryContext({ library: 'Movies' });

    render(
      <MemoryRouter initialEntries={['/libraries/Movies?lib=Kids+Movies']}>
        <Routes>
          <Route
            path="/libraries/:library"
            element={
              <>
                <LibraryPage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/libraries/Movies');
    });
    expect(screen.getByTestId('location')).not.toHaveTextContent('?lib=');
  });

  it('opens poster/background choices for movie libraries', () => {
    mockLibraryContext({ notReadyCount: 0 });

    render(
      <MemoryRouter initialEntries={['/libraries?lib=Movies']}>
        <LibraryPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /import assets/i }));

    expect(screen.getByRole('dialog', { name: /import assets/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Posters')).toBeChecked();
    expect(screen.getByLabelText('Backgrounds')).toBeChecked();
  });

  it('opens series and season choices for TV libraries', () => {
    mockLibraryContext({
      libraries: ['TV Series'],
      library: 'TV Series',
      notReadyCount: 0,
    });

    render(
      <MemoryRouter initialEntries={['/libraries?lib=TV%20Series']}>
        <LibraryPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /import assets/i }));

    expect(screen.getByLabelText('Series poster')).toBeChecked();
    expect(screen.getByLabelText('Season posters')).toBeChecked();
    expect(screen.getByLabelText('Series background')).toBeChecked();
    expect(screen.getByLabelText('Season backgrounds')).toBeChecked();
  });

  it('labels a nested collections view for its parent library', () => {
    mockLibraryContext({ library: 'Movies', totalCount: 2, notReadyCount: 0 });

    render(
      <MemoryRouter initialEntries={['/libraries/Movies/collections']}>
        <Routes>
          <Route
            path="/libraries/:library/collections"
            element={<LibraryPage collectionsOnly />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Movies Collections' })).toBeInTheDocument();
    expect(screen.getByText('Collections', { selector: '.page-eyebrow' })).toBeInTheDocument();
  });
});
