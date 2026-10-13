import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthCard from '../components/auth/AuthCard';
import FormField from '../components/auth/FormField';
import { validateEmail, validatePassword } from '../utils/validation';
import './AuthPage.css';

export default function AuthPage() 
{
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});

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

  const handleSubmit = (e) => 
  {
    e.preventDefault();

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

    navigate('/');
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

          <button className="auth-submit" type="submit">
            Зарегистрироваться
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