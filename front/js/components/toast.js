(function () {
  function show(message, kind) {
    const region = document.querySelector('#toast-region'); if (!region) return;
    const toast = document.createElement('div'); toast.className = `toast${kind === 'error' ? ' error' : ''}`; toast.textContent = message;
    region.appendChild(toast); setTimeout(() => toast.remove(), 3600);
  }
  window.HamLogToast = {show, error: message => show(message, 'error')};
}());
