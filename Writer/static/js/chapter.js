(function () {
  const num = window.CHAPTER_NUM;
  const textEl = document.getElementById('chapter-text');
  const wcEl = document.getElementById('wc');
  const statusEl = document.getElementById('status-info');
  const mainEl = document.querySelector('.chapter-main');
  const btnGen = document.getElementById('btn-generate');
  const btnSave = document.getElementById('btn-save');
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnApply = document.getElementById('btn-apply');
  const btnRollback = document.getElementById('btn-rollback');
  const patchStatus = document.getElementById('patch-status');
  const patchDiff = document.getElementById('patch-diff');
  const thinkEl = document.getElementById('thinking-stream');
  const thinkBody = thinkEl && thinkEl.querySelector('.thinking-body');
  const thinkText = thinkEl && thinkEl.querySelector('.thinking-text');
  const thinkPill = document.getElementById('thinking-pill');

  let streaming = false;
  let buffer = '';
  let currentPatch = null;
  const st = UI.stream();

  function setStreaming(on) {
    streaming = on;
    btnGen.disabled = on;
    btnGen.textContent = on ? tr('⏳ Генерация…') : '▶ Generate';
    textEl.classList.toggle('is-streaming', on);
    if (mainEl) mainEl.classList.toggle('is-streaming', on);
  }

  function wc(text) {
    return text.trim() ? text.trim().split(/\s+/).length : 0;
  }

  // ── Панель размышлений модели (reasoning) ───────────────────
  // В живом режиме держим в DOM только хвост потока — старое
  // растворяется туманом сверху; полный текст копится в строке.
  const THINK_TAIL = 2000;
  let thinkingFull = '';
  let thinkingActive = false;

  // декоративная подсветка «под редактор кода»: строки, числа, стрелки
  function highlightThinking(escaped) {
    return escaped
      .replace(/("[^"\n]*"|«[^»\n]*»)/g, '<span class="tq">$1</span>')
      .replace(/\b\d+(?:[.,]\d+)?\b/g, '<span class="tn">$&</span>')
      .replace(/(→|←|=&gt;|-&gt;|✓|✗)/g, '<span class="tf">$1</span>');
  }

  function showThinking() {
    thinkEl.style.display = 'block';
    thinkEl.classList.add('is-live');
    thinkEl.classList.remove('is-collapsed', 'is-expanded');
    if (thinkPill) thinkPill.style.display = 'none';
    if (mainEl) mainEl.classList.add('is-thinking');
  }

  function onThinking(txt) {
    if (!thinkEl) return;
    if (thinkEl.style.display === 'none') showThinking();
    if (!thinkingActive) {
      thinkingActive = true;
      st.note(tr('модель размышляет…'));
    }
    thinkingFull += txt;
    const tail = thinkingFull.length > THINK_TAIL
      ? '…' + thinkingFull.slice(-THINK_TAIL)
      : thinkingFull;
    thinkText.innerHTML = highlightThinking(UI.esc(tail));
    if (thinkBody) thinkBody.scrollTop = thinkBody.scrollHeight;
  }

  function setPillText() {
    if (thinkPill) {
      thinkPill.textContent =
        tr('Размышления · {n} знаков', { n: thinkingFull.length });
    }
  }

  function collapseThinking() {
    if (!thinkEl || thinkEl.style.display === 'none' ||
        thinkEl.classList.contains('is-collapsed')) return;
    thinkEl.classList.remove('is-live');
    thinkEl.classList.add('is-collapsed');
    if (thinkPill) { setPillText(); thinkPill.style.display = 'inline-flex'; }
    if (mainEl) mainEl.classList.remove('is-thinking');
  }

  function expandThinking() {
    if (!thinkEl || !thinkingFull) return;
    thinkEl.classList.remove('is-collapsed');
    thinkEl.classList.add('is-expanded');
    setPillText();
    if (thinkBody) thinkBody.scrollTop = 0;
  }

  function resetThinking() {
    thinkingFull = '';
    thinkingActive = false;
    if (!thinkEl) return;
    thinkEl.style.display = 'none';
    thinkEl.classList.remove('is-live', 'is-collapsed', 'is-expanded');
    if (mainEl) mainEl.classList.remove('is-thinking');
  }

  if (thinkPill) thinkPill.addEventListener('click', () => {
    if (thinkEl.classList.contains('is-expanded')) collapseThinking();
    else expandThinking();
  });

  async function generate(qaAnswers) {
    if (streaming) return;
    const ok = await UI.confirm({
      title: tr('Генерация главы'),
      text: tr('Сгенерировать главу заново? Текущий текст будет перезаписан.'),
      okText: tr('Сгенерировать'),
    });
    if (!ok) return;

    setStreaming(true);
    textEl.textContent = '';
    buffer = '';
    resetThinking();
    if (patchDiff) patchDiff.innerHTML = '';
    if (patchStatus) patchStatus.textContent = '';
    currentPatch = null;
    if (btnApply) btnApply.disabled = true;

    st.reset();
    st.work(qaAnswers && qaAnswers.length
      ? tr('соединение (с ответами на {n} вопросов)…', { n: qaAnswers.length })
      : tr('соединение с моделью…'));

    const t0 = Date.now();
    let target = 0;

    const fetchOpts = { method: 'POST' };
    if (qaAnswers && qaAnswers.length) {
      const fd = new FormData();
      fd.append('qa_json', JSON.stringify(qaAnswers));
      fetchOpts.body = fd;
    }

    try {
      const resp = await fetch(`/api/chapter/${num}/generate`, fetchOpts);
      if (!resp.ok || !resp.body) {
        st.error(`HTTP ${resp.status}`);
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
          handleEvent(ev, t0, () => target, v => { target = v; });
        }
      }
    } catch (e) {
      if (thinkingActive) { thinkingActive = false; collapseThinking(); }
      st.error(tr('Ошибка: {msg}', { msg: e.message }));
    } finally {
      setStreaming(false);
    }
  }

  function handleEvent(ev, t0, getTarget, setTarget) {
    switch (ev.type) {
      case 'meta':
        setTarget((ev.plan && ev.plan.word_target) || 0);
        st.note(tr('глава «{t}» · POV: {pov} · пишет {m}…',
                   { t: ev.title, pov: ev.plan.pov,
                     m: ev.model || tr('модель') }));
        break;
      case 'thinking':
        onThinking(ev.text);
        break;
      case 'chunk':
        if (thinkingActive) {
          thinkingActive = false;
          collapseThinking();
          st.note(tr('модель пишет…'));
        }
        buffer += ev.text;
        textEl.textContent = buffer;
        wcEl.textContent = wc(buffer);
        {
          const words = wc(buffer);
          const mins = (Date.now() - t0) / 60000;
          st.progress(words, getTarget(), mins > 0.05 ? words / mins : 0);
        }
        window.scrollTo(0, document.body.scrollHeight);
        break;
      case 'continuing':
        st.warn(tr('глава короткая ({a}/{b} слов) — запрашиваю продолжение…',
                   { a: ev.have, b: ev.target }));
        break;
      case 'warning':
        st.warn(ev.message);
        break;
      case 'done':
        if (thinkingActive) { thinkingActive = false; collapseThinking(); }
        wcEl.textContent = ev.word_count;
        statusEl.innerHTML =
          tr('статус: draft · слов: <span id="wc">{n}</span>', { n: ev.word_count });
        st.done(tr('✓ готово · {w} слов · {c} знаков',
                   { w: ev.word_count, c: ev.chars }));
        UI.toast(tr('Глава сгенерирована'), 'ok');
        break;
      case 'error':
        if (thinkingActive) { thinkingActive = false; collapseThinking(); }
        st.error(`✗ ${ev.message}`);
        break;
    }
  }

  async function save() {
    // innerText, а не textContent: после ручного редактирования абзацы
    // живут как <div>/<br> и textContent склеил бы их в один абзац.
    const text = textEl.innerText || '';
    const fd = new FormData();
    fd.append('text', text);
    const resp = await fetch(`/api/chapter/${num}/save`, {
      method: 'POST', body: fd,
    });
    if (!resp.ok) { UI.toast(tr('Не удалось сохранить'), 'error'); return; }
    const data = await resp.json();
    wcEl.textContent = data.word_count;
    UI.toast(tr('Сохранено'), 'ok');
  }

  async function analyze() {
    if (!patchDiff) return;
    patchDiff.innerHTML = '';
    patchStatus.textContent = tr('анализ…');
    patchStatus.className = 'muted small';
    btnAnalyze.disabled = true;
    btnApply.disabled = true;

    try {
      const resp = await fetch(`/api/chapter/${num}/analyze`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) {
        patchStatus.textContent = data.detail || `HTTP ${resp.status}`;
        patchStatus.className = 'small st-err';
        return;
      }
      if (!data.ok) {
        patchStatus.textContent = tr('✗ ошибки валидации — см. список ниже');
        patchStatus.className = 'small st-err';
        renderPatch(data.patch || {}, true, data.warnings || []);
        UI.validation(patchDiff, data.errors || [], []);
        return;
      }
      currentPatch = data.patch;
      const warns = data.warnings || [];
      patchStatus.textContent = warns.length
        ? tr('✓ анализ готов · {n} предупреждений', { n: warns.length })
        : tr('✓ анализ готов');
      patchStatus.className = 'small st-ok';
      btnApply.disabled = false;
      renderPatch(currentPatch, false, warns);
    } catch (e) {
      patchStatus.textContent = tr('ошибка: {msg}', { msg: e.message });
      patchStatus.className = 'small st-err';
    } finally {
      btnAnalyze.disabled = false;
    }
  }

  function renderPatch(patch, hasErrors, warnings) {
    warnings = warnings || [];
    const parts = [];

    if (warnings.length) {
      parts.push(
        `<div class="chapter-hint hint-warn" style="margin-bottom:8px">` +
        `<span>⚠</span><span>${warnings.map(w => UI.esc(w)).join('<br>')}</span></div>`
      );
    }

    if ((patch.events_created || []).length) {
      parts.push(`<h4>${tr('События ({n})', { n: patch.events_created.length })}</h4>`);
      patch.events_created.forEach(e => {
        parts.push(`<div class="diff-row">· <b>${UI.esc(e.id)}</b>: ${UI.esc(e.description)}</div>`);
      });
    }
    if ((patch.character_state_changes || []).length) {
      parts.push(`<h4>${tr('Состояние персонажей')}</h4>`);
      patch.character_state_changes.forEach(c => {
        const cls = c.delta > 0 ? 'pos' : 'neg';
        parts.push(`<div class="diff-row">
          <b>${UI.esc(c.char_id)}</b> · ${UI.esc(c.field)}:
          <span class="${cls}">${c.delta > 0 ? '+' : ''}${c.delta}</span>
          <span class="muted small"> — ${UI.esc(c.reason || '')}</span>
        </div>`);
      });
    }
    if ((patch.relationship_changes || []).length) {
      parts.push(`<h4>${tr('Отношения')}</h4>`);
      patch.relationship_changes.forEach(r => {
        const cls = r.delta > 0 ? 'pos' : 'neg';
        parts.push(`<div class="diff-row">
          ${UI.esc(r.from)} → ${UI.esc(r.to)} · ${UI.esc(r.field)}:
          <span class="${cls}">${r.delta > 0 ? '+' : ''}${r.delta}</span>
          <span class="muted small"> — ${UI.esc(r.reason || '')}</span>
        </div>`);
      });
    }
    if ((patch.knowledge_gained || []).length) {
      parts.push(`<h4>${tr('Знание')}</h4>`);
      patch.knowledge_gained.forEach(k => {
        parts.push(`<div class="diff-row"><b>${UI.esc(k.char_id)}</b>: ${UI.esc(k.fact)}</div>`);
      });
    }
    if ((patch.secrets_revealed || []).length) {
      parts.push(`<h4>${tr('Секреты')}</h4>`);
      patch.secrets_revealed.forEach(s => {
        parts.push(`<div class="diff-row">
          <b>${UI.esc(s.secret_id)}</b>
          ${s.partial ? `<span class="muted">${tr('(частично)')}</span>` : ''}
          → ${UI.esc((s.to_whom || []).join(', '))}
        </div>`);
      });
    }
    if ((patch.new_locations || []).length) {
      parts.push(`<h4>${tr('Новые локации')}</h4>`);
      patch.new_locations.forEach(l => {
        parts.push(`<div class="diff-row">· ${UI.esc(l.name || l.id)}</div>`);
      });
    }
    if ((patch.new_institutions || []).length) {
      parts.push(`<h4>${tr('Новые институции')}</h4>`);
      patch.new_institutions.forEach(i => {
        parts.push(`<div class="diff-row">· ${UI.esc(i.name || i.id)}</div>`);
      });
    }

    if (!parts.length) {
      parts.push(`<h4>${tr('Изменений нет')}</h4>`);
    }
    patchDiff.innerHTML = parts.join('');
  }

  async function apply() {
    if (!currentPatch) {
      patchStatus.textContent = tr('✗ нечего применять: сначала нажмите Analyze.');
      patchStatus.className = 'small st-err';
      return;
    }
    const ok = await UI.confirm({
      title: tr('Применить патч'),
      text: tr('Применить патч к канону? Будет создан снапшот для отката.'),
      okText: tr('Применить'),
    });
    if (!ok) return;
    btnApply.disabled = true;
    patchStatus.textContent = tr('применение…');
    patchStatus.className = 'muted small';
    try {
      const resp = await fetch(`/api/chapter/${num}/apply`, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) {
        patchStatus.textContent = `✗ ${data.detail || resp.status}`;
        patchStatus.className = 'small st-err';
        btnApply.disabled = false;
        return;
      }
      patchStatus.textContent = tr('✓ применено {t}',
        { t: new Date().toLocaleTimeString() });
      patchStatus.className = 'small st-ok';
      btnApply.disabled = true;
      UI.toast(tr('Патч применён'), 'ok');
    } catch (e) {
      patchStatus.textContent = tr('ошибка: {msg}', { msg: e.message });
      patchStatus.className = 'small st-err';
      btnApply.disabled = false;
    }
  }

  async function rollback() {
    const ok = await UI.confirm({
      title: tr('Откат канона'),
      text: tr('Откатить канон к состоянию ДО главы {n}?', { n: num }),
      okText: tr('Откатить'),
      danger: true,
    });
    if (!ok) return;
    const resp = await fetch(`/api/chapter/${num}/rollback`, { method: 'POST' });
    if (!resp.ok) {
      const d = await resp.json();
      UI.alert({ title: tr('Ошибка'), text: d.detail || tr('Ошибка отката') });
      return;
    }
    UI.toast(tr('Откат выполнен'), 'ok');
    setTimeout(() => location.reload(), 700);
  }

  if (btnGen) btnGen.addEventListener('click', () => generate());
  window.startGenerationWithQA = (qa) => generate(qa);

  /* ── Переключатель профиля модели (Обычная / Сильная) ───────── */

  const modelSwitch = document.getElementById('model-switch');
  if (modelSwitch) {
    modelSwitch.querySelectorAll('.model-btn').forEach(b => {
      b.addEventListener('click', async () => {
        if (b.classList.contains('disabled')) {
          UI.toast(tr('Сильная модель не настроена (Настройки)'), 'warn');
          return;
        }
        const profile = b.dataset.profile;
        try {
          const r = await fetch('/api/chapter/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile }),
          });
          const data = await r.json().catch(() => ({}));
          if (!r.ok) {
            UI.toast(data.detail || `HTTP ${r.status}`, 'error');
            return;
          }
          modelSwitch.querySelectorAll('.model-btn').forEach(x =>
            x.classList.toggle('active', x === b));
          UI.toast(profile === 'strong'
            ? tr('Главы пишет сильная модель')
            : tr('Главы пишет обычная модель'), 'ok');
        } catch (e) {
          UI.toast(tr('Не удалось переключить: {msg}', { msg: e.message }),
                   'error');
        }
      });
    });
  }

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
    wcEl.textContent = wc(textEl.innerText);
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
        ? tr('✓ применён {t}', { t: d.applied_at || '' })
        : tr('анализ готов');
      patchStatus.className = d.accepted ? 'small st-ok' : 'muted small';
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
    promptText.value = tr('загрузка...');
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

  function openPasteModal() {
    if (!modalPaste) return;
    modalPaste.style.display = 'flex';
    pasteText.value = '';
    pasteText.focus();
  }

  async function savePaste() {
    const text = (pasteText.value || '').trim();
    if (!text) { UI.alert({ text: tr('Пусто.') }); return; }

    btnPaste && (btnPaste.disabled = true);
    const fd = new FormData();
    fd.append('text', text);

    try {
      const r = await fetch(`/api/chapter/${num}/paste`, {
        method: 'POST', body: fd,
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        UI.alert({ title: tr('Ошибка'), text: d.detail || `HTTP ${r.status}` });
        return;
      }
      const data = await r.json();
      textEl.textContent = text;
      wcEl.textContent = data.word_count;
      statusEl.innerHTML =
        tr('статус: draft · слов: <span id="wc">{n}</span>', { n: data.word_count });
      closeModal('modal-paste');
      UI.toast(tr('Текст вставлен — нажмите Analyze'), 'info');
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
})();
