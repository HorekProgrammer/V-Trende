import { formatDate } from '../../utils/dates';
import './StatGrid.css';

function firstAndPeak(history, selectedWeek)
{
  const ranked = (history || [])
    .filter((p) => p.rank != null && (!selectedWeek || p.weekStart <= selectedWeek))
    .sort((a, b) => a.weekStart.localeCompare(b.weekStart));
  if (ranked.length === 0) return { first: null, peak: null };
  const peak = ranked.reduce((best, p) => (p.rank < best.rank ? p : best), ranked[0]);
  return { first: ranked[0], peak };
}

function formatScore(value)
{
  return Number(value).toFixed(2);
}

function ratingFormula(item)
{
  if (item.score == null || item.sourceScore == null || item.wordstatScore == null) return null;

  const source = formatScore(item.sourceScore);
  const extra = formatScore(item.wordstatScore);
  const result = item.score.toFixed(1);

  const components = item.scoreBreakdown?.components || [];
  const lines = components.map((component) => ({
    label: component.label,
    value: component.position == null
      ? formatScore(component.value)
      : `Позиция: #${component.position} → ${formatScore(component.value)} балла`,
  }));

  if (item.sphere === 'games') return {
    lines,
    formula: `Лучший результат: ${source} × 65% + Whatstat: ${extra} × 35% = ${result}`,
  };

  const sourceLabels = {
    music: 'Музыкальные чарты',
    movies: 'Кинопоиск',
    streamers: 'TwitchTracker',
  };
  if (components.length && item.sphere !== 'streamers') {
    const weighted = components
      .map((component) => `${formatScore(component.value)} × ${Math.round(component.weight * 100)}%`)
      .join(' + ');
    const weightSum = components.reduce((sum, component) => sum + component.weight, 0);
    lines.push({
      label: 'Баллы источников',
      value: weightSum === 1 ? `${weighted} = ${source}` : `(${weighted}) ÷ ${(weightSum * 100).toFixed(0)}% = ${source}`,
    });
  } else if (components.length) {
    const weighted = components
      .map((component) => `${formatScore(component.value)} × ${Math.round(component.weight * 100)}%`)
      .join(' + ');
    lines.push({ label: 'Баллы TwitchTracker', value: `${weighted} = ${source}` });
  }

  return {
    lines,
    formula: `${sourceLabels[item.sphere] || 'Источники'}: ${source} × 97% + Wordstat: ${extra} × 3% = ${result}`,
  };
}

function RatingInfo({ breakdown })
{
  if (!breakdown) return null;

  return (
    <span className="rating-info">
      <button className="rating-info-button" type="button" aria-label={`Формула итогового рейтинга: ${breakdown.formula}`}>i</button>
      <span className="rating-info-tooltip" role="tooltip">
        {breakdown.lines.map((line) => (
          <span className="rating-info-line" key={`${line.label}-${line.value}`}>
            <span>{line.label}</span>
            <strong>{line.value}</strong>
          </span>
        ))}
        <strong className="rating-info-formula">{breakdown.formula}</strong>
      </span>
    </span>
  );
}

export default function StatGrid({ item }) 
{
  const { first, peak } = firstAndPeak(item.history, item.weekStart);
  const stats = [
    { value: item.rank == null ? 'Вне чарта' : `#${item.rank}`, label: 'Текущая позиция' },
    {
      value: item.score == null ? '—' : item.score.toFixed(1),
      label: 'Итоговый рейтинг',
      breakdown: ratingFormula(item),
    },
    { value: item.peak == null ? '—' : `#${item.peak}`, note: peak ? formatDate(peak.weekStart) : null, label: 'Пиковая позиция' },
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
          <div className="stat-label">
            {s.label}
            <RatingInfo breakdown={s.breakdown} />
          </div>
        </div>
      ))}
    </div>
  );
}
