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
let cache = { customers: [], types: [], tags: [], objects: [], obory: [], presets: [] };

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

function fmtRelative(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 45) return 'právě teď';
  if (sec < 3600) return `před ${Math.max(1, Math.floor(sec / 60))} min`;
  if (sec < 86400) return `před ${Math.floor(sec / 3600)} h`;
  const days = Math.floor(sec / 86400);
  if (days === 1) return 'včera';
  if (days < 7) return `před ${days} dny`;
  return fmtDate(iso);
}

function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  const letters = ((parts[0] && parts[0][0]) || '') + ((parts[1] && parts[1][0]) || '');
  return (letters || '?').toUpperCase();
}

function fieldKindLabel(druh) {
  return ({
    text: 'Text',
    dlouhy_text: 'Dlouhý text',
    cislo: 'Číslo',
    datum: 'Datum',
    ano_ne: 'Ano / ne',
    vyber: 'Výběr',
  })[druh] || druh;
}

function emptyState(title, text) {
  return `<div class="empty-state"><strong>${esc(title)}</strong><p class="muted">${esc(text)}</p></div>`;
}

function noun(form) {
  const one = (me && me.objekt_jednotne) || 'Objekt';
  const many = (me && me.objekt_mnozne) || 'Objekty';
  return form === 'one' ? one : many;
}

function typePhrase() {
  const one = noun('one');
  return ({
    Zvíře: 'Typ zvířete',
    Vozidlo: 'Typ vozidla',
    Profil: 'Typ profilu',
    Objekt: 'Typ objektu',
  })[one] || `Typ: ${one}`;
}

function addObjectCta() {
  return `+ Přidat ${noun('one').toLowerCase()}`;
}

function objName(o) {
  return (o && (o.display_name || o.nazev || o.typ_nazev)) || '';
}

function applyTerms() {
  const tab = document.querySelector('[data-tab="objects"]');
  if (tab) tab.textContent = noun('many');
  const search = $('#search-q');
  if (search) {
    search.placeholder = `Hledat jméno, telefon, e-mail, ${noun('one').toLowerCase()}…`;
  }
}

function lockBadge(row) {
  if (!(row && (row.zamceno || row.zdroj_preset))) return '';
  return '<span class="lock-badge" title="Spravováno Archivníkem">🔒 Z presetu</span>';
}

const ACTIVITY_KIND = {
  zapis: 'Zápis',
  fotografie: 'Fotografie',
  dokument: 'Dokument',
  objekt: 'Objekt',
  pripominka: 'Připomínka',
};
const MASCOT_SRC = 'https://haklweb.b-cdn.net/modernik/logo_archivnik.webp';
let selectedTypeUuid = null;
let selectedOborUuid = null;

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

function assetSrc(uuid) {
  return `${API_PUBLIC_BASE_URL}/assets/${uuid}/content/?token=${encodeURIComponent(getToken())}`;
}

async function apiUpload(path, formData) {
  const headers = {};
  const token = getToken();
  if (token) headers['X-Archivnik-Token'] = token;
  const res = await fetch(`${API_PUBLIC_BASE_URL}${path}`, { method: 'POST', headers, body: formData });
  let data = null;
  try { data = await res.json(); } catch (_) { data = null; }
  if (res.status === 401 || res.status === 403) {
    setToken('');
    throw new Error(data?.detail || 'Přihlášení vypršelo.');
  }
  if (!res.ok) throw new Error(data?.detail || res.statusText || 'Chyba');
  return data;
}

let galleryItems = [];
let galleryIndex = 0;
let galleryCtx = { canCover: false, objectUuid: null, coverUuid: null, onChange: null };

function openGallery(items, start = 0, ctx = {}) {
  galleryItems = items || [];
  if (!galleryItems.length) return;
  galleryIndex = start;
  galleryCtx = {
    canCover: Boolean(ctx.canCover),
    objectUuid: ctx.objectUuid || null,
    coverUuid: ctx.coverUuid || null,
    onChange: ctx.onChange || null,
  };
  showGallery();
}

function showGallery() {
  const item = galleryItems[galleryIndex];
  if (!item) return;
  $('#lightbox-img').src = assetSrc(item.uuid);
  $('#lightbox-img').alt = item.nazev || '';
  const isCover = galleryCtx.coverUuid && galleryCtx.coverUuid === item.uuid;
  $('#lightbox-caption').textContent = isCover ? `${item.nazev || 'Fotografie'} · hlavní` : (item.nazev || '');
  $('#lightbox').classList.remove('hidden');
  const coverBtn = $('#lightbox-cover');
  coverBtn.classList.toggle('hidden', !galleryCtx.canCover);
  coverBtn.disabled = isCover;
  coverBtn.textContent = isCover ? 'Hlavní fotografie' : 'Nastavit jako hlavní';
}

function closeGallery() {
  $('#lightbox').classList.add('hidden');
  $('#lightbox-img').src = '';
}

async function confirmDeleteAsset(asset) {
  const msg = asset.zapis_uuid
    ? 'Tento soubor je zároveň přílohou zápisu. Smazáním zmizí z dokumentace i z historie — jde o jeden soubor, ne o kopii.\n\nOpravdu smazat?'
    : 'Opravdu smazat tento soubor?';
  if (!(await askConfirm(msg))) return false;
  await api(`/assets/${asset.uuid}/`, { method: 'DELETE' });
  return true;
}

function coverBlock(uuid, alt) {
  if (!uuid) return '<div class="cover-hero" aria-hidden="true"></div>';
  return `<button type="button" class="cover-open" data-gallery-cover>
    <img class="cover-hero" src="${assetSrc(uuid)}" alt="${esc(alt)}">
    <span class="cover-label">Hlavní fotografie</span>
  </button>`;
}

function photoGrid(photos, coverUuid) {
  if (!photos.length) return '';
  return `<div class="photo-grid">${photos.map((p, i) => `
    <button type="button" data-gallery="${i}">
      <span class="photo-wrap">
        <img class="photo-thumb" src="${assetSrc(p.uuid)}" alt="${esc(p.nazev)}">
        ${coverUuid && p.uuid === coverUuid ? '<span class="photo-badge">Hlavní</span>' : ''}
      </span>
    </button>`).join('')}</div>`;
}

