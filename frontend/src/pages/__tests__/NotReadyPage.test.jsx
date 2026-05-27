import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import NotReadyPage from '../NotReadyPage.jsx';
import { useLibraryItemsContext } from '../../hooks/LibraryItemsProvider.jsx';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: vi.fn(),
}));

vi.mock('../../components/FolderFinderModal.jsx', () => ({
  default: ({ isOpen, onFolderAssigned }) =>
    isOpen ? (
      <button type="button" onClick={() => onFolderAssigned({ folderName: 'Needs Assets (2020)' })}>
        Use selected folder
      </button>
    ) : null,
}));

function jsonResponse(data) {
  return {
    ok: true,
    json: () => Promise.resolve(data),
  };
}

function renderNotReadyPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/not-ready']}>
      <Routes>
        <Route path="/libraries/:library/not-ready" element={<NotReadyPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('NotReadyPage', () => {
  let updateItem;
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    updateItem = vi.fn();
    useLibraryItemsContext.mockImplementation(() => {
      const [notReadyCount, setNotReadyCount] = useState(1);
      return {
        library: 'Movies',
        setLibrary: vi.fn(),
        pageSize: 60,
        notReadyCount,
        setNotReadyCount,
        updateItem,
      };
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.clearAllMocks();
  });

  it('removes an assigned item and updates the shared count before the follow-up refresh returns', async () => {
    let itemFetches = 0;
    let resolveSecondFetch;
    const secondFetch = new Promise((resolve) => {
      resolveSecondFetch = resolve;
    });

    global.fetch = vi.fn((url) => {
      if (!String(url).startsWith('/api/items?')) {
        throw new Error(`Unexpected request: ${url}`);
      }
      itemFetches += 1;
      if (itemFetches === 1) {
        return Promise.resolve(
          jsonResponse({
            page: 1,
            total_pages: 1,
            not_ready_count: 1,
            items: [
              {
                ratingKey: '22',
                title: 'Needs Assets',
                year: 2020,
                assetReady: false,
              },
            ],
          })
        );
      }
      return secondFetch;
    });

    renderNotReadyPage();

    expect(await screen.findByText('Needs Assets')).toBeInTheDocument();
    expect(screen.getByText('1 not-ready item')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Not Ready/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Use selected folder' }));

    await waitFor(() => {
      expect(screen.getByText('0 not-ready items')).toBeInTheDocument();
    });
    expect(screen.queryByText('Needs Assets')).not.toBeInTheDocument();
    expect(updateItem).toHaveBeenCalledWith('22', {
      assetReady: true,
      folderName: 'Needs Assets (2020)',
      folder: 'Needs Assets (2020)',
    });

    resolveSecondFetch(
      jsonResponse({
        page: 1,
        total_pages: 1,
        not_ready_count: 0,
        items: [],
      })
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(screen.getByText('No items found.')).toBeInTheDocument();
    });
  });
});
