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

          <label className="sr-only" htmlFor="librarySearch">
            Search library
          </label>
          <input
            id="librarySearch"
            className="library-search"
            type="search"
            placeholder="Search…"
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
          />

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
                <option value="title">A-Z</option>
                <option value="newest">Newest</option>
              </select>
            </>
          ) : null}
        </div>
      </div>

      <div className="toolbar-command-row">
        <div className="toolbar-status-group">
          <span className="count-label" id="count">
            {countLabel}
          </span>

          {showNotReadyButton ? (
            <button
              type="button"
              className="not-ready-button"
              onClick={onViewNotReady}
              disabled={disableNotReady}
              title={notReadyTitle}
            >
              Not Ready
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

        <div className="toolbar-action-group">
          <button
            type="button"
            className="toolbar-primary-action"
            onClick={onImportAll}
            disabled={importDisabled}
            title={importTitle}
          >
            Import Assets
          </button>

          {onScanMapping ? (
            <button
              type="button"
              className="toolbar-secondary-action"
              onClick={onScanMapping}
              disabled={scanDisabled}
              title={scanTitle}
            >
              Scan Mapping
            </button>
          ) : null}
        </div>
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
