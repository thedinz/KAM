import { useEffect, useRef } from 'react';

const IDLE_OPERATION = Object.freeze({
  uploading: false,
  importing: false,
  success: false,
  error: null,
  lastAction: null,
});

function ArtworkCard({
  label,
  variant: variantProp = null,
  exists = false,
  imageUrl = null,
  folderExists = false,
  operation = IDLE_OPERATION,
  onUpload,
  onImport,
  uploadLabel = 'Upload',
  importLabel = 'Import',
}) {
  const inputRef = useRef(null);

  const uploading = Boolean(operation?.uploading);
  const importing = Boolean(operation?.importing);
  const success = Boolean(operation?.success);
  const error = operation?.error || null;
  const lastAction = operation?.lastAction || null;

  const busy = uploading || importing;
  const hasImport = typeof onImport === 'function';
  const hasUpload = typeof onUpload === 'function';

  useEffect(() => {
    if (!folderExists && inputRef.current) {
      inputRef.current.value = '';
    }
  }, [folderExists]);

  const handleUploadClick = () => {
    if (!hasUpload || busy || !folderExists) return;
    if (inputRef.current) {
      inputRef.current.value = '';
      inputRef.current.click();
    }
  };

  const handleFileChange = (event) => {
    if (!hasUpload || busy || !folderExists) return;
    const selected = event.target.files && event.target.files[0] ? event.target.files[0] : null;
    if (!selected) return;
    const result = onUpload(selected);
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  };

  const handleImportClick = () => {
    if (!hasImport) return;
    const result = onImport();
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  };

  const uploadDisabled = !folderExists || busy;
  const importDisabled = !folderExists || busy;

  let statusText = '\u00a0';
  let statusClass = 'status-text';
  if (error) {
    statusText = error;
    statusClass = 'status-text error';
  } else if (success) {
    statusText = lastAction === 'upload' ? 'Upload complete.' : 'Import complete.';
    statusClass = 'status-text success';
  } else if (busy) {
    statusText = uploading ? 'Uploading…' : 'Importing…';
  }

  const normalizedLabel = typeof label === 'string' ? label.trim().toLowerCase() : '';
  const variant = variantProp || (normalizedLabel.includes('poster') ? 'poster' : 'default');
  const imageWrapperClassName = ['asset-image-wrapper'];
  if (variant === 'poster') {
    imageWrapperClassName.push('asset-image-wrapper--poster');
  } else {
    imageWrapperClassName.push('asset-image-wrapper--landscape');
  }

  return (
    <div className="asset-card">
      <div className="asset-label">
        <span>{label}</span>
        <span className={`asset-flag ${exists ? 'exists' : 'missing'}`}>
          {exists ? 'exists' : 'missing'}
        </span>
      </div>
      <div className={imageWrapperClassName.join(' ')}>
        {imageUrl ? (
          <img className="asset-image" src={imageUrl} alt={label} loading="lazy" />
        ) : (
          <div className="asset-placeholder" aria-hidden="true">
            No preview available
          </div>
        )}
      </div>
      <div className="asset-actions">
        {hasUpload ? (
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="asset-file-input"
            tabIndex={-1}
            disabled={!folderExists || busy}
            onChange={handleFileChange}
            hidden
            style={{ display: 'none' }}
          />
        ) : null}
        {hasUpload ? (
          <button
            type="button"
            className="btn"
            aria-label={`Upload ${label}`}
            onClick={handleUploadClick}
            disabled={uploadDisabled}
          >
            {uploading ? 'Uploading…' : uploadLabel}
          </button>
        ) : null}
        {hasImport ? (
          <button
            type="button"
            className="btn"
            aria-label={`Import ${label}`}
            onClick={handleImportClick}
            disabled={importDisabled}
          >
            {importing ? 'Importing…' : importLabel}
          </button>
        ) : null}
      </div>
      <div className={statusClass} aria-live="polite">
        {statusText}
      </div>
    </div>
  );
}

export default ArtworkCard;
export { IDLE_OPERATION };
