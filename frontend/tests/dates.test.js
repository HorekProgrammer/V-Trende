import { describe, it, expect } from 'vitest';
import { formatWeek, formatDate } from '../src/utils/dates';

describe('Функция formatWeek', () => {
  it('должна возвращать пустую строку для пустой даты', () => {
    expect(formatWeek(null)).toBe('');
  });
  it('должна красиво форматировать неделю в пределах одного месяца', () => {
    expect(formatWeek('2026-10-05')).toBe('5–11 октября');
  });
  it('должна корректно склеивать месяцы', () => {
    expect(formatWeek('2026-10-26')).toBe('26 октября – 1 ноября');
  });
});

describe('Функция formatDate', () => {
  it('должна переводить ISO в формат DD/MM/YY', () => {
    expect(formatDate('2026-10-19')).toBe('19/10/26');
    expect(formatDate(null)).toBe('');
  });
});