function bindAssets(root, { photos, docs, coverUuid, objectUuid, onChange }) {
  root.querySelectorAll('[data-gallery]').forEach((btn) => {
    btn.addEventListener('click', () => openGallery(photos, Number(btn.dataset.gallery), {
      canCover: Boolean(objectUuid),
      objectUuid,
      coverUuid,
      onChange,
    }));
  });
  const coverOpen = root.querySelector('[data-gallery-cover]');
  if (coverOpen && photos.length) {
    const idx = photos.findIndex((p) => p.uuid === coverUuid);
    coverOpen.addEventListener('click', () => openGallery(photos, idx < 0 ? 0 : idx, {
      canCover: Boolean(objectUuid),
      objectUuid,
      coverUuid,
      onChange,
    }));
  }
  root.querySelectorAll('[data-del-asset]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const asset = (docs || []).find((d) => d.uuid === btn.dataset.delAsset);
      if (!asset) return;
      try {
        if (await confirmDeleteAsset(asset) && onChange) onChange();
      } catch (err) {
        window.alert(err.message || 'Soubor se nepodařilo smazat.');
      }
    });
  });
}

function docRows(docs) {
  if (!docs.length) return '';
  return docs.map((d) => `
    <div class="doc-row">
      <span class="doc-ico">${(d.content_type || '').includes('pdf') ? 'PDF' : 'SOUB'}</span>
      <div>
        <strong>${esc(d.nazev)}</strong>
        <div class="muted">${d.zapis_uuid ? 'příloha zápisu' : 'dokument karty'} · ${fmtDate(d.vytvoreno)}</div>
      </div>
      <div class="doc-actions">
        <a class="btn-small" href="${assetSrc(d.uuid)}" target="_blank" rel="noopener">Otevřít</a>
        <button type="button" class="btn-small" data-del-asset="${d.uuid}">Smazat</button>
      </div>
    </div>`).join('');
}

function fieldRows(fields) {
  if (!fields.length) return '';
  return `<div class="field-grid">${fields.map((f) => `
    <div class="field-row"><span class="muted">${esc(f.nazev)}</span><strong>${esc(formatField(f) || '—')}</strong></div>
  `).join('')}</div>`;
}

function wrapSection(id, title, inner) {
  if (!inner) return '';
  return `<section class="section"${id ? ` id="${id}"` : ''}><h3>${esc(title)}</h3>${inner}</section>`;
}

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function reminderTone(termin) {
  const day = String(termin || '').slice(0, 10);
  const today = todayIso();
  if (day && day < today) return 'overdue';
  if (day === today) return 'today';
  return 'later';
}

function reminderToneLabel(tone) {
  if (tone === 'overdue') return 'Po termínu';
  if (tone === 'today') return 'Dnes';
  return 'Nadcházející';
}

function formatField(f) {
  if (f.druh === 'ano_ne') {
    if (f.hodnota === 'ano') return 'Ano';
    if (f.hodnota === 'ne') return 'Ne';
  }
  if (f.druh === 'datum') return fmtDate(f.hodnota);
  return f.hodnota;
}

function attachHtml(files) {
  if (!files || !files.length) return '';
  return `<div class="attach-thumbs">${files.map((a) => (
    (a.content_type || '').startsWith('image/')
      ? `<img src="${assetSrc(a.uuid)}" alt="${esc(a.nazev)}">`
      : `<a href="${assetSrc(a.uuid)}" target="_blank" rel="noopener">PDF</a>`
  )).join('')}</div>`;
}

function showLogin(error) {
  $('#app-screen').classList.add('hidden');
  const onboard = $('#onboard-screen');
  if (onboard) onboard.classList.add('hidden');
  $('#login-screen').classList.remove('hidden');
  $('#login-error').textContent = error || '';
  $('#login-error').classList.toggle('hidden', !error);
}

function showApp() {
  $('#login-screen').classList.add('hidden');
  const onboard = $('#onboard-screen');
  if (onboard) onboard.classList.add('hidden');
  $('#app-screen').classList.remove('hidden');
  $('#sidebar-name').textContent = me.jmeno || me.email;
  $('#sidebar-salon').textContent = me.provozovna || '';
  applyTerms();
}

function showOnboard() {
  $('#login-screen').classList.add('hidden');
  $('#app-screen').classList.add('hidden');
  const onboard = $('#onboard-screen');
  if (onboard) onboard.classList.remove('hidden');
  renderOnboard();
}

function renderOnboard() {
  const box = $('#onboard-body');
  if (!box) return;
  box.innerHTML = `
    <h1>Jaký je váš obor?</h1>
    <p class="muted">Vyberte jednou. Typy a pole z předvyplnění půjde používat, ale později je nebude možné měnit. Vlastní typy si můžete přidat v Nastavení.</p>
    <div class="onboard-choices">
      <button type="button" class="onboard-choice" data-preset="vet">Veterinární ordinace</button>
      <button type="button" class="onboard-choice" data-preset="beauty">Kadeřnický &amp; beauty salon</button>
      <button type="button" class="onboard-choice" data-preset="pneu">Pneuservis</button>
      <button type="button" class="onboard-choice" data-preset="">Jiný / vlastní</button>
    </div>
    <form id="form-onboard-custom" class="form-grid hidden">
      <input name="nazev" value="Vlastní obor" required>
      <button class="btn-gold" type="submit">Založit vlastní obor</button>
    </form>
    <p id="onboard-error" class="error hidden"></p>
  `;
  const err = () => box.querySelector('#onboard-error');
  const showErr = (msg) => {
    err().textContent = msg || '';
    err().classList.toggle('hidden', !msg);
  };
  box.querySelectorAll('[data-preset]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const kod = btn.dataset.preset;
      if (!kod) {
        box.querySelector('#form-onboard-custom').classList.remove('hidden');
        return;
      }
      try {
        await api('/presets/apply/', { method: 'POST', body: JSON.stringify({ kod }) });
        me = await api('/me/');
        showApp();
        await openDeepLinkCustomer();
      } catch (e) {
        showErr(e.message);
      }
    });
  });
  box.querySelector('#form-onboard-custom').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const nazev = new FormData(ev.target).get('nazev');
    try {
      await api('/obory/', {
        method: 'POST',
        body: JSON.stringify({ nazev, objekt_jednotne: 'Objekt', objekt_mnozne: 'Objekty' }),
      });
      me = await api('/me/');
      showApp();
      await openDeepLinkCustomer();
    } catch (e) {
      showErr(e.message);
    }
  });
}

function pendingCustomerUuid() {
  try {
    const raw = (new URLSearchParams(window.location.search).get('zakaznik') || '').trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(raw)) return '';
    return raw;
  } catch (_) {
    return '';
  }
}

