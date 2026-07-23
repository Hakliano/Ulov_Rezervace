const host = location.hostname;
const isLocal = host === 'localhost' || host === '127.0.0.1';
const API_BASE = isLocal ? `http://${host}:8000/api` : 'https://api.ulovklienty.cz/api';
const SALON_ID = 14;
const STAFF_WEB_TOKEN_KEY = `staff_token_web_${SALON_ID}`;
const STAFF_WEB_USER_KEY = `staff_user_web_${SALON_ID}`;

let salonData = null;
let staffToken = sessionStorage.getItem(STAFF_WEB_TOKEN_KEY) || '';
let staffUser = null;
try {
  staffUser = JSON.parse(sessionStorage.getItem(STAFF_WEB_USER_KEY) || 'null');
} catch {
  staffUser = null;
}
let bunnyConfigured = false;

function isMajitel() {
  return staffUser?.je_majitel === true;
}

function staffHeaders(extra = {}) {
  const headers = { ...extra };
  if (staffToken) headers['X-Staff-Token'] = staffToken;
  return headers;
}

async function fetchPersonel() {
  const res = await fetch(`${API_BASE}/salon/${SALON_ID}/personel/`);
  if (!res.ok) throw new Error('Nepodařilo se načíst personál.');
  return res.json();
}

async function apiRezervace(path, opts = {}) {
  const headers = staffHeaders({ 'Content-Type': 'application/json', ...(opts.headers || {}) });
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
  if (!res.ok) throw new Error(data?.detail || 'Chyba API');
  return data;
}

let personelAdminData = [];

function renderPersonelPublic(list) {
  const grid = document.getElementById('personel-list');
  const section = grid?.closest('section');
  if (!list.length) {
    grid.innerHTML = '';
    section?.classList.add('hidden');
    return;
  }
  section?.classList.remove('hidden');
  grid.innerHTML = list.map((p, i) => {
    const hours = (p.rozvrh || []).map((r) => {
      const cas = r.volno ? '<span class="zavreno">Volno</span>' : `${formatTime(r.od)} – ${formatTime(r.do)}`;
      return `<tr><td>${esc(r.den_nazev)}</td><td>${cas}</td></tr>`;
    }).join('');
    return `<article class="team-card" style="--i:${i}">
      <div class="team-photo">${p.fotka
        ? `<img src="${esc(p.fotka)}" alt="${esc(p.jmeno)}" loading="lazy">`
        : '<div class="team-photo-placeholder" aria-hidden="true"></div>'}</div>
      <div class="team-body">
        <h3>${esc(p.jmeno)}</h3>
        ${p.specializace ? `<p class="team-role">${esc(p.specializace)}</p>` : ''}
        ${p.popis ? `<p class="team-desc">${esc(p.popis)}</p>` : ''}
        <table class="team-hours"><tbody>${hours}</tbody></table>
      </div>
    </article>`;
  }).join('');
}

function personelRozvrhRows(rozvrh) {
  return (rozvrh || []).map((r) => `
    <tr data-den="${r.den}">
      <td>${esc(r.den_nazev)}</td>
      <td><input type="time" class="p-roz-od" value="${formatTime(r.od)}" ${r.volno ? 'disabled' : ''}></td>
      <td><input type="time" class="p-roz-do" value="${formatTime(r.do)}" ${r.volno ? 'disabled' : ''}></td>
      <td><input type="checkbox" class="p-roz-volno" ${r.volno ? 'checked' : ''}></td>
    </tr>
  `).join('');
}

function personelEditCard(z) {
  const id = z.id || '';
  return `<div class="personel-edit-card" data-id="${id}">
    <div class="personel-edit-head">
      <strong>${esc(z.jmeno || 'Nový člen týmu')}</strong>
      <label class="checkbox"><input type="checkbox" class="p-web" ${z.zobrazit_na_webu !== false ? 'checked' : ''}> Na webu</label>
    </div>
    <label>Jméno<input type="text" class="p-jmeno" value="${esc(z.jmeno)}"></label>
    <label>Specializace (krátký text)<input type="text" class="p-spec" value="${esc(z.specializace || '')}"></label>
    <label>Popis<textarea class="p-popis" rows="3">${esc(z.popis || '')}</textarea></label>
    <div class="p-foto-preview">${z.fotka ? `<img src="${esc(z.fotka)}" alt="">` : '<span class="placeholder">Bez fotky</span>'}</div>
    <label class="btn btn-secondary btn-upload btn-sm">Nahrát fotku<input type="file" class="p-foto-upload" accept="image/*" hidden></label>
    <p class="admin-hint">Pracovní doba určuje dostupnost v rezervacích i otevírací dobu salonu na webu (součet všech zaměstnanců).</p>
    <table class="rozvrh-table admin-rozvrh">
      <thead><tr><th>Den</th><th>Od</th><th>Do</th><th>Volno</th></tr></thead>
      <tbody>${personelRozvrhRows(z.rozvrh)}</tbody>
    </table>
    <div class="personel-edit-actions">
      <button type="button" class="btn btn-primary btn-sm btn-save-personel">Uložit</button>
      ${id && z.role !== 'majitel' && z.aktivni !== false ? '<button type="button" class="btn btn-secondary btn-sm btn-del-personel">Deaktivovat účet</button>' : ''}
    </div>
    ${id && z.aktivni === false ? '<p class="admin-hint error">Účet deaktivován — zaměstnanec se nemůže přihlásit. Obnovte zaškrtnutím „Aktivní“ v rezervacích → Pracovníci.</p>' : ''}
  </div>`;
}

