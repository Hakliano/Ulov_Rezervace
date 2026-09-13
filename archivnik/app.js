const PUBLIC_BASE_PATH = '/archivnik/';
const API_PUBLIC_BASE_URL = (function () {
  const h = window.location.hostname;
  const local = window.location.protocol === 'file:'
    || h === '127.0.0.1' || h === '::1' || h === '[::1]'
    || (h && h.indexOf('.') === -1);
  if (local) {
    const apiHost = (h === '::1' || h === '[::1]') ? '127.0.0.1' : (h || '127.0.0.1');
    return 'http://' + apiHost + ':8000/api/archivnik';
  }
  if (h && h.indexOf('staging') !== -1) return 'https://api-staging.ulovklienty.cz/api/archivnik';
  return 'https://api.ulovklienty.cz/api/archivnik';
})();

const TOKEN_KEY = 'archivnik_token';
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let me = null;
let currentTab = 'overview';
let selectedCustomer = null;
let cache = { customers: [], types: [], tags: [], reminders: [], objects: [], entries: [] };

function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers['X-Archivnik-Token'] = token;
  const res = await fetch(`${API_PUBLIC_BASE_URL}${path}`, { ...options, headers });
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (_) { data = null; }
  if (res.status === 401 || res.status === 403) {
    if (path !== '/auth/login/') setToken('');
    throw new Error(data?.detail || 'Přihlášení vypršelo.');
  }
  if (!res.ok) throw new Error(data?.detail || res.statusText || 'Chyba');
  return data;
}

function showLogin(error) {
  $('#app-screen').classList.add('hidden');
  $('#login-screen').classList.remove('hidden');
  $('#login-error').textContent = error || '';
  $('#login-error').classList.toggle('hidden', !error);
}

function showApp() {
  $('#login-screen').classList.add('hidden');
  $('#app-screen').classList.remove('hidden');
  $('#sidebar-name').textContent = me.jmeno || me.email;
  $('#sidebar-salon').textContent = me.provozovna || '';
}

async function boot() {
  if (!getToken()) { showLogin(); return; }
  try {
    me = await api('/me/');
    showApp();
    await loadTab(currentTab);
  } catch (err) {
    setToken('');
    showLogin(err.message);
  }
}

$('#login-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  try {
    const data = await api('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#login-email').value,
        password: $('#login-password').value,
      }),
    });
    setToken(data.token);
    me = data;
    showApp();
    await loadTab('overview');
  } catch (err) {
    showLogin(err.message);
  }
});

$('#btn-logout').addEventListener('click', async () => {
  try { await api('/auth/logout/', { method: 'POST' }); } catch (_) {}
  setToken('');
  me = null;
  showLogin();
});

$$('.tab').forEach((btn) => {
  btn.addEventListener('click', () => loadTab(btn.dataset.tab));
});

$('#search-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const q = $('#search-q').value.trim();
  const box = $('#search-results');
  if (q.length < 2) { box.classList.add('hidden'); return; }
  const data = await api(`/search/?q=${encodeURIComponent(q)}`);
  box.classList.remove('hidden');
  box.innerHTML = `
    <h3>Nalezení zákazníci</h3>
    ${(data.zakaznici || []).map((c) => `<div class="row"><button type="button" class="linkish" data-open-customer="${c.uuid}">${esc(c.display_name)}</button><span class="muted">${esc(c.telefon || c.email)}</span></div>`).join('') || '<p class="muted">Nikdo.</p>'}
    <h3>Objekty</h3>
    ${(data.objekty || []).map((o) => `<div class="row"><span>${esc(o.nazev)} <span class="muted">${esc(o.typ_nazev)}</span></span><button type="button" class="linkish" data-open-customer="${o.zakaznik_uuid}">${esc(o.zakaznik_jmeno)}</button></div>`).join('') || '<p class="muted">Nic.</p>'}
  `;
  bindCustomerLinks(box);
});

function setTab(tab) {
  currentTab = tab;
  $$('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.tab-panel').forEach((el) => el.classList.toggle('hidden', el.id !== `tab-${tab}`));
}

async function loadTab(tab) {
  setTab(tab);
  if (tab === 'overview') await renderOverview();
  if (tab === 'customers') await renderCustomers();
  if (tab === 'reminders') await renderReminders();
  if (tab === 'tags') await renderTags();
  if (tab === 'types') await renderTypes();
}

