import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LibraryToolbar from '../LibraryToolbar.jsx';

function renderToolbar(overrides = {}) {
  const props = {
    libraries: ['Movies', 'TV Shows'],
    selectedLibrary: 'Movies',
    onLibraryChange: vi.fn(),
    searchValue: '',
    onSearchChange: vi.fn(),
    sortValue: 'title',
    onSortChange: vi.fn(),
    onImportAll: vi.fn(),
    importDisabled: false,
    importTitle: 'Import all assets',
    page: 1,
    totalPages: 3,
    onFirst: vi.fn(),
    onPrev: vi.fn(),
    onNext: vi.fn(),
    onLast: vi.fn(),
    countLabel: '120 items',
    ...overrides,
  };

  render(<LibraryToolbar {...props} />);
  return props;
}

describe('LibraryToolbar', () => {
  it('notifies when the sort mode changes', () => {
    const props = renderToolbar();

    fireEvent.change(screen.getByLabelText('Sort library items'), {
      target: { value: 'newest' },
    });

    expect(props.onSortChange).toHaveBeenCalledWith('newest');
  });

  it('uses alphabetical sorting by default', () => {
    renderToolbar();

    expect(screen.getByLabelText('Sort library items')).toHaveValue('title');
  });
});