function collectPersonelRozvrh(card) {
  return [...card.querySelectorAll('tbody tr[data-den]')].map((row) => {
    const volno = row.querySelector('.p-roz-volno').checked;
    const od = row.querySelector('.p-roz-od').value;
    const do_ = row.querySelector('.p-roz-do').value;
    return {
      den: parseInt(row.dataset.den, 10),
      volno,
      od: volno ? null : (od || null),
      do: volno ? null : (do_ || null),
    };
  });
}

async function loadPersonelAdmin() {
  const data = await apiRezervace(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/`);
  personelAdminData = (data.zamestnanci || []).filter((z) => z.role !== 'majitel');
  renderPersonelAdminEdit();
}

function renderPersonelAdminEdit() {
  const el = document.getElementById('personel-edit');
  el.innerHTML = personelAdminData.map((z) => personelEditCard(z)).join('');
  bindPersonelEditEvents(el);
}

function bindPersonelEditEvents(root) {
  root.querySelectorAll('.p-roz-volno').forEach((cb) => {
    cb.addEventListener('change', () => {
      const row = cb.closest('tr');
      row.querySelector('.p-roz-od').disabled = cb.checked;
      row.querySelector('.p-roz-do').disabled = cb.checked;
    });
  });
  root.querySelectorAll('.btn-save-personel').forEach((btn) => {
    btn.addEventListener('click', () => savePersonelCard(btn.closest('.personel-edit-card')));
  });
  root.querySelectorAll('.btn-del-personel').forEach((btn) => {
    btn.addEventListener('click', () => deletePersonelCard(btn.closest('.personel-edit-card')));
  });
  root.querySelectorAll('.p-foto-upload').forEach((inp) => {
    inp.addEventListener('change', (e) => uploadPersonelPhoto(e, inp.closest('.personel-edit-card')));
  });
}

async function savePersonelCard(card) {
  const msg = document.getElementById('status-msg');
  const payload = {
    jmeno: card.querySelector('.p-jmeno').value.trim(),
    specializace: card.querySelector('.p-spec').value.trim(),
    popis: card.querySelector('.p-popis').value.trim(),
    zobrazit_na_webu: card.querySelector('.p-web').checked,
    aktivni: true,
    rozvrh: collectPersonelRozvrh(card),
  };
  if (!payload.jmeno) {
    msg.textContent = 'Jméno je povinné.';
    msg.className = 'status-msg error';
    return;
  }
  msg.textContent = 'Ukládám personál…';
  msg.className = 'status-msg';
  try {
    const id = card.dataset.id;
    if (id) {
      await apiRezervace(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${id}/`, {
        method: 'PUT', body: JSON.stringify(payload),
      });
    } else {
      await apiRezervace(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/`, {
        method: 'POST', body: JSON.stringify(payload),
      });
    }
    await loadPersonelAdmin();
    renderPersonelPublic(await fetchPersonel());
    await refreshOteviraciDoba();
    msg.textContent = 'Personál uložen.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function deletePersonelCard(card) {
  const id = card.dataset.id;
  if (!id || !confirm('Deaktivovat účet tohoto člena týmu?\n\nÚčet se nesmaže — zůstane historie a audit. Zaměstnanec se už nepřihlásí.')) return;
  await apiRezervace(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${id}/deaktivovat/`, { method: 'POST' });
  await loadPersonelAdmin();
  renderPersonelPublic(await fetchPersonel());
  await refreshOteviraciDoba();
}

