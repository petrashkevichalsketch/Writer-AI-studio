(function () {
  const num = window.CHAPTER_NUM;
  const modal = document.getElementById('wizard-modal');
  const body = document.getElementById('wizard-body');
  const label = document.getElementById('wizard-step-label');
  const fill = document.getElementById('wizard-progress-fill');
  const btnNext = document.getElementById('wizard-next');
  const btnBack = document.getElementById('wizard-back');
  const btnSkip = document.getElementById('wizard-skip');
  const btnClose = document.getElementById('wizard-close');
  const btnOpen = document.getElementById('btn-questions');

  // Ссылки на элементы страницы главы
  const textEl = document.getElementById('chapter-text');
  const wcEl = document.getElementById('wc');
  const statusEl = document.getElementById('status-info');
  const tail = document.getElementById('stream-tail');
  const btnGen = document.getElementById('btn-generate');

  if (!modal || !btnOpen) return;

  let questions = [];
  let answers = {};
  let current = 0;

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  async function openWizard() {
    modal.style.display = 'flex';
    body.innerHTML =
      '<div class="llm-head" style="margin-bottom:6px">' +
      '<span class="spinner"></span>' +
      '<span class="llm-stage">Модель формулирует вопросы…</span></div>' +
      '<div class="skeleton w-80"></div>' +
      '<div class="skeleton"></div>' +
      '<div class="skeleton w-60"></div>' +
      '<div class="skeleton w-80"></div>' +
      '<div class="skeleton w-40"></div>';
    label.textContent = '—';
    fill.style.width = '0%';
    btnNext.disabled = true;
    btnBack.disabled = true;
    btnSkip.disabled = true;

    try {
      const r = await fetch(`/api/chapter/${num}/questions`, { method: 'POST' });
      const data = await r.json();
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
      render();
    } catch (e) {
      body.innerHTML = `<p class="log-error">Ошибка сети: ${esc(e.message)}</p>`;
    }
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

  async function finish() {
    modal.style.display = 'none';

    // Формируем qa — плоский список
    const qa = questions.map(q => ({
      id: q.id,
      question: q.text,
      answer: answers[q.id] || ''
    }));

    // Прямая генерация с ответами — не зависим от chapter.js
    const ok = await UI.confirm({
      title: 'Генерация главы',
      text: 'Сгенерировать главу заново? Текущий текст будет перезаписан.',
      okText: 'Сгенерировать',
    });
    if (!ok) return;

    const st = UI.stream();
    st.reset();
    st.work(`соединение (с ответами на ${qa.length} вопросов)…`);
    if (textEl) textEl.textContent = '';
    textEl && textEl.classList.add('is-streaming');
    if (btnGen) { btnGen.disabled = true; btnGen.textContent = '⏳ Генерация…'; }

    const t0 = Date.now();
    let target = 0;

    const fd = new FormData();
    fd.append('qa_json', JSON.stringify(qa));

    let buffer = '';
    try {
      const resp = await fetch(`/api/chapter/${num}/generate`, {
        method: 'POST', body: fd,
      });
      if (!resp.ok || !resp.body) {
        st.error(`HTTP ${resp.status}`);
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
          handleEvent(ev, {
            getBuf: () => buffer,
            setBuf: t => { buffer = t; },
            target: () => target,
            setTarget: v => { target = v; },
            t0,
            st,
          });
        }
      }
    } catch (e) {
      st.error(`Ошибка: ${e.message}`);
    } finally {
      if (btnGen) { btnGen.disabled = false; btnGen.textContent = '▶ Generate'; }
      textEl && textEl.classList.remove('is-streaming');
    }
  }

  function handleEvent(ev, ctx) {
    const { getBuf, setBuf, st } = ctx;
    switch (ev.type) {
      case 'chunk':
        setBuf(getBuf() + ev.text);
        if (textEl) textEl.textContent = getBuf();
        {
          const words = getBuf().trim().split(/\s+/).filter(Boolean).length;
          if (wcEl) wcEl.textContent = words;
          const mins = (Date.now() - ctx.t0) / 60000;
          st.progress(words, ctx.target(), mins > 0.05 ? words / mins : 0);
        }
        window.scrollTo(0, document.body.scrollHeight);
        break;
      case 'meta':
        ctx.setTarget((ev.plan && ev.plan.word_target) || 0);
        st.note(`глава «${ev.title}» · POV: ${ev.plan.pov} · модель пишет…`);
        break;
      case 'continuing':
        st.warn(`глава короткая (${ev.have}/${ev.target} слов) — запрашиваю продолжение…`);
        break;
      case 'warning':
        st.warn(ev.message);
        break;
      case 'done':
        if (wcEl) wcEl.textContent = ev.word_count;
        if (statusEl) statusEl.innerHTML = `статус: draft · слов: <span id="wc">${ev.word_count}</span>`;
        st.done(`✓ готово · ${ev.word_count} слов · ${ev.chars} знаков`);
        UI.toast('Глава сгенерирована', 'ok');
        break;
      case 'error':
        st.error(`✗ ${ev.message}`);
        break;
    }
  }

  btnNext.addEventListener('click', () => {
    collectAnswer();
    if (current < questions.length - 1) {
      current++;
      render();
    } else {
      finish();
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
      finish();
    }
  });

  btnClose.addEventListener('click', () => modal.style.display = 'none');
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display === 'flex') {
      modal.style.display = 'none';
    }
  });

  btnOpen.addEventListener('click', openWizard);
})();