async function openDeepLinkCustomer() {
  const uuid = pendingCustomerUuid();
  if (!uuid) {
    currentTab = 'overview';
    await loadTab('overview');
    return;
  }
  try {
    await openCustomer(uuid);
  } catch (_) {
    currentTab = 'overview';
    await loadTab('overview');
  }
}

async function finishAuth(data) {
  if (data && data.token) setToken(data.token);
  if (data && data.jmeno) me = data;
  else me = await api('/me/');
  if (!me.onboarded) {
    showOnboard();
    return;
  }
  showApp();
  await openDeepLinkCustomer();
}

function hideSearch() {
  $('#search-results').classList.add('hidden');
}

async function ensureTypes() {
  cache.types = await api('/object-types/');
  return cache.types;
}

function typeOptionsHtml(types) {
  const groups = new Map();
  const loose = [];
  types.filter((t) => t.aktivni !== false).forEach((t) => {
    if (t.obor_uuid) {
      if (!groups.has(t.obor_uuid)) groups.set(t.obor_uuid, { nazev: t.obor_nazev, typy: [] });
      groups.get(t.obor_uuid).typy.push(t);
    } else loose.push(t);
  });
  const blocks = [];
  groups.forEach((g) => {
    blocks.push(`<optgroup label="${esc(g.nazev)}">${g.typy.map((t) => `<option value="${t.uuid}" data-vyzaduje-nazev="${t.vyzaduje_nazev === false ? '0' : '1'}">${esc(t.nazev)}</option>`).join('')}</optgroup>`);
  });
  if (loose.length) {
    blocks.push(`<optgroup label="Bez oboru">${loose.map((t) => `<option value="${t.uuid}">${esc(t.nazev)}</option>`).join('')}</optgroup>`);
  }
  return blocks.join('') || types.filter((t) => t.aktivni !== false).map((t) => `<option value="${t.uuid}">${esc(t.nazev)}</option>`).join('');
}

function typesForPrimaryObor(types, extraUuid) {
  const oborUuid = me && me.obor_uuid;
  return (types || []).filter((t) => {
    if (extraUuid && t.uuid === extraUuid) return true;
    if (t.aktivni === false) return false;
    if (!oborUuid) return !t.obor_uuid;
    return t.obor_uuid === oborUuid;
  });
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

let confirmWait = null;

function closeModal() {
  $('#modal').classList.add('hidden');
  $('#modal-body').innerHTML = '';
  if (confirmWait) {
    const done = confirmWait;
    confirmWait = null;
    done(false);
  }
}

function openModal(title, html, onReady) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = `<p id="modal-error" class="error hidden"></p>${html}`;
  $('#modal').classList.remove('hidden');
  if (onReady) onReady($('#modal-body'));
}

function askConfirm(message, okLabel = 'Smazat') {
  return new Promise((resolve) => {
    confirmWait = resolve;
    openModal('Potvrzení', `
      <p class="confirm-copy">${esc(message).replace(/\n/g, '<br>')}</p>
      <div class="actions confirm-actions">
        <button type="button" class="btn-small" id="confirm-no">Zpět</button>
        <button type="button" class="btn-danger" id="confirm-yes">${esc(okLabel)}</button>
      </div>
    `, (body) => {
      body.querySelector('#confirm-no').addEventListener('click', () => closeModal());
      body.querySelector('#confirm-yes').addEventListener('click', () => {
        const done = confirmWait;
        confirmWait = null;
        closeModal();
        if (done) done(true);
      });
    });
  });
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
  const host = $(`#tab-${tab}`);
  host.innerHTML = '<div class="panel empty-state"><p class="muted">Načítám…</p></div>';
  try {
    if (tab === 'overview') await renderOverview();
    if (tab === 'customers') await renderCustomers();
    if (tab === 'objects') await renderObjects();
    if (tab === 'reminders') await renderReminders();
    if (tab === 'settings') await renderSettings();
  } catch (err) {
    host.innerHTML = `<div class="panel empty-state"><p class="error">${esc(err.message || 'Nepodařilo se načíst data.')}</p></div>`;
  }
}

async function boot() {
  if (!getToken()) { showLogin(); return; }
  try {
    await finishAuth(await api('/me/'));
  } catch (err) {
    setToken('');
    showLogin(err.message);
  }
}

