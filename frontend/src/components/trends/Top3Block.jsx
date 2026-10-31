import Cover from '../common/Cover';
import { subtitleWithYear } from '../../utils/trendFormat';
import './Top3Block.css';

export default function Top3Block({id, title, description, groups, onItemClick }) 
{
  return (
    <div className="group-block" id={id}>
      <div className="group-head">
        <h2>{title}</h2>
      </div>
      {description && <p className="group-desc">{description}</p>}

      <div className="top3-columns">
        {groups.map(({ category, items }) => (
          <div className="top3-col" key={category.id}>
            <div className="top3-col-head">{category.label}</div>
            {items.map((item) => (
              <div
                className="top3-item"
                key={item.key}
                onClick={() => onItemClick?.(item)}
              >
                <div className="top3-rank">{item.rank}</div>
                <Cover item={item} className="top3-cover" />
                <div className="top3-info">
                  <div className="top3-title">{item.title}</div>
                  <div className="top3-sub">{subtitleWithYear(item)}</div>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}