async function uploadPersonelPhoto(e, card) {
  const file = e.target.files[0];
  const id = card.dataset.id;
  if (!file || !id) {
    alert('Nejdříve uložte člena týmu, pak nahrajte fotku.');
    e.target.value = '';
    return;
  }
  const msg = document.getElementById('status-msg');
  const form = new FormData();
  form.append('file', file);
  form.append('typ', 'personel');
  form.append('zamestnanec_id', id);
  msg.textContent = 'Nahrávám fotku…';
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/upload/`, {
      method: 'POST',
      headers: staffHeaders(),
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Nahrání selhalo');
    card.querySelector('.p-foto-preview').innerHTML = `<img src="${esc(data.url)}" alt="">`;
    await loadPersonelAdmin();
    renderPersonelPublic(await fetchPersonel());
    await refreshOteviraciDoba();
    msg.textContent = 'Fotka nahrána.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function fetchSalon() {
  const res = await fetch(`${API_BASE}/salon/${SALON_ID}/`);
  if (!res.ok) throw new Error('Nepodařilo se načíst data salonu.');
  return res.json();
}

async function fetchBunnyStatus() {
  try {
    const res = await fetch(`${API_BASE}/bunny/status/`);
    const data = await res.json();
    bunnyConfigured = data.configured;
    return data;
  } catch {
    return { configured: false };
  }
}

function formatTime(t) {
  if (!t) return '';
  return t.slice(0, 5);
}

function formatDate(d) {
  if (!d) return '';
  const [y, m, day] = d.split('-');
  return `${day}.${m}.${y}`;
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function renderOteviraciDoba(list) {
  const tbody = document.querySelector('#oteviraci-doba tbody');
  if (!tbody) return;
  tbody.innerHTML = (list || []).map(d => {
    const cas = d.zavreno
      ? '<span class="zavreno">Zavřeno</span>'
      : `${formatTime(d.od)} – ${formatTime(d.do)}`;
    return `<tr><td>${d.den_nazev}</td><td>${cas}</td></tr>`;
  }).join('');
}

async function refreshOteviraciDoba() {
  salonData = await fetchSalon();
  renderOteviraciDoba(salonData.oteviraci_doba);
}



function applySalonBanner(data) {
  const el = document.getElementById('site-banner');
  if (!el) return;
  const text = (data.banner_text || '').trim();
  const enabled = !!data.banner_enabled;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const od = data.banner_od ? new Date(`${data.banner_od}T00:00:00`) : null;
  const doDate = data.banner_do ? new Date(`${data.banner_do}T00:00:00`) : null;
  const inRange = (!od || today >= od) && (!doDate || today <= doDate);
  if (enabled && text && inRange) {
    el.textContent = text;
    el.classList.remove('hidden');
  } else {
    el.textContent = '';
    el.classList.add('hidden');
  }
}

function applySalonBrand(data) {
  const root = document.documentElement;
  if (data.primary_color) {
    root.style.setProperty('--bg', data.primary_color);
    root.style.setProperty('--surface', data.primary_color);
  }
  if (data.accent_color) {
    root.style.setProperty('--gold', data.accent_color);
    root.style.setProperty('--accent', data.accent_color);
  }

  let icon = document.querySelector('link[data-salon-favicon]');
  if (data.favicon_url) {
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      icon.setAttribute('data-salon-favicon', '1');
      document.head.appendChild(icon);
    }
    icon.href = data.favicon_url;
  } else if (icon) {
    icon.remove();
  }

  const nav = document.getElementById('nav-logo');
  if (!nav) return;
  if (data.logo_url) {
    nav.innerHTML = `<img class="nav-logo-img" src="${esc(data.logo_url)}" alt="${esc(data.name || 'Logo')}">`;
  } else {
    const fallback = nav.dataset.fallbackText || data.name || '';
    nav.textContent = fallback;
  }
}

function renderBrandPreview(elId, url, emptyText) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = url
    ? `<img src="${esc(url)}" alt="">`
    : `<span class="placeholder">${emptyText}</span>`;
}

function syncColorInputs(kind, hex) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl) return;
  const value = /^#[0-9A-Fa-f]{6}$/.test(hex || '') ? hex : colorEl.value;
  colorEl.value = value;
  hexEl.value = value.toUpperCase();
}

function wireColorPair(kind) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl || colorEl.dataset.wired) return;
  colorEl.dataset.wired = '1';
  colorEl.addEventListener('input', () => {
    hexEl.value = colorEl.value.toUpperCase();
  });
  hexEl.addEventListener('change', () => {
    let v = (hexEl.value || '').trim();
    if (v && !v.startsWith('#')) v = `#${v}`;
    if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
      colorEl.value = v;
      hexEl.value = v.toUpperCase();
    } else {
      hexEl.value = colorEl.value.toUpperCase();
    }
  });
}

