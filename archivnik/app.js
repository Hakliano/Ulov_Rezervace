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
let selectedObject = null;
let cache = { customers: [], types: [], tags: [], objects: [] };

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

function fmtDate(iso) {
  if (!iso) return '—';
  const raw = String(iso);
  const d = raw.length <= 10 ? new Date(`${raw}T00:00:00`) : new Date(raw);
  if (Number.isNaN(d.getTime())) return esc(raw);
  return `${d.getDate()}. ${d.getMonth() + 1}. ${d.getFullYear()}`;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 11) return 'Dobré ráno';
  if (h < 18) return 'Dobré odpoledne';
  return 'Dobrý večer';
}

function stavLabel(stav) {
  return stav === 'archivovany' ? 'Archivovaný' : 'Aktivní';
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

function hideSearch() {
  $('#search-results').classList.add('hidden');
}

async function ensureTypes() {
  if (!cache.types.length) cache.types = await api('/object-types/');
  return cache.types;
}

function markActive(selector, uuid) {
  $$(selector).forEach((el) => {
    const id = el.dataset.openCustomer || el.dataset.openObject;
    el.classList.toggle('active', id === uuid);
  });
}

function showModalError(message) {
  const err = $('#modal-error');
  if (!err) return;
  err.textContent = message || '';
  err.classList.toggle('hidden', !message);
}

function closeModal() {
  $('#modal').classList.add('hidden');
  $('#modal-body').innerHTML = '';
}

function openModal(title, html, onReady) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = `<p id="modal-error" class="error hidden"></p>${html}`;
  $('#modal').classList.remove('hidden');
  if (onReady) onReady($('#modal-body'));
}

function setTab(tab) {
  currentTab = tab;
  hideSearch();
  $$('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.tab-panel').forEach((el) => el.classList.toggle('hidden', el.id !== `tab-${tab}`));
}

async function loadTab(tab) {
  if (tab !== 'customers') selectedCustomer = null;
  if (tab !== 'customers' && tab !== 'objects') selectedObject = null;
  setTab(tab);
  if (tab === 'overview') await renderOverview();
  if (tab === 'customers') await renderCustomers();
  if (tab === 'objects') await renderObjects();
  if (tab === 'reminders') await renderReminders();
  if (tab === 'settings') await renderSettings();
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
$('#modal-close').addEventListener('click', closeModal);
$('#modal').addEventListener('click', (ev) => {
  if (ev.target.id === 'modal') closeModal();
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
    ${(data.objekty || []).map((o) => `<div class="row"><button type="button" class="linkish" data-open-object="${o.uuid}">${esc(o.nazev)}</button><span class="muted">${esc(o.typ_nazev)} · ${esc(o.zakaznik_jmeno)}</span></div>`).join('') || '<p class="muted">Nic.</p>'}
  `;
  bindNav(box);
});

function bindNav(root) {
  root.querySelectorAll('[data-open-customer]').forEach((btn) => {
    btn.addEventListener('click', () => {
      hideSearch();
      selectedObject = null;
      openCustomer(btn.dataset.openCustomer);
    });
  });
  root.querySelectorAll('[data-open-object]').forEach((btn) => {
    btn.addEventListener('click', () => {
      hideSearch();
      const fromObjects = currentTab === 'objects' || Boolean(btn.closest('#tab-objects'));
      openObject(btn.dataset.openObject, { fromObjects });
    });
  });
}

function reminderRow(r) {
  return `<div class="row">
    <div>
      <strong>${esc(r.text)}</strong>
      <div class="muted">${fmtDate(r.termin)}${r.objekt_nazev ? ' · ' + esc(r.objekt_nazev) : ''}${r.zakaznik_jmeno ? ' · ' + esc(r.zakaznik_jmeno) : ''}</div>
    </div>
    <button type="button" class="btn-small" data-done="${r.uuid}">Hotovo</button>
  </div>`;
}

function bindDone(root, after) {
  root.querySelectorAll('[data-done]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/reminders/${btn.dataset.done}/done/`, { method: 'POST' });
      await after();
    });
  });
}

