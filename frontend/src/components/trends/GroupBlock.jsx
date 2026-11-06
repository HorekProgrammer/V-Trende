import { useEffect, useRef } from 'react';
import './GroupBlock.css';
import MiniCard from './MiniCard';
import LegendRow from './LegendRow';

export default function GroupBlock({ id, title, description, items, onItemClick, variant, icon })
{
  const maxWeeks = Math.max(...items.map((item) => item.weeks));
  const cardRowRef = useRef(null);
  const isCarousel = id === 'group-global';

  useEffect(() =>
  {
    if (!isCarousel || items.length === 0)
    {
      return;
    }

    const container = cardRowRef.current;

    if (!container)
    {
      return;
    }

    const sets = container.querySelectorAll('.carousel-set');

    if (sets.length !== 3 || sets[0].offsetWidth <= 0)
    {
      return;
    }

    container.scrollLeft = sets[0].offsetWidth;

    let timer = null;

    const recenter = () =>
    {
      const setWidth = sets[0].offsetWidth;

      if (setWidth <= 0)
      {
        return;
      }

      const half = setWidth / 2;
      const current = container.scrollLeft;
      const normalized = half + ((((current - half) % setWidth) + setWidth) % setWidth);

      if (Math.abs(normalized - current) > 0.5)
      {
        container.scrollLeft = normalized;
      }
    };

    const handleScroll = () =>
    {
      const maxScroll = container.scrollWidth - container.clientWidth;

      if (container.scrollLeft <= 1 || container.scrollLeft >= maxScroll - 1)
      {
        recenter();
        return;
      }

      clearTimeout(timer);
      timer = setTimeout(recenter, 140);
    };

    container.addEventListener('scroll', handleScroll, { passive: true });

    return () =>
    {
      container.removeEventListener('scroll', handleScroll);
      clearTimeout(timer);
    };
  }, [isCarousel, items]);

  const scrollCarousel = (direction) =>
  {
    const container = cardRowRef.current;

    if (!container)
    {
      return;
    }

    const firstCard = container.querySelector('.mini-card');

    if (!firstCard)
    {
      return;
    }

    const containerStyles = window.getComputedStyle(container);
    const cardWidth = firstCard.getBoundingClientRect().width;
    const gap = parseFloat(containerStyles.columnGap) || 0;
    const step = cardWidth + gap;

    container.scrollBy(
    {
      left: direction === 'next' ? step : -step,
      behavior: 'smooth'
    });
  };

  const renderCards = (setIndex) =>
  {
    return (
      <div className="carousel-set" key={setIndex}>
        {items.map((item, index) => (
          <MiniCard
            key={`${setIndex}-${item.key || index}`}
            item={item}
            onClick={() => onItemClick?.(item)}
          />
        ))}
      </div>
    );
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
          {isCarousel ? (
            <>
              {renderCards(0)}
              {renderCards(1)}
              {renderCards(2)}
            </>
          ) : (
            items.map((item) => (
              <MiniCard
                key={item.key}
                item={item}
                onClick={() => onItemClick?.(item)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}