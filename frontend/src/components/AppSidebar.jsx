import { NavLink, useLocation } from 'react-router-dom';
import BrandLockup from './BrandLockup.jsx';
import { useLibraryItemsContext } from '../hooks/LibraryItemsProvider.jsx';
import { useTheme } from '../theme/ThemeProvider.jsx';
import { KAM_VERSION } from '../version.js';

function NavigationIcon({ name }) {
  const paths = {
    library: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    movie: (
      <>
        <path d="M4 7h16v12H4z" />
        <path d="m5 3 3 4m3-4 3 4m3-4 3 4M4 11h16" />
      </>
    ),
    show: (
      <>
        <rect x="3" y="5" width="18" height="13" rx="2" />
        <path d="M8 21h8M12 18v3" />
      </>
    ),
    collection: (
      <>
        <path d="M3 7.5h7l2 2h9v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <path d="M3 7.5V6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v1.5" />
      </>
    ),
    attention: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v6m0 4h.01" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.09A1.7 1.7 0 0 0 9 19.36a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.09A1.7 1.7 0 0 0 4.64 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63a1.7 1.7 0 0 0 1-1.55V3h4v.09A1.7 1.7 0 0 0 15 4.64a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9a1.7 1.7 0 0 0 1.56 1H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
      </>
    ),
  };

  return (
    <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.library}
    </svg>
  );
}

function libraryIcon(library) {
  const type = String(library?.type || '').toLowerCase();
  const name = String(library?.name || '').toLowerCase();
  if (name.includes('collection')) return 'collection';
  if (type.includes('show') || type.includes('tv')) return 'show';
  if (type.includes('movie')) return 'movie';
  return 'library';
}

function hasCollectionsMapping(library) {
  if (String(library?.collectionsPath || '').trim()) return true;
  if (Array.isArray(library?.collectionAssetPaths) && library.collectionAssetPaths.length) return true;
  return Array.isArray(library?.collectionOverrides)
    && library.collectionOverrides.some((entry) => String(entry?.collectionsPath || '').trim());
}

function AppSidebar() {
  const location = useLocation();
  const { libraries = [] } = useTheme();
  const { library: selectedLibrary, notReadyCount, totalCount } = useLibraryItemsContext();
  const mappedLibraries = libraries.filter((entry) => String(entry?.assetPath || '').trim());
  const normalizedSelected = String(selectedLibrary || '').trim().toLowerCase();
  const attentionCount = Number(notReadyCount) || 0;
  const libraryTotal = Number(totalCount) || 0;
  const attentionRatio = `${attentionCount.toLocaleString()} / ${libraryTotal.toLocaleString()}`;
  const attentionHref = selectedLibrary
    ? `/libraries/${encodeURIComponent(selectedLibrary)}/not-ready`
    : '/libraries';

  return (
    <aside className="app-sidebar">
      <NavLink className="app-sidebar-brand" to="/libraries" aria-label="KAM library home">
        <BrandLockup compact />
      </NavLink>

      <nav className="app-navigation" aria-label="Primary navigation">
        {mappedLibraries.length ? (
          <>
            <div className="app-nav-section-label">Libraries</div>
            <div className="app-library-links">
              {mappedLibraries.map((entry) => {
                const name = String(entry?.name || '').trim();
                if (!name) return null;
                const href = `/libraries/${encodeURIComponent(name)}`;
                const collectionsHref = `${href}/collections`;
                const collectionsActive = location.pathname === collectionsHref
                  || location.pathname.startsWith(`${collectionsHref}/`);
                const active = normalizedSelected === name.toLowerCase()
                  && location.pathname !== '/settings'
                  && !collectionsActive;
                return (
                  <div className="app-library-group" key={name}>
                    <NavLink className={`app-nav-item${active ? ' is-active' : ''}`} to={href}>
                      <NavigationIcon name={libraryIcon(entry)} />
                      <span title={name}>{name}</span>
                    </NavLink>
                    {hasCollectionsMapping(entry) ? (
                      <NavLink
                        className={`app-nav-item app-nav-subitem${collectionsActive ? ' is-active' : ''}`}
                        to={collectionsHref}
                        aria-label={`${name} Collections`}
                      >
                        <span className="app-nav-branch" aria-hidden="true">
                          <svg viewBox="0 0 20 50" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
                            <path className="app-nav-branch-line" d="M1 0v35a10 10 0 0 0 10 10h7" />
                            <path className="app-nav-branch-arrow" d="m15 42 3 3-3 3" />
                          </svg>
                        </span>
                        <NavigationIcon name="collection" />
                        <span>Collections</span>
                      </NavLink>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </>
        ) : null}

        {selectedLibrary ? (
          <NavLink
            className={({ isActive }) => `app-nav-item app-nav-attention${isActive ? ' is-active' : ''}`}
            to={attentionHref}
            aria-label={`Needs Attention ${attentionRatio}`}
          >
            <NavigationIcon name="attention" />
            <span>Needs Attention</span>
            <span className="app-nav-badge">{attentionRatio}</span>
          </NavLink>
        ) : (
          <span className="app-nav-item app-nav-attention is-disabled" aria-disabled="true">
            <NavigationIcon name="attention" />
            <span>Needs Attention</span>
          </span>
        )}
      </nav>

      <div className="app-sidebar-bottom">
        <NavLink className={({ isActive }) => `app-nav-item${isActive ? ' is-active' : ''}`} to="/settings">
          <NavigationIcon name="settings" />
          <span>Settings</span>
        </NavLink>
        <span className="app-sidebar-version">KAM v{KAM_VERSION}</span>
      </div>
    </aside>
  );
}

export default AppSidebar;
