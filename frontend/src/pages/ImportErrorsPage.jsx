import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import {
  clearImportErrorReport,
  formatImportError,
  importErrorIsFolderIssue,
  loadImportErrorReport,
  saveImportErrorReport,
} from '../utils/importErrors.js';
import { buildDetailPath } from '../utils/items.js';

function decodeRouteLibrary(routeLibrary) {
  try {
    return decodeURIComponent(routeLibrary || '').trim();
  } catch {
    return String(routeLibrary || '').trim();
  }
}

function makeModalItem(row, selectedLibrary) {
  return {
    ...row,
    library: row.library || selectedLibrary,
    name: row.title,
    folderName: row.folder,
    folder: row.folder,
    assetReady: false,
  };
}

function ImportErrorsPage() {
  const { library: routeLibrary = '' } = useParams();
  const navigate = useNavigate();
  const selectedLibrary = decodeRouteLibrary(routeLibrary);
  const {
    library,
    setLibrary,
    setNotReadyCount,
    updateItem,
  } = useLibraryItemsContext();

  const [report, setReport] = useState(null);
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [folderModalItem, setFolderModalItem] = useState(null);

  useEffect(() => {
    if (selectedLibrary && selectedLibrary !== library) {
      setLibrary(selectedLibrary);
    }
  }, [selectedLibrary, library, setLibrary]);

  useEffect(() => {
    setReport(loadImportErrorReport(selectedLibrary));
  }, [selectedLibrary]);

  const rows = useMemo(() => {
    return Array.isArray(report?.errors) ? report.errors : [];
  }, [report]);

  const unresolvedCount = useMemo(
    () => rows.filter((row) => row && !row.resolved).length,
    [rows]
  );
  const resolvedCount = rows.length - unresolvedCount;
  const savedAtLabel = report?.savedAt ? new Date(report.savedAt).toLocaleString() : '';

  const backHref = useMemo(() => {
    const params = new URLSearchParams();
    if (selectedLibrary) params.set('lib', selectedLibrary);
    return params.toString() ? `/libraries?${params.toString()}` : '/libraries';
  }, [selectedLibrary]);

  const mappingHref = selectedLibrary
    ? `/libraries/${encodeURIComponent(selectedLibrary)}/mapping`
    : '/libraries';

  const persistRows = useCallback(
    (nextRows) => {
      const nextReport = saveImportErrorReport(selectedLibrary, nextRows, report?.receipt || null);
      setReport(nextReport);
    },
    [report?.receipt, selectedLibrary]
  );

  const handleClear = useCallback(() => {
    clearImportErrorReport(selectedLibrary);
    setReport(null);
  }, [selectedLibrary]);

  const handleBack = useCallback(() => {
    navigate(backHref);
  }, [backHref, navigate]);

  const openFolderModal = useCallback(
    (row) => {
      if (!row?.ratingKey) return;
      setFolderModalItem(makeModalItem(row, selectedLibrary));
      setFolderModalOpen(true);
    },
    [selectedLibrary]
  );

  const closeFolderModal = useCallback(() => {
    setFolderModalOpen(false);
    setFolderModalItem(null);
  }, []);

  const handleFolderAssigned = useCallback(
    ({ folderName }) => {
      if (!folderModalItem) return;
      const ratingKey = folderModalItem.ratingKey;
      if (ratingKey != null) {
        updateItem(String(ratingKey), { assetReady: true, folderName, folder: folderName });
      }
      const nextRows = rows.map((row) => {
        if (row.id !== folderModalItem.id) return row;
        return {
          ...row,
          folder: folderName,
          resolved: true,
          resolvedFolder: folderName,
        };
      });
      persistRows(nextRows);
      if (typeof setNotReadyCount === 'function') {
        setNotReadyCount((prev) => Math.max(0, (Number(prev) || 0) - 1));
      }
      closeFolderModal();
    },
    [closeFolderModal, folderModalItem, persistRows, rows, setNotReadyCount, updateItem]
  );

  if (!selectedLibrary) {
    return (
      <main className="import-errors-page">
        <p>No library selected.</p>
      </main>
    );
  }

  return (
    <div>
      <header className="import-errors-header">
        <div className="import-errors-heading">
          <button type="button" className="back-button" onClick={handleBack}>
            Back
          </button>
          <div>
            <span className="page-eyebrow">Import review</span>
            <h1>Import Issues</h1>
            <p>{selectedLibrary}</p>
          </div>
        </div>
        <div className="import-errors-actions">
          <Link className="btn-secondary" to={mappingHref}>
            Scan Mapping
          </Link>
          <button type="button" className="btn-secondary" onClick={handleClear} disabled={!rows.length}>
            Clear
          </button>
        </div>
      </header>
      <main className="import-errors-page">
        <div className="import-errors-summary" aria-live="polite">
          <span className="badge-label">
            {unresolvedCount.toLocaleString()} open
          </span>
          <span>{resolvedCount.toLocaleString()} resolved</span>
          {savedAtLabel ? <span>Last import: {savedAtLabel}</span> : null}
        </div>

        {!rows.length ? (
          <section className="import-errors-empty">
            <h2>No Import Issues</h2>
            <p>The latest import error report for this library is empty.</p>
            <Link className="btn" to={backHref}>
              Back to Library
            </Link>
          </section>
        ) : (
          <div className="import-errors-table" role="table" aria-label="Import issues">
            <div className="import-errors-row import-errors-row-header" role="row">
              <div role="columnheader">Media</div>
              <div role="columnheader">Folder</div>
              <div role="columnheader">Issue</div>
              <div role="columnheader">Action</div>
            </div>
            {rows.map((row) => {
              const rowLibrary = row.library || selectedLibrary;
              const folderIssue = importErrorIsFolderIssue(row);
              const canConfirmFolder = folderIssue && row.ratingKey && !row.resolved;
              const detailPath = row.ratingKey ? buildDetailPath(makeModalItem(row, rowLibrary), rowLibrary) : null;
              return (
                <div
                  className={`import-errors-row${row.resolved ? ' is-resolved' : ''}`}
                  role="row"
                  key={row.id}
                >
                  <div className="import-errors-media" role="cell">
                    <strong>{row.title || '(Untitled)'}</strong>
                    {row.year ? <span>{row.year}</span> : null}
                  </div>
                  <div role="cell">
                    {row.resolved && row.resolvedFolder ? row.resolvedFolder : row.folder || 'Not assigned'}
                  </div>
                  <div className="import-errors-message" role="cell">
                    <span>{row.asset || 'Import'}</span>
                    <span>{row.message || formatImportError(row)}</span>
                  </div>
                  <div className="import-errors-action" role="cell">
                    {row.resolved ? (
                      <span className="mapping-status-ok">Resolved</span>
                    ) : canConfirmFolder ? (
                      <button type="button" onClick={() => openFolderModal(row)}>
                        Confirm Folder
                      </button>
                    ) : detailPath ? (
                      <Link className="btn-secondary" to={detailPath}>
                        Open Details
                      </Link>
                    ) : folderIssue ? (
                      <Link className="btn-secondary" to={mappingHref}>
                        Scan Mapping
                      </Link>
                    ) : (
                      <span className="mapping-status-miss">Review</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
      <FolderFinderModal
        isOpen={folderModalOpen}
        item={folderModalItem}
        library={selectedLibrary}
        onClose={closeFolderModal}
        onFolderAssigned={handleFolderAssigned}
      />
    </div>
  );
}

export default ImportErrorsPage;
