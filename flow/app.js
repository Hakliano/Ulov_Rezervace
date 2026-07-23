const API_BASE = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
  ? 'http://localhost:8000/api'
  : 'https://api.ulovklienty.cz/api';
const TOKEN_KEY = 'flow_token';

const STAV_LABEL = {
  ceka: 'Čeká',
  potvrzeno: 'Potvrzeno',
  zakaznik_storno: 'Zrušeno zákazníkem',
  salon_storno: 'Zrušeno salonem',
  dokonceno: 'Dokončeno',
  no_show: 'NO-show',
};

const DEN_SHORT = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let currentUser = null;
let weekOffset = 0;
let ovWeekOffset = 0;
let monthOffset = 0;
let monthCache = { rezervace: [], absence: [], rozvrh: [] };
let selectedDayYmd = null;
let rezById = new Map();
let noshowTargetId = null;
let platbaTarget = null;
let sluzbyCache = null;
let selectedCas = null;

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getToken();
  if (token) headers['X-Flow-Token'] = token;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail || data?.non_field_errors?.[0] || res.statusText || 'Chyba';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

function showMsg(el, text, ok) {
  if (!el) return;
  el.hidden = false;
  el.textContent = text;
  el.className = ok ? 'msg ok' : 'msg error';
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function toYmd(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseYmd(ymd) {
  const [y, m, d] = ymd.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function startOfWeek(base = new Date()) {
  const d = new Date(base);
  d.setHours(0, 0, 0, 0);
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  return d;
}

function weekRange(offset) {
  const start = startOfWeek();
  start.setDate(start.getDate() + offset * 7);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return { od: toYmd(start), do: toYmd(end), start, end };
}

function monthRange(offset) {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
  return {
    od: toYmd(first),
    do: toYmd(last),
    first,
    last,
    label: first.toLocaleDateString('cs-CZ', { month: 'long', year: 'numeric' }),
  };
}

function formatWeekLabel(range) {
  const opts = { day: 'numeric', month: 'numeric' };
  return `${range.start.toLocaleDateString('cs-CZ', opts)} – ${range.end.toLocaleDateString('cs-CZ', opts)} ${range.end.getFullYear()}`;
}

function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('cs-CZ', {
    weekday: 'short',
    day: 'numeric',
    month: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso + 'T12:00:00').toLocaleDateString('cs-CZ');
}

function formatTime(t) {
  if (!t) return '';
  return String(t).slice(0, 5);
}

function sluzbyText(r) {
  return (r.polozky || []).map((p) => p.nazev || p.sluzba?.nazev || 'služba').join(', ') || '—';
}

function canAct(r) {
  return !['zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'].includes(r.stav);
}

function rememberRez(items) {
  (items || []).forEach((r) => rezById.set(r.id, r));
}

function setTab(name) {
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.pane').forEach((p) => p.classList.add('hidden'));
  const pane = $(`#pane-${name}`);
  if (pane) pane.classList.remove('hidden');
  if (name === 'mujden') loadWeekList(false);
  if (name === 'mesic') loadMonth();
  if (name === 'rozvrh') loadRozvrh();
  if (name === 'overview') loadWeekList(true);
  if (name === 'absence') loadAbsence();
}

function showLoggedIn(user) {
  currentUser = user;
  $('#view-login').classList.add('hidden');
  $('#view-home').classList.remove('hidden');
  $('#btn-logout').classList.remove('hidden');
  $('#shell').classList.add('app-mode');
  $('#hero-brand').classList.add('compact');
  $('#home-name').textContent = user.zamestnanec?.jmeno || '—';
  $('#home-salon').textContent = user.salon?.name || '—';
  $('#home-email').textContent = user.email || '—';
  $('#home-overview').textContent = user.visible_overview ? 'zapnuto' : 'vypnuto';
  const ovTab = $('#tab-overview');
  if (user.visible_overview) ovTab.classList.remove('hidden');
  else ovTab.classList.add('hidden');
  setTab('mujden');
}

function showLogin() {
  currentUser = null;
  $('#view-login').classList.remove('hidden');
  $('#view-home').classList.add('hidden');
  $('#btn-logout').classList.add('hidden');
  $('#shell').classList.remove('app-mode');
  $('#hero-brand').classList.remove('compact');
}

function renderRezervaceList(container, items, { readonly = false, emptyText = 'Žádné rezervace.' } = {}) {
  if (!items.length) {
    container.innerHTML = `<p class="empty">${esc(emptyText)}</p>`;
    return;
  }
  container.innerHTML = items.map((r) => {
    const actions = (!readonly && canAct(r))
      ? `<div class="actions">
          <button type="button" class="btn tiny primary" data-act="done" data-id="${r.id}">Proběhla</button>
          <button type="button" class="btn tiny danger" data-act="noshow" data-id="${r.id}">NO-show</button>
          <button type="button" class="btn tiny ghost" data-act="platba" data-id="${r.id}">Platba QR</button>
          <button type="button" class="btn tiny ghost" data-act="storno" data-id="${r.id}">Storno</button>
        </div>`
      : (readonly
        ? `<p class="meta">u ${esc(r.zamestnanec_jmeno || '—')}</p>`
        : '');
    return `<article class="item stav-${esc(r.stav)}" data-id="${r.id}">
      <div class="item-top">
        <time>${esc(formatDateTime(r.zacatek))}</time>
        <span class="badge">${esc(STAV_LABEL[r.stav] || r.stav)}</span>
      </div>
      <p class="item-title">${esc(r.kontaktni_jmeno || r.jmeno_host || 'Zákazník')}</p>
      <p class="meta">${esc(sluzbyText(r))}</p>
      ${r.kontaktni_email ? `<p class="meta">${esc(r.kontaktni_email)}</p>` : ''}
      ${actions}
    </article>`;
  }).join('');
}

function renderAbsenceBlocks(absences, { withName = false, canDelete = false } = {}) {
  if (!absences.length) return '';
  return absences.map((a) => {
    const who = withName ? `<span class="meta"> — ${esc(a.zamestnanec_jmeno || '')}</span>` : '';
    const del = canDelete
      ? `<button type="button" class="btn tiny ghost" data-abs-del="${a.id}">Smazat</button>`
      : '';
    return `<article class="item absence">
      <div class="item-top">
        <time>${esc(formatDate(a.datum_od))} – ${esc(formatDate(a.datum_do))}</time>
        <span class="badge">${esc(a.typ_label || a.typ)}</span>
      </div>
      <p class="meta">${esc(a.poznamka || 'Absence')}${who}</p>
      ${del}
    </article>`;
  }).join('');
}

async function loadWeekList(overview) {
  const offset = overview ? ovWeekOffset : weekOffset;
  const range = weekRange(offset);
  const labelEl = overview ? $('#ov-week-label') : $('#week-label');
  const listEl = overview ? $('#ov-list') : $('#cal-list');
  const msgEl = overview ? $('#ov-msg') : $('#cal-msg');
  labelEl.textContent = formatWeekLabel(range);
  msgEl.hidden = true;
  listEl.innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const q = new URLSearchParams({ od: range.od, do: range.do });
    if (overview) q.set('overview', '1');
    const data = await api(`/flow/kalendar/?${q}`);
    rememberRez(data.rezervace);
    const absHtml = renderAbsenceBlocks(data.absence || [], {
      withName: overview,
      canDelete: false,
    });
    listEl.innerHTML = '';
    if (absHtml) {
      listEl.innerHTML += `<h3 class="list-h">Absence</h3>${absHtml}`;
    }
    listEl.innerHTML += `<h3 class="list-h">Rezervace</h3>`;
    const holder = document.createElement('div');
    renderRezervaceList(holder, data.rezervace || [], {
      readonly: overview,
      emptyText: 'Žádné rezervace v tomto týdnu.',
    });
    listEl.appendChild(holder);
    if (!overview) bindCalActions(holder, () => loadWeekList(false));
  } catch (err) {
    listEl.innerHTML = '';
    showMsg(msgEl, err.message, false);
  }
}

function bindCalActions(root, onDone) {
  root.querySelectorAll('[data-act]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.id);
      const act = btn.dataset.act;
      if (act === 'done') {
        if (!confirm('Označit rezervaci jako proběhlou?')) return;
        try {
          await api(`/flow/rezervace/${id}/dokonceno/`, { method: 'POST', body: '{}' });
          onDone?.();
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'storno') {
        if (!confirm('Stornovat rezervaci? Zákazník dostane e-mail.')) return;
        try {
          await api(`/flow/rezervace/${id}/storno/`, { method: 'DELETE' });
          onDone?.();
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'noshow') {
        openNoshow(id);
      } else if (act === 'platba') {
        openPlatba(id);
      }
    });
  });
}

function findRezervace(id) {
  return rezById.get(id) || null;
}

function isAbsenceDay(ymd, absences) {
  return (absences || []).some((a) => a.datum_od <= ymd && a.datum_do >= ymd);
}

function daySchedule(ymd, rozvrh) {
  const d = parseYmd(ymd);
  const den = (d.getDay() + 6) % 7;
  return (rozvrh || []).find((r) => Number(r.den) === den) || { volno: true };
}

async function loadMonth() {
  const range = monthRange(monthOffset);
  $('#month-label').textContent = range.label;
  $('#month-msg').hidden = true;
  $('#month-grid').innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const q = new URLSearchParams({ od: range.od, do: range.do });
    const [cal, roz] = await Promise.all([
      api(`/flow/kalendar/?${q}`),
      api('/flow/rozvrh/'),
    ]);
    monthCache = {
      rezervace: cal.rezervace || [],
      absence: cal.absence || [],
      rozvrh: roz.rozvrh || [],
    };
    rememberRez(monthCache.rezervace);
    renderMonthGrid(range);
    if (selectedDayYmd && selectedDayYmd >= range.od && selectedDayYmd <= range.do) {
      showMonthDay(selectedDayYmd);
    } else {
      $('#month-day-detail').classList.add('hidden');
    }
  } catch (err) {
    $('#month-grid').innerHTML = '';
    showMsg($('#month-msg'), err.message, false);
  }
}

