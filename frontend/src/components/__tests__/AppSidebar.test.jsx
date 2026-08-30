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
      {
        name: 'Kids Movies',
        type: 'movie',
        assetPath: '/assets/Kids Movies',
        collectionsPath: '/assets/Collections',
      },
      { name: 'Kids TV', type: 'show', assetPath: '' },
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

  it('preserves collection scope in the needs-attention link', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies/collections']}>
        <AppSidebar />
      </MemoryRouter>
    );

    const attentionLink = screen.getByRole('link', { name: 'Needs Attention 4 / 28' });
    expect(attentionLink).toHaveAttribute(
      'href',
      '/libraries/Kids%20Movies/not-ready?scope=collections'
    );
    expect(screen.getByRole('link', { name: 'Kids Movies Collections' })).toHaveClass('is-active');
  });

  it('keeps Collections selected on the scoped needs-attention page', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies/not-ready?scope=collections']}>
        <AppSidebar />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Kids Movies Collections' })).toHaveClass('is-active');
    expect(screen.getByRole('link', { name: 'Kids Movies' })).not.toHaveClass('is-active');
    expect(screen.getByRole('link', { name: 'Needs Attention 4 / 28' })).toHaveAttribute(
      'href',
      '/libraries/Kids%20Movies/not-ready?scope=collections'
    );
  });

  it('only lists mapped libraries', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies']}>
        <AppSidebar />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Kids Movies' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Kids TV' })).not.toBeInTheDocument();
  });

  it('links orphaned assets outside needs attention', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies']}>
        <AppSidebar />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Orphaned Assets' })).toHaveAttribute(
      'href',
      '/libraries/Kids%20Movies/orphaned-assets'
    );
    expect(screen.getByRole('link', { name: 'Duplicate Folders' })).toHaveAttribute(
      'href',
      '/libraries/Kids%20Movies/duplicate-folders'
    );
  });

  it('removes the generic library link and nests collections under mapped libraries', () => {
    render(
      <MemoryRouter initialEntries={['/libraries/Kids%20Movies']}>
        <AppSidebar />
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: 'Library' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Kids Movies Collections' })).toHaveAttribute(
      'href',
      '/libraries/Kids%20Movies/collections'
    );
    expect(
      screen.getByRole('link', { name: 'Kids Movies Collections' }).querySelector('.app-nav-branch')
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Kids TV Collections' })).not.toBeInTheDocument();
  });
});
