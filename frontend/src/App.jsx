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
          <Route path="/libraries/:library/movies/:ratingKey" element={<MovieDetailPage />} />
          <Route path="/libraries/:library/shows/:ratingKey" element={<ShowDetailPage />} />
          <Route path="/movie" element={<MovieDetailPage />} />
          <Route path="/show" element={<ShowDetailPage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
