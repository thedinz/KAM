import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';

const BATCH_RESOLUTION_KEY = '__all__';

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

function initialChoices(groups) {
  return Object.fromEntries(groups.map((group) => [
    group.ratingKey,
    group.activeFolderName || group.folders?.[0]?.folderName || '',
  ]));
}

function DuplicateFoldersPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { library: libraryParam } = useParams();
  const targetLibrary = libraryParam ? decodeURIComponent(libraryParam) : '';
  const cleanupScope = new URLSearchParams(location.search).get('scope') === 'collections'
    ? 'collections'
    : 'assets';
  const collectionScope = cleanupScope === 'collections';
  const { library, setLibrary, reload } = useLibraryItemsContext();
  const [groups, setGroups] = useState([]);
  const [root, setRoot] = useState('');
  const [choices, setChoices] = useState({});
  const [loading, setLoading] = useState(false);
  const [resolvingKey, setResolvingKey] = useState('');
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const stagedSelections = useMemo(() => groups
    .map((group) => ({
      ratingKey: group.ratingKey,
      keepFolderName: choices[group.ratingKey],
    }))
    .filter((selection) => selection.keepFolderName), [groups, choices]);

  const stagedDeleteCount = useMemo(() => groups.reduce(
    (total, group) => total + Math.max(0, (group.folders?.length || 0) - 1),
    0
  ), [groups]);

  useEffect(() => {
    if (targetLibrary && targetLibrary !== library) setLibrary(targetLibrary);
  }, [targetLibrary, library, setLibrary]);

  const fetchDuplicates = useCallback(async () => {
    if (!targetLibrary) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ library: targetLibrary, scope: cleanupScope });
      const response = await fetch(`/api/duplicate-folders?${params.toString()}`);
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      const nextGroups = Array.isArray(data?.groups) ? data.groups : [];
      setGroups(nextGroups);
      setRoot(data?.root || '');
      setChoices((previous) => ({ ...initialChoices(nextGroups), ...Object.fromEntries(
        nextGroups
          .filter((group) => group.folders?.some((folder) => folder.folderName === previous[group.ratingKey]))
          .map((group) => [group.ratingKey, previous[group.ratingKey]])
      ) }));
    } catch (err) {
      setGroups([]);
      setError(err?.message || 'Failed to scan duplicate folders.');
    } finally {
      setLoading(false);
    }
  }, [targetLibrary, cleanupScope]);

  useEffect(() => {
    fetchDuplicates();
  }, [fetchDuplicates]);

  const resolveGroup = useCallback(async (group) => {
    const keepFolderName = choices[group.ratingKey];
    if (!keepFolderName || resolvingKey) return;
    const deleteCount = Math.max(0, group.folders.length - 1);
    const selectedFolder = group.folders.find((folder) => folder.folderName === keepFolderName);
    const assignmentMessage = selectedFolder && !selectedFolder.isActive
      ? ` KAM will switch this asset to “${keepFolderName}” before deleting the old folder.`
      : '';
    const confirmed = window.confirm(
      `Keep “${keepFolderName}” for ${group.title} and permanently delete the other ${deleteCount} asset ${deleteCount === 1 ? 'folder' : 'folders'} and everything inside?${assignmentMessage} This cannot be undone.`
    );
    if (!confirmed) return;

    setResolvingKey(group.ratingKey);
    setError('');
    setStatus(`Rechecking ${group.title} before deleting duplicate folders…`);
    try {
      const response = await fetch('/api/duplicate-folders/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          library: targetLibrary,
          scope: cleanupScope,
          ratingKey: group.ratingKey,
          keepFolderName,
        }),
      });
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      await fetchDuplicates();
      reload();
      const deleted = Array.isArray(data?.deleted) ? data.deleted : [];
      const failures = Array.isArray(data?.errors) ? data.errors : [];
      const keptFolderName = data?.keptFolderName || keepFolderName;
      const assignmentMessage = data?.folderAssignmentChanged
        ? ` KAM now uses ${keptFolderName}.`
        : '';
      setStatus(`Kept ${keptFolderName} and deleted ${deleted.length} duplicate ${deleted.length === 1 ? 'folder' : 'folders'}.${assignmentMessage}`);
      if (failures.length) {
        setError(failures.map((entry) => `${entry.folderName}: ${entry.error}`).join(' '));
      }
    } catch (err) {
      setStatus('');
      setError(err?.message || 'Failed to resolve duplicate folders.');
    } finally {
      setResolvingKey('');
    }
  }, [choices, resolvingKey, targetLibrary, cleanupScope, fetchDuplicates, reload]);

  const resolveAllGroups = useCallback(async () => {
    if (
      resolvingKey
      || !stagedSelections.length
      || stagedSelections.length !== groups.length
    ) return;

    const assetCount = stagedSelections.length;
    const confirmed = window.confirm(
      `Process all ${assetCount} ${assetCount === 1 ? 'asset' : 'assets'} and permanently delete ${stagedDeleteCount} unselected duplicate ${stagedDeleteCount === 1 ? 'folder' : 'folders'} and everything inside? KAM will switch to any newly selected folder before deleting the old one. This cannot be undone.`
    );
    if (!confirmed) return;

    setResolvingKey(BATCH_RESOLUTION_KEY);
    setError('');
    setStatus(`Rechecking and processing ${assetCount} ${assetCount === 1 ? 'asset' : 'assets'}…`);
    try {
      const response = await fetch('/api/duplicate-folders/resolve-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          library: targetLibrary,
          scope: cleanupScope,
          selections: stagedSelections,
        }),
      });
      const data = await safeJson(response);
      if (!response.ok) throw new Error(responseErrorMessage(response, data));
      await fetchDuplicates();
      reload();

      const processedCount = Number(data?.processedCount) || 0;
      const deletedCount = Number(data?.deletedCount) || 0;
      const changedCount = Number(data?.folderAssignmentsChanged) || 0;
      const resultErrors = (Array.isArray(data?.results) ? data.results : [])
        .flatMap((result) => (Array.isArray(result?.errors) ? result.errors : [])
          .map((entry) => `${result.keptFolderName}: ${entry.folderName}: ${entry.error}`));
      const failures = (Array.isArray(data?.failures) ? data.failures : [])
        .map((entry) => `${entry.keepFolderName}: ${entry.error}`);

      setStatus(
        `Processed ${processedCount} ${processedCount === 1 ? 'asset' : 'assets'} and deleted ${deletedCount} duplicate ${deletedCount === 1 ? 'folder' : 'folders'}.`
        + (changedCount ? ` Switched KAM to ${changedCount} newly selected ${changedCount === 1 ? 'folder' : 'folders'}.` : '')
      );
      if (resultErrors.length || failures.length) {
        setError([...resultErrors, ...failures].join(' '));
      }
    } catch (err) {
      setStatus('');
      setError(err?.message || 'Failed to process duplicate folders.');
    } finally {
      setResolvingKey('');
    }
  }, [
    resolvingKey,
    stagedSelections,
    stagedDeleteCount,
    groups.length,
    targetLibrary,
    cleanupScope,
    fetchDuplicates,
    reload,
  ]);

  const backHref = useMemo(
    () => (targetLibrary
      ? `/libraries/${encodeURIComponent(targetLibrary)}${collectionScope ? '/collections' : ''}`
      : '/libraries'),
    [targetLibrary, collectionScope]
  );

  return (
    <div>
      <header className="not-ready-header orphaned-assets-header">
        <div className="not-ready-heading">
          <button type="button" className="back-button" onClick={() => navigate(backHref)}>← Back</button>
          <div>
            <span className="page-eyebrow">{collectionScope ? 'Collections cleanup' : 'Library cleanup'}</span>
            <h1>Duplicate Folders</h1>
            <p>
              Library assets with multiple folders that match known title, year, and edition variations.
              Choose the folder to keep for each asset, then process them individually or all at once.
              If you keep a folder KAM is not currently using, KAM switches to it before removing the others.
            </p>
          </div>
        </div>
        <div className="not-ready-meta">
          <span className="badge-label">{groups.length.toLocaleString()} assets</span>
          <button type="button" onClick={fetchDuplicates} disabled={loading || Boolean(resolvingKey)}>
            {loading ? 'Scanning…' : 'Scan again'}
          </button>
        </div>
      </header>

      <main className="orphaned-assets-page duplicate-folders-page">
        {root ? <p className="orphaned-assets-root" title={root}>Asset root: <code>{root}</code></p> : null}
        {!loading && groups.length ? (
          <div className="duplicate-folders-batch-toolbar">
            <div>
              <strong>{stagedSelections.length.toLocaleString()} of {groups.length.toLocaleString()} assets ready</strong>
              <span>Review each retained folder, then apply every staged choice together.</span>
            </div>
            <button
              type="button"
              className="duplicate-folder-resolve duplicate-folder-resolve-all"
              onClick={resolveAllGroups}
              disabled={Boolean(resolvingKey) || stagedSelections.length !== groups.length}
            >
              {resolvingKey === BATCH_RESOLUTION_KEY
                ? 'Processing all…'
                : `Process all ${groups.length.toLocaleString()} ${groups.length === 1 ? 'asset' : 'assets'}`}
            </button>
          </div>
        ) : null}
        {status ? <div className="success-state orphaned-assets-message" role="status">{status}</div> : null}
        {error ? <div className="error-banner" role="alert">{error}</div> : null}
        {loading ? <div className="loading-state">Matching Plex assets against every asset folder…</div> : null}
        {!loading && !error && !groups.length ? (
          <div className="empty-state">
            <div className="orphaned-assets-empty-copy">
              <strong>No duplicate asset folders</strong>
              <span>Each matched asset currently has one asset folder.</span>
            </div>
          </div>
        ) : null}

        {!loading && groups.length ? (
          <div className="duplicate-folder-groups" aria-live="polite">
            {groups.map((group) => (
              <section className="duplicate-folder-group" key={group.ratingKey}>
                <div className="duplicate-folder-heading">
                  <div>
                    <span className="page-eyebrow">{group.folders.length} matching folders</span>
                    <h2>{group.title}{group.year ? <span> ({group.year})</span> : null}</h2>
                  </div>
                  <button
                    type="button"
                    className="duplicate-folder-resolve"
                    onClick={() => resolveGroup(group)}
                    disabled={Boolean(resolvingKey) || !choices[group.ratingKey]}
                  >
                    {resolvingKey === group.ratingKey ? 'Rechecking…' : 'Keep selected folder'}
                  </button>
                </div>
                <div className="duplicate-folder-options">
                  {group.folders.map((folder) => {
                    const selected = choices[group.ratingKey] === folder.folderName;
                    return (
                      <label className={`duplicate-folder-option${selected ? ' is-selected' : ''}`} key={folder.folderName}>
                        <input
                          type="radio"
                          name={`duplicate-${group.ratingKey}`}
                          checked={selected}
                          onChange={() => setChoices((previous) => ({ ...previous, [group.ratingKey]: folder.folderName }))}
                          disabled={Boolean(resolvingKey)}
                        />
                        <span className="orphaned-asset-preview">
                          {folder.posterUrl ? <img src={folder.posterUrl} alt="" loading="lazy" /> : <span aria-hidden="true">No poster</span>}
                        </span>
                        <span className="duplicate-folder-copy">
                          <strong title={folder.folderName}>{folder.folderName}</strong>
                          <span>{Number(folder.assetCount || 0).toLocaleString()} files <span aria-hidden="true">•</span> {formatBytes(folder.sizeBytes)}</span>
                          {folder.isActive ? <em>Currently used by KAM</em> : null}
                          {selected && !folder.isActive ? <em className="will-use">KAM will switch to this folder</em> : null}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default DuplicateFoldersPage;