async function renderOverview() {
  const data = await api('/overview/');
  $('#tab-overview').innerHTML = `
    <div class="kpis">
      <div class="kpi"><span class="muted">Zákazníci</span><strong>${data.zakaznici}</strong></div>
      <div class="kpi"><span class="muted">Objekty</span><strong>${data.objekty}</strong></div>
      <div class="kpi"><span class="muted">Zápisy tento měsíc</span><strong>${data.zapisy_mesic}</strong></div>
      <div class="kpi"><span class="muted">Aktivní připomínky</span><strong>${data.pripominky_aktivni}</strong></div>
    </div>
    <div class="panel">
      <h3>Objekty podle typu</h3>
      ${(data.podle_typu || []).map((r) => `<div class="row"><span>${esc(r.typ)}</span><strong>${r.pocet}</strong></div>`).join('') || '<p class="muted">Zatím žádné objekty.</p>'}
    </div>
  `;
}

async function renderCustomers() {
  cache.customers = await api('/customers/?stav=aktivni');
  cache.types = await api('/object-types/');
  cache.tags = await api('/tags/');
  const el = $('#tab-customers');
  el.innerHTML = `
    <div class="grid-2">
      <div class="panel">
        <div class="row"><h2>Zákazníci</h2></div>
        ${cache.customers.map((c) => `
          <div class="row">
            <button type="button" class="linkish" data-open-customer="${c.uuid}">${esc(c.display_name)}</button>
            <span class="muted">${c.objekty_pocet || 0} obj.</span>
          </div>`).join('') || '<p class="muted">Zatím nikdo.</p>'}
      </div>
      <div class="panel">
        <h2>Nový zákazník</h2>
        <form id="form-customer" class="form-grid">
          <input name="jmeno" placeholder="Jméno">
          <input name="prijmeni" placeholder="Příjmení / název" required>
          <input name="telefon" placeholder="Telefon">
          <input name="email" type="email" placeholder="E-mail">
          <input name="adresa" placeholder="Adresa">
          <textarea name="poznamka" placeholder="Interní poznámka"></textarea>
          <button class="btn-primary" type="submit">Uložit</button>
        </form>
        <div id="customer-detail"></div>
      </div>
    </div>
  `;
  el.querySelector('#form-customer').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    await api('/customers/', { method: 'POST', body: JSON.stringify(Object.fromEntries(fd)) });
    await renderCustomers();
  });
  bindCustomerLinks(el);
  if (selectedCustomer) await openCustomer(selectedCustomer);
}

function bindCustomerLinks(root) {
  root.querySelectorAll('[data-open-customer]').forEach((btn) => {
    btn.addEventListener('click', () => openCustomer(btn.dataset.openCustomer));
  });
}

