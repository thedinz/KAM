import { describe, expect, it } from 'vitest';

import { uploadStatusMessage } from '../plexArtwork.js';


describe('uploadStatusMessage', () => {
  it('describes automatic Plex success', () => {
    expect(uploadStatusMessage({ plex: { attempted: true, ok: true } })).toBe(
      'Upload complete and sent to Plex.'
    );
  });

  it('keeps the saved upload successful when Plex fails', () => {
    expect(
      uploadStatusMessage({
        plex: { attempted: true, ok: false, error: 'Plex is unavailable.' },
      })
    ).toBe('Upload complete. Plex update failed: Plex is unavailable.');
  });
});
