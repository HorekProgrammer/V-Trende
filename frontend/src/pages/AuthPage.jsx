import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthCard from '../components/auth/AuthCard';
import FormField from '../components/auth/FormField';
import { validateEmail, validatePassword } from '../utils/validation';
import { apiPost } from '../api/client';
import { registerPath } from '../api/paths';
import './AuthPage.css';

export default function AuthPage() 
{
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {document.title = 'Регистрация • В-Тренде'}, []);

  const handleEmailChange = (e) => 
  {
    setEmail(e.target.value);
    if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
  };

  const handlePasswordChange = (e) => 
  {
    setPassword(e.target.value);
    if (errors.password) setErrors((prev) => ({ ...prev, password: '' }));
  };

  const handleSubmit = async (e) => 
  {
    e.preventDefault();
    if (submitting) return;

    const nextErrors = 
    {
      email: validateEmail(email.trim()),
      password: validatePassword(password),
    };
    if (nextErrors.email || nextErrors.password) 
    {
      setErrors(nextErrors);
      return;
    }

    setFormError('');
    setSubmitting(true);
    try 
    {
      // Сервер создаёт аккаунт и сразу выполняет вход: ставит cookie сессии.
      await apiPost(registerPath(), { email: email.trim(), password });
      navigate('/');
    } 
    catch (error) 
    {
      if (error.fields && (error.fields.email || error.fields.password)) 
      {
        setErrors({ email: error.fields.email || '', password: error.fields.password || '' });
      } 
      else 
      {
        setFormError(error.status ? error.message : 'Сервер недоступен. Попробуйте позже.');
      }
    } 
    finally 
    {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-wrap">
      <AuthCard
        title="Создать аккаунт"
        subtitle="Сохраняйте чарты и следите за трендами"
      >
        <form onSubmit={handleSubmit} noValidate>
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

          {formError && <div className="auth-form-error" role="alert">{formError}</div>}

          <button className="auth-submit" type="submit" disabled={submitting}>
            {submitting ? 'Регистрация…' : 'Зарегистрироваться'}
          </button>
        </form>

        <div className="auth-divider">или</div>
        <div className="auth-switch">
          Уже есть аккаунт? <button type="button" className="auth-link">Войти</button>
        </div>
      </AuthCard>
    </div>
  );
}