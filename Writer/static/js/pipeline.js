(function () {
  const logEl = document.getElementById('log');

  /* ── Лог: липкий низ. Пока читатель у нижнего края, лог следует
     за новыми записями; колесо вверх отпускает автопрокрутку,
     пилюля «К свежим записям» плавно возвращает. ──────────────── */
  let logPinned = true;
  let logResuming = false;
  const logResumeBtn = document.getElementById('log-resume');

  function logGap() {
    return logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight;
  }
  function updateLogResume() {
    if (logResumeBtn) logResumeBtn.style.display =
      (!logPinned && logEl.scrollHeight > logEl.clientHeight) ? '' : 'none';
  }
  logEl.addEventListener('scroll', () => {
    const gap = logGap();
    if (logResuming) {
      if (gap < 20) { logResuming = false; logPinned = true; }
    } else {
      if (gap > 60) logPinned = false;       // читатель уехал вверх
      else if (gap < 20) logPinned = true;   // досмотрел до хвоста
    }
    updateLogResume();
  }, { passive: true });
  if (logResumeBtn) logResumeBtn.addEventListener('click', () => {
    logResuming = true; logPinned = true; updateLogResume();
    logEl.scrollTo({ top: logEl.scrollHeight, behavior: 'smooth' });
  });
  // для соседних скриптов (bridge.js): можно ли автопрокручивать лог
  window.logSticky = { pinned: () => logPinned };

  /* декоративная подсветка «под редактор кода» — та же, что на
     экране размышлений главы: строки, числа, стрелки, ✓/✗.
     JSON-подобные строки (превью стадий, reasoning с JSON) вместо
     этого красятся как JSON: иначе почти вся строка оказывается
     внутри «кавычек» и бурит лог (--code-str). */
  function highlightJSON(escaped) {
    const re = /("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|\b\d+(?:[.,]\d+)?\b/g;
    return escaped.replace(re, (m, str, colon, kw) => {
      if (str) {
        // ключ — голубой, строковое значение — нейтральное (.tval):
        // коричневый в JSON оставлен только прозе вне лога
        return colon
          ? '<span class="tkey">' + str + '</span>' + colon
          : '<span class="tval">' + str + '</span>';
      }
      if (kw) return '<span class="tf">' + kw + '</span>';
      return '<span class="tn">' + m + '</span>';
    });
  }

  function highlightThinking(escaped) {
    const jsonLike = /[{[]/.test(escaped) &&
                     (escaped.match(/"\s*:/g) || []).length >= 2;
    if (jsonLike) return highlightJSON(escaped);
    return escaped
      .replace(/("[^"\n]{1,80}"|«[^»\n]{1,80}»)/g, '<span class="tq">$1</span>')
      .replace(/\b\d+(?:[.,]\d+)?\b/g, '<span class="tn">$&</span>')
      .replace(/(→|←|=&gt;|-&gt;|✓|✗)/g, '<span class="tf">$1</span>');
  }
  // для соседних скриптов (bridge.js пишет в тот же лог)
  window.renderLogLine = text => highlightThinking(UI.esc(text));

  function append(text, cls) {
    const d = document.createElement('div');
    if (cls) d.className = cls;
    d.innerHTML = highlightThinking(UI.esc(text));
    logEl.appendChild(d);
    if (logPinned) logEl.scrollTop = logEl.scrollHeight;
  }

  /* метка кнопки живёт в .btn-label — svg-иконки не затираются */
  function setBtnLabel(btn, text) {
    if (!btn) return;
    const lbl = btn.querySelector('.btn-label');
    if (lbl) lbl.textContent = text;
    else btn.textContent = text;
  }

  /* ── «Голографический экран» стадии: панель статуса + мысли ──
     Те же компоненты, что у генерации глав: UI.stream + блок
     thinking-stream. Питается событиями stage_progress (локальный
     запуск) и strong-событиями (кнопка 🤖, см. bridge.js). ──────── */

  const stageMount = document.getElementById('stage-stream');
  const stageThink = document.getElementById('stage-thinking');
  const stageThinkBody =
    stageThink && stageThink.querySelector('.thinking-body');
  const stageThinkText =
    stageThink && stageThink.querySelector('.thinking-text');
  const stageThinkPill = document.getElementById('stage-thinking-pill');

  let stageSt = null;
  let stageThinkingShown = false;

  function phaseLabel(ev) {
    const p = ev.phase_params || {};
    switch (ev.phase_key) {
      case 'batch':   return tr('пакет {i}/{n} · главы {a}..{b}', p);
      case 'merging': return tr('сборка и финальная проверка плана…');
      case 'single':  return tr('одним вызовом');
      default:        return '';
    }
  }

  function showThinking(tail, total) {
    if (!stageThink || !stageThinkText || !tail) return;
    if (!stageThinkingShown) {
      stageThinkingShown = true;
      stageThink.style.display = '';
      stageThink.classList.add('is-live');
      stageThink.classList.remove('is-collapsed', 'is-expanded');
    }
    stageThinkText.innerHTML = highlightThinking(UI.esc(tail));
    if (stageThinkPill) {
      stageThinkPill.style.display = '';
      stageThinkPill.textContent =
        tr('Размышления · {n} знаков', { n: total });
    }
    if (stageThinkBody) stageThinkBody.scrollTop = stageThinkBody.scrollHeight;
  }

  function collapseThinking() {
    if (stageThink && stageThinkingShown) {
      stageThink.classList.remove('is-live');
      stageThink.classList.add('is-collapsed');
    }
  }

  const StagePanel = {
    start(name, phaseText) {
      if (!stageMount) return;
      if (!stageSt) stageSt = UI.stream(stageMount);
      stageSt.reset();
      stageSt.work(name + (phaseText ? ' · ' + phaseText : ''));
      stageThinkingShown = false;
      if (stageThink) {
        stageThink.style.display = 'none';
        stageThink.classList.remove('is-live', 'is-collapsed', 'is-expanded');
      }
      if (stageThinkPill) stageThinkPill.style.display = 'none';
    },
    progress(ev) {
      if (!stageSt) return;
      const phase = phaseLabel(ev);
      if (phase) stageSt.note(phase);
      if (ev.target > 0) {
        stageSt.progress(ev.value, ev.target, null, '<b>{n}</b> глав');
      } else if (ev.chars > 0) {
        stageSt.progress(ev.chars, 0, null, '<b>{n}</b> знаков');
      }
      showThinking(ev.tail, ev.thinking_chars);
    },
    note(text) { if (stageSt) stageSt.note(text); },
    done(text) {
      if (stageSt) stageSt.done(text);
      collapseThinking();
    },
    error(text) {
      if (stageSt) stageSt.error(text);
      collapseThinking();
    },
  };
  window.StagePanel = StagePanel;

  if (stageThinkPill) stageThinkPill.addEventListener('click', () => {
    if (!stageThink) return;
    const expanded = stageThink.classList.toggle('is-expanded');
    stageThink.classList.toggle('is-collapsed', !expanded);
  });

  function setStageStatus(name, status) {
    document.querySelectorAll(`li[data-stage="${name}"]`).forEach(li => {
      li.className = 'stage stage-' + status;
      const st = li.querySelector('.status');
      if (st) st.textContent = status;
      const ic = li.querySelector('.icon');
      if (ic) {
        if (status === 'running') {
          ic.innerHTML = '<span class="spinner spinner-sm"></span>';
        } else {
          ic.textContent =
            status === 'done' ? '✓' :
            status === 'failed' ? '✗' :
            status === 'waiting_approval' ? '✋' : '·';
        }
      }
    });
  }

  // Обёртка: на время стадии экран не гаснет (Wake Lock в ui.js),
  // иначе мобильный браузер рвёт SSE-стрим при блокировке экрана.
  async function runStage(name, qaAnswers) {
    if (window.UI && UI.keepAwake) UI.keepAwake(true);
    try {
      return await runStageInner(name, qaAnswers);
    } finally {
      if (window.UI && UI.keepAwake) UI.keepAwake(false);
    }
  }

  // Возвращает true при успехе стадии, false при провале.
  async function runStageInner(name, qaAnswers) {
    append(tr('▶ Запуск {name}', { name }), 'log-info');
    setStageStatus(name, 'running');
    if (window.StagePanel) window.StagePanel.start(name);

    let lastType = null;

    let resp;
    try {
      const fetchOpts = { method: 'POST' };
      if (qaAnswers && qaAnswers.length) {
        const fd = new FormData();
        fd.append('qa_json', JSON.stringify(qaAnswers));
        fetchOpts.body = fd;
      }
      resp = await fetch(`/api/pipeline/run/${name}`, fetchOpts);
    } catch (e) {
      append(tr('  ! сеть: {msg}', { msg: e.message }), 'log-error');
      setStageStatus(name, 'failed');
      return false;
    }

    if (!resp.ok || !resp.body) {
      append(`HTTP ${resp.status}`, 'log-error');
      setStageStatus(name, 'failed');
      return false;
    }

    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        if (!chunk.startsWith('data: ')) continue;
        let ev;
        try { ev = JSON.parse(chunk.slice(6)); } catch (e) { continue; }
        handleEvent(ev, name);
        if (ev.type === 'stage_done' || ev.type === 'stage_failed'
            || ev.type === 'error') {
          lastType = ev.type;
        }
      }
    }

    return lastType === 'stage_done';
  }

  function handleEvent(ev, name) {
    switch (ev.type) {
      case 'stage_started':
        append(tr('  → старт'), 'log-info'); break;
      case 'attempt':
        append(tr('  попытка {a}/{m}', { a: ev.attempt, m: ev.max }), 'log-info'); break;
      case 'stage_progress':
        if (window.StagePanel) window.StagePanel.progress(ev); break;
      case 'warning':
        (ev.warnings || []).forEach(w =>
          append(tr('  ⚠ предупреждение: {w}', { w }), 'log-warn'));
        break;
      case 'validation_failed':
        append(tr('  ✗ валидация: {e}', { e: ev.errors.join('; ') }), 'log-warn'); break;
      case 'stage_done':
        append(tr('  ✓ готово. Превью: {p}', { p: ev.preview }), 'log-ok');
        (ev.warnings || []).forEach(w =>
          append(tr('  ⚠ {w}', { w }), 'log-warn'));
        setStageStatus(name, 'done');
        if (window.StagePanel) window.StagePanel.done(tr('✓ готово'));
        break;
      case 'stage_failed':
        append(tr('  ✗ провал: {e}', { e: (ev.errors || []).join('; ') }), 'log-error');
        setStageStatus(name, 'failed');
        if (window.StagePanel) window.StagePanel.error(tr('✗ провал'));
        break;
      case 'exception':
        append(`  ! ${ev.message}`, 'log-error'); break;
      case 'error':
        append(`  ! ${ev.message}`, 'log-error');
        setStageStatus(name, 'failed');
        if (window.StagePanel) window.StagePanel.error(ev.message);
        break;
      case 'end':
        append(tr('— поток закрыт —'), 'log-dim'); break;
    }
  }

  // Получить список всех стадий, как они отрисованы в DOM (по порядку)
  function listAllStages() {
    const out = [];
    document.querySelectorAll('#stages-phase1 li[data-stage], #stages-phase2 li[data-stage]')
      .forEach(li => out.push(li.dataset.stage));
    return out;
  }

  function stageStatus(name) {
    const li = document.querySelector(`li[data-stage="${name}"]`);
    if (!li) return 'pending';
    const st = li.querySelector('.status');
    return st ? st.textContent : 'pending';
  }

  let autoRunning = false;

  async function runAll() {
    if (autoRunning) return;
    if (!confirm(
      tr('Запустить автосбор?\n\n' +
         '• Все стадии Фазы 1 и Фазы 2 по порядку\n' +
         '• Уже готовые (done) будут пропущены\n' +
         '• При первой ошибке автосбор останавливается\n\n' +
         'Это может занять 30–90 минут (зависит от модели).')
    )) return;

    autoRunning = true;
    const btn = document.getElementById('btn-run-all');
    if (btn) { btn.disabled = true; setBtnLabel(btn, tr('Автосбор идёт…')); }

    const stages = listAllStages();
    append('', 'log-dim');
    append(tr('═══ АВТОСБОР НАЧАТ ═══'), 'log-info');
    append(tr('Всего стадий: {n}', { n: stages.length }), 'log-dim');

    try {
      for (let i = 0; i < stages.length; i++) {
        const st = stages[i];

        if (stageStatus(st) === 'done') {
          append(tr('⏭ {s} — уже готово, пропуск', { s: st }), 'log-dim');
          continue;
        }

        append('', 'log-dim');
        append(`── [${i + 1}/${stages.length}] ${st} ──`, 'log-info');

        const ok = await runStage(st);
        if (!ok) {
          append('', 'log-dim');
          append(tr('⛔ Автосбор прерван на стадии «{s}»', { s: st }), 'log-error');
          append(tr('Проверьте ошибку выше, исправьте и запустите автосбор заново — ' +
                    'готовые стадии будут пропущены.'), 'log-dim');
          return;
        }
      }

      append('', 'log-dim');
      append(tr('═══ ✓ АВТОСБОР ЗАВЕРШЁН ═══'), 'log-ok');
      append(tr('Мир и сюжет готовы. Переходите на /world, /characters, /outline — ' +
                'проверяйте и жмите Approve.'), 'log-dim');
      UI.toast(tr('Автосбор завершён — мир и сюжет готовы'), 'ok');

    } finally {
      autoRunning = false;
      if (btn) { btn.disabled = false; setBtnLabel(btn, tr('Автосбор: мир + сюжет')); }
    }
  }

  // ─── Автосбор с уточнениями ───────────────────────────────
  const EXCLUDED_QUIZ = new Set([
    'lore_graph', 'relevance_map', 'consistency_audit',
  ]);

  async function runAllWithQuestions() {
    if (autoRunning) return;
    if (!confirm(
      tr('Запустить автосбор с уточнениями?\n\n' +
         '• Перед каждой стадией — wizard уточнений\n' +
         '• «Пропустить всё» — идти без вопросов\n' +
         '• Крестик — прервать весь автосбор\n' +
         '• Уже готовые (done) — пропускаются\n\n' +
         'Продолжить?')
    )) return;

    if (typeof window.openWizardInteractive !== 'function') {
      alert(tr('pipeline_wizard.js не загрузился.'));
      return;
    }

    autoRunning = true;
    const btn = document.getElementById('btn-run-all-qa');
    if (btn) { btn.disabled = true; setBtnLabel(btn, tr('Автосбор с вопросами…')); }

    const stages = listAllStages();
    append('', 'log-dim');
    append(tr('═══ АВТОСБОР С ВОПРОСАМИ НАЧАТ ═══'), 'log-info');
    append(tr('Всего стадий: {n}', { n: stages.length }), 'log-dim');

    try {
      for (let i = 0; i < stages.length; i++) {
        const st = stages[i];

        if (stageStatus(st) === 'done') {
          append(tr('⏭ {s} — уже готово, пропуск', { s: st }), 'log-dim');
          continue;
        }

        append('', 'log-dim');
        append(`── [${i + 1}/${stages.length}] ${st} ──`, 'log-info');

        let qa = null;

        if (!EXCLUDED_QUIZ.has(st)) {
          append(tr('  ❓ уточнения…'), 'log-info');
          const result = await window.openWizardInteractive(st, 'auto');

          if (result.action === 'cancel') {
            append(tr('⛔ Автосбор прерван пользователем'), 'log-warn');
            return;
          }
          if (result.action === 'skip') {
            append(tr('  ⏭ вопросы пропущены'), 'log-dim');
            qa = null;
          } else {
            qa = result.qa;
            append(tr('  ✓ получено ответов: {n}', { n: qa.length }), 'log-ok');
          }
        }

        const ok = await runStage(st, qa);
        if (!ok) {
          append('', 'log-dim');
          append(tr('⛔ Автосбор прерван на стадии «{s}»', { s: st }), 'log-error');
          append(tr('Проверьте ошибку выше, исправьте и запустите автосбор заново — ' +
                    'готовые стадии будут пропущены.'), 'log-dim');
          UI.toast(tr('Автосбор прерван: {s}', { s: st }), 'error');
          return;
        }
      }

      append('', 'log-dim');
      append(tr('═══ ✓ АВТОСБОР С ВОПРОСАМИ ЗАВЕРШЁН ═══'), 'log-ok');
      append(tr('Мир и сюжет готовы. Переходите на /world, /characters, /outline.'),
             'log-dim');
      UI.toast(tr('Автосбор завершён — мир и сюжет готовы'), 'ok');

    } finally {
      autoRunning = false;
      if (btn) { btn.disabled = false; setBtnLabel(btn, tr('Автосбор с вопросами')); }
    }
  }

  const btnRunAll = document.getElementById('btn-run-all');
  if (btnRunAll) btnRunAll.addEventListener('click', runAll);

  const btnRunAllQa = document.getElementById('btn-run-all-qa');
  if (btnRunAllQa) btnRunAllQa.addEventListener('click', runAllWithQuestions);

  const pingBtn = document.getElementById('btn-ping');
  if (pingBtn) pingBtn.addEventListener('click', () => runStage('_ping'));

  const clearBtn = document.getElementById('btn-clear');
  if (clearBtn) clearBtn.addEventListener('click', () => { logEl.innerHTML = ''; });

  document.querySelectorAll('button.run-one').forEach(b => {
    b.addEventListener('click', () => runStage(b.dataset.stage));
  });

  window.runStageWithQA = (stage, qa) => runStage(stage, qa);
})();
