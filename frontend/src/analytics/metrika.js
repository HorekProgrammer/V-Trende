export const METRIKA_ID = 114283365;
export const ANALYTICS_CONSENT_KEY = 'vcharte_analytics_consent';

let initialized = false;
let lastTrackedUrl = null;


export function loadYandexMetrika(win = window, doc = document) {
  if (initialized) return;

  win.ym = win.ym || function metrikaQueue() {
    (win.ym.a = win.ym.a || []).push(arguments);
  };
  win.ym.l = Number(new Date());

  const source = `https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}`;
  if (![...doc.scripts].some((script) => script.src === source)) {
    const script = doc.createElement('script');
    script.async = true;
    script.src = source;
    const firstScript = doc.getElementsByTagName('script')[0];
    firstScript.parentNode.insertBefore(script, firstScript);
  }

  win.ym(METRIKA_ID, 'init', {
    defer: true,
    ssr: true,
    webvisor: true,
    clickmap: true,
    ecommerce: 'dataLayer',
    accurateTrackBounce: true,
    trackLinks: true,
  });
  initialized = true;
}


export function trackPageView(url, referer, title, win = window) {
  if (!initialized || lastTrackedUrl === url) return false;
  win.ym(METRIKA_ID, 'hit', url, { referer, title });
  lastTrackedUrl = url;
  return true;
}


export function resetMetrikaForTests() {
  initialized = false;
  lastTrackedUrl = null;
}
