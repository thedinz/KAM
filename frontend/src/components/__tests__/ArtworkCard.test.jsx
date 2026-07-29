import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArtworkCard from '../ArtworkCard.jsx';


describe('ArtworkCard Plex action', () => {
  it('sends an existing saved asset to Plex', async () => {
    const onSendToPlex = vi.fn().mockResolvedValue({ ok: true });

    render(
      <ArtworkCard
        label="Poster"
        exists
        folderExists
        imageUrl="/fileproxy?path=poster.jpg"
        onSendToPlex={onSendToPlex}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Send Poster to Plex' }));

    await waitFor(() => {
      expect(onSendToPlex).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('Sent to Plex.')).toBeInTheDocument();
  });

  it('disables the Plex action when the saved asset is missing', () => {
    render(
      <ArtworkCard
        label="Poster"
        exists={false}
        folderExists
        onSendToPlex={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Send Poster to Plex' })).toBeDisabled();
  });
});
