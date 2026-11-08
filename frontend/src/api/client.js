const BASE = '/api/v1';

export class ApiError extends Error 
{
  constructor(status, message, fields = {}) 
  {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

async function toApiError(res) 
{
  let message = `HTTP ${res.status}`;
  let fields = {};
  try 
  {
    const body = await res.json();
    if (typeof body.detail === 'string') message = body.detail;
    else if (body.detail && typeof body.detail.message === 'string') 
    {
      message = body.detail.message;
      if (body.detail.fields && typeof body.detail.fields === 'object') fields = body.detail.fields;
    }
  } catch 
  {
  }
  return new ApiError(res.status, message, fields);
}

export async function apiGet(path, signal) 
{
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

export async function apiPost(path, data) 
{
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}
