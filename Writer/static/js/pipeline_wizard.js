(function () {
  const modal = document.getElementById('wizard-modal');
  const body = document.getElementById('wizard-body');
  const label = document.getElementById('wizard-step-label');
  const fill = document.getElementById('wizard-progress-fill');
  const btnNext = document.getElementById('wizard-next');
  const btnBack = document.getElementById('wizard-back');
  const btnSkip = document.getElementById('wizard-skip');
  const btnSkipAll = document.getElementById('wizard-skip-all');
  const btnClose = document.getElementById('wizard-close');

  if (!modal) return;

  let stage = null;
  let mode = 'manual';
  let questions = [];
  let answers = {};
  let current = 0;
  let resolvePromise = null;

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function finish(result) {
    const r = resolvePromise;
    resolvePromise = null;
    modal.style.display = 'none';
    if (r) r(result);
  }

  function openWizardInteractive(forStage, forMode) {
    stage = forStage;
    mode = forMode || 'manual';
    modal.style.display = 'flex';
    body.innerHTML = '<p class="muted small">Модель формулирует вопросы…</p>';
    label.textContent = '—';
    fill.style.width = '0%';
    btnNext.disabled = true;
    btnBack.disabled = true;
    btnSkip.disabled = true;
    if (btnSkipAll) btnSkipAll.disabled = true;

    return new Promise((resolve) => {
      resolvePromise = resolve;

      fetch(`/api/pipeline/${stage}/questions`, { method: 'POST' })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) {
            body.innerHTML = `<p class="log-error">Ошибка: ${esc(data.detail || r.status)}</p>`;
            return;
          }
          if (!data.ok) {
            body.innerHTML = `<p class="log-error">Ошибка: ${esc(data.error || 'неизвестная')}</p>`;
            return;
          }
          questions = data.questions;
          answers = {};
          current = 0;
          btnNext.disabled = false;
          btnBack.disabled = false;
          btnSkip.disabled = false;
          if (btnSkipAll) btnSkipAll.disabled = false;
          render();
        })
        .catch((e) => {
          body.innerHTML = `<p class="log-error">Ошибка сети: ${esc(e.message)}</p>`;
        });
    });
  }

  function render() {
    const q = questions[current];
    label.textContent = `Вопрос ${current + 1} из ${questions.length}`;
    fill.style.width = `${((current + 1) / questions.length) * 100}%`;

    const saved = answers[q.id] || '';
    const isCustom = saved && !(q.options || []).includes(saved);

    let html = '';
    html += `<div class="wizard-q-text">${esc(q.text)}</div>`;
    if (q.hint) html += `<div class="wizard-q-hint">${esc(q.hint)}</div>`;

    html += '<div class="wizard-options">';
    (q.options || []).forEach(opt => {
      const checked = saved === opt ? 'checked' : '';
      html += `<label class="wizard-option">
        <input type="radio" name="wiz_q" value="${esc(opt)}" ${checked}>
        <span>${esc(opt)}</span>
      </label>`;
    });
    html += '</div>';

    html += `<label class="wizard-custom">
      <span class="muted small">Или свой вариант:</span>
      <textarea id="wizard-custom" placeholder="Свободный ответ…">${isCustom ? esc(saved) : ''}</textarea>
    </label>`;

    body.innerHTML = html;

    body.querySelectorAll('input[name="wiz_q"]').forEach(r => {
      r.addEventListener('change', () => {
        const ta = document.getElementById('wizard-custom');
        if (ta) ta.value = '';
      });
    });
    const ta = document.getElementById('wizard-custom');
    if (ta) {
      ta.addEventListener('input', () => {
        body.querySelectorAll('input[name="wiz_q"]').forEach(r => r.checked = false);
      });
    }

    btnBack.disabled = current === 0;
    const isLast = current === questions.length - 1;
    btnNext.textContent = isLast ? '▶ Сгенерировать с ответами' : 'Далее →';
  }

  function collectAnswer() {
    const q = questions[current];
    const ta = document.getElementById('wizard-custom');
    if (ta && ta.value.trim()) {
      answers[q.id] = ta.value.trim();
      return;
    }
    const checked = body.querySelector('input[name="wiz_q"]:checked');
    if (checked) {
      answers[q.id] = checked.value;
    } else {
      delete answers[q.id];
    }
  }

  function buildQA() {
    return questions.map(q => ({
      id: q.id,
      question: q.text,
      answer: answers[q.id] || ''
    }));
  }

  btnNext.addEventListener('click', () => {
    collectAnswer();
    if (current < questions.length - 1) {
      current++;
      render();
    } else {
      finish({ action: 'generate', qa: buildQA() });
    }
  });

  btnBack.addEventListener('click', () => {
    collectAnswer();
    if (current > 0) { current--; render(); }
  });

  btnSkip.addEventListener('click', () => {
    const q = questions[current];
    delete answers[q.id];
    if (current < questions.length - 1) {
      current++;
      render();
    } else {
      finish({ action: 'generate', qa: buildQA() });
    }
  });

  if (btnSkipAll) {
    btnSkipAll.addEventListener('click', () => {
      finish({ action: 'skip' });
    });
  }

  btnClose.addEventListener('click', () => {
    if (mode === 'auto') {
      if (confirm('Прервать автосбор?')) {
        finish({ action: 'cancel' });
      }
      return;
    }
    finish({ action: 'cancel' });
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      if (mode === 'auto') {
        if (confirm('Прервать автосбор?')) {
          finish({ action: 'cancel' });
        }
        return;
      }
      finish({ action: 'cancel' });
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display === 'flex') {
      if (mode === 'auto') {
        if (confirm('Прервать автосбор?')) {
          finish({ action: 'cancel' });
        }
        return;
      }
      finish({ action: 'cancel' });
    }
  });

  // Manual-режим: клик на ❓ → открыть wizard → по завершении запустить стадию
  document.querySelectorAll('.run-quiz').forEach(btn => {
    btn.addEventListener('click', async () => {
      const result = await openWizardInteractive(btn.dataset.stage, 'manual');
      if (result.action === 'generate') {
        if (typeof window.runStageWithQA === 'function') {
          window.runStageWithQA(btn.dataset.stage, result.qa);
        } else {
          alert('pipeline.js не загрузился — генерация недоступна.');
        }
      }
      // 'cancel' — просто закрыли, ничего не делаем
      // 'skip' в manual-режиме недостижим (кнопки "Пропустить всё" нет на модалке — есть, но она просто закроет без запуска)
    });
  });

  window.openWizardInteractive = openWizardInteractive;
})();