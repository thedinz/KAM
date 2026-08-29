function LibraryToolbar({
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
  children,
}) {
  const showSortControl = typeof onSortChange === 'function';

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

      {showSortControl ? (
        <div className="toolbar-command-row toolbar-sort-row">
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
        </div>
      ) : null}

      {children ? (
        <div className="toolbar-feedback">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export default LibraryToolbar;
