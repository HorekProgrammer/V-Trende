const BASE = '/api/v1';

export class ApiError extends Error 
{
  constructor(status, message) 
  {
    super(message);
    this.status = status;
  }
}

export async function apiGet(path, signal) 
{
  const res = await fetch(`${BASE}${path}`, { signal });

  if (!res.ok) 
    {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch 
    {
      // Если тело ответа не JSON, оставляем универсальное сообщение HTTP.
    }
    throw new ApiError(res.status, message);
  }

  return res.json();
}
