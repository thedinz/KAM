import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
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
            <Route path="/libraries/:library/not-ready" element={<NotReadyPage />} />
            <Route path="/libraries/*" element={<LibraryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </LibraryItemsProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
