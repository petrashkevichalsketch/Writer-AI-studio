/* ═══════════════════════════════════════════════════════════════
   UI-хелперы Writer AI Studio: тосты, диалоги confirm/alert,
   панель статуса LLM-стрима, валидационные панели.
   Подключается в base.html до остальных скриптов.
   ═══════════════════════════════════════════════════════════════ */
window.UI = (function () {
  'use strict';

  /* ── Локализация: словарь инжектится в base.html (window.I18N);
     ключ — исходная русская строка, нет перевода — вернётся она же ── */

  function tr(s, params) {
    let t = (window.I18N && window.I18N[s]) || s;
    if (params) {
      for (const k in params) t = t.split('{' + k + '}').join(params[k]);
    }
    return t;
  }
  window.tr = tr;

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
    const { title = '', text = '', okText = tr('ОК'),
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
    return dialog(Object.assign({ cancelText: tr('Отмена') }, opts));
  }

  function alert(opts) {
    if (typeof opts === 'string') opts = { text: opts };
    return dialog(opts);
  }

  /* Диалог-выбор: options = [{id, label}]. Resolve — id нажатого
     варианта или null (Отмена / Esc / клик мимо). */
  function choose(opts) {
    const { title = '', text = '', options = [],
            cancelText = tr('Отмена') } = opts;
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
      options.forEach((o, idx) => {
        const b = document.createElement('button');
        b.textContent = o.label;
        if (idx === 0) b.className = 'primary';
        b.addEventListener('click', () => done(o.id));
        actions.appendChild(b);
      });
      const cancelBtn = document.createElement('button');
      cancelBtn.textContent = cancelText;
      cancelBtn.addEventListener('click', () => done(null));
      actions.appendChild(cancelBtn);
      box.appendChild(actions);

      wrap.appendChild(box);
      document.body.appendChild(wrap);
      (actions.querySelector('button') || cancelBtn).focus();

      const done = val => {
        wrap.remove();
        document.removeEventListener('keydown', onKey);
        resolve(val);
      };
      function onKey(e) {
        if (e.key === 'Escape') done(null);
      }
      document.addEventListener('keydown', onKey);
      wrap.addEventListener('mousedown', e => {
        if (e.target === wrap) done(null);
      });
    });
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

      progress(words, target, cps, unitKey) {
        if (target) {
          el.prog.style.display = '';
          el.fill.style.width =
            Math.min(100, (words / target) * 100).toFixed(1) + '%';
        }
        const parts = [tr(unitKey || '<b>{n}</b> слов', { n: words })];
        if (target) parts.push(tr('цель {n}', { n: target }));
        if (cps) parts.push(tr('~{n} слов/мин', { n: Math.round(cps) }));
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
        el.stage.textContent = text || tr('✓ готово');
      },

      error(text) {
        stopTimer(this);
        mount.style.display = 'block';
        this._mode('is-error');
        el.spin.style.display = 'none';
        el.dot.style.display = '';
        el.dot.className = 'pulse-dot llm-dot err';
        el.stage.textContent = text || tr('✗ ошибка');
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
      `<div class="val-head">${isErr ? tr('⛔ Ошибки ({n})', { n: errors.length })
                                      : tr('⚠ Предупреждения ({n})', { n: warns.length })}` +
      `<button type="button" class="val-copy">${tr('копировать')}</button></div>` +
      `<ol class="val-list">${all.map(x => `<li>${esc(x)}</li>`).join('')}</ol>` +
      `</div>`;
    mount.querySelector('.val-copy').addEventListener('click', () => {
      navigator.clipboard.writeText(all.join('\n'))
        .then(() => toast(tr('Скопировано'), 'ok'))
        .catch(() => toast(tr('Не удалось скопировать'), 'warn'));
    });
  }

  /* ── Глобальное поведение форм: data-confirm ───────────────── */

  document.addEventListener('submit', e => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement)) return;
    if (!f.dataset.confirm || f.dataset.confirmed) return;
    e.preventDefault();
    confirm({ text: f.dataset.confirm, okText: tr('Подтвердить') }).then(ok => {
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

  /* ── Кнопки-крестики: data-close / data-bridge-close и т.п. ── */

  document.addEventListener('click', e => {
    const b = e.target.closest(
      '[data-close], [data-bridge-close], [data-fix-close], [data-edit-close]');
    if (!b) return;
    const id = b.dataset.close || b.dataset.bridgeClose ||
               b.dataset.fixClose || b.dataset.editClose;
    const m = (id && document.getElementById(id)) || b.closest('.modal');
    if (m) m.style.display = 'none';
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

  /* ── Wake Lock: экран не гаснет, пока идёт долгая генерация ── */
  /* Без этого мобильный браузер обрывает SSE-стрим при блокировке экрана. */

  let wakeLock = null;
  let wantWake = false;

  async function _acquireWakeLock() {
    if (!('wakeLock' in navigator)) return;   // десктоп/старый WebView — тихо
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (e) {
      wakeLock = null;
    }
  }

  async function keepAwake(on) {
    wantWake = !!on;
    if (on) {
      if (!wakeLock) await _acquireWakeLock();
    } else if (wakeLock) {
      try { await wakeLock.release(); } catch (e) { /* уже отпущен */ }
      wakeLock = null;
    }
  }

  // Экран погасили и включили снова — захват повторяется, пока поток жив.
  document.addEventListener('visibilitychange', () => {
    if (wantWake && document.visibilityState === 'visible' && !wakeLock) {
      _acquireWakeLock();
    }
  });

  /* ── Мобильные: боковой свайп = переход к соседнему разделу меню ── */
  /* Паттерн по web.dev/MDN: touch-action отдаёт браузеру только
     вертикальный скролл и пинч, горизонталь приходит в JS целиком —
     жест не «умирает» touchcancel, если палец слегка уехал вверх.
     Порог мягче (50px) + скорость: короткий быстрый флик тоже свайп. */

  (function () {
    // Телефоны и планшеты (pointer: coarse) + запас по ширине для
    // альбомной ориентации и старых WebView без pointer-медиа.
    var coarse = window.matchMedia && (
      window.matchMedia('(pointer: coarse)').matches ||
      window.matchMedia('(max-width: 920px)').matches);
    if (!coarse) return;
    if (!('ontouchstart' in window)) return;

    const links = Array.from(document.querySelectorAll('.topbar nav a'));
    if (links.length < 2) return;
    const path = location.pathname.replace(/\/+$/, '') || '/';
    let idx = links.findIndex(a => {
      const href = a.getAttribute('href') || '';
      return href === path || (href !== '/' && path.startsWith(href));
    });
    // /chapter/N нет в меню — свайп от главы ведёт к разделу «Книга».
    if (idx < 0 && path.startsWith('/chapter')) {
      idx = links.findIndex(a => a.getAttribute('href') === '/book');
    }
    if (idx < 0) return;

    const style = document.createElement('style');
    style.textContent =
      'body { touch-action: pan-y pinch-zoom; overscroll-behavior-x: none; }';
    document.head.appendChild(style);

    const SLOP = 8;     // порог решения о направлении = нативный touch slop
                        // браузера (~8px). Раньше было 12px: WebView успевал
                        // начать вертикальный скролл до нашего решения, а
                        // preventDefault после старта скролла уже не работает
                        // — боковой свайп «съедался» прокруткой страницы.
    const MIN_DX = 50;  // порог расстояния
    const MIN_V = 0.4;  // скорость px/мс — быстрый короткий флик
    const RATIO = 1.2;  // |dx| должен превышать |dy|
    let yAnchor = 0, scrollAnchor = 0;  // страховка вертикального дрейфа

    // Кнопки и ссылки НЕ исключаем: короткий тап всё равно нажмёт их
    // (браузер отменяет click при смещении пальца), а свайп с кнопки —
    // легитимный жест навигации. Исключаем текстовый ввод, модалки и
    // полосу чипов справки (она скроллится горизонтально сама).
    const interactive = 'input, textarea, select, #help-toc, '
      + '[contenteditable="true"], .modal, .topbar, .modal-actions';

    let x0 = 0, y0 = 0, xLast = 0, yLast = 0, tLast = 0;
    let tracking = false, locked = null;   // null | 'x' | 'y'

    document.addEventListener('touchstart', e => {
      if (e.touches.length !== 1) { tracking = false; return; }
      const t = e.touches[0];
      if (t.target.closest && t.target.closest(interactive)) {
        tracking = false;
        return;
      }
      x0 = xLast = t.clientX;
      y0 = yLast = t.clientY;
      tLast = Date.now();
      tracking = true;
      locked = null;
    }, { passive: true });

    document.addEventListener('touchmove', e => {
      if (!tracking) return;
      const t = e.touches[0];
      const dx = t.clientX - x0, dy = t.clientY - y0;
      if (!locked) {
        if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
        // Решение — на том же touchmove, на котором его принимает браузер:
        // слушатель блокирующий, наш preventDefault отменяет нативный
        // скролл до того, как тот стартует.
        locked = Math.abs(dx) >= Math.abs(dy) ? 'x' : 'y';
      }
      if (locked === 'x') {
        // Горизонталь — наша: гасим нативный скролл на весь жест,
        // чтобы страница не «уезжала» вверх/вниз.
        e.preventDefault();
        // Страховка: если после захвата жест явно ушёл в вертикаль
        // (свайп вбок начался с дрейфа вниз) — двигаем страницу сами:
        // нативный скролл после preventDefault уже не включится.
        if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 30) {
          locked = 'manualY';
          yAnchor = t.clientY;
          scrollAnchor = window.scrollY;
          return;
        }
        xLast = t.clientX; yLast = t.clientY; tLast = Date.now();
        return;
      }
      if (locked === 'manualY') {
        e.preventDefault();
        window.scrollTo(0, scrollAnchor + (yAnchor - t.clientY));
      }
    }, { passive: false });

    document.addEventListener('touchend', e => {
      if (!tracking) return;
      tracking = false;
      if (locked !== 'x') return;          // вертикаль/неопределено — не свайп
      const t = e.changedTouches[0];
      const dx = t.clientX - x0, dy = t.clientY - y0;
      const dist = Math.abs(dx);
      // скорость последнего сегмента: быстрый короткий флик тоже свайп
      const v = Math.abs(t.clientX - xLast)
        / Math.max(1, Date.now() - tLast);
      if (dist < 24) return;               // микрожест
      if (dist < MIN_DX && v < MIN_V) return;
      if (dist < Math.abs(dy) * RATIO) return;
      const dir = dx > 0 ? -1 : 1;            // вправо — назад
      // Справка навигирует разделы приложения как все страницы; полоса
      // чипов — единственное исключение (скроллится сама, см. exclusion).
      const next = idx + dir;
      if (next < 0 || next >= links.length) return;
      if (UI.toast) UI.toast('↔ ' + links[next].textContent.trim());
      location.href = links[next].getAttribute('href');
    }, { passive: true });

    // Браузер забрал жест (входящий звонок, системный жест) — только сброс.
    document.addEventListener('touchcancel', () => {
      tracking = false;
      locked = null;
    }, { passive: true });
  })();

  /* ── Справка: полоса чипов скроллится только жестом по ней самой ── */
  /* Свайпы по остальному экрану на Справке навигируют разделы приложения
     (общий детектор выше). Полоса чипов — единственное исключение:
     touch-action: pan-x (screens.css) + глушение click после движения
     пальца, иначе WebView догенерировал click по чипу и anchor-прыжок
     #h-… уносил страницу. */

  (function () {
    if (location.pathname !== '/help') return;

    const toc = document.getElementById('help-toc');
    if (!toc) return;

    let stripMoved = false;
    toc.addEventListener('touchstart', () => { stripMoved = false; },
      { passive: true });
    toc.addEventListener('touchmove', () => { stripMoved = true; },
      { passive: true });
    toc.addEventListener('click', e => {
      if (stripMoved) {
        e.preventDefault();
        e.stopPropagation();
        stripMoved = false;
      }
    }, true);

    /* Десктоп: тачпад двумя пальцами, наклонное колесо, shift+колесо —
       листают разделы приложения (как свайп на телефоне). */
    const links = Array.from(toc ? document.querySelectorAll('.topbar nav a') : []);
    const path = location.pathname.replace(/\/+$/, '') || '/';
    let idx = links.findIndex(a => {
      const href = a.getAttribute('href') || '';
      return href === path || (href !== '/' && path.startsWith(href));
    });
    if (idx < 0) return;
    let wheelLock = 0;
    document.addEventListener('wheel', e => {
      let dx = e.deltaX, dy = e.deltaY;
      if (e.shiftKey && Math.abs(dy) > Math.abs(dx)) { dx = dy; dy = 0; }
      if (Math.abs(dx) <= Math.abs(dy) || Math.abs(dx) < 25) return;
      e.preventDefault();
      const now = Date.now();
      if (now - wheelLock < 400) return;
      wheelLock = now;
      const next = idx + (dx > 0 ? 1 : -1);
      if (next < 0 || next >= links.length) return;
      if (UI.toast) UI.toast('↔ ' + links[next].textContent.trim());
      location.href = links[next].getAttribute('href');
    }, { passive: false });
  })();

  return { tr, toast, confirm, alert, choose, validation, stream, esc, keepAwake };
})();
