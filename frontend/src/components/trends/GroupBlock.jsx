import './GroupBlock.css';
import MiniCard from './MiniCard';
import LegendRow from './LegendRow';

export default function GroupBlock({id, title, description, items, onItemClick, variant, icon }) {
  const maxWeeks = Math.max(...items.map((item) => item.weeks));

  return (
    <div className="group-block" id={id}>
      <div className="group-head">
        <h2>{title}{icon}</h2>
      </div>
      {description && <p className="group-desc">{description}</p>}

      {variant === 'legend' ? 
      (
        <div className="legend-list">
          {items.map((item) => 
          (
            <LegendRow
              key={item.key}
              item={item}
              maxWeeks={maxWeeks}
              onClick={() => onItemClick?.(item)}
            />
          ))}
        </div>
      ) : variant === 'grid' ? (
        <div className="grid-2col">
          {items.map((item) => (
            <MiniCard
              key={item.key}
              item={item}
              onClick={() => onItemClick?.(item)}
            />
          ))}
        </div>
      ) : (
        <div className="card-row">
          {items.map((item) => (
            <MiniCard
              key={item.key}
              item={item}
              onClick={() => onItemClick?.(item)}
            />
          ))}
        </div>
      )}
    </div>
  );
}