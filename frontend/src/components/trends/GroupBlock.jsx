import { useRef } from 'react';
import './GroupBlock.css';
import MiniCard from './MiniCard';
import LegendRow from './LegendRow';

export default function GroupBlock({ id, title, description, items, onItemClick, variant, icon })
{
  const maxWeeks = Math.max(...items.map((item) => item.weeks));
  const cardRowRef = useRef(null);
  const isCarousel = id === 'group-global';

  const scrollCarousel = (direction) =>
  {
    const container = cardRowRef.current;

    if (!container)
    {
      return;
    }

    const maxScroll = container.scrollWidth - container.clientWidth;

    if (maxScroll <= 0)
    {
      return;
    }

    const firstCard = container.querySelector('.mini-card');

    if (!firstCard)
    {
      return;
    }

    const styles = window.getComputedStyle(container);
    const gap = parseFloat(styles.columnGap) || 0;
    const step = firstCard.offsetWidth + gap;

    if (direction === 'next')
    {
      if (container.scrollLeft >= maxScroll - 2)
      {
        container.scrollTo({ left: 0, behavior: 'smooth' });
      }
      else
      {
        container.scrollBy({ left: step, behavior: 'smooth' });
      }
    }
    else
    {
      if (container.scrollLeft <= 2)
      {
        container.scrollTo({ left: maxScroll, behavior: 'smooth' });
      }
      else
      {
        container.scrollBy({ left: -step, behavior: 'smooth' });
      }
    }
  };

  return (
    <div className={`group-block ${isCarousel ? 'group-block--carousel' : ''}`} id={id}>
      <div className="group-head">
        <h2>{title}{icon}</h2>

        {isCarousel && (
          <div className="carousel-controls">
            <button
              type="button"
              className="carousel-arrow"
              aria-label="Предыдущая карточка"
              onClick={() => scrollCarousel('prev')}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M15 18L9 12L15 6" />
              </svg>
            </button>

            <button
              type="button"
              className="carousel-arrow"
              aria-label="Следующая карточка"
              onClick={() => scrollCarousel('next')}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M9 18L15 12L9 6" />
              </svg>
            </button>
          </div>
        )}
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
        <div className="card-row" ref={isCarousel ? cardRowRef : null}>
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