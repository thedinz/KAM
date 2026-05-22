import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import ArtworkCard from '../components/ArtworkCard.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';
import { useTheme } from '../theme/ThemeProvider.jsx';

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

function ShowDetailPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const rawLibrary = params.library ?? searchParams.get('library') ?? searchParams.get('lib') ?? '';
  const rawRatingKey = params.ratingKey ?? searchParams.get('ratingKey') ?? searchParams.get('id') ?? '';
  const library = rawLibrary ? String(rawLibrary) : '';
  const ratingKey = rawRatingKey ? String(rawRatingKey) : '';

  const { excludeItem, includeItem, isItemExcluded, exclusionsLoading } = useTheme();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [operations, setOperations] = useState({
    poster: createOperation(),
    background: createOperation(),
    seasons: {},
  });
  const [exclusionPending, setExclusionPending] = useState(false);

  const backgroundInputRef = useRef(null);

  useEffect(() => {
    setDetail(null);
    setError(null);
    setStatusMessage('');
    setOperations({ poster: createOperation(), background: createOperation(), seasons: {} });
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
        const nextKeys = new Set();
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
        });
        Object.keys(seasonsMap).forEach((key) => {
          if (!nextKeys.has(key)) {
            delete seasonsMap[key];
          }
        });
        return {
          poster: prev.poster ?? createOperation(),
          background: prev.background ?? createOperation(),
          seasons: seasonsMap,
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
    if (!folderExists && backgroundInputRef.current) {
      backgroundInputRef.current.value = '';
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
  const backgroundUploading = Boolean(backgroundOperation.uploading);
  const backgroundImporting = Boolean(backgroundOperation.importing);
  const backgroundBusy = backgroundUploading || backgroundImporting;
  const backgroundStatus = (() => {
    if (backgroundOperation.error) {
      return { text: backgroundOperation.error, className: 'status-text error' };
    }
    if (backgroundOperation.success) {
      const label = backgroundOperation.lastAction === 'upload' ? 'Upload complete.' : 'Import complete.';
      return { text: label, className: 'status-text success' };
    }
    if (backgroundUploading) {
      return { text: 'Uploading…', className: 'status-text' };
    }
    if (backgroundImporting) {
      return { text: 'Importing…', className: 'status-text' };
    }
    return { text: '\u00a0', className: 'status-text' };
  })();

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
        return {
          index: idx,
          title,
          posterUrl,
          plexPosterUrl,
          posterExists,
          backgroundUrl,
          plexBackgroundUrl,
          backgroundExists,
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
        setStatusMessage('Upload complete.');
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
    [folderExists, library, folderName, fetchDetails, updateOperation]
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
    [folderExists, library, folderName, effectiveRatingKey, detail, fetchDetails, updateOperation]
  );

  const handleSeasonUpload = useCallback(
    async (index, kind, file) => {
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
        setStatusMessage('Upload complete.');
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

  const backLink = library ? `/libraries?lib=${encodeURIComponent(library)}` : '/libraries';
  const folderDisplay = folderName || 'Not assigned';

  const handleBackgroundUploadClick = () => {
    if (!folderExists || backgroundBusy) return;
    if (backgroundInputRef.current) {
      backgroundInputRef.current.value = '';
      backgroundInputRef.current.click();
    }
  };

  const handleBackgroundFileChange = (event) => {
    if (!folderExists || backgroundBusy) return;
    const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
    if (!file) return;
    const result = handleShowUpload('background', file);
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  };

  const handleBackgroundImportClick = () => {
    if (!folderExists || backgroundBusy) return;
    const result = handleShowImport('background');
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
        <h1>{headerTitle}</h1>
        {headerYear ? <span className="detail-year">({headerYear})</span> : null}
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
            <section className="detail-hero">
              <div className="detail-hero-image">
                {showBackgroundImage ? (
                  <img className="detail-hero-image-src" src={showBackgroundImage} alt="Series background" loading="lazy" />
                ) : (
                  <div className="detail-hero-placeholder" aria-hidden="true">
                    No background available
                  </div>
                )}
              </div>
              <div className="detail-hero-body">
                <div className="detail-hero-header">
                  <span className="detail-hero-title">Background</span>
                  <span className={`asset-flag ${showBackgroundExists ? 'exists' : 'missing'}`}>
                    {showBackgroundExists ? 'exists' : 'missing'}
                  </span>
                </div>
                <div className="detail-hero-actions">
                  <input
                    ref={backgroundInputRef}
                    type="file"
                    accept="image/*"
                    className="asset-file-input"
                    disabled={!folderExists || backgroundBusy}
                    onChange={handleBackgroundFileChange}
                  />
                  <button
                    type="button"
                    className="btn"
                    onClick={handleBackgroundUploadClick}
                    disabled={!folderExists || backgroundBusy}
                  >
                    {backgroundUploading ? 'Uploading…' : 'Upload'}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={handleBackgroundImportClick}
                    disabled={!folderExists || backgroundBusy}
                  >
                    {backgroundImporting ? 'Importing…' : 'Import'}
                  </button>
                </div>
                <div className={backgroundStatus.className} aria-live="polite">
                  {backgroundStatus.text}
                </div>
              </div>
            </section>
            {!folderExists ? (
              <div className="detail-warning" role="alert">
                <strong>✖</strong>
                <span>{MISSING_FOLDER_MESSAGE}</span>
              </div>
            ) : null}
            <div className="detail-folder" aria-live="polite">
              Asset folder:
              <span className="detail-folder-name">{folderDisplay}</span>
            </div>
            <section className="detail-series-cards">
              <h2 className="detail-section-title">Series &amp; Seasons</h2>
              <div className="asset-card-grid asset-card-grid--seasons">
                <ArtworkCard
                  label="Series Poster"
                  variant="poster"
                  exists={showPosterExists}
                  imageUrl={showPosterImage}
                  folderExists={folderExists}
                  operation={operations.poster}
                  onUpload={(file) => handleShowUpload('poster', file)}
                  onImport={() => handleShowImport('poster')}
                />
                {seasons.map((season) => {
                  const posterOp = operations.seasons?.[seasonOperationKey(season.index, 'poster')] ?? createOperation();
                  const backgroundOp = operations.seasons?.[seasonOperationKey(season.index, 'background')] ?? createOperation();
                  return (
                    <Fragment key={season.index}>
                      <ArtworkCard
                        label={`${season.title} Poster`}
                        variant="poster"
                        exists={season.posterExists}
                        imageUrl={season.posterUrl}
                        folderExists={folderExists}
                        operation={posterOp}
                        onUpload={(file) => handleSeasonUpload(season.index, 'poster', file)}
                        onImport={() => handleSeasonImport(season.index, 'poster', season.plexPosterUrl)}
                      />
                      <ArtworkCard
                        label={`${season.title} Background`}
                        variant="landscape"
                        exists={season.backgroundExists}
                        imageUrl={season.backgroundUrl}
                        folderExists={folderExists}
                        operation={backgroundOp}
                        onUpload={(file) => handleSeasonUpload(season.index, 'background', file)}
                        onImport={() => handleSeasonImport(season.index, 'background', season.plexBackgroundUrl)}
                      />
                    </Fragment>
                  );
                })}
              </div>
              {seasons.length ? null : (
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
