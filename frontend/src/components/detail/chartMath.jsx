export const W = 640;
export const H = 220;
export const PAD_L = 8;
export const PAD_R = 8;
export const PAD_T = 18;
export const PAD_B = 26;
export const INNER_W = W - PAD_L - PAD_R;
export const INNER_H = H - PAD_T - PAD_B;

export function rankY(rank, topSize) 
{
  if (!(topSize > 1)) return PAD_T;
  const clamped = Math.min(Math.max(rank, 1), topSize);
  return PAD_T + ((clamped - 1) / (topSize - 1)) * INNER_H;
}

export function chartCoords(values, topSize) 
{
  return values.map((rank, i) => {
    const x =
      values.length === 1
        ? PAD_L + INNER_W / 2
        : PAD_L + (i / (values.length - 1)) * INNER_W;
    return [x, rankY(rank, topSize)];
  });
}

export function axisRanks(topSize) 
{
  return [...new Set([1, Math.round(topSize / 2), topSize])];
}