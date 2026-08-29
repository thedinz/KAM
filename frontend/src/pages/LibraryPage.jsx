import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ImportStatusPanel from '../components/ImportStatusPanel.jsx';
import ItemGrid from '../components/ItemGrid.jsx';
import LibraryToolbar from '../components/LibraryToolbar.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import {
  buildImportErrorsPath,
  clearImportErrorReport,
  saveImportErrorReport,
} from '../utils/importErrors.js';
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

const IMPORT_PREPARING_LABELS = [
  'Preparing import...',
  'Preparing import... This can take a minute for larger libraries.',
  'Preparing import... Contacting Plex.',
  'Preparing import... Please be patient while KAM gathers library items.',
  'Preparing import... Checking asset folders before import starts.',
];

const PRIMARY_IMPORT_OPTIONS = [
  { key: 'poster', label: 'Posters' },
  { key: 'background', label: 'Backgrounds' },
];

const TV_IMPORT_OPTIONS = [
  { key: 'seriesPoster', label: 'Series poster' },
  { key: 'seasonPosters', label: 'Season posters' },
  { key: 'seriesBackground', label: 'Series background' },
  { key: 'seasonBackgrounds', label: 'Season backgrounds' },
];

function isTelevisionLibraryName(library) {
  const lower = String(library || '').trim().toLowerCase();
  return lower.includes('tv') || lower.includes('show') || lower.includes('series');
}

function importModeForLibrary(library) {
  const lower = String(library || '').trim().toLowerCase();
  if (lower === 'collections') return 'collection';
  return isTelevisionLibraryName(library) ? 'tv' : 'movie';
}

function defaultImportOptionsForLibrary(library) {
  if (importModeForLibrary(library) === 'tv') {
    return {
      seriesPoster: true,
      seasonPosters: true,
      seriesBackground: true,
      seasonBackgrounds: true,
    };
  }
  return {
    poster: true,
    background: true,
  };
}

function normalizeImportOptionsForLibrary(library, options = {}) {
  const defaults = defaultImportOptionsForLibrary(library);
  return Object.fromEntries(
    Object.keys(defaults).map((key) => [key, options[key] ?? defaults[key]])
  );
}

function hasImportSelection(options) {
  return Object.values(options || {}).some(Boolean);
}

function importChoicesForLibrary(library) {
  return importModeForLibrary(library) === 'tv' ? TV_IMPORT_OPTIONS : PRIMARY_IMPORT_OPTIONS;
}