function renderMonthGrid(range) {
  const grid = $('#month-grid');
  const firstWeekday = (range.first.getDay() + 6) % 7;
  const daysInMonth = range.last.getDate();
  const today = toYmd(new Date());
  const byDay = {};
  monthCache.rezervace.forEach((r) => {
    const ymd = toYmd(new Date(r.zacatek));
    (byDay[ymd] ||= []).push(r);
  });

  let html = DEN_SHORT.map((d) => `<div class="m-head">${d}</div>`).join('');
  for (let i = 0; i < firstWeekday; i += 1) {
    html += '<div class="m-cell empty-cell"></div>';
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const ymd = `${range.first.getFullYear()}-${pad(range.first.getMonth() + 1)}-${pad(day)}`;
    const sch = daySchedule(ymd, monthCache.rozvrh);
    const abs = isAbsenceDay(ymd, monthCache.absence);
    const count = (byDay[ymd] || []).length;
    const classes = ['m-cell'];
    if (ymd === today) classes.push('today');
    if (ymd === selectedDayYmd) classes.push('selected');
    if (abs) classes.push('abs');
    else if (sch.volno) classes.push('off');
    else classes.push('work');
    const hours = (!abs && !sch.volno && sch.od)
      ? `<span class="m-hours">${esc(formatTime(sch.od))}–${esc(formatTime(sch.do))}</span>`
      : (abs ? '<span class="m-hours">absence</span>' : '<span class="m-hours">volno</span>');
    html += `<button type="button" class="${classes.join(' ')}" data-day="${ymd}">
      <span class="m-num">${day}</span>
      ${hours}
      ${count ? `<span class="m-count">${count}</span>` : ''}
    </button>`;
  }
  grid.innerHTML = html;
  grid.querySelectorAll('[data-day]').forEach((btn) => {
    btn.addEventListener('click', () => {
      selectedDayYmd = btn.dataset.day;
      renderMonthGrid(range);
      showMonthDay(selectedDayYmd);
    });
  });
}

