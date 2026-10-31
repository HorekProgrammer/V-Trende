const COVER_GRADIENTS = 
[
  'linear-gradient(135deg, #FF7A29, #D62828)',
  'linear-gradient(135deg, #29E1B5, #2B6CF6)',
  'linear-gradient(135deg, #F2B84B, #D62828)',
  'linear-gradient(135deg, #2B6CF6, #FF7A29)',
  'linear-gradient(135deg, #D62828, #F2B84B)',
  'linear-gradient(135deg, #29E1B5, #FF7A29)',
];

export function coverGrad(seedStr) 
{
  let h = 0;
  for (const c of seedStr) {
    h = (h * 31 + c.charCodeAt(0)) >>> 0;
  }
  return COVER_GRADIENTS[h % COVER_GRADIENTS.length];
}

export function initials(str) 
{
  return str.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

export function fmtSearches(n) 
{
  if (n == null) return '';
  if (n >= 1000000) return (n / 1000000).toFixed(1).replace('.0', '') + ' млн запросов';
  if (n >= 1000) return Math.round(n / 1000) + ' тыс. запросов';
  return n + ' запросов';
}
export function subtitleWithYear(item) 
{
  const parts = item.subtitle ? [item.subtitle] : [];
  if (item.year && String(item.year) !== item.subtitle) parts.push(item.year);
  return parts.join(' · ');
}
