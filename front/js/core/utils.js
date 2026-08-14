(function () {
  function escapeHtml(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function uid(prefix) { return `${prefix || 'id'}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`; }
  function json(value) { return escapeHtml(JSON.stringify(value, null, 2)); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function dateTime(value) { if (!value) return '未记录'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', {year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'}); }
  function formatNumber(value) { return Number(value || 0).toLocaleString('zh-CN'); }
  function downloadText(text, filename, type) { const blob = new Blob([text], {type: type || 'text/plain;charset=utf-8'}); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
  window.HamLogUtils = {escapeHtml, uid, json, today, dateTime, formatNumber, downloadText, debounce};
}());
