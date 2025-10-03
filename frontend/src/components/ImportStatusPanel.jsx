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

function ImportStatusPanel({ active, percent, label, errors }) {
  const hasErrors = Array.isArray(errors) && errors.length > 0;
  const clamped = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;
  const classes = ['import-status'];
  if (active) classes.push('is-active');
  if (hasErrors) classes.push('has-errors');

  return (
    <div className={classes.join(' ')} aria-live="polite">
      <div className="progress-wrapper">
        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${clamped}%` }} />
        </div>
        <span className="progress-label">{label}</span>
      </div>
      <ul className="error-list">
        {hasErrors && errors.map((entry, index) => <li key={index}>{formatFailure(entry)}</li>)}
      </ul>
    </div>
  );
}

export default ImportStatusPanel;
