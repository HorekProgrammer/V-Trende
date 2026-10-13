import { PERIODS } from './periods';

export default function PeriodChips({ value, onChange }) 
{
  return (
    <div className="period-chips">
      {PERIODS.map((p) => (
        <button
          key={p.days}
          type="button"
          className={`period-chip ${p.days === value ? 'is-active' : ''}`}
          onClick={() => onChange(p.days)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}