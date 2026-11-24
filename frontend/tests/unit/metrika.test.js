import { describe, it, expect, beforeEach } from 'vitest';
import {
  METRIKA_ID,
  loadYandexMetrika,
  resetMetrikaForTests,
  trackPageView,
} from '../../src/analytics/metrika.js';

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

describe('Яндекс.Метрика', () => {
  beforeEach(() => {
    resetMetrikaForTests();
  });

  it('счетчик инициализируется один раз с отложенными просмотрами', () => {
    const env = environment();
    loadYandexMetrika(env.window, env.document);
    loadYandexMetrika(env.window, env.document); // Вызываем второй раз

    expect(env.inserted.length).toBe(1);
    expect(env.inserted[0].src).toBe(`https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}`);
    
    const calls = env.window.ym.a.map((args) => [...args]);
    expect(calls.length).toBe(1);
    expect(calls[0][1]).toBe('init');
    expect(calls[0][2].defer).toBe(true);
    expect(calls[0][2].ssr).toBe(true);
  });

  it('каждый уникальный URL SPA генерирует ровно один хит', () => {
    const env = environment();
    loadYandexMetrika(env.window, env.document);

    expect(trackPageView('https://vcharte.com/', '', 'Главная', env.window)).toBe(true);
    expect(trackPageView('https://vcharte.com/', '', 'Главная', env.window)).toBe(false);
    expect(trackPageView('https://vcharte.com/category/games', 'https://vcharte.com/', 'Игры', env.window)).toBe(true);

    const hits = env.window.ym.a
      .map((args) => [...args])
      .filter((call) => call[1] === 'hit');
      
    expect(hits.length).toBe(2);
    expect(hits[0][2]).toBe('https://vcharte.com/');
    expect(hits[1][2]).toBe('https://vcharte.com/category/games');
    expect(hits[1][3].referer).toBe('https://vcharte.com/');
  });
});