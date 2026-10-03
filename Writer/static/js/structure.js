(function () {
  const tc = window.TENSION_CURVE || [];
  const svg = document.getElementById('tension-svg');
  if (!svg || !tc.length) return;

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
  xAxis.setAttribute('stroke', '#232936');
  svg.appendChild(xAxis);

  const yAxis = document.createElementNS(ns, 'line');
  yAxis.setAttribute('x1', pad); yAxis.setAttribute('y1', pad);
  yAxis.setAttribute('x2', pad); yAxis.setAttribute('y2', H - pad);
  yAxis.setAttribute('stroke', '#232936');
  svg.appendChild(yAxis);

  // polyline
  const pts = tc.map((v, i) => `${pad + i * step},${y(v)}`).join(' ');
  const poly = document.createElementNS(ns, 'polyline');
  poly.setAttribute('points', pts);
  poly.setAttribute('fill', 'none');
  poly.setAttribute('stroke', '#4b7bec');
  poly.setAttribute('stroke-width', '2');
  svg.appendChild(poly);

  // точки
  tc.forEach((v, i) => {
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('cx', pad + i * step);
    dot.setAttribute('cy', y(v));
    dot.setAttribute('r', '3');
    dot.setAttribute('fill', '#4b7bec');
    svg.appendChild(dot);

    const t = document.createElementNS(ns, 'text');
    t.setAttribute('x', pad + i * step);
    t.setAttribute('y', H - pad + 14);
    t.setAttribute('fill', '#8a93a4');
    t.setAttribute('font-size', '10');
    t.setAttribute('text-anchor', 'middle');
    t.textContent = (i + 1);
    svg.appendChild(t);
  });
})();