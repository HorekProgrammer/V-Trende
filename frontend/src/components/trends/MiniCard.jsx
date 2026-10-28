import './MiniCard.css';
import { coverGrad, initials, fmtSearches } from '../../utils/trendFormat';


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
        {(item.score != null || item.searchCount != null) && (
          <div className="mini-views">
            {item.score != null ? `Рейтинг: ${item.score.toFixed(1)}` : fmtSearches(item.searchCount)}
          </div>
        )}
      </div>
    </div>
  );
}