async function openCustomer(uuid) {
  selectedCustomer = uuid;
  setTab('customers');
  const c = await api(`/customers/${uuid}/`);
  cache.objects = await api(`/objects/?zakaznik=${uuid}`);
  cache.entries = await api(`/entries/?zakaznik=${uuid}&vcetne_objektu=1`);
  const box = $('#customer-detail');
  if (!box) {
    await renderCustomers();
    return;
  }
  box.innerHTML = `
    <hr>
    <h2>${esc(c.display_name)}</h2>
    <p class="muted">${esc(c.telefon || '—')} · ${esc(c.email || '—')}</p>
    ${(c.tagy || []).map((t) => `<span class="chip">${esc(t.nazev)}</span>`).join('')}
    <h3>Objekty</h3>
    ${cache.objects.map((o) => `<div class="row"><span>${esc(o.nazev)} <span class="muted">${esc(o.typ_nazev)}</span></span></div>`).join('') || '<p class="muted">Žádný objekt.</p>'}
    <form id="form-object" class="form-grid">
      <select name="typ_uuid" required>
        <option value="">Typ objektu</option>
        ${cache.types.filter((t) => t.aktivni).map((t) => `<option value="${t.uuid}">${esc(t.nazev)}</option>`).join('')}
      </select>
      <input name="nazev" placeholder="Název objektu" required>
      <textarea name="popis" placeholder="Popis"></textarea>
      <button class="btn-small" type="submit">Přidat objekt</button>
    </form>
    <h3>Zápisy</h3>
    ${cache.entries.map((e) => `<div class="row"><div><strong>${esc(e.nadpis || e.typ_zapisu)}</strong><div class="muted">${esc(e.objekt_nazev || 'u zákazníka')} · ${esc((e.nastalo || '').slice(0, 16).replace('T', ' '))}</div><div>${esc(e.text)}</div></div></div>`).join('') || '<p class="muted">Žádné zápisy.</p>'}
    <form id="form-entry" class="form-grid">
      <select name="objekt_uuid">
        <option value="">Zápis k zákazníkovi</option>
        ${cache.objects.map((o) => `<option value="${o.uuid}">${esc(o.nazev)}</option>`).join('')}
      </select>
      <input name="nadpis" placeholder="Nadpis (volitelně)">
      <textarea name="text" placeholder="Text zápisu" required></textarea>
      <button class="btn-small" type="submit">Přidat zápis</button>
    </form>
    <form id="form-reminder" class="form-grid">
      <input name="termin" type="date" required>
      <input name="text" placeholder="Připomínka" required>
      <button class="btn-small" type="submit">Přidat připomínku</button>
    </form>
  `;
  box.querySelector('#form-object').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = Object.fromEntries(new FormData(ev.target));
    await api('/objects/', { method: 'POST', body: JSON.stringify({ ...fd, zakaznik_uuid: uuid }) });
    await openCustomer(uuid);
  });
  box.querySelector('#form-entry').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = Object.fromEntries(new FormData(ev.target));
    const payload = { text: fd.text, nadpis: fd.nadpis };
    if (fd.objekt_uuid) payload.objekt_uuid = fd.objekt_uuid;
    else payload.zakaznik_uuid = uuid;
    await api('/entries/', { method: 'POST', body: JSON.stringify(payload) });
    await openCustomer(uuid);
  });
  box.querySelector('#form-reminder').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = Object.fromEntries(new FormData(ev.target));
    await api('/reminders/', { method: 'POST', body: JSON.stringify({ ...fd, zakaznik_uuid: uuid }) });
    await openCustomer(uuid);
  });
}

async function renderReminders() {
  const data = await api('/reminders/?stav=aktivni');
  $('#tab-reminders').innerHTML = `
    <div class="panel">
      <h2>Aktivní připomínky</h2>
      ${data.map((r) => `
        <div class="row">
          <div>
            <strong>${esc(r.text)}</strong>
            <div class="muted">${esc(r.termin)} · ${esc(r.zakaznik_jmeno)}${r.objekt_nazev ? ' · ' + esc(r.objekt_nazev) : ''}</div>
          </div>
          <button type="button" class="btn-small" data-done="${r.uuid}">Hotovo</button>
        </div>`).join('') || '<p class="muted">Nic nečeká.</p>'}
    </div>
  `;
  $('#tab-reminders').querySelectorAll('[data-done]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/reminders/${btn.dataset.done}/done/`, { method: 'POST' });
      await renderReminders();
    });
  });
}

async function renderTags() {
  const data = await api('/tags/');
  $('#tab-tags').innerHTML = `
    <div class="panel">
      <h2>Štítky</h2>
      ${data.map((t) => `<div class="row"><span>${esc(t.nazev)}</span><span class="muted">${esc(t.rozsah)}</span></div>`).join('') || '<p class="muted">Žádné štítky.</p>'}
      <form id="form-tag" class="form-grid">
        <input name="nazev" placeholder="Název štítku" required>
        <select name="rozsah">
          <option value="obe">Zákazník i objekt</option>
          <option value="zakaznik">Jen zákazník</option>
          <option value="objekt">Jen objekt</option>
        </select>
        <button class="btn-primary" type="submit">Přidat</button>
      </form>
    </div>
  `;
  $('#form-tag').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    await api('/tags/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(ev.target))) });
    await renderTags();
  });
}

async function renderTypes() {
  const data = await api('/object-types/');
  $('#tab-types').innerHTML = `
    <div class="panel">
      <h2>Typy objektů</h2>
      ${data.map((t) => `<div class="row"><span>${esc(t.nazev)}</span><span class="muted">${t.aktivni ? 'aktivní' : 'vypnuto'}</span></div>`).join('') || '<p class="muted">Zatím žádný typ.</p>'}
      <form id="form-type" class="form-grid">
        <input name="nazev" placeholder="Např. Vozidlo, Nemovitost, Zvíře" required>
        <button class="btn-primary" type="submit">Přidat typ</button>
      </form>
    </div>
  `;
  $('#form-type').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    await api('/object-types/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(ev.target))) });
    await renderTypes();
  });
}

boot();
void PUBLIC_BASE_PATH;
