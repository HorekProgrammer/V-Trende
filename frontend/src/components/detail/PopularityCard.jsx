import PopularityChart from './PopularityChart';
import { formatWeek } from '../../utils/dates';
import './PopularityCard.css';

export default function PopularityCard({ history, topSize })
{
  const points = history
    .map((point) => ({
      weekStart: point.weekStart,
      value: point.rank ?? topSize + 1,
      isOutside: point.rank == null,
      dateLabel: formatWeek(point.weekStart),
      label: point.rank == null
        ? `${formatWeek(point.weekStart)}: вне топ-${topSize}`
        : `${formatWeek(point.weekStart)}: #${point.rank}`,
    }));

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div className="chart-title">Динамика позиции в чарте</div>
      </div>

      {points.length === 0 ? (
        <div className="chart-empty">Пока нет данных для графика</div>
      ) : (
        <>
          <PopularityChart points={points} outsideValue={topSize + 1} topSize={topSize} />
          {points.length > 1 && (
            <div className="chart-foot">
              <span>{formatWeek(points[0].weekStart)}</span>
              <span>{formatWeek(points[points.length - 1].weekStart)}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
