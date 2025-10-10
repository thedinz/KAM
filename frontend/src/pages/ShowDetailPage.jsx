import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import ArtworkCard from '../components/ArtworkCard.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';

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

function ShowDetailPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const rawLibrary = params.library ?? searchParams.get('library') ?? searchParams.get('lib') ?? '';
  const rawRatingKey = params.ratingKey ?? searchParams.get('ratingKey') ?? searchParams.get('id') ?? '';
  const library = rawLibrary ? String(rawLibrary) : '';
  const ratingKey = rawRatingKey ? String(rawRatingKey) : '';

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [operations, setOperations] = useState({
    poster: createOperation(),
    background: createOperation(),
    seasons: {},
  });

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

  const updateSeasonOperation = useCallback((index, nextState) => {
    const key = String(index);
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
          const key = season?.index != null ? String(season.index) : null;
          if (!key) return;
          nextKeys.add(key);
          if (!seasonsMap[key]) {
            seasonsMap[key] = createOperation();
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

  const seasons = useMemo(() => {
    if (!Array.isArray(detail?.seasons)) return [];
    return detail.seasons
      .filter((season) => season && season.index != null)
      .map((season) => {
        const idx = season.index;
        const title = season.title || `Season ${String(idx).padStart(2, '0')}`;
        const posterUrl = season.posterUrl || season.url || null;
        const plexPosterUrl = season.plexPosterUrl || season.urlPlex || null;
        const exists = typeof season.exists === 'boolean'
          ? season.exists
          : Boolean(posterUrl && posterUrl.startsWith('/fileproxy'));
        return {
          index: idx,
          title,
          posterUrl,
          plexPosterUrl,
          exists,
        };
      });
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
    async (index, file) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        throw new Error(MISSING_FOLDER_MESSAGE);
      }
      const idx = Number(index);
      updateSeasonOperation(idx, {
        uploading: true,
        importing: false,
        success: false,
        error: null,
        lastAction: 'upload',
      });
      setStatusMessage(`Uploading season ${String(index).padStart(2, '0')}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(index));
      form.append('file', file);

      try {
        const response = await fetch('/api/upload_season', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateSeasonOperation(idx, {
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
        updateSeasonOperation(idx, {
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
    async (index, plexUrl) => {
      if (!folderExists) {
        setStatusMessage(MISSING_FOLDER_MESSAGE);
        return;
      }
      const idx = Number(index);
      updateSeasonOperation(idx, {
        uploading: false,
        importing: true,
        success: false,
        error: null,
        lastAction: 'import',
      });
      setStatusMessage(`Importing season ${String(index).padStart(2, '0')}…`);

      const form = new FormData();
      form.append('library', library);
      if (folderName) form.append('folderName', folderName);
      form.append('season', String(index));
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      if (plexUrl) form.append('url', plexUrl);

      try {
        const response = await fetch('/api/import/season', { method: 'POST', body: form });
        const data = await safeJson(response);
        if (!response.ok || !(data && (data.ok || data.path || data.src))) {
          throw new Error(responseErrorMessage(response, data));
        }
        updateSeasonOperation(idx, {
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
        updateSeasonOperation(idx, {
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

  const backLink = library ? `/libraries?lib=${encodeURIComponent(library)}` : '/libraries';
  const folderDisplay = folderName || 'Not assigned';
  const headerTitle = detail?.title || 'Show Details';
  const headerYear = detail?.year;

  return (
    <div className="detail-page">
      <header>
        <Link className="btn" to={backLink}>
          ← Back
        </Link>
        <h1>{headerTitle}</h1>
        {headerYear ? <span className="detail-year">({headerYear})</span> : null}
        <span className="detail-header-gap" aria-hidden="true" />
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
            <div className="detail-folder" aria-live="polite">
              Asset folder:
              <span className="detail-folder-name">{folderDisplay}</span>
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
              />
              <ArtworkCard
                label="Background"
                exists={showBackgroundExists}
                imageUrl={showBackgroundImage}
                folderExists={folderExists}
                operation={operations.background}
                onUpload={(file) => handleShowUpload('background', file)}
                onImport={() => handleShowImport('background')}
              />
            </section>
            <section>
              <h2 className="detail-section-title">Seasons</h2>
              {seasons.length ? (
                <div className="asset-card-grid season-grid">
                  {seasons.map((season) => {
                    const op = operations.seasons?.[String(season.index)] ?? createOperation();
                    return (
                      <ArtworkCard
                        key={season.index}
                        label={season.title}
                        variant="poster"
                        exists={season.exists}
                        imageUrl={season.posterUrl}
                        folderExists={folderExists}
                        operation={op}
                        onUpload={(file) => handleSeasonUpload(season.index, file)}
                        onImport={() => handleSeasonImport(season.index, season.plexPosterUrl)}
                      />
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
