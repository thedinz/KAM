import { afterEach, describe, expect, it, vi } from 'vitest';
import { assignMatchedFolders, isCertainItemFolderMatch, runLibraryMappingScan } from '../mappingScan.js';

function jsonResponse(payload, { ok = true, status = 200, statusText = 'OK' } = {}) {
  return {
    ok,
    status,
    statusText,
    json: () => Promise.resolve(payload),
  };
}

describe('runLibraryMappingScan', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('only uses the selected library folders when scanning movies', async () => {
    global.fetch = vi.fn((url) => {
      const parsed = new URL(url, 'http://localhost');
      expect(parsed.pathname).toBe('/api/asset-folders');
      expect(parsed.searchParams.get('library')).toBe('Movies');
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '101',
          title: 'Alien',
          year: 1979,
          type: 'movie',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'Movies', fetchAllForLibrary });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(fetchAllForLibrary).toHaveBeenCalledWith('Movies', '', { notReadyOnly: false });
    expect(result.entries[0]).toMatchObject({
      matched: false,
      matchedFolder: '',
      assetReady: false,
    });
  });

  it('uses the lightweight mapping source when no legacy item fetcher is provided', async () => {
    global.fetch = vi.fn((url) => {
      const parsed = new URL(url, 'http://localhost');
      if (parsed.pathname === '/api/asset-folders') {
        return Promise.resolve(jsonResponse({ items: [{ name: 'Alien (1979)', isDir: true }] }));
      }
      expect(parsed.pathname).toBe('/api/items/mapping-source');
      expect(parsed.searchParams.get('library')).toBe('Movies');
      return Promise.resolve(
        jsonResponse({
          items: [
            {
              ratingKey: '101',
              title: 'Alien',
              year: 1979,
              type: 'movie',
              assetReady: false,
            },
          ],
        })
      );
    });

    const result = await runLibraryMappingScan({ library: 'Movies' });

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(result.entries[0]).toMatchObject({
      matched: true,
      matchedFolder: 'Alien (1979)',
      assetReady: false,
    });
  });

  it('requires movie year matches when Plex has a year', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          items: [
            { name: 'Dune (1984)', isDir: true },
            { name: 'Dune (2021)', isDir: true },
          ],
        })
      )
    );
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '2021',
          title: 'Dune',
          folderName: 'Dune',
          year: 2021,
          type: 'movie',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'Movies', fetchAllForLibrary });

    expect(result.entries[0]).toMatchObject({
      matched: true,
      matchedFolder: 'Dune (2021)',
      matchedFrom: 'titleYear',
    });
  });

  it('does not match movies to the same title from a different year', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(jsonResponse({ items: [{ name: 'Dune (1984)', isDir: true }] }))
    );
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '2021',
          title: 'Dune',
          year: 2021,
          type: 'movie',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'Movies', fetchAllForLibrary });

    expect(result.entries[0]).toMatchObject({
      matched: false,
      matchedFolder: '',
    });
  });

  it('does not assign a year-scoped movie to a yearless folder', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(jsonResponse({ items: [{ name: 'Dune', isDir: true }] }))
    );
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '2021',
          title: 'Dune',
          year: 2021,
          type: 'movie',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'Movies', fetchAllForLibrary });

    expect(result.entries[0]).toMatchObject({
      matched: false,
      matchedFolder: '',
    });
  });

  it('does not treat Roman numeral sequel names as edition suffixes', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(jsonResponse({ items: [{ name: 'A Quiet Place', isDir: true }] }))
    );
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: 'quiet-place-two',
          title: 'A Quiet Place Part II',
          type: 'movie',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'Movies', fetchAllForLibrary });

    expect(result.entries[0]).toMatchObject({
      matched: false,
      matchedFolder: '',
    });
  });

  it('uses the same selected-library-only matching for TV series', async () => {
    global.fetch = vi.fn((url) => {
      const parsed = new URL(url, 'http://localhost');
      expect(parsed.pathname).toBe('/api/asset-folders');
      expect(parsed.searchParams.get('library')).toBe('TV Shows');
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '301',
          title: 'The Expanse',
          year: 2015,
          type: 'show',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'TV Shows', fetchAllForLibrary });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(fetchAllForLibrary).toHaveBeenCalledWith('TV Shows', '', { notReadyOnly: false });
    expect(result.entries[0]).toMatchObject({
      matched: false,
      matchedFolder: '',
      assetReady: false,
    });
  });

  it('allows TV series to match folders without the Plex year', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(jsonResponse({ items: [{ name: 'Breaking Bad', isDir: true }] }))
    );
    const fetchAllForLibrary = vi.fn().mockResolvedValue({
      items: [
        {
          ratingKey: '401',
          title: 'Breaking Bad',
          year: 2008,
          type: 'show',
          assetReady: false,
        },
      ],
    });

    const result = await runLibraryMappingScan({ library: 'TV Shows', fetchAllForLibrary });

    expect(result.entries[0]).toMatchObject({
      matched: true,
      matchedFolder: 'Breaking Bad',
    });
  });
});

