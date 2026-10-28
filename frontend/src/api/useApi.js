import { useEffect, useState } from 'react';
import { apiGet } from './client';


export function useApi(path) 
{
  const [result, setResult] = useState({ path: null, data: null, error: null });

  useEffect(() => {
    if (!path) return undefined;

    const controller = new AbortController();
    apiGet(path, controller.signal)
      .then((data) => setResult({ path, data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setResult({ path, data: null, error });
      });

    return () => controller.abort();
  }, [path]);

  const ready = result.path === path;
  return {
    data: result.data,
    error: ready ? result.error : null,
    loading: Boolean(path) && !ready,
  };
}