import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from './AuthProvider.jsx';
import { useTheme } from '../theme/ThemeProvider.jsx';

import { responseErrorMessage, safeJson } from '../utils/api.js';

const PAGE_SIZE = 60;
const COLLECTIONS_LIBRARY = 'Collections';

function isCollectionsLibrary(value) {
  return String(value || '').trim().toLowerCase() === COLLECTIONS_LIBRARY.toLowerCase();
}

function prioritizeLibraries(values) {
  const seen = new Set();
  const libraries = [];
  (Array.isArray(values) ? values : []).forEach((value) => {
    const name = String(value || '').trim();
    if (!name || seen.has(name)) return;
    seen.add(name);
    libraries.push(name);
  });
  return libraries.sort((a, b) => {
    const aCollections = isCollectionsLibrary(a);
    const bCollections = isCollectionsLibrary(b);
    if (aCollections !== bCollections) {
      return aCollections ? 1 : -1;
    }
    return a.localeCompare(b, undefined, { sensitivity: 'base' });
  });
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await safeJson(response);
  if (!response.ok) {
    const message = responseErrorMessage(response, data);
    throw new Error(message);
  }
  return data;
}

export function useLibraryItems({ initialLibrary, enabled = true } = {}) {
  const { enabled: authEnabled, authenticated, loading: authLoading } = useAuth();
  const {
    savedLibraryMappings = [],
    exclusions = [],
    isItemExcluded,
  } = useTheme();
  const canFetch = enabled && !authLoading && (!authEnabled || authenticated);
  const savedLibraryMappingsKey = useMemo(() => {
    if (!Array.isArray(savedLibraryMappings)) return '';
    return savedLibraryMappings
      .map((entry) => {
        if (!entry || typeof entry !== 'object') return '';
        const name = entry.library || '';
        const asset = entry.assetPath || '';
        const collections = entry.collectionsPath || '';
        return `${name}::${asset}::${collections}`;
      })
      .sort()
      .join('|');
  }, [savedLibraryMappings]);

  const [libraries, setLibraries] = useState([]);
  const [library, setLibrary] = useState(initialLibrary || '');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [notReadyCount, setNotReadyCount] = useState(0);
  const [rawItems, setRawItems] = useState([]);
  const [query, setQuery] = useState('');
  const [sortMode, setSortModeState] = useState('title');
  const [notReadyOnly, setNotReadyOnlyState] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAbort = useRef(null);
  const initialLibraryRef = useRef(initialLibrary);
  const libraryRef = useRef(library);

  useEffect(() => {
    libraryRef.current = library;
  }, [library]);

  const fetchLibraries = useCallback(async () => {
    if (!canFetch) return;
    try {
      setError(null);
      const data = await fetchJson('/api/libraries');
      const libs = prioritizeLibraries(
        Array.isArray(data?.libraries) ? data.libraries : Array.isArray(data) ? data : []
      );

      setLibraries(libs);
      setError(null);
      if (!libs.length) return;

      const desired = initialLibraryRef.current;
      if (desired && libs.includes(desired)) {
        initialLibraryRef.current = null;
        setLibrary(desired);
        return;
      }
      const currentLibrary = libraryRef.current;
      if (!currentLibrary || !libs.includes(currentLibrary)) {
        setLibrary(libs.find((name) => !isCollectionsLibrary(name)) || libs[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch libraries');
    }
  }, [canFetch]);

  useEffect(() => {
    if (!canFetch) return;
    fetchLibraries();
  }, [canFetch, fetchLibraries, savedLibraryMappingsKey]);

  const loadItems = useCallback(
    async ({
      targetLibrary,
      targetPage,
      searchTerm,
      sortMode: overrideSortMode,
      notReadyOnly: overrideNotReadyOnly,
    } = {}) => {
      const lib = targetLibrary ?? library;
      if (!canFetch || !lib) return;
      const desiredPage = targetPage ?? page;
      const q = searchTerm ?? query;
      const sort = overrideSortMode ?? sortMode;
      const notReady = overrideNotReadyOnly ?? notReadyOnly;
      const normalized = lib.trim().toLowerCase();
      const base = normalized === 'collections' ? '/collections' : '/api/items';
      const params = new URLSearchParams();
      if (base !== '/collections') {
        params.set('library', lib);
      }
      params.set('page', String(desiredPage));
      params.set('page_size', String(PAGE_SIZE));
      params.set('sort', sort);
      if (q) {
        params.set('query', q);
      }
      if (notReady) {
        params.set('not_ready_only', 'true');
      }

      if (fetchAbort.current) {
        fetchAbort.current.abort();
      }
      const controller = new AbortController();
      fetchAbort.current = controller;
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${base}?${params.toString()}`, { signal: controller.signal });
        const data = await safeJson(response);
        if (!response.ok) {
          const message = responseErrorMessage(response, data);
          throw new Error(message);
        }
        setRawItems(Array.isArray(data?.items) ? data.items : []);
        setTotalPages(data?.total_pages || 1);
        setTotalCount(data?.total_count || (Array.isArray(data?.items) ? data.items.length : 0));
        setNotReadyCount(data?.not_ready_count || 0);
      } catch (err) {
        if (err.name === 'AbortError') return;
        setRawItems([]);
        setTotalPages(1);
        setTotalCount(0);
        setNotReadyCount(0);
        setError(err.message || 'Failed to load items');
      } finally {
        if (fetchAbort.current === controller) {
          fetchAbort.current = null;
          setLoading(false);
        }
      }
    },
    [canFetch, library, page, query, sortMode, notReadyOnly]
  );

  useEffect(() => {
    if (!canFetch || !library) return;
    loadItems();
  }, [canFetch, library, page, query, loadItems]);

  useEffect(() => () => fetchAbort.current?.abort(), []);

  useEffect(() => {
    if (enabled) return;
    fetchAbort.current?.abort();
    fetchAbort.current = null;
    setLoading(false);
  }, [enabled]);

  const changeLibrary = useCallback((next) => {
    setPage(1);
    setLibrary(next);
  }, []);

  const changePage = useCallback((nextPage) => {
    setPage(nextPage);
  }, []);

  const changeQuery = useCallback((nextQuery) => {
    setPage(1);
    setQuery(nextQuery);
  }, []);

  const changeSortMode = useCallback((nextSortMode) => {
    setPage(1);
    setSortModeState(nextSortMode === 'newest' ? 'newest' : 'title');
  }, []);

  const changeNotReadyOnly = useCallback((nextValue) => {
    setPage(1);
    setNotReadyOnlyState((prev) => {
      const resolved = typeof nextValue === 'function' ? nextValue(prev) : nextValue;
      return Boolean(resolved);
    });
  }, []);

  const reload = useCallback(() => {
    loadItems();
  }, [loadItems]);

  const exclusionsKey = useMemo(() => {
    if (!Array.isArray(exclusions) || exclusions.length === 0) return '';
    return exclusions
      .map((entry) => {
        if (!entry || typeof entry !== 'object') return '';
        const libraryName = entry.library != null ? String(entry.library).trim() : '';
        const typeName = entry.type != null ? String(entry.type).trim() : '';
        const ratingKeyValue = entry.ratingKey != null ? String(entry.ratingKey).trim() : '';
        if (!libraryName || !ratingKeyValue) return '';
        return `${libraryName}:::${typeName}:::${ratingKeyValue}`;
      })
      .filter(Boolean)
      .sort()
      .join('|');
  }, [exclusions]);

  const previousExclusionsKeyRef = useRef(exclusionsKey);
  const handledInitialExclusionsRef = useRef(false);

  useEffect(() => {
    const previousKey = previousExclusionsKeyRef.current;
    if (!handledInitialExclusionsRef.current) {
      handledInitialExclusionsRef.current = true;
      previousExclusionsKeyRef.current = exclusionsKey;
      return;
    }
    if (previousKey === exclusionsKey) {
      return;
    }
    previousExclusionsKeyRef.current = exclusionsKey;
    if (!library) {
      return;
    }
    reload();
  }, [exclusionsKey, reload, library]);

  const refreshNotReadyCount = useCallback(
    async (targetLibrary) => {
      const lib = targetLibrary ?? library;
      if (!lib) return 0;
      const normalized = lib.trim().toLowerCase();
      const base = normalized === 'collections' ? '/collections' : '/api/items';
      const params = new URLSearchParams();
      if (base !== '/collections') {
        params.set('library', lib);
      }
      params.set('page', '1');
      params.set('page_size', '1');
      try {
        const response = await fetch(`${base}?${params.toString()}`);
        const data = await safeJson(response);
        if (!response.ok) {
          const message = responseErrorMessage(response, data);
          throw new Error(message);
        }
        const nextNotReady =
          typeof data?.not_ready_count === 'number'
            ? data.not_ready_count
            : typeof data?.notReadyCount === 'number'
            ? data.notReadyCount
            : 0;
        setNotReadyCount(nextNotReady);
        return nextNotReady;
      } catch (err) {
        console.warn('Failed to refresh not-ready count', err);
        return notReadyCount;
      }
    },
    [library, notReadyCount]
  );

  const fetchAllForLibrary = useCallback(
    async (lib, searchTerm, options = {}) => {
      if (!lib) return { items: [], totalPages: 0, totalCount: 0 };
      const normalized = lib.trim().toLowerCase();
      const base = normalized === 'collections' ? '/collections' : '/api/items';
      const params = new URLSearchParams();
      if (base !== '/collections') {
        params.set('library', lib);
      }
      params.set('page_size', String(PAGE_SIZE));
      if (searchTerm) {
        params.set('query', searchTerm);
      }
      params.set('sort', options?.sortMode || sortMode);
      if (options?.notReadyOnly) {
        params.set('not_ready_only', 'true');
      }

      const makeUrl = (pageNumber) => {
        const search = new URLSearchParams(params);
        search.set('page', String(pageNumber));
        return `${base}?${search.toString()}`;
      };

      const firstResponse = await fetch(makeUrl(1));
      const firstData = await safeJson(firstResponse);
      if (!firstResponse.ok) {
        const message = responseErrorMessage(firstResponse, firstData);
        throw new Error(message);
      }
      const allItems = Array.isArray(firstData?.items) ? [...firstData.items] : [];
      const totalPagesResp = firstData?.total_pages || 1;
      const totalCountResp = firstData?.total_count || allItems.length;
      const notReadyCountResp = firstData?.not_ready_count || 0;

      for (let p = 2; p <= totalPagesResp; p += 1) {
        const response = await fetch(makeUrl(p));
        const data = await safeJson(response);
        if (!response.ok) {
          const message = responseErrorMessage(response, data);
          throw new Error(message);
        }
        if (Array.isArray(data?.items)) {
          allItems.push(...data.items);
        }
      }

      return {
        items: allItems,
        totalPages: totalPagesResp,
        totalCount: totalCountResp,
        notReadyCount: notReadyCountResp,
      };
    },
    [sortMode]
  );

  const updateItem = useCallback((ratingKey, updates) => {
    setRawItems((prev) =>
      prev.map((item) => {
        const key = item?.ratingKey ?? item?.key ?? item?.id;
        if (key == null) return item;
        if (String(key) !== String(ratingKey)) return item;
        return { ...item, ...updates };
      })
    );
  }, []);

  const filteredItems = useMemo(() => {
    if (!Array.isArray(rawItems)) return [];
    if (typeof isItemExcluded !== 'function') {
      return rawItems;
    }
    if (!Array.isArray(exclusions) || exclusions.length === 0) {
      return rawItems;
    }
    const libraryFallback = typeof library === 'string' ? library.trim() : '';
    const toText = (value) => (value == null ? '' : String(value).trim());
    return rawItems.filter((item) => {
      const ratingKeyRaw = item?.ratingKey ?? item?.key ?? item?.id;
      if (ratingKeyRaw == null) return true;
      const ratingKey = toText(ratingKeyRaw);
      if (!ratingKey) return true;
      const candidates = [];
      const possibleLibraries = [
        item?.library,
        item?.libraryName,
        item?.library_name,
        item?.sourceLibrary,
        item?.source_library,
        item?.source,
        item?.parentLibrary,
        item?.parent_library,
        item?.librarySectionTitle,
        item?.collectionLibrary,
        item?.collection_library,
      ];
      possibleLibraries.forEach((value) => {
        const text = toText(value);
        if (text) {
          candidates.push(text);
        }
      });
      if (libraryFallback) {
        candidates.push(libraryFallback);
      }
      if (!candidates.length) {
        return true;
      }
      const uniqueLibraries = Array.from(new Set(candidates.map((name) => toText(name)).filter(Boolean)));
      return !uniqueLibraries.some((name) => isItemExcluded(name, ratingKey));
    });
  }, [rawItems, library, exclusions, isItemExcluded]);

  return useMemo(
    () => ({
      libraries,
      library,
      setLibrary: changeLibrary,
      page,
      setPage: changePage,
      totalPages,
      totalCount,
      notReadyCount,
      items: filteredItems,
      query,
      setQuery: changeQuery,
      sortMode,
      setSortMode: changeSortMode,
      notReadyOnly,
      setNotReadyOnly: changeNotReadyOnly,
      loading,
      error,
      reload,
      setNotReadyCount,
      refreshNotReadyCount,
      fetchAllForLibrary,
      updateItem,
      pageSize: PAGE_SIZE,
    }),
    [
      libraries,
      library,
      changeLibrary,
      page,
      changePage,
      totalPages,
      totalCount,
      notReadyCount,
      filteredItems,
      query,
      changeQuery,
      sortMode,
      changeSortMode,
      notReadyOnly,
      changeNotReadyOnly,
      loading,
      error,
      reload,
      setNotReadyCount,
      refreshNotReadyCount,
      fetchAllForLibrary,
      updateItem,
    ]
  );
}
