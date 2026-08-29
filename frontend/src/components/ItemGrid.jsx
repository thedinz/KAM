import { Link, useLocation } from 'react-router-dom';
import { buildDetailPath, normalizePoster } from '../utils/items.js';
import { currentPathWithSearch } from '../utils/navigation.js';

function ItemGrid({ items, library, onRequestFolder, loading, error }) {
  const location = useLocation();
  const returnTo = currentPathWithSearch(location);

  if (loading) {
    return <div className="loading-state">Loading items…</div>;
  }

  if (error) {
    return <div className="error-state">{error}</div>;
  }

  if (!items.length) {
    return <div className="empty-state">No items found.</div>;
  }

  return (
    <div id="grid" aria-live="polite">
      {items.map((item, index) => {
        const rawKey = item?.ratingKey ?? item?.key ?? item?.id ?? item?.title ?? index;
        const key = typeof rawKey === 'string' ? rawKey : String(rawKey);
        return (
          <ItemCard
            key={key}
            item={item}
            library={library}
            onRequestFolder={onRequestFolder}
            returnTo={returnTo}
          />
        );
      })}
    </div>
  );
}

function ItemCard({ item, library, onRequestFolder, returnTo }) {
  const ready = item?.assetReady !== false;
  const title = item?.title || item?.name || '(Untitled)';
  const year = item?.year;
  const poster = normalizePoster(item);
  const detailPath = buildDetailPath(item, library);
  const readinessTooltip = ready
    ? 'Ready: asset folder found. Click to change the assigned folder.'
    : 'Not ready: asset folder missing. Click to choose a folder.';

  const openFolder = (event) => {
    if (!onRequestFolder) return;
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    onRequestFolder(item);
  };

  const handleBadgeKey = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      openFolder(event);
    }
  };

  const cardTitle = detailPath ? `${readinessTooltip} Click to open details.` : readinessTooltip;

  const content = (
    <>
      <img className="poster" src={poster} alt={title} loading="lazy" />
      <div className="meta">
        <div className="title">
          <span className="title-text" title={title}>
            {title}
          </span>
          {year ? <span className="year">{String(year)}</span> : null}
        </div>
        <span
          className={`ready-badge ${ready ? 'ready' : 'not-ready'}`}
          title={
            ready
              ? 'Asset folder found. Click to change the assigned folder.'
              : 'Asset folder missing. Click to choose a folder.'
          }
          role="button"
          tabIndex={0}
          aria-label={ready ? 'Ready' : 'Not Ready: folder needed'}
          onClick={openFolder}
          onKeyDown={handleBadgeKey}
          aria-haspopup="dialog"
        >
          <span className="ready-badge-icon" aria-hidden="true">{ready ? '✓' : '!'}</span>
          {ready ? 'Ready' : 'Folder needed'}
        </span>
      </div>
    </>
  );

  if (detailPath) {
    return (
      <Link
        className="card"
        data-ready={ready ? 'true' : 'false'}
        title={cardTitle}
        to={detailPath}
        state={{ returnTo }}
      >
        {content}
      </Link>
    );
  }

  return (
    <div className="card" data-ready={ready ? 'true' : 'false'} title={cardTitle}>
      {content}
    </div>
  );
}

export default ItemGrid;
