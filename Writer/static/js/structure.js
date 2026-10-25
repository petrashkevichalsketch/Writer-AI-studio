(function () {
  const tc = window.TENSION_CURVE || [];
  const svg = document.getElementById('tension-svg');
  if (!svg || !tc.length) return;

  // Цвета — из дизайн-токенов, чтобы график жил в одной палитре с UI
  const root = getComputedStyle(document.documentElement);
  const C = {
    accent:  root.getPropertyValue('--accent').trim()  || '#6d8dff',
    accent2: root.getPropertyValue('--accent-2').trim() || '#9d7bff',
    axis:    'rgba(255, 255, 255, 0.12)',
    dim:     root.getPropertyValue('--text-dim').trim() || '#9aa5ba',
  };

  const W = svg.clientWidth || 900;
  const H = 200;
  const pad = 30;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  const step = (W - pad * 2) / (tc.length - 1 || 1);
  const y = v => pad + (1 - v) * (H - pad * 2);

  const ns = 'http://www.w3.org/2000/svg';

  // оси
  const xAxis = document.createElementNS(ns, 'line');
  xAxis.setAttribute('x1', pad); xAxis.setAttribute('y1', H - pad);
  xAxis.setAttribute('x2', W - pad); xAxis.setAttribute('y2', H - pad);
  xAxis.setAttribute('stroke', C.axis);
  svg.appendChild(xAxis);

  const yAxis = document.createElementNS(ns, 'line');
  yAxis.setAttribute('x1', pad); yAxis.setAttribute('y1', pad);
  yAxis.setAttribute('x2', pad); yAxis.setAttribute('y2', H - pad);
  yAxis.setAttribute('stroke', C.axis);
  svg.appendChild(yAxis);

  // градиентная заливка под кривой
  const defs = document.createElementNS(ns, 'defs');
  const grad = document.createElementNS(ns, 'linearGradient');
  grad.setAttribute('id', 'tension-fill');
  grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
  grad.setAttribute('x2', '0'); grad.setAttribute('y2', '1');
  const stop1 = document.createElementNS(ns, 'stop');
  stop1.setAttribute('offset', '0%');
  stop1.setAttribute('stop-color', C.accent);
  stop1.setAttribute('stop-opacity', '0.25');
  const stop2 = document.createElementNS(ns, 'stop');
  stop2.setAttribute('offset', '100%');
  stop2.setAttribute('stop-color', C.accent);
  stop2.setAttribute('stop-opacity', '0');
  grad.append(stop1, stop2);
  defs.appendChild(grad);
  svg.appendChild(defs);

  const pts = tc.map((v, i) => `${pad + i * step},${y(v)}`).join(' ');

  const area = document.createElementNS(ns, 'polygon');
  area.setAttribute('points',
    `${pad},${y(0)} ${pts} ${pad + (tc.length - 1) * step},${y(0)}`);
  area.setAttribute('fill', 'url(#tension-fill)');
  svg.appendChild(area);

  const poly = document.createElementNS(ns, 'polyline');
  poly.setAttribute('points', pts);
  poly.setAttribute('fill', 'none');
  poly.setAttribute('stroke', C.accent);
  poly.setAttribute('stroke-width', '2.5');
  poly.setAttribute('stroke-linejoin', 'round');
  poly.setAttribute('stroke-linecap', 'round');
  svg.appendChild(poly);

  // точки
  tc.forEach((v, i) => {
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('cx', pad + i * step);
    dot.setAttribute('cy', y(v));
    dot.setAttribute('r', '3.5');
    dot.setAttribute('fill', C.accent2);
    dot.setAttribute('stroke', C.accent);
    dot.setAttribute('stroke-width', '1.5');
    svg.appendChild(dot);

    const t = document.createElementNS(ns, 'text');
    t.setAttribute('x', pad + i * step);
    t.setAttribute('y', H - pad + 14);
    t.setAttribute('fill', C.dim);
    t.setAttribute('font-size', '10');
    t.setAttribute('text-anchor', 'middle');
    t.textContent = (i + 1);
    svg.appendChild(t);
  });
})();
