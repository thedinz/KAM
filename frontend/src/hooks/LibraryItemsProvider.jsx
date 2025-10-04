import { createContext, useContext } from 'react';
import { useLocation } from 'react-router-dom';
import { useLibraryItems } from './useLibraryItems.js';

const LibraryItemsContext = createContext(null);

export function LibraryItemsProvider({ children }) {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const initialLibrary = searchParams.get('lib') || undefined;
  const value = useLibraryItems({ initialLibrary });

  return <LibraryItemsContext.Provider value={value}>{children}</LibraryItemsContext.Provider>;
}

export function useLibraryItemsContext() {
  const ctx = useContext(LibraryItemsContext);
  if (!ctx) {
    throw new Error('useLibraryItemsContext must be used within a LibraryItemsProvider');
  }
  return ctx;
}
