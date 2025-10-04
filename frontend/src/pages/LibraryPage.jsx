import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ImportStatusPanel from '../components/ImportStatusPanel.jsx';
import ItemGrid from '../components/ItemGrid.jsx';
import LibraryToolbar from '../components/LibraryToolbar.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { useTheme } from '../theme/ThemeProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import { isShowItem } from '../utils/items.js';
import {
  collectResultFailures,
  importAllSeasons,
  importCollectionAssets,
  importMovieAssets,
  importShowPosterPreferShowEndpoint,
  pushFailureEntry,
  summarizeImportResult,
} from '../utils/importers.js';

function LibraryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlLibrary = searchParams.get('lib') || '';
  const {
    libraries,
    library,
    setLibrary,
    page,
    setPage,
    totalPages,
    totalCount,
    notReadyCount,
    items,
    query,
    setQuery,
    notReadyOnly,
    setNotReadyOnly,
    loading,
    error,
    reload,
    fetchAllForLibrary,
    updateItem,
    notReadyCount,
  } = useLibraryItemsContext();

  const { toggleTheme } = useTheme();

  const [searchInput, setSearchInput] = useState(query || '');
  const searchTimerRef = useRef();

  useEffect(() => setSearchInput(query || ''), [query]);

  useEffect(() => {
    if (!urlLibrary) return;
    if (urlLibrary !== library) {
      setLibrary(urlLibrary);
    }
  }, [urlLibrary, library, setLibrary]);

  useEffect(() => {
    if (!library) return;
    setSearchParams({ lib: library });
  }, [library, setSearchParams]);

  useEffect(() => () => clearTimeout(searchTimerRef.current), []);

  const handleSearchChange = useCallback(
    (value) => {
      setSearchInput(value);
      clearTimeout(searchTimerRef.current);
      searchTimerRef.current = setTimeout(() => {
        const trimmed = value.trim();
        setQuery(trimmed);
      }, 300);
    },
    [setQuery]
  );

  const handleFirst = useCallback(() => setPage(1), [setPage]);
  const handlePrev = useCallback(() => setPage(Math.max(1, page - 1)), [setPage, page]);
  const handleNext = useCallback(() => setPage(Math.min(totalPages || 1, page + 1)), [setPage, page, totalPages]);
  const handleLast = useCallback(() => setPage(totalPages || 1), [setPage, totalPages]);

  const handleToggleNotReady = useCallback(() => {
    setNotReadyOnly((prev) => !prev);
  }, [setNotReadyOnly]);

  const [importState, setImportState] = useState({ active: false, percent: 0, label: '', errors: [] });
  const hideTimerRef = useRef();
  const [isImporting, setIsImporting] = useState(false);

  const showStatus = useCallback(({ percent = 0, label = '', errors = [], active = true }) => {
    clearTimeout(hideTimerRef.current);
    setImportState({ active, percent, label, errors });
  }, []);

  const hideStatus = useCallback((delay = 0) => {
    clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => {
      setImportState({ active: false, percent: 0, label: '', errors: [] });
    }, delay);
  }, []);

  useEffect(() => () => clearTimeout(hideTimerRef.current), []);

  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [folderModalItem, setFolderModalItem] = useState(null);

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
      }
      handleCloseFolderModal();
      if (!isImporting) {
        showStatus({ active: true, percent: 0, label: `Folder assigned: ${folderName}`, errors: [] });
        hideStatus(2000);
      }
      await reload();
    },
    [folderModalItem, updateItem, handleCloseFolderModal, isImporting, showStatus, hideStatus, reload]
  );

  const handleImportAll = useCallback(async () => {
    if (!library) return;
    const lib = library.trim();
    if (!lib) return;
    setIsImporting(true);
    const lower = lib.toLowerCase();
    const isCollections = lower === 'collections';
    const isTVLib = lower.includes('tv');
    const failures = [];

    showStatus({ active: true, percent: 0, label: 'Preparing import…', errors: [] });

    try {
      const { items: allItems = [] } = await fetchAllForLibrary(lib, query, { notReadyOnly });
      const importable = allItems.filter((item) => item?.assetReady !== false);
      const skipped = allItems.filter((item) => item?.assetReady === false);

      skipped.forEach((skip) => {
        const context = {
          library: lib,
          title: skip?.title || skip?.name || '(Untitled)',
          folder: skip?.folderName || skip?.folder || skip?.name || skip?.title || '',
        };
        pushFailureEntry(failures, context, 'Item', 'Skipped (asset folder missing)');
      });

      if (!importable.length) {
        if (failures.length) {
          const count = failures.length;
          showStatus({
            active: true,
            percent: 0,
            label: `Import skipped. ${count} item${count === 1 ? '' : 's'} missing asset folders.`,
            errors: failures.slice(),
          });
        } else {
          showStatus({ active: true, percent: 0, label: 'Nothing to import.', errors: [] });
          hideStatus(2000);
        }
        return;
      }

      let processed = 0;
      const total = importable.length;
      const skipSuffix = skipped.length
        ? ` (skipping ${skipped.length} not-ready item${skipped.length === 1 ? '' : 's'})`
        : '';

      const updateProgress = () => {
        const pct = total ? (processed / total) * 100 : 100;
        showStatus({
          active: true,
          percent: pct,
          label: `Importing assets from Plex… ${processed}/${total}${skipSuffix}`,
          errors: failures.slice(),
        });
      };

      updateProgress();

      for (const item of importable) {
        const title = item?.title || item?.name || '(Untitled)';
        let folderName = item?.folderName || '';
        if (!folderName && item?.assetReady !== false) {
          folderName = item?.folder || item?.name || item?.title || '';
        }
        const ratingKey = item?.ratingKey ?? item?.key ?? item?.id;
        const context = { library: lib, title, folder: folderName };

        try {
          if (isCollections) {
            const result = await importCollectionAssets(lib, ratingKey, folderName);
            collectResultFailures(failures, context, result);
          } else if (isTVLib || isShowItem(item, lib)) {
            let showData = null;
            if (ratingKey != null) {
              try {
                const url = `/api/show?library=${encodeURIComponent(lib)}&ratingKey=${encodeURIComponent(ratingKey)}`;
                const response = await fetch(url);
                const data = await safeJson(response);
                if (!response.ok) {
                  throw new Error(responseErrorMessage(response, data));
                }
                showData = data;
              } catch (err) {
                pushFailureEntry(failures, context, 'Show Lookup', err?.message || String(err));
              }
            }
            const showFolder = showData?.folderName || folderName;
            const seasonsMeta = Array.isArray(showData?.seasons) ? showData.seasons : [];
            const showResult = await importShowPosterPreferShowEndpoint(lib, ratingKey, showFolder);
            collectResultFailures(failures, context, showResult);
            const hasSeasonResults = Array.isArray(showResult.seasons) && showResult.seasons.length > 0;
            if (!hasSeasonResults && seasonsMeta.length) {
              const seasonResult = await importAllSeasons(lib, showFolder, seasonsMeta, ratingKey);
              collectResultFailures(failures, context, seasonResult);
            }
          } else {
            const result = await importMovieAssets(lib, ratingKey, folderName);
            collectResultFailures(failures, context, result);
          }
        } catch (err) {
          pushFailureEntry(failures, context, 'Import', err?.message || String(err));
        }

        processed += 1;
        updateProgress();
      }

      await reload();

      if (failures.length) {
        showStatus({ active: true, percent: 100, label: summarizeImportResult(failures), errors: failures.slice() });
      } else {
        showStatus({ active: true, percent: 100, label: 'Import complete.', errors: [] });
        hideStatus(2500);
      }
    } catch (err) {
      const message = `Import failed: ${err?.message || err}`;
      pushFailureEntry(failures, { library: lib, title: '', folder: '' }, 'Import', message);
      showStatus({ active: true, percent: 0, label: message, errors: failures.slice() });
    } finally {
      setIsImporting(false);
    }
  }, [library, fetchAllForLibrary, query, notReadyOnly, reload, showStatus, hideStatus]);

  const countLabel = useMemo(() => {
    const count = Number(totalCount) || 0;
    return `${count.toLocaleString()} item${count === 1 ? '' : 's'}`;
  }, [totalCount]);

  const normalizedLibrary = (library || '').trim();
  const importTooltip = normalizedLibrary
    ? normalizedLibrary.toLowerCase() === 'collections'
      ? 'Import all collection posters/backgrounds from Plex into Kometa asset folders'
      : 'Import all posters/backgrounds (and TV seasons) from Plex into Kometa asset folders'
    : 'Choose a library first.';

  const notReadyControl = useMemo(() => {
    if (!library && !notReadyOnly) return null;
    const disabled = !library || (!notReadyCount && !notReadyOnly);
    const label = `Show items missing asset folders (${notReadyCount})`;
    return (
      <button
        type="button"
        className={`ready-badge not-ready${notReadyOnly ? ' active' : ''}`}
        onClick={handleToggleNotReady}
        aria-pressed={notReadyOnly}
        disabled={disabled}
        title={label}
        data-active={notReadyOnly || undefined}
      >
        Not Ready {notReadyCount}
      </button>
    );
  }, [library, notReadyCount, notReadyOnly, handleToggleNotReady]);

  return (
    <div>
      <header>
        <h1>KAM</h1>
        <LibraryToolbar
          libraries={libraries}
          selectedLibrary={library || ''}
          onLibraryChange={setLibrary}
          searchValue={searchInput}
          onSearchChange={handleSearchChange}
          onImportAll={handleImportAll}
          importDisabled={!library || isImporting || loading}
          importTitle={importTooltip}
          page={page || 1}
          totalPages={totalPages || 1}
          onFirst={handleFirst}
          onPrev={handlePrev}
          onNext={handleNext}
          onLast={handleLast}
          countLabel={countLabel}
          notReadyControl={notReadyControl}
        >
          <ImportStatusPanel
            active={importState.active}
            percent={importState.percent}
            label={importState.label}
            errors={importState.errors}
          />
        </LibraryToolbar>
        <button type="button" className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
          🌓
        </button>
      </header>
      <main>
        <ItemGrid
          items={items}
          library={library}
          onRequestFolder={handleRequestFolder}
          loading={loading}
          error={error}
        />
      </main>
      <FolderFinderModal
        isOpen={folderModalOpen}
        item={folderModalItem}
        library={library}
        onClose={handleCloseFolderModal}
        onFolderAssigned={handleFolderAssigned}
      />
    </div>
  );
}

export default LibraryPage;
