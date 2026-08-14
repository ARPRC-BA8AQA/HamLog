let csrfToken = null;

async function getCsrfToken() {
  if (csrfToken) return csrfToken;
  const response = await fetch('/api/auth/csrf', {method: 'POST'});
  const result = await response.json();
  csrfToken = result.data.csrf_token;
  return csrfToken;
}

async function post(path, body = {}) {
  const headers = {'Content-Type': 'application/json'};
  if (!['/auth/csrf', '/auth/login', '/auth/refresh', '/auth/status'].includes(path)) headers['X-CSRF-Token'] = await getCsrfToken();
  const response = await fetch('/api' + path, { method: 'POST', headers, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok || result.code !== 200) throw new Error(result.msg || '请求失败');
  return result.data;
}
