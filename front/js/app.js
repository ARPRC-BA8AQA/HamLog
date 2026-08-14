const app = document.querySelector('#app');
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function renderLogs() {
  app.innerHTML = `<section class="panel"><h1>QSO 日志</h1><form id="log-form"><input name="Callsign" placeholder="呼号" required><input name="Freq" placeholder="频率"><input name="Mode" placeholder="模式"><input name="QTH" placeholder="QTH"><button>添加日志</button></form><div class="toolbar"><input id="keyword" placeholder="搜索呼号、QTH、设备或备注"><button id="search">搜索</button></div><div id="table">加载中...</div></section>`;
  const refresh = async keyword => { const data = await post('/log/list', {keyword}); document.querySelector('#table').innerHTML = `<table><thead><tr><th>ID</th><th>呼号</th><th>频率</th><th>模式</th><th>QTH</th><th>备注</th></tr></thead><tbody>${data.items.map(item => `<tr><td>${item.id}</td><td>${escapeHtml(item.Callsign)}</td><td>${escapeHtml(item.Freq)}</td><td>${escapeHtml(item.Mode)}</td><td>${escapeHtml(item.QTH)}</td><td>${escapeHtml(item.Remarks)}</td></tr>`).join('')}</tbody></table><p class="muted">共 ${data.total} 条</p>`; };
  document.querySelector('#log-form').onsubmit = async event => { event.preventDefault(); const payload = Object.fromEntries(new FormData(event.target)); await post('/log/add', payload); event.target.reset(); await refresh(''); };
  document.querySelector('#search').onclick = () => refresh(document.querySelector('#keyword').value);
  await refresh('');
}

async function renderSettings() { const settings = await post('/settings/get_all'); app.innerHTML = `<section class="panel"><h1>本台设置</h1><p class="muted">配置保存在本地 SQLite 数据库。</p><form id="settings-form"><input name="key" placeholder="设置名称" required><input name="value" placeholder="设置值" required><button>保存</button></form><pre>${escapeHtml(JSON.stringify(settings, null, 2))}</pre></section>`; document.querySelector('#settings-form').onsubmit = async event => { event.preventDefault(); await post('/settings/set', Object.fromEntries(new FormData(event.target))); renderSettings(); }; }

function renderQsl() { app.innerHTML = `<section class="panel"><h1>QSL 卡片</h1><p>QSL 设计器将使用标准 .hamqsl JSON 工程格式。</p><button onclick="location.href='/qsl_designer/designer.html'">打开设计器</button></section>`; }
function render(view = 'logs') { ({logs: renderLogs, settings: renderSettings, qsl: renderQsl}[view] || renderLogs)().catch(error => { app.innerHTML = `<section class="panel"><h1>请求失败</h1><p>${escapeHtml(error.message)}</p></section>`; }); }
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => render(button.dataset.view));
render();
