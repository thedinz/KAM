function LibraryToolbar({
  libraries,
  selectedLibrary,
  onLibraryChange,
  searchValue,
  onSearchChange,
  onImportAll,
  importDisabled,
  importTitle,
  page,
  totalPages,
  onFirst,
  onPrev,
  onNext,
  onLast,
  countLabel,
  notReadyControl,
  children,
}) {
  return (
    <div className="page-header-tools" id="toolbar">
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

      <button type="button" onClick={onImportAll} disabled={importDisabled} title={importTitle}>
        Import Assets
      </button>

      <div className="pager" id="pager">
        <button type="button" onClick={onFirst} disabled={page <= 1}>
          « First
        </button>
        <button type="button" onClick={onPrev} disabled={page <= 1}>
          ‹ Prev
        </button>
        <span aria-live="polite" id="pageInfo">
          Page {page} / {totalPages || 1}
        </span>
        <button type="button" onClick={onNext} disabled={page >= totalPages}>
          Next ›
        </button>
        <button type="button" onClick={onLast} disabled={page >= totalPages}>
          Last »
        </button>
      </div>

      <span className="count-label" id="count">
        {countLabel}
      </span>

      {notReadyControl}

      {children}
    </div>
  );
}

export default LibraryToolbar;