$('#login-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  try {
    await finishAuth(await api('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#login-email').value,
        password: $('#login-password').value,
      }),
    }));
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
$('#lightbox-close').addEventListener('click', closeGallery);
$('#lightbox').addEventListener('click', (ev) => {
  if (ev.target.id === 'lightbox') closeGallery();
});
$('#lightbox-prev').addEventListener('click', () => {
  if (!galleryItems.length) return;
  galleryIndex = (galleryIndex + galleryItems.length - 1) % galleryItems.length;
  showGallery();
});
$('#lightbox-next').addEventListener('click', () => {
  if (!galleryItems.length) return;
  galleryIndex = (galleryIndex + 1) % galleryItems.length;
  showGallery();
});
$('#lightbox-cover').addEventListener('click', async () => {
  const item = galleryItems[galleryIndex];
  if (!item || !galleryCtx.objectUuid) return;
  try {
    await api(`/objects/${galleryCtx.objectUuid}/cover/`, {
      method: 'POST',
      body: JSON.stringify({ asset_uuid: item.uuid }),
    });
    closeGallery();
    if (galleryCtx.onChange) galleryCtx.onChange();
  } catch (err) {
    window.alert(err.message || 'Hlavní fotografii se nepodařilo nastavit.');
  }
});
$('#lightbox-delete').addEventListener('click', async () => {
  const item = galleryItems[galleryIndex];
  if (!item) return;
  try {
    if (await confirmDeleteAsset(item)) {
      closeGallery();
      if (galleryCtx.onChange) galleryCtx.onChange();
    }
  } catch (err) {
    window.alert(err.message || 'Soubor se nepodařilo smazat.');
  }
});
document.addEventListener('keydown', (ev) => {
  if ($('#lightbox').classList.contains('hidden')) return;
  if (ev.key === 'Escape') closeGallery();
  if (ev.key === 'ArrowLeft') $('#lightbox-prev').click();
  if (ev.key === 'ArrowRight') $('#lightbox-next').click();
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
    <h3>${esc(noun('many'))}</h3>
    ${(data.objekty || []).map((o) => `<div class="row"><button type="button" class="linkish" data-open-object="${o.uuid}">${esc(objName(o))}</button><span class="muted">${esc(o.typ_nazev)} · ${esc(o.zakaznik_jmeno)}</span></div>`).join('') || '<p class="muted">Nic.</p>'}
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
  const tone = reminderTone(r.termin);
  return `<div class="reminder-card ${tone}">
    <div class="reminder-when">
      <span class="reminder-date">${fmtDate(r.termin)}</span>
      <span class="reminder-tone">${reminderToneLabel(tone)}</span>
    </div>
    <div class="reminder-body">
      <strong>${esc(r.text)}</strong>
      <div class="reminder-who">
        <button type="button" class="linkish" data-open-customer="${r.zakaznik_uuid}">${esc(r.zakaznik_jmeno)}</button>
        ${r.objekt_uuid ? `<span class="muted">·</span><button type="button" class="linkish" data-open-object="${r.objekt_uuid}">${esc(r.objekt_nazev)}</button>` : ''}
      </div>
    </div>
    <button type="button" class="btn-gold" data-done="${r.uuid}">Hotovo</button>
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
    <div class="timeline-when">${fmtDate(e.nastalo)} · ${esc(who || 'Zákazník')}${e.typ_zapisu ? ' · ' + esc(e.typ_zapisu) : ''}</div>
    <strong>${esc(e.nadpis || e.typ_zapisu || 'Zápis')}</strong>
    <div>${esc(e.text)}</div>
    ${attachHtml(e.prilohy)}
    ${e.autor ? `<div class="muted">${esc(e.autor)}</div>` : ''}
  </article>`;
}

function objCardHtml(o, extra) {
  return `<button type="button" class="obj-card" data-open-object="${o.uuid}">
    ${o.cover_uuid
      ? `<img class="cover-thumb" src="${assetSrc(o.cover_uuid)}" alt="">`
      : `<div class="cover-thumb avatar-fallback">${esc(initials(objName(o)))}</div>`}
    <span class="obj-card-copy">
      <strong>${esc(objName(o))}</strong>
      <span class="obj-card-meta">${esc(o.typ_nazev)}${o.zakaznik_jmeno ? ' · ' + esc(o.zakaznik_jmeno) : extra ? ' · ' + esc(extra) : ''}</span>
      <span class="muted">${o.posledni_zapis ? 'Poslední zápis ' + fmtDate(o.posledni_zapis) : 'Bez zápisu'}</span>
      <span class="obj-card-stats">${o.zapisy_pocet || 0} zápisů · ${o.pripominky_aktivni || 0} připomínek</span>
    </span>
  </button>`;
}

async function renderOverview() {
  const data = await api('/overview/');
  const soon = data.nejblizsi_pripominky || [];
  const feed = data.posledni_aktivita || [];
  const months = data.aktivita || [];
  const maxVal = Math.max(1, ...months.flatMap((m) => [m.zakaznici || 0, m.zapisy || 0]));
  const hasActivity = months.some((m) => (m.zakaznici || 0) + (m.zapisy || 0) > 0);
  const hlaseni = data.hlaseni || [];
  $('#tab-overview').innerHTML = `
    <div class="hero-line">
      <h1>${greeting()}, ${esc(data.provozovna)}</h1>
    </div>
    <div class="kpis">
      <div class="kpi"><span class="muted">Zákazníci</span><strong>${data.zakaznici}</strong></div>
      <div class="kpi kpi-teal"><span class="muted">${esc(noun('many'))}</span><strong>${data.objekty}</strong></div>
      <div class="kpi kpi-gold"><span class="muted">Zápisy tento měsíc</span><strong>${data.zapisy_mesic}</strong></div>
      <div class="kpi"><span class="muted">Aktivní připomínky</span><strong>${data.pripominky_aktivni}</strong></div>
    </div>
    <div class="ov-lead">
      <section class="panel hlaseni">
        <img class="hlaseni-mascot" src="${MASCOT_SRC}" alt="Archivník" width="196" height="60">
        <div>
          <h3>Archivník hlásí</h3>
          <ul>${hlaseni.map((line) => `<li>${esc(line)}</li>`).join('')}</ul>
        </div>
      </section>
      <section class="panel chart-panel">
        <div class="panel-head">
          <h3>Aktivita za 6 měsíců</h3>
          <div class="chart-legend">
            <span><i class="dot gold"></i> Noví zákazníci</span>
            <span><i class="dot teal"></i> Zápisy</span>
          </div>
        </div>
        ${hasActivity ? `<div class="chart">
          ${months.map((m) => `
            <div class="chart-col" title="${esc(m.label)}: ${m.zakaznici} zákazníků, ${m.zapisy} zápisů">
              <div class="chart-bars">
                <span class="chart-bar gold" style="height:${Math.round(((m.zakaznici || 0) / maxVal) * 100)}%"></span>
                <span class="chart-bar teal" style="height:${Math.round(((m.zapisy || 0) / maxVal) * 100)}%"></span>
              </div>
              <span class="chart-label">${esc(m.label)}</span>
            </div>`).join('')}
        </div>` : emptyState('Zatím bez aktivity', 'Jakmile přibydou zákazníci a zápisy, tady uvidíte vývoj.')}
      </section>
    </div>
    <div class="ov-grid">
      <section class="panel">
        <h3>Co vás čeká</h3>
        ${soon.length ? soon.map(reminderRow).join('') : emptyState('Nic nečeká', 'Žádné aktivní připomínky.')}
      </section>
      <section class="panel">
        <h3>Poslední aktivita</h3>
        ${feed.length ? feed.map((row) => `
          <button type="button" class="feed-row" ${row.objekt_uuid ? `data-open-object="${row.objekt_uuid}"` : `data-open-customer="${row.zakaznik_uuid}"`}>
            <span class="feed-kind ${row.druh}">${esc(row.druh === 'objekt' ? noun('one') : (ACTIVITY_KIND[row.druh] || row.druh))}</span>
            <strong>${esc(row.titulek)}</strong>
            <span class="muted">${esc(row.subjekt)} · ${fmtRelative(row.cas)}</span>
          </button>`).join('') : emptyState('Ticho v archivu', 'Nové zápisy, fotografie a dokumenty se tu objeví chronologicky.')}
      </section>
    </div>
  `;
  bindNav($('#tab-overview'));
  bindDone($('#tab-overview'), renderOverview);
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
            <span class="list-person"><span class="avatar sm">${esc(initials(c.display_name))}</span>${esc(c.display_name)}</span>
            <span class="muted">${c.objekty_pocet || 0} obj.</span>
          </button>`).join('') || emptyState('Zatím nikdo', 'Přidejte prvního zákazníka. Objekty, zápisy i připomínky visí na jeho kartě.')}
      </div>
      <div id="customer-workspace" class="panel">${selectedObject || selectedCustomer ? '' : emptyState('Vyberte zákazníka', 'Nebo založte nového zlatým tlačítkem vlevo.')}</div>
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
  const [c, objects, entries, reminders, photos, docs] = await Promise.all([
    api(`/customers/${uuid}/`),
    api(`/objects/?zakaznik=${uuid}`),
    api(`/entries/?zakaznik=${uuid}&vcetne_objektu=1`),
    api(`/reminders/?stav=aktivni&zakaznik=${uuid}`),
    api(`/assets/?zakaznik=${uuid}&jen_zakaznik=1&druh=fotografie`),
    api(`/assets/?zakaznik=${uuid}&jen_zakaznik=1&druh=dokument`),
  ]);
  cache.objects = objects;
  await ensureTypes();
  box.innerHTML = `
    <div class="card-head">
      <div class="person">
        <span class="avatar lg">${esc(initials(c.display_name))}</span>
        <div>
          <h2>${esc(c.display_name)}</h2>
          <p class="meta muted">${esc(c.telefon || '—')} · ${esc(c.email || '—')}${c.adresa ? ' · ' + esc(c.adresa) : ''}</p>
          ${c.poznamka ? `<p>${esc(c.poznamka)}</p>` : ''}
          <div class="chips">${(c.tagy || []).map((t) => `<span class="chip">${esc(t.nazev)}</span>`).join('')}<span class="chip">${esc(stavLabel(c.stav))}</span></div>
        </div>
      </div>
    </div>
    <div class="actions">
      <button type="button" class="btn-gold cta-main" data-act="object">${esc(addObjectCta())}</button>
      <button type="button" class="btn-small" data-act="entry">+ Nový zápis</button>
      <button type="button" class="btn-small" data-act="reminder">+ Připomínka</button>
      <button type="button" class="btn-small" data-act="photo">+ Fotografie</button>
      <button type="button" class="btn-small" data-act="doc">+ Dokument</button>
      <button type="button" class="btn-small" data-act="edit">Upravit</button>
    </div>
    <section class="section" id="c-objekty">
      <h3>${esc(noun('many'))}</h3>
      <div class="obj-grid">${objects.map((o) => objCardHtml(o)).join('') || emptyState(`Žádné ${noun('one').toLowerCase()}`, `Přidejte první ${noun('one').toLowerCase()}.`)}</div>
    </section>
    ${wrapSection('c-foto', 'Fotografie', photoGrid(photos))}
    ${wrapSection('c-docs', 'Dokumenty', docRows(docs))}
    ${wrapSection('c-remind', 'Připomínky', reminders.length ? reminders.map(reminderRow).join('') : '')}
    ${wrapSection('c-hist', 'Historie', entries.length ? `<div class="timeline">${entries.map(timelineItem).join('')}</div>` : '')}
  `;
  bindNav(box);
  bindDone(box, () => openCustomer(uuid, { skipList: true }));
  bindAssets(box, {
    photos,
    docs,
    onChange: () => openCustomer(uuid, { skipList: true }),
  });
  box.querySelector('[data-act="entry"]').addEventListener('click', () => showEntryForm({ zakaznik: c, objects }));
  box.querySelector('[data-act="reminder"]').addEventListener('click', () => showReminderForm({ zakaznik: c, objects }));
  box.querySelector('[data-act="photo"]').addEventListener('click', () => showAssetForm({ zakaznik: c, druh: 'fotografie' }));
  box.querySelector('[data-act="doc"]').addEventListener('click', () => showAssetForm({ zakaznik: c, druh: 'dokument' }));
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
  const [entries, reminders, fields, photos, docs] = await Promise.all([
    api(`/entries/?objekt=${uuid}`),
    api(`/reminders/?stav=aktivni&objekt=${uuid}`),
    api(`/objects/${uuid}/fields/`),
    api(`/assets/?objekt=${uuid}&druh=fotografie`),
    api(`/assets/?objekt=${uuid}&druh=dokument`),
  ]);
  let box = $(`#${hostId}`);
  if (!box) {
    if (opts.fromObjects) await renderObjects();
    else await renderCustomers();
    return;
  }
  markActive('#tab-objects .list-item, #tab-objects .obj-card', uuid);
  const back = opts.fromObjects
    ? `<button type="button" class="linkish back" id="back-objects">← ${esc(noun('many'))}</button>`
    : `<button type="button" class="linkish back" data-open-customer="${obj.zakaznik_uuid}">← ${esc(obj.zakaznik_jmeno)}</button>`;
  const fieldsHtml = fieldRows(fields);
  const photosHtml = photoGrid(photos, obj.cover_uuid);
  const docsHtml = docRows(docs);
  const remindersHtml = reminders.length ? reminders.map(reminderRow).join('') : '';
  const historyHtml = entries.length ? `<div class="timeline">${entries.map(timelineItem).join('')}</div>` : '';
  const nav = [
    fieldsHtml && ['o-udaje', 'Údaje'],
    photosHtml && ['o-foto', 'Fotografie'],
    docsHtml && ['o-docs', 'Dokumenty'],
    remindersHtml && ['o-remind', 'Připomínky'],
    historyHtml && ['o-hist', 'Historie'],
  ].filter(Boolean);
  box.innerHTML = `
    ${back}
    <div class="card-hero">
      ${coverBlock(obj.cover_uuid || (photos[0] && photos[0].uuid), objName(obj))}
      <div>
        <h2>${esc(objName(obj))}</h2>
        <p class="meta muted">${esc(obj.typ_nazev)} · <button type="button" class="linkish" data-open-customer="${obj.zakaznik_uuid}">${esc(obj.zakaznik_jmeno)}</button></p>
        ${obj.popis ? `<p>${esc(obj.popis)}</p>` : ''}
        <p class="meta muted">${photos.length} fotografií · ${docs.length} dokumentů · ${entries.length} zápisů · ${reminders.length} připomínek</p>
        <div class="chips">${(obj.tagy || []).map((t) => `<span class="chip">${esc(t.nazev)}</span>`).join('')}</div>
      </div>
    </div>
    <div class="actions">
      <button type="button" class="btn-gold" data-act="entry">+ Zápis</button>
      <button type="button" class="btn-small" data-act="reminder">+ Připomínka</button>
      <button type="button" class="btn-small" data-act="photo">+ Fotografie</button>
      <button type="button" class="btn-small" data-act="doc">+ Dokument</button>
      <button type="button" class="btn-small" data-act="fields">Upravit údaje</button>
      <button type="button" class="btn-small" data-act="edit">Upravit</button>
    </div>
    ${nav.length > 1 ? `<nav class="section-nav">${nav.map(([id, label]) => `<a href="#${id}">${label}</a>`).join('')}</nav>` : ''}
    ${wrapSection('o-udaje', 'Údaje', fieldsHtml)}
    ${wrapSection('o-foto', 'Fotografie', photosHtml)}
    ${wrapSection('o-docs', 'Dokumenty', docsHtml)}
    ${wrapSection('o-remind', 'Připomínky', remindersHtml)}
    ${wrapSection('o-hist', 'Historie', historyHtml)}
  `;
  bindNav(box);
  const backBtn = box.querySelector('#back-objects');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      selectedObject = null;
      renderObjects();
    });
  }
  bindAssets(box, {
    photos,
    docs,
    coverUuid: obj.cover_uuid,
    objectUuid: obj.uuid,
    onChange: () => openObject(uuid, opts),
  });
  bindDone(box, () => openObject(uuid, opts));
  box.querySelector('[data-act="entry"]').addEventListener('click', () => showEntryForm({ objekt: obj }));
  box.querySelector('[data-act="reminder"]').addEventListener('click', () => showReminderForm({ objekt: obj }));
  box.querySelector('[data-act="photo"]').addEventListener('click', () => showAssetForm({ objekt: obj, druh: 'fotografie' }));
  box.querySelector('[data-act="doc"]').addEventListener('click', () => showAssetForm({ objekt: obj, druh: 'dokument' }));
  box.querySelector('[data-act="fields"]').addEventListener('click', () => showFieldsForm(obj, fields));
  box.querySelector('[data-act="edit"]').addEventListener('click', () => showEditObject(obj));
}

