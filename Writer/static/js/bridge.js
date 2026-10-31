(function () {
  const modalPrompt = document.getElementById('bridge-modal-prompt');
  const modalPaste  = document.getElementById('bridge-modal-paste');
  const modalVariants = document.getElementById('bridge-modal-variants');
  const promptText  = document.getElementById('bridge-prompt-text');
  const promptSize  = document.getElementById('bridge-prompt-size');
  const pasteText   = document.getElementById('bridge-paste-text');
  const pasteStatus = document.getElementById('bridge-paste-status');

  if (!modalPrompt || !modalPaste) return;

  let currentStage = null;

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  }

  async function openPromptModal(stage) {
    currentStage = stage;
    modalPrompt.style.display = 'flex';
    promptText.value = tr('загрузка...');
    if (promptSize) promptSize.textContent = '';
    try {
      const r = await fetch(`/api/pipeline/${stage}/prompt`);
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        promptText.value = d.detail || `HTTP ${r.status}`;
        return;
      }
      const data = await r.json();
      promptText.value = data.combined;
      if (promptSize) {
        promptSize.textContent =
          tr('system: {a} симв. · user: {b} симв.',
             { a: data.system_chars, b: data.user_chars });
      }
    } catch (e) {
      promptText.value = tr('ошибка: {msg}', { msg: e.message });
    }
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(promptText.value);
      UI.toast(tr('Промпт скопирован'), 'ok');
    } catch (e) {
      promptText.select();
      UI.toast(tr('Скопируйте вручную: Ctrl+C'), 'warn');
    }
  }

  function openPasteModal(stage) {
    currentStage = stage;
    modalPaste.style.display = 'flex';
    pasteText.value = '';
    pasteStatus.textContent = '';
    pasteText.focus();
  }

  async function savePaste() {
    if (!currentStage) return;
    const text = (pasteText.value || '').trim();
    if (!text) { UI.alert({ text: tr('Пусто.') }); return; }

    pasteStatus.textContent = tr('проверка…');
    pasteStatus.className = 'muted small';

    const fd = new FormData();
    fd.append('text', text);

    try {
      const r = await fetch(`/api/pipeline/${currentStage}/paste`, {
        method: 'POST', body: fd,
      });
      const data = await r.json();
      if (!r.ok) {
        UI.validation(pasteStatus, [data.detail || `HTTP ${r.status}`], []);
        return;
      }
      if (!data.ok) {
        pasteStatus.textContent = '';
        UI.validation(pasteStatus, data.errors || [], []);
        return;
      }
      pasteStatus.textContent = tr('✓ сохранено');
      pasteStatus.className = 'small st-ok';
      UI.toast(tr('Стадия обновлена'), 'ok');
      setTimeout(() => location.reload(), 800);
    } catch (e) {
      UI.validation(pasteStatus, [e.message], []);
    }
  }

  /* ── 🤖 Написать сильной моделью (SSE в общий лог пайплайна) ── */

  const logEl = document.getElementById('log');

  function appendLog(text, cls) {
    if (!logEl) return;
    const d = document.createElement('div');
    if (cls) d.className = cls;
    d.textContent = text;
    logEl.appendChild(d);
    logEl.scrollTop = logEl.scrollHeight;
  }

  let strongRunning = false;
  let strongChars = 0;
  let strongShown = 0;
  let strongTail = '';
  let strongThinkingChars = 0;

  async function runStrong(stage) {
    if (strongRunning) {
      UI.toast(tr('Сильная модель уже работает — дождитесь завершения'), 'warn');
      return;
    }
    strongRunning = true;
    strongChars = 0;
    strongShown = 0;
    strongTail = '';
    strongThinkingChars = 0;
    appendLog(tr('🤖 Запрос к сильной модели: {name}', { name: stage }), 'log-info');
    let doneType = null;
    try {
      const resp = await fetch(`/api/pipeline/${stage}/strong`, { method: 'POST' });
      if (!resp.ok || !resp.body) {
        const d = await resp.json().catch(() => ({}));
        appendLog(d.detail || `HTTP ${resp.status}`, 'log-error');
        return;
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
          handleStrongEvent(ev);
          if (ev.type === 'strong_done' || ev.type === 'stage_failed'
              || ev.type === 'error') {
            doneType = ev.type;
          }
        }
      }
    } catch (e) {
      appendLog(tr('  ! сеть: {msg}', { msg: e.message }), 'log-error');
      return;
    } finally {
      strongRunning = false;
    }
    if (doneType === 'strong_done') {
      UI.toast(tr('Сильная модель закончила — вариант сохранён'), 'ok');
      appendLog(tr('Откройте 🗂 «Варианты стадии», чтобы сравнить и применить.'),
                'log-info');
    }
  }

  function handleStrongEvent(ev) {
    const panel = window.StagePanel;
    switch (ev.type) {
      case 'strong_started':
        appendLog(tr('  → модель: {m}', { m: ev.model }), 'log-info');
        if (panel) panel.start(ev.stage,
          tr('сильная модель · {m}', { m: ev.model }));
        break;
      case 'attempt':
        appendLog(tr('  попытка {a}/{m}', { a: ev.attempt, m: ev.max }), 'log-info');
        break;
      case 'chunk':
        strongChars += (ev.text || '').length;
        if (panel) {
          panel.progress({ phase_key: '', chars: strongChars, target: 0,
                           tail: '', thinking_chars: 0 });
        }
        if (strongChars - strongShown >= 1000) {
          strongShown = strongChars;
          appendLog(tr('  … получено {n} симв.', { n: strongChars }), 'log-dim');
        }
        break;
      case 'thinking':
        strongThinkingChars += (ev.text || '').length;
        strongTail = (strongTail + (ev.text || '')).slice(-600);
        if (panel) {
          panel.progress({ phase_key: '', chars: strongChars, target: 0,
                           tail: strongTail,
                           thinking_chars: strongThinkingChars });
        }
        break;
      case 'warning':
        (ev.warnings || []).forEach(w =>
          appendLog(tr('  ⚠ предупреждение: {w}', { w }), 'log-warn'));
        break;
      case 'validation_failed':
        appendLog(tr('  ✗ валидация: {e}', { e: (ev.errors || []).join('; ') }),
                  'log-warn');
        if (panel) panel.note(tr('валидация ответа…'));
        break;
      case 'exception':
        appendLog(`  ! ${ev.message}`, 'log-error'); break;
      case 'strong_done':
        appendLog(tr('  ✓ вариант «сильная модель» сохранён (id {id})',
                     { id: ev.variant_id }), 'log-ok');
        if (panel) panel.done(tr('✓ вариант сохранён'));
        break;
      case 'stage_failed':
        appendLog(tr('  ✗ провал: {e}', { e: (ev.errors || []).join('; ') }),
                  'log-error');
        if (panel) panel.error(tr('✗ провал'));
        break;
      case 'error':
        appendLog(`  ! ${ev.message}`, 'log-error');
        if (panel) panel.error(ev.message);
        break;
      case 'end':
        appendLog(tr('— поток закрыт —'), 'log-dim'); break;
    }
  }

  /* ── 🗂 Варианты стадии: список, сравнение, применение ──────── */

  function variantLabel(kind) {
    return { local:     tr('Локальная модель'),
             strong:    tr('Сильная модель'),
             manual:    tr('Вставка вручную') }[kind] || kind;
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function fmtVal(v) {
    if (v === null || v === undefined) return '—';
    if (Array.isArray(v)) return v.join(', ');
    return String(v);
  }

  function diffLabel(row) {
    const p = row.params || {};
    switch (row.key) {
      case 'chapters_count':     return tr('Глав (текущий → вариант)');
      case 'chapter_field':      return tr('Глава {num}: {field}', p);
      case 'chapter_beats':      return tr('Глава {num}: число сцен', p);
      case 'chapter_scenes_sum': return tr('Глава {num}: сумма word_target сцен', p);
      case 'chapter_events':     return tr('Глава {num}: events', p);
      case 'chapter_secrets':    return tr('Глава {num}: secrets_touched', p);
      case 'chapter_same':       return tr('Глава {num}: без изменений', p);
      case 'list_count':         return tr('{key}: элементов', p);
      case 'ids_added':          return tr('{key}: добавлены id', p);
      case 'ids_removed':        return tr('{key}: удалены id', p);
      case 'keys_count':         return tr('{key}: ключей', p);
      case 'field':              return p.key || row.key;
      default:                   return row.key;
    }
  }

  async function openVariantsModal(stage) {
    modalVariants.style.display = 'flex';
    document.getElementById('bridge-variants-title').textContent =
      tr('Варианты стадии: {stage}', { stage });
    const listEl = document.getElementById('bridge-variants-list');
    const diffEl = document.getElementById('bridge-variants-diff');
    const statusEl = document.getElementById('bridge-variants-status');
    diffEl.innerHTML = '';
    statusEl.textContent = tr('загрузка…');
    listEl.innerHTML = '';
    let data;
    try {
      const r = await fetch(`/api/pipeline/${stage}/variants`);
      data = await r.json();
    } catch (e) {
      statusEl.textContent = '✗ ' + e.message;
      return;
    }
    statusEl.textContent = '';
    const vs = data.variants || [];
    if (!vs.length) {
      listEl.innerHTML =
        `<span class="muted small">${esc(
          tr('Вариантов пока нет — запустите стадию ▶, нажмите 🤖 или вставьте JSON через 📥.'))}</span>`;
      return;
    }
    vs.forEach(v => listEl.appendChild(renderVariant(stage, v)));
  }

  function renderVariant(stage, v) {
    const row = document.createElement('div');
    row.className = 'variant-item' + (v.is_active ? ' active-variant' : '');
    const created = (v.created_at || '').replace('T', ' ').slice(0, 16);
    row.innerHTML =
      `<span class="v-name">${esc(variantLabel(v.variant))}</span>` +
      (v.is_active
        ? `<span class="badge badge-ok">${esc(tr('активный'))}</span>` : '') +
      `<span class="v-meta">${esc(created)} · ${v.chars} ${esc(tr('симв.'))}</span>` +
      `<span class="v-actions"></span>`;
    const actions = row.querySelector('.v-actions');
    if (!v.is_active) {
      const cmp = document.createElement('button');
      cmp.textContent = tr('⚖ Сравнить');
      cmp.addEventListener('click', () => compareVariant(stage, v.id));
      actions.appendChild(cmp);
      const act = document.createElement('button');
      act.className = 'primary';
      act.textContent = tr('✓ Применить');
      act.addEventListener('click', () => activateVariant(stage, v.id));
      actions.appendChild(act);
    }
    return row;
  }

  async function compareVariant(stage, id) {
    const diffEl = document.getElementById('bridge-variants-diff');
    const statusEl = document.getElementById('bridge-variants-status');
    statusEl.textContent = tr('сравнение…');
    diffEl.innerHTML = '';
    let data;
    try {
      const r = await fetch(`/api/pipeline/${stage}/variants/${id}/compare`);
      data = await r.json();
    } catch (e) {
      statusEl.textContent = '✗ ' + e.message;
      return;
    }
    statusEl.textContent = '';
    if (!data.ok) {
      statusEl.textContent = '✗ ' + (data.errors || []).join('; ');
      return;
    }
    const rowsHtml = (data.rows || []).map(row => {
      const cls = row.key === 'chapter_same' ? 'd-same'
                  : (row.changed ? 'd-changed' : '');
      return `<div class="vdiff-row ${cls}">` +
        `<span class="d-label">${esc(diffLabel(row))}</span>` +
        `<span class="d-val">${esc(fmtVal(row.a))}</span>` +
        `<span class="d-val">${esc(fmtVal(row.b))}</span>` +
        `</div>`;
    }).join('');
    diffEl.innerHTML =
      `<h4 style="margin:4px 0 8px">${esc(tr('Текущий слой → выбранный вариант'))}</h4>` +
      (rowsHtml || `<span class="muted small">${esc(tr('Различий нет.'))}</span>`);
    if (data.errors_now && data.errors_now.length) {
      diffEl.innerHTML +=
        `<div class="val-panel" style="margin-top:10px">` +
        `<div class="val-head">${esc(
          tr('⚠ Вариант не проходит валидацию против текущей библии ({n})',
             { n: data.errors_now.length }))}</div>` +
        `<ol class="val-list">${data.errors_now.map(x => `<li>${esc(x)}</li>`).join('')}</ol>` +
        `</div>`;
    } else {
      diffEl.innerHTML +=
        `<p class="muted small">✓ ${esc(tr('Вариант валиден против текущей библии.'))}</p>`;
    }
  }

  async function activateVariant(stage, id) {
    const ok = await UI.confirm({
      title: tr('Применить вариант'),
      text: tr('Вариант заменит текущий активный слой стадии «{stage}». ' +
               'Стадии, собранные после неё, могут стать неактуальными. ' +
               'Продолжить?', { stage }),
      okText: tr('Применить'),
    });
    if (!ok) return;
    const statusEl = document.getElementById('bridge-variants-status');
    statusEl.textContent = tr('применение…');
    try {
      const r = await fetch(`/api/pipeline/${stage}/variants/${id}/activate`,
                            { method: 'POST' });
      const data = await r.json();
      if (!r.ok || !data.ok) {
        statusEl.textContent = '';
        UI.alert({ text: (data.errors || [`HTTP ${r.status}`]).join('\n') });
        return;
      }
      UI.toast(tr('Вариант применён'), 'ok');
      setTimeout(() => location.reload(), 600);
    } catch (e) {
      statusEl.textContent = '✗ ' + e.message;
    }
  }

  /* ── Привязка кнопок ────────────────────────────────────────── */

  document.querySelectorAll('.bridge-prompt').forEach(b => {
    b.addEventListener('click', () => openPromptModal(b.dataset.stage));
  });
  document.querySelectorAll('.bridge-paste').forEach(b => {
    b.addEventListener('click', () => openPasteModal(b.dataset.stage));
  });
  document.querySelectorAll('.bridge-strong').forEach(b => {
    b.addEventListener('click', () => runStrong(b.dataset.stage));
  });
  document.querySelectorAll('.bridge-variants').forEach(b => {
    b.addEventListener('click', () => openVariantsModal(b.dataset.stage));
  });

  const copyBtn = document.getElementById('bridge-prompt-copy');
  const dlBtn   = document.getElementById('bridge-prompt-download');
  if (copyBtn) copyBtn.addEventListener('click', copyPrompt);
  if (dlBtn)   dlBtn.addEventListener('click', () => {
    if (currentStage) window.location = `/api/pipeline/${currentStage}/prompt.txt`;
  });

  const saveBtn = document.getElementById('bridge-paste-save');
  if (saveBtn) saveBtn.addEventListener('click', savePaste);

  document.querySelectorAll('[data-bridge-close]').forEach(b => {
    b.addEventListener('click', () => closeModal(b.dataset.bridgeClose));
  });

  [modalPrompt, modalPaste, modalVariants].forEach(m => {
    if (!m) return;
    m.addEventListener('click', (e) => {
      if (e.target === m) m.style.display = 'none';
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal('bridge-modal-prompt');
      closeModal('bridge-modal-paste');
      closeModal('bridge-modal-variants');
    }
  });
})();
