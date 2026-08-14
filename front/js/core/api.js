(function () {
  const state = { accessToken: sessionStorage.getItem('hamlog.access') || '', refreshToken: sessionStorage.getItem('hamlog.refresh') || '', csrfToken: null };
  const publicPaths = new Set(['/auth/csrf', '/auth/login', '/auth/refresh', '/auth/status']);

  function setTokens(data) {
    if (data && Object.prototype.hasOwnProperty.call(data, 'access_token')) state.accessToken = data.access_token || '';
    if (data && Object.prototype.hasOwnProperty.call(data, 'refresh_token')) state.refreshToken = data.refresh_token || '';
    if (state.accessToken) sessionStorage.setItem('hamlog.access', state.accessToken); else sessionStorage.removeItem('hamlog.access');
    if (state.refreshToken) sessionStorage.setItem('hamlog.refresh', state.refreshToken); else sessionStorage.removeItem('hamlog.refresh');
  }

  async function readResponse(response) {
    const type = response.headers.get('content-type') || '';
    if (type.includes('application/json')) {
      const result = await response.json();
      if (!response.ok || result.code !== 200) {
        const error = new Error(result.msg || `请求失败 (${response.status})`);
        error.code = result.code || response.status;
        error.data = result.data;
        throw error;
      }
      return result.data;
    }
    if (!response.ok) throw new Error(`请求失败 (${response.status})`);
    return response.blob();
  }

  async function csrf() {
    if (state.csrfToken) return state.csrfToken;
    const response = await fetch('/api/auth/csrf', { method: 'POST', credentials: 'same-origin' });
    const result = await response.json();
    if (!response.ok || result.code !== 200) throw new Error(result.msg || '无法获取 CSRF 令牌');
    state.csrfToken = result.data && result.data.csrf_token;
    return state.csrfToken;
  }

  async function refresh() {
    if (!state.refreshToken) return false;
    try {
      const response = await fetch('/api/auth/refresh', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({refresh_token: state.refreshToken}), credentials: 'same-origin' });
      const result = await response.json();
      if (!response.ok || result.code !== 200) throw new Error('refresh failed');
      setTokens(result.data || {});
      return true;
    } catch (_) {
      setTokens({access_token: '', refresh_token: ''});
      return false;
    }
  }

  async function request(path, body, options, retried) {
    const opts = options || {};
    const isMultipart = opts.multipart === true;
    const headers = Object.assign({}, opts.headers || {});
    if (!isMultipart) headers['Content-Type'] = 'application/json';
    if (state.accessToken) headers.Authorization = `Bearer ${state.accessToken}`;
    if (!publicPaths.has(path) && !opts.skipCsrf) headers['X-CSRF-Token'] = await csrf();
    const response = await fetch('/api' + path, { method: 'POST', headers, body: isMultipart ? body : JSON.stringify(body || {}), credentials: 'same-origin' });
    if (response.status === 401 && !retried && await refresh()) {
      return request(path, body, options, true);
    }
    try {
      return await readResponse(response);
    } catch (error) {
      if (error.code === 401 && !retried && await refresh()) return request(path, body, options, true);
      throw error;
    }
  }

  async function post(path, body, options) { return request(path, body, options || {}, false); }
  async function download(path, body, filename) {
    const blob = await request(path, body, {});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = filename || 'hamlog-export'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return blob;
  }
  async function upload(path, formData) { return request(path, formData, {multipart: true}); }
  function clear() { setTokens({access_token: '', refresh_token: ''}); state.csrfToken = null; }
  function tokenState() { return {accessToken: state.accessToken, refreshToken: state.refreshToken}; }
  window.HamLogAPI = { post, download, upload, refresh, clear, setTokens, tokenState, csrf };
  window.post = post;
}());
