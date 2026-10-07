import './TrendCard.css';

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
  for (const c of seedStr) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COVER_GRADIENTS[h % COVER_GRADIENTS.length];
}

function initials(str) {
  return str.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

function fmtViews(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1).replace('.0', '') + ' млн просмотров';
  return Math.round(n / 1000) + ' тыс. просмотров';
}

function TrendBadge({ prevRank, rank }) {
  const delta = prevRank - rank;
  if (delta > 0) return <span className="trend-badge trend-up">▲ {delta}</span>;
  if (delta < 0) return <span className="trend-badge trend-down">▼ {Math.abs(delta)}</span>;
  return <span className="trend-badge trend-flat">— 0</span>;
}

export default function TrendCard({ item, onClick }) {
  return (
    <div className="row-card" onClick={onClick}>
      <div className="row-rank">{item.rank}</div>
      <div className="row-cover" style={{ background: coverGrad(item.key) }}>
        {initials(item.title)}
      </div>
      <div className="row-info">
        <div className="row-title">{item.title}</div>
        <div className="row-sub">{item.subtitle}</div>
      </div>
      <div className="row-views">{fmtViews(item.views)}</div>
      <div className="row-trend">
        <TrendBadge prevRank={item.prevRank} rank={item.rank} />
      </div>
      <div className="row-arrow">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
          <path
            d="M9 6l6 6-6 6"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}