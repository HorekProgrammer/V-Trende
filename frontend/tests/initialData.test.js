import assert from 'node:assert/strict';
import test from 'node:test';

import { apiFailureResult, initialApiResult } from '../src/api/initialData.js';


test('embedded home feed is the initial successful result', () => {
  const feed = { weekStart: '2026-11-16', global: [{ title: 'Лидер' }] };
  assert.deepEqual(initialApiResult('/feed', { '/feed': feed }), {
    path: '/feed',
    data: feed,
    error: null,
  });
});


test('embedded category and trend data are selected by API path', () => {
  const category = { items: [{ title: 'Игра' }] };
  const trend = { title: 'Игра', rank: 1 };
  const data = {
    '/categories/games/trends?sort=popular&limit=100': category,
    '/trends/42': trend,
  };
  assert.equal(
    initialApiResult('/categories/games/trends?sort=popular&limit=100', data).data,
    category,
  );
  assert.equal(initialApiResult('/trends/42', data).data, trend);
});


test('a failed refresh preserves an embedded feed', () => {
  const feed = { weekStart: '2026-11-16', global: [{ title: 'Лидер' }] };
  const current = { path: '/feed', data: feed, error: null };
  assert.strictEqual(
    apiFailureResult(current, '/feed', new Error('network unavailable')),
    current,
  );
});


test('a request without fallback data still exposes its error', () => {
  const error = new Error('network unavailable');
  assert.deepEqual(
    apiFailureResult({ path: null, data: null, error: null }, '/feed', error),
    { path: '/feed', data: null, error },
  );
});
