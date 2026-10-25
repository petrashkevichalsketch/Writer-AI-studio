/* ═══════════════════════════════════════════════════════════════
   UI-хелперы Writer AI Studio: тосты, диалоги confirm/alert,
   панель статуса LLM-стрима, валидационные панели.
   Подключается в base.html до остальных скриптов.
   ═══════════════════════════════════════════════════════════════ */
window.UI = (function () {
  'use strict';

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  /* ── Тосты ─────────────────────────────────────────────────── */

  const ICONS = { ok: '✓', error: '✕', warn: '⚠', info: 'ℹ' };
  let stack = null;

  function toast(msg, type = 'info', ms = 2800) {
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      document.body.appendChild(stack);
    }
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    const ico = document.createElement('span');
    ico.className = 't-ico';
    ico.textContent = ICONS[type] || ICONS.info;
    const body = document.createElement('span');
    body.textContent = msg;
    t.append(ico, body);
    stack.appendChild(t);
    setTimeout(() => {
      t.classList.add('out');
      setTimeout(() => t.remove(), 320);
    }, ms);
    return t;
  }

  /* ── Диалоги confirm / alert (Promise) ─────────────────────── */

  function dialog(opts) {
    const { title = '', text = '', okText = 'ОК',
            cancelText = null, danger = false } = opts;
    return new Promise(resolve => {
      const wrap = document.createElement('div');
      wrap.className = 'modal dlg-host';
      const box = document.createElement('div');
      box.className = 'modal-box dlg-box';

      if (title) {
        const head = document.createElement('div');
        head.className = 'modal-head';
        const h = document.createElement('h3');
        h.textContent = title;
        head.appendChild(h);
        box.appendChild(head);
      }
      const body = document.createElement('div');
      body.className = 'dlg-text';
      body.textContent = text;
      box.appendChild(body);

      const actions = document.createElement('div');
      actions.className = 'dlg-actions';
      let cancelBtn = null;
      if (cancelText) {
        cancelBtn = document.createElement('button');
        cancelBtn.textContent = cancelText;
        actions.appendChild(cancelBtn);
      }
      const okBtn = document.createElement('button');
      okBtn.textContent = okText;
      okBtn.className = danger ? 'danger' : 'primary';
      actions.appendChild(okBtn);
      box.appendChild(actions);

      wrap.appendChild(box);
      document.body.appendChild(wrap);
      okBtn.focus();

      const done = val => {
        wrap.remove();
        document.removeEventListener('keydown', onKey);
        resolve(val);
      };
      okBtn.addEventListener('click', () => done(true));
      if (cancelBtn) {
        cancelBtn.addEventListener('click', () => done(false));
        wrap.addEventListener('mousedown', e => {
          if (e.target === wrap) done(false);
        });
      }
      function onKey(e) {
        if (e.key === 'Escape') done(!!cancelBtn ? false : true);
        if (e.key === 'Enter') done(true);
      }
      document.addEventListener('keydown', onKey);
    });
  }

  function confirm(opts) {
    if (typeof opts === 'string') opts = { text: opts };
    return dialog(Object.assign({ cancelText: 'Отмена' }, opts));
  }

  function alert(opts) {
    if (typeof opts === 'string') opts = { text: opts };
    return dialog(opts);
  }

  /* ── Панель статуса LLM (стрим главы) ──────────────────────── */

  function stream(mount) {
    mount = mount || document.getElementById('stream-tail');
    if (!mount) return null;

    mount.classList.add('llm-panel');
    mount.style.display = 'none';
    mount.innerHTML =
      '<div class="llm-head">' +
      '  <span class="spinner llm-spin" style="display:none"></span>' +
      '  <span class="pulse-dot llm-dot" style="display:none"></span>' +
      '  <span class="llm-stage"></span>' +
      '  <span class="llm-time"></span>' +
      '</div>' +
      '<div class="llm-progress" style="display:none"><i></i></div>' +
      '<div class="llm-stats" style="display:none"></div>';

    const el = {
      spin:  mount.querySelector('.llm-spin'),
      dot:   mount.querySelector('.llm-dot'),
      stage: mount.querySelector('.llm-stage'),
      time:  mount.querySelector('.llm-time'),
      prog:  mount.querySelector('.llm-progress'),
      fill:  mount.querySelector('.llm-progress i'),
      stats: mount.querySelector('.llm-stats'),
    };

    const stopTimer = st => {
      if (st._timer) { clearInterval(st._timer); st._timer = null; }
    };

    const st = {
      _timer: null, _t0: 0,

      _mode(cls) {
        mount.classList.remove('is-working', 'is-done', 'is-error');
        if (cls) mount.classList.add(cls);
      },

      work(text) {
        mount.style.display = 'block';
        this._mode('is-working');
        el.spin.style.display = '';
        el.dot.style.display = 'none';
        el.stage.textContent = text || '…';
        if (!this._t0) this._t0 = Date.now();
        stopTimer(this);
        this._timer = setInterval(() => {
          const s = Math.max(0, Math.round((Date.now() - this._t0) / 1000));
          el.time.textContent =
            `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
        }, 1000);
      },

      note(text) { el.stage.textContent = text; },
      warn(text) { el.stage.textContent = '⚠ ' + text; },

      progress(words, target, cps) {
        if (target) {
          el.prog.style.display = '';
          el.fill.style.width =
            Math.min(100, (words / target) * 100).toFixed(1) + '%';
        }
        const parts = [`<b>${words}</b> слов`];
        if (target) parts.push(`цель ${target}`);
        if (cps) parts.push(`~${Math.round(cps)} слов/мин`);
        el.stats.style.display = '';
        el.stats.innerHTML = parts.join(' · ');
      },

      done(text) {
        stopTimer(this);
        mount.style.display = 'block';
        this._mode('is-done');
        el.spin.style.display = 'none';
        el.dot.style.display = '';
        el.dot.className = 'pulse-dot llm-dot ok';
        el.stage.textContent = text || '✓ готово';
      },

      error(text) {
        stopTimer(this);
        mount.style.display = 'block';
        this._mode('is-error');
        el.spin.style.display = 'none';
        el.dot.style.display = '';
        el.dot.className = 'pulse-dot llm-dot err';
        el.stage.textContent = text || '✗ ошибка';
      },

      hide() { mount.style.display = 'none'; },
      reset() { this._t0 = 0; el.time.textContent = ''; },
    };
    return st;
  }

  /* ── Панель валидации (ошибки/предупреждения) ──────────────── */

  function validation(mount, errors, warns) {
    if (!mount) return;
    errors = (errors || []).filter(Boolean);
    warns = (warns || []).filter(Boolean);
    if (!errors.length && !warns.length) {
      mount.innerHTML = '';
      return;
    }
    const isErr = errors.length > 0;
    const all = errors.concat(warns);
    mount.innerHTML =
      `<div class="val-panel${isErr ? '' : ' val-warn'}">` +
      `<div class="val-head">${isErr ? '⛔ Ошибки (' + errors.length + ')'
                                      : '⚠ Предупреждения (' + warns.length + ')'}` +
      `<button type="button" class="val-copy">копировать</button></div>` +
      `<ol class="val-list">${all.map(x => `<li>${esc(x)}</li>`).join('')}</ol>` +
      `</div>`;
    mount.querySelector('.val-copy').addEventListener('click', () => {
      navigator.clipboard.writeText(all.join('\n'))
        .then(() => toast('Скопировано', 'ok'))
        .catch(() => toast('Не удалось скопировать', 'warn'));
    });
  }

  /* ── Глобальное поведение форм: data-confirm ───────────────── */

  document.addEventListener('submit', e => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement)) return;
    if (!f.dataset.confirm || f.dataset.confirmed) return;
    e.preventDefault();
    confirm({ text: f.dataset.confirm, okText: 'Подтвердить' }).then(ok => {
      if (!ok) return;
      f.dataset.confirmed = '1';
      if (f.requestSubmit) f.requestSubmit(); else f.submit();
      delete f.dataset.confirmed;
    });
  });

  /* ── Глобальное закрытие модалок: Esc и клик по фону ───────── */

  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const modals = [...document.querySelectorAll('.modal')]
      .filter(m => m.style.display !== 'none' && !m.classList.contains('dlg-host'));
    if (modals.length) modals[modals.length - 1].style.display = 'none';
  });

  document.addEventListener('mousedown', e => {
    if (e.target.classList && e.target.classList.contains('modal') &&
        !e.target.classList.contains('dlg-host')) {
      e.target.style.display = 'none';
    }
  });

  /* ── Активная ссылка навигации ─────────────────────────────── */

  document.addEventListener('DOMContentLoaded', () => {
    const path = location.pathname;
    document.querySelectorAll('.topbar nav a').forEach(a => {
      const href = a.getAttribute('href') || '';
      if (href === path || (href !== '/' && path.startsWith(href + ''))) {
        a.classList.add('active-nav');
      }
    });
  });

  return { toast, confirm, alert, validation, stream, esc };
})();
