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
  let raw = '';            // полный транскрипт ответов модели
  let parsed = null;       // { edited, raw, part1 }
  let activeTab = 'notes';
  let t0 = 0;
  let editMode = false;    // ручная правка текста в окне
  let editedDirty = false; // в редактуру внесены ручные правки

  /* По-сценный режим: сцены копятся по мере прохождения */
  let scenesTotal = 1;     // всего сцен (meta.scenes)
  let sceneIdx = 0;        // текущая сцена
  let scenesDone = 0;      // сколько сцен обработано
  let sceneRaw = '';       // ответ модели по текущей сцене
  let notesHead = null;    // заголовок таблицы замечаний от модели
  const notesRows = [];    // { scene, cells: [фрагмент, проблема, вариант] }
  let editedParts = [];    // редактуры сцен (fallback — исходная сцена)
  let lastPart1 = '';      // «Шаг 1» без таблицы (односценный режим)

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

  function scenePrefix() {
    return scenesTotal > 1
      ? tr('сцена {a} из {b}:', { a: sceneIdx, b: scenesTotal }) + ' '
      : '';
  }

  function pushLive(kind, txt) {
    if (kind === 'reasoning') {
      liveLabel.textContent = scenePrefix() + tr('Модель размышляет…');
      liveText.classList.add('is-think');
    } else {
      liveLabel.textContent = scenePrefix() + tr('модель пишет…');
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
    scenesTotal = 1; sceneIdx = 0; scenesDone = 0; sceneRaw = '';
    notesHead = null; notesRows.length = 0; editedParts = []; lastPart1 = '';
    setEditMode(false);
    editedDirty = false;
    setLive(true);
    resultEl.style.display = 'none';
    liveText.textContent = '';
    liveLabel.textContent = tr('соединение с моделью…');
    btnCopy.disabled = true;
    btnApply.disabled = true;
    btnApply.title = applyHint();
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
      // Обрыв связи: показываем накопленное, но НЕ собираем редактуру
      // из сырого текста — запись разрешается только после всех сцен.
      if (!parsed && raw.trim()) {
        parsed = { edited: editedJoined(), raw, part1: lastPart1 };
        renderResult();
      }
    }
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case 'meta':
        scenesTotal = ev.scenes || 1;
        modelEl.textContent =
          tr('модель: {m} · в главе {n} слов',
             { m: ev.model || '…', n: ev.words }) +
          (scenesTotal > 1 ? ' · ' + tr('{s} сцен', { s: scenesTotal }) : '');
        break;
      case 'scene':
        sceneIdx = ev.num;
        sceneRaw = ''; tail = '';
        liveText.textContent = '';
        liveLabel.textContent = scenePrefix() + tr('соединение с моделью…');
        break;
      case 'thinking':
        pushLive('reasoning', ev.text);
        break;
      case 'chunk':
        raw += ev.text;
        sceneRaw += ev.text;
        pushLive('content', ev.text);
        break;
      case 'scene_done': {
        const ps = parseEditorResponse(sceneRaw);
        scenesDone = ev.num;
        if (ps.rows) {
          if (!notesHead) notesHead = ps.rows[0];
          ps.rows.slice(1).forEach(cells => notesRows.push({
            scene: ev.num,
            cells,
            accepted: true,                    // галочка «правка принята»
            origFragment: cells[0] || '',      // фрагмент ДО правки
            origVariant: cells[2] || '',       // вариант, предложенный моделью
            variant: cells[2] || '',           // вариант (можно править)
            miss: false,                       // фрагмент не нашёлся в тексте
          }));
        }
        if (scenesTotal === 1) lastPart1 = ps.part1;
        editedParts[ev.num - 1] = ev.edited_ok
          ? ps.edited
          : (ev.original_scene || '');
        setStatus(tr('✓ сцена {a} из {b}', { a: ev.num, b: ev.total }));
        renderProgress();   // промежуточный результат — сразу в окно
        break;
      }
      case 'done':
        parsed = { edited: editedJoined(), raw, part1: lastPart1 };
        renderResult();
        setStatus(scenesTotal > 1
          ? tr('✓ готово · {n} сцен · {s} c',
               { n: scenesTotal,
                 s: Math.max(1, Math.round((Date.now() - t0) / 1000)) })
          : tr('✓ готово · {s} c',
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

  /* Редактуры сцен → текст главы. Сцена с нераспознанной редактурой
     идёт в итог своим исходным текстом (приходит в scene_done). */
  function editedJoined() {
    return editedParts
      .map(p => (p || '').trim())
      .filter(Boolean)
      .join('\n\n***\n\n');
  }

  function renderNotesPane() {
    if (notesRows.length && notesHead) {
      const withScene = scenesTotal > 1;
      // патчи по строкам возможны, только если есть текст редактуры
      const canPatch = !!(parsed && parsed.edited);
      const headCells = [
        ...(canPatch ? [tr('✓')] : []),
        ...(withScene ? [tr('Сцена')] : []),
        ...notesHead,
      ];
      paneNotes.innerHTML =
        '<table class="editor-table"><thead><tr>' +
        headCells.map(c => '<th>' + UI.esc(c) + '</th>').join('') +
        '</tr></thead><tbody>' +
        notesRows.map((r, idx) => {
          const cb = canPatch
            ? '<td class="cb-cell"><input type="checkbox" class="rowcb"' +
              (r.accepted ? ' checked' : '') +
              ' title="' + UI.esc(tr('Снимите галочку, чтобы оставить текст как был')) + '">' +
              (r.miss ? '<span class="miss-ico" title="' +
                UI.esc(tr('Фрагмент не найден в тексте — правка не применена')) +
                '">⚠</span>' : '') +
              '</td>'
            : '';
          const sc = withScene ? '<td class="sc">' + r.scene + '</td>' : '';
          const variantTd = canPatch
            ? '<td class="variant" contenteditable="true" spellcheck="false">' +
              UI.esc(r.variant) + '</td>'
            : '<td>' + UI.esc(r.cells[2] || '') + '</td>';
          return '<tr data-idx="' + idx + '"' +
              (r.accepted ? '' : ' class="is-rejected"') + '>' +
            cb + sc +
            '<td>' + UI.esc(r.cells[0] || '') + '</td>' +
            '<td>' + UI.esc(r.cells[1] || '') + '</td>' +
            variantTd + '</tr>';
        }).join('') +
        '</tbody></table>';
      notesBadge.textContent = notesRows.length;
      notesBadge.style.display = '';
    } else if (scenesTotal === 1 && parsed && parsed.part1) {
      // модель ответила без таблицы — показываем «Шаг 1» как есть
      paneNotes.innerHTML =
        '<pre class="editor-rawpre">' + UI.esc(parsed.part1) + '</pre>';
      notesBadge.style.display = 'none';
    } else {
      paneNotes.innerHTML = '<div class="editor-empty">' +
        UI.esc(tr('Замечаний нет — стилистических проблем не найдено.')) +
        '</div>';
      notesBadge.style.display = 'none';
    }
  }

  /* ── Принять / отклонить / поправить отдельную правку ──────────
     Текст в «Отредактированном тексте» — источник истины: модель уже
     внесла все правки, галочка ОТКЛОНЯЕТ (вариант → исходный фрагмент),
     повторная галочка возвращает, правка варианта подменяет его. */

  const CB_HINT = () => tr('Снимите галочку, чтобы оставить текст как был');
  const MISS_HINT = () => tr('Фрагмент не найден в тексте — правка не применена');

  function stripQuotes(s) {
    const q = '«»"\'`“”‘’';
    s = (s || '').trim();
    let a = 0, b = s.length;
    while (a < b && q.includes(s[a])) a++;
    while (b > a && q.includes(s[b - 1])) b--;
    return s.slice(a, b);
  }

  function normForMatch(s) {
    return stripQuotes(s).replace(/\s+/g, ' ').trim();
  }

  /* Первое вхождение from → to; не нашли — текст без изменений.
     Кавычки по краям срезаются с ОБЕИХ сторон: в таблице модель часто
     пишет варианты в «ёлочках», которых в прозе нет — иначе при
     повторных переключениях кавычки накапливаются. */
  function patchText(text, from, to) {
    const cands = [normForMatch(from), (from || '').trim()]
      .filter(c => c && c.length);
    const clean = stripQuotes(to);
    for (const c of cands) {
      const i = text.indexOf(c);
      if (i >= 0) {
        return { text: text.slice(0, i) + clean + text.slice(i + c.length), hits: 1 };
      }
    }
    return { text, hits: 0 };
  }

  /* Патч в пределах СВОЕЙ сцены: повторяющиеся фразы в разных сценах
     не должны превращать отклонение строки сцены 2 в правку сцены 1 */
  function patchScene(row, from, to) {
    const cur = paneEditText();
    let segs;
    if (scenesTotal > 1) {
      segs = cur.split('\n\n***\n\n');
      if (segs.length !== scenesTotal) {
        segs = cur.split(/\n[ \t]*\*\*\*[ \t]*\n/);
      }
    } else {
      segs = [cur];
    }
    const i = Math.min(row.scene - 1, segs.length - 1);
    const res = patchText(segs[i] || '', from, to);
    segs[i] = res.text;
    return {
      text: scenesTotal > 1 ? segs.join('\n\n***\n\n') : segs[0],
      hits: res.hits,
    };
  }

  function paneEditText() {
    return (paneEdited.innerText || '').replace(/\r\n/g, '\n');
  }

  function setPaneText(t) {
    paneEdited.textContent = t;
    if (parsed) parsed.edited = t;
    editedDirty = true;   // патчи строк не затираются при перерисовке
  }

  function updateMissMarker(trEl, row) {
    const cbCell = trEl.querySelector('.cb-cell');
    if (!cbCell) return;
    let ico = cbCell.querySelector('.miss-ico');
    if (row.miss && !ico) {
      ico = document.createElement('span');
      ico.className = 'miss-ico';
      ico.textContent = '⚠';
      ico.title = MISS_HINT();
      cbCell.appendChild(ico);
    } else if (!row.miss && ico) {
      ico.remove();
    }
  }

  function onRowToggle(row, trEl) {
    // в тексте сейчас либо текущий вариант (принято), либо исходный
    // фрагмент (отклонено) — подмена от того, что там фактически есть
    const res = row.accepted
      ? patchScene(row, row.variant, row.origFragment)       // отклонить
      : patchScene(row, row.origFragment, row.variant);      // вернуть
    row.accepted = !row.accepted;
    row.miss = !res.hits;
    setPaneText(res.text);
    trEl.classList.toggle('is-rejected', !row.accepted);
    updateMissMarker(trEl, row);
  }

  function onVariantInput(row, td, trEl) {
    const val = td.innerText.replace(/\u00a0/g, ' ').replace(/\n+$/, '');
    if (row.accepted && val === row.variant) return;
    const from = row.accepted ? row.variant : row.origFragment;
    const res = patchScene(row, from, val);
    row.miss = !res.hits;
    row.variant = val;
    row.accepted = true;
    setPaneText(res.text);
    trEl.classList.remove('is-rejected');
    updateMissMarker(trEl, row);
  }

  // делегирование: чекбоксы и правка варианта прямо в таблице
  paneNotes.addEventListener('change', e => {
    if (!e.target.classList || !e.target.classList.contains('rowcb')) return;
    const trEl = e.target.closest('tr');
    const row = notesRows[+trEl.dataset.idx];
    if (row) onRowToggle(row, trEl);
  });
  paneNotes.addEventListener('input', e => {
    const td = e.target.closest ? e.target.closest('td.variant') : null;
    if (!td) return;
    const trEl = td.closest('tr');
    const row = notesRows[+trEl.dataset.idx];
    if (row) onVariantInput(row, td, trEl);
  });

  /* Промежуточная отрисовка: панель результата появляется рядом
     с живым потоком сразу после первой обработанной сцены */
  function renderProgress() {
    resultEl.style.display = 'block';
    renderNotesPane();
    paneEdited.textContent = editedJoined();
  }

  /* Запись главы разрешается только после ВСЕХ сцен: при обрыве на
     середине применение накопленного стёрло бы остальные сцены */
  function allScenesDone() {
    return scenesTotal > 0 && scenesDone >= scenesTotal;
  }

  function applyHint() {
    return allScenesDone()
      ? ''
      : tr('Запись станет доступна после проверки всех сцен');
  }

  function renderResult() {
    resultEl.style.display = 'block';
    rawEl.textContent = parsed.raw;
    renderNotesPane();

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

    switchTab(notesRows.length || (scenesTotal === 1 && parsed.part1)
      ? 'notes' : 'edited');
    const canApply = !!parsed.edited && allScenesDone();
    btnCopy.disabled = false;
    btnApply.disabled = !canApply;
    btnApply.title = applyHint();
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
    else if (notesRows.length && notesHead) {
      const withScene = scenesTotal > 1;
      const head = (withScene ? [tr('Сцена'), ...notesHead] : notesHead)
        .map(c => c === '✓' ? '' : c);
      const rows = notesRows.map(r => {
        const cells = r.cells.slice();
        if (cells.length >= 3) cells[2] = r.variant;  // текущий вариант
        return (withScene ? [r.scene, ...cells] : cells).join('\t');
      });
      text = [head.join('\t'), ...rows].join('\n');
    } else if (parsed) text = parsed.part1 || '';
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
    if (!allScenesDone()) {
      UI.toast(tr('Запись станет доступна после проверки всех сцен'), 'warn');
      return;
    }
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
