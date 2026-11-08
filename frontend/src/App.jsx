import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/common/Header';
import HomePage from './pages/HomePage';
import CategoryPage from './pages/CategoryPage';
import DetailPage from './pages/DetailPage';
import AuthPage from './pages/AuthPage';
import LoginPage from './pages/LoginPage';
import EmberBackground from './components/common/EmberBackground';

function App() {
  return (
    <BrowserRouter>
      <EmberBackground />
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/category/:name" element={<CategoryPage />} />
        <Route path="/trend/:id" element={<DetailPage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;