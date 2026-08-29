import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import AppSidebar from './components/AppSidebar.jsx';
import BrandLockup from './components/BrandLockup.jsx';
import LoginPage from './pages/LoginPage.jsx';
import CollectionDetailPage from './pages/CollectionDetailPage.jsx';
import ImportErrorsPage from './pages/ImportErrorsPage.jsx';
import LibraryPage from './pages/LibraryPage.jsx';
import MovieDetailPage from './pages/MovieDetailPage.jsx';
import MappingScanPage from './pages/MappingScanPage.jsx';
import NotReadyPage from './pages/NotReadyPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import ShowDetailPage from './pages/ShowDetailPage.jsx';
import { AuthProvider, useAuth } from './hooks/AuthProvider.jsx';
import { LibraryItemsProvider } from './hooks/LibraryItemsProvider.jsx';
import { ThemeProvider } from './theme/ThemeProvider.jsx';
import { KAM_VERSION } from './version.js';

function RequireAuth() {
  const { enabled, authenticated, loading } = useAuth();

  if (loading) {
    return (
      <main className="login-page">
        <section className="login-card">
          <h1 className="login-brand-title">
            <BrandLockup compact />
          </h1>
          <p className="login-subtitle">Checking your session…</p>
        </section>
      </main>
    );
  }

  if (enabled && !authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

function AppFooter() {
  return (
    <footer className="app-footer">
      <span>Made and provided for free with love</span>
      <span aria-hidden="true">/</span>
      <span>KAM v{KAM_VERSION}</span>
    </footer>
  );
}

function AppLayout() {
  return (
    <div className="workspace-shell">
      <AppSidebar />
      <div className="workspace-content">
        <div className="workspace-routes">
          <Outlet />
        </div>
        <AppFooter />
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <BrowserRouter>
          <LibraryItemsProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<RequireAuth />}>
                <Route element={<AppLayout />}>
                    <Route path="/" element={<Navigate to="/libraries" replace />} />
                    <Route path="/libraries" element={<LibraryPage />} />
                    <Route path="/libraries/:library" element={<LibraryPage />} />
                    <Route path="/libraries/:library/import-errors" element={<ImportErrorsPage />} />
                    <Route path="/libraries/:library/not-ready" element={<NotReadyPage />} />
                    <Route path="/libraries/:library/mapping" element={<MappingScanPage />} />
                    <Route path="/libraries/:library/movies/:ratingKey" element={<MovieDetailPage />} />
                    <Route path="/libraries/:library/shows/:ratingKey" element={<ShowDetailPage />} />
                    <Route path="/libraries/:library/collections/:ratingKey" element={<CollectionDetailPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/libraries" replace />} />
            </Routes>
          </LibraryItemsProvider>
        </BrowserRouter>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
