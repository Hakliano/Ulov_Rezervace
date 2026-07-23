const API_BASE = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
  ? 'http://localhost:8000/api'
  : 'https://api.ulovklienty.cz/api';

const TOKEN_KEY = 'partner_hub_token';
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let token = localStorage.getItem(TOKEN_KEY) || '';
let salonId = null;
let salonCache = null;
let nastaveniCache = null;

function setMsg(el, text, ok) {
  if (!el) return;
  el.hidden = !text;
  el.textContent = text || '';
  el.className = 'msg ' + (ok ? 'ok' : 'err');
}

function partnerHeaders(extra = {}) {
  const h = { Accept: 'application/json', ...extra };
  if (token) h['X-Partner-Token'] = token;
  return h;
}

async function api(path, opts = {}) {
  const headers = partnerHeaders(opts.headers || {});
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  let data = null;
  const raw = await res.text();
  try { data = raw ? JSON.parse(raw) : null; } catch { data = { detail: raw }; }
  if (!res.ok) {
    const detail = data?.detail || data?.non_field_errors?.[0] || res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

function showLogin() {
  $('#view-login').classList.remove('hidden');
  $('#view-app').classList.add('hidden');
  $('#btn-logout').classList.add('hidden');
  $('#who').textContent = '';
}

function showApp(user) {
  $('#view-login').classList.add('hidden');
  $('#view-app').classList.remove('hidden');
  $('#btn-logout').classList.remove('hidden');
  $('#who').textContent = user ? `${user.username}${user.is_superuser ? ' (superuser)' : ''}` : '';
}

async function boot() {
  if (!token) {
    showLogin();
    return;
  }
  try {
    const me = await api('/partner/me/');
    showApp(me);
    await loadSalony();
  } catch {
    token = '';
    localStorage.removeItem(TOKEN_KEY);
    showLogin();
  }
}

async function loadSalony() {
  const list = await api('/partner/salony/');
  const sel = $('#salon-select');
  sel.innerHTML = list.map((s) => `<option value="${s.id}">#${s.id} — ${s.name}</option>`).join('');
}

function switchTab(name) {
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.pane').forEach((p) => p.classList.toggle('hidden', p.id !== `pane-${name}`));
}

function fillWeb(s) {
  $('#w-name').value = s.name || '';
  $('#w-email').value = s.email || '';
  $('#w-phone').value = s.phone || '';
  $('#w-address').value = s.address || '';
  $('#w-desc').value = s.description || '';
  $('#w-logo').value = s.logo_url || '';
  $('#w-favicon').value = s.favicon_url || '';
  $('#w-hero').value = s.hero_image || '';
}

function fillBanner(s) {
  $('#b-text').value = s.banner_text || '';
  $('#b-od').value = s.banner_od || '';
  $('#b-do').value = s.banner_do || '';
  $('#b-on').checked = !!s.banner_enabled;
}

function renderCenik(items) {
  const box = $('#cenik-list');
  box.innerHTML = '';
  (items || []).forEach((item, idx) => {
    const row = document.createElement('div');
    row.className = 'block';
    row.dataset.idx = String(idx);
    row.innerHTML = `
      <div class="edit-row">
        <input data-f="nazev" placeholder="Název" value="${escapeAttr(item.nazev || '')}">
        <input data-f="cena" type="number" step="0.01" placeholder="Cena" value="${item.cena ?? ''}">
      </div>
      <div class="edit-row">
        <input data-f="delka_minut" type="number" placeholder="Délka min" value="${item.delka_minut ?? ''}">
        <input data-f="poradi" type="number" placeholder="Pořadí" value="${item.poradi ?? idx}">
      </div>
      <label class="check"><input data-f="aktivni" type="checkbox" ${item.aktivni !== false ? 'checked' : ''}> Aktivní</label>
      <label class="check"><input data-f="rizikovy" type="checkbox" ${item.rizikovy ? 'checked' : ''}> Rizikový produkt</label>
      <input type="hidden" data-f="id" value="${item.id || ''}">
    `;
    box.appendChild(row);
  });
}

function collectCenik() {
  return [...$('#cenik-list').children].map((row) => {
    const get = (f) => row.querySelector(`[data-f="${f}"]`);
    const idVal = get('id')?.value;
    const out = {
      nazev: get('nazev').value.trim(),
      cena: get('cena').value === '' ? null : Number(get('cena').value),
      delka_minut: Number(get('delka_minut').value) || 0,
      poradi: Number(get('poradi').value) || 0,
      aktivni: get('aktivni').checked,
      rizikovy: get('rizikovy').checked,
    };
    if (idVal) out.id = Number(idVal);
    return out;
  }).filter((x) => x.nazev);
}

function renderNovinky(items) {
  const box = $('#novinky-list');
  box.innerHTML = '';
  (items || []).forEach((item) => {
    const row = document.createElement('div');
    row.className = 'block';
    row.innerHTML = `
      <input data-f="nadpis" placeholder="Nadpis" value="${escapeAttr(item.nadpis || '')}">
      <textarea data-f="text" rows="3" placeholder="Text">${escapeHtml(item.text || '')}</textarea>
      <input type="hidden" data-f="id" value="${item.id || ''}">
    `;
    box.appendChild(row);
  });
}

function collectNovinky() {
  return [...$('#novinky-list').children].map((row) => {
    const get = (f) => row.querySelector(`[data-f="${f}"]`);
    const idVal = get('id')?.value;
    const out = {
      nadpis: get('nadpis').value.trim(),
      text: get('text').value,
    };
    if (idVal) out.id = Number(idVal);
    return out;
  }).filter((x) => x.nadpis);
}

function fillRez(n) {
  $('#r-interval').value = n.interval_minut ?? '';
  $('#r-min').value = n.min_predstih_hodin ?? '';
  $('#r-max').value = n.max_predstih_mesicu ?? '';
  $('#r-storno').value = n.storno_do_hodin ?? '';
  $('#r-potv').value = n.potvrzeni_platnost_hodin ?? '';
  $('#r-gdpr').value = n.gdpr_zasady_verze || '';
  $('#r-auto').checked = !!n.auto_potvrzeni;
}

function fillEmaily(n) {
  $('#e-recenze').value = n.recenze_url || '';
  $('#e-notif').value = JSON.stringify(n.notifikace || [], null, 2);
  const guide = $('#e-tag-guide');
  if (guide && n.notifikace_tagy) {
    guide.textContent = (n.notifikace_tagy || []).map((t) => `${t.tag} — ${t.popis || ''}`).join('\n')
      || (n.notifikace_placeholders || '');
  }
}

function fillSmtp(e) {
  $('#s-host').value = e.smtp_host || '';
  $('#s-port').value = e.smtp_port ?? 465;
  $('#s-user').value = e.smtp_user || '';
  $('#s-pass').value = '';
  $('#s-pass').placeholder = e.smtp_password_nastaveno ? 'heslo nastaveno — nechte prázdné' : '(volitelné)';
  $('#s-from-name').value = e.email_jmeno_odesilatele || '';
  $('#s-from-email').value = e.email_odesilatel || '';
  $('#s-web').value = e.web_rezervace_url || '';
  $('#s-ssl').checked = e.smtp_use_ssl !== false;
  $('#s-imap-host').value = e.imap_host || '';
  $('#s-imap-port').value = e.imap_port ?? 993;
  $('#s-imap-ssl').checked = e.imap_use_ssl !== false;
  $('#s-imap-on').checked = !!e.imap_enabled;
}

async function renderStaff() {
  const data = await api(`/salon/${salonId}/rezervace/admin/zamestnanci/`);
  const box = $('#staff-list');
  box.innerHTML = '';
  (data.zamestnanci || []).forEach((z) => {
    const row = document.createElement('div');
    row.className = 'block';
    row.innerHTML = `
      <strong>${escapeHtml(z.jmeno || '')}</strong>
      <span class="muted"> · ${escapeHtml(z.role || '')}${z.ma_prihlaseni ? ' · FLOW účet' : ''}</span>
      <label>Číslo účtu / IBAN
        <input data-ucet value="${escapeAttr(z.cislo_uctu || '')}" placeholder="CZ… nebo 123456789/0100">
      </label>
      <button type="button" class="btn sm primary" data-save-staff="${z.id}">Uložit účet</button>
    `;
    box.appendChild(row);
  });
  box.querySelectorAll('[data-save-staff]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-save-staff');
      const ucet = btn.parentElement.querySelector('[data-ucet]').value.trim();
      try {
        await api(`/salon/${salonId}/rezervace/admin/zamestnanci/${id}/`, {
          method: 'PUT',
          body: JSON.stringify({ cislo_uctu: ucet }),
        });
        setMsg($('#app-msg'), 'Účet pracovníka uložen.', true);
      } catch (err) {
        setMsg($('#app-msg'), err.message, false);
      }
    });
  });
}

