import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function formatFailure(entry) {
  if (!entry) return 'Unknown issue';
  const parts = [];
  if (entry.library) parts.push(`[${entry.library}]`);
  if (entry.title) parts.push(entry.title);
  if (entry.folder && entry.folder !== entry.title) parts.push(`(${entry.folder})`);
  let text = parts.join(' ');
  if (entry.asset) text = text ? `${text} – ${entry.asset}` : entry.asset;
  if (entry.message) text = text ? `${text}: ${entry.message}` : entry.message;
  return text || 'Unknown issue';
}

function ImportStatusPanel({
  active,
  percent,
  label,
  errors,
  errorHeading = 'Import Errors',
  errorNoun = 'import error',
  modalId = 'importErrorsDialog',
}) {
  const formattedErrors = useMemo(() => {
    if (!Array.isArray(errors)) return [];
    return errors
      .map((entry) => formatFailure(entry))
      .filter((text) => typeof text === 'string' && text.trim().length > 0);
  }, [errors]);

  const hasErrors = formattedErrors.length > 0;
  const clamped = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;
  const classes = ['import-status'];
  if (active) classes.push('is-active');
  if (hasErrors) classes.push('has-errors');

  const [isModalOpen, setModalOpen] = useState(false);
  const closeButtonRef = useRef(null);
  const headingId = `${modalId}Heading`;

  const closeModal = useCallback(() => {
    setModalOpen(false);
  }, []);

  const openModal = useCallback(() => {
    if (hasErrors) {
      setModalOpen(true);
    }
  }, [hasErrors]);

  const handleBackdropClick = useCallback(
    (event) => {
      if (event.target === event.currentTarget) {
        closeModal();
      }
    },
    [closeModal],
  );

  useEffect(() => {
    if (!hasErrors) {
      closeModal();
    }
  }, [hasErrors, closeModal]);

  useEffect(() => {
    if (!isModalOpen) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isModalOpen, closeModal]);

  useEffect(() => {
    if (isModalOpen && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [isModalOpen]);

  const errorCountLabel = useMemo(() => {
    const count = formattedErrors.length;
    const noun = errorNoun || 'import error';
    const label = count === 1 ? noun : `${noun}s`;
    return `${count} ${label}`;
  }, [formattedErrors.length, errorNoun]);

  return (
    <div className={classes.join(' ')} aria-live="polite">
      <div className="progress-wrapper">
        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${clamped}%` }} />
        </div>
        <span className="progress-label">{label}</span>
      </div>
      {hasErrors ? (
        <button
          type="button"
          className="error-trigger"
          onClick={openModal}
          aria-haspopup="dialog"
          aria-expanded={isModalOpen}
          aria-controls={modalId}
        >
          View {errorCountLabel}
        </button>
      ) : null}
      {hasErrors && isModalOpen ? (
        <div className="dialog-backdrop" role="presentation" onClick={handleBackdropClick}>
          <div
            className="dialog-panel error-dlg"
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            id={modalId}
          >
            <div className="dialog-body">
              <div className="dialog-heading">
                <h2 id={headingId}>{errorHeading}</h2>
                <button
                  type="button"
                  className="dialog-close"
                  aria-label="Close import errors"
                  onClick={closeModal}
                  ref={closeButtonRef}
                >
                  ×
                </button>
              </div>
              <p className="import-error-summary">{errorCountLabel}. Scroll to review each item.</p>
              <ol className="import-error-list">
                {formattedErrors.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ol>
            </div>
            <div className="actions">
              <button type="button" onClick={closeModal}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default ImportStatusPanel;
