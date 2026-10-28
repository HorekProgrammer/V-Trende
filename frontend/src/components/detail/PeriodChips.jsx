import { PERIODS } from './periods';

export default function PeriodChips({ value, onChange }) 
{
  return (
    <div className="period-chips">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          type="button"
          className={`period-chip ${p.id === value ? 'is-active' : ''}`}
          onClick={() => onChange(p.id)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}