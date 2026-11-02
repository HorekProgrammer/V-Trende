import { useSearchParams } from 'react-router-dom';

const WEEK_RE = /^\d{4}-\d{2}-\d{2}$/;


export function useWeek() 
{
  const [params, setParams] = useSearchParams();
  const raw = params.get('week');
  const week = raw && WEEK_RE.test(raw) ? raw : null;

  const setWeek = (value) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set('week', value);
        else next.delete('week');
        return next;
      },
      { replace: true }
    );

  return [week, setWeek];
}