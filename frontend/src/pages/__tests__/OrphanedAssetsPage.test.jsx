import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OrphanedAssetsPage from '../OrphanedAssetsPage.jsx';

const setLibrary = vi.fn();
const reload = vi.fn();

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: () => ({ library: 'Movies', setLibrary, reload }),
}));

const scanPayload = {
  library: 'Movies',
  root: '/assets/Movies',
  totalCount: 2,
  items: [
    {
      folderName: 'Step Brothers (2008)',
      title: 'Step Brothers',
      year: 2008,
      assetCount: 2,
      sizeBytes: 2048,
      posterUrl: '/fileproxy?path=poster',
    },
    {
      folderName: 'Old Movie (1999)',
      title: 'Old Movie',
      year: 1999,
      assetCount: 1,
      sizeBytes: 1024,
      posterUrl: null,
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/orphaned-assets']}>
      <Routes>
        <Route path="/libraries/:library/orphaned-assets" element={<OrphanedAssetsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('OrphanedAssetsPage', () => {
  beforeEach(() => {
    setLibrary.mockReset();
    reload.mockReset();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    global.fetch = vi.fn(async (_url, options = {}) => {
      if (options.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            library: 'Movies',
            deletedCount: 2,
            deleted: ['Step Brothers (2008)', 'Old Movie (1999)'],
            skipped: [],
            errors: [],
          }),
        };
      }
      const scanCalls = global.fetch.mock.calls.filter(([, requestOptions = {}]) => requestOptions.method !== 'POST');
      return {
        ok: true,
        json: async () => (scanCalls.length > 1 ? { ...scanPayload, totalCount: 0, items: [] } : scanPayload),
      };
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('selects all orphaned folders and deletes them after confirmation', async () => {
    renderPage();

    const stepBrothers = await screen.findByRole('heading', { name: /Step Brothers/ });
    expect(stepBrothers.closest('article')).toHaveTextContent('2.0 KB');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all' }));
    expect(screen.getByText('2 selected')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete selected' }));

    await waitFor(() => expect(window.confirm).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      const deleteCall = global.fetch.mock.calls.find(([, options = {}]) => options.method === 'POST');
      expect(JSON.parse(deleteCall[1].body)).toEqual({
        library: 'Movies',
        folderNames: ['Step Brothers (2008)', 'Old Movie (1999)'],
      });
    });
    expect(await screen.findByText('No orphaned asset folders')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Deleted 2 asset folders.');
    expect(reload).toHaveBeenCalled();
  });
});
