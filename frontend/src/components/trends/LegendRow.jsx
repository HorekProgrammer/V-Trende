import Cover from '../common/Cover';
import { subtitleWithYear } from '../../utils/trendFormat';
import './LegendRow.css';


export default function LegendRow({ item, maxWeeks, onClick }) 
{
  const percent = Math.round((item.weeks / maxWeeks) * 100);

  return (
    <div className="legend-row" onClick={onClick}>
      <Cover item={item} className="legend-cover" />
      <div className="legend-info">
        <div className="legend-title">{item.title}</div>
        <div className="legend-sub">
          <span className="legend-chip">{item.categoryLabel}</span>
          <span className="legend-sub-text">{subtitleWithYear(item)}</span>
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