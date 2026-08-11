(function () {
  const tiles = document.querySelectorAll('.tile[data-tile]');
  const tabs = document.querySelectorAll('.portfolio-tabs .tab');
  const items = document.querySelectorAll('.portfolio-item');

  function closeAllTiles(except) {
    tiles.forEach((tile) => {
      if (tile !== except) tile.classList.remove('is-open');
    });
  }

  tiles.forEach((tile) => {
    const closeBtn = tile.querySelector('.tile-close');
    tile.addEventListener('click', (e) => {
      if (e.target.closest('.tile-close')) {
        tile.classList.remove('is-open');
        return;
      }
      if (tile.classList.contains('is-open')) return;
      closeAllTiles(tile);
      tile.classList.add('is-open');
      tile.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    closeBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      tile.classList.remove('is-open');
    });
  });

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const cat = tab.dataset.category || 'all';
      tabs.forEach((t) => t.classList.toggle('is-active', t === tab));
      items.forEach((item) => {
        const match = cat === 'all' || item.dataset.category === cat;
        item.hidden = !match;
      });
    });
  });

  const form = document.querySelector('.contact-form');
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    if (btn) {
      btn.textContent = 'Děkujeme — brzy se ozveme';
      btn.disabled = true;
    }
  });
})();