function timelineItem(e) {
  const isObject = Boolean(e.objekt_uuid);
  const who = isObject ? e.objekt_nazev : e.zakaznik_jmeno;
  return `<article class="timeline-item ${isObject ? 'object' : 'customer'}">
    <div class="timeline-when">${fmtDate(e.nastalo)} · ${esc(who || 'Zákazník')}</div>
    <strong>${esc(e.nadpis || e.typ_zapisu || 'Zápis')}</strong>
    <div>${esc(e.text)}</div>
    ${e.autor ? `<div class="muted">${esc(e.autor)}</div>` : ''}
  </article>`;
}

async function renderOverview() {
  const data = await api('/overview/');
  const maxTyp = Math.max(1, ...(data.podle_typu || []).map((r) => r.pocet));
  const soon = data.nejblizsi_pripominky || [];
  $('#tab-overview').innerHTML = `
    <div class="hero-line">
      <h1>${greeting()}, ${esc(data.provozovna)}</h1>
      <p class="muted">Váš Archivník má přehled o <strong>${data.zakaznici}</strong> zákaznících a <strong>${data.objekty}</strong> objektech.</p>
    </div>
    <div class="kpis">
      <div class="kpi"><span class="muted">Zákazníci</span><strong>${data.zakaznici}</strong></div>
      <div class="kpi"><span class="muted">Objekty</span><strong>${data.objekty}</strong></div>
      <div class="kpi"><span class="muted">Zápisy tento měsíc</span><strong>${data.zapisy_mesic}</strong></div>
      <div class="kpi"><span class="muted">Aktivní připomínky</span><strong>${data.pripominky_aktivni}</strong></div>
    </div>
    <div class="ov-grid">
      <section class="panel ov-slot">
        <h3>Váš archiv</h3>
        ${(data.podle_typu || []).map((r) => `
          <div class="bar-row">
            <div>${esc(r.typ)} <span class="muted">${r.pocet}</span>
              <div class="bar"><span style="width:${Math.round((r.pocet / maxTyp) * 100)}%"></span></div>
            </div>
          </div>`).join('') || '<p class="muted">Zatím žádné objekty.</p>'}
        <p class="muted ov-soon">Grafickou vizualizaci typů dokončíme v P2.</p>
      </section>
      <section class="panel ov-slot">
        <h3>Co vás čeká</h3>
        ${soon.map((r) => `<div class="row"><div><strong>${esc(r.text)}</strong><div class="muted">${fmtDate(r.termin)}${r.objekt_nazev ? ' · ' + esc(r.objekt_nazev) : ''}</div></div></div>`).join('') || '<p class="muted">Žádné aktivní připomínky.</p>'}
      </section>
      <section class="panel ov-slot">
        <h3>Růst archivu</h3>
        <p class="muted">Vývoj zákazníků a objektů za posledních 6 měsíců připravíme v P2. Struktura této sekce už tady zůstane.</p>
      </section>
      <section class="panel ov-slot">
        <h3>Poslední aktivita</h3>
        <p class="muted">Přehled posledních zápisů, fotografií a dokumentů připravíme v P2.</p>
      </section>
      <section class="panel ov-slot" style="grid-column:1 / -1">
        <h3>Archivník hlásí</h3>
        <p class="muted">Brandová karta z denních dat přijde ve vizuálním P2. Teď tu zůstává místo, aby se stránka později nepřestavovala.</p>
      </section>
    </div>
  `;
}

async function renderCustomers() {
  cache.customers = await api('/customers/?stav=aktivni');
  cache.types = await api('/object-types/');
  const el = $('#tab-customers');
  el.innerHTML = `
    <div class="workspace">
      <div class="panel list-panel">
        <div class="toolbar">
          <h2>Zákazníci</h2>
          <button type="button" class="btn-gold" id="btn-new-customer">+ Nový zákazník</button>
        </div>
        ${cache.customers.map((c) => `
          <button type="button" class="list-item ${c.uuid === selectedCustomer ? 'active' : ''}" data-open-customer="${c.uuid}">
            <span>${esc(c.display_name)}</span>
            <span class="muted">${c.objekty_pocet || 0} obj.</span>
          </button>`).join('') || '<p class="muted">Zatím nikdo.</p>'}
      </div>
      <div id="customer-workspace" class="panel">${selectedObject || selectedCustomer ? '' : '<p class="muted">Vyberte zákazníka, nebo založte nového.</p>'}</div>
    </div>
  `;
  el.querySelector('#btn-new-customer').addEventListener('click', showNewCustomerForm);
  bindNav(el);
  if (selectedObject) await openObject(selectedObject, { skipList: true });
  else if (selectedCustomer) await openCustomer(selectedCustomer, { skipList: true });
}