async function handleBrandUpload(e, typ) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = await uploadImage(file, typ);
    if (typ === 'logo') {
      salonData.logo_url = data.url;
      renderBrandPreview('logo-preview', data.url, 'Žádné logo');
    } else {
      salonData.favicon_url = data.url;
      renderBrandPreview('favicon-preview', data.url, 'Žádný favicon');
    }
    renderSalon(salonData);
    const msg = document.getElementById('status-msg');
    msg.textContent = typ === 'logo' ? 'Logo nahráno.' : 'Favicon nahrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    const msg = document.getElementById('status-msg');
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function clearBrandAsset(field) {
  if (!staffToken || !isMajitel()) return;
  const msg = document.getElementById('status-msg');
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/`, {
      method: 'PUT',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ [field]: '' }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || JSON.stringify(err));
    }
    salonData = await fetchSalon();
    renderSalon(salonData);
    showEditForm();
    msg.textContent = field === 'logo_url' ? 'Logo odebráno.' : 'Favicon odebrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

function renderSalon(data) {
  document.title = data.name;
  document.getElementById('salon-name').textContent = data.name;
  const _nav = document.getElementById('nav-logo');
  if (_nav) _nav.dataset.fallbackText = data.name;
  applySalonBrand(data);
  document.getElementById('footer-name').textContent = data.name;
  document.getElementById('salon-desc').textContent = data.description;
  document.getElementById('about-text').textContent = data.description;
  document.getElementById('salon-address').textContent = data.address;

  const phoneEl = document.getElementById('salon-phone');
  phoneEl.textContent = data.phone;
  phoneEl.href = `tel:${data.phone.replace(/\s/g, '')}`;

  const emailEl = document.getElementById('salon-email');
  emailEl.textContent = data.email;
  emailEl.href = `mailto:${data.email}`;

  const heroBg = document.getElementById('hero-bg');
  if (data.hero_image) {
    heroBg.style.backgroundImage = `url('${data.hero_image}')`;
    heroBg.classList.add('has-image');
  } else {
    heroBg.style.backgroundImage = '';
    heroBg.classList.remove('has-image');
  }

  const gallery = document.getElementById('gallery');
  const gallerySection = gallery?.closest('section');
  const obrazky = data.obrazky || [];
  if (obrazky.length) {
    gallery.innerHTML = obrazky.map(o =>
      `<figure class="gallery-item" data-url="${esc(o.url)}">
        <img src="${esc(o.url)}" alt="${esc(o.popis)}" loading="lazy">
        ${o.popis ? `<figcaption>${esc(o.popis)}</figcaption>` : ''}
      </figure>`
    ).join('');
    gallerySection?.classList.remove('hidden');
    gallery.querySelectorAll('.gallery-item').forEach(el => {
      el.addEventListener('click', () => openLightbox(el.dataset.url));
    });
  } else {
    gallery.innerHTML = '';
    gallerySection?.classList.add('hidden');
  }

  document.getElementById('cenik-list').innerHTML = data.cenik.map(item =>
    `<div class="price-card ${item.obrazek ? 'price-card-has-image' : ''}">
      ${item.obrazek ? `<figure class="price-media"><img src="${esc(item.obrazek)}" alt="${esc(item.nazev)}" loading="lazy"></figure>` : ''}
      <div class="price-copy">
        <span class="price-name">${esc(item.nazev)}</span>
        <span class="price-value">${item.cena} Kč</span>
      </div>
    </div>`
  ).join('');

  document.getElementById('novinky-list').innerHTML = data.novinky.map(n =>
    `<article class="news-card">
      <div class="news-card-body">
        <time>${formatDate(n.datum)}</time>
        <h3>${esc(n.nadpis)}</h3>
        <p>${esc(n.text)}</p>
      </div>
      ${n.obrazek ? `<figure class="news-card-media"><img src="${esc(n.obrazek)}" alt="${esc(n.nadpis)}" loading="lazy"></figure>` : ''}
    </article>`
  ).join('');

  renderOteviraciDoba(data.oteviraci_doba);

  document.getElementById('loading').classList.add('hidden');
  document.getElementById('content').classList.remove('hidden');
}

function openLightbox(url) {
  document.getElementById('lightbox-img').src = url;
  document.getElementById('lightbox').classList.remove('hidden');
}

function closeLightbox() {
  document.getElementById('lightbox').classList.add('hidden');
}

async function verifyStaffSession() {
  if (!staffToken) return false;
  try {
    const data = await apiRezervace(`/salon/${SALON_ID}/rezervace/staff/me/`);
    staffUser = data;
    sessionStorage.setItem(STAFF_WEB_USER_KEY, JSON.stringify(staffUser));
    return isMajitel();
  } catch {
    staffToken = '';
    staffUser = null;
    sessionStorage.removeItem(STAFF_WEB_TOKEN_KEY);
    sessionStorage.removeItem(STAFF_WEB_USER_KEY);
    return false;
  }
}

async function openAdmin() {
  document.getElementById('admin-panel').classList.add('open');
  const ok = await verifyStaffSession();
  if (ok) {
    try {
      salonData = await fetchSalon();
      renderSalon(salonData);
      showEditForm();
    } catch (err) {
      console.error(err);
      document.getElementById('login-section').classList.remove('hidden');
      document.getElementById('edit-section').classList.add('hidden');
    }
  } else {
    setWebAdminAuthUi(false);
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('edit-section').classList.add('hidden');
  }
}

async function closeAdmin() {
  document.getElementById('admin-panel').classList.remove('open');
  const msg = document.getElementById('status-msg');
  const loginMsg = document.getElementById('login-status-msg');
  msg.textContent = '';
  msg.className = 'status-msg';
  if (loginMsg) {
    loginMsg.textContent = '';
    loginMsg.className = 'status-msg';
  }
  document.getElementById('login-section').classList.remove('hidden');
  document.getElementById('edit-section').classList.add('hidden');
  setWebAdminAuthUi(false);
  if (staffToken && isMajitel()) {
    try {
      salonData = await fetchSalon();
      renderSalon(salonData);
    } catch (err) {
      console.error(err);
    }
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const login = document.getElementById('staff-login').value.trim();
  const password = document.getElementById('staff-password').value;
  const msg = document.getElementById('login-status-msg');
  msg.textContent = 'Ověřuji…';
  msg.className = 'status-msg';

  try {
    const data = await apiRezervace(`/salon/${SALON_ID}/rezervace/staff/prihlaseni/`, {
      method: 'POST',
      body: JSON.stringify({ prihlasovaci_jmeno: login, password }),
    });
    if (!data.staff?.je_majitel) {
      msg.textContent = 'Úprava webu je dostupná jen pro majitelku salonu.';
      msg.className = 'status-msg error';
      return;
    }
    staffToken = data.token;
    staffUser = data.staff;
    sessionStorage.setItem(STAFF_WEB_TOKEN_KEY, staffToken);
    sessionStorage.setItem(STAFF_WEB_USER_KEY, JSON.stringify(staffUser));
    document.getElementById('login-section').classList.add('hidden');
    showEditForm();
    msg.textContent = '';
  } catch (err) {
    msg.textContent = err.message || 'Nesprávné přihlašovací jméno nebo heslo.';
    msg.className = 'status-msg error';
    console.error(err);
  }
}

function setWebAdminAuthUi(loggedIn) {
  const logoutBtn = document.getElementById('btn-web-logout');
  if (logoutBtn) logoutBtn.classList.toggle('hidden', !loggedIn);
}

async function handleWebAdminLogout() {
  if (staffToken) {
    try {
      await apiRezervace(`/salon/${SALON_ID}/rezervace/staff/odhlaseni/`, { method: 'POST' });
    } catch {
      /* token už mohl být neplatný */
    }
  }
  staffToken = '';
  staffUser = null;
  sessionStorage.removeItem(STAFF_WEB_TOKEN_KEY);
  sessionStorage.removeItem(STAFF_WEB_USER_KEY);
  setWebAdminAuthUi(false);
  document.getElementById('login-section').classList.remove('hidden');
  document.getElementById('edit-section').classList.add('hidden');
  document.getElementById('login-form')?.reset();
}

function showEditForm() {
  setWebAdminAuthUi(true);
  document.getElementById('login-section').classList.add('hidden');
  document.getElementById('edit-section').classList.remove('hidden');
  const d = salonData;

  document.getElementById('edit-name').value = d.name;
  document.getElementById('edit-desc').value = d.description;
  document.getElementById('edit-address').value = d.address;
  document.getElementById('edit-phone').value = d.phone;
  document.getElementById('edit-email').value = d.email;

  syncColorInputs('primary', d.primary_color || '#080808');
  syncColorInputs('accent', d.accent_color || '#c9a962');
  renderBrandPreview('logo-preview', d.logo_url, 'Žádné logo');
  renderBrandPreview('favicon-preview', d.favicon_url, 'Žádný favicon');

  const bannerEnabled = document.getElementById('edit-banner-enabled');
  const bannerText = document.getElementById('edit-banner-text');
  const bannerOd = document.getElementById('edit-banner-od');
  const bannerDo = document.getElementById('edit-banner-do');
  if (bannerEnabled) bannerEnabled.checked = !!d.banner_enabled;
  if (bannerText) bannerText.value = d.banner_text || '';
  if (bannerOd) bannerOd.value = d.banner_od || '';
  if (bannerDo) bannerDo.value = d.banner_do || '';

  renderHeroPreview(d.hero_image);
  renderGalleryEdit(d.obrazky || []);

  const hint = document.getElementById('bunny-hint');
  hint.textContent = bunnyConfigured
    ? 'Obrázky se nahrávají na Bunny.net CDN.'
    : '⚠ Bunny.net není nastaven – vyplňte backend/.env (viz README).';

  const cenikEdit = document.getElementById('cenik-edit');
  cenikEdit.innerHTML = d.cenik.map(item => cenikEditRow(item)).join('');
  document.getElementById('btn-add-cenik').onclick = () => {
    cenikEdit.insertAdjacentHTML('beforeend', cenikEditRow({ nazev: '', cena: 0, obrazek: '' }));
  };

  const novinkyEdit = document.getElementById('novinky-edit');
  novinkyEdit.innerHTML = d.novinky.map(n => novinkaEditRow(n)).join('');
  document.getElementById('btn-add-novinka').onclick = () => {
    novinkyEdit.insertAdjacentHTML('beforeend', novinkaEditRow({ nadpis: '', text: '', obrazek: '' }));
  };

  if (staffToken && isMajitel()) loadPersonelAdmin().catch(console.error);
}

function renderHeroPreview(url) {
  const el = document.getElementById('hero-preview');
  el.innerHTML = url
    ? `<img src="${esc(url)}" alt="Hero">`
    : '<span class="placeholder">Žádná fotka</span>';
}

function renderGalleryEdit(obrazky) {
  const el = document.getElementById('gallery-edit');
  el.innerHTML = obrazky.map(o =>
    `<div class="gallery-edit-item" data-id="${o.id}" data-url="${esc(o.url)}">
      <img src="${esc(o.url)}" alt="">
      <input type="text" class="obrazek-popis" value="${esc(o.popis)}" placeholder="Popis">
      <button type="button" class="btn-delete-img" data-id="${o.id}">Smazat</button>
    </div>`
  ).join('');
  el.querySelectorAll('.btn-delete-img').forEach(btn => {
    btn.addEventListener('click', () => deleteImage(parseInt(btn.dataset.id, 10)));
  });
}

async function uploadImage(file, typ) {
  const msg = document.getElementById('status-msg');
  const form = new FormData();
  form.append('file', file);
  form.append('typ', typ);

  msg.textContent = 'Nahrávám…';
  msg.className = 'status-msg';

  const res = await fetch(`${API_BASE}/salon/${SALON_ID}/upload/?typ=${typ}`, {
    method: 'POST',
    headers: staffHeaders(),
    body: form,
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Nahrání selhalo');
  return data;
}

async function handleHeroUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = await uploadImage(file, 'hero');
    salonData.hero_image = data.url;
    renderSalon(salonData);
    renderHeroPreview(data.url);
    const msg = document.getElementById('status-msg');
    msg.textContent = 'Hero fotka nahrána.';
    msg.className = 'status-msg success';
  } catch (err) {
    const msg = document.getElementById('status-msg');
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function handleGalleryUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const novy = await uploadImage(file, 'galerie');
    salonData.obrazky = salonData.obrazky || [];
    salonData.obrazky.push(novy);
    renderSalon(salonData);
    renderGalleryEdit(salonData.obrazky);
    const msg = document.getElementById('status-msg');
    msg.textContent = 'Fotka přidána do galerie.';
    msg.className = 'status-msg success';
  } catch (err) {
    const msg = document.getElementById('status-msg');
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function deleteImage(imageId) {
  if (!confirm('Smazat tento obrázek?')) return;
  const msg = document.getElementById('status-msg');
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/obrazek/${imageId}/`, {
      method: 'DELETE',
      headers: staffHeaders(),
    });
    if (!res.ok) throw new Error('Smazání selhalo');
    salonData = await fetchSalon();
    renderSalon(salonData);
    renderGalleryEdit(salonData.obrazky || []);
    msg.textContent = 'Obrázek smazán.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

