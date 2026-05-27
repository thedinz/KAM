import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
});
