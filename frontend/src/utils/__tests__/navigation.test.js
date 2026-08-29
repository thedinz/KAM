import { describe, expect, it } from 'vitest';

import { buildLibraryBackLink } from '../navigation.js';

describe('buildLibraryBackLink', () => {
  it('builds the canonical route without a duplicate library query parameter', () => {
    expect(buildLibraryBackLink('Kids Movies')).toBe('/libraries/Kids%20Movies');
  });
});