function showMonthDay(ymd) {
  const detail = $('#month-day-detail');
  const list = $('#month-day-list');
  detail.classList.remove('hidden');
  const d = parseYmd(ymd);
  const sch = daySchedule(ymd, monthCache.rozvrh);
  const abs = isAbsenceDay(ymd, monthCache.absence);
  let status = 'volno';
  if (abs) status = 'absence';
  else if (!sch.volno && sch.od) status = `${formatTime(sch.od)}–${formatTime(sch.do)}`;
  $('#month-day-title').textContent =
    `${d.toLocaleDateString('cs-CZ', { weekday: 'long', day: 'numeric', month: 'long' })} · ${status}`;
  const items = monthCache.rezervace.filter((r) => toYmd(new Date(r.zacatek)) === ymd);
  list.innerHTML = `<button type="button" class="btn tiny primary" id="btn-nova-day">＋ Zadat na tento den</button>`;
  const holder = document.createElement('div');
  renderRezervaceList(holder, items, { emptyText: 'Žádné rezervace tento den.' });
  list.appendChild(holder);
  $('#btn-nova-day')?.addEventListener('click', () => openNova(ymd));
  bindCalActions(holder, () => loadMonth());
}

async function loadRozvrh() {
  const box = $('#rozvrh-editor');
  const msg = $('#rozvrh-msg');
  msg.hidden = true;
  box.innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const data = await api('/flow/rozvrh/');
    renderRozvrhEditor(data.rozvrh || []);
  } catch (err) {
    box.innerHTML = '';
    showMsg(msg, err.message, false);
  }
}

