import { coverGrad, initials } from '../../utils/trendFormat';
import { CATEGORY_THEMES } from '../category/categoryThemes';
import './DetailHero.css';

export default function DetailHero({ item, category }) {
  const theme = CATEGORY_THEMES[category.id];

  return (
    <div className="detail-hero">
      <div className="detail-cover" style={{ background: coverGrad(item.key) }}>
        {initials(item.title)}
      </div>
      <div className="detail-meta">
        <div className="detail-tags">
          <span
            className="detail-tag detail-tag--category"
            style={{ color: theme.c1, borderColor: theme.c1, background: `${theme.c1}1F` }}
          >
            {category.label}
          </span>
          <span className="detail-tag">{item.genre}</span>
        </div>
        <h1 className="detail-title">{item.title}</h1>
        <div className="detail-sub">{item.subtitle}</div>
      </div>
    </div>
  );
}