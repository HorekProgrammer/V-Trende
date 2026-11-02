import { formatDate } from '../../utils/dates';
import './StatGrid.css';

function firstAndPeak(history) 
{
  const ranked = (history || [])
    .filter((p) => p.rank != null)
    .sort((a, b) => a.weekStart.localeCompare(b.weekStart));
  if (ranked.length === 0) return { first: null, peak: null };
  const peak = ranked.reduce((best, p) => (p.rank < best.rank ? p : best), ranked[0]);
  return { first: ranked[0], peak };
}

export default function StatGrid({ item }) 
{
  const { first, peak } = firstAndPeak(item.history);
  const stats = [
    { value: `#${item.rank}`, label: 'Текущая позиция' },
    { value: item.score == null ? '—' : item.score.toFixed(1), label: 'Итоговый рейтинг' },
    { value: `#${item.peak}`, note: peak ? formatDate(peak.weekStart) : null, label: 'Пиковая позиция' },
    { value: item.weeks, label: 'Недель в чарте' },
    { value: first ? `#${first.rank}` : '—', note: first ? formatDate(first.weekStart) : null, label: 'Дебют' },
  ];

  return (
    <div className="stat-grid">
      {stats.map((s) => (
        <div key={s.label} className="stat-box">
          <div className="stat-num">
            {s.value}
            {s.note && <span className="stat-note">{s.note}</span>}
          </div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  );
}