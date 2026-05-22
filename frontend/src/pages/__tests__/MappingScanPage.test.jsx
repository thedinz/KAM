import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MappingScanPage from '../MappingScanPage.jsx';
import { useLibraryItemsContext } from '../../hooks/LibraryItemsProvider.jsx';
import { assignMatchedFolders, runLibraryMappingScan } from '../../utils/mappingScan.js';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: vi.fn(),
}));

vi.mock('../../utils/mappingScan.js', () => ({
  assignMatchedFolders: vi.fn(),
  runLibraryMappingScan: vi.fn(),
}));

vi.mock('../../components/FolderFinderModal.jsx', () => ({
  default: ({ isOpen, onFolderAssigned }) =>
    isOpen ? (
      <button type="button" onClick={() => onFolderAssigned({ folderName: 'Manual Movie (2024)' })}>
        Use selected folder
      </button>
    ) : null,
}));

const scanEntries = [
  {
    ratingKey: '1',
    title: 'Ready Movie',
    matched: true,
    assetReady: true,
    matchedFolder: 'Ready Movie (2020)',
  },
  {
    ratingKey: '2',
    title: 'Missing Movie',
    matched: false,
    assetReady: false,
    matchedFolder: '',
  },
  {
    ratingKey: '3',
    title: 'Assignment Failed',
    matched: true,
    assetReady: false,
    matchedFolder: 'Assignment Failed (2024)',
    assignmentError: 'Folder assignment failed',
  },
];

function renderMappingScanPage() {
  return render(
    <MemoryRouter initialEntries={['/libraries/Movies/mapping']}>
      <Routes>
        <Route path="/libraries/:library/mapping" element={<MappingScanPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('MappingScanPage result filters', () => {
  let updateItem;

  beforeEach(() => {
    localStorage.clear();
    updateItem = vi.fn();
    useLibraryItemsContext.mockReturnValue({
      library: 'Movies',
      setLibrary: vi.fn(),
      reload: vi.fn().mockResolvedValue(undefined),
      refreshNotReadyCount: vi.fn().mockResolvedValue(undefined),
      fetchAllForLibrary: vi.fn(),
      updateItem,
    });
    runLibraryMappingScan.mockResolvedValue({
      library: 'Movies',
      scannedAt: '2026-05-22T12:00:00.000Z',
      entries: scanEntries,
    });
    assignMatchedFolders.mockImplementation(async ({ entries }) => ({
      entries,
      assignedCount: 0,
      errors: [],
    }));
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('filters scanned rows between mapped and not-ready items', async () => {
    renderMappingScanPage();

    expect(await screen.findByText('Ready Movie')).toBeInTheDocument();
    expect(screen.getByText('Missing Movie')).toBeInTheDocument();
    expect(screen.getByText('Assignment Failed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Not Ready (2)' }));

    expect(screen.queryByText('Ready Movie')).not.toBeInTheDocument();
    expect(screen.getByText('Missing Movie')).toBeInTheDocument();
    expect(screen.getByText('Assignment Failed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Mapped (1)' }));

    expect(screen.getByText('Ready Movie')).toBeInTheDocument();
    expect(screen.queryByText('Missing Movie')).not.toBeInTheDocument();
    expect(screen.queryByText('Assignment Failed')).not.toBeInTheDocument();
  });

  it('removes a manually assigned row from the not-ready filter', async () => {
    renderMappingScanPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Not Ready (2)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Not matched (click to set folder)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Use selected folder' }));

    await waitFor(() => {
      expect(screen.queryByText('Missing Movie')).not.toBeInTheDocument();
    });

    expect(updateItem).toHaveBeenCalledWith('2', {
      assetReady: true,
      folderName: 'Manual Movie (2024)',
      folder: 'Manual Movie (2024)',
    });
    expect(screen.getByRole('button', { name: 'Not Ready (1)' })).toBeInTheDocument();
    expect(screen.getByText('Assignment Failed')).toBeInTheDocument();
  });
});
