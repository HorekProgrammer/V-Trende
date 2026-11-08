import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiPost } from '../api/client';
import AuthCard from '../components/auth/AuthCard';
import FormField from '../components/auth/FormField';
import { loginPath } from '../api/paths';
import './AuthPage.css';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [serverError, setServerError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    document.title = 'Вход • В-Тренде';
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setServerError('');
    try {
      await apiPost(loginPath(), { email: email.trim(), password });
      window.location.assign('/'); 
    } catch (err) {
      setServerError(err.message || 'Неверный email или пароль');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <AuthCard title="Вход" subtitle="Войдите, чтобы следить за трендами">
        <form onSubmit={handleSubmit} noValidate>
          {serverError && <div className="auth-form-error">{serverError}</div>}

          <FormField
            id="login-email"
            label="Email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <FormField
            id="login-pass"
            label="Пароль"
            type="password"
            placeholder="Ваш пароль"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button className="auth-submit" type="submit" disabled={isLoading}>
            {isLoading ? 'Входим...' : 'Войти'}
          </button>
        </form>

        <div className="auth-divider">или</div>
        <div className="auth-switch">
          Нет аккаунта? <Link to="/auth" className="auth-link">Зарегистрироваться</Link>
        </div>
      </AuthCard>
    </div>
  );
}