function cenikEditRow(item) {
  const url = item.obrazek || '';
  return `<div class="edit-block cenik-edit-item" data-id="${item.id || ''}" data-obrazek="${attrEsc(url)}">
    <div class="edit-row">
      <input type="text" class="cenik-nazev" value="${esc(item.nazev)}" placeholder="Služba">
      <input type="number" class="cenik-cena" value="${item.cena}" placeholder="Kč">
    </div>
    <div class="cenik-img-preview">${url ? `<img src="${esc(url)}" alt="">` : '<span class="placeholder">Bez obrázku</span>'}</div>
    <div class="cenik-img-actions">
      <label class="btn btn-secondary btn-sm btn-upload">Nahrát obrázek<input type="file" class="upload-cenik" accept="image/*" hidden></label>
      <button type="button" class="btn-remove-cenik-img btn-sm">Odebrat</button>
    </div>
  </div>`;
}

function renderCenikPreview(row, url) {
  const prev = row.querySelector('.cenik-img-preview');
  if (!prev) return;
  prev.innerHTML = url
    ? `<img src="${esc(url)}" alt="">`
    : '<span class="placeholder">Bez obrázku</span>';
}

function refreshCenikEdit() {
  if (document.getElementById('edit-section').classList.contains('hidden')) return;
  const cenikEdit = document.getElementById('cenik-edit');
  cenikEdit.innerHTML = (salonData.cenik || []).map(item => cenikEditRow(item)).join('');
  document.getElementById('btn-add-cenik').onclick = () => {
    cenikEdit.insertAdjacentHTML('beforeend', cenikEditRow({ nazev: '', cena: 0, obrazek: '' }));
  };
}

