/* ═══════════════════════════════════════════════════════════════
   Корректор главы: кнопка «Редактор» открывает модальное окно,
   текст главы уходит на /api/chapter/{n}/editor (SSE), ответ
   модели разбирается на таблицу замечаний и отредактированный
   вариант. Текст главы перезаписывается только по кнопке.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const num = window.CHAPTER_NUM;
  const textEl = document.getElementById('chapter-text');
  const statusEl = document.getElementById('status-info');

  const btnEditor = document.getElementById('btn-editor');
  const modal = document.getElementById('modal-editor');
  const btnRun = document.getElementById('editor-run');
  const runLabel = document.getElementById('editor-run-label');
  const modelEl = document.getElementById('editor-model');
  const edStatus = document.getElementById('editor-status');
  const liveEl = document.getElementById('editor-live');
  const liveLabel = document.getElementById('editor-live-label');
  const liveText = document.getElementById('editor-live-text');
  const resultEl = document.getElementById('editor-result');
  const tabsEl = document.getElementById('editor-tabs');
  const paneNotes = document.getElementById('editor-pane-notes');
  const paneEdited = document.getElementById('editor-pane-edited');
  const paneRaw = document.getElementById('editor-pane-raw');
  const rawEl = document.getElementById('editor-raw');
  const notesBadge = document.getElementById('editor-notes-count');
  const btnCopy = document.getElementById('editor-copy');
  const btnApply = document.getElementById('editor-apply');
  const btnEdit = document.getElementById('editor-editmode');

  if (!modal) return;

  let running = false;
  let raw = '';          // полный ответ модели
  let parsed = null;     // { rows, part1, edited, raw }
  let activeTab = 'notes';
  let t0 = 0;
  let editMode = false;  // ручная правка текста в окне
  let editedDirty = false; // в редактуру внесены ручные правки

  /* ── Разбор ответа: Шаг 1 (таблица) / Шаг 2 (редактура) ─────── */

  function stripFence(s) {
    const t = (s || '').trim();
    if (t.startsWith('```') && t.endsWith('```') &&
        t.split('```').length - 1 === 2) {
      const nl = t.indexOf('\n');
      if (nl > 0) return t.slice(nl + 1).replace(/```\s*$/, '').trim();
    }
    return t;
  }

  function parseEditorResponse(src) {
    src = stripFence(src);
    // Граница «Шаг 2 / Step 2» — заголовок в любой разметке (#, **, :)
    const m = src.match(
      /(?:^|\n)[ \t]*(?:#{1,6}[ \t]*)?\**[ \t]*(?:Шаг|Step)[ \t]*2\b[^\n]*/i);
    let part1 = src, part2 = '';
    if (m && m.index != null) {
      part1 = src.slice(0, m.index).trim();
      part2 = src.slice(m.index + m[0].length).trim();
      part2 = part2.replace(/^[ \t]*[:.—-][ \t]*/, '');
    }
    return { rows: extractTable(part1), part1, edited: stripFence(part2), raw: src };
  }

  function extractTable(text) {
    const rows = [];
    for (const line of (text || '').split('\n')) {
      const t = line.trim();
      if (!t.startsWith('|') || !t.endsWith('|')) continue;
      const cells = t.slice(1, -1).split('|').map(c => c.trim());
      if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue;  // разделитель
      rows.push(cells);
    }
    // таблица = заголовок + хотя бы одна строка замечаний
    return rows.length >= 2 ? rows : null;
  }

  /* ── Статусная строка ───────────────────────────────────────── */

  function setStatus(text, cls) {
    edStatus.textContent = text;
    edStatus.className = 'muted small' + (cls ? ' ' + cls : '');
  }

  /* ── Живой хвост потока ─────────────────────────────────────── */

  const LIVE_TAIL = 1200;
  let tail = '';

  function pushLive(kind, txt) {
    if (kind === 'reasoning') {
      liveLabel.textContent = tr('Модель размышляет…');
      liveText.classList.add('is-think');
    } else {
      liveLabel.textContent = tr('модель пишет…');
      liveText.classList.remove('is-think');
    }
    tail = (tail + txt).slice(-LIVE_TAIL);
    liveText.textContent = tail.length >= LIVE_TAIL ? '…' + tail : tail;
    const body = liveText.closest('.editor-live-body');
    if (body) body.scrollTop = body.scrollHeight;
  }

  /* ── Запуск проверки ────────────────────────────────────────── */

  function setRunning(on) {
    running = on;
    btnRun.disabled = on;
    if (runLabel) {
      runLabel.textContent = on ? tr('Проверка…') : tr('Проверить текст');
    }
  }

  async function run() {
    if (running) return;
    const text = (textEl.innerText || '').trim();
    if (!text) {
      UI.toast(tr('Глава пуста — сначала сгенерируйте или вставьте текст.'), 'warn');
      return;
    }

    setRunning(true);
    raw = ''; tail = ''; parsed = null;
    setEditMode(false);
    editedDirty = false;
    setLive(true);
    resultEl.style.display = 'none';
    liveText.textContent = '';
    liveLabel.textContent = tr('соединение с моделью…');
    btnCopy.disabled = true;
    btnApply.disabled = true;
    if (btnEdit) btnEdit.disabled = true;
    setStatus(tr('проверка…'));
    t0 = Date.now();

    try {
      const resp = await fetch(`/api/chapter/${num}/editor`, { method: 'POST' });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
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
      setStatus(tr('Ошибка: {msg}', { msg: e.message }), 'st-err');
    } finally {
      setRunning(false);
      setLive(false);
      // Частичный ответ тоже показываем — не пропадает зря
      if (raw.trim() && !parsed) {
        parsed = parseEditorResponse(raw);
        renderResult();
      }
    }
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case 'meta':
        modelEl.textContent = tr('модель: {m} · в главе {n} слов',
                                 { m: ev.model || '…', n: ev.words });
        break;
      case 'thinking':
        pushLive('reasoning', ev.text);
        break;
      case 'chunk':
        raw += ev.text;
        pushLive('content', ev.text);
        break;
      case 'done':
        parsed = parseEditorResponse(raw);
        renderResult();
        setStatus(tr('✓ готово · {s} c',
                     { s: Math.max(1, Math.round((Date.now() - t0) / 1000)) }),
                  'st-ok');
        break;
      case 'error':
        setStatus(ev.message, 'st-err');
        break;
    }
  }

  function setLive(show) {
    liveEl.style.display = show ? 'block' : 'none';
    if (show) resultEl.style.display = 'none';
  }

  /* ── Ручная правка редактуры перед записью ──────────────────── */

  function setEditMode(on) {
    if (!parsed || !parsed.edited) on = false;
    editMode = on;
    paneEdited.contentEditable = on ? 'true' : 'false';
    paneEdited.classList.toggle('is-editing', on);
    if (btnEdit) btnEdit.classList.toggle('on', on);
    if (on) {
      switchTab('edited');
      paneEdited.focus();
    }
  }

  if (btnEdit) btnEdit.addEventListener('click', () => setEditMode(!editMode));
  // правка возможна и без переключателя? нет: вводим текст только в режиме правки
  paneEdited.addEventListener('input', () => { editedDirty = true; });

  /* ── Отрисовка результата ───────────────────────────────────── */

  function renderResult() {
    resultEl.style.display = 'block';
    rawEl.textContent = parsed.raw;

    // Таблица замечаний (или запасной показ текста Шага 1)
    if (parsed.rows) {
      const [head, ...body] = parsed.rows;
      paneNotes.innerHTML =
        '<table class="editor-table"><thead><tr>' +
        head.map(c => '<th>' + UI.esc(c) + '</th>').join('') +
        '</tr></thead><tbody>' +
        body.map(r => '<tr>' +
          r.map(c => '<td>' + UI.esc(c) + '</td>').join('') + '</tr>').join('') +
        '</tbody></table>';
      notesBadge.textContent = body.length;
      notesBadge.style.display = '';
    } else if (parsed.part1) {
      paneNotes.innerHTML =
        '<pre class="editor-rawpre">' + UI.esc(parsed.part1) + '</pre>';
      notesBadge.style.display = 'none';
    } else {
      paneNotes.innerHTML = '<div class="editor-empty">' +
        UI.esc(tr('Замечаний нет — стилистических проблем не найдено.')) +
        '</div>';
      notesBadge.style.display = 'none';
    }

    // Отредактированный вариант. Ручные правки не затираем:
    // при повторном открытии окна с кэшированным результатом
    // пользователь продолжает с того места, где остановился.
    if (parsed.edited) {
      if (!editedDirty) paneEdited.textContent = parsed.edited;
    } else {
      paneEdited.innerHTML = '<div class="editor-empty">' +
        UI.esc(tr('Модель не вернула отредактированный вариант — ' +
                  'смотрите вкладку «Ответ модели».')) +
        '</div>';
    }

    switchTab(parsed.rows || parsed.part1 ? 'notes' : 'edited');
    btnCopy.disabled = false;
    btnApply.disabled = !parsed.edited;
    if (btnEdit) btnEdit.disabled = !parsed.edited;
    if (btnEdit) btnEdit.classList.toggle('on', editMode);
  }

  function switchTab(name) {
    activeTab = name;
    tabsEl.querySelectorAll('.editor-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name));
    paneNotes.style.display = name === 'notes' ? '' : 'none';
    paneEdited.style.display = name === 'edited' ? '' : 'none';
    paneRaw.style.display = name === 'raw' ? '' : 'none';
  }

  tabsEl.addEventListener('click', e => {
    const b = e.target.closest('.editor-tab');
    if (b) switchTab(b.dataset.tab);
  });

  /* ── Копирование текущей вкладки ────────────────────────────── */

  function copyCurrent() {
    let text = '';
    if (activeTab === 'edited') text = editedText();
    else if (activeTab === 'raw') text = raw;
    else if (parsed && parsed.rows) {
      text = parsed.rows.map(r => r.join('\t')).join('\n');
    } else if (parsed) text = parsed.part1;
    if (!text) return;
    navigator.clipboard.writeText(text)
      .then(() => UI.toast(tr('Скопировано'), 'ok'))
      .catch(() => UI.toast(tr('Не удалось скопировать'), 'warn'));
  }

  /* Текущая редактура: как в панели — с ручными правками, если они были */
  function editedText() {
    return (paneEdited.innerText || '').trim();
  }

  /* ── Замена текста главы отредактированным вариантом ────────── */

  async function applyEdited() {
    if (!parsed || !parsed.edited) return;
    const text = editedText();
    if (!text) {
      UI.toast(tr('Редактура пуста — нечего записывать.'), 'warn');
      return;
    }
    const ok = await UI.confirm({
      title: tr('Заменить текст главы'),
      text: tr('Заменить текущий текст главы отредактированным вариантом? ' +
               'Текущий текст будет перезаписан.'),
      okText: tr('Заменить'),
    });
    if (!ok) return;
    btnApply.disabled = true;
    const fd = new FormData();
    fd.append('text', text);
    try {
      const r = await fetch(`/api/chapter/${num}/save`, {
        method: 'POST', body: fd,
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        UI.alert({ title: tr('Ошибка'),
                   text: d.detail || `HTTP ${r.status}` });
        btnApply.disabled = false;
        return;
      }
      const data = await r.json();
      textEl.textContent = text;
      if (statusEl) {
        statusEl.innerHTML =
          tr('статус: draft · слов: <span id="wc">{n}</span>',
             { n: data.word_count });
      }
      modal.style.display = 'none';
      setEditMode(false);
      UI.toast(tr('Текст главы заменён отредактированным вариантом'), 'ok');
    } catch (e) {
      UI.alert({ title: tr('Ошибка'),
                 text: tr('Ошибка: {msg}', { msg: e.message }) });
      btnApply.disabled = false;
    }
  }

  /* ── Открытие окна ──────────────────────────────────────────── */

  function openModal() {
    if (textEl.classList.contains('is-streaming')) {
      UI.toast(tr('Дождитесь окончания генерации главы.'), 'warn');
      return;
    }
    modal.style.display = 'flex';
    setEditMode(false);                // правка всегда включается осознанно
    if (parsed) renderResult();        // прошлый результат — сразу в окно
    else if (!running) run();          // первый запуск — проверяем сразу
  }

  if (btnEditor) btnEditor.addEventListener('click', openModal);
  if (btnRun) btnRun.addEventListener('click', run);
  if (btnCopy) btnCopy.addEventListener('click', copyCurrent);
  if (btnApply) btnApply.addEventListener('click', applyEdited);
})();
