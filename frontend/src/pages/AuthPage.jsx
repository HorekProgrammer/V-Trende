import { useState, useEffect } from 'react';
import { apiPost } from '../api/client';
import AuthCard from '../components/auth/AuthCard';
import FormField from '../components/auth/FormField';
import { Link } from 'react-router-dom';
import { validateEmail, validatePassword } from '../utils/validation';
import './AuthPage.css';

export default function AuthPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    document.title = 'Регистрация • В-Тренде';
  }, []);

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    if (errors.password) setErrors((prev) => ({ ...prev, password: '' }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const nextErrors = {
      email: validateEmail(email.trim()),
      password: validatePassword(password),
    };
    
    if (nextErrors.email || nextErrors.password) {
      setErrors(nextErrors);
      return;
    }

    setIsLoading(true);
    setServerError('');

    try {
      await apiPost('/auth/register', {
        email: email.trim(),
        password: password,
      });

      window.location.assign('/');
    } catch (err) {
      setServerError(err.message || 'Ошибка регистрации. Попробуйте позже.');
      
      if (err.fields) {
        setErrors({ email: '', password: '' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <AuthCard
        title="Создать аккаунт"
        subtitle="Следите за трендами"
      >
        <form onSubmit={handleSubmit} noValidate>
          {serverError && (
            <div className="auth-form-error">
              {serverError}
            </div>
          )}

          <FormField
            id="reg-email"
            label="Email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={handleEmailChange}
            error={errors.email}
          />
          <FormField
            id="reg-pass"
            label="Пароль"
            type="password"
            placeholder="Минимум 8 символов"
            autoComplete="new-password"
            value={password}
            onChange={handlePasswordChange}
            error={errors.password}
          />

          <button className="auth-submit" type="submit" disabled={isLoading}>
            {isLoading ? 'Отправка...' : 'Зарегистрироваться'}
          </button>
        </form>

        <div className="auth-divider">или</div>
        <div className="auth-switch">
          Уже есть аккаунт? <Link to="/login" className="auth-link">Войти</Link>
        </div>
      </AuthCard>
    </div>
  );
}