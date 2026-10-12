import musicIcon from '../../assets/icons/music.png';
import moviesIcon from '../../assets/icons/movies.png';
import gamesIcon from '../../assets/icons/games.png';
import streamersIcon from '../../assets/icons/streamers.png';

export const CATEGORY_THEMES = 
{
  music:     { c1: '#2B9EFF', c2: '#29E1B5', icon: musicIcon },
  movies:    { c1: '#A855F7', c2: '#4C1D95', icon: moviesIcon },
  games:     { c1: '#FF5959', c2: '#FF2D55', icon: gamesIcon },
  streamers: { c1: '#FF3D8A', c2: '#FFB020', icon: streamersIcon },
};

function hexA(hex, a) 
{
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

export function themeGrad({ c1, c2 }) 
{
  return `linear-gradient(135deg, ${c1}, ${c2})`;
}

export function themeWash({ c1, c2 }) 
{
  return `radial-gradient(60% 55% at 12% 8%, ${hexA(c1, 0.26)}, transparent 70%),
    radial-gradient(50% 50% at 88% 22%, ${hexA(c2, 0.22)}, transparent 70%),
    radial-gradient(55% 50% at 70% 88%, ${hexA(c1, 0.18)}, transparent 70%),
    radial-gradient(45% 45% at 15% 80%, ${hexA(c2, 0.16)}, transparent 70%),
    var(--bg)`;
}