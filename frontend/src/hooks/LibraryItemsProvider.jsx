import { createContext, useContext } from 'react';
import { useLocation } from 'react-router-dom';
import { useLibraryItems } from './useLibraryItems.js';

const LibraryItemsContext = createContext(null);

function shouldLoadLibraryGrid(pathname) {
  const path = String(pathname || '').replace(/\/+$/, '') || '/';
  if (path === '/libraries') return true;
  const segments = path.split('/').filter(Boolean);
  return (
    (segments.length === 2 && segments[0] === 'libraries')
    || (segments.length === 3 && segments[0] === 'libraries' && segments[2] === 'collections')
  );
}

function libraryFromPathname(pathname) {
  const path = String(pathname || '').replace(/\/+$/, '') || '/';
  const segments = path.split('/').filter(Boolean);
  if (
    segments[0] !== 'libraries'
    || (segments.length !== 2 && !(segments.length === 3 && segments[2] === 'collections'))
  ) return undefined;
  try {
    return decodeURIComponent(segments[1]);
  } catch {
    return segments[1];
  }
}

export function LibraryItemsProvider({ children }) {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const initialLibrary = libraryFromPathname(location.pathname) || searchParams.get('lib') || undefined;
  const collectionsOnly = /\/collections\/?$/.test(location.pathname);
  const value = useLibraryItems({
    initialLibrary,
    enabled: shouldLoadLibraryGrid(location.pathname),
    collectionsOnly,
  });

  return <LibraryItemsContext.Provider value={value}>{children}</LibraryItemsContext.Provider>;
}

export function useLibraryItemsContext() {
  const ctx = useContext(LibraryItemsContext);
  if (!ctx) {
    throw new Error('useLibraryItemsContext must be used within a LibraryItemsProvider');
  }
  return ctx;
}
