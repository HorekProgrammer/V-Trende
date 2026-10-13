import { useState } from 'react';
import PeriodChips from './PeriodChips';
import PopularityChart from './PopularityChart';
import { PERIODS } from './periods';
import './PopularityCard.css';

export default function PopularityCard({ item }) 
{
  const [days, setDays] = useState(90);
  const period = PERIODS.find((p) => p.days === days);
  const points = item.history.slice(-period.points);

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div className="chart-title">
          Динамика популярности <span>· последние {period.days} дней</span>
        </div>
        <PeriodChips value={days} onChange={setDays} />
      </div>

      <PopularityChart points={points} />

      <div className="chart-foot">
        <span>{period.footLeft}</span>
        <span>Сегодня</span>
      </div>
    </div>
  );
}