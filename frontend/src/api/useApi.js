import { useEffect, useState } from 'react';
import { apiGet } from './client';
import { apiFailureResult, initialApiResult } from './initialData';


export function useApi(path) 
{
  const [result, setResult] = useState(() => {
    return initialApiResult(path, window.__VCHARTE_INITIAL_DATA__);
  });

  useEffect(() => {
    if (!path) return undefined;

    const controller = new AbortController();
    apiGet(path, controller.signal)
      .then((data) => setResult({ path, data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setResult((current) => {
          // The home snapshot was generated from the same live feed as this
          // request. Keep it visible if the repeated API request temporarily
          // fails for a crawler or a regular user.
          return apiFailureResult(current, path, error);
        });
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
