import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ImportStatusPanel from '../components/ImportStatusPanel.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { assignMatchedFolders, runLibraryMappingScan } from '../utils/mappingScan.js';

function storageKeyForLibrary(library) {
  return `kam.mappingScan.${String(library || '').trim().toLowerCase()}`;
}

function MappingScanPage() {
  const { library: routeLibrary = '' } = useParams();
  const navigate = useNavigate();
  const {
    library,
    setLibrary,
    reload,
    refreshNotReadyCount,
    fetchAllForLibrary,
    updateItem,
  } = useLibraryItemsContext();

  const selectedLibrary = decodeURIComponent(routeLibrary || '').trim();
  const [scanState, setScanState] = useState({ active: false, percent: 0, label: '', errors: [] });
  const [rows, setRows] = useState([]);
  const [lastScannedAt, setLastScannedAt] = useState('');
  const [scanError, setScanError] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [folderModalItem, setFolderModalItem] = useState(null);

  useEffect(() => {
    if (selectedLibrary && selectedLibrary !== library) {
      setLibrary(selectedLibrary);
    }
  }, [selectedLibrary, library, setLibrary]);

  useEffect(() => {
    if (!selectedLibrary) return;
    try {
      const raw = localStorage.getItem(storageKeyForLibrary(selectedLibrary));
      if (!raw) return;
      const parsed = JSON.parse(raw);
      const savedRows = Array.isArray(parsed?.entries) ? parsed.entries : [];
      setRows(savedRows);
      setLastScannedAt(typeof parsed?.scannedAt === 'string' ? parsed.scannedAt : '');
    } catch (err) {
      console.warn('Failed to restore mapping scan cache', err);
    }
  }, [selectedLibrary]);

  const runScan = useCallback(async () => {
    if (!selectedLibrary) return;
    setIsScanning(true);
    setScanError('');
    setScanState({ active: true, percent: 0, label: 'Preparing mapping scan…', errors: [] });
    try {
      const result = await runLibraryMappingScan({
        library: selectedLibrary,
        fetchAllForLibrary,
        onProgress: ({ percent, label }) => {
          setScanState({ active: true, percent, label: label || '', errors: [] });
        },
      });
      const assignmentResult = await assignMatchedFolders({
        library: selectedLibrary,
        entries: result.entries,
        onProgress: ({ label }) => {
          setScanState({ active: true, percent: 100, label: label || '', errors: [] });
        },
      });
      const nextResult = { ...result, entries: assignmentResult.entries };
      const unmatchedCountNext = nextResult.entries.filter((entry) => !entry.matched).length;
      const assignmentErrors = assignmentResult.errors || [];
      const appliedText = assignmentResult.assignedCount
        ? ` Applied ${assignmentResult.assignedCount.toLocaleString()} folder assignment${
            assignmentResult.assignedCount === 1 ? '' : 's'
          }.`
        : '';
      const errorText = assignmentErrors.length
        ? ` ${assignmentErrors.length.toLocaleString()} assignment${
            assignmentErrors.length === 1 ? '' : 's'
          } failed.`
        : '';
      setRows(nextResult.entries);
      setLastScannedAt(result.scannedAt);
      localStorage.setItem(storageKeyForLibrary(selectedLibrary), JSON.stringify(nextResult));
      setScanState({
        active: true,
        percent: 100,
        label: `Scan complete. ${unmatchedCountNext.toLocaleString()} unmatched item${
          unmatchedCountNext === 1 ? '' : 's'
        }.${appliedText}${errorText}`,
        errors: assignmentErrors,
      });
      await reload();
      await refreshNotReadyCount(selectedLibrary);
    } catch (err) {
      const message = err?.message || String(err);
      setScanError(message);
      setScanState({ active: true, percent: 0, label: `Scan failed: ${message}`, errors: [] });
    } finally {
      setIsScanning(false);
    }
  }, [selectedLibrary, fetchAllForLibrary, reload, refreshNotReadyCount]);

  useEffect(() => {
    if (!selectedLibrary || rows.length) return;
    runScan();
  }, [selectedLibrary, rows.length, runScan]);

  const unmatchedCount = useMemo(() => rows.filter((entry) => !entry.matched).length, [rows]);

  const openFolderModal = useCallback((entry) => {
    setFolderModalItem(entry);
    setFolderModalOpen(true);
  }, []);

  const closeFolderModal = useCallback(() => {
    setFolderModalOpen(false);
    setFolderModalItem(null);
  }, []);

  const handleFolderAssigned = useCallback(
    async ({ folderName }) => {
      if (!folderModalItem) return;
      const ratingKey = String(folderModalItem?.ratingKey || '').trim();
      if (ratingKey) {
        updateItem(ratingKey, { assetReady: true, folderName, folder: folderName });
      }
      const nextRows = rows.map((entry) => {
        if (String(entry.ratingKey) !== ratingKey) return entry;
        return {
          ...entry,
          currentFolder: folderName,
          matchedFolder: folderName,
          matched: true,
        };
      });
      setRows(nextRows);
      localStorage.setItem(
        storageKeyForLibrary(selectedLibrary),
        JSON.stringify({ library: selectedLibrary, scannedAt: lastScannedAt || new Date().toISOString(), entries: nextRows })
      );
      closeFolderModal();
      await reload();
      await refreshNotReadyCount(selectedLibrary);
    },
    [folderModalItem, updateItem, rows, selectedLibrary, lastScannedAt, closeFolderModal, reload, refreshNotReadyCount]
  );

  if (!selectedLibrary) {
    return (
      <main className="mapping-page">
        <p>No library selected.</p>
      </main>
    );
  }

  return (
    <div>
      <header>
        <h1>Mapping Scan</h1>
        <div className="mapping-header-actions">
          <button type="button" onClick={runScan} disabled={isScanning}>
            {isScanning ? 'Scanning…' : 'Scan Again'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate(`/libraries/${encodeURIComponent(selectedLibrary)}`)}>
            Back to Library
          </button>
        </div>
        <Link className="settings-link" to="/settings" aria-label="Open settings">
          <span aria-hidden="true">⚙</span>
        </Link>
      </header>
      <main className="mapping-page">
        <p className="mapping-subtitle">
          {selectedLibrary}: {rows.length.toLocaleString()} scanned • {unmatchedCount.toLocaleString()} unmatched
        </p>
        {lastScannedAt ? <p className="mapping-meta">Last scanned: {new Date(lastScannedAt).toLocaleString()}</p> : null}
        <ImportStatusPanel
          active={scanState.active}
          percent={scanState.percent}
          label={scanState.label}
          errors={scanState.errors}
          errorHeading="Mapping Errors"
          errorNoun="mapping error"
          modalId="mappingErrorsDialog"
        />
        {scanError ? <p className="mapping-error">{scanError}</p> : null}
        <div className="mapping-table" role="table" aria-label="Mapping scan results">
          <div className="mapping-row mapping-row-header" role="row">
            <div role="columnheader">Media</div>
            <div role="columnheader">Folder</div>
            <div role="columnheader">Status</div>
          </div>
          {rows.map((entry) => (
            <div className="mapping-row" key={`${entry.ratingKey}-${entry.title}`} role="row">
              <div className="mapping-title" role="cell">{entry.title}</div>
              <div role="cell">
                <button type="button" className="mapping-folder-btn" onClick={() => openFolderModal(entry)}>
                  {entry.matchedFolder || 'Not matched (click to set folder)'}
                </button>
              </div>
              <div
                role="cell"
                className={entry.assignmentError ? 'mapping-status-miss' : entry.matched ? 'mapping-status-ok' : 'mapping-status-miss'}
              >
                {entry.assignmentError
                  ? `⚠ ${entry.assignmentError}`
                  : entry.assigned
                  ? '✅ Assigned'
                  : entry.matched
                  ? '✅ Match'
                  : '❌ Missing'}
              </div>
            </div>
          ))}
        </div>
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

export default MappingScanPage;
