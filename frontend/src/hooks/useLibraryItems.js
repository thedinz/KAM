import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const PAGE_SIZE = 60;

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const message = `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return response.json();
}

export function useLibraryItems({ initialLibrary } = {}) {
  const [libraries, setLibraries] = useState([]);
  const [library, setLibrary] = useState(initialLibrary || '');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');
  const [notReadyOnly, setNotReadyOnlyState] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAbort = useRef(null);
  const initialLibraryRef = useRef(initialLibrary);

  const fetchLibraries = useCallback(async () => {
    try {
      const data = await fetchJson('/api/libraries');
      let libs = Array.isArray(data?.libraries) ? data.libraries : Array.isArray(data) ? data : [];
      libs = libs.map((name) => String(name));

      try {
        const probe = await fetch('/collections?page=1&page_size=1');
        if (probe.ok && !libs.includes('Collections')) {
          libs = libs.concat('Collections');
        }
      } catch (err) {
        console.warn('Collections probe failed', err);
      }

      setLibraries(libs);
      if (!libs.length) return;

      const desired = initialLibraryRef.current;
      if (desired && libs.includes(desired)) {
        initialLibraryRef.current = null;
        setLibrary(desired);
        return;
      }
      if (!library || !libs.includes(library)) {
        setLibrary(libs[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch libraries');
    }
  }, [library]);

  useEffect(() => {
    fetchLibraries();
  }, [fetchLibraries]);

  const loadItems = useCallback(
    async ({ targetLibrary, targetPage, searchTerm, notReadyOnly: overrideNotReadyOnly } = {}) => {
      const lib = targetLibrary ?? library;
      if (!lib) return;
      const desiredPage = targetPage ?? page;
      const q = searchTerm ?? query;
      const notReady = overrideNotReadyOnly ?? notReadyOnly;
      const normalized = lib.trim().toLowerCase();
      const base = normalized === 'collections' ? '/collections' : '/api/items';
      const params = new URLSearchParams();
      if (base !== '/collections') {
        params.set('library', lib);
      }
      params.set('page', String(desiredPage));
      params.set('page_size', String(PAGE_SIZE));
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
        if (!response.ok) {
          const message = `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const data = await response.json();
        setItems(Array.isArray(data?.items) ? data.items : []);
        setTotalPages(data?.total_pages || 1);
        setTotalCount(data?.total_count || (Array.isArray(data?.items) ? data.items.length : 0));
        setNotReadyCount(data?.not_ready_count || 0);
      } catch (err) {
        if (err.name === 'AbortError') return;
        setItems([]);
        setTotalPages(1);
        setTotalCount(0);
        setNotReadyCount(0);
        setError(err.message || 'Failed to load items');
      } finally {
        setLoading(false);
      }
    },
    [library, page, query, notReadyOnly]
  );

  useEffect(() => {
    if (!library) return;
    loadItems();
  }, [library, page, query, loadItems]);

  useEffect(() => () => fetchAbort.current?.abort(), []);

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
        if (!response.ok) {
          const message = `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const data = await response.json();
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
      if (options?.notReadyOnly) {
        params.set('not_ready_only', 'true');
      }

      const makeUrl = (pageNumber) => {
        const search = new URLSearchParams(params);
        search.set('page', String(pageNumber));
        return `${base}?${search.toString()}`;
      };

      const firstResponse = await fetch(makeUrl(1));
      if (!firstResponse.ok) {
        const message = `${firstResponse.status} ${firstResponse.statusText}`;
        throw new Error(message);
      }
      const firstData = await firstResponse.json();
      const allItems = Array.isArray(firstData?.items) ? [...firstData.items] : [];
      const totalPagesResp = firstData?.total_pages || 1;
      const totalCountResp = firstData?.total_count || allItems.length;
      const notReadyCountResp = firstData?.not_ready_count || 0;

      for (let p = 2; p <= totalPagesResp; p += 1) {
        const response = await fetch(makeUrl(p));
        if (!response.ok) {
          const message = `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const data = await response.json();
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
    []
  );

  const updateItem = useCallback((ratingKey, updates) => {
    setItems((prev) =>
      prev.map((item) => {
        const key = item?.ratingKey ?? item?.key ?? item?.id;
        if (key == null) return item;
        if (String(key) !== String(ratingKey)) return item;
        return { ...item, ...updates };
      })
    );
  }, []);

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
      items,
      query,
      setQuery: changeQuery,
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
      items,
      query,
      changeQuery,
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
