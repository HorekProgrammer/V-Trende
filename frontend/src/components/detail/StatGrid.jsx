import { fmtViews } from '../../utils/trendFormat';
import './StatGrid.css';

export default function StatGrid({ item }) 
{
  const [viewsNum, ...viewsLabel] = fmtViews(item.views).split(' ');

  const stats = 
  [
    { value: `#${item.rank}`, label: 'Текущая позиция' },
    { value: `#${item.peak}`, label: 'Пиковая позиция' },
    { value: item.weeks, label: 'Недель в чарте' },
    { value: viewsNum, label: viewsLabel.join(' ') },
  ];

  return (
    <div className="stat-grid">
      {stats.map((s) => (
        <div key={s.label} className="stat-box">
          <div className="stat-num">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  );
}