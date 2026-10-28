import { useState } from 'react';
import PeriodChips from './PeriodChips';
import PopularityChart from './PopularityChart';
import { PERIODS } from './periods';
import { formatWeek } from '../../utils/dates';
import './PopularityCard.css';

export default function PopularityCard({ history, topSize }) 
{
  const [periodId, setPeriodId] = useState('12w');
  const period = PERIODS.find((p) => p.id === periodId);

  const all = history
    .filter((point) => point.rank != null)
    .map((point) => ({
      weekStart: point.weekStart,
      value: point.rank,
      label: `${formatWeek(point.weekStart)}: #${point.rank}`,
    }));
  const points = period.points ? all.slice(-period.points) : all;

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div className="chart-title">Динамика позиции в чарте</div>
        {all.length > 0 && <PeriodChips value={periodId} onChange={setPeriodId} />}
      </div>

      {points.length === 0 ? (
        <div className="chart-empty">Пока нет данных для графика</div>
      ) : (
        <>
          <PopularityChart points={points} topSize={topSize} />
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