function showNewCustomerForm() {
  openModal('Nový zákazník', `
    <form id="form-customer" class="form-grid">
      <input name="jmeno" placeholder="Jméno">
      <input name="prijmeni" placeholder="Příjmení / název" required>
      <input name="telefon" placeholder="Telefon">
      <input name="email" type="email" placeholder="E-mail">
      <input name="adresa" placeholder="Adresa">
      <textarea name="poznamka" placeholder="Interní poznámka"></textarea>
      <button class="btn-primary" type="submit">Uložit</button>
    </form>
  `, (body) => {
    body.querySelector('#form-customer').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        const created = await api('/customers/', {
          method: 'POST',
          body: JSON.stringify(Object.fromEntries(new FormData(ev.target))),
        });
        closeModal();
        selectedCustomer = created.uuid;
        selectedObject = null;
        await renderCustomers();
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

async function openCustomer(uuid, opts = {}) {
  selectedCustomer = uuid;
  selectedObject = null;
  setTab('customers');
  if (!opts.skipList && !$('#customer-workspace')) {
    await renderCustomers();
    return;
  }
  const box = $('#customer-workspace');
  if (!box) {
    await renderCustomers();
    return;
  }
  markActive('#tab-customers .list-item', uuid);
  const [c, objects, entries, reminders] = await Promise.all([
    api(`/customers/${uuid}/`),
    api(`/objects/?zakaznik=${uuid}`),
    api(`/entries/?zakaznik=${uuid}&vcetne_objektu=1`),
    api(`/reminders/?stav=aktivni&zakaznik=${uuid}`),
  ]);
  cache.objects = objects;
  await ensureTypes();
  box.innerHTML = `
    <div class="card-head">
      <div>
        <h2>${esc(c.display_name)}</h2>
        <p class="meta muted">${esc(c.telefon || '—')} · ${esc(c.email || '—')}${c.adresa ? ' · ' + esc(c.adresa) : ''}</p>
        ${c.poznamka ? `<p>${esc(c.poznamka)}</p>` : ''}
        <div class="chips">${(c.tagy || []).map((t) => `<span class="chip">${esc(t.nazev)}</span>`).join('')}<span class="chip">${esc(stavLabel(c.stav))}</span></div>
      </div>
    </div>
    <div class="actions">
      <button type="button" class="btn-gold" data-act="entry">+ Nový zápis</button>
      <button type="button" class="btn-small" data-act="reminder">+ Připomínka</button>
      <button type="button" class="btn-small" data-act="object">+ Přidat objekt</button>
      <button type="button" class="btn-small" data-act="edit">Upravit</button>
    </div>
    <section class="section">
      <h3>Objekty</h3>
      <div class="obj-grid">
        ${objects.map((o) => `
          <button type="button" class="obj-card" data-open-object="${o.uuid}">
            <strong>${esc(o.nazev)}</strong>
            <span class="muted">${esc(o.typ_nazev)}</span>
            <span class="muted">${o.posledni_zapis ? 'poslední zápis ' + fmtDate(o.posledni_zapis) : 'zatím bez zápisu'}</span>
            <span class="muted">${o.zapisy_pocet || 0} zápisů · ${o.pripominky_aktivni || 0} připomínek · Otevřít →</span>
          </button>`).join('') || '<p class="muted">Žádný objekt. Přidejte první akcí výše.</p>'}
      </div>
    </section>
    <section class="section">
      <h3>Aktivní připomínky</h3>
      ${reminders.map(reminderRow).join('') || '<p class="muted">Nic nečeká.</p>'}
    </section>
    <section class="section">
      <h3>Historie</h3>
      <p class="muted">Zápisy zákazníka i všech jeho objektů. Zlato = zákazník, tyrkys = objekt.</p>
      <div class="timeline">${entries.map(timelineItem).join('') || '<p class="muted">Žádné zápisy.</p>'}</div>
    </section>
  `;
  bindNav(box);
  bindDone(box, () => openCustomer(uuid, { skipList: true }));
  box.querySelector('[data-act="entry"]').addEventListener('click', () => showEntryForm({ zakaznik: c, objects }));
  box.querySelector('[data-act="reminder"]').addEventListener('click', () => showReminderForm({ zakaznik: c, objects }));
  box.querySelector('[data-act="object"]').addEventListener('click', () => showObjectForm({ zakaznik: c }));
  box.querySelector('[data-act="edit"]').addEventListener('click', () => showEditCustomer(c));
}

async function openObject(uuid, opts = {}) {
  selectedObject = uuid;
  setTab(opts.fromObjects ? 'objects' : 'customers');
  const hostId = opts.fromObjects ? 'object-workspace' : 'customer-workspace';
  if (!opts.skipList && !$(`#${hostId}`)) {
    if (opts.fromObjects) await renderObjects();
    else await renderCustomers();
    return;
  }
  const obj = await api(`/objects/${uuid}/`);
  selectedCustomer = obj.zakaznik_uuid;
  await ensureTypes();
  const [entries, reminders] = await Promise.all([
    api(`/entries/?objekt=${uuid}`),
    api(`/reminders/?stav=aktivni&objekt=${uuid}`),
  ]);
  let box = $(`#${hostId}`);
  if (!box) {
    if (opts.fromObjects) await renderObjects();
    else await renderCustomers();
    return;
  }
  markActive('#tab-objects .list-item, #tab-objects .obj-card', uuid);
  const back = opts.fromObjects
    ? `<button type="button" class="linkish back" id="back-objects">← Objekty</button>`
    : `<button type="button" class="linkish back" data-open-customer="${obj.zakaznik_uuid}">← ${esc(obj.zakaznik_jmeno)}</button>`;
  box.innerHTML = `
    ${back}
    <div class="card-head">
      <div>
        <h2>${esc(obj.nazev)}</h2>
        <p class="meta muted">${esc(obj.typ_nazev)} · Majitel: <button type="button" class="linkish" data-open-customer="${obj.zakaznik_uuid}">${esc(obj.zakaznik_jmeno)}</button></p>
        ${obj.popis ? `<p>${esc(obj.popis)}</p>` : ''}
        <div class="chips">${(obj.tagy || []).map((t) => `<span class="chip">${esc(t.nazev)}</span>`).join('')}</div>
      </div>
    </div>
    <div class="actions">
      <button type="button" class="btn-gold" data-act="entry">+ Zápis</button>
      <button type="button" class="btn-small" data-act="reminder">+ Připomínka</button>
      <button type="button" class="btn-small" data-act="edit">Upravit</button>
    </div>
    <section class="section">
      <h3>Aktivní připomínky</h3>
      ${reminders.map(reminderRow).join('') || '<p class="muted">Nic nečeká.</p>'}
    </section>
    <section class="section">
      <h3>Historie objektu</h3>
      <p class="muted">Jen zápisy tohoto objektu.</p>
      <div class="timeline">${entries.map(timelineItem).join('') || '<p class="muted">Žádné zápisy.</p>'}</div>
    </section>
  `;
  bindNav(box);
  const backBtn = box.querySelector('#back-objects');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      selectedObject = null;
      renderObjects();
    });
  }
  bindDone(box, () => openObject(uuid, opts));
  box.querySelector('[data-act="entry"]').addEventListener('click', () => showEntryForm({ objekt: obj }));
  box.querySelector('[data-act="reminder"]').addEventListener('click', () => showReminderForm({ objekt: obj }));
  box.querySelector('[data-act="edit"]').addEventListener('click', () => showEditObject(obj));
}

