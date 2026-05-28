import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  addImportResultToReceipt,
  createImportReceipt,
  importAllSeasons,
  importMovieAssets,
  importShowPosterPreferShowEndpoint,
} from '../importers.js';

function jsonResponse(body, { ok = true, status = 200, statusText = 'OK' } = {}) {
  return {
    ok,
    status,
    statusText,
    json: async () => body,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('import receipts', () => {
  it('counts imported, overwritten, and failed artwork results', () => {
    const receipt = createImportReceipt();

    addImportResultToReceipt(receipt, {
      ok: false,
      poster: { ok: true, replaced: true },
      background: { ok: false, replaced: false },
      seasons: [{ ok: true, replaced: false }],
      seasonBackgrounds: [{ ok: true, replaced: true }],
    });

    expect(receipt).toEqual({
      imported: 3,
      overwritten: 2,
      skipped: 0,
      failed: 1,
    });
  });

  it('does not count unselected artwork entries', () => {
    const receipt = createImportReceipt();

    addImportResultToReceipt(receipt, {
      ok: true,
      poster: { ok: true, replaced: false },
      background: null,
      seasons: [],
      seasonBackgrounds: [],
    });

    expect(receipt).toEqual({
      imported: 1,
      overwritten: 0,
      skipped: 0,
      failed: 0,
    });
  });
});

describe('selective import helpers', () => {
  it('passes movie include flags and omits unselected background results', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        ok: true,
        results: {
          poster: { ok: true, path: '/assets/Movie/poster.jpg', replaced: true },
          background: { ok: false, error: null },
        },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await importMovieAssets('Movies', '123', 'Movie', {
      poster: true,
      background: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/import/movie',
      expect.objectContaining({ method: 'POST', body: expect.any(FormData) })
    );
    const body = fetchMock.mock.calls[0][1].body;
    expect(body.get('includePoster')).toBe('true');
    expect(body.get('includeBackground')).toBe('false');
    expect(result.poster.ok).toBe(true);
    expect(result.background).toBeNull();
  });

  it('passes TV series and season include flags', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        ok: true,
        poster: { ok: false, error: null },
        background: { ok: true, path: '/assets/Show/background.jpg' },
        seasons: [{ ok: true, index: 1 }],
        seasonBackgrounds: [{ ok: true, index: 1 }],
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await importShowPosterPreferShowEndpoint('TV Series', '456', 'Show', {
      seriesPoster: false,
      seriesBackground: true,
      seasonPosters: false,
      seasonBackgrounds: true,
    });

    const body = fetchMock.mock.calls[0][1].body;
    expect(body.get('includePoster')).toBe('false');
    expect(body.get('includeBackground')).toBe('true');
    expect(body.get('includeSeasons')).toBe('false');
    expect(body.get('includeSeasonBackgrounds')).toBe('true');
    expect(result.poster).toBeNull();
    expect(result.background.ok).toBe(true);
    expect(result.seasons).toEqual([]);
    expect(result.seasonBackgrounds).toHaveLength(1);
  });

  it('imports only selected season asset kinds during fallback', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true, path: '/assets/Show/Season01_background.jpg' }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await importAllSeasons(
      'TV Series',
      'Show',
      [{ index: 1, plexPosterUrl: 'poster-url', plexBackgroundUrl: 'background-url' }],
      '456',
      { posters: false, backgrounds: true }
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = fetchMock.mock.calls[0][1].body;
    expect(body.get('kind')).toBe('background');
    expect(body.get('url')).toBe('background-url');
    expect(result.seasons).toEqual([]);
    expect(result.seasonBackgrounds[0].ok).toBe(true);
  });
});
