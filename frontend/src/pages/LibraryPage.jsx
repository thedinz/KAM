import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import FolderFinderModal from '../components/FolderFinderModal.jsx';
import ImportStatusPanel from '../components/ImportStatusPanel.jsx';
import ItemGrid from '../components/ItemGrid.jsx';
import LibraryToolbar from '../components/LibraryToolbar.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
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

  const [scanState, setScanState] = useState({ active: false, percent: 0, label: '', errors: [] });
  const scanHideTimerRef = useRef();
  const [isScanning, setIsScanning] = useState(false);

  const showScanStatus = useCallback(({ percent = 0, label = '', errors = [], active = true }) => {
    clearTimeout(scanHideTimerRef.current);
    setScanState({ active, percent, label, errors });
  }, []);

  const hideScanStatus = useCallback((delay = 0) => {
    clearTimeout(scanHideTimerRef.current);
    scanHideTimerRef.current = setTimeout(() => {
      setScanState({ active: false, percent: 0, label: '', errors: [] });
    }, delay);
  }, []);

  useEffect(() => () => clearTimeout(scanHideTimerRef.current), []);

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

  const handleScanMapping = useCallback(async () => {
    if (!library) return;
    const lib = library.trim();
    if (!lib) return;
    setIsScanning(true);
    showScanStatus({ active: true, percent: 0, label: 'Step 1/3: Scanning asset folders…', errors: [] });

    try {
      const STOPWORDS = new Set(['the', 'a', 'an', 'movie', 'film']);
      const normalizeTitle = (value) => {
        if (!value) return { key: '', year: null };
        const normalized = String(value).normalize('NFKC').replace(/[\u0000-\u001f]/g, '');
        const tokens = normalized
          .toLowerCase()
          .split(/[^0-9a-z]+/)
          .filter(Boolean)
          .filter((token) => !STOPWORDS.has(token));
        let year = null;
        if (tokens.length > 1 && /^\d{4}$/.test(tokens[tokens.length - 1])) {
          year = tokens.pop();
        }
        return { key: tokens.join(''), year };
      };
      const buildFolderIndex = (names) =>
        names
          .map((name) => ({ name, ...normalizeTitle(name) }))
          .filter((entry) => entry.key);
      const matchesFolder = (candidate, index) => {
        const { key, year } = normalizeTitle(candidate);
        if (!key) return false;
        for (const entry of index) {
          if (entry.key !== key) continue;
          if (year && entry.year && entry.year !== year) continue;
          return true;
        }
        for (const entry of index) {
          if (!entry.key) continue;
          if (!(entry.key.startsWith(key) || key.startsWith(entry.key))) continue;
          if (year && entry.year && entry.year !== year) continue;
          return true;
        }
        return false;
      };
      const fetchFolderNames = async (targetLibrary, { optional } = {}) => {
        const response = await fetch(`/api/asset-folders?library=${encodeURIComponent(targetLibrary)}`);
        const data = await safeJson(response);
        if (!response.ok) {
          if (optional && response.status === 404) {
            return [];
          }
          throw new Error(responseErrorMessage(response, data));
        }
        return Array.isArray(data?.items)
          ? data.items
              .filter((entry) => entry?.isDir)
              .map((entry) => String(entry?.name || '').trim())
              .filter(Boolean)
          : [];
      };
      const folderNames = await fetchFolderNames(lib);
      const collectionNames =
        lib.toLowerCase() === 'collections' ? [] : await fetchFolderNames('Collections', { optional: true });
      const folderIndex = buildFolderIndex([...folderNames, ...collectionNames]);

      showScanStatus({ active: true, percent: 33, label: 'Step 2/3: Scanning Plex library…', errors: [] });
      const { items: allItems = [] } = await fetchAllForLibrary(lib, '', { notReadyOnly: false });

      showScanStatus({ active: true, percent: 66, label: 'Step 3/3: Matching media to folders…', errors: [] });

      const unmatched = allItems.filter((item) => {
        const folderName = String(item?.folderName || item?.folder || '').trim();
        const title = String(item?.title || item?.name || '').trim();
        const year = item?.year != null ? String(item.year).trim() : '';
        const candidates = new Set();
        if (folderName) {
          candidates.add(folderName);
        }
        if (title) {
          candidates.add(title);
          if (year) {
            candidates.add(`${title} (${year})`);
          }
        }
        if (!candidates.size) {
          return true;
        }
        return !Array.from(candidates).some((candidate) => matchesFolder(candidate, folderIndex));
      });

      const unmatchedEntries = unmatched.map((item) => ({
        library: lib,
        title: item?.title || item?.name || '(Untitled)',
        folder: item?.folderName || item?.folder || '',
        message: 'No matching asset folder found',
      }));

      if (unmatchedEntries.length) {
        showScanStatus({
          active: true,
          percent: 100,
          label: `Scan complete. ${unmatchedEntries.length} item${
            unmatchedEntries.length === 1 ? '' : 's'
          } missing asset folders.`,
          errors: unmatchedEntries,
        });
      } else {
        showScanStatus({
          active: true,
          percent: 100,
          label: 'Scan complete. All items matched to asset folders.',
          errors: [],
        });
        hideScanStatus(2500);
      }
    } catch (err) {
      const message = `Scan failed: ${err?.message || err}`;
      showScanStatus({
        active: true,
        percent: 0,
        label: message,
        errors: [{ library: lib, title: '', folder: '', message }],
      });
    } finally {
      setIsScanning(false);
    }
  }, [library, fetchAllForLibrary, showScanStatus, hideScanStatus]);

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

  const notReadyButtonDisabled = !library || (Number(notReadyCount) || 0) <= 0;
  const scanDisabled = !library || isScanning || loading;
  const scanTitle = library
    ? 'Scan the mapped asset folders and Plex library to find missing matches.'
    : 'Choose a library first.';

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
          />
          <ImportStatusPanel
            active={scanState.active}
            percent={scanState.percent}
            label={scanState.label}
            errors={scanState.errors}
            errorHeading="Unmatched Items"
            errorNoun="unmatched item"
            modalId="mappingScanDialog"
          />
        </LibraryToolbar>
        <Link className="settings-link" to="/settings" aria-label="Open settings">
          <span aria-hidden="true">⚙</span>
        </Link>
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
