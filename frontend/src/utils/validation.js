const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(value) 
{
  if (!value) return 'Введите email';
  if (!EMAIL_RE.test(value)) return 'Некорректный email';
  return '';
}

export function validatePassword(value) 
{
  if (!value) return 'Введите пароль';
  if (value.length < 8) return 'Минимум 8 символов';
  return '';
}