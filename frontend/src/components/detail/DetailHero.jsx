import { useState } from 'react';
import Cover from '../common/Cover';
import CoverViewer from '../common/CoverViewer';
import { CATEGORY_THEMES } from '../category/categoryThemes';
import './DetailHero.css';

export default function DetailHero({ item, category }) 
{
  const theme = CATEGORY_THEMES[category.id];
  const [viewerOpen, setViewerOpen] = useState(false);

  const cover = <Cover item={item} className="detail-cover" />;

  return (
    <div className="detail-hero">
      {item.cover ? (
        <button
          type="button"
          className="detail-cover-btn"
          onClick={() => setViewerOpen(true)}
          aria-label="Открыть обложку"
        >
          {cover}
        </button>
      ) : (
        cover
      )}
      {viewerOpen && (
        <CoverViewer
          src={item.cover}
          title={item.title}
          onClose={() => setViewerOpen(false)}
        />
      )}
      <div className="detail-meta">
        <div className="detail-tags">
          <span
            className="detail-tag detail-tag--category"
            style={{ color: theme.c1, borderColor: theme.c1, background: `${theme.c1}1F` }}
          >
            {category.label}
          </span>
          {item.genre && <span className="detail-tag">{item.genre}</span>}
        </div>
        <h1 className="detail-title">{item.title}</h1>
        <div className="detail-sub">{item.subtitle}</div>
      </div>
    </div>
  );
}