function showEntryForm({ zakaznik, objekt, objects }) {
  const objectOptions = (objects || []).map((o) => `<option value="${o.uuid}">${esc(objName(o))}</option>`).join('');
  openModal('Nový zápis', `
    <form id="form-entry" class="form-grid">
      ${objekt ? `<p class="muted">K ${esc(noun('one').toLowerCase())} ${esc(objName(objekt))}</p>` : `
        <select name="objekt_uuid">
          <option value="">Zápis k zákazníkovi</option>
          ${objectOptions}
        </select>`}
      <input name="typ_zapisu" placeholder="Typ zápisu (např. Vyšetření)" value="Poznámka">
      <input name="nadpis" placeholder="Nadpis (volitelně)">
      <textarea name="text" placeholder="Text zápisu" required></textarea>
      <label>Přílohy
        <input name="prilohy" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,image/*,application/pdf">
      </label>
      <button class="btn-primary" type="submit">Uložit zápis</button>
    </form>
  `, (body) => {
    body.querySelector('#form-entry').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const form = ev.target;
      const fd = Object.fromEntries(new FormData(form));
      const payload = { text: fd.text, nadpis: fd.nadpis, typ_zapisu: fd.typ_zapisu || 'Poznámka' };
      if (objekt) payload.objekt_uuid = objekt.uuid;
      else if (fd.objekt_uuid) payload.objekt_uuid = fd.objekt_uuid;
      else payload.zakaznik_uuid = zakaznik.uuid;
      try {
        const created = await api('/entries/', { method: 'POST', body: JSON.stringify(payload) });
        const files = form.querySelector('[name=prilohy]').files || [];
        for (const file of files) {
          const up = new FormData();
          up.append('soubor', file);
          up.append('zapis_uuid', created.uuid);
          up.append('nazev', file.name);
          up.append('druh', file.type.startsWith('image/') ? 'fotografie' : 'dokument');
          await apiUpload('/assets/', up);
        }
        closeModal();
        if (objekt) await openObject(objekt.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
        else await openCustomer(zakaznik.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

function showAssetForm({ zakaznik, objekt, druh }) {
  const title = druh === 'fotografie' ? 'Nová fotografie' : 'Nový dokument';
  const accept = druh === 'fotografie' ? 'image/jpeg,image/png,image/webp,image/gif' : '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png';
  openModal(title, `
    <form id="form-asset" class="form-grid">
      <input name="nazev" placeholder="Název souboru (volitelně)">
      <input name="soubor" type="file" required accept="${accept}">
      <button class="btn-primary" type="submit">Nahrát</button>
    </form>
  `, (body) => {
    body.querySelector('#form-asset').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const form = ev.target;
      const file = form.soubor.files[0];
      const up = new FormData();
      up.append('soubor', file);
      up.append('druh', druh);
      up.append('nazev', form.nazev.value.trim() || file.name);
      if (objekt) up.append('objekt_uuid', objekt.uuid);
      else up.append('zakaznik_uuid', zakaznik.uuid);
      try {
        await apiUpload('/assets/', up);
        closeModal();
        if (objekt) await openObject(objekt.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
        else await openCustomer(zakaznik.uuid, { skipList: true });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

function showFieldsForm(obj, fields) {
  if (!fields.length) {
    openModal('Vlastní údaje', '<p class="muted">Nejdřív v Nastavení přidejte pole k tomuto typu objektu.</p>');
    return;
  }
  openModal('Vlastní údaje', `
    <form id="form-fields" class="form-grid">
      ${fields.map((f) => {
        if (f.druh === 'ano_ne') {
          return `<label>${esc(f.nazev)}
            <select name="${f.pole_uuid}">
              <option value="">—</option>
              <option value="ano" ${f.hodnota === 'ano' ? 'selected' : ''}>Ano</option>
              <option value="ne" ${f.hodnota === 'ne' ? 'selected' : ''}>Ne</option>
            </select>
          </label>`;
        }
        if (f.druh === 'vyber') {
          const opts = (f.volby || []).map((opt) => `<option value="${esc(opt)}" ${f.hodnota === opt ? 'selected' : ''}>${esc(opt)}</option>`).join('');
          return `<label>${esc(f.nazev)}
            <select name="${f.pole_uuid}">
              <option value="">—</option>
              ${opts}
            </select>
          </label>`;
        }
        if (f.druh === 'dlouhy_text') {
          return `<label>${esc(f.nazev)}<textarea name="${f.pole_uuid}" rows="4">${esc(f.hodnota || '')}</textarea></label>`;
        }
        const type = f.druh === 'datum' ? 'date' : (f.druh === 'cislo' ? 'number' : 'text');
        return `<label>${esc(f.nazev)}<input name="${f.pole_uuid}" type="${type}" value="${esc(f.hodnota || '')}"></label>`;
      }).join('')}
      <button class="btn-primary" type="submit">Uložit údaje</button>
    </form>
  `, (body) => {
    body.querySelector('#form-fields').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(ev.target));
      const hodnoty = Object.entries(fd).map(([pole_uuid, hodnota]) => ({ pole_uuid, hodnota }));
      try {
        await api(`/objects/${obj.uuid}/fields/`, { method: 'PUT', body: JSON.stringify({ hodnoty }) });
        closeModal();
        await openObject(obj.uuid, { skipList: true, fromObjects: currentTab === 'objects' });
      } catch (err) {
        showModalError(err.message);
      }
    });
  });
}

function showReminderForm({ zakaznik, objekt, objects }) {
  const objectOptions = (objects || []).map((o) => `<option value="${o.uuid}">${esc(objName(o))}</option>`).join('');
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
  openModal(addObjectCta(), `
    <form id="form-object" class="form-grid">
      <select name="typ_uuid" required>
        <option value="">${esc(typePhrase())}</option>
        ${typeOptionsHtml(typesForPrimaryObor(cache.types))}
      </select>
      <input name="nazev" placeholder="Název (volitelně podle typu)" required>
      <textarea name="popis" placeholder="Popis"></textarea>
      <button class="btn-gold" type="submit">Uložit</button>
    </form>
  `, (body) => {
    const form = body.querySelector('#form-object');
    const typSel = form.querySelector('[name=typ_uuid]');
    const nazev = form.querySelector('[name=nazev]');
    const syncName = () => {
      const opt = typSel.selectedOptions[0];
      const need = !opt || opt.dataset.vyzadujeNazev !== '0';
      nazev.required = need;
      nazev.placeholder = need ? `Název ${noun('one').toLowerCase()}` : `Název (nemusíte vyplňovat — použije se ${esc((opt && opt.textContent) || 'typ')})`;
    };
    typSel.addEventListener('change', syncName);
    syncName();
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(form));
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
  openModal(`Upravit ${noun('one').toLowerCase()}`, `
    <form id="form-edit-object" class="form-grid">
      <select name="typ_uuid">
        ${typesForPrimaryObor(cache.types, obj.typ_uuid).map((t) => `<option value="${t.uuid}" data-vyzaduje-nazev="${t.vyzaduje_nazev === false ? '0' : '1'}" ${t.uuid === obj.typ_uuid ? 'selected' : ''}>${esc(t.nazev)}</option>`).join('')}
      </select>
      <input name="nazev" value="${esc(obj.nazev || '')}" ${obj.vyzaduje_nazev === false ? '' : 'required'}>
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
      <div class="toolbar"><h2>${esc(noun('many'))}</h2></div>
      <div class="obj-grid">
        ${objects.map((o) => objCardHtml(o)).join('') || emptyState(`Zatím žádné ${noun('one').toLowerCase()}`, `${noun('one')} založíte na kartě zákazníka.`)}
      </div>
    </div>
  `;
  bindNav(el);
}

async function renderReminders() {
  const data = await api('/reminders/?stav=aktivni');
  $('#tab-reminders').innerHTML = `
    <div class="panel">
      <div class="toolbar"><h2>Aktivní připomínky</h2></div>
      ${data.length ? data.map(reminderRow).join('') : emptyState('Nic nečeká', 'Připomínku přidáte na kartě zákazníka nebo objektu.')}
    </div>
  `;
  bindNav($('#tab-reminders'));
  bindDone($('#tab-reminders'), renderReminders);
}

async function renderSettings() {
  const [tags, types, obory, presets] = await Promise.all([
    api('/tags/'),
    api('/object-types/'),
    api('/obory/'),
    api('/presets/'),
  ]);
  cache.types = types;
  cache.obory = obory;
  cache.presets = presets;
  const bezOboru = types.filter((t) => !t.obor_uuid);
  if (!selectedOborUuid || (selectedOborUuid !== 'bez' && !obory.some((o) => o.uuid === selectedOborUuid))) {
    selectedOborUuid = obory[0] ? obory[0].uuid : (bezOboru.length ? 'bez' : null);
  }
  const typePool = selectedOborUuid === 'bez'
    ? bezOboru
    : types.filter((t) => t.obor_uuid === selectedOborUuid);
  if (!selectedTypeUuid || !typePool.some((t) => t.uuid === selectedTypeUuid)) {
    selectedTypeUuid = typePool[0] ? typePool[0].uuid : null;
  }
  const selectedObor = obory.find((o) => o.uuid === selectedOborUuid) || null;
  const selected = types.find((t) => t.uuid === selectedTypeUuid) || null;
  $('#tab-settings').innerHTML = `
    <div class="settings-intro">
      <h2>Nastavení kartotéky</h2>
      <p class="muted">Typy z předvyplnění jsou zamčené. Můžete přidat vlastní ${typePhrase().toLowerCase()} a k němu vlastní pole. Mazání struktury zatím není v provozovně k dispozici.</p>
    </div>
    <div class="settings-grid">
      <div class="panel">
        <h2>Co eviduji</h2>
        ${obory.map((o) => `
          <button type="button" class="list-item ${o.uuid === selectedOborUuid ? 'active' : ''}" data-select-obor="${o.uuid}">
            <span>${esc(o.nazev)} ${o.zdroj_preset ? lockBadge({ zdroj_preset: o.zdroj_preset }) : ''}</span>
            <span class="muted">${o.typy_pocet} typů</span>
          </button>`).join('')}
        ${bezOboru.length ? `
          <button type="button" class="list-item ${selectedOborUuid === 'bez' ? 'active' : ''}" data-select-obor="bez">
            <span>Bez oboru</span>
            <span class="muted">${bezOboru.length} typů</span>
          </button>` : ''}
        ${!obory.length && !bezOboru.length ? emptyState('Zatím nic', 'Obor se volí při prvním spuštění.') : ''}
        <form id="form-obor" class="form-grid settings-add">
          <input name="nazev" placeholder="Další vlastní obor" required>
          <button class="btn-gold" type="submit">Vlastní obor</button>
        </form>
      </div>
      <div class="panel">
        <h2>${esc(typePhrase())}</h2>
        <p class="muted">${selectedObor ? esc(selectedObor.nazev) : (selectedOborUuid === 'bez' ? 'Typy bez oboru' : 'Nejdřív vyberte obor.')}</p>
        ${typePool.map((t) => `
          <button type="button" class="list-item ${t.uuid === selectedTypeUuid ? 'active' : ''}" data-select-type="${t.uuid}">
            <span>${esc(t.nazev)} ${lockBadge(t)}</span>
            <span class="muted">${(t.pole || []).length} údajů</span>
          </button>`).join('') || emptyState('Žádný typ', selectedObor ? `Přidejte ${typePhrase().toLowerCase()} do tohoto oboru.` : 'Vyberte nebo založte obor.')}
        ${selectedObor ? `
          <form id="form-type" class="form-grid settings-add">
            <input name="nazev" placeholder="Nový vlastní typ" required>
            <label class="check-row"><input type="checkbox" name="vyzaduje_nazev" checked> Vyžadovat název</label>
            <button class="btn-gold" type="submit">Přidat typ</button>
          </form>
        ` : ''}
      </div>
      <div class="panel">
        ${selected ? `
          <h2>${esc(selected.nazev)} ${lockBadge(selected)}</h2>
          <p class="muted">${selected.zamceno ? 'Spravováno Archivníkem — definici tohoto typu nelze měnit. Vlastní pole přidat můžete.' : 'Jaké informace chci u tohoto typu evidovat'}</p>
          ${(selected.pole || []).length
            ? selected.pole.map((p) => `<div class="row"><span>${esc(p.nazev)} ${lockBadge(p)}</span><span class="muted">${esc(fieldKindLabel(p.druh))}</span></div>`).join('')
            : emptyState('Žádné údaje', 'Přidejte pole. Při založení objektu zůstanou volitelná.')}
          <form class="form-grid form-field settings-add" data-typ="${selected.uuid}">
            <input name="nazev" placeholder="Název vlastního pole" required>
            <select name="druh" data-field-kind>
              <option value="text">Text</option>
              <option value="dlouhy_text">Dlouhý text</option>
              <option value="cislo">Číslo</option>
              <option value="datum">Datum</option>
              <option value="ano_ne">Ano / ne</option>
              <option value="vyber">Výběr</option>
            </select>
            <textarea name="volby" class="hidden" data-field-volby rows="4" placeholder="Možnosti, každá na nový řádek (např. Samec / Samice / Neurčeno)"></textarea>
            <button class="btn-gold" type="submit">Přidat pole</button>
          </form>
        ` : emptyState('Nejdřív typ', `Vlevo zvolte ${typePhrase().toLowerCase()}, potom k němu přidejte údaje.`)}
      </div>
      <div class="panel settings-tags">
        <h2>Štítky</h2>
        ${tags.map((t) => `<div class="row"><span>${esc(t.nazev)}</span><span class="muted">${esc(t.rozsah)}</span></div>`).join('') || emptyState('Žádné štítky', 'Štítky pomáhají filtrovat zákazníky i objekty.')}
        <form id="form-tag" class="form-grid settings-add">
          <input name="nazev" placeholder="Název štítku" required>
          <select name="rozsah">
            <option value="obe">Zákazník i objekt</option>
            <option value="zakaznik">Jen zákazník</option>
            <option value="objekt">Jen objekt</option>
          </select>
          <button class="btn-gold" type="submit">Přidat</button>
        </form>
      </div>
    </div>
  `;
  $$('[data-select-obor]').forEach((btn) => {
    btn.addEventListener('click', () => {
      selectedOborUuid = btn.dataset.selectObor;
      selectedTypeUuid = null;
      renderSettings();
    });
  });
  $$('[data-select-type]').forEach((btn) => {
    btn.addEventListener('click', () => {
      selectedTypeUuid = btn.dataset.selectType;
      renderSettings();
    });
  });
  const oborForm = $('#form-obor');
  if (oborForm) {
    oborForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        const created = await api('/obory/', {
          method: 'POST',
          body: JSON.stringify(Object.fromEntries(new FormData(ev.target))),
        });
        selectedOborUuid = created.uuid;
        selectedTypeUuid = null;
        await renderSettings();
      } catch (err) {
        window.alert(err.message);
      }
    });
  }
  const presetForm = $('#form-preset');
  if (presetForm) {
    presetForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const kod = new FormData(ev.target).get('kod');
      try {
        const applied = await api('/presets/apply/', {
          method: 'POST',
          body: JSON.stringify({ kod }),
        });
        selectedOborUuid = applied.uuid;
        selectedTypeUuid = null;
        cache.types = [];
        await renderSettings();
      } catch (err) {
        window.alert(err.message);
      }
    });
  }
  const typeForm = $('#form-type');
  if (typeForm) {
    typeForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        const fd = Object.fromEntries(new FormData(ev.target));
        const created = await api('/object-types/', {
          method: 'POST',
          body: JSON.stringify({
            nazev: fd.nazev,
            obor_uuid: selectedOborUuid,
            vyzaduje_nazev: Boolean(fd.vyzaduje_nazev),
          }),
        });
        selectedTypeUuid = created.uuid;
        cache.types = [];
        await renderSettings();
      } catch (err) {
        window.alert(err.message);
      }
    });
  }
  const tagForm = $('#form-tag');
  if (tagForm) {
    tagForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        await api('/tags/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(ev.target))) });
        await renderSettings();
      } catch (err) {
        window.alert(err.message);
      }
    });
  }
  $$('[data-field-kind]').forEach((sel) => {
    const box = sel.closest('form').querySelector('[data-field-volby]');
    const sync = () => box.classList.toggle('hidden', sel.value !== 'vyber');
    sel.addEventListener('change', sync);
    sync();
  });
  $$('.form-field').forEach((form) => {
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = Object.fromEntries(new FormData(form));
      const volby = String(fd.volby || '').split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      try {
        await api('/fields/', {
          method: 'POST',
          body: JSON.stringify({
            nazev: fd.nazev,
            druh: fd.druh,
            volby: fd.druh === 'vyber' ? volby : [],
            typ_uuid: form.dataset.typ,
          }),
        });
        await renderSettings();
      } catch (err) {
        window.alert(err.message);
      }
    });
  });
}

boot();
void PUBLIC_BASE_PATH;
