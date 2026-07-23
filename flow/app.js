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
let riskyAlertItems = [];
let mailUnseenCount = 0;
let noshowTargetId = null;
let platbaTarget = null;
let platbaIsZaloha = false;
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
  if (name === 'mail') loadMailList();
}

function applyFlowBanner(salon) {
  const el = $('#flow-banner');
  if (!el) return;
  const text = (salon?.banner_text || '').trim();
  const enabled = !!salon?.banner_enabled;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const od = salon?.banner_od ? new Date(`${salon.banner_od}T00:00:00`) : null;
  const doDate = salon?.banner_do ? new Date(`${salon.banner_do}T00:00:00`) : null;
  const inRange = (!od || today >= od) && (!doDate || today <= doDate);
  if (enabled && text && inRange) {
    el.textContent = text;
    el.classList.remove('hidden');
  } else {
    el.textContent = '';
    el.classList.add('hidden');
  }
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
  applyFlowBanner(user.salon);
  const ovTab = $('#tab-overview');
  if (user.visible_overview) ovTab.classList.remove('hidden');
  else ovTab.classList.add('hidden');
  setTab('mujden');
  refreshTopAlerts();
}

function showLogin() {
  currentUser = null;
  riskyAlertItems = [];
  mailUnseenCount = 0;
  applyFlowBanner(null);
  const alerts = $('#flow-alerts');
  if (alerts) {
    alerts.classList.add('hidden');
    alerts.innerHTML = '';
  }
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
    const badges = [];
    if (r.je_rizikova && !r.zaloha_ok_at) badges.push('<span class="badge warn">riziková</span>');
    if (r.zaloha_vyzadana_at && !r.zaloha_ok_at) badges.push('<span class="badge warn">čeká záloha</span>');
    if (r.zaloha_ok_at) badges.push('<span class="badge ok">záloha OK</span>');
    const actions = (!readonly && canAct(r))
      ? `<div class="actions">
          <button type="button" class="btn tiny primary" data-act="done" data-id="${r.id}">Proběhla</button>
          <button type="button" class="btn tiny danger" data-act="noshow" data-id="${r.id}">NO-show</button>
          <button type="button" class="btn tiny ghost" data-act="platba" data-id="${r.id}">Platba QR</button>
          ${r.je_rizikova || r.zaloha_vyzadana_at ? `<button type="button" class="btn tiny ghost" data-act="zaloha" data-id="${r.id}">Požádat o zálohu</button>` : ''}
          ${r.zaloha_vyzadana_at && !r.zaloha_ok_at ? `<button type="button" class="btn tiny primary" data-act="zaloha-ok" data-id="${r.id}">Záloha OK</button>` : ''}
          <button type="button" class="btn tiny ghost" data-act="storno" data-id="${r.id}">Storno</button>
        </div>`
      : (readonly
        ? `<p class="meta">u ${esc(r.zamestnanec_jmeno || '—')}</p>`
        : '');
    return `<article class="item stav-${esc(r.stav)}${r.je_rizikova && !r.zaloha_ok_at ? ' risky' : ''}" data-id="${r.id}">
      <div class="item-top">
        <time>${esc(formatDateTime(r.zacatek))}</time>
        <span class="badge">${esc(STAV_LABEL[r.stav] || r.stav)}</span>
        ${badges.join(' ')}
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
    if (!overview) refreshRiskyInbox();
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
        const r = findRezervace(id);
        let duvod = '';
        if (r?.zaloha_vyzadana_at && !r?.zaloha_ok_at) {
          duvod = prompt('Důvod storna:', 'Nezaplacená zálohová platba') || 'Nezaplacená zálohová platba';
        }
        if (!confirm('Stornovat rezervaci? Zákazník dostane e-mail.')) return;
        try {
          await api(`/flow/rezervace/${id}/storno/`, {
            method: 'DELETE',
            body: JSON.stringify({ duvod }),
          });
          onDone?.();
          refreshTopAlerts();
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'noshow') {
        openNoshow(id);
      } else if (act === 'platba') {
        openPlatba(id, false);
      } else if (act === 'zaloha') {
        openPlatba(id, true);
      } else if (act === 'zaloha-ok') {
        if (!confirm('Potvrdit přijetí zálohy? Zákazník dostane e-mail.')) return;
        try {
          await api(`/flow/rezervace/${id}/zaloha-ok/`, { method: 'POST', body: '{}' });
          onDone?.();
          refreshTopAlerts();
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
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

async function openPlatba(id, asZaloha = false) {
  const r = findRezervace(id);
  platbaTarget = r || { id };
  platbaIsZaloha = !!asZaloha;
  const title = $('#platba-modal h2');
  if (title) title.textContent = asZaloha ? 'Žádost o zálohu' : 'Žádost o platbu';
  $('#platba-info').textContent = r
    ? `${r.kontaktni_jmeno || 'Zákazník'} — ${formatDateTime(r.zacatek)}${asZaloha ? ' · záloha (lhůtu uveďte v e-mailové šabloně)' : ''}`
    : `Rezervace #${id}`;
  $('#platba-castka').value = r?.zaloha_castka || '';
  $('#platba-ucet').value = r?.zamestnanec_cislo_uctu || '';
  $('#platba-vs').value = String(id);
  $('#platba-msg').hidden = true;
  $('#platba-modal').classList.remove('hidden');
}

