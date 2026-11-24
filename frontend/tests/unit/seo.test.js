import { beforeEach, describe, expect, it } from 'vitest';
import { setPageMetadata } from '../../src/utils/seo';

describe('setPageMetadata', () => {
  beforeEach(() => {
    document.head.innerHTML = '<title>Старая страница</title>';
  });

  it('updates title, description and canonical without duplicating tags', () => {
    const metadata = {
      title: 'Топ игр недели | В ЧАРТЕ',
      description: 'Рейтинг популярных игр.',
      path: '/category/games',
    };
    setPageMetadata(metadata);
    setPageMetadata(metadata);

    expect(document.title).toBe(metadata.title);
    expect(document.querySelectorAll('meta[name="description"]')).toHaveLength(1);
    expect(document.querySelector('meta[name="description"]')).toHaveAttribute('content', metadata.description);
    expect(document.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://vcharte.com/category/games'
    );
  });
});
