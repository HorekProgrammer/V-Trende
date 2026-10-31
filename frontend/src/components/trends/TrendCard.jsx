import './TrendCard.css';
import { fmtSearches, subtitleWithYear } from '../../utils/trendFormat';
import Cover from '../common/Cover';


function TrendBadge({ prevRank, rank, isNew }) {
  if (isNew) return <span className="trend-badge trend-new">NEW</span>;
  if (prevRank == null) return <span className="trend-badge trend-flat">—</span>;
  const delta = prevRank - rank;
  if (delta > 0) return <span className="trend-badge trend-up">▲ {delta}</span>;
  if (delta < 0) return <span className="trend-badge trend-down">▼ {Math.abs(delta)}</span>;
  return <span className="trend-badge trend-flat">— 0</span>;
}

export default function TrendCard({ item, onClick }) {
  return (
    <div className="row-card" onClick={onClick}>
      <div className="row-rank">{item.rank}</div>
      <Cover item={item} className="row-cover" />
      <div className="row-info">
        <div className="row-title">{item.title}</div>
        <div className="row-sub">{subtitleWithYear(item)}</div>
      </div>
      <div className="row-views">
        {item.score == null ? fmtSearches(item.searchCount) : `${item.score.toFixed(1)} балла`}
      </div>
      <div className="row-trend">
           <TrendBadge prevRank={item.prevRank} rank={item.rank} isNew={item.isNew} />
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
