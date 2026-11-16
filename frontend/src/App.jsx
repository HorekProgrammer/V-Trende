import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import Header from './components/common/Header';
import HomePage from './pages/HomePage';
import CategoryPage from './pages/CategoryPage';
import DetailPage from './pages/DetailPage';
import EmberBackground from './components/common/EmberBackground';
import YandexMetrika from './analytics/YandexMetrika';

function App() {
  return (
    <BrowserRouter>
      <YandexMetrika />
      <EmberBackground />
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/category/:name" element={<CategoryPage />} />
        <Route path="/trend/:id" element={<DetailPage />} />
        <Route path="/auth" element={<Navigate to="/" replace />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
