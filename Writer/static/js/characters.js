(function () {
  // Цвета берём из дизайн-токенов — графики живут в одной палитре с UI
  const root = getComputedStyle(document.documentElement);
  const C = {
    accent:  root.getPropertyValue('--accent').trim()  || '#6d8dff',
    textHi:  root.getPropertyValue('--text-hi').trim() || '#eef2fa',
    textDim: root.getPropertyValue('--text-dim').trim() || '#9aa5ba',
    nodeBg:  'rgba(255, 255, 255, 0.06)',
  };

  function init() {
    const chars = window.CHARACTERS_DATA || [];
    const rels  = window.RELATIONS_DATA || [];
    const svg = document.getElementById('rel-svg');

    console.log('[characters.js] chars=', chars.length, 'rels=', rels.length);

    if (!svg) {
      console.warn('[characters.js] #rel-svg не найден');
      return;
    }
    if (!chars.length) {
      svg.outerHTML = '<p class="muted">' + tr('Нет данных о персонажах.') + '</p>';
      return;
    }

    const rect = svg.getBoundingClientRect();
    const W = rect.width || (svg.parentElement && svg.parentElement.clientWidth) || 900;
    const H = 520;
    const cx = W / 2, cy = H / 2;
    const r = Math.max(40, Math.min(W, H) / 2 - 80);

    const positions = {};
    chars.forEach((c, i) => {
      const a = (2 * Math.PI * i) / chars.length - Math.PI / 2;
      positions[c.id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });

    const ns = 'http://www.w3.org/2000/svg';
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

    rels.forEach(rel => {
      const a = positions[rel.from], b = positions[rel.to];
      if (!a || !b) return;
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('x1', a.x); line.setAttribute('y1', a.y);
      line.setAttribute('x2', b.x); line.setAttribute('y2', b.y);
      line.setAttribute('stroke', relColor(rel.type));
      line.setAttribute('stroke-width', '1.5');
      line.setAttribute('opacity', '0.75');
      svg.appendChild(line);

      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const t = document.createElementNS(ns, 'text');
      t.setAttribute('x', mx); t.setAttribute('y', my - 3);
      t.setAttribute('fill', relColor(rel.type));
      t.setAttribute('font-size', '10');
      t.setAttribute('text-anchor', 'middle');
      t.textContent = rel.type;
      svg.appendChild(t);
    });

    chars.forEach(c => {
      const p = positions[c.id];
      const g = document.createElementNS(ns, 'g');
      g.setAttribute('transform', `translate(${p.x},${p.y})`);

      const circle = document.createElementNS(ns, 'circle');
      circle.setAttribute('r', '26');
      circle.setAttribute('fill', C.nodeBg);
      circle.setAttribute('stroke', C.accent);
      circle.setAttribute('stroke-width', '2');
      g.appendChild(circle);

      const label = document.createElementNS(ns, 'text');
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('dominant-baseline', 'middle');
      label.setAttribute('fill', C.textHi);
      label.setAttribute('font-size', '11');
      label.textContent = c.id;
      g.appendChild(label);

      const name = document.createElementNS(ns, 'text');
      name.setAttribute('text-anchor', 'middle');
      name.setAttribute('y', '42');
      name.setAttribute('fill', C.textDim);
      name.setAttribute('font-size', '11');
      name.textContent = c.name;
      g.appendChild(name);

      svg.appendChild(g);
    });
  }

  function relColor(type) {
    switch (type) {
      case 'ally':    return '#4bde7c';
      case 'enemy':   return '#ff6b6b';
      case 'lover':   return '#ff7db1';
      case 'family':  return '#f5c542';
      case 'rival':   return '#f59b42';
      case 'mentor':  return '#8ab4f8';
      default:        return '#5b6473';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      requestAnimationFrame(init);
    });
  } else {
    requestAnimationFrame(init);
  }
})();

/* ── Редактирование карточки персонажа ──────────────────────────
   Кнопка ✏ на карточке открывает модалку; сохранение уходит в
   /api/characters/{id}/edit — сервер атомарно правит сырой слой
   world_bible['characters'] и таблицу characters, не трогая id,
   отношения, секреты и живое состояние из патчей канона. ─────── */
(function () {
  const modal = document.getElementById('char-modal');
  const form = document.getElementById('char-form');
  if (!modal || !form) return;

  const chars = window.CHARACTERS_DATA || [];
  const TEXT_FIELDS = ['name', 'role_in_conflict', 'personal_stake',
                       'contradiction', 'arc_potential',
                       'backstory_wound', 'defense_mechanism'];
  const LIST_FIELDS = ['goals', 'flaws'];
  let currentId = null;

  document.querySelectorAll('.char-edit').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = chars.find(x => x.id === btn.dataset.cid);
      if (!c) return;
      currentId = c.id;
      TEXT_FIELDS.forEach(f => { form.elements[f].value = c[f] || ''; });
      LIST_FIELDS.forEach(f => {
        form.elements[f].value = (c[f] || []).join('\n');
      });
      modal.style.display = '';
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentId) return;
    const payload = {};
    TEXT_FIELDS.forEach(f => { payload[f] = form.elements[f].value.trim(); });
    if (!payload.name) {
      UI.toast(tr('Имя не может быть пустым'), 'error');
      return;
    }
    LIST_FIELDS.forEach(f => {
      payload[f] = form.elements[f].value.split('\n')
        .map(s => s.trim()).filter(Boolean);
    });

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;
    try {
      const r = await fetch(
        `/api/characters/${encodeURIComponent(currentId)}/edit`,
        { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        UI.toast(d.detail || `HTTP ${r.status}`, 'error');
        return;
      }
      UI.toast(tr('Персонаж обновлён'), 'ok');
      modal.style.display = 'none';
      setTimeout(() => location.reload(), 350);
    } catch (err) {
      UI.toast(tr('Ошибка сети: {msg}', { msg: err.message }), 'error');
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
})();
