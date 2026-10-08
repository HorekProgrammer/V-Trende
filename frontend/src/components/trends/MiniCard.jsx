import './MiniCard.css';

const COVER_GRADIENTS = [
  'linear-gradient(135deg, #FF7A29, #D62828)',
  'linear-gradient(135deg, #29E1B5, #2B6CF6)',
  'linear-gradient(135deg, #F2B84B, #D62828)',
  'linear-gradient(135deg, #2B6CF6, #FF7A29)',
  'linear-gradient(135deg, #D62828, #F2B84B)',
  'linear-gradient(135deg, #29E1B5, #FF7A29)',
];

function coverGrad(seedStr) {
  let h = 0;
  for (const c of seedStr) {
    h = (h * 31 + c.charCodeAt(0)) >>> 0;
  }
  return COVER_GRADIENTS[h % COVER_GRADIENTS.length];
}

function initials(str) {
  return str.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

function fmtViews(n) {
  if (n >= 1000000) {
    return (n / 1000000).toFixed(1).replace('.0', '') + ' млн просмотров';
  }
  return Math.round(n / 1000) + ' тыс. просмотров';
}

export default function MiniCard({ item, onClick }) {
  return (
    <div className="mini-card" onClick={onClick}>
      <div className="mini-cover" style={{ background: coverGrad(item.key) }}>
        {initials(item.title)}
      </div>
      <div className="mini-body">
        <div className="mini-tag">{item.categoryLabel || item.sphere}</div>
        <div className="mini-title">{item.title}</div>
        <div className="mini-sub">{item.subtitle}</div>
        <div className="mini-views">{fmtViews(item.views)}</div>
      </div>
    </div>
  );
}