import { describe, it, expect } from 'vitest';
import { validateEmail, validatePassword } from '../../src/utils/validation';

describe('Функция validateEmail', () => {
  it('должна выдавать ошибку при пустом значении', () => {
    expect(validateEmail('')).toBe('Введите email');
  });
  it('должна выдавать ошибку при неверном формате', () => {
    expect(validateEmail('test')).toBe('Некорректный email');
    expect(validateEmail('test@')).toBe('Некорректный email');
    expect(validateEmail('@mail.ru')).toBe('Некорректный email');
  });
  it('должна пропускать правильный email', () => {
    expect(validateEmail('test@mail.ru')).toBe('');
    expect(validateEmail('user.name+tag@domain.co.uk')).toBe('');
  });
});

describe('Функция validatePassword', () => {
  it('должна требовать ввода', () => {
    expect(validatePassword('')).toBe('Введите пароль');
  });
  it('должна проверять минимальную длину (8 символов)', () => {
    expect(validatePassword('1234567')).toBe('Минимум 8 символов');
    expect(validatePassword('12345678')).toBe('');
  });
});