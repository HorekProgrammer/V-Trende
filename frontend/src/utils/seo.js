const SITE_URL = 'https://vcharte.com';

function upsertMeta(selector, attributes) {
  let element = document.head.querySelector(selector);
  if (!element) {
    element = document.createElement(attributes.rel ? 'link' : 'meta');
    document.head.appendChild(element);
  }
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
}

export function setPageMetadata({ title, description, path }) {
  document.title = title;
  upsertMeta('meta[name="description"]', { name: 'description', content: description });
  upsertMeta('link[rel="canonical"]', { rel: 'canonical', href: `${SITE_URL}${path}` });
}