async function handleCenikUpload(e) {
  const input = e.target;
  const file = input.files[0];
  if (!file) return;
  const row = input.closest('.cenik-edit-item');
  const msg = document.getElementById('status-msg');
  if (!row.dataset.id) {
    msg.textContent = 'Nejdřív uložte službu, pak nahrajte obrázek.';
    msg.className = 'status-msg error';
    input.value = '';
    return;
  }
  const form = new FormData();
  form.append('file', file);
  msg.textContent = 'Nahrávám obrázek služby…';
  msg.className = 'status-msg';
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/upload/?typ=cenik&cenik_id=${row.dataset.id}`, {
      method: 'POST',
      headers: staffHeaders(),
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Nahrání selhalo');
    salonData = await fetchSalon();
    renderSalon(salonData);
    refreshCenikEdit();
    if (typeof renderDelkyEdit === 'function') renderDelkyEdit();
    msg.textContent = 'Obrázek služby nahrán a uložen.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  input.value = '';
}

function removeCenikImage(btn) {
  const row = btn.closest('.cenik-edit-item');
  row.dataset.obrazek = '';
  row.dataset.obrazekRemoved = 'true';
  renderCenikPreview(row, '');
  if (row.dataset.id && salonData.cenik) {
    const item = salonData.cenik.find(x => x.id === parseInt(row.dataset.id, 10));
    if (item) item.obrazek = '';
  }
}

function renderNovinkaPreview(row, url) {
  const prev = row.querySelector('.novinka-img-preview');
  if (!prev) return;
  prev.innerHTML = url
    ? `<img src="${esc(url)}" alt="">`
    : '<span class="placeholder">Bez obrázku</span>';
}

function refreshNovinkyEdit() {
  if (document.getElementById('edit-section').classList.contains('hidden')) return;
  const novinkyEdit = document.getElementById('novinky-edit');
  novinkyEdit.innerHTML = (salonData.novinky || []).map(n => novinkaEditRow(n)).join('');
  document.getElementById('btn-add-novinka').onclick = () => {
    novinkyEdit.insertAdjacentHTML('beforeend', novinkaEditRow({ nadpis: '', text: '', obrazek: '' }));
  };
}

function attrEsc(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

function novinkaEditRow(item) {
  const url = item.obrazek || '';
  return `<div class="edit-block novinka-edit-item" data-id="${item.id || ''}" data-obrazek="${attrEsc(url)}">
    <input type="text" class="novinka-nadpis" value="${esc(item.nadpis)}" placeholder="Nadpis">
    <textarea class="novinka-text" rows="2" placeholder="Text">${esc(item.text)}</textarea>
    <div class="novinka-img-preview">${url ? `<img src="${esc(url)}" alt="">` : '<span class="placeholder">Bez obrázku</span>'}</div>
    <div class="novinka-img-actions">
      <label class="btn btn-secondary btn-sm btn-upload">Nahrát obrázek<input type="file" class="upload-novinka" accept="image/*" hidden></label>
      <button type="button" class="btn-remove-novinka-img btn-sm">Odebrat</button>
    </div>
  </div>`;
}

async function handleNovinkaUpload(e) {
  const input = e.target;
  const file = input.files[0];
  if (!file) return;

  const row = input.closest('.novinka-edit-item');
  const msg = document.getElementById('status-msg');

  if (!row.dataset.id) {
    msg.textContent = 'Nejdřív uložte novinku (tlačítko „Uložit textová data“), pak nahrajte obrázek.';
    msg.className = 'status-msg error';
    input.value = '';
    return;
  }

  const form = new FormData();
  form.append('file', file);

  msg.textContent = 'Nahrávám obrázek novinky…';
  msg.className = 'status-msg';

  try {
    const res = await fetch(
      `${API_BASE}/salon/${SALON_ID}/upload/?typ=novinka&novinka_id=${row.dataset.id}`,
      {
        method: 'POST',
        headers: staffHeaders(),
        body: form,
      },
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Nahrání selhalo');

    salonData = await fetchSalon();
    renderSalon(salonData);
    refreshCenikEdit();
    refreshNovinkyEdit();
    msg.textContent = 'Obrázek novinky nahrán a uložen.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  input.value = '';
}

function removeNovinkaImage(btn) {
  const row = btn.closest('.novinka-edit-item');
  row.dataset.obrazek = '';
  row.dataset.obrazekRemoved = 'true';
  renderNovinkaPreview(row, '');
  if (row.dataset.id && salonData.novinky) {
    const n = salonData.novinky.find(x => x.id === parseInt(row.dataset.id, 10));
    if (n) n.obrazek = '';
  }
}

function collectFormData() {
  const cenik = [...document.querySelectorAll('#cenik-edit .cenik-edit-item')].map((el, i) => {
    const id = el.dataset.id;
    const item = {
      nazev: el.querySelector('.cenik-nazev').value,
      cena: parseInt(el.querySelector('.cenik-cena').value, 10) || 0,
      poradi: i,
    };
    if (id) item.id = parseInt(id, 10);
    if (el.dataset.obrazekRemoved === 'true') {
      item.obrazek = '';
    } else if (!id && el.dataset.obrazek) {
      item.obrazek = el.dataset.obrazek;
    }
    return item;
  });

  const novinky = [...document.querySelectorAll('#novinky-edit .novinka-edit-item')].map(el => {
    const id = el.dataset.id;
    const item = {
      nadpis: el.querySelector('.novinka-nadpis').value,
      text: el.querySelector('.novinka-text').value,
    };
    if (id) item.id = parseInt(id, 10);
    if (el.dataset.obrazekRemoved === 'true') {
      item.obrazek = '';
    } else if (!id && el.dataset.obrazek) {
      item.obrazek = el.dataset.obrazek;
    }
    return item;
  });

  const obrazky = [...document.querySelectorAll('#gallery-edit .gallery-edit-item')].map((el, i) => ({
    id: parseInt(el.dataset.id, 10),
    popis: el.querySelector('.obrazek-popis').value,
    poradi: i,
  }));

  return {
    name: document.getElementById('edit-name').value,
    description: document.getElementById('edit-desc').value,
    address: document.getElementById('edit-address').value,
    phone: document.getElementById('edit-phone').value,
    email: document.getElementById('edit-email').value,
    primary_color: document.getElementById('edit-primary-color')?.value || '',
    accent_color: document.getElementById('edit-accent-color')?.value || '',
    banner_enabled: !!document.getElementById('edit-banner-enabled')?.checked,
    banner_text: document.getElementById('edit-banner-text')?.value.trim() || '',
    banner_od: document.getElementById('edit-banner-od')?.value || null,
    banner_do: document.getElementById('edit-banner-do')?.value || null,
    cenik, novinky, obrazky,
  };
}

async function handleSave() {
  const msg = document.getElementById('status-msg');
  if (!staffToken || !isMajitel()) {
    msg.textContent = 'Pro uložení se přihlaste jako majitel salonu.';
    msg.className = 'status-msg error';
    return;
  }
  const payload = collectFormData();
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/`, {
      method: 'PUT',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || JSON.stringify(err));
    }
    salonData = await fetchSalon();
    renderSalon(salonData);
    refreshCenikEdit();
    refreshNovinkyEdit();
    msg.textContent = 'Změny uloženy.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = 'Chyba: ' + err.message;
    msg.className = 'status-msg error';
  }
}

