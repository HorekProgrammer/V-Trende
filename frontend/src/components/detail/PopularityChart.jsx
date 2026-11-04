import { W, H, PAD_L, PAD_R, PAD_T, INNER_H, chartTop, chartBottom, chartCoords, rankY, axisRanks } from './chartMath';

export default function PopularityChart({ points }) 
{
  const values = points.map((p) => p.value);
  const top = chartTop(values);
  const bottom = chartBottom(values, top);
  const coords = chartCoords(values, top, bottom);

  const linePath = coords
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');

  const baseY = PAD_T + INNER_H;
  const first = coords[0];
  const last = coords[coords.length - 1];
  const areaPath = `${linePath} L${last[0].toFixed(1)},${baseY} L${first[0].toFixed(1)},${baseY} Z`;

  const ranks = axisRanks(top, bottom);

  return (
    <div className="chart-plot">
      <div className="chart-axis">
        {ranks.map((r) => (
          <span key={r} style={{ top: rankY(r, top, bottom) }}>
            #{r}
          </span>
        ))}
      </div>

      <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FF7A29" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#FF7A29" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#FF7A29" />
            <stop offset="100%" stopColor="#D62828" />
          </linearGradient>
        </defs>

        {ranks.map((r) => {
          const y = rankY(r, top, bottom);
          return (
            <line key={r} x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} style={{ stroke: 'var(--border)' }} strokeWidth="1" />
          );
        })}

        <path d={areaPath} fill="url(#areaGrad)" />
        <path
          d={linePath}
          fill="none"
          stroke="url(#lineGrad)"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {coords.map(([x, y], i) => (
          <circle
            key={points[i].weekStart}
            cx={x}
            cy={y}
            r="3.5"
            style={{ fill: 'var(--chart-dot)' }}
            stroke="#FF7A29"
            strokeWidth="2"
          >
            <title>{points[i].label}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}