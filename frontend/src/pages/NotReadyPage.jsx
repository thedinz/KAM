import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ItemGrid from '../components/ItemGrid.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';

function NotReadyPage() {
  const navigate = useNavigate();
  const { library: libraryParam } = useParams();
  const targetLibrary = libraryParam ? decodeURIComponent(libraryParam) : '';
  const {
    library,
    setLibrary,
    pageSize,
    notReadyCount,
    setNotReadyCount,
    updateItem,
  } = useLibraryItemsContext();

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [folderModalItem, setFolderModalItem] = useState(null);

  useEffect(() => {
    if (!targetLibrary) return;
    if (targetLibrary !== library) {
      setLibrary(targetLibrary);
    }
  }, [targetLibrary, library, setLibrary]);

  useEffect(() => {
    setPage(1);
  }, [targetLibrary]);

  const backHref = useMemo(() => {
    if (!targetLibrary) {
      return '/libraries';
    }
    const search = new URLSearchParams();
    search.set('lib', targetLibrary);
    return `/libraries?${search.toString()}`;
  }, [targetLibrary]);

  const fetchItems = useCallback(
    async (desiredPage = 1) => {
      if (!targetLibrary) {
        setItems([]);
        setTotalPages(1);
        setNotReadyCount(0);
        return;
      }
      setLoading(true);
      setError('');
      const params = new URLSearchParams();
      const trimmedLibrary = targetLibrary.trim();
      const isCollections = trimmedLibrary.toLowerCase() === 'collections';
      params.set('page', String(desiredPage));
      params.set('page_size', String(pageSize));
      params.set('not_ready_only', '1');
      try {
        let endpoint = '/api/items';
        if (isCollections) {
          endpoint = '/collections';
        } else {
          params.set('library', trimmedLibrary);
        }
        const response = await fetch(`${endpoint}?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) {
          const message = data?.detail || data?.error || `${response.status} ${response.statusText}`;
          throw new Error(message);
        }
        const list = Array.isArray(data?.items) ? data.items : [];
        const reportedPage = data?.page || desiredPage;
        const nextTotalPages = data?.total_pages || 1;
        setTotalPages(nextTotalPages);
        if (reportedPage !== desiredPage) {
          setPage(reportedPage);
        }
        setItems(list);
        const nextNotReady =
          typeof data?.not_ready_count === 'number'
            ? data.not_ready_count
            : typeof data?.notReadyCount === 'number'
            ? data.notReadyCount
            : 0;
        setNotReadyCount(nextNotReady);
      } catch (err) {
        setItems([]);
        setError(err.message || 'Failed to load not-ready items');
      } finally {
        setLoading(false);
      }
    },
    [targetLibrary, pageSize, setNotReadyCount]
  );

  useEffect(() => {
    fetchItems(page);
  }, [fetchItems, page]);

  const handleFirst = useCallback(() => setPage(1), []);
  const handlePrev = useCallback(() => setPage((prev) => Math.max(1, prev - 1)), []);
  const handleNext = useCallback(() => setPage((prev) => Math.min(totalPages, prev + 1)), [totalPages]);
  const handleLast = useCallback(() => setPage(totalPages || 1), [totalPages]);

  const handleRequestFolder = useCallback((item) => {
    setFolderModalItem(item);
    setFolderModalOpen(true);
  }, []);

  const handleCloseFolderModal = useCallback(() => {
    setFolderModalItem(null);
    setFolderModalOpen(false);
  }, []);

  const handleFolderAssigned = useCallback(
    async ({ folderName }) => {
      if (!folderModalItem) return;
      const ratingKey = folderModalItem?.ratingKey ?? folderModalItem?.key ?? folderModalItem?.id;
      if (ratingKey != null) {
        updateItem(String(ratingKey), { assetReady: true, folderName, folder: folderName });
        setItems((prev) =>
          prev.filter((item) => {
            const key = item?.ratingKey ?? item?.key ?? item?.id;
            return key == null || String(key) !== String(ratingKey);
          })
        );
        setNotReadyCount((prev) => Math.max(0, (Number(prev) || 0) - 1));
      }
      handleCloseFolderModal();
      await fetchItems(page);
    },
    [folderModalItem, updateItem, handleCloseFolderModal, fetchItems, page]
  );

  const notReadyLabel = useMemo(() => {
    const count = Number(notReadyCount) || 0;
    return `${count.toLocaleString()} not-ready item${count === 1 ? '' : 's'}`;
  }, [notReadyCount]);

  const pageLabel = useMemo(() => {
    return `Page ${page} / ${totalPages || 1}`;
  }, [page, totalPages]);

  const handleBack = useCallback(() => {
    navigate(backHref);
  }, [navigate, backHref]);

  return (
    <div>
      <header className="not-ready-header">
        <div className="not-ready-heading">
          <button type="button" className="back-button" onClick={handleBack}>
            ← Back
          </button>
          <div>
            <h1>Not Ready Items</h1>
            <p>
              {targetLibrary ? `Library: ${targetLibrary}` : 'Select a library to review not-ready items.'}
            </p>
          </div>
        </div>
        <div className="not-ready-meta">
          <span className="badge-label">{notReadyLabel}</span>
          <span>{pageLabel}</span>
        </div>
        <Link className="settings-link" to="/settings" aria-label="Open settings">
          <span aria-hidden="true">⚙</span>
        </Link>
      </header>
      <main>
        <ItemGrid
          items={items}
          library={targetLibrary}
          onRequestFolder={handleRequestFolder}
          loading={loading}
          error={error}
        />
        <nav className="pager not-ready-pager" aria-label="Pagination">
          <button type="button" onClick={handleFirst} disabled={page <= 1}>
            « First
          </button>
          <button type="button" onClick={handlePrev} disabled={page <= 1}>
            ‹ Prev
          </button>
          <span aria-live="polite">{pageLabel}</span>
          <button type="button" onClick={handleNext} disabled={page >= totalPages}>
            Next ›
          </button>
          <button type="button" onClick={handleLast} disabled={page >= totalPages}>
            Last »
          </button>
        </nav>
      </main>
      <FolderFinderModal
        isOpen={folderModalOpen}
        item={folderModalItem}
        library={targetLibrary}
        onClose={handleCloseFolderModal}
        onFolderAssigned={handleFolderAssigned}
      />
    </div>
  );
}

export default NotReadyPage;
