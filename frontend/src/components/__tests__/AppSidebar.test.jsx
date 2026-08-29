import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import AppSidebar from '../AppSidebar.jsx';

vi.mock('../../hooks/LibraryItemsProvider.jsx', () => ({
  useLibraryItemsContext: () => ({
    library: 'Kids Movies',
    notReadyCount: 4,
    totalCount: 28,
  }),
}));

vi.mock('../../theme/ThemeProvider.jsx', () => ({
  useTheme: () => ({
    libraries: [
      { name: 'Kids Movies', type: 'movie' },
      { name: 'Kids TV', type: 'show' },
    ],
  }),
}));

describe('AppSidebar', () => {
  it('shows needs-attention progress for the selected library', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies']}>
        <AppSidebar />
      </MemoryRouter>
    );

    const attentionLink = screen.getByRole('link', { name: 'Needs Attention 4 / 28' });
    expect(attentionLink).toHaveAttribute('href', '/libraries/Kids%20Movies/not-ready');
    expect(attentionLink).toHaveTextContent('Needs Attention');
    expect(attentionLink).toHaveTextContent('4 / 28');
  });
});
