import assert from 'node:assert/strict';
import test from 'node:test';

import {
  METRIKA_ID,
  loadYandexMetrika,
  resetMetrikaForTests,
  trackPageView,
} from '../src/analytics/metrika.js';


function environment() {
  const inserted = [];
  const anchor = { parentNode: { insertBefore: (script) => inserted.push(script) } };
  const document = {
    scripts: [anchor],
    createElement: () => ({}),
    getElementsByTagName: () => [anchor],
  };
  return { window: {}, document, inserted };
}


test('the counter is initialized once with deferred SPA pageviews', () => {
  resetMetrikaForTests();
  const env = environment();
  loadYandexMetrika(env.window, env.document);
  loadYandexMetrika(env.window, env.document);

  assert.equal(env.inserted.length, 1);
  assert.equal(
    env.inserted[0].src,
    `https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}`,
  );
  const calls = env.window.ym.a.map((args) => [...args]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1], 'init');
  assert.equal(calls[0][2].defer, true);
  assert.equal(calls[0][2].ssr, true);
});


test('each distinct SPA URL produces exactly one hit', () => {
  resetMetrikaForTests();
  const env = environment();
  loadYandexMetrika(env.window, env.document);

  assert.equal(trackPageView('https://vcharte.com/', '', 'Главная', env.window), true);
  assert.equal(trackPageView('https://vcharte.com/', '', 'Главная', env.window), false);
  assert.equal(
    trackPageView(
      'https://vcharte.com/category/games',
      'https://vcharte.com/',
      'Игры',
      env.window,
    ),
    true,
  );

  const hits = env.window.ym.a
    .map((args) => [...args])
    .filter((call) => call[1] === 'hit');
  assert.equal(hits.length, 2);
  assert.equal(hits[0][2], 'https://vcharte.com/');
  assert.equal(hits[1][2], 'https://vcharte.com/category/games');
  assert.equal(hits[1][3].referer, 'https://vcharte.com/');
});
