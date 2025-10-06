import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import CollectionDetailPage from './pages/CollectionDetailPage.jsx';
import LibraryPage from './pages/LibraryPage.jsx';
import MovieDetailPage from './pages/MovieDetailPage.jsx';
import NotReadyPage from './pages/NotReadyPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import ShowDetailPage from './pages/ShowDetailPage.jsx';
import { LibraryItemsProvider } from './hooks/LibraryItemsProvider.jsx';
import { ThemeProvider } from './theme/ThemeProvider.jsx';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <LibraryItemsProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/libraries" replace />} />
            <Route path="/libraries" element={<LibraryPage />} />
            <Route path="/libraries/:library" element={<LibraryPage />} />
            <Route path="/libraries/:library/not-ready" element={<NotReadyPage />} />
            <Route path="/libraries/:library/movies/:ratingKey" element={<MovieDetailPage />} />
            <Route path="/libraries/:library/shows/:ratingKey" element={<ShowDetailPage />} />
            <Route path="/libraries/:library/collections/:ratingKey" element={<CollectionDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/libraries" replace />} />
          </Routes>
        </LibraryItemsProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