function fillLinks() {
  const base = window.location.origin;
  const demo = salonId <= 8 ? `https://demo${salonId}.ulovklienty.cz` : `${base}/salon${salonId}`;
  const isStaging = location.hostname.includes('staging');
  const demoUrl = isStaging
    ? `https://www.staging.ulovklienty.cz/salon${salonId}/`
    : demo.endsWith('/') ? demo : `${demo}/`;
  $('#link-web').href = demoUrl;
  $('#link-web').textContent = demoUrl;
  $('#link-rez').href = `${demoUrl}rezervace.html`;
  $('#link-rez').textContent = `${demoUrl}rezervace.html`;
  $('#link-flow').href = isStaging
    ? 'https://www.staging.ulovklienty.cz/flow/'
    : 'https://www.ulovklienty.cz/flow/';
  $('#link-django').href = isStaging
    ? 'https://api-staging.ulovklienty.cz/admin/'
    : 'https://api.ulovklienty.cz/admin/';
}

async function openSalon() {
  salonId = Number($('#salon-select').value);
  if (!salonId) return;
  setMsg($('#app-msg'), 'Načítám…', true);
  try {
    salonCache = await api(`/partner/salony/${salonId}/`);
    nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`);
    const emailCfg = await api(`/salon/${salonId}/admin/email/`);
    fillWeb(salonCache);
    fillBanner(salonCache);
    renderCenik(salonCache.cenik || []);
    renderNovinky(salonCache.novinky || []);
    fillRez(nastaveniCache);
    fillEmaily(nastaveniCache);
    fillSmtp(emailCfg);
    await renderStaff();
    fillLinks();
    $('#tabs').classList.remove('hidden');
    switchTab('web');
    setMsg($('#app-msg'), `Salon #${salonId} načten.`, true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
}

function escapeAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

$('#form-login').addEventListener('submit', async (e) => {
  e.preventDefault();
  setMsg($('#login-msg'), '', true);
  try {
    const data = await api('/partner/prihlaseni/', {
      method: 'POST',
      body: JSON.stringify({
        username: $('#login-user').value.trim(),
        password: $('#login-pass').value,
      }),
    });
    token = data.token;
    localStorage.setItem(TOKEN_KEY, token);
    showApp(data.user);
    await loadSalony();
  } catch (err) {
    setMsg($('#login-msg'), err.message, false);
  }
});

$('#btn-logout').addEventListener('click', () => {
  token = '';
  localStorage.removeItem(TOKEN_KEY);
  salonId = null;
  showLogin();
});

$('#btn-open-salon').addEventListener('click', openSalon);

$$('.tab').forEach((t) => t.addEventListener('click', () => switchTab(t.dataset.tab)));

$('#form-web').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const payload = {
      name: $('#w-name').value.trim(),
      email: $('#w-email').value.trim(),
      phone: $('#w-phone').value.trim(),
      address: $('#w-address').value.trim(),
      description: $('#w-desc').value,
    };
    // URL assetů jen mazání prázdným stringem — neposílat neprázdné logo/favicon/hero
    if (!$('#w-logo').value.trim()) payload.logo_url = '';
    if (!$('#w-favicon').value.trim()) payload.favicon_url = '';
    salonCache = await api(`/salon/${salonId}/`, { method: 'PUT', body: JSON.stringify(payload) });
    fillWeb(salonCache);
    setMsg($('#app-msg'), 'Web uložen.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#form-banner').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    salonCache = await api(`/salon/${salonId}/`, {
      method: 'PUT',
      body: JSON.stringify({
        banner_text: $('#b-text').value.trim(),
        banner_od: $('#b-od').value || null,
        banner_do: $('#b-do').value || null,
        banner_enabled: $('#b-on').checked,
      }),
    });
    fillBanner(salonCache);
    setMsg($('#app-msg'), 'Banner uložen.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#btn-add-cenik').addEventListener('click', () => {
  renderCenik([...(collectCenik()), { nazev: '', cena: 0, delka_minut: 60, poradi: 0, aktivni: true, rizikovy: false }]);
});

$('#btn-save-cenik').addEventListener('click', async () => {
  try {
    salonCache = await api(`/salon/${salonId}/`, {
      method: 'PUT',
      body: JSON.stringify({ cenik: collectCenik() }),
    });
    renderCenik(salonCache.cenik || []);
    setMsg($('#app-msg'), 'Ceník uložen.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#btn-add-novinka').addEventListener('click', () => {
  renderNovinky([...(collectNovinky()), { nadpis: '', text: '' }]);
});

$('#btn-save-novinky').addEventListener('click', async () => {
  try {
    salonCache = await api(`/salon/${salonId}/`, {
      method: 'PUT',
      body: JSON.stringify({ novinky: collectNovinky() }),
    });
    renderNovinky(salonCache.novinky || []);
    setMsg($('#app-msg'), 'Novinky uloženy.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#form-rez').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const payload = {
      interval_minut: Number($('#r-interval').value) || 15,
      min_predstih_hodin: Number($('#r-min').value) || 0,
      max_predstih_mesicu: Number($('#r-max').value) || 3,
      storno_do_hodin: Number($('#r-storno').value) || 24,
      potvrzeni_platnost_hodin: Number($('#r-potv').value) || 24,
      gdpr_zasady_verze: $('#r-gdpr').value.trim(),
      auto_potvrzeni: $('#r-auto').checked,
      notifikace: nastaveniCache?.notifikace || [],
    };
    nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    fillRez(nastaveniCache);
    setMsg($('#app-msg'), 'Pravidla rezervací uložena.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#btn-toggle-guide')?.addEventListener('click', () => {
  const g = $('#e-tag-guide-wrap');
  if (!g) return;
  const nowHidden = g.classList.toggle('hidden');
  $('#btn-toggle-guide').textContent = nowHidden
    ? 'Ukázat nápovědu dynamických polí'
    : 'Skrýt nápovědu';
});

$('#btn-save-emaily').addEventListener('click', async () => {
  try {
    let notifikace;
    try {
      notifikace = JSON.parse($('#e-notif').value);
    } catch {
      throw new Error('Notifikace JSON není platný.');
    }
    nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`, {
      method: 'PUT',
      body: JSON.stringify({
        ...nastaveniCache,
        recenze_url: $('#e-recenze').value.trim(),
        notifikace,
      }),
    });
    fillEmaily(nastaveniCache);
    setMsg($('#app-msg'), 'E-mailové šablony uloženy.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

$('#form-smtp').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const payload = {
      smtp_host: $('#s-host').value.trim(),
      smtp_port: Number($('#s-port').value) || 465,
      smtp_use_ssl: $('#s-ssl').checked,
      smtp_user: $('#s-user').value.trim(),
      email_jmeno_odesilatele: $('#s-from-name').value.trim(),
      email_odesilatel: $('#s-from-email').value.trim(),
      web_rezervace_url: $('#s-web').value.trim(),
      imap_host: $('#s-imap-host').value.trim(),
      imap_port: Number($('#s-imap-port').value) || 993,
      imap_use_ssl: $('#s-imap-ssl').checked,
      imap_enabled: $('#s-imap-on').checked,
    };
    const pwd = $('#s-pass').value;
    if (pwd) payload.smtp_password = pwd;
    const emailCfg = await api(`/salon/${salonId}/admin/email/`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    fillSmtp(emailCfg);
    setMsg($('#app-msg'), 'SMTP/IMAP uloženo.', true);
  } catch (err) {
    setMsg($('#app-msg'), err.message, false);
  }
});

boot();
