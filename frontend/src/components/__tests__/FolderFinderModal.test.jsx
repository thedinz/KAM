import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import FolderFinderModal from '../FolderFinderModal.jsx';

describe('FolderFinderModal - settings mode', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          root: '/assets',
          parent: '',
          parentAbsolute: '/assets',
          items: [
            { name: 'Assets', path: 'Assets', absolutePath: '/assets/Assets', isDir: true },
            {
              name: 'Collections',
              path: 'Collections',
              absolutePath: '/assets/Collections',
              isDir: true,
            },
          ],
        }),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('allows selecting an asset folder and confirms with payload', async () => {
    const onSettingsConfirm = vi.fn();

    render(
      <FolderFinderModal
        isOpen
        context="settings"
        library="Movies"
        settingsLibraries={['Movies', 'TV Shows']}
        defaultTarget="asset"
        settingsIntent="asset"
        onClose={vi.fn()}
        onSettingsConfirm={onSettingsConfirm}
      />
    );

    const option = await screen.findByRole('button', { name: 'Assets' });
    fireEvent.click(option);

    const confirmButton = screen.getByRole('button', { name: /Apply selection/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(onSettingsConfirm).toHaveBeenCalledWith(
        { assetPath: '/assets/Assets' },
        expect.objectContaining({ assetSelection: expect.any(Object) })
      );
    });
  });

  it('allows confirming using the currently open folder when nothing is selected', async () => {
    const onSettingsConfirm = vi.fn();

    const payloads = {
      '': {
        root: '/assets',
        parent: '',
        parentAbsolute: '/assets',
        items: [
          { name: 'Kids TV', path: 'Kids TV', absolutePath: '/assets/Kids TV', isDir: true },
        ],
      },
      'Kids TV': {
        root: '/assets',
        parent: 'Kids TV',
        parentAbsolute: '/assets/Kids TV',
        items: [],
      },
    };

    global.fetch = vi.fn((url) => {
      const parsed = new URL(url, 'http://localhost');
      const parent = parsed.searchParams.get('parent') || '';
      const payload = payloads[parent];
      if (!payload) {
        throw new Error(`Unexpected parent ${parent}`);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(payload),
      });
    });

    render(
      <FolderFinderModal
        isOpen
        context="settings"
        library="Kids"
        settingsLibraries={['Kids']}
        defaultTarget="asset"
        settingsIntent="asset"
        onClose={vi.fn()}
        onSettingsConfirm={onSettingsConfirm}
      />
    );

    const openButton = await screen.findByRole('button', { name: 'Open' });
    fireEvent.click(openButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('parent=Kids%20TV')
      );
    });

    const confirmButton = await screen.findByRole('button', { name: /Apply selection/i });

    await waitFor(() => {
      expect(confirmButton).not.toBeDisabled();
    });

    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(onSettingsConfirm).toHaveBeenCalledWith(
        { assetPath: '/assets/Kids TV' },
        expect.objectContaining({ assetSelection: null, collectionsSelection: null })
      );
    });
  });

  it('returns both asset and collections selections when provided', async () => {
    const onSettingsConfirm = vi.fn();

    render(
      <FolderFinderModal
        isOpen
        context="settings"
        library="Movies"
        settingsLibraries={['Movies']}
        defaultTarget="asset"
        settingsIntent="asset"
        onClose={vi.fn()}
        onSettingsConfirm={onSettingsConfirm}
      />
    );

    const assetOption = await screen.findByRole('button', { name: 'Assets' });
    fireEvent.click(assetOption);

    const collectionsToggle = screen.getByRole('button', { name: /Collections folder/i });
    fireEvent.click(collectionsToggle);

    const results = await screen.findByRole('listbox');
    const collectionsOption = within(results).getByRole('button', { name: 'Collections' });
    fireEvent.click(collectionsOption);

    const confirmButton = screen.getByRole('button', { name: /Apply selection/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(onSettingsConfirm).toHaveBeenCalledWith(
        { assetPath: '/assets/Assets', collectionsPath: '/assets/Collections' },
        expect.objectContaining({
          assetSelection: expect.any(Object),
          collectionsSelection: expect.any(Object),
        })
      );
    });
  });

  it('navigates between mapping and assets root in settings mode', async () => {
    const makeResponse = (payload) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(payload),
      });

    const payloads = {
      '': {
        root: '/assets',
        parent: '',
        parentAbsolute: '/assets',
        items: [
          { name: 'Movies', path: 'Movies', absolutePath: '/assets/Movies', isDir: true },
          {
            name: 'LooseAssets',
            path: 'LooseAssets',
            absolutePath: '/assets/LooseAssets',
            isDir: true,
          },
        ],
      },
      '/assets/Movies/Featured': {
        root: '/assets',
        parent: 'Movies/Featured',
        parentAbsolute: '/assets/Movies/Featured',
        items: [
          {
            name: 'Posters',
            path: 'Movies/Featured/Posters',
            absolutePath: '/assets/Movies/Featured/Posters',
            isDir: true,
          },
        ],
      },
      'Movies/Featured': {
        root: '/assets',
        parent: 'Movies/Featured',
        parentAbsolute: '/assets/Movies/Featured',
        items: [
          {
            name: 'Posters',
            path: 'Movies/Featured/Posters',
            absolutePath: '/assets/Movies/Featured/Posters',
            isDir: true,
          },
        ],
      },
      Movies: {
        root: '/assets',
        parent: 'Movies',
        parentAbsolute: '/assets/Movies',
        items: [
          {
            name: 'Featured',
            path: 'Movies/Featured',
            absolutePath: '/assets/Movies/Featured',
            isDir: true,
          },
        ],
      },
    };

    global.fetch = vi.fn((url) => {
      const parsed = new URL(url, 'http://localhost');
      expect(parsed.searchParams.get('settings')).toBe('true');
      const key = parsed.searchParams.get('parent') || '';
      const payload = payloads[key];
      if (!payload) {
        throw new Error(`Unexpected parent ${key}`);
      }
      return makeResponse(payload);
    });

    render(
      <FolderFinderModal
        isOpen
        context="settings"
        library="Movies"
        settingsLibraries={['Movies']}
        defaultTarget="asset"
        settingsIntent="asset"
        onClose={vi.fn()}
        onSettingsConfirm={vi.fn()}
        initialAssetPath="/assets/Movies/Featured"
      />
    );

    await screen.findByRole('button', { name: 'Posters' });

    const breadcrumbNav = screen.getByLabelText('Folder breadcrumbs');
    const moviesCrumb = within(breadcrumbNav).getByRole('button', { name: 'Movies' });
    fireEvent.click(moviesCrumb);

    await screen.findByRole('button', { name: 'Featured' });

    const featuredFolder = screen.getByRole('button', { name: 'Featured' });
    fireEvent.click(featuredFolder);

    await screen.findByRole('button', { name: 'Posters' });

    const rootCrumb = within(screen.getByLabelText('Folder breadcrumbs')).getByRole('button', {
      name: 'Root',
    });
    fireEvent.click(rootCrumb);

    await screen.findByRole('button', { name: 'LooseAssets' });

    expect(global.fetch).toHaveBeenCalled();
  });
});
