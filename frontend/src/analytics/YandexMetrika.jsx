import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  ANALYTICS_CONSENT_KEY,
  loadYandexMetrika,
  trackPageView,
} from './metrika';
import './YandexMetrika.css';


function readConsent() {
  try {
    return localStorage.getItem(ANALYTICS_CONSENT_KEY);
  } catch {
    return null;
  }
}


function saveConsent(value) {
  try {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, value);
  } catch {
    // The choice still applies to the current page when storage is unavailable.
  }
}


function PageViewTracker({ enabled }) {
  const location = useLocation();
  const previousUrl = useRef(document.referrer || '');
  const hasTrackedPage = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;

    loadYandexMetrika();
    const currentUrl = window.location.href;
    const referer = previousUrl.current;
    let observer = null;
    let timer = null;
    const send = () => {
      if (trackPageView(currentUrl, referer, document.title)) {
        previousUrl.current = currentUrl;
        hasTrackedPage.current = true;
      }
      observer?.disconnect();
      if (timer != null) window.clearTimeout(timer);
    };

    if (!hasTrackedPage.current) {
      timer = window.setTimeout(send, 0);
    } else {
      observer = new MutationObserver(send);
      observer.observe(document.querySelector('title'), { childList: true });
      timer = window.setTimeout(send, 5000);
    }

    return () => {
      observer?.disconnect();
      if (timer != null) window.clearTimeout(timer);
    };
  }, [enabled, location.key, location.pathname, location.search]);

  return null;
}


export default function YandexMetrika() {
  const [consent, setConsent] = useState(readConsent);
  const enabled = consent === 'accepted';

  const choose = (value) => {
    saveConsent(value);
    setConsent(value);
  };

  return (
    <>
      <PageViewTracker enabled={enabled} />
      {consent == null && (
        <aside className="analytics-consent" aria-label="Настройки аналитики">
          <p>
            С вашего согласия мы используем Яндекс Метрику для статистики
            посещений. Сервис применяет аналитические cookie и данные о
            взаимодействии с сайтом; дополнительные сведения о пользователе мы
            в Метрику не передаём.
          </p>
          <div className="analytics-consent__actions">
            <button type="button" onClick={() => choose('declined')}>
              Только необходимые
            </button>
            <button type="button" className="is-primary" onClick={() => choose('accepted')}>
              Разрешить аналитику
            </button>
          </div>
        </aside>
      )}
    </>
  );
}
