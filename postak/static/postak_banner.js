(function () {
  'use strict';
  var clockEl = document.getElementById('dash-clock');
  var namesEl = document.getElementById('dash-jmeniny');
  var dataEl = document.getElementById('jmeniny-data');
  if (!clockEl && !namesEl) return;

  var calendar = {};
  if (dataEl && dataEl.textContent) {
    try {
      calendar = JSON.parse(dataEl.textContent);
    } catch (e) {
      calendar = {};
    }
  }

  function pragueNow() {
    var fmt = new Intl.DateTimeFormat('cs-CZ', {
      timeZone: 'Europe/Prague',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
    var parts = {};
    fmt.formatToParts(new Date()).forEach(function (p) {
      parts[p.type] = p.value;
    });
    return parts;
  }

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function updateJmeniny(parts) {
    if (!namesEl) return;
    var key = parts.month + '-' + parts.day;
    var list = calendar[key];
    if (!list || !list.length) {
      namesEl.textContent = 'Dnes v kalendáři jmenin nejsou uvedena jména.';
      return;
    }
    namesEl.textContent = list.join(', ');
  }

  function tick() {
    var p = pragueNow();
    if (clockEl) {
      clockEl.textContent = p.hour + ':' + p.minute + ':' + p.second;
    }
    var dayKey = p.year + '-' + p.month + '-' + p.day;
    if (tick._lastDay !== dayKey) {
      tick._lastDay = dayKey;
      updateJmeniny(p);
    }
  }

  tick._lastDay = '';
  tick();
  setInterval(tick, 1000);
})();
