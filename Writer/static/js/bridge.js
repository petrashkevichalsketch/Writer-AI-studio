(function () {
  const modalPrompt = document.getElementById('bridge-modal-prompt');
  const modalPaste  = document.getElementById('bridge-modal-paste');
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
    promptText.value = 'загрузка…';
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
    if (!text) { alert('Пусто.'); return; }

    pasteStatus.textContent = 'проверка…';
    pasteStatus.style.color = '';

    const fd = new FormData();
    fd.append('text', text);

    try {
      const r = await fetch(`/api/pipeline/${currentStage}/paste`, {
        method: 'POST', body: fd,
      });
      const data = await r.json();
      if (!r.ok) {
        pasteStatus.textContent = data.detail || `HTTP ${r.status}`;
        pasteStatus.style.color = '#ff6b6b';
        return;
      }
      if (!data.ok) {
        pasteStatus.innerHTML = '✗ ошибки валидации:<br>' +
          (data.errors || []).map(e => '· ' + esc(e)).join('<br>');
        pasteStatus.style.color = '#ff6b6b';
        return;
      }
      pasteStatus.textContent = '✓ сохранено';
      pasteStatus.style.color = '#4bde7c';
      flash('Стадия обновлена');
      setTimeout(() => location.reload(), 800);
    } catch (e) {
      pasteStatus.textContent = '✗ ' + e.message;
      pasteStatus.style.color = '#ff6b6b';
    }
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

  document.querySelectorAll('.bridge-prompt').forEach(b => {
    b.addEventListener('click', () => openPromptModal(b.dataset.stage));
  });
  document.querySelectorAll('.bridge-paste').forEach(b => {
    b.addEventListener('click', () => openPasteModal(b.dataset.stage));
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

  [modalPrompt, modalPaste].forEach(m => {
    if (!m) return;
    m.addEventListener('click', (e) => {
      if (e.target === m) m.style.display = 'none';
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal('bridge-modal-prompt');
      closeModal('bridge-modal-paste');
    }
  });
})();