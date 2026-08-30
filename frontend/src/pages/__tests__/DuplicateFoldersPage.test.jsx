import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DuplicateFoldersPage from '../DuplicateFoldersPage.jsx';

const setLibrary = vi.fn();
const reload = vi.fn();

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: () => ({ library: 'Movies', setLibrary, reload }),
}));

const duplicatePayload = {
  library: 'Movies',
  root: '/assets/Movies',
  totalCount: 1,
  groups: [
    {
      ratingKey: '123',
      title: 'Step Brothers',
      year: 2008,
      activeFolderName: 'Step Brothers (2008)',
      folders: [
        {
          folderName: 'Step Brothers',
          assetCount: 1,
          sizeBytes: 1024,
          posterUrl: null,
          isActive: false,
        },
        {
          folderName: 'Step Brothers (2008)',
          assetCount: 2,
          sizeBytes: 2048,
          posterUrl: '/fileproxy?path=poster',
          isActive: true,
        },
        {
          folderName: 'Step Brothers Directors Cut (2008)',
          assetCount: 3,
          sizeBytes: 3072,
          posterUrl: null,
          isActive: false,
        },
      ],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/duplicate-folders']}>
      <Routes>
        <Route path="/libraries/:library/duplicate-folders" element={<DuplicateFoldersPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('DuplicateFoldersPage', () => {
  beforeEach(() => {
    setLibrary.mockReset();
    reload.mockReset();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    global.fetch = vi.fn(async (url, options = {}) => {
      if (url === '/api/duplicate-folders/resolve' && options.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            library: 'Movies',
            ratingKey: '123',
            keptFolderName: 'Step Brothers Directors Cut (2008)',
            deleted: ['Step Brothers', 'Step Brothers (2008)'],
            deletedCount: 2,
            folderAssignmentChanged: true,
            errors: [],
          }),
        };
      }
      if (url === '/api/duplicate-folders/resolve-all' && options.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            library: 'Movies',
            processedCount: 1,
            deletedCount: 2,
            folderAssignmentsChanged: 1,
            results: [{
              ratingKey: '123',
              keptFolderName: 'Step Brothers Directors Cut (2008)',
              folderAssignmentChanged: true,
              deleted: ['Step Brothers', 'Step Brothers (2008)'],
              deletedCount: 2,
              errors: [],
            }],
            failures: [],
          }),
        };
      }
      const getCalls = global.fetch.mock.calls.filter(([requestUrl]) => String(requestUrl).startsWith('/api/duplicate-folders?'));
      return {
        ok: true,
        json: async () => (getCalls.length > 1 ? { ...duplicatePayload, totalCount: 0, groups: [] } : duplicatePayload),
      };
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults to the active folder and lets the user choose a different folder to keep', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Step Brothers (2008)' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Step Brothers \(2008\).*2 files/i })).toBeChecked();
    fireEvent.click(screen.getByRole('radio', { name: /Step Brothers Directors Cut.*3 files/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Keep selected folder' }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining(
      'Keep “Step Brothers Directors Cut (2008)”'
    ));
    await waitFor(() => {
      const resolveCall = global.fetch.mock.calls.find(([url]) => url === '/api/duplicate-folders/resolve');
      expect(JSON.parse(resolveCall[1].body)).toEqual({
        library: 'Movies',
        ratingKey: '123',
        keepFolderName: 'Step Brothers Directors Cut (2008)',
      });
    });
    expect(await screen.findByText('No duplicate asset folders')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Kept Step Brothers Directors Cut (2008) and deleted 2 duplicate folders.'
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'KAM now uses Step Brothers Directors Cut (2008).'
    );
    expect(reload).toHaveBeenCalled();
  });

  it('stages choices and processes the full list in one action', async () => {
    renderPage();

    expect(await screen.findByText('1 of 1 assets ready')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: /Step Brothers Directors Cut.*3 files/i }));

    expect(screen.getByText('KAM will switch to this folder')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Process all 1 asset' }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining(
      'KAM will switch to any newly selected folder before deleting the old one.'
    ));
    await waitFor(() => {
      const resolveCall = global.fetch.mock.calls.find(
        ([url]) => url === '/api/duplicate-folders/resolve-all'
      );
      expect(JSON.parse(resolveCall[1].body)).toEqual({
        library: 'Movies',
        selections: [{
          ratingKey: '123',
          keepFolderName: 'Step Brothers Directors Cut (2008)',
        }],
      });
    });
    expect(await screen.findByText('No duplicate asset folders')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Processed 1 asset and deleted 2 duplicate folders.'
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'Switched KAM to 1 newly selected folder.'
    );
    expect(reload).toHaveBeenCalled();
  });
});