function renderRozvrhEditor(rozvrh) {
  const box = $('#rozvrh-editor');
  const byDen = {};
  (rozvrh || []).forEach((r) => { byDen[r.den] = r; });
  box.innerHTML = `<table class="rozvrh-table">
    <thead><tr><th>Den</th><th>Volno</th><th>Od</th><th>Do</th></tr></thead>
    <tbody>
      ${[0, 1, 2, 3, 4, 5, 6].map((den) => {
        const r = byDen[den] || { den, volno: true, od: null, do: null };
        const volno = !!r.volno;
        return `<tr data-den="${den}">
          <td>${DEN_SHORT[den]}</td>
          <td><input type="checkbox" class="roz-volno" ${volno ? 'checked' : ''}></td>
          <td><input type="time" class="roz-od" value="${esc(formatTime(r.od))}" ${volno ? 'disabled' : ''}></td>
          <td><input type="time" class="roz-do" value="${esc(formatTime(r.do))}" ${volno ? 'disabled' : ''}></td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
  box.querySelectorAll('.roz-volno').forEach((cb) => {
    cb.addEventListener('change', () => {
      const row = cb.closest('tr');
      row.querySelector('.roz-od').disabled = cb.checked;
      row.querySelector('.roz-do').disabled = cb.checked;
    });
  });
}

function collectRozvrh() {
  return [...$$('#rozvrh-editor tr[data-den]')].map((row) => {
    const volno = row.querySelector('.roz-volno').checked;
    return {
      den: Number(row.dataset.den),
      volno,
      od: volno ? null : (row.querySelector('.roz-od').value || null),
      do: volno ? null : (row.querySelector('.roz-do').value || null),
    };
  });
}

async function openNoshow(id) {
  noshowTargetId = id;
  const r = findRezervace(id);
  $('#noshow-info').textContent = r
    ? `${r.kontaktni_jmeno || 'Zákazník'} — ${formatDateTime(r.zacatek)}`
    : `Rezervace #${id}`;
  const hasEmail = !!(r && r.kontaktni_email);
  $('#noshow-send-email').checked = hasEmail;
  $('#noshow-send-email').disabled = !hasEmail;
  $('#noshow-msg').hidden = true;
  $('#noshow-modal').classList.remove('hidden');
}

function closeNoshow() {
  noshowTargetId = null;
  $('#noshow-modal').classList.add('hidden');
}

async function openPlatba(id) {
  const r = findRezervace(id);
  platbaTarget = r || { id };
  $('#platba-info').textContent = r
    ? `${r.kontaktni_jmeno || 'Zákazník'} — ${formatDateTime(r.zacatek)}`
    : `Rezervace #${id}`;
  $('#platba-castka').value = '';
  $('#platba-ucet').value = r?.zamestnanec_cislo_uctu || '';
  $('#platba-vs').value = String(id);
  $('#platba-msg').hidden = true;
  $('#platba-modal').classList.remove('hidden');
}

function closePlatba() {
  platbaTarget = null;
  $('#platba-modal').classList.add('hidden');
}

async function loadAbsence() {
  const list = $('#abs-list');
  list.innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const items = await api('/flow/absence/');
    if (!items.length) {
      list.innerHTML = '<p class="empty">Zatím žádná absence.</p>';
      return;
    }
    list.innerHTML = renderAbsenceBlocks(items, { canDelete: true });
    list.querySelectorAll('[data-abs-del]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('Smazat tuto absenci?')) return;
        try {
          await api(`/flow/absence/${btn.dataset.absDel}/`, { method: 'DELETE' });
          $('#abs-konflikt')?.classList.add('hidden');
          loadAbsence();
        } catch (err) {
          showMsg($('#abs-msg'), err.message, false);
        }
      });
    });
  } catch (err) {
    list.innerHTML = '';
    showMsg($('#abs-msg'), err.message, false);
  }
}

