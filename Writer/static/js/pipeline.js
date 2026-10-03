(function () {
  const logEl = document.getElementById('log');

  function append(text, cls) {
    const d = document.createElement('div');
    if (cls) d.className = cls;
    d.textContent = text;
    logEl.appendChild(d);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setStageStatus(name, status) {
    document.querySelectorAll(`li[data-stage="${name}"]`).forEach(li => {
      li.className = 'stage stage-' + status;
      const st = li.querySelector('.status');
      if (st) st.textContent = status;
      const ic = li.querySelector('.icon');
      if (ic) {
        ic.textContent =
          status === 'done' ? '✓' :
          status === 'running' ? '●' :
          status === 'failed' ? '✗' :
          status === 'waiting_approval' ? '✋' : '·';
      }
    });
  }

  // Возвращает true при успехе стадии, false при провале.
  async function runStage(name) {
    append(`▶ Запуск ${name}`, 'log-info');
    setStageStatus(name, 'running');

    let lastType = null;

    let resp;
    try {
      resp = await fetch(`/api/pipeline/run/${name}`, { method: 'POST' });
    } catch (e) {
      append(`  ! сеть: ${e.message}`, 'log-error');
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
        append('  → старт', 'log-info'); break;
      case 'attempt':
        append(`  попытка ${ev.attempt}/${ev.max}`, 'log-info'); break;
      case 'warning':
        (ev.warnings || []).forEach(w =>
          append(`  ⚠ предупреждение: ${w}`, 'log-warn'));
        break;
      case 'validation_failed':
        append(`  ✗ валидация: ${ev.errors.join('; ')}`, 'log-warn'); break;
      case 'stage_done':
        append(`  ✓ готово. Превью: ${ev.preview}`, 'log-ok');
        (ev.warnings || []).forEach(w =>
          append(`  ⚠ ${w}`, 'log-warn'));
        setStageStatus(name, 'done'); break;
      case 'stage_failed':
        append(`  ✗ провал: ${(ev.errors || []).join('; ')}`, 'log-error');
        setStageStatus(name, 'failed'); break;
      case 'exception':
        append(`  ! ${ev.message}`, 'log-error'); break;
      case 'error':
        append(`  ! ${ev.message}`, 'log-error');
        setStageStatus(name, 'failed'); break;
      case 'end':
        append('— поток закрыт —', 'log-dim'); break;
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
      'Запустить автосбор?\n\n' +
      '• Все стадии Фазы 1 и Фазы 2 по порядку\n' +
      '• Уже готовые (done) будут пропущены\n' +
      '• При первой ошибке автосбор останавливается\n\n' +
      'Это может занять 30–90 минут (зависит от модели).'
    )) return;

    autoRunning = true;
    const btn = document.getElementById('btn-run-all');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Автосбор идёт…'; }

    const stages = listAllStages();
    append('', 'log-dim');
    append('═══ АВТОСБОР НАЧАТ ═══', 'log-info');
    append(`Всего стадий: ${stages.length}`, 'log-dim');

    try {
      for (let i = 0; i < stages.length; i++) {
        const st = stages[i];

        if (stageStatus(st) === 'done') {
          append(`⏭ ${st} — уже готово, пропуск`, 'log-dim');
          continue;
        }

        append('', 'log-dim');
        append(`── [${i + 1}/${stages.length}] ${st} ──`, 'log-info');

        const ok = await runStage(st);
        if (!ok) {
          append('', 'log-dim');
          append(`⛔ Автосбор прерван на стадии «${st}»`, 'log-error');
          append('Проверьте ошибку выше, исправьте и запустите автосбор заново — ' +
                 'готовые стадии будут пропущены.', 'log-dim');
          return;
        }
      }

      append('', 'log-dim');
      append('═══ ✓ АВТОСБОР ЗАВЕРШЁН ═══', 'log-ok');
      append('Мир и сюжет готовы. Переходите на /world, /characters, /outline — ' +
             'проверяйте и жмите Approve.', 'log-dim');

    } finally {
      autoRunning = false;
      if (btn) { btn.disabled = false; btn.textContent = '▶▶ Автосбор: мир + сюжет'; }
    }
  }

  const btnRunAll = document.getElementById('btn-run-all');
  if (btnRunAll) btnRunAll.addEventListener('click', runAll);

  const pingBtn = document.getElementById('btn-ping');
  if (pingBtn) pingBtn.addEventListener('click', () => runStage('_ping'));

  const clearBtn = document.getElementById('btn-clear');
  if (clearBtn) clearBtn.addEventListener('click', () => { logEl.innerHTML = ''; });

  document.querySelectorAll('button.run-one').forEach(b => {
    b.addEventListener('click', () => runStage(b.dataset.stage));
  });
})();