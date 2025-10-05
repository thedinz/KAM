import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
});
