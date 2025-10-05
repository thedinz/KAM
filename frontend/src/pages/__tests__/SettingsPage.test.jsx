import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SettingsPage from '../SettingsPage.jsx';
import { useTheme } from '../../theme/ThemeProvider.jsx';

vi.mock('../../theme/ThemeProvider.jsx', () => ({
  useTheme: vi.fn(),
}));

describe('SettingsPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('renders plex libraries and enables bulk actions after selection', () => {
    const mockSave = vi.fn().mockResolvedValue({});
    const mockRefresh = vi.fn().mockResolvedValue([]);
    useTheme.mockReturnValue({
      theme: 'dark',
      savedTheme: 'dark',
      plexUrl: 'http://plex.local',
      plexToken: 'token',
      savedSettings: { plexUrl: 'http://plex.local', plexToken: 'token' },
      libraryMappings: [
        { library: 'Movies', assetPath: '/assets/Movies', collectionsPath: '' },
      ],
      savedLibraryMappings: [
        { library: 'Movies', assetPath: '/assets/Movies', collectionsPath: '' },
      ],
      libraries: [
        { name: 'Movies', type: 'movie', key: '1', assetPath: '/assets/Movies', collectionsPath: '' },
        { name: 'TV Shows', type: 'show', key: '2', assetPath: '', collectionsPath: '' },
      ],
      librariesLoading: false,
      librariesError: null,
      loading: false,
      saving: false,
      error: null,
      libraryMappingsDirty: false,
      hasUnsavedChanges: false,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: mockSave,
      revertSettings: vi.fn(),
      refreshLibraries: mockRefresh,
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: /Plex Libraries/i })).toBeInTheDocument();
    expect(screen.getByText('Movies')).toBeInTheDocument();

    const bulkButton = screen.getByRole('button', { name: /Set asset folder for selected/i });
    expect(bulkButton).toBeDisabled();

    const moviesCheckbox = screen.getByLabelText('Select Movies');
    fireEvent.click(moviesCheckbox);
    expect(moviesCheckbox).toBeChecked();
    expect(bulkButton).not.toBeDisabled();

    const revertButton = screen.getByRole('button', { name: /Revert/i });
    expect(revertButton).toBeDisabled();
  });

  it('surfaces library errors in the status message', () => {
    useTheme.mockReturnValue({
      theme: 'dark',
      savedTheme: 'dark',
      plexUrl: '',
      plexToken: '',
      savedSettings: { plexUrl: '', plexToken: '' },
      libraryMappings: [],
      savedLibraryMappings: [],
      libraries: [],
      librariesLoading: false,
      librariesError: 'Unable to load libraries',
      loading: false,
      saving: false,
      error: null,
      libraryMappingsDirty: false,
      hasUnsavedChanges: false,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: vi.fn(),
      revertSettings: vi.fn(),
      refreshLibraries: vi.fn(),
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load libraries');
  });

  it('invokes refreshLibraries and reports success when refreshing', async () => {
    const mockRefresh = vi.fn().mockResolvedValue([]);
    useTheme.mockReturnValue({
      theme: 'dark',
      savedTheme: 'dark',
      plexUrl: '',
      plexToken: '',
      savedSettings: { plexUrl: '', plexToken: '' },
      libraryMappings: [],
      savedLibraryMappings: [],
      libraries: [],
      librariesLoading: false,
      librariesError: null,
      loading: false,
      saving: false,
      error: null,
      libraryMappingsDirty: false,
      hasUnsavedChanges: false,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: vi.fn().mockResolvedValue({}),
      revertSettings: vi.fn(),
      refreshLibraries: mockRefresh,
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    const refreshButton = screen.getByRole('button', { name: /Refresh libraries/i });
    fireEvent.click(refreshButton);

    expect(mockRefresh).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent('Plex libraries refreshed.');
  });

  it('shows loading status when settings are loading', async () => {
    useTheme.mockReturnValue({
      theme: 'dark',
      savedTheme: 'dark',
      plexUrl: '',
      plexToken: '',
      savedSettings: { plexUrl: '', plexToken: '' },
      libraryMappings: [],
      savedLibraryMappings: [],
      libraries: [],
      librariesLoading: false,
      librariesError: null,
      loading: true,
      saving: false,
      error: null,
      libraryMappingsDirty: false,
      hasUnsavedChanges: false,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: vi.fn(),
      revertSettings: vi.fn(),
      refreshLibraries: vi.fn(),
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('Loading settings…');
  });

  it('shows saving status while persisting changes', async () => {
    useTheme.mockReturnValue({
      theme: 'dark',
      savedTheme: 'dark',
      plexUrl: '',
      plexToken: '',
      savedSettings: { plexUrl: '', plexToken: '' },
      libraryMappings: [],
      savedLibraryMappings: [],
      libraries: [],
      librariesLoading: false,
      librariesError: null,
      loading: false,
      saving: true,
      error: null,
      libraryMappingsDirty: false,
      hasUnsavedChanges: true,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: vi.fn(),
      revertSettings: vi.fn(),
      refreshLibraries: vi.fn(),
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('Saving settings…');
  });

  it('displays success status after saving changes', async () => {
    const mockSave = vi.fn().mockResolvedValue({});
    useTheme.mockReturnValue({
      theme: 'light',
      savedTheme: 'dark',
      plexUrl: '',
      plexToken: '',
      savedSettings: { plexUrl: '', plexToken: '' },
      libraryMappings: [],
      savedLibraryMappings: [],
      libraries: [],
      librariesLoading: false,
      librariesError: null,
      loading: false,
      saving: false,
      error: null,
      libraryMappingsDirty: true,
      hasUnsavedChanges: true,
      applyTheme: vi.fn(),
      updateSettings: vi.fn(),
      saveSettings: mockSave,
      revertSettings: vi.fn(),
      refreshLibraries: vi.fn(),
      setLibraryMapping: vi.fn(),
      setLibraryMappings: vi.fn(),
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    const saveButton = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(saveButton);

    expect(mockSave).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent('Settings saved successfully.');
  });
});
