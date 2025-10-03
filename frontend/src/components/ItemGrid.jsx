import { buildDetailUrl, normalizePoster } from '../utils/items.js';

function ItemGrid({ items, library, onRequestFolder, loading, error }) {
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
        return <ItemCard key={key} item={item} library={library} onRequestFolder={onRequestFolder} />;
      })}
    </div>
  );
}

function ItemCard({ item, library, onRequestFolder }) {
  const ready = item?.assetReady !== false;
  const title = item?.title || item?.name || '(Untitled)';
  const year = item?.year;
  const poster = normalizePoster(item);
  const detailUrl = buildDetailUrl(item, library);
  const readinessTooltip = ready ? 'Ready: asset folder found.' : 'Not ready: asset folder missing.';

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

  const handleCardClick = (event) => {
    if (!detailUrl) return;
    if (event.metaKey || event.ctrlKey) {
      window.open(detailUrl, '_blank');
    } else {
      window.location.href = detailUrl;
    }
  };

  return (
    <div
      className="card"
      data-ready={ready ? 'true' : 'false'}
      title={detailUrl ? `${readinessTooltip} Click to open details.` : readinessTooltip}
      onClick={detailUrl ? handleCardClick : undefined}
      role={detailUrl ? 'button' : undefined}
      tabIndex={detailUrl ? 0 : undefined}
      onKeyDown={detailUrl ? (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handleCardClick(event);
        }
      } : undefined}
    >
      <img className="poster" src={poster} alt={title} loading="lazy" />
      <div className="meta">
        <div className="title">
          <span className="title-text" title={title}>
            {title}
          </span>
          <span
            className={`ready-badge ${ready ? 'ready' : 'not-ready'}`}
            title={ready ? 'Asset folder found. This item is ready for imports.' : 'Asset folder missing. Click to choose a folder.'}
            role={!ready ? 'button' : undefined}
            tabIndex={!ready ? 0 : undefined}
            onClick={!ready ? openFolder : undefined}
            onKeyDown={!ready ? handleBadgeKey : undefined}
            aria-haspopup={!ready ? 'dialog' : undefined}
          >
            {ready ? '✔ Ready' : '✖ Not Ready'}
          </span>
        </div>
        <div className="year">{year ? String(year) : ''}</div>
      </div>
    </div>
  );
}

export default ItemGrid;
