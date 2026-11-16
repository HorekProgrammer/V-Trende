export function initialApiResult(path, initialData) {
  const data = initialData?.[path];
  return data
    ? { path, data, error: null }
    : { path: null, data: null, error: null };
}


export function apiFailureResult(current, path, error) {
  if (current.path === path && current.data) return current;
  return { path, data: null, error };
}