document.querySelectorAll('.admin-tabs .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.admin-tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.add('active');
    if (tab.dataset.tab === 'email' && staffToken && isMajitel()) loadEmailSettings();
    if (tab.dataset.tab === 'personel' && staffToken && isMajitel()) loadPersonelAdmin();
  });
});

document.getElementById('btn-add-personel').addEventListener('click', () => {
  personelAdminData.push({
    jmeno: '', specializace: '', popis: '', fotka: '', zobrazit_na_webu: true,
    rozvrh: [0, 1, 2, 3, 4, 5, 6].map((den) => ({
      den, den_nazev: ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle'][den],
      od: null, do: null, volno: true,
    })),
  });
  renderPersonelAdminEdit();
});

function defaultRezervaceUrl() {
  const port = SALON_ID === 1 ? 5500 : 5501;
  return `http://localhost:${port}/rezervace.html`;
}

async function loadEmailSettings() {
  const status = document.getElementById('email-status');
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/admin/email/`, {
      headers: staffHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Nelze načíst');
    document.getElementById('smtp-host').value = data.smtp_host || 'smtp.forpsi.com';
    document.getElementById('smtp-port').value = data.smtp_port || 465;
    document.getElementById('smtp-ssl').checked = data.smtp_use_ssl !== false;
    document.getElementById('smtp-user').value = data.smtp_user || document.getElementById('edit-email').value || '';
    document.getElementById('smtp-password').value = '';
    document.getElementById('web-rezervace-url').value = data.web_rezervace_url || defaultRezervaceUrl();
    document.getElementById('smtp-password').placeholder = data.smtp_password_nastaveno
      ? '•••••••• (nastaveno – nechte prázdné pro zachování)'
      : 'Heslo ke schránce';
    status.textContent = data.smtp_aktivni
      ? `✓ Odesílání aktivní · Od: ${data.email_odesilatel}`
      : '⚠ Doplňte SMTP heslo pro odesílání potvrzení rezervací.';
    status.className = data.smtp_aktivni ? 'admin-hint success' : 'admin-hint';
  } catch (err) {
    status.textContent = err.message;
    status.className = 'admin-hint error';
  }
}

async function saveEmailSettings() {
  const msg = document.getElementById('email-save-msg');
  msg.textContent = 'Ukládám…';
  msg.className = 'status-msg';
  const payload = {
    smtp_host: document.getElementById('smtp-host').value.trim(),
    smtp_port: parseInt(document.getElementById('smtp-port').value, 10) || 465,
    smtp_use_ssl: document.getElementById('smtp-ssl').checked,
    smtp_user: document.getElementById('smtp-user').value.trim(),
    web_rezervace_url: document.getElementById('web-rezervace-url').value.trim(),
  };
  const pwd = document.getElementById('smtp-password').value;
  if (pwd) payload.smtp_password = pwd;

  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/admin/email/`, {
      method: 'PUT',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    msg.textContent = 'E-mail nastavení uloženo.';
    msg.className = 'status-msg success';
    loadEmailSettings();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function testEmailSettings() {
  const msg = document.getElementById('email-save-msg');
  msg.textContent = 'Odesílám test…';
  msg.className = 'status-msg';
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/admin/email/test/`, {
      method: 'POST',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ email: document.getElementById('smtp-user').value.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Test selhal');
    msg.textContent = data.message;
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

document.getElementById('nav-toggle')?.addEventListener('click', () => {
  document.querySelector('.nav-links')?.classList.toggle('open');
  document.body.classList.toggle('nav-open');
});

document.querySelectorAll('.nav-links a').forEach(a => {
  a.addEventListener('click', () => {
    document.querySelector('.nav-links')?.classList.remove('open');
    document.body.classList.remove('nav-open');
  });
});

window.addEventListener('scroll', () => {
  document.getElementById('nav')?.classList.toggle('scrolled', window.scrollY > 60);
});

document.getElementById('edit-section').addEventListener('change', e => {
  if (e.target.matches('.upload-cenik')) handleCenikUpload(e);
  if (e.target.matches('.upload-novinka')) handleNovinkaUpload(e);
});
document.getElementById('edit-section').addEventListener('click', e => {
  if (e.target.matches('.btn-remove-cenik-img')) removeCenikImage(e.target);
  if (e.target.matches('.btn-remove-novinka-img')) removeNovinkaImage(e.target);
});

document.getElementById('admin-toggle').addEventListener('click', openAdmin);
document.getElementById('btn-cancel').addEventListener('click', closeAdmin);
document.getElementById('btn-web-logout')?.addEventListener('click', handleWebAdminLogout);
document.getElementById('login-form').addEventListener('submit', handleLogin);
document.getElementById('btn-save').addEventListener('click', handleSave);
document.getElementById('btn-save-email').addEventListener('click', saveEmailSettings);
document.getElementById('btn-test-email').addEventListener('click', testEmailSettings);
document.getElementById('upload-hero').addEventListener('change', handleHeroUpload);
document.getElementById('upload-gallery').addEventListener('change', handleGalleryUpload);
document.getElementById('upload-logo')?.addEventListener('change', (e) => handleBrandUpload(e, 'logo'));
document.getElementById('upload-favicon')?.addEventListener('change', (e) => handleBrandUpload(e, 'favicon'));
document.getElementById('btn-clear-logo')?.addEventListener('click', () => clearBrandAsset('logo_url'));
document.getElementById('btn-clear-favicon')?.addEventListener('click', () => clearBrandAsset('favicon_url'));
wireColorPair('primary');
wireColorPair('accent');
document.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
document.getElementById('lightbox').addEventListener('click', e => {
  if (e.target.id === 'lightbox') closeLightbox();
});

Promise.all([fetchSalon(), fetchBunnyStatus(), fetchPersonel()])
  .then(([data, , personel]) => {
    salonData = data;
    renderSalon(data);
    renderPersonelPublic(personel);
  })
  .catch(err => {
    document.getElementById('loading').innerHTML =
      '<p>Obsah se nepodařilo načíst. Zkuste to prosím později.</p>';
    console.error(err);
  });
