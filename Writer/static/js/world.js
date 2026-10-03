(function () {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.tab-panel');

  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const key = btn.dataset.tab;
      const p = document.querySelector(`.tab-panel[data-panel="${key}"]`);
      if (p) p.classList.add('active');
    });
  });
})();