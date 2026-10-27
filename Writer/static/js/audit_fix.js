(function () {
  const modal = document.getElementById('fix-modal');
  if (!modal) return;

  const layerEl     = document.getElementById('fix-layer');
  const layerWarnEl = document.getElementById('fix-layer-warning');
  const sevEl       = document.getElementById('fix-severity');
  const descEl      = document.getElementById('fix-description');
  const suggEl      = document.getElementById('fix-suggestion');
  const applyBtn    = document.getElementById('fix-apply');
  const rollbackBtn = document.getElementById('fix-rollback');
  const reloadBtn   = document.getElementById('fix-reload');
  const statusEl    = document.getElementById('fix-status');
  const resultEl    = document.getElementById('fix-result');

  let currentIndex = null;
  let currentSnapshotId = null;

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function openModal(index, layer, severity, description, suggestion) {
    currentIndex = index;
    currentSnapshotId = null;
    layerEl.textContent = layer;
    layerWarnEl.textContent = layer;
    sevEl.textContent = severity;
    descEl.textContent = description || '';
    suggEl.textContent = suggestion || tr('(не указана)');
    statusEl.textContent = '';
    resultEl.style.display = 'none';
    resultEl.innerHTML = '';
    applyBtn.disabled = false;
    applyBtn.style.display = 'inline-block';
    rollbackBtn.style.display = 'none';
    reloadBtn.style.display = 'none';
    modal.style.display = 'flex';
  }

  function closeModal() {
    modal.style.display = 'none';
    currentIndex = null;
  }

  async function applyFix() {
    if (currentIndex === null) return;
    applyBtn.disabled = true;
    statusEl.textContent = tr('модель правит слой…');
    statusEl.className = 'small';

    try {
      const r = await fetch(`/api/audit/fix/${currentIndex}`, { method: 'POST' });
      const data = await r.json();

      if (!r.ok) {
        statusEl.textContent = '✗ ' + (data.detail || `HTTP ${r.status}`);
        statusEl.className = 'small st-err';
        applyBtn.disabled = false;
        return;
      }

      statusEl.textContent = tr('✓ применено');
      statusEl.className = 'small st-ok';
      applyBtn.style.display = 'none';

      currentSnapshotId = data.snapshot_id;
      const reset = data.reset_stages || [];
      const lines = [];
      lines.push(`<div class="fix-result-line ok">${tr('✓ Слой «{s}» обновлён.', { s: esc(data.updated_layer) })}</div>`);

      if (reset.length) {
        lines.push(`<div class="fix-result-line warn">${tr('↺ Сброшено {n} стадий: {list}', { n: reset.length, list: reset.map(esc).join(', ') })}</div>`);
      }

      if (data.warning) {
        lines.push(`<div class="fix-result-line warn">⚠ ${esc(data.warning)}</div>`);
      } else {
        lines.push(`<div class="fix-result-line info">${tr('Аудит: было {a} проблем ({v1}) → стало {b} ({v2}).', { a: data.old_problem_count, v1: esc(data.old_verdict), b: data.new_problem_count, v2: esc(data.new_verdict) })}</div>`);
      }

      resultEl.innerHTML = lines.join('');
      resultEl.style.display = 'block';

      if (currentSnapshotId) rollbackBtn.style.display = 'inline-block';
      reloadBtn.style.display = 'inline-block';
    } catch (e) {
      statusEl.textContent = '✗ ' + e.message;
      statusEl.className = 'small st-err';
      applyBtn.disabled = false;
    }
  }

  async function rollbackFix() {
    if (!currentSnapshotId) return;
    if (!await UI.confirm({ title: tr('Откат фикса'), text: tr('Откатить фикс? Слой вернётся к состоянию до правки.'), okText: tr('Откатить') })) return;

    rollbackBtn.disabled = true;
    statusEl.textContent = tr('откат…');
    statusEl.className = 'small';

    try {
      const r = await fetch(`/api/audit/rollback/${currentSnapshotId}`, {
        method: 'POST',
      });
      const data = await r.json();
      if (!r.ok) {
        statusEl.textContent = '✗ ' + (data.detail || `HTTP ${r.status}`);
        statusEl.className = 'small st-err';
        rollbackBtn.disabled = false;
        return;
      }
      statusEl.textContent = tr('✓ откат выполнен');
      statusEl.className = 'small st-ok';
      rollbackBtn.style.display = 'none';
      reloadBtn.style.display = 'inline-block';
    } catch (e) {
      statusEl.textContent = '✗ ' + e.message;
      statusEl.className = 'small st-err';
      rollbackBtn.disabled = false;
    }
  }

  document.querySelectorAll('.fix-problem').forEach(btn => {
    btn.addEventListener('click', () => {
      const card = btn.closest('.problem');
      const desc = card.querySelector('.problem-desc')?.textContent || '';
      const sugg = (card.querySelector('.problem-suggestion')?.textContent || '')
        .replace(/^\s*→\s*/, '');
      openModal(
        parseInt(btn.dataset.index, 10),
        btn.dataset.layer,
        btn.dataset.severity || '—',
        desc,
        sugg,
      );
    });
  });

  applyBtn.addEventListener('click', applyFix);
  rollbackBtn.addEventListener('click', rollbackFix);
  reloadBtn.addEventListener('click', () => location.reload());

  document.querySelectorAll('[data-fix-close]').forEach(b => {
    b.addEventListener('click', closeModal);
  });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display === 'flex') closeModal();
  });

  // ─── Ручная правка слоя ────────────────────────────────────
  const editModal     = document.getElementById('edit-modal');
  if (!editModal) return;

  const editLayer     = document.getElementById('edit-layer');
  const editProblemTx = document.getElementById('edit-problem-text');
  const editProblemBl = document.getElementById('edit-problem-block');
  const editTextarea  = document.getElementById('edit-textarea');
  const editLoad      = document.getElementById('edit-load');
  const editLoadStat  = document.getElementById('edit-load-status');
  const editSave      = document.getElementById('edit-save');
  const editStatus    = document.getElementById('edit-status');

  let editCurrentLayer = null;

  function closeEdit() {
    editModal.style.display = 'none';
    editCurrentLayer = null;
    if (editStatus) editStatus.textContent = '';
    if (editLoadStat) editLoadStat.textContent = '';
    if (editStatus) editStatus.className = '';
  }

  function openEdit(layer, description, suggestion) {
    editCurrentLayer = layer;
    editLayer.textContent = layer;
    if (editStatus) {
      editStatus.textContent = '';
      editStatus.className = '';
    }
    if (editLoadStat) editLoadStat.textContent = '';

    if (description) {
      editProblemBl.style.display = 'block';
      editProblemTx.textContent = description +
        (suggestion ? ' → ' + suggestion : '');
    } else {
      editProblemBl.style.display = 'none';
      editProblemTx.textContent = '';
    }

    editTextarea.value = tr('загрузка...');
    editModal.style.display = 'flex';
    loadCurrentLayer();
  }

  async function loadCurrentLayer() {
    if (!editCurrentLayer) return;
    editLoadStat.textContent = tr('загрузка...');
    try {
      const r = await fetch(`/api/bible/${editCurrentLayer}`);
      const data = await r.json();
      if (!r.ok) {
        editTextarea.value = tr('// ошибка: {msg}', { msg: data.detail || r.status });
        editLoadStat.textContent = '';
        return;
      }
      editTextarea.value = JSON.stringify(data.content, null, 2);
      editLoadStat.textContent = tr('загружено');
    } catch (e) {
      editTextarea.value = tr('// ошибка: {msg}', { msg: e.message });
      editLoadStat.textContent = '';
    }
  }

  async function saveEdit() {
    if (!editCurrentLayer) return;

    let parsed;
    try {
      parsed = JSON.parse(editTextarea.value);
    } catch (e) {
      editStatus.textContent = tr('✗ невалидный JSON: {msg}', { msg: e.message });
      editStatus.className = 'st-err';
      return;
    }

    editSave.disabled = true;
    editStatus.textContent = tr('запись…');
    editStatus.className = '';

    try {
      const fd = new FormData();
      fd.append('content_json', JSON.stringify(parsed));
      fd.append('reset_downstream', '0');

      const r = await fetch(`/api/audit/manual_edit/${editCurrentLayer}`, {
        method: 'POST',
        body: fd,
      });

      const rawText = await r.text();
      let data;
      try {
        data = JSON.parse(rawText);
      } catch (parseErr) {
        editStatus.textContent = tr('✗ HTTP {code}, ответ не-JSON: {body}',
          { code: r.status, body: rawText.slice(0, 300) });
        editStatus.className = 'st-err';
        return;
      }

      if (!r.ok) {
        editStatus.textContent = '✗ ' + (data.detail || `HTTP ${r.status}`);
        editStatus.className = 'st-err';
        return;
      }

      let msg = tr('✓ записано');
      if (data.warnings && data.warnings.length) {
        msg += ' ' + tr('· предупреждений: {n}', { n: data.warnings.length });
      }
      editStatus.textContent = msg;
      editStatus.className = 'st-ok';
      setTimeout(() => location.reload(), 1200);
    } catch (e) {
      editStatus.textContent = '✗ ' + e.message;
      editStatus.className = 'st-err';
    } finally {
      editSave.disabled = false;
    }
  }

  document.querySelectorAll('.manual-edit-problem').forEach(btn => {
    btn.addEventListener('click', () => {
      openEdit(
        btn.dataset.layer,
        btn.dataset.description || '',
        btn.dataset.suggestion || '',
      );
    });
  });

  if (editLoad) editLoad.addEventListener('click', loadCurrentLayer);
  if (editSave) editSave.addEventListener('click', saveEdit);

  document.querySelectorAll('[data-edit-close]').forEach(b => {
    b.addEventListener('click', closeEdit);
  });

  editModal.addEventListener('click', (e) => {
    if (e.target === editModal) closeEdit();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && editModal.style.display === 'flex') closeEdit();
  });
})();