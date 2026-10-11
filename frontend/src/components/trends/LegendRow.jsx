import './LegendRow.css';

const COVER_GRADIENTS = 
[
  'linear-gradient(135deg, #FF7A29, #D62828)',
  'linear-gradient(135deg, #29E1B5, #2B6CF6)',
  'linear-gradient(135deg, #F2B84B, #D62828)',
  'linear-gradient(135deg, #2B6CF6, #FF7A29)',
  'linear-gradient(135deg, #D62828, #F2B84B)',
  'linear-gradient(135deg, #29E1B5, #FF7A29)',
];

function coverGrad(seedStr)
 {
  let h = 0;
  for (const c of seedStr) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COVER_GRADIENTS[h % COVER_GRADIENTS.length];
}

function initials(str) 
{
  return str.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
}

export default function LegendRow({ item, maxWeeks, onClick }) 
{
  const percent = Math.round((item.weeks / maxWeeks) * 100);

  return (
    <div className="legend-row" onClick={onClick}>
      <div className="legend-cover" style={{ background: coverGrad(item.key) }}>
        {initials(item.title)}
      </div>
      <div className="legend-info">
        <div className="legend-title">{item.title}</div>
        <div className="legend-sub">
          <span className="legend-chip">{item.categoryLabel}</span>
          <span className="legend-sub-text">{item.subtitle}</span>
        </div>
      </div>
      <div className="legend-bar-wrap">
        <div className="legend-bar-track">
          <div className="legend-bar-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>
      <div className="legend-weeks">{item.weeks} нед. в топе</div>
    </div>
  );
}