function showEntryForm({ zakaznik, objekt, objects }) {
  const objectOptions = (objects || []).map((o) => `<option value="${o.uuid}">${esc(o.nazev)}</option>`).join('');
  openModal('Nový zápis', `
    <form id="form-entry" class="form-grid">
      ${objekt ? `<p class="muted">K objektu ${esc(objekt.nazev)}</p>` : `
        <select name="objekt_uuid">
          <option value="">Zápis k zákazníkovi</option>
          ${objectOptions}
        </select>`}
      <input name="nadpis" placeholder="Nadpis (volitelně)">
      <textarea name="text" placeholder="Text zápisu" required></textarea>
      <button class="btn-primary" type="submit">Uložit zápis</button>
    </form>
  `, (body) => {
    body.querySelector('#form-entry').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(ev.target));
      const payload = { text: fd.text, nadpis: fd.nadpis };
      if (objekt) payload.objekt_uuid = objekt.uuid;
      else if (fd.objekt_uuid) payload.objekt_uuid = fd.objekt_uuid;
      else payload.zakaznik_uuid = zakaznik.uuid;
      try {
        await api('/entries/', { method: 'POST', body: JSON.stringify(payload) });
        closeModal();
        if (objekt) await openObject(objekt.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
        else await openCustomer(zakaznik.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

function showReminderForm({ zakaznik, objekt, objects }) {
  const objectOptions = (objects || []).map((o) => `<option value="${o.uuid}">${esc(o.nazev)}</option>`).join('');
  openModal('Nová připomínka', `
    <form id="form-reminder" class="form-grid">
      <input name="termin" type="date" required>
      <input name="text" placeholder="Text připomínky" required>
      ${objekt ? '' : `<select name="objekt_uuid"><option value="">K zákazníkovi</option>${objectOptions}</select>`}
      <button class="btn-primary" type="submit">Uložit</button>
    </form>
  `, (body) => {
    body.querySelector('#form-reminder').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(ev.target));
      const payload = {
        termin: fd.termin,
        text: fd.text,
        zakaznik_uuid: objekt ? objekt.zakaznik_uuid : zakaznik.uuid,
      };
      if (objekt) payload.objekt_uuid = objekt.uuid;
      else if (fd.objekt_uuid) payload.objekt_uuid = fd.objekt_uuid;
      try {
        await api('/reminders/', { method: 'POST', body: JSON.stringify(payload) });
        closeModal();
        if (objekt) await openObject(objekt.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
        else await openCustomer(zakaznik.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

async function showObjectForm({ zakaznik }) {
  await ensureTypes();
  openModal('Nový objekt', `
    <form id="form-object" class="form-grid">
      <select name="typ_uuid" required>
        <option value="">Typ objektu</option>
        ${cache.types.filter((t) => t.aktivni).map((t) => `<option value="${t.uuid}">${esc(t.nazev)}</option>`).join('')}
      </select>
      <input name="nazev" placeholder="Název objektu" required>
      <textarea name="popis" placeholder="Popis"></textarea>
      <button class="btn-primary" type="submit">Uložit objekt</button>
    </form>
  `, (body) => {
    body.querySelector('#form-object').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(ev.target));
      try {
        const created = await api('/objects/', {
          method: 'POST',
          body: JSON.stringify({ ...fd, zakaznik_uuid: zakaznik.uuid }),
        });
        closeModal();
        await openObject(created.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

function showEditCustomer(c) {
  openModal('Upravit zákazníka', `
    <form id="form-edit-customer" class="form-grid">
      <input name="jmeno" value="${esc(c.jmeno)}" placeholder="Jméno">
      <input name="prijmeni" value="${esc(c.prijmeni)}" required>
      <input name="telefon" value="${esc(c.telefon)}" placeholder="Telefon">
      <input name="email" type="email" value="${esc(c.email)}" placeholder="E-mail">
      <input name="adresa" value="${esc(c.adresa)}" placeholder="Adresa">
      <textarea name="poznamka" placeholder="Interní poznámka">${esc(c.poznamka)}</textarea>
      <button class="btn-primary" type="submit">Uložit změny</button>
    </form>
  `, (body) => {
    body.querySelector('#form-edit-customer').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        await api(`/customers/${c.uuid}/`, {
          method: 'PATCH',
          body: JSON.stringify(Object.fromEntries(new FormData(ev.target))),
        });
        closeModal();
        await openCustomer(c.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

async function showEditObject(obj) {
  await ensureTypes();
  openModal('Upravit objekt', `
    <form id="form-edit-object" class="form-grid">
      <select name="typ_uuid">
        ${cache.types.map((t) => `<option value="${t.uuid}" ${t.uuid === obj.typ_uuid ? 'selected' : ''}>${esc(t.nazev)}</option>`).join('')}
      </select>
      <input name="nazev" value="${esc(obj.nazev)}" required>
      <textarea name="popis">${esc(obj.popis || '')}</textarea>
      <button class="btn-primary" type="submit">Uložit změny</button>
    </form>
  `, (body) => {
    body.querySelector('#form-edit-object').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        await api(`/objects/${obj.uuid}/`, {
          method: 'PATCH',
          body: JSON.stringify(Object.fromEntries(new FormData(ev.target))),
        });
        closeModal();
        await openObject(obj.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

async function renderObjects() {
  await ensureTypes();
  const objects = await api('/objects/');
  const el = $('#tab-objects');
  if (selectedObject) {
    el.innerHTML = '<div id="object-workspace" class="panel"></div>';
    await openObject(selectedObject, { skipList: true, fromObjects: true });
    return;
  }
  el.innerHTML = `
    <div class="panel">
      <div class="toolbar"><h2>Objekty</h2></div>
      <div class="obj-grid cols-2">
        ${objects.map((o) => `
          <button type="button" class="obj-card" data-open-object="${o.uuid}">
            <strong>${esc(o.nazev)}</strong>
            <span class="muted">${esc(o.typ_nazev)} · ${esc(o.zakaznik_jmeno)}</span>
            <span class="muted">${o.posledni_zapis ? 'poslední zápis ' + fmtDate(o.posledni_zapis) : 'zatím bez zápisu'}</span>
            <span class="muted">${o.zapisy_pocet || 0} zápisů · ${o.pripominky_aktivni || 0} připomínek · Otevřít →</span>
          </button>`).join('') || '<p class="muted">Zatím žádný objekt.</p>'}
      </div>
    </div>
  `;
  bindNav(el);
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
            <div class="muted">${fmtDate(r.termin)} · <button type="button" class="linkish" data-open-customer="${r.zakaznik_uuid}">${esc(r.zakaznik_jmeno)}</button>${r.objekt_uuid ? ' · <button type="button" class="linkish" data-open-object="' + r.objekt_uuid + '">' + esc(r.objekt_nazev) + '</button>' : ''}</div>
          </div>
          <button type="button" class="btn-small" data-done="${r.uuid}">Hotovo</button>
        </div>`).join('') || '<p class="muted">Nic nečeká.</p>'}
    </div>
  `;
  bindNav($('#tab-reminders'));
  bindDone($('#tab-reminders'), renderReminders);
}

async function renderSettings() {
  const [tags, types] = await Promise.all([api('/tags/'), api('/object-types/')]);
  cache.types = types;
  $('#tab-settings').innerHTML = `
    <div class="ov-grid">
      <div class="panel">
        <h2>Typy objektů</h2>
        ${types.map((t) => `<div class="row"><span>${esc(t.nazev)}</span><span class="muted">${t.aktivni ? 'aktivní' : 'vypnuto'}</span></div>`).join('') || '<p class="muted">Zatím žádný typ.</p>'}
        <form id="form-type" class="form-grid">
          <input name="nazev" placeholder="Např. Vozidlo, Nemovitost, Zvíře" required>
          <button class="btn-primary" type="submit">Přidat typ</button>
        </form>
      </div>
      <div class="panel">
        <h2>Štítky</h2>
        ${tags.map((t) => `<div class="row"><span>${esc(t.nazev)}</span><span class="muted">${esc(t.rozsah)}</span></div>`).join('') || '<p class="muted">Žádné štítky.</p>'}
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
    </div>
  `;
  $('#form-type').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    try {
      await api('/object-types/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(ev.target))) });
      await renderSettings();
    } catch (err) {
      alert(err.message);
    }
  });
  $('#form-tag').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    try {
      await api('/tags/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(ev.target))) });
      await renderSettings();
    } catch (err) {
      alert(err.message);
    }
  });
}

boot();
void PUBLIC_BASE_PATH;