async function ensureSluzby() {
  if (sluzbyCache) return sluzbyCache;
  sluzbyCache = await api('/flow/sluzby/');
  return sluzbyCache;
}

function selectedSluzbyIds() {
  return [...$$('#nova-sluzby input:checked')].map((i) => Number(i.value));
}

async function openNova(prefillDate = '') {
  const msg = $('#nova-msg');
  msg.hidden = true;
  selectedCas = null;
  $('#nova-cas').value = '';
  $('#nova-terminy').innerHTML = '';
  $('#nova-terminy-msg').textContent = 'Načítám služby…';
  $('#form-nova').reset();
  $('#nova-no-email').checked = false;
  $('#nova-email').disabled = false;
  const today = toYmd(new Date());
  $('#nova-datum').value = prefillDate || selectedDayYmd || today;
  $('#nova-datum').min = today;
  $('#nova-modal').classList.remove('hidden');
  try {
    const sluzby = await ensureSluzby();
    if (!sluzby.length) {
      $('#nova-sluzby').innerHTML = '<p class="empty">Žádné aktivní služby v salonu.</p>';
      $('#nova-terminy-msg').textContent = '';
      return;
    }
    $('#nova-sluzby').innerHTML = sluzby.map((s) => `
      <label class="sluzba-row">
        <input type="checkbox" value="${s.id}">
        <span>
          ${esc(s.nazev)}
          <span class="sluzba-meta">${esc(s.delka_minut)} min · ${esc(s.cena)} Kč</span>
        </span>
      </label>
    `).join('');
    $('#nova-terminy-msg').textContent = 'Vyberte služby a datum — pak se načtou volné časy.';
    $$('#nova-sluzby input').forEach((cb) => cb.addEventListener('change', loadNovaTerminy));
    loadNovaTerminy();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function closeNova() {
  $('#nova-modal').classList.add('hidden');
  selectedCas = null;
}

async function loadNovaTerminy() {
  const msg = $('#nova-terminy-msg');
  const box = $('#nova-terminy');
  selectedCas = null;
  $('#nova-cas').value = '';
  box.innerHTML = '';
  const sluzby = selectedSluzbyIds();
  const datum = $('#nova-datum').value;
  if (!sluzby.length || !datum) {
    msg.textContent = 'Vyberte služby a datum.';
    return;
  }
  msg.textContent = 'Načítám volné termíny…';
  try {
    const q = new URLSearchParams({
      datum,
      sluzby: sluzby.join(','),
    });
    const data = await api(`/flow/volne-terminy/?${q}`);
    if (data.zavreno || !data.terminy?.length) {
      msg.textContent = data.duvod || 'Žádný volný termín.';
      return;
    }
    msg.textContent = `${data.terminy.length} volných termínů u vás`;
    box.innerHTML = data.terminy.map((t) => {
      const cas = (t.cas || t).toString().slice(0, 5);
      return `<button type="button" class="termin-btn" data-cas="${esc(cas)}">${esc(cas)}</button>`;
    }).join('');
    box.querySelectorAll('.termin-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        box.querySelectorAll('.termin-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        selectedCas = btn.dataset.cas;
        $('#nova-cas').value = selectedCas;
      });
    });
  } catch (err) {
    msg.textContent = err.message;
  }
}

function refreshAfterNova() {
  const active = $$('.tab.active')[0]?.dataset.tab;
  if (active === 'mujden') loadWeekList(false);
  else if (active === 'mesic') loadMonth();
  else if (active === 'overview') loadWeekList(true);
}

async function boot() {
  if (!getToken()) {
    showLogin();
    return;
  }
  try {
    const user = await api('/flow/me/');
    showLoggedIn(user);
  } catch (_) {
    setToken('');
    showLogin();
  }
}

$('#form-login')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#login-msg');
  try {
    const data = await api('/flow/prihlaseni/', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#login-email').value.trim(),
        password: $('#login-password').value,
      }),
    });
    setToken(data.token);
    showLoggedIn(data.user);
    msg.hidden = true;
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#btn-logout')?.addEventListener('click', async () => {
  try {
    await api('/flow/odhlaseni/', { method: 'POST' });
  } catch (_) { /* ignore */ }
  setToken('');
  showLogin();
});

