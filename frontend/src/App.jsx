import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LibraryPage from './pages/LibraryPage.jsx';
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
