const W = 640;
const H = 220;
const PAD_L = 8;
const PAD_R = 8;
const PAD_T = 18;
const PAD_B = 26;
const INNER_W = W - PAD_L - PAD_R;
const INNER_H = H - PAD_T - PAD_B;
const MAX = 100;
const MIN = 0;

export default function PopularityChart({ points }) {
  const coords = points.map((v, i) => {
    const x = points.length === 1 ? PAD_L : PAD_L + (i / (points.length - 1)) * INNER_W;
    const y = PAD_T + INNER_H - ((v - MIN) / (MAX - MIN)) * INNER_H;
    return [x, y];
  });

  const linePath = coords
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');

  const baseY = PAD_T + INNER_H;
  const first = coords[0];
  const last = coords[coords.length - 1];
  const areaPath = `${linePath} L${last[0].toFixed(1)},${baseY} L${first[0].toFixed(1)},${baseY} Z`;

  const gridYs = [0, 1, 2, 3].map((i) => PAD_T + (INNER_H / 3) * i);

  return (
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

      {gridYs.map((y) => (
        <line key={y} x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} stroke="#2A2534" strokeWidth="1" />
      ))}

      <path d={areaPath} fill="url(#areaGrad)" />
      <path
        d={linePath}
        fill="none"
        stroke="url(#lineGrad)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {coords.map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r="3.5" fill="#0B0A10" stroke="#FF7A29" strokeWidth="2" />
      ))}
    </svg>
  );
}