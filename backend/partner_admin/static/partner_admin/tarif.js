(function () {
  function normalizuj(nazev) {
    return String(nazev || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .replace('materialník', 'materiálník');
  }

  function logoUrl(nazev, mapa) {
    var key = normalizuj(nazev);
    var mo = key.indexOf('moderník') !== -1;
    var ma = key.indexOf('materiálník') !== -1;
    var ar = key.indexOf('archivník') !== -1;
    if (mapa[key]) return mapa[key];
    if (mo && ma && ar) return mapa.trojice;
    if (mo && ar && !ma) return mapa['moderník + archivník'];
    if (ma && ar && !mo) return mapa['materiálník + archivník'];
    if (mo && ma) return mapa.combo;
    if (key === 'web') return mapa.web;
    return mapa.fallback;
  }

  var mapaEl = document.getElementById('tarif-loga');
  var logoEl = document.getElementById('tarif-logo');
  var captionEl = document.getElementById('tarif-logo-caption');
  var mapa = null;
  if (mapaEl) {
    try { mapa = JSON.parse(mapaEl.textContent); } catch (err) { mapa = null; }
  }

  document.querySelectorAll('select.tarif-select, select[name="tarif"]').forEach(function (sel) {
    function syncLogo() {
      if (!mapa || !logoEl) return;
      var nazev = sel.value || '';
      logoEl.src = logoUrl(nazev, mapa);
      logoEl.alt = nazev || '—';
      if (captionEl) captionEl.textContent = nazev || '—';
    }
    sel.addEventListener('change', function () {
      var opt = sel.selectedOptions && sel.selectedOptions[0];
      var cena = opt && opt.getAttribute('data-cena');
      if (cena && sel.form) {
        var castka = sel.form.querySelector('[name="castka"]');
        if (castka) castka.value = cena;
      }
      syncLogo();
    });
  });
})();
