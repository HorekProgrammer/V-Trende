import { formatWeek } from '../../utils/dates';
import './WeekSwitcher.css';

function Chevron({ dir }) 
{
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={dir === 'left' ? 'M15 6l-6 6 6 6' : 'M9 6l6 6-6 6'}
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function WeekSwitcher({ weeks, value, onChange }) 
{
  if (!weeks || weeks.length === 0) return null;

  const current = value && weeks.includes(value) ? value : weeks[0];
  const index = weeks.indexOf(current);
  const older = weeks[index + 1];
  const newer = weeks[index - 1];

  const select = (week) => onChange(week === weeks[0] ? null : week);

  return (
    <div className="week-switcher">
      <button
        type="button"
        className="week-arrow"
        onClick={() => select(older)}
        disabled={!older}
        aria-label="Предыдущая неделя"
      >
        <Chevron dir="left" />
      </button>

      <label className="week-label">
        <span>Неделя: {formatWeek(current)}</span>
        <select
          className="week-select"
          value={current}
          onChange={(event) => select(event.target.value)}
          aria-label="Выбрать неделю"
        >
          {weeks.map((week) => (
            <option key={week} value={week}>
              {formatWeek(week)}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        className="week-arrow"
        onClick={() => select(newer)}
        disabled={!newer}
        aria-label="Следующая неделя"
      >
        <Chevron dir="right" />
      </button>
    </div>
  );
}