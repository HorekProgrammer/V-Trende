export const W = 640;
export const H = 220;
export const PAD_L = 8;
export const PAD_R = 8;
export const PAD_T = 18;
export const PAD_B = 26;
export const INNER_W = W - PAD_L - PAD_R;
export const INNER_H = H - PAD_T - PAD_B;

export function chartTop(values) 
{
  return Math.min(...values);
}

export function chartBottom(values, top) 
{
  return Math.max(top + 1, ...values);
}

export function rankY(rank, top, bottom) 
{
  if (!(bottom > top)) return PAD_T;
  const clamped = Math.min(Math.max(rank, top), bottom);
  return PAD_T + ((clamped - top) / (bottom - top)) * INNER_H;
}

export function chartCoords(values, top, bottom) 
{
  return values.map((rank, i) => {
    const x =
      values.length === 1
        ? PAD_L + INNER_W / 2
        : PAD_L + (i / (values.length - 1)) * INNER_W;
    return [x, rankY(rank, top, bottom)];
  });
}

export function axisRanks(top, bottom) 
{
  if (bottom - top < 5) 
  {
    return Array.from({ length: bottom - top + 1 }, (_, i) => top + i);
  }
  return [...new Set([top, Math.round((top + bottom) / 2), bottom])];
}