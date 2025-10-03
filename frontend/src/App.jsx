import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LibraryPage from './pages/LibraryPage.jsx';
import MovieDetailPage from './pages/MovieDetailPage.jsx';
import ShowDetailPage from './pages/ShowDetailPage.jsx';
import { ThemeProvider } from './theme/ThemeProvider.jsx';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/libraries" replace />} />
          <Route path="/libraries" element={<LibraryPage />} />
          <Route path="/libraries/*" element={<LibraryPage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