$('#form-password')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#pwd-msg');
  try {
    const data = await api('/flow/zmena-hesla/', {
      method: 'POST',
      body: JSON.stringify({
        current_password: $('#pwd-current').value,
        new_password: $('#pwd-new').value,
      }),
    });
    showMsg(msg, data.detail || 'Hotovo.', true);
    e.target.reset();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$$('.tab').forEach((tab) => {
  tab.addEventListener('click', () => setTab(tab.dataset.tab));
});

$('#week-prev')?.addEventListener('click', () => { weekOffset -= 1; loadWeekList(false); });
$('#week-next')?.addEventListener('click', () => { weekOffset += 1; loadWeekList(false); });
$('#week-today')?.addEventListener('click', () => { weekOffset = 0; loadWeekList(false); });
$('#ov-week-prev')?.addEventListener('click', () => { ovWeekOffset -= 1; loadWeekList(true); });
$('#ov-week-next')?.addEventListener('click', () => { ovWeekOffset += 1; loadWeekList(true); });
$('#ov-week-today')?.addEventListener('click', () => { ovWeekOffset = 0; loadWeekList(true); });
$('#month-prev')?.addEventListener('click', () => { monthOffset -= 1; loadMonth(); });
$('#month-next')?.addEventListener('click', () => { monthOffset += 1; loadMonth(); });
$('#month-today')?.addEventListener('click', () => { monthOffset = 0; loadMonth(); });

$('#btn-rozvrh-save')?.addEventListener('click', async () => {
  const msg = $('#rozvrh-msg');
  try {
    await api('/flow/rozvrh/', {
      method: 'PUT',
      body: JSON.stringify({ rozvrh: collectRozvrh() }),
    });
    showMsg(msg, 'Pracovní doba uložena. Web i rezervace ji už používají.', true);
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#btn-nova-rez')?.addEventListener('click', () => openNova());
$('#nova-close')?.addEventListener('click', closeNova);
$('#nova-cancel')?.addEventListener('click', closeNova);
$('#nova-datum')?.addEventListener('change', loadNovaTerminy);
$('#form-nova')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#nova-msg');
  const sluzby = selectedSluzbyIds();
  if (!sluzby.length) {
    showMsg(msg, 'Vyberte alespoň jednu službu.', false);
    return;
  }
  const cas = ($('#nova-cas').value || selectedCas || '').slice(0, 5);
  if (!cas) {
    showMsg(msg, 'Vyberte čas termínu.', false);
    return;
  }
  let email = '';
  if (!$('#nova-no-email').checked) {
    email = $('#nova-email').value.trim();
    if (!email) {
      showMsg(msg, 'Vyplňte e-mail, nebo zaškrtněte „Nemá e-mail“.', false);
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showMsg(msg, 'E-mail vypadá neplatně.', false);
      return;
    }
  }
  try {
    await api('/flow/rezervace/', {
      method: 'POST',
      body: JSON.stringify({
        sluzby,
        datum: $('#nova-datum').value,
        cas,
        nick: $('#nova-nick').value.trim(),
        email,
        poznamka_zakaznika: $('#nova-pozn').value.trim(),
        poznamka_interni: $('#nova-interni').value.trim(),
        typ_vytvoreni: $('#nova-typ').value,
        stav: 'potvrzeno',
      }),
    });
    closeNova();
    refreshAfterNova();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#nova-no-email')?.addEventListener('change', () => {
  const off = $('#nova-no-email').checked;
  const input = $('#nova-email');
  input.disabled = off;
  if (off) input.value = '';
});

function renderAbsenceKonflikt(items, absence = null) {
  const box = $('#abs-konflikt');
  if (!box) return;
  const typ = absence?.typ || '';
  const typLabel = absence?.typ_label || ({
    dovolena: 'Dovolená',
    nemoc: 'Nemoc',
    technicke: 'Technické problémy',
  }[typ] || 'Absence');
  const duvodText = ({
    dovolena: 'dovolené',
    nemoc: 'nemoci',
    technicke: 'technickým problémům',
  }[typ] || 'absenci');
  const duvodZakaznik = ({
    dovolena: 'plánovaná dovolená našeho týmu',
    nemoc: 'nečekaná nemoc v týmu',
    technicke: 'technické okolnosti na naší straně',
  }[typ] || typLabel);
  box.classList.remove('hidden', 'ok');
  if (!items.length) {
    box.classList.add('ok');
    box.innerHTML = `
      <h3>${esc(typLabel)} uložena</h3>
      <p class="hint">V tomto období nemáte žádné aktivní rezervace — není co řešit.</p>
    `;
    return;
  }
  box.innerHTML = `
    <h3>Pozor: ${items.length} aktivní rezervace při „${esc(typLabel)}“</h3>
    <p class="hint">Nové termíny se zablokují kvůli ${esc(duvodText)}, ale tyto už existují. Kontaktujte zákazníka (s omluvou) a případně stornujte — dostane zdvořilý storno e-mail.</p>
    <div class="list" id="abs-konflikt-list"></div>
  `;
  const list = $('#abs-konflikt-list');
  list.innerHTML = items.map((r) => {
    const jmeno = r.kontaktni_jmeno || r.jmeno_host || 'Zákazník';
    const email = (r.kontaktni_email || '').trim();
    const kontakt = email
      ? `<p class="kontakt-line">Kontakt: <a href="mailto:${esc(email)}">${esc(email)}</a></p>`
      : `<p class="kontakt-line">Kontakt: <em>bez e-mailu — domluvte se telefonicky / osobně</em></p>`;
    return `<article class="item" data-id="${r.id}">
      <div class="item-top">
        <time>${esc(formatDateTime(r.zacatek))}</time>
        <span class="badge">${esc(STAV_LABEL[r.stav] || r.stav)}</span>
      </div>
      <p class="item-title">${esc(jmeno)}</p>
      <p class="meta">${esc(sluzbyText(r))}</p>
      ${kontakt}
      <div class="actions">
        <button type="button" class="btn tiny danger" data-abs-storno="${r.id}">Stornovat s omluvou</button>
      </div>
    </article>`;
  }).join('');
  list.querySelectorAll('[data-abs-storno]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.absStorno);
      if (!confirm(`Stornovat rezervaci a omluvit se zákazníkovi?\nDůvod v e-mailu: ${duvodZakaznik}`)) return;
      try {
        await api(`/flow/rezervace/${id}/storno/`, {
          method: 'DELETE',
          headers: { 'X-Absence-Duvod': duvodZakaznik },
        });
        const left = items.filter((r) => r.id !== id);
        renderAbsenceKonflikt(left, absence);
        loadAbsence();
      } catch (err) {
        showMsg($('#abs-msg'), err.message, false);
      }
    });
  });
}