function ImportOptionsDialog({ isOpen, library, options, disabled, onChange, onClose, onSubmit }) {
  if (!isOpen) return null;

  const normalizedOptions = normalizeImportOptionsForLibrary(library, options);
  const choices = importChoicesForLibrary(library);
  const nothingSelected = !hasImportSelection(normalizedOptions);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (nothingSelected || disabled) return;
    onSubmit(normalizedOptions);
  };

  return (
    <div
      className="dialog-backdrop import-options-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        className="dialog-panel import-options-dlg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="importOptionsTitle"
        onSubmit={handleSubmit}
      >
        <div className="dialog-body">
          <div className="dialog-heading">
            <h2 id="importOptionsTitle">Import Assets</h2>
            <button
              type="button"
              className="dialog-close"
              onClick={onClose}
              aria-label="Close import options"
            >
              x
            </button>
          </div>
          <p className="import-options-summary">
            Existing selected assets in mapped Kometa folders will be overwritten.
          </p>
          <div className="import-options-list">
            {choices.map((choice) => (
              <label className="import-option-row" key={choice.key}>
                <input
                  type="checkbox"
                  checked={Boolean(normalizedOptions[choice.key])}
                  onChange={() =>
                    onChange({
                      ...normalizedOptions,
                      [choice.key]: !normalizedOptions[choice.key],
                    })
                  }
                />
                <span>{choice.label}</span>
              </label>
            ))}
          </div>
          <div className="import-options-actions">
            <button type="button" className="toolbar-secondary-action" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="toolbar-primary-action" disabled={nothingSelected || disabled}>
              Go
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function LibraryPage() {
  const navigate = useNavigate();
  const { library: routeLibraryParam = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeLibrary = String(routeLibraryParam || '').trim();
  const queryLibrary = searchParams.get('lib') || '';
  const urlLibrary = routeLibrary || queryLibrary;
  const lastUrlLibraryRef = useRef('');
  const pendingUrlLibraryRef = useRef('');
  const {
    library,
    setLibrary,
    page,
    setPage,
    totalPages,
    totalCount,
    notReadyCount,
    notReadyCountLoading,
    items,
    query,
    setQuery,
    sortMode,
    setSortMode,
    notReadyOnly,
    loading,
    error,
    reload,
    refreshNotReadyCount,
    fetchAllForLibrary,
    updateItem,
  } = useLibraryItemsContext();


  const [searchInput, setSearchInput] = useState(query || '');
  const searchTimerRef = useRef();
  const refreshedLibraryRef = useRef('');

  useEffect(() => setSearchInput(query || ''), [query]);

  useEffect(() => {
    const lib = (library || '').trim();
    if (!lib) return;
    if (refreshedLibraryRef.current === lib) return;
    refreshedLibraryRef.current = lib;
    refreshNotReadyCount?.(lib);
  }, [library, refreshNotReadyCount]);

  useEffect(() => {
    if (!urlLibrary) return;
    if (lastUrlLibraryRef.current === urlLibrary) return;

    lastUrlLibraryRef.current = urlLibrary;

    if (urlLibrary !== library) {
      pendingUrlLibraryRef.current = urlLibrary;
      setLibrary(urlLibrary);
    }
  }, [urlLibrary, library, setLibrary]);

  useEffect(() => {
    if (!library) return;
    if (pendingUrlLibraryRef.current) {
      if (pendingUrlLibraryRef.current !== library) return;
      pendingUrlLibraryRef.current = '';
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    if (routeLibrary) {
      nextSearchParams.delete('lib');
    } else {
      nextSearchParams.set('lib', library);
    }
    if (nextSearchParams.toString() !== searchParams.toString()) {
      setSearchParams(nextSearchParams, { replace: true });
    }
  }, [library, routeLibrary, searchParams, setSearchParams]);

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
  const [importOptionsOpen, setImportOptionsOpen] = useState(false);
  const [importOptions, setImportOptions] = useState(() => defaultImportOptionsForLibrary(library));
  const unresolvedCount = Number(notReadyCount) || 0;

  useEffect(() => {
    if (!importOptionsOpen) {
      setImportOptions(defaultImportOptionsForLibrary(library));
    }
  }, [importOptionsOpen, library]);

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

  const runImportAll = useCallback(async (requestedOptions = null) => {
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
    const selectedOptions = normalizeImportOptionsForLibrary(lib, requestedOptions || {});
    if (!hasImportSelection(selectedOptions)) {
      showStatus({ active: true, percent: 0, label: 'No asset types selected.', errors: [] });
      hideStatus(2000);
      return;
    }
    setIsImporting(true);
    const lower = lib.toLowerCase();
    const isCollections = lower === 'collections';
    const isTVLib = isTelevisionLibraryName(lib);
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
      const importable = readyItems;
      receipt.skipped = skipped.length;

      skipped.forEach((skip) => {
        const ratingKey = skip?.ratingKey ?? skip?.key ?? skip?.id;
        const context = {
          library: lib,
          title: skip?.title || skip?.name || '(Untitled)',
          folder: skip?.folderName || skip?.folder || skip?.name || skip?.title || '',
          ratingKey,
          type: skip?.type || '',
          year: skip?.year ?? null,
          isShow: isShowItem(skip, lib),
        };
        pushFailureEntry(failures, context, 'Item', 'Skipped (asset folder missing)');
      });

      if (!importable.length) {
        if (failures.length) {
          const count = failures.length;
          saveImportErrorReport(lib, failures, receipt);
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
      const skippedCount = skipped.length;
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
        const context = {
          library: lib,
          title,
          folder: folderName,
          ratingKey,
          type: item?.type || '',
          year: item?.year ?? null,
          isShow: isShowItem(item, lib),
        };

        try {
          if (isCollections) {
            const result = await importCollectionAssets(lib, ratingKey, folderName, selectedOptions);
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
            const showResult = await importShowPosterPreferShowEndpoint(lib, ratingKey, showFolder, selectedOptions);
            addImportResultToReceipt(receipt, showResult);
            collectResultFailures(failures, context, showResult);
            const wantsSeasonPosters = Boolean(selectedOptions.seasonPosters);
            const wantsSeasonBackgrounds = Boolean(selectedOptions.seasonBackgrounds);
            const hasSeasonPosterResults = Array.isArray(showResult.seasons) && showResult.seasons.length > 0;
            const hasSeasonBackgroundResults =
              Array.isArray(showResult.seasonBackgrounds) && showResult.seasonBackgrounds.length > 0;
            const needsSeasonFallback =
              seasonsMeta.length &&
              ((wantsSeasonPosters && !hasSeasonPosterResults) ||
                (wantsSeasonBackgrounds && !hasSeasonBackgroundResults));
            if (needsSeasonFallback) {
              const seasonResult = await importAllSeasons(lib, showFolder, seasonsMeta, ratingKey, {
                posters: wantsSeasonPosters && !hasSeasonPosterResults,
                backgrounds: wantsSeasonBackgrounds && !hasSeasonBackgroundResults,
              });
              addImportResultToReceipt(receipt, seasonResult);
              collectResultFailures(failures, context, seasonResult);
            }
          } else {
            const result = await importMovieAssets(lib, ratingKey, folderName, selectedOptions);
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
        saveImportErrorReport(lib, failures, receipt);
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
        clearImportErrorReport(lib);
      }
    } catch (err) {
      const message = `Import failed: ${err?.message || err}`;
      pushFailureEntry(failures, { library: lib, title: '', folder: '' }, 'Import', message);
      receipt.failed = Math.max(receipt.failed, failures.length);
      saveImportErrorReport(lib, failures, receipt);
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

  const handleImportAll = useCallback(() => {
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
    setImportOptions(defaultImportOptionsForLibrary(lib));
    setImportOptionsOpen(true);
  }, [library, showStatus, unresolvedCount]);

  const handleImportOptionsChange = useCallback((nextOptions) => {
    setImportOptions(nextOptions);
  }, []);

  const handleCloseImportOptions = useCallback(() => {
    setImportOptionsOpen(false);
  }, []);

  const handleStartSelectedImport = useCallback(
    (selectedOptions) => {
      const lib = (library || '').trim();
      const normalizedOptions = normalizeImportOptionsForLibrary(lib, selectedOptions);
      if (!hasImportSelection(normalizedOptions)) {
        showStatus({ active: true, percent: 0, label: 'No asset types selected.', errors: [] });
        hideStatus(2000);
        return;
      }
      setImportOptionsOpen(false);
      void runImportAll(normalizedOptions);
    },
    [hideStatus, library, runImportAll, showStatus]
  );

  const handleViewImportErrors = useCallback(() => {
    const lib = (library || '').trim();
    if (!lib || !Array.isArray(importState.errors) || !importState.errors.length) return;
    saveImportErrorReport(lib, importState.errors, importState.receipt);
    navigate(buildImportErrorsPath(lib));
  }, [importState.errors, importState.receipt, library, navigate]);

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
    : notReadyCountLoading
      ? 'Checking not-ready items before import is available.'
    : unresolvedCount > 0
      ? `Resolve or exclude ${unresolvedCount} not-ready item${unresolvedCount === 1 ? '' : 's'} before importing.`
      : normalizedLibrary.toLowerCase() === 'collections'
        ? 'Choose collection posters/backgrounds to import from Plex into Kometa asset folders.'
        : 'Choose which posters/backgrounds and TV season artwork to import from Plex into Kometa asset folders.';

  const scanDisabled = !library || loading;
  const scanTitle = library
    ? 'Scan the mapped asset folders and Plex library to find missing matches.'
    : 'Choose a library first.';

  return (
    <div>
      <header className="library-header">
        <div className="page-title-block">
          <span className="page-eyebrow">Media Library</span>
          <h1>{library || 'Library'}</h1>
          <p>{countLabel} <span aria-hidden="true">•</span> Kometa assets</p>
        </div>
        <div className="library-header-controls">
          <LibraryToolbar
            searchValue={searchInput}
            onSearchChange={handleSearchChange}
            sortValue={sortMode}
            onSortChange={setSortMode}
            onImportAll={handleImportAll}
            importDisabled={!library || isImporting || loading || notReadyCountLoading || unresolvedCount > 0}
            importTitle={importTooltip}
            onScanMapping={handleScanMapping}
            scanDisabled={scanDisabled}
            scanTitle={scanTitle}
          >
            <ImportStatusPanel
              active={importState.active}
              percent={importState.percent}
              label={importState.label}
              errors={importState.errors}
              receipt={importState.receipt}
              onViewErrors={handleViewImportErrors}
            />
          </LibraryToolbar>
        </div>
      </header>
      <main className="library-main">
        <ItemGrid
          items={items}
          library={library}
          onRequestFolder={handleRequestFolder}
          loading={loading}
          error={error}
        />
        <nav className="library-pagination-footer" aria-label="Library pages">
          <div className="pager" id="pager">
            <button
              type="button"
              onClick={handleFirst}
              disabled={(page || 1) <= 1}
              aria-label="First page"
              title="First page"
            >
              «
            </button>
            <button
              type="button"
              onClick={handlePrev}
              disabled={(page || 1) <= 1}
              aria-label="Previous page"
              title="Previous page"
            >
              ‹
            </button>
            <span aria-live="polite" id="pageInfo">
              Page {page || 1} / {totalPages || 1}
            </span>
            <button
              type="button"
              onClick={handleNext}
              disabled={(page || 1) >= (totalPages || 1)}
              aria-label="Next page"
              title="Next page"
            >
              ›
            </button>
            <button
              type="button"
              onClick={handleLast}
              disabled={(page || 1) >= (totalPages || 1)}
              aria-label="Last page"
              title="Last page"
            >
              »
            </button>
          </div>
        </nav>
      </main>
      <FolderFinderModal
        isOpen={folderModalOpen}
        item={folderModalItem}
        library={library}
        onClose={handleCloseFolderModal}
        onFolderAssigned={handleFolderAssigned}
      />
      <ImportOptionsDialog
        isOpen={importOptionsOpen}
        library={library}
        options={importOptions}
        disabled={isImporting}
        onChange={handleImportOptionsChange}
        onClose={handleCloseImportOptions}
        onSubmit={handleStartSelectedImport}
      />
    </div>
  );
}

export default LibraryPage;
