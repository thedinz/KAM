import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import ArtworkCard from '../components/ArtworkCard.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import { sendSavedArtworkToPlex, uploadStatusMessage } from '../utils/plexArtwork.js';
import { useTheme } from '../theme/ThemeProvider.jsx';
import { buildLibraryBackLink, detailBackLink } from '../utils/navigation.js';

const MISSING_FOLDER_MESSAGE = 'Create the Kometa asset folder first.';

function createOperation() {
  return {
    uploading: false,
    importing: false,
    success: false,
    error: null,
    lastAction: null,
  };
}

function seasonOperationKey(index, kind) {
  return `${String(index)}:${kind === 'background' ? 'background' : 'poster'}`;
}

function titleCardOperationKey(seasonIndex, episodeIndex) {
  return `${String(seasonIndex)}:${String(episodeIndex)}:title-card`;
}

function episodeCode(seasonIndex, episodeIndex) {
  return `S${String(seasonIndex).padStart(2, '0')}E${String(episodeIndex).padStart(2, '0')}`;
}

function ShowDetailPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const rawLibrary = params.library ?? searchParams.get('library') ?? searchParams.get('lib') ?? '';
  const rawRatingKey = params.ratingKey ?? searchParams.get('ratingKey') ?? searchParams.get('id') ?? '';
  const library = rawLibrary ? String(rawLibrary) : '';
  const ratingKey = rawRatingKey ? String(rawRatingKey) : '';

  const { excludeItem, includeItem, isItemExcluded, exclusionsLoading } = useTheme();
  const { reload: reloadLibraryItems } = useLibraryItemsContext();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [operations, setOperations] = useState({
    poster: createOperation(),
    background: createOperation(),
    mediux: createOperation(),
    seasons: {},
    titleCards: {},
  });
  const [expandedSeasons, setExpandedSeasons] = useState(() => new Set());
  const [exclusionPending, setExclusionPending] = useState(false);

  const mediuxZipInputRef = useRef(null);

  useEffect(() => {
    setDetail(null);
    setError(null);
    setStatusMessage('');
    setOperations({
      poster: createOperation(),
      background: createOperation(),
      mediux: createOperation(),
      seasons: {},
      titleCards: {},
    });
    setExpandedSeasons(new Set());
  }, [library, ratingKey]);

  const updateOperation = useCallback((kind, nextState) => {
    setOperations((prev) => {
      const prevState = prev[kind] ?? createOperation();
      const next = typeof nextState === 'function' ? nextState(prevState) : nextState;
      if (
        prevState.uploading === next.uploading &&
        prevState.importing === next.importing &&
        prevState.success === next.success &&
        prevState.error === next.error &&
        prevState.lastAction === next.lastAction
      ) {
        return prev;
      }
      return { ...prev, [kind]: next };
    });
  }, []);

  const updateSeasonOperation = useCallback((index, kind, nextState) => {
    const key = seasonOperationKey(index, kind);
    setOperations((prev) => {
      const current = prev.seasons?.[key] ?? createOperation();
      const next = typeof nextState === 'function' ? nextState(current) : nextState;
      if (
        current.uploading === next.uploading &&
        current.importing === next.importing &&
        current.success === next.success &&
        current.error === next.error &&
        current.lastAction === next.lastAction
      ) {
        return prev;
      }
      return {
        ...prev,
        seasons: { ...prev.seasons, [key]: next },
      };
    });
  }, []);

  const updateTitleCardOperation = useCallback((seasonIndex, episodeIndex, nextState) => {
    const key = titleCardOperationKey(seasonIndex, episodeIndex);
    setOperations((prev) => {
      const current = prev.titleCards?.[key] ?? createOperation();
      const next = typeof nextState === 'function' ? nextState(current) : nextState;
      if (
        current.uploading === next.uploading &&
        current.importing === next.importing &&
        current.success === next.success &&
        current.error === next.error &&
        current.lastAction === next.lastAction
      ) {
        return prev;
      }
      return {
        ...prev,
        titleCards: { ...prev.titleCards, [key]: next },
      };
    });
  }, []);

  const fetchDetails = useCallback(async () => {
    if (!library || !ratingKey) {
      setError('Missing library or rating key.');
      setLoading(false);
      setDetail(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const query = new URLSearchParams({
        library,
        ratingKey,
      });
      const response = await fetch(`/api/show?${query.toString()}`);
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      setDetail(data || null);
      if (typeof document !== 'undefined') {
        const titlePieces = [];
        if (data?.title) titlePieces.push(data.title);
        if (data?.year) titlePieces.push(`(${data.year})`);
        document.title = titlePieces.length ? `KAM • ${titlePieces.join(' ')}` : 'KAM • Show Details';
      }
      setStatusMessage((prev) => {
        if (!data?.folderExists) return MISSING_FOLDER_MESSAGE;
        if (prev && prev !== MISSING_FOLDER_MESSAGE) return prev;
        return '';
      });
      setOperations((prev) => {
        const seasonsMap = { ...(prev.seasons || {}) };
        const titleCardsMap = { ...(prev.titleCards || {}) };
        const nextKeys = new Set();
        const nextTitleCardKeys = new Set();
        (Array.isArray(data?.seasons) ? data.seasons : []).forEach((season) => {
          const key = season?.index != null ? seasonOperationKey(season.index, 'poster') : null;
          const backgroundKey = season?.index != null ? seasonOperationKey(season.index, 'background') : null;
          if (!key) return;
          nextKeys.add(key);
          nextKeys.add(backgroundKey);
          if (!seasonsMap[key]) {
            seasonsMap[key] = createOperation();
          }
          if (!seasonsMap[backgroundKey]) {
            seasonsMap[backgroundKey] = createOperation();
          }
          (Array.isArray(season?.episodes) ? season.episodes : []).forEach((episode) => {
            if (episode?.index == null) return;
            const titleCardKey = titleCardOperationKey(season.index, episode.index);
            nextTitleCardKeys.add(titleCardKey);
            if (!titleCardsMap[titleCardKey]) {
              titleCardsMap[titleCardKey] = createOperation();
            }
          });
        });
        Object.keys(seasonsMap).forEach((key) => {
          if (!nextKeys.has(key)) {
            delete seasonsMap[key];
          }
        });
        Object.keys(titleCardsMap).forEach((key) => {
          if (!nextTitleCardKeys.has(key)) {
            delete titleCardsMap[key];
          }
        });
        return {
          poster: prev.poster ?? createOperation(),
          background: prev.background ?? createOperation(),
          seasons: seasonsMap,
          titleCards: titleCardsMap,
        };
      });
    } catch (err) {
      const message = err?.message || String(err);
      setError(message);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [library, ratingKey]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  const folderExists = Boolean(detail?.folderExists);
  const folderName = detail?.folderName || '';
  const effectiveRatingKey = detail?.ratingKey != null ? String(detail.ratingKey) : ratingKey;

  const isExcluded = useMemo(() => {
    if (detail?.excluded != null) {
      return Boolean(detail.excluded);
    }
    if (!library || !effectiveRatingKey) {
      return false;
    }
    return isItemExcluded(library, effectiveRatingKey);
  }, [detail, isItemExcluded, library, effectiveRatingKey]);

  const exclusionBusy = exclusionPending || exclusionsLoading;

  const headerTitle = detail?.title || 'Show Details';
  const headerYear = detail?.year;

  useEffect(() => {
    if (!folderExists && mediuxZipInputRef.current) {
      mediuxZipInputRef.current.value = '';
    }
  }, [folderExists]);

  const showPosterExists = useMemo(() => {
    if (typeof detail?.posterExists === 'boolean') return detail.posterExists;
    return Boolean(detail?.posterUrl);
  }, [detail]);

  const showBackgroundExists = useMemo(() => {
    if (typeof detail?.backgroundExists === 'boolean') return detail.backgroundExists;
    return Boolean(detail?.backgroundUrl);
  }, [detail]);

  const showPosterImage = detail?.posterUrl || detail?.posterUrlPlex || detail?.plexPosterUrl || null;
  const showBackgroundImage = detail?.backgroundUrl || detail?.backgroundUrlPlex || detail?.plexBackgroundUrl || null;

  const backgroundOperation = operations.background ?? createOperation();
  const mediuxOperation = operations.mediux ?? createOperation();
  const mediuxImporting = Boolean(mediuxOperation.importing);
  const mediuxBusy = Boolean(mediuxOperation.uploading || mediuxOperation.importing);

  const seasons = useMemo(() => {
    if (!Array.isArray(detail?.seasons)) return [];
    const normalized = detail.seasons
      .filter((season) => season && season.index != null)
      .map((season) => {
        const idx = season.index;
        const title = season.title || `Season ${String(idx).padStart(2, '0')}`;
        const posterUrl = season.posterUrl || season.url || null;
        const plexPosterUrl = season.plexPosterUrl || season.urlPlex || null;
        const posterExists = typeof season.posterExists === 'boolean'
          ? season.posterExists
          : typeof season.exists === 'boolean'
            ? season.exists
          : Boolean(posterUrl && posterUrl.startsWith('/fileproxy'));
        const backgroundUrl = season.backgroundUrl || season.backgroundUrlPlex || null;
        const plexBackgroundUrl = season.plexBackgroundUrl || null;
        const backgroundExists = typeof season.backgroundExists === 'boolean'
          ? season.backgroundExists
          : Boolean(backgroundUrl && backgroundUrl.startsWith('/fileproxy'));
        const episodes = (Array.isArray(season.episodes) ? season.episodes : [])
          .filter((episode) => episode && episode.index != null)
          .map((episode) => {
            const episodeIndex = episode.index;
            const episodeTitle = episode.title || `Episode ${String(episodeIndex).padStart(2, '0')}`;
            const titleCardUrl = episode.titleCardUrl || episode.posterUrl || episode.url || null;
            const plexTitleCardUrl = episode.plexTitleCardUrl || episode.plexPosterUrl || episode.urlPlex || null;
            const titleCardExists = typeof episode.titleCardExists === 'boolean'
              ? episode.titleCardExists
              : typeof episode.exists === 'boolean'
                ? episode.exists
                : Boolean(titleCardUrl && titleCardUrl.startsWith('/fileproxy'));
            return {
              index: episodeIndex,
              seasonIndex: episode.seasonIndex ?? idx,
              title: episodeTitle,
              ratingKey: episode.ratingKey != null ? String(episode.ratingKey) : '',
              titleCardUrl,
              plexTitleCardUrl,
              titleCardExists,
            };
          })
          .sort((a, b) => {
            if (a.index === b.index) {
              return a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: 'base' });
            }
            return a.index - b.index;
          });
        return {
          index: idx,
          title,
          ratingKey: season.ratingKey != null ? String(season.ratingKey) : '',
          posterUrl,
          plexPosterUrl,
          posterExists,
          backgroundUrl,
          plexBackgroundUrl,
          backgroundExists,
          episodes,
        };
      });

    normalized.sort((a, b) => {
      if (a.index === b.index) {
        return a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: 'base' });
      }
      return a.index - b.index;
    });

    return normalized;
  }, [detail]);

  const toggleSeasonExpanded = useCallback((index) => {
    setExpandedSeasons((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const handleShowUpload = useCallback(
    async (kind, file) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        throw new Error(MISSING_FOLDER_MESSAGE);
      }
      const label = kind === 'background' ? 'background' : 'poster';
      updateOperation(kind, {
        uploading: true,
        importing: false,
        success: false,
        error: null,
        lastAction: 'upload',
      });
      setStatusMessage(`Uploading ${label}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      form.append('kind', kind);
      form.append('file', file);

      try {
        const response = await fetch('/api/upload_show', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateOperation(kind, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'upload',
        });
        setStatusMessage(uploadStatusMessage(data));
        if (kind === 'poster') {
          reloadLibraryItems();
        }
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateOperation(kind, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'upload',
        });
        setStatusMessage(message);
        throw err;
      }
    },
    [folderExists, library, folderName, effectiveRatingKey, fetchDetails, reloadLibraryItems, updateOperation]
  );

  const handleShowImport = useCallback(
    async (kind) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        return;
      }
      const label = kind === 'background' ? 'background' : 'poster';
      updateOperation(kind, {
        uploading: false,
        importing: true,
        success: false,
        error: null,
        lastAction: 'import',
      });
      setStatusMessage(`Importing ${label}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      const plexUrl =
        kind === 'background'
          ? detail?.plexBackgroundUrl || detail?.backgroundUrlPlex || null
          : detail?.plexPosterUrl || detail?.posterUrlPlex || null;
      if (plexUrl) {
        form.append('url', plexUrl);
      }
      const endpoint = kind === 'background' ? '/api/import/background' : '/api/import/poster';

      try {
        const response = await fetch(endpoint, { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok || !(data && data.ok)) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateOperation(kind, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'import',
        });
        setStatusMessage('Import complete.');
        if (kind === 'poster') {
          reloadLibraryItems();
        }
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateOperation(kind, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'import',
        });
        setStatusMessage(message);
      }
    },
    [folderExists, library, folderName, effectiveRatingKey, detail, fetchDetails, reloadLibraryItems, updateOperation]
  );

  const handleSeasonUpload = useCallback(
    async (index, kind, file, seasonRatingKey) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        throw new Error(MISSING_FOLDER_MESSAGE);
      }
      const idx = Number(index);
      const normalizedKind = kind === 'background' ? 'background' : 'poster';
      const description = normalizedKind === 'background' ? 'background' : 'poster';
      updateSeasonOperation(idx, normalizedKind, {
        uploading: true,
        importing: false,
        success: false,
        error: null,
        lastAction: 'upload',
      });
      setStatusMessage(`Uploading season ${String(index).padStart(2, '0')} ${description}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(index));
      form.append('kind', normalizedKind);
      if (seasonRatingKey) form.append('ratingKey', seasonRatingKey);
      form.append('file', file);

      try {
        const response = await fetch('/api/upload_season', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateSeasonOperation(idx, normalizedKind, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'upload',
        });
        setStatusMessage(uploadStatusMessage(data));
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateSeasonOperation(idx, normalizedKind, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'upload',
        });
        setStatusMessage(message);
        throw err;
      }
    },
    [folderExists, library, folderName, fetchDetails, updateSeasonOperation]
  );

  const handleSeasonImport = useCallback(
    async (index, kind, plexUrl) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        return;
      }
      const idx = Number(index);
      const normalizedKind = kind === 'background' ? 'background' : 'poster';
      const description = normalizedKind === 'background' ? 'background' : 'poster';
      updateSeasonOperation(idx, normalizedKind, {
        uploading: false,
        importing: true,
        success: false,
        error: null,
        lastAction: 'import',
      });
      setStatusMessage(`Importing season ${String(index).padStart(2, '0')} ${description}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(index));
      form.append('kind', normalizedKind);
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      if (plexUrl) form.append('url', plexUrl);

      try {
        const response = await fetch('/api/import/season', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok || !(data && (data.ok || data.path || data.src))) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateSeasonOperation(idx, normalizedKind, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'import',
        });
        setStatusMessage('Import complete.');
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateSeasonOperation(idx, normalizedKind, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'import',
        });
        setStatusMessage(message);
      }
    },
    [folderExists, library, folderName, effectiveRatingKey, fetchDetails, updateSeasonOperation]
  );

  const handleTitleCardUpload = useCallback(
    async (seasonIndex, episodeIndex, file, episodeRatingKey) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        throw new Error(MISSING_FOLDER_MESSAGE);
      }
      const seasonIdx = Number(seasonIndex);
      const episodeIdx = Number(episodeIndex);
      updateTitleCardOperation(seasonIdx, episodeIdx, {
        uploading: true,
        importing: false,
        success: false,
        error: null,
        lastAction: 'upload',
      });
      setStatusMessage(`Uploading ${episodeCode(seasonIdx, episodeIdx)} title card…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(seasonIdx));
      form.append('episode', String(episodeIdx));
      if (episodeRatingKey) form.append('ratingKey', episodeRatingKey);
      form.append('file', file);

      try {
        const response = await fetch('/api/upload_title_card', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateTitleCardOperation(seasonIdx, episodeIdx, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'upload',
        });
        setStatusMessage(uploadStatusMessage(data));
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateTitleCardOperation(seasonIdx, episodeIdx, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'upload',
        });
        setStatusMessage(message);
        throw err;
      }
    },
    [folderExists, library, folderName, fetchDetails, updateTitleCardOperation]
  );

  const handleSendToPlex = useCallback(
    async ({ kind = 'poster', ratingKey: targetRatingKey, season = null, episode = null }) => {
      const targetKind = kind === 'background' ? 'background' : 'poster';
      setStatusMessage('Sending artwork to Plex…');
      try {
        await sendSavedArtworkToPlex({
          library,
          folderName,
          ratingKey: targetRatingKey,
          kind: targetKind,
          season,
          episode,
        });
        setStatusMessage('Artwork sent to Plex.');
      } catch (err) {
        const message = err?.message || 'Failed to send artwork to Plex.';
        setStatusMessage(message);
        throw err;
      }
    },
    [library, folderName]
  );

  const handleTitleCardImport = useCallback(
    async (seasonIndex, episode) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        return;
      }
      const seasonIdx = Number(seasonIndex);
      const episodeIdx = Number(episode?.index);
      updateTitleCardOperation(seasonIdx, episodeIdx, {
        uploading: false,
        importing: true,
        success: false,
        error: null,
        lastAction: 'import',
      });
      setStatusMessage(`Importing ${episodeCode(seasonIdx, episodeIdx)} title card…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(seasonIdx));
      form.append('episode', String(episodeIdx));
      if (episode?.ratingKey) form.append('ratingKey', episode.ratingKey);
      if (episode?.plexTitleCardUrl) form.append('url', episode.plexTitleCardUrl);

      try {
        const response = await fetch('/api/import/title-card', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok || !(data && (data.ok || data.path || data.src))) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateTitleCardOperation(seasonIdx, episodeIdx, {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'import',
        });
        setStatusMessage('Import complete.');
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateTitleCardOperation(seasonIdx, episodeIdx, {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'import',
        });
        setStatusMessage(message);
      }
    },
    [folderExists, library, folderName, fetchDetails, updateTitleCardOperation]
  );

  const handleMediuxZipImport = useCallback(
    async (file) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        throw new Error(MISSING_FOLDER_MESSAGE);
      }

      updateOperation('mediux', {
        uploading: false,
        importing: true,
        success: false,
        error: null,
        lastAction: 'import',
      });
      setStatusMessage('Importing Mediux zip…');

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('file', file);

      try {
        const response = await fetch('/api/import/mediux-zip', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }

        const importedCount = Number(data?.importedCount ?? data?.imported?.length ?? 0);
        const replacedCount = Number(data?.replacedCount ?? 0);
        const skippedCount = Number(data?.skippedCount ?? data?.skipped?.length ?? 0);
        const errorCount = Number(data?.errorCount ?? data?.errors?.length ?? 0);
        if (!importedCount) {
          const firstError = Array.isArray(data?.errors) && data.errors[0]?.error ? data.errors[0].error : null;
          throw new Error(firstError || 'No recognizable Mediux assets found in that zip.');
        }

        updateOperation('mediux', {
          uploading: false,
          importing: false,
          success: true,
          error: null,
          lastAction: 'import',
        });
        const importedLabel = `${importedCount} Mediux asset${importedCount === 1 ? '' : 's'}`;
        const replacedLabel = replacedCount ? `, replaced ${replacedCount}` : '';
        const skippedLabel = skippedCount ? `, skipped ${skippedCount}` : '';
        const errorLabel = errorCount ? `, ${errorCount} failed` : '';
        setStatusMessage(`Imported ${importedLabel}${replacedLabel}${skippedLabel}${errorLabel}.`);
        reloadLibraryItems();
        await fetchDetails();
      } catch (err) {
        const message = err?.message || String(err);
        updateOperation('mediux', {
          uploading: false,
          importing: false,
          success: false,
          error: message,
          lastAction: 'import',
        });
        setStatusMessage(message);
        throw err;
      }
    },
    [folderExists, library, folderName, fetchDetails, reloadLibraryItems, updateOperation]
  );

  const handleExclude = useCallback(async () => {
    if (!library || !effectiveRatingKey) return;
    setExclusionPending(true);
    setStatusMessage('Excluding item…');
    try {
      await excludeItem({
        library,
        ratingKey: effectiveRatingKey,
        type: 'show',
        title: detail?.title || headerTitle,
        year: detail?.year,
      });
      setDetail((prev) => (prev ? { ...prev, excluded: true } : prev));
      setStatusMessage('Item excluded. Restore it from Settings → Exclusions.');
    } catch (err) {
      const message = err?.message || 'Failed to exclude item.';
      setStatusMessage(message);
    } finally {
      setExclusionPending(false);
    }
  }, [library, effectiveRatingKey, excludeItem, detail, headerTitle]);

  const handleInclude = useCallback(async () => {
    if (!library || !effectiveRatingKey) return;
    setExclusionPending(true);
    setStatusMessage('Including item…');
    try {
      await includeItem(library, effectiveRatingKey);
      setDetail((prev) => (prev ? { ...prev, excluded: false } : prev));
      setStatusMessage('Item included again.');
    } catch (err) {
      const message = err?.message || 'Failed to include item.';
      setStatusMessage(message);
    } finally {
      setExclusionPending(false);
    }
  }, [library, effectiveRatingKey, includeItem]);

  const backLink = detailBackLink(location, buildLibraryBackLink(library));
  const folderDisplay = folderName || 'Not assigned';

  const handleMediuxZipClick = () => {
    if (!folderExists || mediuxBusy) return;
    if (mediuxZipInputRef.current) {
      mediuxZipInputRef.current.value = '';
      mediuxZipInputRef.current.click();
    }
  };

  const handleMediuxZipChange = (event) => {
    if (!folderExists || mediuxBusy) return;
    const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
    if (!file) return;
    const result = handleMediuxZipImport(file);
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  };

  return (
    <div className="detail-page">
      <header>
        <Link className="btn" to={backLink}>
          ← Back
        </Link>
        <div className="detail-heading">
          <span className="page-eyebrow">Series artwork</span>
          <div className="detail-heading-title">
            <h1>{headerTitle}</h1>
            {headerYear ? <span className="detail-year">{headerYear}</span> : null}
          </div>
        </div>
        <span className="detail-header-gap" aria-hidden="true" />
        <button
          type="button"
          className={`detail-action-button ${
            isExcluded ? 'detail-action-button--include' : 'detail-action-button--exclude'
          }`}
          onClick={isExcluded ? handleInclude : handleExclude}
          disabled={exclusionBusy || !library || !effectiveRatingKey}
        >
          {exclusionBusy
            ? isExcluded
              ? 'Including…'
              : 'Excluding…'
            : isExcluded
            ? 'Include item'
            : 'Exclude item'}
        </button>
        <Link className="settings-link" to="/settings" aria-label="Open settings">
          <span aria-hidden="true">⚙</span>
        </Link>
      </header>
      <main className="detail-main">
        {loading ? (
          <div className="detail-container">
            <div className="status-text" aria-live="polite">
              Loading…
            </div>
          </div>
        ) : error ? (
          <div className="detail-container">
            <div className="status-text error" aria-live="polite">
              {error}
            </div>
            <button type="button" className="btn" onClick={fetchDetails}>
              Retry
            </button>
          </div>
        ) : detail ? (
          <div className="detail-container">
            {!folderExists ? (
              <div className="detail-warning" role="alert">
                <strong>✖</strong>
                <span>{MISSING_FOLDER_MESSAGE}</span>
              </div>
            ) : null}
            <div className="detail-asset-bar">
              <div className="detail-folder" aria-live="polite">
                Asset folder:
                <span className="detail-folder-name">{folderDisplay}</span>
              </div>
              <div className="detail-asset-actions">
                <input
                  ref={mediuxZipInputRef}
                  type="file"
                  accept=".zip,application/zip,application/x-zip-compressed"
                  className="asset-file-input"
                  aria-label="Mediux zip file"
                  disabled={!folderExists || mediuxBusy}
                  onChange={handleMediuxZipChange}
                />
                <button
                  type="button"
                  className="btn"
                  onClick={handleMediuxZipClick}
                  disabled={!folderExists || mediuxBusy}
                >
                  {mediuxImporting ? 'Importing Mediux zip…' : 'Import Mediux zip'}
                </button>
              </div>
            </div>
            <section className="asset-card-grid">
              <ArtworkCard
                label="Series Poster"
                variant="poster"
                exists={showPosterExists}
                imageUrl={showPosterImage}
                folderExists={folderExists}
                operation={operations.poster}
                onUpload={(file) => handleShowUpload('poster', file)}
                onImport={() => handleShowImport('poster')}
                onSendToPlex={() =>
                  handleSendToPlex({ kind: 'poster', ratingKey: effectiveRatingKey })
                }
              />
              <ArtworkCard
                label="Series Background"
                variant="landscape"
                exists={showBackgroundExists}
                imageUrl={showBackgroundImage}
                folderExists={folderExists}
                operation={backgroundOperation}
                onUpload={(file) => handleShowUpload('background', file)}
                onImport={() => handleShowImport('background')}
                onSendToPlex={() =>
                  handleSendToPlex({ kind: 'background', ratingKey: effectiveRatingKey })
                }
              />
            </section>
            <section className="detail-seasons">
              <h2 className="detail-section-title">Seasons</h2>
              {seasons.length ? (
                <div className="season-panel-grid">
                {seasons.map((season) => {
                  const isExpanded = expandedSeasons.has(season.index);
                  const showSeasonBackground = seasons.length > 1 || season.backgroundExists;
                  const posterOp = operations.seasons?.[seasonOperationKey(season.index, 'poster')] ?? createOperation();
                  const backgroundOp = operations.seasons?.[seasonOperationKey(season.index, 'background')] ?? createOperation();
                  return (
                    <article
                      className={`season-panel ${isExpanded ? 'is-expanded' : ''}`}
                      key={season.index}
                    >
                      <button
                        type="button"
                        className="season-summary-card"
                        aria-expanded={isExpanded}
                        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${season.title} assets`}
                        onClick={() => toggleSeasonExpanded(season.index)}
                      >
                        <div className="asset-image-wrapper asset-image-wrapper--poster season-summary-image">
                          {season.posterUrl ? (
                            <img className="asset-image" src={season.posterUrl} alt="" loading="lazy" />
                          ) : (
                            <div className="asset-placeholder" aria-hidden="true">
                              No preview available
                            </div>
                          )}
                        </div>
                        <span className="season-summary-body">
                          <span className="season-summary-title">{season.title}</span>
                          <span className={`asset-flag ${season.posterExists ? 'exists' : 'missing'}`}>
                            {season.posterExists ? 'exists' : 'missing'}
                          </span>
                          <span className="season-summary-count">
                            {season.episodes.length} title card{season.episodes.length === 1 ? '' : 's'}
                          </span>
                        </span>
                        <span className="season-summary-toggle" aria-hidden="true">
                          {isExpanded ? '-' : '+'}
                        </span>
                      </button>
                      {isExpanded ? (
                        <div className="season-detail-panel">
                          <div
                            className={`asset-card-grid asset-card-grid--season-detail ${
                              showSeasonBackground ? '' : 'asset-card-grid--season-detail-single'
                            }`}
                          >
                            <ArtworkCard
                              label={`${season.title} Poster`}
                              variant="poster"
                              exists={season.posterExists}
                              imageUrl={season.posterUrl}
                              folderExists={folderExists}
                              operation={posterOp}
                              onUpload={(file) =>
                                handleSeasonUpload(season.index, 'poster', file, season.ratingKey)
                              }
                              onImport={() => handleSeasonImport(season.index, 'poster', season.plexPosterUrl)}
                              onSendToPlex={
                                season.ratingKey
                                  ? () =>
                                      handleSendToPlex({
                                        kind: 'poster',
                                        ratingKey: season.ratingKey,
                                        season: season.index,
                                      })
                                  : undefined
                              }
                            />
                            {showSeasonBackground ? (
                              <ArtworkCard
                                label={`${season.title} Background`}
                                variant="landscape"
                                exists={season.backgroundExists}
                                imageUrl={season.backgroundUrl}
                                folderExists={folderExists}
                                operation={backgroundOp}
                                onUpload={(file) =>
                                  handleSeasonUpload(season.index, 'background', file, season.ratingKey)
                                }
                                onImport={() => handleSeasonImport(season.index, 'background', season.plexBackgroundUrl)}
                                onSendToPlex={
                                  season.ratingKey
                                    ? () =>
                                        handleSendToPlex({
                                          kind: 'background',
                                          ratingKey: season.ratingKey,
                                          season: season.index,
                                        })
                                    : undefined
                                }
                              />
                            ) : null}
                          </div>
                          <div className="season-title-card-group">
                            <h3 className="detail-subsection-title">Title Cards</h3>
                            {season.episodes.length ? (
                              <div className="asset-card-grid asset-card-grid--title-cards">
                                {season.episodes.map((episode) => {
                                  const titleCardOp =
                                    operations.titleCards?.[titleCardOperationKey(season.index, episode.index)] ??
                                    createOperation();
                                  return (
                                    <ArtworkCard
                                      key={episode.index}
                                      label={`${episodeCode(season.index, episode.index)} - ${episode.title}`}
                                      variant="landscape"
                                      exists={episode.titleCardExists}
                                      imageUrl={episode.titleCardUrl}
                                      folderExists={folderExists}
                                      operation={titleCardOp}
                                      onUpload={(file) =>
                                        handleTitleCardUpload(
                                          season.index,
                                          episode.index,
                                          file,
                                          episode.ratingKey
                                        )
                                      }
                                      onImport={() => handleTitleCardImport(season.index, episode)}
                                      onSendToPlex={
                                        episode.ratingKey
                                          ? () =>
                                              handleSendToPlex({
                                                kind: 'poster',
                                                ratingKey: episode.ratingKey,
                                                season: season.index,
                                                episode: episode.index,
                                              })
                                          : undefined
                                      }
                                    />
                                  );
                                })}
                              </div>
                            ) : (
                              <div className="status-text" aria-live="polite">
                                No episodes found for this season.
                              </div>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
                </div>
              ) : (
                <div className="status-text" aria-live="polite">
                  No seasons found for this series.
                </div>
              )}
            </section>
            <div className="detail-status" aria-live="polite">
              {statusMessage || '\u00a0'}
            </div>
          </div>
        ) : (
          <div className="detail-container">
            <div className="status-text" aria-live="polite">
              Details unavailable.
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default ShowDetailPage;
