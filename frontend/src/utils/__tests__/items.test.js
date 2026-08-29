import { describe, expect, it } from 'vitest';

import { buildDetailPath } from '../items.js';

describe('buildDetailPath', () => {
  it('keeps collection details beneath their parent library', () => {
    expect(
      buildDetailPath(
        { ratingKey: 42, library: 'Movies', type: 'collection' },
        'Movies'
      )
    ).toBe('/libraries/Movies/collections/42');
  });

  it('preserves the source library for the legacy global collections view', () => {
    expect(
      buildDetailPath(
        { ratingKey: 42, library: 'Movies', type: 'collection' },
        'Collections'
      )
    ).toBe('/libraries/Collections/collections/42?source=Movies');
  });
});
