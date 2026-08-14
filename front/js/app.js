(function () {
  const app = document.querySelector('#app');
  const authDialog = document.querySelector('#auth-dialog');
  const loginForm = document.querySelector('#login-form');
  const authAction = document.querySelector('#auth-action');
  const userStatus = document.querySelector('#user-status');
  const connectionDot = document.querySelector('#connection-dot');
  const sidebar = document.querySelector('#sidebar');
  const backdrop = document.querySelector('#sidebar-backdrop');
  let cleanup = null;
  let setupRequired = false;

  const pageNames = {dashboard: '概览', logs: 'QSO 日志', qrz: 'QRZ 查询', adif: 'ADIF 导出', lotw: 'LoTW 上传', network: '网络监测', plugins: '插件中心', settings: '本台设置', system: '系统与更新'};
  const pages = window.HamLogPages = window.HamLogPages || {};
  const {escapeHtml, formatNumber} = HamLogUtils;
  document.body.dataset.theme = localStorage.getItem('hamlog.theme') || 'light';

  function closeSidebar() { sidebar.classList.remove('is-open'); backdrop.classList.remove('is-visible'); }
  document.querySelector('#mobile-menu').onclick = () => { sidebar.classList.toggle('is-open'); backdrop.classList.toggle('is-visible'); };
  backdrop.onclick = closeSidebar;

  function statCard(label, value, note) {
    return `<div class="stat"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value">${escapeHtml(value)}</div><div class="stat-note">${escapeHtml(note || '')}</div></div>`;
  }

  pages.dashboard = async function dashboard(container) {
    container.innerHTML = `<div class="page-heading"><div><p class="eyebrow">Operations</p><h1>电台工作台</h1><p>通联概览与常用操作。</p></div><a class="button button-primary" href="#/logs?new=1">录入 QSO</a></div><div id="dashboard-stats" class="stats-grid"><div class="loading">加载统计...</div></div><div class="grid-2"><section class="panel"><div class="panel-header"><div><h2>最近通联</h2><p>最新 6 条 QSO 记录</p></div><a href="#/logs" class="button button-secondary button-small">查看全部</a></div><div id="recent-logs" class="loading">加载中...</div></section><section class="panel"><div class="panel-header"><div><h2>快捷操作</h2><p>常用电台工具</p></div></div><div class="action-list"><a class="action-link" href="#/qrz">查询 QRZ <span>→</span></a><a class="action-link" href="#/adif">导出 ADIF <span>→</span></a><a class="action-link" href="/qsl_designer/designer.html">设计 QSL 卡片 <span>→</span></a><a class="action-link" href="#/network">检测网络节点 <span>→</span></a></div></section></div><div class="grid-2" style="margin-top:18px"><section class="panel"><div class="panel-header"><div><h2>模式分布</h2><p>按当前统计数据汇总</p></div></div><div id="mode-bars" class="bar-list"></div></section><section class="panel"><div class="panel-header"><div><h2>运行状态</h2><p>本机 HamLog 服务</p></div></div><div id="system-summary" class="metric-list"></div></section></div>`;
    const [statsResult, logsResult, systemResult] = await Promise.allSettled([HamLogAPI.post('/log/stats'), HamLogAPI.post('/log/list', {page: 1, page_size: 6}), HamLogAPI.post('/system/info')]);
    const stats = statsResult.status === 'fulfilled' ? statsResult.value : {};
    document.querySelector('#dashboard-stats').innerHTML = [statCard('全部通联', formatNumber(stats.total), '数据库累计记录'), statCard('今日通联', formatNumber(stats.today), '按本地日期'), statCard('本月通联', formatNumber(stats.this_month), '当前自然月'), statCard('常用模式', Object.keys(stats.by_mode || {})[0] || '暂无', Object.keys(stats.by_mode || {}).length ? '通联数最高' : '等待统计数据')].join('');
    const logs = logsResult.status === 'fulfilled' ? logsResult.value.items || [] : [];
    document.querySelector('#recent-logs').innerHTML = logs.length ? `<div class="table-wrap"><table><thead><tr><th>呼号</th><th>UTC 日期</th><th>时间</th><th>频率</th><th>模式</th><th>QTH</th></tr></thead><tbody>${logs.map(item => `<tr><td><strong>${escapeHtml(item.Callsign)}</strong></td><td>${escapeHtml([item.Year, String(item.Month || '').padStart(2,'0'), String(item.Day || '').padStart(2,'0')].filter(Boolean).join('-'))}</td><td>${escapeHtml(item.Time || '-')}</td><td>${escapeHtml(item.Freq || '-')}</td><td>${escapeHtml(item.Mode || '-')}</td><td>${escapeHtml(item.QTH || '-')}</td></tr>`).join('')}</tbody></table></div>` : '<div class="table-empty">还没有 QSO 记录，从录入第一条通联开始。</div>';
    const modes = Object.entries(stats.by_mode || {}); const max = Math.max(1, ...modes.map(([, value]) => Number(value)));
    document.querySelector('#mode-bars').innerHTML = modes.length ? modes.map(([mode, count]) => `<div class="bar-row"><span>${escapeHtml(mode)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, Number(count) / max * 100)}%"></div></div><strong>${formatNumber(count)}</strong></div>`).join('') : '<div class="table-empty">后端尚未提供模式聚合数据。</div>';
    const system = systemResult.status === 'fulfilled' ? systemResult.value : {};
    document.querySelector('#system-summary').innerHTML = `<div class="metric-item"><span>服务连接</span><span class="badge success">正常</span></div><div class="metric-item"><span>应用版本</span><strong>${escapeHtml(system.app_version || '未知')}</strong></div><div class="metric-item"><span>Python</span><strong>${escapeHtml(system.python_version || '未知')}</strong></div><div class="metric-item"><span>运行平台</span><span>${escapeHtml(system.platform || '未知')}</span></div>`;
  };

  async function updateAuthStatus() {
    try {
      const status = await HamLogAPI.post('/auth/status');
      HamLogStore.update({auth: status});
      connectionDot.className = 'connection-dot is-online';
       setupRequired = Boolean(status.setup_required);
       if (!status.auth_enabled) { userStatus.textContent = '本地管理员'; authAction.textContent = '免登录'; authAction.disabled = true; }
       else if (status.setup_required) { userStatus.textContent = '需要初始化'; authAction.textContent = '创建管理员'; authAction.disabled = false; }
      else if (status.logged_in) { userStatus.textContent = `${status.username} · ${status.role === 'admin' ? '管理员' : '用户'}`; authAction.textContent = '退出'; authAction.disabled = false; }
      else { userStatus.textContent = '未登录'; authAction.textContent = '登录'; authAction.disabled = false; }
      return status;
    } catch (_) {
      connectionDot.className = 'connection-dot is-offline'; userStatus.textContent = '服务离线'; authAction.textContent = '重试'; authAction.disabled = false;
      return null;
    }
  }

  authAction.onclick = async () => {
    const auth = HamLogStore.state.auth;
    if (auth.auth_enabled && auth.logged_in) {
      try { await HamLogAPI.post('/auth/logout'); } catch (_) { /* local logout still applies */ }
      HamLogAPI.clear(); await updateAuthStatus(); HamLogToast.show('已退出当前账户'); route();
    } else if (!auth.auth_enabled && connectionDot.classList.contains('is-offline')) { await updateAuthStatus(); route(); }
    else { openAuthDialog(); }
  };
  function openAuthDialog() {
    document.querySelector('#login-error').textContent = '';
    document.querySelector('#auth-dialog-title').textContent = setupRequired ? '创建首个管理员' : '登录 HamLog';
    document.querySelector('#auth-dialog-description').textContent = setupRequired ? '首次启用认证需要创建管理员账户，密码至少 8 位。' : '认证开启后，受保护的日志与设置会使用当前账户。';
    document.querySelector('#auth-submit').textContent = setupRequired ? '创建管理员' : '登录';
    authDialog.showModal();
  }
  document.querySelector('#login-cancel').onclick = () => authDialog.close();
  document.querySelector('#login-close').onclick = () => authDialog.close();
  loginForm.onsubmit = async event => {
    event.preventDefault(); const submit = loginForm.querySelector('[type="submit"]'); submit.disabled = true;
    try {
      const credentials = Object.fromEntries(new FormData(loginForm));
      if (setupRequired) await HamLogAPI.post('/auth/user/create', {...credentials, role:'admin'});
      const data = await HamLogAPI.post('/auth/login', credentials);
      HamLogAPI.setTokens(data); authDialog.close(); loginForm.reset(); await updateAuthStatus(); HamLogToast.show('登录成功'); route();
    } catch (error) { document.querySelector('#login-error').textContent = error.message; }
    finally { submit.disabled = false; }
  };

  async function route() {
    closeSidebar(); if (cleanup) { cleanup(); cleanup = null; }
    const routeName = (location.hash.match(/^#\/([^?]+)/) || [])[1] || 'dashboard';
    document.querySelectorAll('[data-route]').forEach(link => link.classList.toggle('active', link.dataset.route === routeName));
    document.querySelector('#topbar-context').textContent = pageNames[routeName] || '电台工作台';
    app.innerHTML = '<div class="loading">正在加载...</div>'; app.focus();
    const renderer = pages[routeName] || pages.dashboard;
    try { const result = await renderer(app, new URLSearchParams((location.hash.split('?')[1] || ''))); if (typeof result === 'function') cleanup = result; connectionDot.className = 'connection-dot is-online'; }
    catch (error) {
       if (error.code === 401) { app.innerHTML = `<section class="panel"><p class="eyebrow">Authentication</p><h1>${setupRequired ? '需要初始化管理员' : '需要登录'}</h1><p class="muted">${setupRequired ? '当前服务已开启认证，请先创建首个管理员。' : '当前服务已开启认证，请登录后继续。'}</p><button class="button button-primary" id="page-login">${setupRequired ? '创建管理员' : '登录'}</button></section>`; document.querySelector('#page-login').onclick = openAuthDialog; }
      else app.innerHTML = `<section class="panel"><p class="eyebrow">Request error</p><h1>无法加载此页面</h1><p class="muted">${escapeHtml(error.message)}</p><button class="button button-secondary" id="page-retry">重试</button></section>`;
      const retry = document.querySelector('#page-retry'); if (retry) retry.onclick = route;
      if (!navigator.onLine || error instanceof TypeError) connectionDot.className = 'connection-dot is-offline';
    }
  }

  window.addEventListener('hashchange', route);
  window.addEventListener('online', updateAuthStatus);
  window.addEventListener('offline', () => { connectionDot.className = 'connection-dot is-offline'; });
  updateAuthStatus().then(route);
}());
