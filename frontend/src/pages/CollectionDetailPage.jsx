import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import ArtworkCard from '../components/ArtworkCard.jsx';
import { responseErrorMessage, safeJson } from '../utils/api.js';

const MISSING_FOLDER_MESSAGE = 'Create the Kometa collections folder first.';

function createOperation() {
  return {
    uploading: false,
    importing: false,
    success: false,
    error: null,
    lastAction: null,
  };
}

function CollectionDetailPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const rawLibrary = params.library ?? searchParams.get('library') ?? searchParams.get('lib') ?? '';
  const rawRatingKey = params.ratingKey ?? searchParams.get('ratingKey') ?? searchParams.get('id') ?? '';
  const sourceParam = searchParams.get('source') ?? searchParams.get('sourceLibrary') ?? '';
  const library = rawLibrary ? String(rawLibrary) : '';
  const ratingKey = rawRatingKey ? String(rawRatingKey) : '';
  const sourceLibrary = sourceParam ? String(sourceParam) : '';

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [operations, setOperations] = useState({
    poster: createOperation(),
    background: createOperation(),
  });

  useEffect(() => {
    setDetail(null);
    setError(null);
    setStatusMessage('');
    setOperations({ poster: createOperation(), background: createOperation() });
  }, [library, ratingKey, sourceLibrary]);

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
      if (sourceLibrary) {
        query.set('source', sourceLibrary);
      }
      const response = await fetch(`/api/collection?${query.toString()}`);
      const data = await safeJson(response);
      if (!response.ok) {
        throw new Error(responseErrorMessage(response, data));
      }
      setDetail(data || null);
      if (typeof document !== 'undefined') {
        const titlePieces = [];
        if (data?.title) titlePieces.push(data.title);
        if (data?.year) titlePieces.push(`(${data.year})`);
        document.title = titlePieces.length
          ? `KAM • ${titlePieces.join(' ')}`
          : 'KAM • Collection Details';
      }
      setStatusMessage((prev) => {
        if (!data?.folderExists) return MISSING_FOLDER_MESSAGE;
        if (prev && prev !== MISSING_FOLDER_MESSAGE) return prev;
        return '';
      });
    } catch (err) {
      const message = err?.message || String(err);
      setError(message);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [library, ratingKey, sourceLibrary]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  const folderExists = Boolean(detail?.folderExists);
  const folderName = detail?.folderName || '';
  const effectiveRatingKey = detail?.ratingKey != null ? String(detail.ratingKey) : ratingKey;

  const posterExists = useMemo(() => {
    if (typeof detail?.posterExists === 'boolean') return detail.posterExists;
    return Boolean(detail?.posterUrl);
  }, [detail]);

  const backgroundExists = useMemo(() => {
    if (typeof detail?.backgroundExists === 'boolean') return detail.backgroundExists;
    return Boolean(detail?.backgroundUrl);
  }, [detail]);

  const posterImage = detail?.posterUrl || detail?.posterUrlPlex || null;
  const backgroundImage = detail?.backgroundUrl || detail?.backgroundUrlPlex || null;

  const handleUpload = useCallback(
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
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      if (folderName) form.append('folderName', folderName);
      form.append('kind', kind);
      form.append('file', file);

      try {
        const response = await fetch('/api/upload', { method: 'POST', body: form });
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
    [folderExists, library, effectiveRatingKey, folderName, fetchDetails, updateOperation]
  );

  const handleImport = useCallback(
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
      if (effectiveRatingKey) form.append('ratingKey', effectiveRatingKey);
      if (folderName) form.append('folderName', folderName);
      const plexUrl =
        kind === 'background'
          ? detail?.backgroundUrlPlex || detail?.plexBackgroundUrl || null
          : detail?.posterUrlPlex || detail?.plexPosterUrl || null;
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
    [folderExists, library, effectiveRatingKey, folderName, detail, fetchDetails, updateOperation]
  );

  const backLink = library ? `/libraries?lib=${encodeURIComponent(library)}` : '/libraries';
  const folderDisplay = folderName || 'Not assigned';
  const headerTitle = detail?.title || 'Collection Details';
  const headerYear = detail?.year;
  const displaySource = detail?.sourceLibrary || sourceLibrary || '';

  return (
    <div className="detail-page">
      <header>
        <Link className="btn" to={backLink}>
          ← Back
        </Link>
        <h1>{headerTitle}</h1>
        {headerYear ? <span className="detail-year">({headerYear})</span> : null}
        {displaySource ? <span className="detail-source">• {displaySource}</span> : null}
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
              Collections folder:
              <span className="detail-folder-name">{folderDisplay}</span>
            </div>
            <section className="asset-card-grid">
              <ArtworkCard
                label="Poster"
                exists={posterExists}
                imageUrl={posterImage}
                folderExists={folderExists}
                operation={operations.poster}
                onUpload={(file) => handleUpload('poster', file)}
                onImport={() => handleImport('poster')}
              />
              <ArtworkCard
                label="Background"
                exists={backgroundExists}
                imageUrl={backgroundImage}
                folderExists={folderExists}
                operation={operations.background}
                onUpload={(file) => handleUpload('background', file)}
                onImport={() => handleImport('background')}
              />
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

export default CollectionDetailPage;
