import { describe, it, expect } from 'vitest';
import { apiFailureResult, initialApiResult } from '../../src/api/initialData.js';

describe('initialData (Кэш и SSR)', () => {
  it('должен возвращать встроенные данные как начальный результат', () => {
    const feed = { weekStart: '2026-11-16', global: [{ title: 'Лидер' }] };
    expect(initialApiResult('/feed', { '/feed': feed })).toEqual({
      path: '/feed',
      data: feed,
      error: null,
    });
  });

  it('должен выбирать данные по пути API', () => {
    const category = { items: [{ title: 'Игра' }] };
    const trend = { title: 'Игра', rank: 1 };
    const data = {
      '/categories/games/trends?sort=popular&limit=100': category,
      '/trends/42': trend,
    };
    expect(initialApiResult('/categories/games/trends?sort=popular&limit=100', data).data).toEqual(category);
    expect(initialApiResult('/trends/42', data).data).toEqual(trend);
  });

  it('должен сохранять старые данные при ошибке сети', () => {
    const feed = { weekStart: '2026-11-16', global: [{ title: 'Лидер' }] };
    const current = { path: '/feed', data: feed, error: null };
    expect(apiFailureResult(current, '/feed', new Error('network unavailable'))).toBe(current);
  });

  it('должен возвращать ошибку, если резервных данных нет', () => {
    const error = new Error('network unavailable');
    expect(apiFailureResult({ path: null, data: null, error: null }, '/feed', error)).toEqual({
      path: '/feed',
      data: null,
      error,
    });
  });
});