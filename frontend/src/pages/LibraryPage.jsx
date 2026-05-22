import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import BrandLockup from '../components/BrandLockup.jsx';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ImportStatusPanel from '../components/ImportStatusPanel.jsx';
import ItemGrid from '../components/ItemGrid.jsx';
import LibraryToolbar from '../components/LibraryToolbar.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import { isShowItem } from '../utils/items.js';
import {
  addImportResultToReceipt,
  collectResultFailures,
  createImportReceipt,
  importAllSeasons,
  importCollectionAssets,
  importMovieAssets,
  importShowPosterPreferShowEndpoint,
  pushFailureEntry,
  summarizeImportResult,
} from '../utils/importers.js';
import { isCertainItemFolderMatch } from '../utils/mappingScan.js';

const IMPORT_PREPARING_LABELS = [
  'Preparing import...',
  'Preparing import... This can take a minute for larger libraries.',
  'Preparing import... Contacting Plex.',
  'Preparing import... Please be patient while KAM gathers library items.',
  'Preparing import... Checking asset folders before import starts.',
];

function LibraryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlLibrary = searchParams.get('lib') || '';
  const lastUrlLibraryRef = useRef(urlLibrary);
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
    loading,
    error,
    reload,
    fetchAllForLibrary,
    updateItem,
  } = useLibraryItemsContext();


  const [searchInput, setSearchInput] = useState(query || '');
  const searchTimerRef = useRef();

  useEffect(() => setSearchInput(query || ''), [query]);

  useEffect(() => {
    if (!urlLibrary) return;
    if (lastUrlLibraryRef.current === urlLibrary) return;

    lastUrlLibraryRef.current = urlLibrary;

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

  const handleViewNotReady = useCallback(() => {
    if (!library) return;
    const lib = library.trim();
    if (!lib) return;
    navigate(`/libraries/${encodeURIComponent(lib)}/not-ready`);
  }, [library, navigate]);

  const [importState, setImportState] = useState({
    active: false,
    percent: 0,
    label: '',
    errors: [],
    receipt: null,
  });
  const hideTimerRef = useRef();
  const preparingTimerRef = useRef();
  const [isImporting, setIsImporting] = useState(false);
  const unresolvedCount = Number(notReadyCount) || 0;

  const showStatus = useCallback(({ percent = 0, label = '', errors = [], receipt = null, active = true }) => {
    clearTimeout(hideTimerRef.current);
    setImportState({ active, percent, label, errors, receipt });
  }, []);

  const hideStatus = useCallback((delay = 0) => {
    clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => {
      setImportState({ active: false, percent: 0, label: '', errors: [], receipt: null });
    }, delay);
  }, []);

  useEffect(
    () => () => {
      clearTimeout(hideTimerRef.current);
      clearInterval(preparingTimerRef.current);
    },
    []
  );

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
    if (unresolvedCount > 0) {
      showStatus({
        active: true,
        percent: 0,
        label: `Import blocked. Resolve or exclude ${unresolvedCount} not-ready item${unresolvedCount === 1 ? '' : 's'} first.`,
        errors: [],
      });
      return;
    }
    const confirmed =
      typeof window === 'undefined' ||
      typeof window.confirm !== 'function' ||
      window.confirm(
        `Import all Plex artwork for ${lib}? Existing assets in mapped Kometa folders will be overwritten.`
      );
    if (!confirmed) {
      showStatus({ active: true, percent: 0, label: 'Import canceled.', errors: [] });
      hideStatus(2000);
      return;
    }
    setIsImporting(true);
    const lower = lib.toLowerCase();
    const isCollections = lower === 'collections';
    const isTVLib = lower.includes('tv');
    const failures = [];
    const receipt = createImportReceipt();
    let preparingLabelIndex = 0;

    const stopPreparingStatus = () => {
      if (preparingTimerRef.current) {
        clearInterval(preparingTimerRef.current);
        preparingTimerRef.current = null;
      }
    };

    const showPreparingStatus = () => {
      showStatus({
        active: true,
        percent: 0,
        label: IMPORT_PREPARING_LABELS[preparingLabelIndex],
        errors: [],
      });
      preparingLabelIndex = (preparingLabelIndex + 1) % IMPORT_PREPARING_LABELS.length;
    };

    stopPreparingStatus();
    showPreparingStatus();
    preparingTimerRef.current = setInterval(showPreparingStatus, 3500);

    try {
      const { items: allItems = [] } = await fetchAllForLibrary(lib, query, { notReadyOnly });
      stopPreparingStatus();
      const readyItems = allItems.filter((item) => item?.assetReady !== false);
      const skipped = allItems.filter((item) => item?.assetReady === false);
      const uncertain = isCollections
        ? []
        : readyItems.filter((item) => {
            const folderName = item?.folderName || item?.folder || '';
            return !isCertainItemFolderMatch(item, folderName);
          });
      const uncertainItems = new Set(uncertain);
      const importable = uncertain.length
        ? readyItems.filter((item) => !uncertainItems.has(item))
        : readyItems;
      receipt.skipped = skipped.length + uncertain.length;

      skipped.forEach((skip) => {
        const context = {
          library: lib,
          title: skip?.title || skip?.name || '(Untitled)',
          folder: skip?.folderName || skip?.folder || skip?.name || skip?.title || '',
        };
        pushFailureEntry(failures, context, 'Item', 'Skipped (asset folder missing)');
      });

      uncertain.forEach((skip) => {
        const context = {
          library: lib,
          title: skip?.title || skip?.name || '(Untitled)',
          folder: skip?.folderName || skip?.folder || '',
        };
        pushFailureEntry(failures, context, 'Item', 'Skipped (folder match needs manual confirmation)');
      });

      if (!importable.length) {
        if (failures.length) {
          const count = failures.length;
          showStatus({
            active: true,
            percent: 0,
            label: `Import skipped. ${count} item${count === 1 ? '' : 's'} need attention before bulk import.`,
            errors: failures.slice(),
            receipt: { ...receipt },
          });
        } else {
          showStatus({ active: true, percent: 0, label: 'Nothing to import.', errors: [] });
          hideStatus(2000);
        }
        return;
      }

      let processed = 0;
      const total = importable.length;
      const skippedCount = skipped.length + uncertain.length;
      const skipSuffix = skippedCount
        ? ` (skipping ${skippedCount} item${skippedCount === 1 ? '' : 's'} needing attention)`
        : '';

      const updateProgress = () => {
        const pct = total ? (processed / total) * 100 : 100;
        showStatus({
          active: true,
          percent: pct,
          label: `Importing assets from Plex… ${processed}/${total}${skipSuffix}`,
          errors: failures.slice(),
          receipt: { ...receipt },
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
            addImportResultToReceipt(receipt, result);
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
            addImportResultToReceipt(receipt, showResult);
            collectResultFailures(failures, context, showResult);
            const hasSeasonResults = Array.isArray(showResult.seasons) && showResult.seasons.length > 0;
            if (!hasSeasonResults && seasonsMeta.length) {
              const seasonResult = await importAllSeasons(lib, showFolder, seasonsMeta, ratingKey);
              addImportResultToReceipt(receipt, seasonResult);
              collectResultFailures(failures, context, seasonResult);
            }
          } else {
            const result = await importMovieAssets(lib, ratingKey, folderName);
            addImportResultToReceipt(receipt, result);
            collectResultFailures(failures, context, result);
          }
        } catch (err) {
          pushFailureEntry(failures, context, 'Import', err?.message || String(err));
        }

        processed += 1;
        updateProgress();
      }

      await reload();
      receipt.failed = Math.max(receipt.failed, failures.length);

      if (failures.length) {
        showStatus({
          active: true,
          percent: 100,
          label: summarizeImportResult(failures),
          errors: failures.slice(),
          receipt: { ...receipt },
        });
      } else {
        showStatus({
          active: true,
          percent: 100,
          label: 'Import complete.',
          errors: [],
          receipt: { ...receipt },
        });
      }
    } catch (err) {
      const message = `Import failed: ${err?.message || err}`;
      pushFailureEntry(failures, { library: lib, title: '', folder: '' }, 'Import', message);
      receipt.failed = Math.max(receipt.failed, failures.length);
      showStatus({
        active: true,
        percent: 0,
        label: message,
        errors: failures.slice(),
        receipt: { ...receipt },
      });
    } finally {
      stopPreparingStatus();
      setIsImporting(false);
    }
  }, [library, fetchAllForLibrary, query, notReadyOnly, reload, showStatus, hideStatus, unresolvedCount]);

  const handleScanMapping = useCallback(() => {
    if (!library) return;
    const lib = library.trim();
    if (!lib) return;
    navigate(`/libraries/${encodeURIComponent(lib)}/mapping`);
  }, [library, navigate]);

  const countLabel = useMemo(() => {
    const count = Number(totalCount) || 0;
    return `${count.toLocaleString()} item${count === 1 ? '' : 's'}`;
  }, [totalCount]);

  const normalizedLibrary = (library || '').trim();
  const importTooltip = !normalizedLibrary
    ? 'Choose a library first.'
    : unresolvedCount > 0
      ? `Resolve or exclude ${unresolvedCount} not-ready item${unresolvedCount === 1 ? '' : 's'} before importing.`
      : normalizedLibrary.toLowerCase() === 'collections'
        ? 'Import all collection posters/backgrounds from Plex into Kometa asset folders. Existing assets are overwritten.'
        : 'Import all posters/backgrounds and TV season artwork from Plex into Kometa asset folders. Existing assets are overwritten.';

  const notReadyButtonDisabled = !library || (Number(notReadyCount) || 0) <= 0;
  const scanDisabled = !library || loading;
  const scanTitle = library
    ? 'Scan the mapped asset folders and Plex library to find missing matches.'
    : 'Choose a library first.';

  return (
    <div>
      <header className="library-header">
        <h1 className="library-site-title">
          <BrandLockup />
        </h1>
        <div className="library-header-controls">
          <LibraryToolbar
            libraries={libraries}
            selectedLibrary={library || ''}
            onLibraryChange={setLibrary}
            searchValue={searchInput}
            onSearchChange={handleSearchChange}
            onImportAll={handleImportAll}
            importDisabled={!library || isImporting || loading || unresolvedCount > 0}
            importTitle={importTooltip}
            onScanMapping={handleScanMapping}
            scanDisabled={scanDisabled}
            scanTitle={scanTitle}
            page={page || 1}
            totalPages={totalPages || 1}
            onFirst={handleFirst}
            onPrev={handlePrev}
            onNext={handleNext}
            onLast={handleLast}
            countLabel={countLabel}
            onViewNotReady={handleViewNotReady}
            notReadyCount={notReadyCount}
            notReadyDisabled={notReadyButtonDisabled}
          >
            <ImportStatusPanel
              active={importState.active}
              percent={importState.percent}
              label={importState.label}
              errors={importState.errors}
              receipt={importState.receipt}
            />
          </LibraryToolbar>
          <Link className="settings-link" to="/settings" aria-label="Open settings">
            <span aria-hidden="true">⚙</span>
          </Link>
        </div>
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
