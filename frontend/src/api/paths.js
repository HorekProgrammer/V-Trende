const withWeek = (path, week) =>
  week ? `${path}${path.includes('?') ? '&' : '?'}week=${encodeURIComponent(week)}` : path;

export const weeksPath = () => '/weeks';

export const feedPath = (week) => withWeek('/feed', week);

export const categoryTrendsPath = (category, sort, week) =>
  withWeek(`/categories/${encodeURIComponent(category)}/trends?sort=${sort}&limit=100`, week);

export const trendPath = (id) => `/trends/${encodeURIComponent(id)}`;