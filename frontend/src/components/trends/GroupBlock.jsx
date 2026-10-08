import './GroupBlock.css';
import MiniCard from './MiniCard';

export default function GroupBlock({ title, description, items, onItemClick, variant }) {
  return (
    <div className="group-block">
      <div className="group-head">
        <h2>{title}</h2>
      </div>
      {description && <p className="group-desc">{description}</p>}

      {variant === 'grid' ? (
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