$('#form-absence')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#abs-msg');
  try {
    const data = await api('/flow/absence/', {
      method: 'POST',
      body: JSON.stringify({
        datum_od: $('#abs-od').value,
        datum_do: $('#abs-do').value,
        typ: $('#abs-typ').value,
        poznamka: $('#abs-poznamka').value.trim(),
      }),
    });
    showMsg(msg, 'Absence uložena.', true);
    e.target.reset();
    renderAbsenceKonflikt(data.konfliktni_rezervace || [], data.absence || null);
    loadAbsence();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#noshow-cancel')?.addEventListener('click', closeNoshow);
$('#noshow-confirm')?.addEventListener('click', async () => {
  if (!noshowTargetId) return;
  const msg = $('#noshow-msg');
  try {
    await api(`/flow/rezervace/${noshowTargetId}/noshow/`, {
      method: 'POST',
      body: JSON.stringify({
        odeslat_upozorneni: $('#noshow-send-email').checked,
      }),
    });
    closeNoshow();
    loadWeekList(false);
    if (!$('#pane-mesic').classList.contains('hidden')) loadMonth();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#platba-cancel')?.addEventListener('click', closePlatba);
$('#form-platba')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!platbaTarget) return;
  const msg = $('#platba-msg');
  try {
    const data = await api(`/flow/rezervace/${platbaTarget.id}/platba/`, {
      method: 'POST',
      body: JSON.stringify({
        castka: $('#platba-castka').value.trim(),
        ucet: $('#platba-ucet').value.trim(),
        variabilni_symbol: $('#platba-vs').value.trim(),
      }),
    });
    closePlatba();
    $('#platba-qr-info').textContent = `${data.castka} Kč · účet ${data.ucet} · VS ${data.variabilni_symbol}`;
    $('#platba-qr-image').src = `data:image/png;base64,${data.qr_png_base64}`;
    $('#platba-qr-modal').classList.remove('hidden');
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});
$('#platba-qr-close')?.addEventListener('click', () => {
  $('#platba-qr-modal').classList.add('hidden');
});

boot();
