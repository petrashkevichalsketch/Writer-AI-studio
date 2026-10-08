(function () {
  const num = window.CHAPTER_NUM;
  const textEl = document.getElementById('chapter-text');
  const wcEl = document.getElementById('wc');
  const statusEl = document.getElementById('status-info');
  const btnGen = document.getElementById('btn-generate');
  const btnSave = document.getElementById('btn-save');
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnApply = document.getElementById('btn-apply');
  const btnRollback = document.getElementById('btn-rollback');
  const patchStatus = document.getElementById('patch-status');
  const patchDiff = document.getElementById('patch-diff');
  const tail = document.getElementById('stream-tail');

  let streaming = false;
  let buffer = '';
  let currentPatch = null;

  function setStreaming(on) {
    streaming = on;
    btnGen.disabled = on;
    btnGen.textContent = on ? '⏳ Генерация…' : '▶ Generate';
  }

  function wc(text) {
    return text.trim() ? text.trim().split(/\s+/).length : 0;
  }

  async function generate(qaAnswers) {
    if (streaming) return;
    if (!confirm('Сгенерировать главу заново? Текущий текст будет перезаписан.')) return;

    setStreaming(true);
    textEl.textContent = '';
    buffer = '';
    if (patchDiff) patchDiff.innerHTML = '';
    if (patchStatus) patchStatus.textContent = '';
    currentPatch = null;
    if (btnApply) btnApply.disabled = true;

    tail.style.display = 'block';
    tail.textContent = qaAnswers && qaAnswers.length
      ? `соединение (с ответами на ${qaAnswers.length} вопросов)…`
      : 'соединение…';

    const fetchOpts = { method: 'POST' };
    if (qaAnswers && qaAnswers.length) {
      const fd = new FormData();
      fd.append('qa_json', JSON.stringify(qaAnswers));
      fetchOpts.body = fd;
    }

    try {
      const resp = await fetch(`/api/chapter/${num}/generate`, fetchOpts);
      if (!resp.ok || !resp.body) {
        tail.textContent = `HTTP ${resp.status}`;
        setStreaming(false);
        return;
      }
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let sseBuf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        sseBuf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = sseBuf.indexOf('\n\n')) >= 0) {
          const chunk = sseBuf.slice(0, idx);
          sseBuf = sseBuf.slice(idx + 2);
          if (!chunk.startsWith('data: ')) continue;
          let ev;
          try { ev = JSON.parse(chunk.slice(6)); } catch (e) { continue; }
          handleEvent(ev);
        }
      }
    } catch (e) {
      tail.textContent = `Ошибка: ${e.message}`;
    } finally {
      setStreaming(false);
      tail.textContent = '';
      tail.style.display = 'none';
    }
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case 'meta':
        tail.textContent = `глава «${ev.title}» · POV: ${ev.plan.pov}`;
        break;
      case 'chunk':
        buffer += ev.text;
        textEl.textContent = buffer;
        wcEl.textContent = wc(buffer);
        window.scrollTo(0, document.body.scrollHeight);
        break;
      case 'done':
        wcEl.textContent = ev.word_count;
        statusEl.innerHTML = `статус: draft · слов: <span id="wc">${ev.word_count}</span>`;
        tail.textContent = `✓ готово, ${ev.chars} знаков`;
        break;
      case 'error':
        tail.textContent = `✗ ${ev.message}`;
        break;
    }
  }

  async function save() {
    const text = textEl.textContent || '';
    const fd = new FormData();
    fd.append('text', text);
    const resp = await fetch(`/api/chapter/${num}/save`, {
      method: 'POST', body: fd,
    });
    if (!resp.ok) { alert('Не удалось сохранить'); return; }
    const data = await resp.json();
    wcEl.textContent = data.word_count;
    flash('Сохранено');
  }

  async function analyze() {
    if (!patchDiff) return;
    patchDiff.innerHTML = '';
    patchStatus.textContent = 'анализ…';
    btnAnalyze.disabled = true;
    btnApply.disabled = true;

    try {
      const resp = await fetch(`/api/chapter/${num}/analyze`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) {
        patchStatus.textContent = data.detail || `HTTP ${resp.status}`;
        return;
      }
      if (!data.ok) {
        patchStatus.textContent = `✗ ошибки валидации: ${(data.errors || []).join('; ')}`;
        renderPatch(data.patch || {}, true, data.warnings || []);
        return;
      }
      currentPatch = data.patch;
      const warns = data.warnings || [];
      patchStatus.textContent = warns.length
        ? `✓ анализ готов · ${warns.length} предупреждений`
        : '✓ анализ готов';
      btnApply.disabled = false;
      renderPatch(currentPatch, false, warns);
    } catch (e) {
      patchStatus.textContent = `ошибка: ${e.message}`;
    } finally {
      btnAnalyze.disabled = false;
    }
  }

  function renderPatch(patch, hasErrors, warnings) {
    warnings = warnings || [];
    const parts = [];

    if (warnings.length) {
      parts.push(
        `<div class="muted small" style="margin-bottom:8px">` +
        warnings.map(w => `⚠ ${esc(w)}`).join('<br>') +
        `</div>`
      );
    }

    if ((patch.events_created || []).length) {
      parts.push(`<h4>События (${patch.events_created.length})</h4>`);
      patch.events_created.forEach(e => {
        parts.push(`<div class="diff-row">· <b>${esc(e.id)}</b>: ${esc(e.description)}</div>`);
      });
    }
    if ((patch.character_state_changes || []).length) {
      parts.push(`<h4>Состояние персонажей</h4>`);
      patch.character_state_changes.forEach(c => {
        const cls = c.delta > 0 ? 'pos' : 'neg';
        parts.push(`<div class="diff-row">
          <b>${esc(c.char_id)}</b> · ${esc(c.field)}:
          <span class="${cls}">${c.delta > 0 ? '+' : ''}${c.delta}</span>
          <span class="muted small"> — ${esc(c.reason || '')}</span>
        </div>`);
      });
    }
    if ((patch.relationship_changes || []).length) {
      parts.push(`<h4>Отношения</h4>`);
      patch.relationship_changes.forEach(r => {
        const cls = r.delta > 0 ? 'pos' : 'neg';
        parts.push(`<div class="diff-row">
          ${esc(r.from)} → ${esc(r.to)} · ${esc(r.field)}:
          <span class="${cls}">${r.delta > 0 ? '+' : ''}${r.delta}</span>
          <span class="muted small"> — ${esc(r.reason || '')}</span>
        </div>`);
      });
    }
    if ((patch.knowledge_gained || []).length) {
      parts.push(`<h4>Знание</h4>`);
      patch.knowledge_gained.forEach(k => {
        parts.push(`<div class="diff-row"><b>${esc(k.char_id)}</b>: ${esc(k.fact)}</div>`);
      });
    }
    if ((patch.secrets_revealed || []).length) {
      parts.push(`<h4>Секреты</h4>`);
      patch.secrets_revealed.forEach(s => {
        parts.push(`<div class="diff-row">
          <b>${esc(s.secret_id)}</b>
          ${s.partial ? '<span class="muted">(частично)</span>' : ''}
          → ${esc((s.to_whom || []).join(', '))}
        </div>`);
      });
    }
    if ((patch.new_locations || []).length) {
      parts.push(`<h4>Новые локации</h4>`);
      patch.new_locations.forEach(l => {
        parts.push(`<div class="diff-row">· ${esc(l.name || l.id)}</div>`);
      });
    }
    if ((patch.new_institutions || []).length) {
      parts.push(`<h4>Новые институции</h4>`);
      patch.new_institutions.forEach(i => {
        parts.push(`<div class="diff-row">· ${esc(i.name || i.id)}</div>`);
      });
    }

    if (!parts.length) {
      parts.push(`<p class="muted small">Изменений нет.</p>`);
    }
    patchDiff.innerHTML = parts.join('');
  }

  async function apply() {
    if (!currentPatch) {
      patchStatus.textContent = '✗ нечего применять: сначала нажмите Analyze.';
      return;
    }
    if (!confirm('Применить патч к канону? Это создаст снапшот.')) return;
    btnApply.disabled = true;
    patchStatus.textContent = 'применение…';
    try {
      const resp = await fetch(`/api/chapter/${num}/apply`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) {
        patchStatus.textContent = `✗ ${data.detail || resp.status}`;
        btnApply.disabled = false;
        return;
      }
      patchStatus.textContent = `✓ применено ${new Date().toLocaleTimeString('ru-RU')}`;
      btnApply.disabled = true;
      flash('Патч применён');
    } catch (e) {
      patchStatus.textContent = `ошибка: ${e.message}`;
      btnApply.disabled = false;
    }
  }

  async function rollback() {
    if (!confirm(`Откатить канон к состоянию ДО главы ${num}?`)) return;
    const resp = await fetch(`/api/chapter/${num}/rollback`, { method: 'POST' });
    if (!resp.ok) {
      const d = await resp.json();
      alert(d.detail || 'Ошибка отката');
      return;
    }
    flash('Откат выполнен');
    location.reload();
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function flash(msg) {
    const el = document.createElement('div');
    el.textContent = msg;
    el.className = 'flash';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1200);
  }

  if (btnGen) btnGen.addEventListener('click', generate);
  window.startGenerationWithQA = (qa) => generate(qa);
  if (btnSave) btnSave.addEventListener('click', save);
  if (btnAnalyze) btnAnalyze.addEventListener('click', analyze);
  if (btnApply) btnApply.addEventListener('click', apply);
  if (btnRollback) btnRollback.addEventListener('click', rollback);

  textEl.addEventListener('dblclick', () => {
    textEl.contentEditable = 'true';
    textEl.focus();
  });
  textEl.addEventListener('blur', () => {
    textEl.contentEditable = 'false';
    wcEl.textContent = wc(textEl.textContent);
  });

  // Подтянуть существующий патч, если есть
  fetch(`/api/chapter/${num}/patch`)
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (!d || !patchDiff) {
        if (btnApply) btnApply.disabled = true;
        return;
      }
      currentPatch = d.patch;
      renderPatch(currentPatch, false, []);
      patchStatus.textContent = d.accepted
        ? `✓ применён ${d.applied_at || ''}`
        : 'анализ готов';
      btnApply.disabled = d.accepted;
    })
    .catch(() => {
      if (btnApply) btnApply.disabled = true;
    });

  // ──────────────────────────────────────────────────────────
  // Внешняя модель: промпт → paste
  // ──────────────────────────────────────────────────────────

  const btnPrompt   = document.getElementById('btn-prompt');
  const btnPaste    = document.getElementById('btn-paste');
  const modalPrompt = document.getElementById('modal-prompt');
  const modalPaste  = document.getElementById('modal-paste');
  const promptText  = document.getElementById('prompt-text');
  const promptSize  = document.getElementById('prompt-size');
  const pasteText   = document.getElementById('paste-text');

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  }

  async function openPromptModal() {
    if (!modalPrompt) return;
    modalPrompt.style.display = 'flex';
    promptText.value = 'загрузка…';
    if (promptSize) promptSize.textContent = '';
    try {
      const r = await fetch(`/api/chapter/${num}/prompt`);
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        promptText.value = d.detail || `HTTP ${r.status}`;
        return;
      }
      const data = await r.json();
      promptText.value = data.combined;
      if (promptSize) {
        promptSize.textContent =
          `system: ${data.system_chars} симв. · user: ${data.user_chars} симв.`;
      }
    } catch (e) {
      promptText.value = `ошибка: ${e.message}`;
    }
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(promptText.value);
      flash('Промпт скопирован');
    } catch (e) {
      promptText.select();
      flash('Скопируйте вручную: Ctrl+C');
    }
  }

  function openPasteModal() {
    if (!modalPaste) return;
    modalPaste.style.display = 'flex';
    pasteText.value = '';
    pasteText.focus();
  }

  async function savePaste() {
    const text = (pasteText.value || '').trim();
    if (!text) { alert('Пусто.'); return; }

    btnPaste && (btnPaste.disabled = true);
    const fd = new FormData();
    fd.append('text', text);

    try {
      const r = await fetch(`/api/chapter/${num}/paste`, {
        method: 'POST', body: fd,
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        alert(d.detail || `HTTP ${r.status}`);
        return;
      }
      const data = await r.json();
      textEl.textContent = text;
      wcEl.textContent = data.word_count;
      statusEl.innerHTML =
        `статус: draft · слов: <span id="wc">${data.word_count}</span>`;
      closeModal('modal-paste');
      flash('Текст вставлен — нажмите Analyze');
    } finally {
      btnPaste && (btnPaste.disabled = false);
    }
  }

  if (btnPrompt) btnPrompt.addEventListener('click', openPromptModal);
  if (btnPaste)  btnPaste.addEventListener('click', openPasteModal);

  const promptCopy = document.getElementById('prompt-copy');
  const promptDl   = document.getElementById('prompt-download');
  if (promptCopy) promptCopy.addEventListener('click', copyPrompt);
  if (promptDl)   promptDl.addEventListener('click', () => {
    window.location = `/api/chapter/${num}/prompt.txt`;
  });

  const pasteSave = document.getElementById('paste-save');
  if (pasteSave) pasteSave.addEventListener('click', savePaste);

  document.querySelectorAll('.modal-close').forEach(b => {
    b.addEventListener('click', () => closeModal(b.dataset.close));
  });

  [modalPrompt, modalPaste].forEach(m => {
    if (!m) return;
    m.addEventListener('click', (e) => {
      if (e.target === m) m.style.display = 'none';
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal('modal-prompt');
      closeModal('modal-paste');
    }
  });
})();