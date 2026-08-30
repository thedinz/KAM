import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && size >= 1024; index += 1) {
    size /= 1024;
    unit = units[index];
  }
  return `${size >= 10 ? size.toFixed(0) : size.toFixed(1)} ${unit}`;
}

function OrphanedAssetsPage() {
  const navigate = useNavigate();
  const { library: libraryParam } = useParams();
  const targetLibrary = libraryParam ? decodeURIComponent(libraryParam) : '';
  const { library, setLibrary, reload } = useLibraryItemsContext();
  const [items, setItems] = useState([]);
  const [root, setRoot] = useState('');
  const [selected, setSelected] = useState(() => new Set());
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionFolder, setActionFolder] = useState('');
  const [showExcluded, setShowExcluded] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    if (targetLibrary && targetLibrary !== library) {
      setLibrary(targetLibrary);
    }
  }, [targetLibrary, library, setLibrary]);

  const fetchOrphanedAssets = useCallback(async () => {
    if (!targetLibrary) return;
    setLoading(true);
    setError('');
    setStatus('');
    try {
      const params = new URLSearchParams({ library: targetLibrary });
      if (showExcluded) params.set('includeExcluded', 'true');
      const response = await fetch(`/api/orphaned-assets?${params.toString()}`);
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      const nextItems = Array.isArray(data?.items) ? data.items : [];
      setItems(nextItems);
      setRoot(data?.root || '');
      setSelected((previous) => {
        const available = new Set(nextItems.map((item) => item.folderName));
        return new Set([...previous].filter((name) => available.has(name)));
      });
    } catch (err) {
      setItems([]);
      setError(err?.message || 'Failed to scan orphaned assets.');
    } finally {
      setLoading(false);
    }
  }, [targetLibrary, showExcluded]);

  useEffect(() => {
    fetchOrphanedAssets();
  }, [fetchOrphanedAssets]);

  const selectableItems = useMemo(() => items.filter((item) => !item.excluded), [items]);
  const allSelected = selectableItems.length > 0 && selected.size === selectableItems.length;
  const selectionLabel = `${selected.size.toLocaleString()} selected`;

  const toggleOne = useCallback((folderName) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(folderName)) next.delete(folderName);
      else next.add(folderName);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setSelected((previous) => {
      if (selectableItems.length && previous.size === selectableItems.length) return new Set();
      return new Set(selectableItems.map((item) => item.folderName));
    });
  }, [selectableItems]);

  const setFolderExcluded = useCallback(async (folderName, excluded) => {
    if (!folderName || actionFolder) return;
    setActionFolder(folderName);
    setError('');
    try {
      const response = await fetch(
        excluded ? '/api/orphaned-assets/include' : '/api/orphaned-assets/exclude',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ library: targetLibrary, folderName }),
        }
      );
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      setSelected((previous) => {
        const next = new Set(previous);
        next.delete(folderName);
        return next;
      });
      await fetchOrphanedAssets();
      setStatus(
        excluded
          ? `${folderName} restored to the orphan audit.`
          : `${folderName} excluded because its movie exists.`
      );
    } catch (err) {
      setError(err?.message || 'Failed to update the orphan exclusion.');
    } finally {
      setActionFolder('');
    }
  }, [actionFolder, targetLibrary, fetchOrphanedAssets]);

  const deleteFolders = useCallback(async (folderNames) => {
    const names = [...new Set(folderNames)].filter(Boolean);
    if (!names.length || deleting) return;
    const noun = names.length === 1 ? 'folder' : 'folders';
    const confirmed = window.confirm(
      `Permanently delete ${names.length} orphaned asset ${noun} and everything inside? This cannot be undone.`
    );
    if (!confirmed) return;

    setDeleting(true);
    setError('');
    setStatus(`Rechecking and deleting ${names.length} ${noun}…`);
    try {
      const response = await fetch('/api/orphaned-assets/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ library: targetLibrary, folderNames: names }),
      });
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      const deleted = Array.isArray(data?.deleted) ? data.deleted : [];
      const skipped = Array.isArray(data?.skipped) ? data.skipped : [];
      const failures = Array.isArray(data?.errors) ? data.errors : [];
      setSelected(new Set());
      await fetchOrphanedAssets();
      reload();
      const parts = [`Deleted ${deleted.length} asset ${deleted.length === 1 ? 'folder' : 'folders'}.`];
      if (skipped.length) parts.push(`${skipped.length} skipped because they are no longer orphaned.`);
      if (failures.length) parts.push(`${failures.length} could not be deleted.`);
      setStatus(parts.join(' '));
      if (failures.length) {
        setError(failures.map((entry) => `${entry.folderName}: ${entry.error}`).join(' '));
      }
    } catch (err) {
      setError(err?.message || 'Failed to delete orphaned assets.');
      setStatus('');
    } finally {
      setDeleting(false);
    }
  }, [deleting, targetLibrary, fetchOrphanedAssets, reload]);

  const backHref = useMemo(
    () => (targetLibrary ? `/libraries/${encodeURIComponent(targetLibrary)}` : '/libraries'),
    [targetLibrary]
  );

  return (
    <div>
      <header className="not-ready-header orphaned-assets-header">
        <div className="not-ready-heading">
          <button type="button" className="back-button" onClick={() => navigate(backHref)}>
            ← Back
          </button>
          <div>
            <span className="page-eyebrow">Library cleanup</span>
            <h1>Orphaned Assets</h1>
            <p>
              Asset folders with no matching item in {targetLibrary || 'Plex'}. Keep them for future reuse,
              or delete the ones you no longer want.
            </p>
          </div>
        </div>
        <div className="not-ready-meta">
          <span className="badge-label">{items.length.toLocaleString()} orphaned</span>
          <button type="button" onClick={fetchOrphanedAssets} disabled={loading || deleting}>
            {loading ? 'Scanning…' : 'Scan again'}
          </button>
        </div>
      </header>

      <main className="orphaned-assets-page">
        {root ? <p className="orphaned-assets-root" title={root}>Asset root: <code>{root}</code></p> : null}

        <label className="orphaned-assets-show-excluded">
          <input
            type="checkbox"
            checked={showExcluded}
            onChange={(event) => setShowExcluded(event.target.checked)}
          />
          <span>Show folders excluded because their movie exists</span>
        </label>

        {!loading && !error && items.length ? (
          <div className="orphaned-assets-toolbar">
            <label className="orphaned-assets-select-all">
              <input type="checkbox" checked={allSelected} onChange={toggleAll} />
              <span>Select all</span>
            </label>
            <span>{selectionLabel}</span>
            <button
              type="button"
              className="orphaned-assets-delete-selected"
              onClick={() => deleteFolders([...selected])}
              disabled={!selected.size || deleting}
            >
              {deleting ? 'Deleting…' : 'Delete selected'}
            </button>
          </div>
        ) : null}

        {status ? <div className="success-state orphaned-assets-message" role="status">{status}</div> : null}
        {error ? <div className="error-banner" role="alert">{error}</div> : null}

        {loading ? <div className="loading-state">Scanning Plex and asset folders…</div> : null}
        {!loading && !error && !items.length ? (
          <div className="empty-state">
            <div className="orphaned-assets-empty-copy">
              <strong>No orphaned asset folders</strong>
              <span>Every folder currently matches an item in Plex.</span>
            </div>
          </div>
        ) : null}

        {!loading && items.length ? (
          <div className="orphaned-assets-grid" aria-live="polite">
            {items.map((item) => {
              const checked = selected.has(item.folderName);
              return (
                <article className={`orphaned-asset-card${checked ? ' is-selected' : ''}`} key={item.folderName}>
                  <label className="orphaned-asset-check">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleOne(item.folderName)}
                      aria-label={`Select ${item.folderName}`}
                      disabled={item.excluded}
                    />
                  </label>
                  <div className="orphaned-asset-preview">
                    {item.posterUrl ? (
                      <img src={item.posterUrl} alt="" loading="lazy" />
                    ) : (
                      <span aria-hidden="true">No poster</span>
                    )}
                  </div>
                  <div className="orphaned-asset-copy">
                    <h2 title={item.title || item.folderName}>
                      {item.title || item.folderName}
                      {item.year ? <span>{item.year}</span> : null}
                    </h2>
                    <code title={item.folderName}>{item.folderName}</code>
                    <p>{Number(item.assetCount || 0).toLocaleString()} files <span aria-hidden="true">•</span> {formatBytes(item.sizeBytes)}</p>
                  </div>
                  <div className="orphaned-asset-actions">
                    <button
                      type="button"
                      className="orphaned-asset-exclude"
                      onClick={() => setFolderExcluded(item.folderName, Boolean(item.excluded))}
                      disabled={deleting || Boolean(actionFolder)}
                    >
                      {actionFolder === item.folderName
                        ? 'Saving…'
                        : item.excluded
                          ? 'Restore'
                          : 'Exclude — movie exists'}
                    </button>
                    {!item.excluded ? (
                      <button
                        type="button"
                        className="orphaned-asset-delete"
                        onClick={() => deleteFolders([item.folderName])}
                        disabled={deleting || Boolean(actionFolder)}
                        aria-label={`Delete ${item.folderName}`}
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default OrphanedAssetsPage;
