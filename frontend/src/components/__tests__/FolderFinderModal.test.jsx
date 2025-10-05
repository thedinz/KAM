import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import FolderFinderModal from '../FolderFinderModal.jsx';

describe('FolderFinderModal - settings mode', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          parent: '',
          items: [
            { name: 'Assets', path: 'Assets', isDir: true },
            { name: 'Collections', path: 'Collections', isDir: true },
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
        { assetPath: 'Assets' },
        expect.objectContaining({ assetSelection: expect.any(Object) })
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
        { assetPath: 'Assets', collectionsPath: 'Collections' },
        expect.objectContaining({
          assetSelection: expect.any(Object),
          collectionsSelection: expect.any(Object),
        })
      );
    });
  });
});
