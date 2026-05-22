import { describe, expect, it } from 'vitest';
import { addImportResultToReceipt, createImportReceipt } from '../importers.js';

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
});
