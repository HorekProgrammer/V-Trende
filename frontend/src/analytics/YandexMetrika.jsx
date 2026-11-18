import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import {
  loadYandexMetrika,
  trackPageView,
} from './metrika';


function PageViewTracker() {
  const location = useLocation();
  const previousUrl = useRef(document.referrer || '');
  const hasTrackedPage = useRef(false);

  useEffect(() => {
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
  }, [location.key, location.pathname, location.search]);

  return null;
}


export default function YandexMetrika() {
  return <PageViewTracker />;
}