describe('isCertainItemFolderMatch', () => {
  it('rejects a current folder from the original movie for a Roman numeral sequel', () => {
    expect(
      isCertainItemFolderMatch(
        {
          title: 'A Quiet Place Part II',
          type: 'movie',
        },
        'A Quiet Place'
      )
    ).toBe(false);
  });

  it('still accepts a known edition folder for bulk import', () => {
    expect(
      isCertainItemFolderMatch(
        {
          title: 'Jurassic World Fallen Kingdom',
          year: 2018,
          type: 'movie',
        },
        'Jurassic World Fallen Kingdom (Extended Edition) (2018)'
      )
    ).toBe(true);
  });
});

describe('assignMatchedFolders', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('assigns matched folders for not-ready items only', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          items: [{ ratingKey: '2', folderName: 'Alien (1979)', assetReady: true }],
          errors: [],
        })
      )
    );

    const result = await assignMatchedFolders({
      library: 'Movies',
      entries: [
        {
          ratingKey: '1',
          title: 'Ready Movie',
          matched: true,
          matchedFolder: 'Ready Movie (2020)',
          assetReady: true,
        },
        {
          ratingKey: '2',
          title: 'Alien',
          matched: true,
          matchedFolder: 'Alien (1979)',
          assetReady: false,
        },
        {
          ratingKey: '3',
          title: 'Missing Movie',
          matched: false,
          matchedFolder: '',
          assetReady: false,
        },
      ],
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/items/assign-folders',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          library: 'Movies',
          assignments: [
            {
              ratingKey: '2',
              folderName: 'Alien (1979)',
            },
          ],
        }),
      })
    );
    expect(result.assignedCount).toBe(1);
    expect(result.errors).toEqual([]);
    expect(result.entries[1]).toMatchObject({
      assigned: true,
      assetReady: true,
      currentFolder: 'Alien (1979)',
    });
    expect(result.entries[0].assigned).toBeUndefined();
    expect(result.entries[2].assigned).toBeUndefined();
  });

  it('assigns matched TV series folders to the selected TV library', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          items: [{ ratingKey: '401', folderName: 'Breaking Bad', assetReady: true }],
          errors: [],
        })
      )
    );

    const result = await assignMatchedFolders({
      library: 'TV Shows',
      entries: [
        {
          ratingKey: '401',
          title: 'Breaking Bad',
          matched: true,
          matchedFolder: 'Breaking Bad',
          assetReady: false,
          type: 'show',
        },
      ],
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/items/assign-folders',
      expect.objectContaining({
        body: JSON.stringify({
          library: 'TV Shows',
          assignments: [
            {
              ratingKey: '401',
              folderName: 'Breaking Bad',
            },
          ],
        }),
      })
    );
    expect(result.assignedCount).toBe(1);
    expect(result.entries[0]).toMatchObject({
      assigned: true,
      assetReady: true,
      currentFolder: 'Breaking Bad',
    });
  });
});
