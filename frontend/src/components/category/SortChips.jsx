import { SORTS } from './sortOptions';

export default function SortChips({ value, onChange }) 
{
  return (
    <div role="radiogroup" aria-label="Сортировка">
      {SORTS.map((s) => (
        <button
          key={s.id}
          type="button"
          role="radio"
          aria-checked={s.id === value}
          className={`sort-chip ${s.id === value ? 'is-active' : ''}`}
          onClick={() => onChange(s.id)}
        >
          <span className="ring" />
          {s.label}
        </button>
      ))}
    </div>
  );
}