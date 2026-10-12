import { themeGrad } from './categoryThemes';
import './CategoryHero.css';

function CalendarIcon() 
{
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="2" />
      <path d="M3 10h18M8 3v4M16 3v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function CategoryHero({ label, theme, period }) 
{
  return (
    <div className="cat-hero">
      <div className="cat-hero-icon" style={{ background: themeGrad(theme) }}>
        <img src={theme.icon} alt="" />
      </div>
      <div className="cat-title-row">
        <h1 className="cat-title">{label}</h1>
        <div className="period-pill">
          <CalendarIcon />
          {period}
        </div>
      </div>
    </div>
  );
}