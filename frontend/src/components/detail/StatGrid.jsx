import { fmtSearches } from '../../utils/trendFormat';
import './StatGrid.css';

function searchStat(count) 
{
  if (count == null) return { value: '—', label: 'Запросов в поиске' };
  const [value, ...label] = fmtSearches(count).split(' ');
  return { value, label: label.join(' ') };
}

export default function StatGrid({ item }) 
{
  const stats = [
    { value: `#${item.rank}`, label: 'Текущая позиция' },
    { value: `#${item.peak}`, label: 'Пиковая позиция' },
    { value: item.weeks, label: 'Недель в чарте' },
    searchStat(item.searchCount),
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