function closePlatba() {
  platbaTarget = null;
  platbaIsZaloha = false;
  $('#platba-modal').classList.add('hidden');
}

function ymdPlusDays(days) {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function filterRiskyItems(items) {
  return (items || []).filter((r) => (
    r.je_rizikova
    && !r.zaloha_ok_at
    && ['ceka', 'potvrzeno'].includes(r.stav)
  ));
}

function renderTopAlerts(riskyN, mailN, mailOk) {
  const box = $('#flow-alerts');
  if (!box) return;
  const parts = [];
  if (riskyN > 0) {
    parts.push(`<div class="flow-alert warn">
      <div class="flow-alert-text">
        <strong>Rizikové rezervace: ${riskyN}</strong>
        <span>Ke kontrole — můžete požádat o zálohu, nebo nechat běžet</span>
      </div>
      <button type="button" class="btn primary sm" id="alert-goto-risky">Zobrazit</button>
    </div>`);
  }
  if (mailOk && mailN > 0) {
    parts.push(`<div class="flow-alert mail">
      <div class="flow-alert-text">
        <strong>Nepřečtené e-maily: ${mailN}</strong>
        <span>Schránka FLOW</span>
      </div>
      <button type="button" class="btn primary sm" id="alert-goto-mail">Otevřít mail</button>
    </div>`);
  }
  if (!parts.length) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  box.innerHTML = parts.join('');
  $('#alert-goto-risky')?.addEventListener('click', () => {
    setTab('mujden');
    requestAnimationFrame(() => {
      $('#risky-inbox')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  $('#alert-goto-mail')?.addEventListener('click', () => setTab('mail'));
}

async function refreshTopAlerts() {
  if (!currentUser) return;
  let risky = [];
  let unseen = 0;
  let mailOk = false;
  try {
    const q = new URLSearchParams({ od: ymdPlusDays(-1), do: ymdPlusDays(120) });
    const data = await api(`/flow/kalendar/?${q}`);
    rememberRez(data.rezervace);
    risky = filterRiskyItems(data.rezervace);
    riskyAlertItems = risky;
  } catch {
    risky = filterRiskyItems([...rezById.values()]);
    riskyAlertItems = risky;
  }
  try {
    const mail = await api('/flow/mail/?limit=40');
    mailOk = true;
    unseen = (mail.items || []).filter((m) => m.unseen).length;
    mailUnseenCount = unseen;
  } catch {
    mailOk = false;
    mailUnseenCount = 0;
  }
  renderTopAlerts(risky.length, unseen, mailOk);
  refreshRiskyInbox();
  const mailTab = $('#tab-mail');
  if (mailTab) {
    mailTab.textContent = (mailOk && unseen > 0) ? `Mail (${unseen})` : 'Mail';
  }
}

function refreshRiskyInbox() {
  const box = $('#risky-inbox');
  if (!box) return;
  const risky = riskyAlertItems.length
    ? riskyAlertItems
    : filterRiskyItems([...rezById.values()]);
  if (!risky.length) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  box.innerHTML = `<h3 class="list-h">Rizikové / ke kontrole (${risky.length})</h3>
    <p class="hint tiny">Služby označené jako rizikové. Můžete požádat o zálohu, nebo nechat rezervaci běžet.</p>
    <div id="risky-list" class="list"></div>`;
  const holder = document.createElement('div');
  renderRezervaceList(holder, risky, { emptyText: '' });
  box.querySelector('#risky-list').appendChild(holder);
  bindCalActions(holder, () => {
    loadWeekList(false);
    refreshTopAlerts();
  });
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

let mailCache = [];
let mailOpenUid = null;
let mailFolder = 'inbox'; // inbox | odeslane

function formatMailDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('cs-CZ', {
      day: 'numeric', month: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch (_) {
    return iso;
  }
}

function setMailFolder(folder) {
  mailFolder = folder === 'odeslane' ? 'odeslane' : 'inbox';
  $$('.mail-folder').forEach((b) => b.classList.toggle('active', b.dataset.folder === mailFolder));
  const replyBtn = $('#mail-reply');
  if (replyBtn) replyBtn.classList.toggle('hidden', mailFolder === 'odeslane');
  loadMailList();
}

function showMailListView() {
  $('#mail-detail')?.classList.add('hidden');
  $('#mail-list')?.classList.remove('hidden');
  mailOpenUid = null;
}

function showMailDetailView() {
  $('#mail-list')?.classList.add('hidden');
  $('#mail-detail')?.classList.remove('hidden');
}

async function loadMailList() {
  const msg = $('#mail-msg');
  const list = $('#mail-list');
  showMailListView();
  if (list) {
    list.innerHTML = mailFolder === 'odeslane'
      ? '<p class="empty">Načítám odeslané…</p>'
      : '<p class="empty">Načítám schránku…</p>';
  }
  try {
    const path = mailFolder === 'odeslane'
      ? '/flow/mail/odeslane/?limit=40'
      : '/flow/mail/?limit=40';
    const data = await api(path);
    mailCache = data.items || [];
    if (mailFolder === 'odeslane') {
      $('#mail-mailbox').textContent = 'Odeslané z FLOW';
    } else {
      $('#mail-mailbox').textContent = data.mailbox
        ? `Schránka · ${data.mailbox}`
        : 'Schránka';
    }
    if (!mailCache.length) {
      list.innerHTML = mailFolder === 'odeslane'
        ? '<p class="empty">Zatím žádné odeslané z FLOW.</p>'
        : '<p class="empty">Žádné zprávy ve schránce.</p>';
      showMsg(msg, '', true);
      msg.hidden = true;
      return;
    }
    list.innerHTML = mailCache.map((m) => {
      if (mailFolder === 'odeslane') {
        return `<article class="item mail-item" data-id="${m.id}">
          <div class="item-top">
            <time>${esc(formatMailDate(m.date))}</time>
          </div>
          <h3>${esc(m.subject)}</h3>
          <p class="meta">Komu: ${esc(m.to)}${m.from_name ? ` · odeslal(a) ${esc(m.from_name)}` : ''}</p>
        </article>`;
      }
      const who = m.from_name || m.from_email || '—';
      const unseen = m.unseen ? ' unseen' : '';
      return `<article class="item mail-item${unseen}" data-uid="${m.uid}">
        <div class="item-top">
          <time>${esc(formatMailDate(m.date))}</time>
          ${m.unseen ? '<span class="badge">Nové</span>' : ''}
        </div>
        <h3>${esc(m.subject)}</h3>
        <p class="meta">${esc(who)}${m.from_email && m.from_name ? ` · ${esc(m.from_email)}` : ''}</p>
      </article>`;
    }).join('');
    list.querySelectorAll('.mail-item').forEach((el) => {
      el.addEventListener('click', () => {
        if (mailFolder === 'odeslane') openOdeslane(Number(el.dataset.id));
        else openMail(Number(el.dataset.uid));
      });
    });
    msg.hidden = true;
  } catch (err) {
    list.innerHTML = '';
    showMsg(msg, err.message, false);
  }
}

async function openMail(uid) {
  const msg = $('#mail-msg');
  try {
    const data = await api(`/flow/mail/${uid}/`);
    mailOpenUid = uid;
    $('#mail-reply')?.classList.remove('hidden');
    $('#mail-subject').textContent = data.subject || '(bez předmětu)';
    const who = data.from_name || data.from_email || '—';
    $('#mail-meta').textContent = `${who}${data.from_email && data.from_name ? ` <${data.from_email}>` : ''} · ${formatMailDate(data.date)}`;
    $('#mail-body').textContent = data.body || '(prázdná zpráva)';
    showMailDetailView();
    const item = mailCache.find((m) => m.uid === uid);
    if (item) item.unseen = false;
    msg.hidden = true;
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

async function openOdeslane(id) {
  const msg = $('#mail-msg');
  try {
    const data = await api(`/flow/mail/odeslane/${id}/`);
    mailOpenUid = null;
    $('#mail-reply')?.classList.add('hidden');
    $('#mail-subject').textContent = data.subject || '(bez předmětu)';
    $('#mail-meta').textContent = `Komu: ${data.to || '—'} · ${formatMailDate(data.date)}${data.from_name ? ` · ${data.from_name}` : ''}`;
    $('#mail-body').textContent = data.body || '(prázdná zpráva)';
    showMailDetailView();
    msg.hidden = true;
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function openMailCompose({ to = '', subject = '', body = '', replyUid = '' } = {}) {
  $('#mail-modal-title').textContent = replyUid ? 'Odpovědět' : 'Nový e-mail';
  $('#mail-reply-uid').value = replyUid ? String(replyUid) : '';
  $('#mail-to').value = to;
  $('#mail-subject-input').value = subject;
  $('#mail-body-input').value = body;
  showMsg($('#mail-send-msg'), '', true);
  $('#mail-send-msg').hidden = true;
  $('#mail-modal').classList.remove('hidden');
}

function closeMailCompose() {
  $('#mail-modal').classList.add('hidden');
}

function quoteForReply(detail) {
  const lines = (detail.body || '').split('\n').map((l) => `> ${l}`).join('\n');
  const who = detail.from_name || detail.from_email || 'odesílatel';
  return `\n\n———\n${who} napsal(a):\n${lines}`;
}

async function replyToOpenMail() {
  if (!mailOpenUid || mailFolder === 'odeslane') return;
  try {
    const data = await api(`/flow/mail/${mailOpenUid}/`);
    let subj = data.subject || '';
    if (!/^re:/i.test(subj)) subj = `Re: ${subj}`;
    openMailCompose({
      to: data.from_email || '',
      subject: subj,
      body: quoteForReply(data),
      replyUid: mailOpenUid,
    });
  } catch (err) {
    showMsg($('#mail-msg'), err.message, false);
  }
}

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

$('#mail-refresh')?.addEventListener('click', () => loadMailList());
$('#mail-compose')?.addEventListener('click', () => openMailCompose());
$$('.mail-folder').forEach((btn) => {
  btn.addEventListener('click', () => setMailFolder(btn.dataset.folder));
});
$('#mail-back')?.addEventListener('click', () => {
  showMailListView();
  loadMailList();
});
$('#mail-reply')?.addEventListener('click', () => replyToOpenMail());
$('#mail-modal-close')?.addEventListener('click', closeMailCompose);
$('#mail-modal-cancel')?.addEventListener('click', closeMailCompose);
$('#form-mail')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#mail-send-msg');
  const replyUid = $('#mail-reply-uid').value;
  try {
    await api('/flow/mail/odeslat/', {
      method: 'POST',
      body: JSON.stringify({
        to: $('#mail-to').value.trim(),
        subject: $('#mail-subject-input').value.trim(),
        body: $('#mail-body-input').value,
        reply_uid: replyUid ? Number(replyUid) : null,
      }),
    });
    showMsg(msg, 'Odesláno.', true);
    closeMailCompose();
    if ($('#pane-mail') && !$('#pane-mail').classList.contains('hidden')) {
      setMailFolder('odeslane');
    }
  } catch (err) {
    showMsg(msg, err.message, false);
  }
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
    <p class="hint">Nové termíny se zablokují kvůli ${esc(duvodText)}. U každé rezervace můžete převést na volného kolegu, nebo stornovat s omluvou.</p>
    <div class="list" id="abs-konflikt-list"></div>
  `;
  const list = $('#abs-konflikt-list');
  list.innerHTML = items.map((r) => {
    const jmeno = r.kontaktni_jmeno || r.jmeno_host || 'Zákazník';
    const email = (r.kontaktni_email || '').trim();
    const kontakt = email
      ? `<p class="kontakt-line">Kontakt: <a href="mailto:${esc(email)}">${esc(email)}</a></p>`
      : `<p class="kontakt-line">Kontakt: <em>bez e-mailu — domluvte se telefonicky / osobně</em></p>`;
    const kolegove = r.dostupni_kolegove || [];
    let prevest = '';
    if (kolegove.length) {
      const opts = kolegove.map((k) =>
        `<option value="${k.id}">${esc(k.jmeno)}</option>`
      ).join('');
      prevest = `
        <div class="prevest-row">
          <select data-abs-kolega="${r.id}" aria-label="Kolega">
            <option value="">— kolega —</option>
            ${opts}
          </select>
          <button type="button" class="btn tiny" data-abs-prevest="${r.id}">Převést</button>
        </div>`;
    } else {
      prevest = `<p class="hint tiny">Žádný volný kolega v tomto termínu.</p>`;
    }
    return `<article class="item" data-id="${r.id}">
      <div class="item-top">
        <time>${esc(formatDateTime(r.zacatek))}</time>
        <span class="badge">${esc(STAV_LABEL[r.stav] || r.stav)}</span>
      </div>
      <p class="item-title">${esc(jmeno)}</p>
      <p class="meta">${esc(sluzbyText(r))}</p>
      ${kontakt}
      ${prevest}
      <div class="actions">
        <button type="button" class="btn tiny danger" data-abs-storno="${r.id}">Stornovat s omluvou</button>
      </div>
    </article>`;
  }).join('');

  list.querySelectorAll('[data-abs-prevest]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.absPrevest);
      const sel = list.querySelector(`select[data-abs-kolega="${id}"]`);
      const kolegaId = Number(sel?.value || 0);
      if (!kolegaId) {
        showMsg($('#abs-msg'), 'Vyberte kolegu.', false);
        return;
      }
      const jmeno = sel.options[sel.selectedIndex]?.textContent || 'kolegu';
      if (!confirm(`Převést rezervaci na ${jmeno}?`)) return;
      try {
        await api(`/flow/rezervace/${id}/prevest/`, {
          method: 'POST',
          body: JSON.stringify({ zamestnanec_id: kolegaId }),
        });
        const left = items.filter((r) => r.id !== id);
        renderAbsenceKonflikt(left, absence);
        showMsg($('#abs-msg'), `Rezervace převedena na ${jmeno}.`, true);
        loadAbsence();
      } catch (err) {
        showMsg($('#abs-msg'), err.message, false);
      }
    });
  });

  list.querySelectorAll('[data-abs-storno]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.absStorno);
      if (!confirm(`Stornovat rezervaci a omluvit se zákazníkovi?\nDůvod v e-mailu: ${duvodZakaznik}`)) return;
      try {
        await api(`/flow/rezervace/${id}/storno/`, {
          method: 'DELETE',
          body: JSON.stringify({ duvod: duvodZakaznik }),
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
        zaloha: platbaIsZaloha,
      }),
    });
    closePlatba();
    $('#platba-qr-info').textContent = `${data.castka} Kč · účet ${data.ucet} · VS ${data.variabilni_symbol}`;
    $('#platba-qr-image').src = `data:image/png;base64,${data.qr_png_base64}`;
    $('#platba-qr-modal').classList.remove('hidden');
    loadWeekList(false);
    refreshTopAlerts();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});
$('#platba-qr-close')?.addEventListener('click', () => {
  $('#platba-qr-modal').classList.add('hidden');
});

boot();
