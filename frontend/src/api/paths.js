export const feedPath = () => '/feed';

export const categoryTrendsPath = (category, sort) =>
  `/categories/${encodeURIComponent(category)}/trends?sort=${sort}&limit=100`;

export const trendPath = (id) => `/trends/${encodeURIComponent(id)}`;