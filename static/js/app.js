/* CareerMind shared UI helpers: toasts, confirm dialogs, CSRF-aware fetch.
   Loaded by every portal base template. Plain JS, no dependencies. */
(function () {
  'use strict';

  function getCookie(name) {
    const parts = (document.cookie || '').split(';');
    for (const c of parts) {
      const t = c.trim();
      if (t.startsWith(name + '=')) return decodeURIComponent(t.slice(name.length + 1));
    }
    return null;
  }

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.content) || getCookie('csrftoken') || '';
  }

  /* ---- toasts ---------------------------------------------------- */
  function toastHost() {
    let host = document.getElementById('cm-toasts');
    if (!host) {
      host = document.createElement('div');
      host.id = 'cm-toasts';
      host.setAttribute('role', 'status');
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(message, type) {
    const el = document.createElement('div');
    el.className = 'cm-toast cm-toast-' + (type || 'info');
    el.textContent = message;               // textContent: never inject HTML
    toastHost().appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    const ttl = type === 'error' ? 6000 : 3500;
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 250);
    }, ttl);
  }

  /* ---- confirm dialog ------------------------------------------- */
  function confirmDialog(opts) {
    opts = opts || {};
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'cm-modal-overlay';
      overlay.innerHTML =
        '<div class="cm-modal" role="dialog" aria-modal="true" aria-labelledby="cm-modal-title">' +
        '<h3 id="cm-modal-title"></h3><p></p>' +
        '<div class="cm-modal-actions"><button type="button" class="cm-btn-secondary" data-act="no"></button>' +
        '<button type="button" class="cm-btn-danger" data-act="yes"></button></div></div>';
      overlay.querySelector('h3').textContent = opts.title || 'Are you sure?';
      overlay.querySelector('p').textContent = opts.message || '';
      overlay.querySelector('[data-act="no"]').textContent = opts.cancelText || 'Cancel';
      overlay.querySelector('[data-act="yes"]').textContent = opts.confirmText || 'Confirm';
      const done = v => { overlay.remove(); document.removeEventListener('keydown', onKey); resolve(v); };
      const onKey = e => { if (e.key === 'Escape') done(false); };
      overlay.addEventListener('click', e => {
        if (e.target === overlay) done(false);
        const act = e.target.getAttribute && e.target.getAttribute('data-act');
        if (act) done(act === 'yes');
      });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(overlay);
      overlay.querySelector('[data-act="no"]').focus();
    });
  }

  /* Any <form data-confirm="message"> (or button[data-confirm]) asks first. */
  document.addEventListener('submit', function (e) {
    const form = e.target;
    const submitter = e.submitter;
    const msg = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
    if (!msg || form.dataset.confirmed === '1') return;
    e.preventDefault();
    confirmDialog({
      title: (submitter && submitter.dataset.confirmTitle) || form.dataset.confirmTitle || 'Please confirm',
      message: msg,
      confirmText: (submitter && submitter.dataset.confirmText) || form.dataset.confirmText || 'Confirm',
    }).then(ok => {
      if (!ok) return;
      form.dataset.confirmed = '1';
      if (submitter && submitter.name) {          // keep the clicked button's value
        const h = document.createElement('input');
        h.type = 'hidden'; h.name = submitter.name; h.value = submitter.value;
        form.appendChild(h);
      }
      form.submit();
    });
  });

  /* Forms with data-loading disable their submit buttons while submitting.
     Runs after the confirm handler, so a cancelled confirm never leaves a dead button. */
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (e.defaultPrevented || !form.hasAttribute || !form.hasAttribute('data-loading')) return;
    setTimeout(function () {
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach(function (b) {
        b.disabled = true;
        if (b.dataset.loadingText) { b.dataset.origText = b.textContent; b.textContent = b.dataset.loadingText; }
      });
    }, 0);
  });
  window.addEventListener('pageshow', function (ev) {
    if (!ev.persisted) return;
    document.querySelectorAll('form[data-loading] button[disabled]').forEach(function (b) {
      b.disabled = false;
      if (b.dataset.origText) b.textContent = b.dataset.origText;
    });
  });

  /* ---- fetch helper --------------------------------------------- */
  async function post(url, data) {
    const body = data instanceof FormData ? data : new URLSearchParams(data || {});
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
      body: body,
      credentials: 'same-origin',
    });
    let json = null;
    try { json = await res.json(); } catch (_) { /* non-JSON error page */ }
    if (!res.ok) {
      const err = new Error((json && json.error) || ('Request failed (' + res.status + ')'));
      err.status = res.status; err.data = json;
      throw err;
    }
    return json;
  }

  /* Django messages rendered as <li data-cm-message="tag"> become toasts. */
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-cm-message]').forEach(el => {
      const tag = el.getAttribute('data-cm-message');
      toast(el.textContent.trim(), tag.includes('error') ? 'error' : tag.includes('success') ? 'success' : 'info');
    });
  });

  window.CM = { toast: toast, confirm: confirmDialog, post: post, csrfToken: csrfToken, getCookie: getCookie };
})();
