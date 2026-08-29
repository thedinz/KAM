function LibraryToolbar({
  libraries,
  selectedLibrary,
  onLibraryChange,
  searchValue,
  onSearchChange,
  sortValue = 'title',
  onSortChange,
  onImportAll,
  importDisabled,
  importTitle,
  onScanMapping,
  scanDisabled,
  scanTitle,
  countLabel,
  readyCount = 0,
  notReadyControl,
  onViewNotReady = null,
  notReadyCount = 0,
  notReadyLoading = false,
  notReadyDisabled = false,
  children,
}) {
  const showNotReadyButton = typeof onViewNotReady === 'function';
  const showSortControl = typeof onSortChange === 'function';
  const notReadyDisplay = Number(notReadyCount) || 0;
  const disableNotReady = Boolean(notReadyDisabled) || Boolean(notReadyLoading) || notReadyDisplay <= 0;
  const notReadyTitle = notReadyLoading
    ? 'Checking not-ready items...'
    : disableNotReady
    ? 'No not-ready items to review yet.'
    : 'Show only items missing asset folders.';

  return (
    <div className="page-header-tools" id="toolbar">
      <div className="toolbar-main-row">
        <div className="toolbar-view-group">
          <label className="sr-only" htmlFor="librarySearch">
            Search library
          </label>
          <div className="library-search-wrap">
            <span className="library-search-icon" aria-hidden="true">⌕</span>
            <input
              id="librarySearch"
              className="library-search"
              type="search"
              placeholder="Search your library"
              value={searchValue}
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </div>
        </div>
        <div className="toolbar-action-group">
          {onScanMapping ? (
            <button
              type="button"
              className="toolbar-secondary-action"
              onClick={onScanMapping}
              disabled={scanDisabled}
              title={scanTitle}
            >
              <span aria-hidden="true">⌗</span>
              Scan Mapping
            </button>
          ) : null}

          <button
            type="button"
            className="toolbar-primary-action"
            onClick={onImportAll}
            disabled={importDisabled}
            title={importTitle}
          >
            <span aria-hidden="true">↥</span>
            Import Assets
          </button>
        </div>
      </div>

      <div className="toolbar-command-row">
        <div className="toolbar-status-group">
          <label className="sr-only" htmlFor="librarySelect">
            Plex library
          </label>
          <select
            id="librarySelect"
            className="library-select"
            value={selectedLibrary || ''}
            onChange={(event) => onLibraryChange(event.target.value)}
          >
            {libraries.length === 0 && (
              <option value="" disabled>
                Loading…
              </option>
            )}
            {libraries.map((lib) => (
              <option key={lib} value={lib}>
                {lib}
              </option>
            ))}
          </select>

          <span className="count-label is-active" id="count">
            All <strong>{countLabel.replace(/\s+items?$/, '')}</strong>
          </span>

          <span className="count-label count-label-ready">
            Ready <strong>{Number(readyCount).toLocaleString()}</strong>
          </span>

          {showNotReadyButton ? (
            <button
              type="button"
              className="not-ready-button"
              aria-label={`Not Ready: ${notReadyLoading ? 'checking' : notReadyDisplay.toLocaleString()} items`}
              onClick={onViewNotReady}
              disabled={disableNotReady}
              title={notReadyTitle}
            >
              Needs Attention
              <span
                className="badge"
                aria-label={
                  notReadyLoading
                    ? 'Checking not-ready items'
                    : `${notReadyDisplay.toLocaleString()} not-ready items`
                }
              >
                {notReadyLoading ? '...' : notReadyDisplay.toLocaleString()}
              </span>
            </button>
          ) : null}

          {notReadyControl}
        </div>

        {showSortControl ? (
          <>
            <label className="sr-only" htmlFor="librarySort">
              Sort library
            </label>
            <select
              id="librarySort"
              className="library-sort-select"
              value={sortValue}
              onChange={(event) => onSortChange(event.target.value)}
              title="Sort library items"
              aria-label="Sort library items"
            >
              <option value="title">Title A–Z</option>
              <option value="newest">Recently Added</option>
            </select>
          </>
        ) : null}
      </div>

      {children ? (
        <div className="toolbar-feedback">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export default LibraryToolbar;
