import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ImportErrorsPage from '../ImportErrorsPage.jsx';
import { useLibraryItemsContext } from '../../hooks/LibraryItemsProvider.jsx';
import { loadImportErrorReport, saveImportErrorReport } from '../../utils/importErrors.js';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: vi.fn(),
}));

vi.mock('../../components/FolderFinderModal.jsx', () => ({
  default: ({ isOpen, onFolderAssigned }) =>
    isOpen ? (
      <button type="button" onClick={() => onFolderAssigned({ folderName: 'E.T. the Extra-Terrestrial (1982)' })}>
        Use selected folder
      </button>
    ) : null,
}));

function renderImportErrorsPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/import-errors']}>
      <Routes>
        <Route path="/libraries/:library/import-errors" element={<ImportErrorsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ImportErrorsPage', () => {
  let updateItem;
  let setNotReadyCount;

  beforeEach(() => {
    localStorage.clear();
    updateItem = vi.fn();
    setNotReadyCount = vi.fn();
    useLibraryItemsContext.mockReturnValue({
      library: 'Movies',
      setLibrary: vi.fn(),
      setNotReadyCount,
      updateItem,
    });
    saveImportErrorReport('Movies', [
      {
        library: 'Movies',
        title: 'E.T.',
        folder: 'E.T. the Extra-Terrestrial (1982)',
        asset: 'Item',
        message: 'Skipped (folder match needs manual confirmation)',
        ratingKey: '42',
        year: 1982,
      },
    ]);
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('shows import issues and resolves folder confirmation rows', async () => {
    renderImportErrorsPage();

    expect(screen.getByRole('heading', { name: 'Import Issues' })).toBeInTheDocument();
    expect(screen.getByText('E.T.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Folder' }));
    fireEvent.click(screen.getByRole('button', { name: 'Use selected folder' }));

    await waitFor(() => {
      expect(updateItem).toHaveBeenCalledWith('42', {
        assetReady: true,
        folderName: 'E.T. the Extra-Terrestrial (1982)',
        folder: 'E.T. the Extra-Terrestrial (1982)',
      });
    });

    expect(screen.getAllByText('Resolved').length).toBeGreaterThan(0);
    const saved = loadImportErrorReport('Movies');
    expect(saved.errors[0]).toMatchObject({
      resolved: true,
      resolvedFolder: 'E.T. the Extra-Terrestrial (1982)',
    });
  });
});
