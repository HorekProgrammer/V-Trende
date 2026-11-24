import { describe, it, expect } from 'vitest';
import { coverGrad, initials, fmtSearches } from '../../src/utils/trendFormat';

describe('initials (Инициалы)', () => {
  it('должна брать первые буквы двух слов', () => {
    expect(initials('Тестовый трек')).toBe('ТТ');
    expect(initials('michael jackson')).toBe('MJ');
  });
  it('должна брать одну букву для одного слова', () => {
    expect(initials('ABBA')).toBe('A');
  });
});

describe('coverGrad (Градиенты)', () => {
  it('должен возвращать валидную CSS-строку', () => {
    expect(coverGrad('123')).toContain('linear-gradient');
  });
  it('должен давать одинаковый результат для одинаковых ключей', () => {
    expect(coverGrad('test')).toBe(coverGrad('test'));
  });
});

describe('fmtSearches (Форматирование чисел)', () => {
  it('должна возвращать пустую строку, если null', () => {
    expect(fmtSearches(null)).toBe('');
  });
  it('должна форматировать миллионы', () => {
    expect(fmtSearches(1500000)).toBe('1.5 млн запросов');
  });
  it('должна форматировать тысячи', () => {
    expect(fmtSearches(2500)).toBe('3 тыс. запросов');
  });
  it('должна выводить точное число, если меньше 1000', () => {
    expect(fmtSearches(500)).toBe('500 запросов');
  });
});