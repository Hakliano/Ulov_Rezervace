const API_BASE = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname) ? 'http://localhost:8000/api' : 'https://api.ulovklienty.cz/api';
const SALON_ID = 3;

let info = null;
let gdprMeta = { zasady_verze: '1.0', jazyk: 'cs' };
let vybraneSluzby = new Set();
let vybranyCas = null;
let sessionToken = localStorage.getItem(`rez_token_${SALON_ID}`);
let staffToken = sessionStorage.getItem(`staff_token_${SALON_ID}`) || '';
let staffUser = null;
try {
  staffUser = JSON.parse(sessionStorage.getItem(`staff_user_${SALON_ID}`) || 'null');
} catch {
  staffUser = null;
}
let auditPage = 1;
let posledniRezervaceId = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function isMajitel() {
  return staffUser?.je_majitel === true;
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (staffToken) headers['X-Staff-Token'] = staffToken;
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
  if (!res.ok) throw new Error(data?.detail || data?.message || 'Chyba API');
  return data;
}

function formatDate(d) {
  if (!d) return '';
  const dt = new Date(d);
  return dt.toLocaleDateString('cs-CZ');
}

function formatDateTime(d) {
  if (!d) return '';
  const dt = new Date(d);
  return dt.toLocaleString('cs-CZ', { dateStyle: 'short', timeStyle: 'short' });
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function showView(name) {
  $$('.view').forEach(v => v.classList.add('hidden'));
  $$('.rez-tab').forEach(t => t.classList.remove('active'));
  const view = $(`#view-${name}`);
  if (view) view.classList.remove('hidden');
  const tab = $(`.rez-tab[data-view="${name}"]`);
  if (tab) tab.classList.add('active');
}

function setStep(n) {
  $$('.step').forEach(s => s.classList.toggle('active', parseInt(s.dataset.step, 10) <= n));
  ['panel-sluzby', 'panel-termin', 'panel-udaje', 'panel-hotovo'].forEach((id, i) => {
    $(`#${id}`).classList.toggle('hidden', i !== n - 1);
  });
}

async function loadInfo() {
  info = await api(`/salon/${SALON_ID}/rezervace/info/`);
  if (info.gdpr) gdprMeta = { ...gdprMeta, ...info.gdpr };
  $('#salon-name').textContent = `Rezervace – ${info.salon.name}`;
  document.title = `Rezervace – ${info.salon.name}`;

  const sel = $('#select-zamestnanec');
  sel.innerHTML = '<option value="any">Je mi to jedno</option>';
  info.zamestnanci.forEach(z => {
    sel.innerHTML += `<option value="${z.id}">${esc(z.jmeno)} – ${esc(z.specializace)}</option>`;
  });

  $('#sluzby-list').innerHTML = info.sluzby.map(s => `
    <label class="sluzba-card">
      <input type="checkbox" value="${s.id}" data-delka="${s.delka_minut + s.rezerva_minut}">
      <span class="sluzba-name">${esc(s.nazev)}</span>
      <span class="sluzba-meta">${s.delka_minut} min · ${s.cena} Kč</span>
    </label>
  `).join('');

  $$('#sluzby-list input').forEach(inp => {
    inp.addEventListener('change', () => {
      if (inp.checked) vybraneSluzby.add(parseInt(inp.value, 10));
      else vybraneSluzby.delete(parseInt(inp.value, 10));
      updateDelkaInfo();
    });
  });

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  $('#input-datum').value = tomorrow.toISOString().slice(0, 10);
  $('#input-datum').min = new Date().toISOString().slice(0, 10);

  $('#loading').classList.add('hidden');
  showView('nova');
  $('#view-nova').classList.remove('hidden');
}

function updateDelkaInfo() {
  let total = 0;
  $$('#sluzby-list input:checked').forEach(inp => { total += parseInt(inp.dataset.delka, 10); });
  $('#delka-info').textContent = vybraneSluzby.size ? `Celková délka: cca ${total} min` : '';
  $('#btn-krok2').disabled = vybraneSluzby.size === 0;
}

async function loadTerminy() {
  const datum = $('#input-datum').value;
  const z = $('#select-zamestnanec').value;
  const sluzby = [...vybraneSluzby].join(',');
  const params = new URLSearchParams({ datum, sluzby });
  if (z !== 'any') params.set('zamestnanec', z);

  $('#terminy-list').innerHTML = '';
  $('#terminy-msg').textContent = 'Načítám termíny…';
  vybranyCas = null;
  $('#btn-krok3').disabled = true;

  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/volne-terminy/?${params}`);
    if (data.zavreno) {
      $('#terminy-msg').textContent = data.duvod || 'Salon je tento den zavřený.';
      return;
    }
    if (!data.terminy.length) {
      $('#terminy-msg').textContent = data.duvod || 'Žádné volné termíny. Zkuste jiný den nebo pracovníka.';
      return;
    }
    $('#terminy-msg').textContent = `${data.terminy.length} volných termínů`;
    $('#terminy-list').innerHTML = data.terminy.map(t => `
      <button type="button" class="termin-btn" data-cas="${t.cas}">${t.cas}</button>
    `).join('');
    $$('.termin-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.termin-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        vybranyCas = btn.dataset.cas;
        $('#btn-krok3').disabled = false;
      });
    });
  } catch (e) {
    $('#terminy-msg').textContent = e.message;
  }
}

function updateSummary() {
  const sluzby = info.sluzby.filter(s => vybraneSluzby.has(s.id)).map(s => s.nazev).join(', ');
  $('#summary').innerHTML = `
    <p><strong>Služby:</strong> ${esc(sluzby)}</p>
    <p><strong>Termín:</strong> ${$('#input-datum').value} v ${vybranyCas}</p>
    <p><strong>Pracovník:</strong> ${esc($('#select-zamestnanec').selectedOptions[0].text)}</p>
  `;
}

async function submitRezervace(e) {
  e.preventDefault();
  const msg = $('#rezervace-msg');
  msg.textContent = 'Odesílám…';
  msg.className = 'status-msg';

  const payload = {
    sluzby: [...vybraneSluzby],
    datum: $('#input-datum').value,
    cas: vybranyCas,
    zamestnanec_id: $('#select-zamestnanec').value === 'any' ? null : parseInt($('#select-zamestnanec').value, 10),
    nick: $('#input-nick').value.trim(),
    email: $('#input-email').value.trim(),
    poznamka: $('#input-poznamka').value.trim(),
    ochrana_udaju_souhlas: $('#input-ochrana').checked,
    zasady_verze: gdprMeta.zasady_verze,
    jazyk: gdprMeta.jazyk || 'cs',
    session_token: sessionToken || null,
  };

  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/`, { method: 'POST', body: JSON.stringify(payload) });
    posledniRezervaceId = data.id;
    setStep(4);
    const cekaPotvrzeni = data.stav === 'ceka';
    const hotovoTitle = $('#panel-hotovo h2');
    if (hotovoTitle) {
      hotovoTitle.textContent = cekaPotvrzeni ? 'Zkontrolujte e-mail' : '✓ Rezervace potvrzena';
    }
    const stornoLink = data.storno_url || `rezervace.html?storno=${data.cancel_token}`;
    const potvrzeniLink = data.potvrzeni_url || (data.potvrzeni_token ? `rezervace.html?potvrdit=${data.potvrzeni_token}` : '');
    const emailNote = data.email_smtp
      ? (cekaPotvrzeni
        ? `Na <strong>${esc(payload.email)}</strong> jsme odeslali e-mail s odkazem pro potvrzení. Rezervace je platná až po kliknutí na odkaz.`
        : `Potvrzení bylo odesláno z adresy <strong>${esc(data.email_odesilatel || '')}</strong> na <strong>${esc(payload.email)}</strong>.`)
      : (cekaPotvrzeni && potvrzeniLink
        ? `Potvrďte rezervaci kliknutím na odkaz: <a href="${esc(potvrzeniLink)}">${esc(potvrzeniLink)}</a>`
        : `Odkaz pro zrušení rezervace: <a href="${esc(stornoLink)}">${esc(stornoLink)}</a>`);
    $('#hotovo-text').innerHTML = `
      ${cekaPotvrzeni ? 'Rezervace <strong>čeká na potvrzení</strong>.' : `Rezervace <strong>${esc(data.stav_label)}</strong>.`}<br>
      Termín: ${formatDateTime(data.zacatek)}<br>
      ${emailNote}<br><br>
      ${cekaPotvrzeni ? '' : `<a href="${esc(stornoLink)}" class="storno-link">Zrušit tuto rezervaci</a>`}
    `;
    const icsLink = $('#ics-link');
    if (icsLink) {
      if (cekaPotvrzeni) {
        icsLink.classList.add('hidden');
      } else {
        icsLink.classList.remove('hidden');
        icsLink.href = `${API_BASE}/salon/${SALON_ID}/rezervace/${data.id}/ics/`;
      }
    }
    msg.textContent = '';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function loadMoje() {
  if (!sessionToken) return;
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/zakaznik/moje/?token=${sessionToken}`);
    $('#moje-login').classList.add('hidden');
    $('#moje-seznam').classList.remove('hidden');
    $('#moje-nick').textContent = data.zakaznik.nick;

    const renderRez = (r) => `
      <div class="rez-card">
        <strong>${formatDateTime(r.zacatek)}</strong>
        <span class="stav stav-${r.stav}">${esc(r.stav_label)}</span>
        <p>${r.polozky.map(p => esc(p.nazev)).join(', ')}</p>
        ${r.stav === 'ceka' ? `<a href="rezervace.html?potvrdit=${r.potvrzeni_token}">Potvrdit rezervaci</a>` : ''}
        ${r.stav === 'potvrzeno' || r.stav === 'ceka' ? `<a href="rezervace.html?storno=${r.cancel_token}">Stornovat</a>` : ''}
      </div>`;

    $('#moje-budouci').innerHTML = data.budouci.length ? data.budouci.map(renderRez).join('') : '<p class="hint">Žádné budoucí rezervace.</p>';
    $('#moje-historie').innerHTML = data.historie.length ? data.historie.map(renderRez).join('') : '<p class="hint">Prázdná historie.</p>';
  } catch {
    sessionToken = null;
    localStorage.removeItem(`rez_token_${SALON_ID}`);
  }
}

async function handlePotvrzeni(token) {
  showView('potvrzeni');
  $('#view-nova').classList.add('hidden');
  $('#potvrzeni-msg').textContent = '';
  $('#potvrzeni-msg').className = 'status-msg';
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/potvrdit/${token}/info/`);
    const r = data.rezervace;
    if (data.jiz_potvrzeno) {
      $('#potvrzeni-info').innerHTML = `
        <p class="success">Rezervace je již potvrzena.</p>
        <p><strong>${formatDateTime(r.zacatek)}</strong></p>
        <p>${r.polozky.map(p => esc(p.nazev)).join(', ')}</p>
      `;
      $('#btn-potvrdit').classList.add('hidden');
      return;
    }
    $('#potvrzeni-info').innerHTML = `
      <p>Prosím potvrďte rezervaci na tento termín:</p>
      <p><strong>${formatDateTime(r.zacatek)}</strong></p>
      <p>${r.polozky.map(p => esc(p.nazev)).join(', ')}</p>
      ${r.zamestnanec_jmeno ? `<p>Pracovník: ${esc(r.zamestnanec_jmeno)}</p>` : ''}
      ${data.lze_potvrdit ? '' : `<p class="error">${esc(data.detail)}</p>`}
    `;
    $('#btn-potvrdit').classList.remove('hidden');
    $('#btn-potvrdit').disabled = !data.lze_potvrdit;
    $('#btn-potvrdit').onclick = async () => {
      try {
        const res = await api(`/salon/${SALON_ID}/rezervace/potvrdit/${token}/`, { method: 'POST', body: '{}' });
        $('#potvrzeni-info').innerHTML = `
          <p class="success">${esc(res.message)}</p>
          <p><strong>${formatDateTime(res.rezervace.zacatek)}</strong></p>
          <p>${res.rezervace.polozky.map(p => esc(p.nazev)).join(', ')}</p>
          <p><a href="${API_BASE}/salon/${SALON_ID}/rezervace/${res.rezervace.id}/ics/">Stáhnout kalendář (.ics)</a></p>
        `;
        $('#potvrzeni-msg').textContent = 'Potvrzovací e-mail byl odeslán.';
        $('#potvrzeni-msg').className = 'status-msg success';
        $('#btn-potvrdit').classList.add('hidden');
      } catch (e) {
        $('#potvrzeni-msg').textContent = e.message;
        $('#potvrzeni-msg').className = 'status-msg error';
      }
    };
  } catch (e) {
    $('#potvrzeni-info').innerHTML = `<p class="error">${esc(e.message)}</p>`;
    $('#btn-potvrdit').classList.add('hidden');
  }
}

async function handleStorno(token) {
  showView('storno');
  $('#view-nova').classList.add('hidden');
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/storno/${token}/info/`);
    const r = data.rezervace;
    $('#storno-info').innerHTML = `
      <p><strong>${formatDateTime(r.zacatek)}</strong></p>
      <p>${r.polozky.map(p => esc(p.nazev)).join(', ')}</p>
      <p>Stav: ${esc(r.stav_label)}</p>
      ${data.lze_stornovat ? '' : `<p class="error">${esc(data.duvod)}</p>`}
    `;
    $('#btn-storno').disabled = !data.lze_stornovat;
    $('#btn-storno').onclick = async () => {
      try {
        await api(`/salon/${SALON_ID}/rezervace/storno/${token}/`, { method: 'POST', body: '{}' });
        $('#storno-msg').textContent = 'Rezervace zrušena.';
        $('#storno-msg').className = 'status-msg success';
        $('#btn-storno').disabled = true;
      } catch (e) {
        $('#storno-msg').textContent = e.message;
        $('#storno-msg').className = 'status-msg error';
      }
    };
  } catch (e) {
    $('#storno-info').innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

const MONTH_NAMES = ['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec'];
const STAV_OPTS = [
  ['ceka', 'Čeká'],
  ['potvrzeno', 'Potvrzeno'],
  ['dokonceno', 'Dokončeno'],
  ['no_show', 'No-show'],
  ['salon_storno', 'Salon storno'],
  ['zakaznik_storno', 'Zák. storno'],
];

let adminCalMonth = new Date();
adminCalMonth.setDate(1);
let adminCalData = [];

function formatTime(d) {
  return new Date(d).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' });
}

function dateKey(d) {
  return new Date(d).toISOString().slice(0, 10);
}

function monthRange(monthDate) {
  const y = monthDate.getFullYear();
  const m = monthDate.getMonth();
  const first = new Date(y, m, 1);
  const last = new Date(y, m + 1, 0);
  return { od: first.toISOString().slice(0, 10), do: last.toISOString().slice(0, 10) };
}

async function loadAdminKalendar() {
  const { od, do: do_ } = monthRange(adminCalMonth);
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/kalendar/?od=${od}&do=${do_}`);
  adminCalData = data.rezervace;
  renderAdminCalendar();
  $('#cal-day-detail').classList.add('hidden');
}

function renderAdminCalendar() {
  $('#cal-month-label').textContent = `${MONTH_NAMES[adminCalMonth.getMonth()]} ${adminCalMonth.getFullYear()}`;

  const y = adminCalMonth.getFullYear();
  const m = adminCalMonth.getMonth();
  const first = new Date(y, m, 1);
  const last = new Date(y, m + 1, 0);
  const startPad = (first.getDay() + 6) % 7;
  const daysInMonth = last.getDate();
  const today = new Date().toISOString().slice(0, 10);

  const byDay = {};
  adminCalData.forEach((r) => {
    const k = dateKey(r.zacatek);
    if (!byDay[k]) byDay[k] = [];
    byDay[k].push(r);
  });

  let html = '';
  for (let i = 0; i < startPad; i += 1) html += '<div class="cal-cell cal-empty"></div>';
  for (let day = 1; day <= daysInMonth; day += 1) {
    const key = new Date(y, m, day).toISOString().slice(0, 10);
    const count = (byDay[key] || []).length;
    const cls = ['cal-cell', key === today ? 'cal-today' : '', count ? 'cal-has-events' : ''].filter(Boolean).join(' ');
    html += `<button type="button" class="${cls}" data-date="${key}" ${count ? '' : 'disabled'}>
      <span class="cal-day-num">${day}</span>
      ${count ? `<span class="cal-badge">${count}</span>` : ''}
    </button>`;
  }
  $('#cal-grid').innerHTML = html;
  $$('#cal-grid .cal-cell[data-date]').forEach((btn) => {
    btn.addEventListener('click', () => showCalDay(btn.dataset.date));
  });
}

function renderRezAkceButtons(r) {
  const hasEmail = !!(r.kontaktni_email || r.email_host);
  const isPast = new Date(r.konec) <= new Date();
  const storno = ['zakaznik_storno', 'salon_storno'];
  const canNoshow = ['ceka', 'potvrzeno'].includes(r.stav) && isPast;
  const canPlatba = hasEmail && !storno.includes(r.stav);
  if (!canNoshow && !canPlatba) return '';
  let html = '<div class="rez-akce">';
  if (canNoshow) {
    html += `
      <button type="button" class="btn btn-primary btn-sm btn-rez-dokonceno" data-id="${r.id}">Rezervace proběhla</button>
      <button type="button" class="btn btn-danger btn-sm btn-rez-noshow" data-id="${r.id}">NO-show</button>`;
  }
  if (canPlatba) {
    html += `
      <button type="button" class="btn btn-secondary btn-sm btn-rez-platba" data-id="${r.id}">Požádat o platbu na účet</button>`;
  }
  html += '</div>';
  return html;
}

const STAV_LABELS = Object.fromEntries(STAV_OPTS);

function renderAdminEvent(r) {
  const jmeno = r.kontaktni_jmeno || r.zakaznik_nick || r.jmeno_host || '—';
  const sluzby = r.polozky.map((p) => esc(p.nazev)).join(', ');
  const stavLabel = STAV_LABELS[r.stav] || r.stav;
  return `
    <div class="cal-event admin-card">
      <div class="cal-event-time">${formatTime(r.zacatek)} – ${formatTime(r.konec)}</div>
      <div class="cal-event-body">
        <div class="rez-event-head">
          <strong>${esc(jmeno)}</strong>
          <span class="stav stav-${r.stav}">${esc(stavLabel)}</span>
        </div>
        <p>${sluzby}</p>
        ${r.zamestnanec_jmeno ? `<p class="hint">Pracovník: ${esc(r.zamestnanec_jmeno)}</p>` : ''}
        ${renderRezAkceButtons(r)}
      </div>
    </div>`;
}

async function refreshCalDayAfterChange() {
  const selected = $(`#cal-grid .cal-cell.selected`)?.dataset.date;
  await loadAdminKalendar();
  if (selected) showCalDay(selected);
}

function bindRezAkce(root) {
  root.querySelectorAll('.btn-rez-dokonceno').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await api(`/salon/${SALON_ID}/rezervace/admin/${btn.dataset.id}/dokonceno/`, { method: 'POST' });
        await refreshCalDayAfterChange();
      } catch (e) {
        alert(e.message);
        btn.disabled = false;
      }
    });
  });
  root.querySelectorAll('.btn-rez-noshow').forEach((btn) => {
    btn.addEventListener('click', () => openNoShowModal(parseInt(btn.dataset.id, 10)));
  });
  root.querySelectorAll('.btn-rez-platba').forEach((btn) => {
    btn.addEventListener('click', () => openPlatbaModal(parseInt(btn.dataset.id, 10)));
  });
}

let pendingNoShowId = null;

function openNoShowModal(rezId) {
  const r = adminCalData.find((x) => Number(x.id) === Number(rezId));
  if (!r) {
    alert('Rezervaci se nepodařilo načíst. Obnovte stránku klávesou Ctrl+F5.');
    return;
  }
  if (!['ceka', 'potvrzeno'].includes(r.stav)) {
    alert('Tuto rezervaci už nelze označit jako NO-show (je ve stavu: ' + (STAV_LABELS[r.stav] || r.stav) + ').');
    return;
  }
  pendingNoShowId = rezId;
  const jmeno = r.kontaktni_jmeno || r.zakaznik_nick || r.jmeno_host || '—';
  const email = r.kontaktni_email || r.email_host || 'bez e-mailu';
  $('#noshow-modal-info').textContent = `${jmeno} (${email}) — ${formatDateTime(r.zacatek)}`;
  $('#noshow-send-email').checked = !!r.kontaktni_email;
  $('#noshow-send-email').disabled = !r.kontaktni_email;
  $('#noshow-block-email').checked = false;
  $('#noshow-modal-msg').textContent = '';
  const modal = $('#noshow-modal');
  if (!modal) {
    alert('Chybí dialog NO-show. Obnovte stránku Ctrl+F5.');
    return;
  }
  modal.classList.remove('hidden');
  document.body.classList.add('modal-open');
}

function closeNoShowModal() {
  pendingNoShowId = null;
  $('#noshow-modal')?.classList.add('hidden');
  document.body.classList.remove('modal-open');
}

let pendingPlatbaId = null;

function openPlatbaModal(rezId) {
  const r = adminCalData.find((x) => Number(x.id) === Number(rezId));
  if (!r) {
    alert('Rezervaci se nepodařilo načíst. Obnovte stránku klávesou Ctrl+F5.');
    return;
  }
  const email = r.kontaktni_email || r.email_host;
  if (!email) {
    alert('Rezervace nemá e-mail zákazníka.');
    return;
  }
  pendingPlatbaId = rezId;
  const jmeno = r.kontaktni_jmeno || r.zakaznik_nick || r.jmeno_host || '—';
  $('#platba-modal-info').textContent = `${jmeno} (${email}) — ${formatDateTime(r.zacatek)}`;
  $('#platba-castka').value = '';
  const ucet = r.zamestnanec_cislo_uctu
    || staffData.find((s) => s.id === r.zamestnanec)?.cislo_uctu
    || '';
  $('#platba-ucet').value = ucet;
  $('#platba-vs').value = String(r.id);
  $('#platba-modal-msg').textContent = '';
  $('#platba-modal')?.classList.remove('hidden');
  document.body.classList.add('modal-open');
}

function closePlatbaModal() {
  pendingPlatbaId = null;
  $('#platba-modal')?.classList.add('hidden');
  if (!$('#platba-qr-modal')?.classList.contains('hidden')) return;
  document.body.classList.remove('modal-open');
}

function showPlatbaQrOnScreen(data) {
  const img = $('#platba-qr-image');
  const info = $('#platba-qr-info');
  if (!img || !data.qr_png_base64) return;
  img.src = `data:image/png;base64,${data.qr_png_base64}`;
  img.alt = 'QR platba';
  if (info) {
    info.innerHTML = `
      <p><strong>${esc(data.castka || '')} Kč</strong></p>
      <p>Účet: ${esc(data.ucet || '')}</p>
      <p>VS: ${esc(data.variabilni_symbol || '')}</p>`;
  }
  $('#platba-qr-modal')?.classList.remove('hidden');
  document.body.classList.add('modal-open');
}

function closePlatbaQrModal() {
  $('#platba-qr-modal')?.classList.add('hidden');
  document.body.classList.remove('modal-open');
}

function applyStaffUI() {
  const badge = $('#admin-actor-badge');
  if (badge && staffUser) {
    badge.textContent = staffUser.je_majitel
      ? `${staffUser.jmeno} · majitelka`
      : staffUser.jmeno;
  }
  const majitelOnly = ['kadernice', 'noshow', 'nastaveni', 'audit'];
  $$('[data-admin]').forEach((btn) => {
    btn.classList.toggle('hidden', !isMajitel() && majitelOnly.includes(btn.dataset.admin));
  });
  if ($('#btn-staff-add')) $('#btn-staff-add').classList.toggle('hidden', !isMajitel());
}

function updateActorBadge() {
  applyStaffUI();
}

async function loadAuditLog(page = 1) {
  auditPage = page;
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/audit-log/?page=${page}`);
  const el = $('#audit-log-list');
  if (!data.vysledky?.length) {
    el.innerHTML = '<p class="hint">Zatím žádné záznamy.</p>';
  } else {
    el.innerHTML = `<table class="tag-table audit-table">
      <thead><tr><th>Kdy</th><th>Kdo</th><th>Co se stalo</th></tr></thead>
      <tbody>${data.vysledky.map((r) => `<tr>
        <td class="audit-kdy">${formatDateTime(r.kdy)}</td>
        <td><strong>${esc(r.kdo)}</strong></td>
        <td>${esc(r.popis)}</td>
      </tr>`).join('')}</tbody>
    </table>`;
  }
  const pag = $('#audit-pager');
  if (pag) pag.textContent = `Strana ${data.stranka} / ${data.celkem_stranek} (${data.celkem} záznamů)`;
  $('#audit-prev').disabled = data.stranka <= 1;
  $('#audit-next').disabled = data.stranka >= data.celkem_stranek;
}

async function loadNoShowArchiv(page = 1) {
  noshowPage = page;
  const params = new URLSearchParams({ page: String(page) });
  if (noshowQuery) params.set('q', noshowQuery);
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/no-show-archiv/?${params}`);
  const el = $('#noshow-archiv-list');
  const pag = $('#noshow-pagination');

  if (!data.vysledky?.length) {
    el.innerHTML = '<p class="hint">Žádný záznam NO-show'
      + (noshowQuery ? ' pro zadané hledání' : '') + '.</p>';
    pag.classList.add('hidden');
    return;
  }

  el.innerHTML = `<table class="tag-table noshow-table">
    <thead><tr>
      <th>E-mail</th><th>Jméno</th><th>NO-show</th><th>Stav</th><th>Poslední</th><th></th>
    </tr></thead>
    <tbody>${data.vysledky.map((z) => {
      let stav = 'V seznamu';
      if (z.blokovan_v_salonu) stav = 'Blokován';
      else if (z.problematicky) stav = 'Problematický';
      const rowCls = z.kriticky ? 'noshow-row-kriticky' : (z.problematicky ? 'noshow-row-varovani' : '');
      const btn = z.blokovan_v_salonu
        ? `<button type="button" class="btn btn-secondary btn-sm btn-noshow-odblok" data-email="${esc(z.email)}">ODBLOKOVAT</button>`
        : `<button type="button" class="btn btn-danger btn-sm btn-noshow-blok" data-email="${esc(z.email)}">ZABLOKOVAT</button>`;
      return `<tr class="${rowCls}">
        <td>${esc(z.email)}</td>
        <td>${esc(z.jmeno)}</td>
        <td><strong>${z.pocet_no_show}×</strong></td>
        <td><span class="stav stav-${z.blokovan_v_salonu ? 'no_show' : z.problematicky ? 'ceka' : 'potvrzeno'}">${stav}</span></td>
        <td>${formatDateTime(z.posledni)}</td>
        <td>${btn}</td>
      </tr>`;
    }).join('')}</tbody></table>
    <p class="hint">Zobrazeno ${data.vysledky.length} z ${data.celkem} kontaktů (strana ${data.stranka}/${data.celkem_stranek}). Řádky s 3+ NO-show jsou zvýrazněny červeně, s 2 NO-show oranžově.</p>`;

  el.querySelectorAll('.btn-noshow-blok').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Zablokovat ${btn.dataset.email} pro online rezervace v tomto salonu?`)) return;
      btn.disabled = true;
      try {
        await api(`/salon/${SALON_ID}/rezervace/admin/no-show-blokovat/`, {
          method: 'POST',
          body: JSON.stringify({ email: btn.dataset.email }),
        });
        await loadNoShowArchiv(noshowPage);
      } catch (e) {
        alert(e.message);
        btn.disabled = false;
      }
    });
  });

  el.querySelectorAll('.btn-noshow-odblok').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Odblokovat ${btn.dataset.email} pro online rezervace v tomto salonu?`)) return;
      btn.disabled = true;
      try {
        await api(`/salon/${SALON_ID}/rezervace/admin/no-show-odblokovat/`, {
          method: 'POST',
          body: JSON.stringify({ email: btn.dataset.email }),
        });
        await loadNoShowArchiv(noshowPage);
      } catch (e) {
        alert(e.message);
        btn.disabled = false;
      }
    });
  });

  if (data.celkem_stranek > 1) {
    pag.classList.remove('hidden');
    pag.innerHTML = `
      <button type="button" class="btn btn-secondary btn-sm" id="noshow-prev" ${data.stranka <= 1 ? 'disabled' : ''}>← Předchozí</button>
      <span>Strana ${data.stranka} / ${data.celkem_stranek}</span>
      <button type="button" class="btn btn-secondary btn-sm" id="noshow-next" ${data.stranka >= data.celkem_stranek ? 'disabled' : ''}>Další →</button>`;
    $('#noshow-prev')?.addEventListener('click', () => loadNoShowArchiv(data.stranka - 1));
    $('#noshow-next')?.addEventListener('click', () => loadNoShowArchiv(data.stranka + 1));
  } else {
    pag.classList.add('hidden');
  }
}

function showCalDay(dateStr) {
  $$('#cal-grid .cal-cell').forEach((c) => c.classList.remove('selected'));
  $(`#cal-grid .cal-cell[data-date="${dateStr}"]`)?.classList.add('selected');

  const dt = new Date(`${dateStr}T12:00:00`);
  $('#cal-day-title').textContent = dt.toLocaleDateString('cs-CZ', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  const events = adminCalData
    .filter((r) => dateKey(r.zacatek) === dateStr)
    .sort((a, b) => new Date(a.zacatek) - new Date(b.zacatek));

  $('#cal-day-timeline').innerHTML = events.length
    ? events.map(renderAdminEvent).join('')
    : '<p class="hint">Žádné rezervace.</p>';
  bindRezAkce($('#cal-day-timeline'));
  $('#cal-day-detail').classList.remove('hidden');
}

async function loadStats() {
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/statistiky/`);
  $('#stats-box').innerHTML = `
    <p>Celkem rezervací: <strong>${data.celkem_rezervaci}</strong></p>
    <p>Dokončeno: ${data.dokonceno} · Storno: ${data.storno} (${data.storno_procent}%)</p>
    <p>No-show: ${data.no_show}</p>
    <h4>Nejprodávanější služby</h4>
    <ul>${data.nejprodavanejsi_sluzby.map(s => `<li>${esc(s.sluzba__nazev)} (${s.pocet}×)</li>`).join('')}</ul>
    <h4>Nejvytíženější zaměstnanci</h4>
    <ul>${data.nejvytizenejsi_zamestnanci.map(z => `<li>${esc(z.zamestnanec__jmeno)} (${z.pocet}×)</li>`).join('')}</ul>
  `;
}

async function loadNastaveni() {
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`);
  $('#nast-interval').value = data.interval_minut;
  $('#nast-min-h').value = data.min_predstih_hodin;
  $('#nast-max-m').value = data.max_predstih_mesicu;
  $('#nast-storno').value = data.storno_do_hodin ?? '';
  $('#nast-potvrzeni-h').value = data.potvrzeni_platnost_hodin ?? 24;
  $('#nast-gdpr-verze').value = data.gdpr_zasady_verze || '1.0';
  $('#nast-recenze-url').value = data.recenze_url || '';
  renderNotifikace(data.notifikace || [], data.notifikace_tagy, data.notifikace_placeholders);
}

const MAX_NOTIFIKACE = 4;

const NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show, bez automatického času',
  'Žádost o úhradu na účet s QR kódem — pouze ručně u rezervace (tlačítko Požádat o platbu)',
];

function renderTagGuide(tagy) {
  const el = $('#notif-tag-guide');
  if (!el) return;
  el.replaceChildren();
  if (!tagy?.length) return;
  const table = document.createElement('table');
  table.className = 'tag-table';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Tag (zkopírujte do textu)</th><th>Co se vypíše</th><th>Příklad</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  tagy.forEach((row) => {
    const tr = document.createElement('tr');
    const tdTag = document.createElement('td');
    const code = document.createElement('code');
    code.className = 'tag-copy';
    code.textContent = row.tag;
    code.title = 'Kliknutím zkopírujete';
    code.addEventListener('click', () => {
      navigator.clipboard?.writeText(row.tag);
      code.classList.add('tag-copied');
      setTimeout(() => code.classList.remove('tag-copied'), 800);
    });
    tdTag.appendChild(code);
    const tdPopis = document.createElement('td');
    tdPopis.textContent = row.popis;
    const tdPriklad = document.createElement('td');
    tdPriklad.className = 'tag-example';
    tdPriklad.textContent = row.priklad;
    tr.append(tdTag, tdPopis, tdPriklad);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

function renderNotifikace(notifikace, tagy, hint) {
  $('#notif-hint').textContent = hint || '';
  renderTagGuide(tagy);
  const list = $('#notifikace-list');
  list.replaceChildren();
  const items = [...(notifikace || [])];
  while (items.length < MAX_NOTIFIKACE) {
    items.push({ id: '', offset: 'manual', manual: true, aktivni: false, predmet: '', text: '' });
  }
  items.slice(0, MAX_NOTIFIKACE).forEach((n, i) => {
    list.appendChild(buildNotifCard(n, i));
  });
}

function buildNotifCard(n, i) {
  const isManual = i >= 2 || n.manual || n.offset === 'manual';
  const manualTyp = n.manual_typ || (i === 3 ? 'platba' : 'noshow');
  const card = document.createElement('div');
  card.className = 'notif-card';
  if (isManual) card.classList.add('notif-manual');
  if (!n.aktivni && !isManual) card.classList.add('notif-inactive');
  card.dataset.idx = String(i);
  card.dataset.manualTyp = manualTyp;

  const title = document.createElement('h5');
  title.className = 'notif-title';
  title.textContent = `Notifikace ${i + 1}`;

  const subtitle = document.createElement('p');
  subtitle.className = 'notif-subtitle';
  subtitle.textContent = NOTIF_POPISY[i] || '';

  const header = document.createElement('div');
  header.className = 'notif-header';

  if (isManual) {
    const manualHint = document.createElement('p');
    manualHint.className = 'notif-manual-hint';
    manualHint.textContent = manualTyp === 'platba'
      ? 'Tento e-mail se neodesílá automaticky. Personál ho odešle tlačítkem „Požádat o platbu na účet“ u rezervace — v e-mailu bude QR kód pro platbu.'
      : 'Tento e-mail se neodesílá automaticky. Text si připravíte zde, odešle se až po stisknutí NO-show u konkrétní rezervace v kalendáři.';
    header.appendChild(manualHint);
  } else {
    const activeLabel = document.createElement('label');
    activeLabel.className = 'checkbox notif-active-label';
    const activeCb = document.createElement('input');
    activeCb.type = 'checkbox';
    activeCb.className = 'notif-aktivni';
    activeCb.checked = !!n.aktivni;
    activeCb.addEventListener('change', () => {
      card.classList.toggle('notif-inactive', !activeCb.checked);
    });
    activeLabel.append(activeCb, document.createTextNode(' Odesílat automaticky (cron)'));

    const offsetLabel = document.createElement('label');
    offsetLabel.className = 'notif-offset-label';
    offsetLabel.append(document.createTextNode('Čas odeslání '));
    const offsetInput = document.createElement('input');
    offsetInput.type = 'text';
    offsetInput.className = 'notif-offset';
    offsetInput.value = n.offset || '+24';
    offsetInput.placeholder = '+24 nebo -2';
    offsetInput.title = '+24 = před termínem, -2 = po skončení rezervace';
    offsetLabel.appendChild(offsetInput);
    header.append(activeLabel, offsetLabel);
  }

  const predmetLabel = document.createElement('label');
  predmetLabel.className = 'notif-field';
  predmetLabel.append(document.createTextNode('Předmět e-mailu'));
  const predmetInput = document.createElement('input');
  predmetInput.type = 'text';
  predmetInput.className = 'notif-predmet';
  predmetInput.value = n.predmet || '';
  predmetLabel.appendChild(predmetInput);

  const textLabel = document.createElement('label');
  textLabel.className = 'notif-field';
  textLabel.append(document.createTextNode('Text e-mailu'));
  const textArea = document.createElement('textarea');
  textArea.className = 'notif-text';
  textArea.rows = 9;
  textArea.value = n.text || '';
  textLabel.appendChild(textArea);

  const idInput = document.createElement('input');
  idInput.type = 'hidden';
  idInput.className = 'notif-id';
  idInput.value = n.id || '';

  card.append(title, subtitle, header, predmetLabel, textLabel, idInput);
  return card;
}

function collectNotifikace() {
  return [...$$('#notifikace-list .notif-card')].map((card, i) => {
    const manual = card.classList.contains('notif-manual') || i >= 2;
    if (manual) {
      const manualTyp = card.dataset.manualTyp || (i === 3 ? 'platba' : 'noshow');
      return {
        id: card.querySelector('.notif-id')?.value || undefined,
        manual: true,
        offset: 'manual',
        manual_typ: manualTyp,
        aktivni: manualTyp === 'platba',
        predmet: card.querySelector('.notif-predmet')?.value ?? '',
        text: card.querySelector('.notif-text')?.value ?? '',
      };
    }
    return {
      id: card.querySelector('.notif-id')?.value || undefined,
      manual: false,
      aktivni: card.querySelector('.notif-aktivni')?.checked ?? false,
      offset: card.querySelector('.notif-offset')?.value.trim() || '+24',
      predmet: card.querySelector('.notif-predmet')?.value ?? '',
      text: card.querySelector('.notif-text')?.value ?? '',
    };
  });
}

let staffData = [];
let staffSalonHours = [];
let selectedStaffId = null;

function formatTimeInput(t) {
  if (!t) return '';
  return String(t).slice(0, 5);
}

function renderSalonHoursHint() {
  if (!staffSalonHours.length) {
    $('#salon-hours-hint').textContent = '—';
    return;
  }
  const parts = staffSalonHours.map((d) => {
    if (d.zavreno) return `${d.den_nazev}: zavřeno`;
    return `${d.den_nazev}: ${formatTimeInput(d.od)}–${formatTimeInput(d.do)}`;
  });
  $('#salon-hours-hint').textContent = parts.join(' · ');
}

async function loadStaff() {
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/`);
  staffData = data.zamestnanci || [];
  staffSalonHours = data.oteviraci_doba_salonu || [];
  renderSalonHoursHint();
  renderStaffList();
  if (selectedStaffId && staffData.some((s) => s.id === selectedStaffId)) {
    selectStaff(selectedStaffId);
  } else if (staffData.length) {
    const first = staffData.find((s) => s.role !== 'majitel') || staffData[0];
    selectStaff(first.id);
  } else {
    selectedStaffId = null;
    $('#staff-detail').classList.add('hidden');
    $('#staff-empty').classList.remove('hidden');
  }
}

function renderStaffList() {
  $('#staff-list').innerHTML = staffData.map((s) => `
    <button type="button" class="staff-list-btn ${s.id === selectedStaffId ? 'active' : ''} ${s.aktivni ? '' : 'staff-inactive'}" data-id="${s.id}">
      ${esc(s.jmeno)}
      <small>${esc(s.specializace || 'bez specializace')}${s.role === 'majitel' ? ' · majitelka' : ''}${s.aktivni ? '' : ' · účet deaktivován'}</small>
    </button>
  `).join('');
  $$('#staff-list .staff-list-btn').forEach((btn) => {
    btn.addEventListener('click', () => selectStaff(parseInt(btn.dataset.id, 10)));
  });
}

function getSelectedStaff() {
  return staffData.find((s) => s.id === selectedStaffId);
}

function renderStaffSluzby() {
  if (!info?.sluzby) return;
  $('#staff-sluzby').innerHTML = info.sluzby.map((s) => `
    <label><input type="checkbox" value="${s.id}"> ${esc(s.nazev)}</label>
  `).join('');
}

function updateStaffUcetUI(staff) {
  const status = $('#staff-ucet-status');
  const btnDeakt = $('#btn-staff-deaktivovat');
  const isMajitelka = staff.role === 'majitel';
  if (status) {
    if (isMajitelka) {
      status.textContent = 'Účet majitele — jen správa salonu, bez rezervací a rozvrhu. Pokud majitel také provádí služby, založte mu běžný zaměstnanecký účet.';
      status.className = 'hint';
    } else if (!staff.aktivni) {
      status.textContent = 'Účet je deaktivován. Zaměstnanec se nemůže přihlásit, historie rezervací a audit zůstávají zachované.';
      status.className = 'hint error';
    } else if (staff.ma_prihlaseni) {
      status.textContent = `Přihlášení: ${staff.prihlasovaci_jmeno}`;
      status.className = 'hint success';
    } else {
      status.textContent = 'Účet zatím nemá nastavené přihlášení.';
      status.className = 'hint';
    }
  }
  if (btnDeakt) {
    btnDeakt.classList.toggle('hidden', isMajitelka || !staff.aktivni || !staff.ma_prihlaseni);
  }
  const loginDisabled = !staff.aktivni && !isMajitelka;
  $('#staff-prihlasovaci-jmeno')?.toggleAttribute('disabled', loginDisabled);
  $('#staff-heslo')?.toggleAttribute('disabled', loginDisabled);
}

function updateStaffServiceUi(staff) {
  const isMajitelka = staff?.role === 'majitel';
  document.querySelector('.staff-active-label')?.classList.toggle('hidden', isMajitelka);
  document.querySelectorAll('#staff-detail .staff-block').forEach((block, index) => {
    if (index > 0) block.classList.toggle('hidden', isMajitelka);
  });
}

function selectStaff(id) {
  selectedStaffId = id;
  const staff = getSelectedStaff();
  if (!staff) return;
  renderStaffList();
  $('#staff-empty').classList.add('hidden');
  $('#staff-detail').classList.remove('hidden');
  $('#staff-detail-name').textContent = staff.jmeno;
  $('#staff-aktivni').checked = staff.aktivni;
  $('#staff-prihlasovaci-jmeno').value = staff.prihlasovaci_jmeno || '';
  $('#staff-heslo').value = '';
  $('#staff-cislo-uctu').value = staff.cislo_uctu || '';
  updateStaffUcetUI(staff);
  $('#staff-rozvrh').innerHTML = staff.rozvrh.map((r) => `
    <tr data-den="${r.den}">
      <td>${esc(r.den_nazev)}</td>
      <td><input type="time" class="roz-od" value="${formatTimeInput(r.od)}" ${r.volno ? 'disabled' : ''}></td>
      <td><input type="time" class="roz-do" value="${formatTimeInput(r.do)}" ${r.volno ? 'disabled' : ''}></td>
      <td><input type="checkbox" class="roz-volno" ${r.volno ? 'checked' : ''}></td>
    </tr>
  `).join('');
  $$('#staff-rozvrh .roz-volno').forEach((cb) => {
    cb.addEventListener('change', () => {
      const row = cb.closest('tr');
      row.querySelector('.roz-od').disabled = cb.checked;
      row.querySelector('.roz-do').disabled = cb.checked;
    });
  });
  $('#staff-absence-list').innerHTML = (staff.absence || []).length
    ? staff.absence.map((a) => `
      <div class="absence-item">
        <span><strong>${esc(a.typ_label)}</strong> ${formatDate(a.datum_od)} – ${formatDate(a.datum_do)}
        ${a.poznamka ? ` · ${esc(a.poznamka)}` : ''}</span>
        <button type="button" class="btn btn-secondary btn-sm btn-del-absence" data-id="${a.id}">Smazat</button>
      </div>
    `).join('')
    : '<p class="hint">Žádné zadané volno.</p>';
  $$('.btn-del-absence').forEach((btn) => {
    btn.addEventListener('click', () => deleteStaffAbsence(parseInt(btn.dataset.id, 10)));
  });
  renderStaffSluzby();
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (!$('#staff-rez-datum').value) {
    $('#staff-rez-datum').value = tomorrow.toISOString().slice(0, 10);
  }
  updateStaffServiceUi(staff);
}

function collectStaffRozvrh() {
  return [...$$('#staff-rozvrh tr[data-den]')].map((row) => {
    const volno = row.querySelector('.roz-volno').checked;
    const od = row.querySelector('.roz-od').value;
    const do_ = row.querySelector('.roz-do').value;
    return {
      den: parseInt(row.dataset.den, 10),
      volno,
      od: volno ? null : (od || null),
      do: volno ? null : (do_ || null),
    };
  });
}

async function deactivateStaffAccount() {
  const staff = getSelectedStaff();
  if (!staff || staff.role === 'majitel') return;
  if (!confirm(`Deaktivovat účet zaměstnance ${staff.jmeno}?\n\nÚčet se nesmaže — zůstane historie rezervací a audit. Zaměstnanec se už nepřihlásí.`)) return;
  const msg = $('#staff-rozvrh-msg');
  msg.textContent = 'Deaktivuji účet…';
  msg.className = 'status-msg';
  try {
    await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${staff.id}/deaktivovat/`, { method: 'POST' });
    msg.textContent = 'Účet byl deaktivován.';
    msg.className = 'status-msg success';
    await loadStaff();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function saveStaffRozvrh() {
  const staff = getSelectedStaff();
  if (!staff || staff.role === 'majitel') return;
  const msg = $('#staff-rozvrh-msg');
  msg.textContent = 'Ukládám…';
  msg.className = 'status-msg';
  try {
    await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${staff.id}/`, {
      method: 'PUT',
      body: JSON.stringify({
        jmeno: staff.jmeno,
        specializace: staff.specializace,
        aktivni: $('#staff-aktivni').checked,
        cislo_uctu: $('#staff-cislo-uctu').value.trim(),
        prihlasovaci_jmeno: $('#staff-prihlasovaci-jmeno').value.trim() || null,
        heslo: $('#staff-heslo').value,
        rozvrh: collectStaffRozvrh(),
      }),
    });
    msg.textContent = 'Údaje kadeřnice uloženy.';
    msg.className = 'status-msg success';
    await loadStaff();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function deleteStaffAbsence(absenceId) {
  if (!selectedStaffId || !confirm('Smazat toto volno?')) return;
  await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${selectedStaffId}/absence/${absenceId}/`, {
    method: 'DELETE',
  });
  await loadStaff();
}

async function addStaffMember() {
  const jmeno = prompt('Jméno kadeřnice:');
  if (!jmeno?.trim()) return;
  const specializace = prompt('Specializace (volitelné):') || '';
  const data = await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/`, {
    method: 'POST',
    body: JSON.stringify({ jmeno: jmeno.trim(), specializace: specializace.trim(), aktivni: true }),
  });
  selectedStaffId = data.id;
  await loadStaff();
}

// Event listeners
$$('.rez-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const v = tab.dataset.view;
    showView(v);
    if (v === 'moje') loadMoje();
    if (v === 'nova') setStep(1);
  });
});

$('#btn-krok2').addEventListener('click', () => { setStep(2); loadTerminy(); });
$('#btn-krok1').addEventListener('click', () => setStep(1));
$('#btn-krok3').addEventListener('click', () => { setStep(3); updateSummary(); });
$('#btn-krok2b').addEventListener('click', () => setStep(2));
$('#input-datum').addEventListener('change', loadTerminy);
$('#select-zamestnanec').addEventListener('change', loadTerminy);
$('#form-rezervace').addEventListener('submit', submitRezervace);
$('#btn-nova-rezervace').addEventListener('click', () => {
  vybraneSluzby.clear();
  vybranyCas = null;
  $$('#sluzby-list input').forEach(i => { i.checked = false; });
  setStep(1);
});

$('#form-registrace').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#moje-login-msg');
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/zakaznik/registrace/`, {
      method: 'POST',
      body: JSON.stringify({
        nick: $('#reg-nick').value.trim(),
        email: $('#reg-email').value.trim(),
        password: $('#reg-password').value,
        ochrana_udaju_souhlas: $('#reg-ochrana').checked,
        zasady_verze: gdprMeta.zasady_verze,
        jazyk: gdprMeta.jazyk || 'cs',
      }),
    });
    sessionToken = data.token;
    localStorage.setItem(`rez_token_${SALON_ID}`, sessionToken);
    msg.textContent = 'Registrace OK.';
    msg.className = 'status-msg success';
    loadMoje();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
});

$('#form-prihlaseni').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#moje-login-msg');
  const fallback = $('#heslo-fallback');
  fallback.classList.add('hidden');
  fallback.innerHTML = '';
  msg.textContent = 'Přihlašuji…';
  msg.className = 'status-msg';

  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/zakaznik/prihlaseni/`, {
      method: 'POST',
      body: JSON.stringify({
        email: $('#login-email').value.trim(),
        password: $('#login-password').value,
      }),
    });
    sessionToken = data.token;
    localStorage.setItem(`rez_token_${SALON_ID}`, sessionToken);
    msg.textContent = '';
    loadMoje();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-zapomenute-heslo').addEventListener('click', async () => {
  const email = $('#login-email').value.trim();
  const msg = $('#moje-login-msg');
  const fallback = $('#heslo-fallback');
  fallback.classList.add('hidden');
  if (!email) {
    msg.textContent = 'Nejdříve zadejte e-mail.';
    msg.className = 'status-msg error';
    return;
  }
  msg.textContent = 'Odesílám nové heslo…';
  msg.className = 'status-msg';
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/zakaznik/zapomenute-heslo/`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    msg.textContent = data.message;
    msg.className = `status-msg ${data.email_odeslan !== false ? 'success' : 'error'}`;
    if (data.heslo) {
      fallback.innerHTML = `<strong>Nové heslo (e-mail se neodeslal):</strong> <code>${esc(data.heslo)}</code>`;
      fallback.classList.remove('hidden');
      $('#login-password').value = data.heslo;
    }
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-odhlasit').addEventListener('click', () => {
  sessionToken = null;
  localStorage.removeItem(`rez_token_${SALON_ID}`);
  $('#moje-seznam').classList.add('hidden');
  $('#moje-login').classList.remove('hidden');
});

$('#form-admin-login').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#admin-login-msg');
  msg.textContent = 'Přihlašuji…';
  msg.className = 'status-msg';
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/staff/prihlaseni/`, {
      method: 'POST',
      body: JSON.stringify({
        prihlasovaci_jmeno: $('#staff-login').value.trim(),
        password: $('#staff-password').value,
      }),
    });
    staffToken = data.token;
    staffUser = data.staff;
    sessionStorage.setItem(`staff_token_${SALON_ID}`, staffToken);
    sessionStorage.setItem(`staff_user_${SALON_ID}`, JSON.stringify(staffUser));
    $('#admin-login').classList.add('hidden');
    $('#admin-panel').classList.remove('hidden');
    applyStaffUI();
    adminCalMonth = new Date();
    adminCalMonth.setDate(1);
    loadAdminKalendar();
    if (isMajitel()) loadNastaveni();
    msg.textContent = '';
  } catch (err) {
    staffToken = '';
    staffUser = null;
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-staff-logout')?.addEventListener('click', async () => {
  try {
    await api(`/salon/${SALON_ID}/rezervace/staff/odhlaseni/`, { method: 'POST' });
  } catch { /* ignore */ }
  staffToken = '';
  staffUser = null;
  sessionStorage.removeItem(`staff_token_${SALON_ID}`);
  sessionStorage.removeItem(`staff_user_${SALON_ID}`);
  $('#admin-panel').classList.add('hidden');
  $('#admin-login').classList.remove('hidden');
});

async function restoreStaffSession() {
  if (!staffToken) return;
  try {
    staffUser = await api(`/salon/${SALON_ID}/rezervace/staff/me/`);
    sessionStorage.setItem(`staff_user_${SALON_ID}`, JSON.stringify(staffUser));
    $('#admin-login').classList.add('hidden');
    $('#admin-panel').classList.remove('hidden');
    applyStaffUI();
    adminCalMonth = new Date();
    adminCalMonth.setDate(1);
    loadAdminKalendar();
    if (isMajitel()) loadNastaveni();
  } catch {
    staffToken = '';
    staffUser = null;
    sessionStorage.removeItem(`staff_token_${SALON_ID}`);
    sessionStorage.removeItem(`staff_user_${SALON_ID}`);
  }
}
restoreStaffSession();

$$('[data-admin]').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.admin-section').forEach(s => s.classList.add('hidden'));
    const sec = $(`#admin-${btn.dataset.admin}`);
    sec.classList.remove('hidden');
    if (btn.dataset.admin === 'kalendar') loadAdminKalendar();
    if (btn.dataset.admin === 'kadernice') loadStaff();
    if (btn.dataset.admin === 'statistiky') loadStats();
    if (btn.dataset.admin === 'noshow') loadNoShowArchiv();
    if (btn.dataset.admin === 'nastaveni') loadNastaveni();
    if (btn.dataset.admin === 'audit') loadAuditLog();
  });
});

$('#audit-prev')?.addEventListener('click', () => { if (auditPage > 1) loadAuditLog(auditPage - 1); });
$('#audit-next')?.addEventListener('click', () => loadAuditLog(auditPage + 1));

$('#cal-prev').addEventListener('click', () => {
  adminCalMonth.setMonth(adminCalMonth.getMonth() - 1);
  loadAdminKalendar();
});
$('#cal-next').addEventListener('click', () => {
  adminCalMonth.setMonth(adminCalMonth.getMonth() + 1);
  loadAdminKalendar();
});
$('#cal-day-close').addEventListener('click', () => {
  $('#cal-day-detail').classList.add('hidden');
  $$('#cal-grid .cal-cell').forEach((c) => c.classList.remove('selected'));
});

$('#noshow-cancel').addEventListener('click', closeNoShowModal);
$('#noshow-modal .modal-backdrop').addEventListener('click', closeNoShowModal);
$('#noshow-search-btn').addEventListener('click', () => {
  noshowQuery = $('#noshow-search').value.trim();
  loadNoShowArchiv(1);
});
$('#noshow-search').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    noshowQuery = $('#noshow-search').value.trim();
    loadNoShowArchiv(1);
  }
});
$('#noshow-confirm').addEventListener('click', async () => {
  if (!pendingNoShowId) return;
  const msg = $('#noshow-modal-msg');
  msg.textContent = 'Ukládám…';
  msg.className = 'status-msg';
  try {
    const res = await api(`/salon/${SALON_ID}/rezervace/admin/${pendingNoShowId}/no-show/`, {
      method: 'POST',
      body: JSON.stringify({
        odeslat_upozorneni: $('#noshow-send-email').checked,
        blokovat_email: $('#noshow-block-email').checked,
      }),
    });
    closeNoShowModal();
    await refreshCalDayAfterChange();
    let info = 'NO-show uložen.';
    if (res.email_odeslan) info += ' Upozornění odesláno.';
    if (res.reputace?.blokovan_v_salonu) info += ' E-mail zablokován (3+ NO-show v tomto salonu).';
    else if (res.reputace?.problematicky) info += ` E-mail je problematický (${res.reputace.pocet}× NO-show v tomto salonu).`;
    else if (res.zakaznik_blokovan) info += ' E-mail zablokován v tomto salonu.';
    alert(info);
  } catch (e) {
    msg.textContent = e.message;
    msg.className = 'status-msg error';
  }
});

$('#platba-cancel').addEventListener('click', closePlatbaModal);
$('#platba-modal .modal-backdrop').addEventListener('click', closePlatbaModal);
$('#platba-qr-close').addEventListener('click', closePlatbaQrModal);
$('#platba-qr-modal .modal-backdrop').addEventListener('click', closePlatbaQrModal);
$('#platba-confirm').addEventListener('click', async () => {
  if (!pendingPlatbaId) return;
  const msg = $('#platba-modal-msg');
  const castka = $('#platba-castka').value.trim();
  const ucet = $('#platba-ucet').value.trim();
  const vs = $('#platba-vs').value.trim();
  if (!castka || !ucet || !vs) {
    msg.textContent = 'Vyplňte částku, číslo účtu a variabilní symbol.';
    msg.className = 'status-msg error';
    return;
  }
  msg.textContent = 'Odesílám…';
  msg.className = 'status-msg';
  try {
    const res = await api(`/salon/${SALON_ID}/rezervace/admin/${pendingPlatbaId}/platba/`, {
      method: 'POST',
      body: JSON.stringify({ castka, ucet, variabilni_symbol: vs }),
    });
    closePlatbaModal();
    showPlatbaQrOnScreen(res);
  } catch (e) {
    msg.textContent = e.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-staff-deaktivovat')?.addEventListener('click', deactivateStaffAccount);

$('#btn-gdpr-export')?.addEventListener('click', async () => {
  const email = $('#gdpr-email')?.value.trim();
  const msg = $('#gdpr-admin-msg');
  if (!email) {
    msg.textContent = 'Zadejte e-mail zákazníka.';
    msg.className = 'status-msg error';
    return;
  }
  msg.textContent = 'Exportuji…';
  try {
    const data = await api(`/salon/${SALON_ID}/rezervace/admin/gdpr/export/?email=${encodeURIComponent(email)}`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `gdpr-export-${email.replace('@', '_')}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    msg.textContent = 'Export stažen.';
    msg.className = 'status-msg success';
  } catch (e) {
    msg.textContent = e.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-gdpr-vymaz')?.addEventListener('click', async () => {
  const email = $('#gdpr-email')?.value.trim();
  const msg = $('#gdpr-admin-msg');
  if (!email) {
    msg.textContent = 'Zadejte e-mail zákazníka.';
    msg.className = 'status-msg error';
    return;
  }
  if (!confirm(`Trvale vymazat osobní údaje zákazníka ${email}?\n\nRezervace zůstanou anonymizované pro statistiky.`)) return;
  msg.textContent = 'Mažu…';
  try {
    await api(`/salon/${SALON_ID}/rezervace/admin/gdpr/vymaz/`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    msg.textContent = 'Osobní údaje byly vymazány.';
    msg.className = 'status-msg success';
  } catch (e) {
    msg.textContent = e.message;
    msg.className = 'status-msg error';
  }
});

$('#btn-staff-add').addEventListener('click', addStaffMember);
$('#btn-staff-save-rozvrh').addEventListener('click', saveStaffRozvrh);

$('#form-staff-absence').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!selectedStaffId) return;
  try {
    await api(`/salon/${SALON_ID}/rezervace/admin/zamestnanci/${selectedStaffId}/absence/`, {
      method: 'POST',
      body: JSON.stringify({
        typ: $('#absence-typ').value,
        datum_od: $('#absence-od').value,
        datum_do: $('#absence-do').value,
        poznamka: $('#absence-poznamka').value.trim(),
      }),
    });
    $('#form-staff-absence').reset();
    await loadStaff();
  } catch (err) {
    alert(err.message);
  }
});

$('#form-staff-rezervace').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!selectedStaffId) return;
  const msg = $('#staff-rez-msg');
  const sluzby = [...$$('#staff-sluzby input:checked')].map((i) => parseInt(i.value, 10));
  if (!sluzby.length) {
    msg.textContent = 'Vyberte alespoň jednu službu.';
    msg.className = 'status-msg error';
    return;
  }
  const cas = $('#staff-rez-cas').value.slice(0, 5);
  msg.textContent = 'Vytvářím rezervaci…';
  msg.className = 'status-msg';
  try {
    await api(`/salon/${SALON_ID}/rezervace/admin/vytvorit/`, {
      method: 'POST',
      body: JSON.stringify({
        sluzby,
        datum: $('#staff-rez-datum').value,
        cas,
        zamestnanec_id: selectedStaffId,
        nick: $('#staff-rez-nick').value.trim(),
        email: $('#staff-rez-email').value.trim(),
        poznamka_zakaznika: $('#staff-rez-poznamka').value.trim(),
        poznamka_interni: $('#staff-rez-interni').value.trim(),
        typ_vytvoreni: 'osobne',
        stav: 'potvrzeno',
      }),
    });
    msg.textContent = 'Rezervace vytvořena.';
    msg.className = 'status-msg success';
    $('#form-staff-rezervace').reset();
    renderStaffSluzby();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
});

$('#form-nastaveni').addEventListener('submit', async (e) => {
  e.preventDefault();
  const storno = $('#nast-storno').value;
  try {
  await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`, {
    method: 'PUT',
    body: JSON.stringify({
      interval_minut: parseInt($('#nast-interval').value, 10),
      min_predstih_hodin: parseInt($('#nast-min-h').value, 10),
      max_predstih_mesicu: parseInt($('#nast-max-m').value, 10),
      storno_do_hodin: storno === '' ? null : parseInt(storno, 10),
      potvrzeni_platnost_hodin: parseInt($('#nast-potvrzeni-h').value, 10) || 24,
      gdpr_zasady_verze: $('#nast-gdpr-verze').value.trim() || '1.0',
      recenze_url: $('#nast-recenze-url').value.trim(),
      notifikace: collectNotifikace(),
    }),
  });
  alert('Nastavení uloženo.');
  loadNastaveni();
  } catch (err) {
    alert(err.message);
  }
});

// Init
const params = new URLSearchParams(location.search);
const stornoToken = params.get('storno');
const potvrditToken = params.get('potvrdit');
if (stornoToken) {
  loadInfo().then(() => handleStorno(stornoToken));
} else if (potvrditToken) {
  loadInfo().then(() => handlePotvrzeni(potvrditToken));
} else {
  loadInfo().then(() => { if (sessionToken) loadMoje(); });
}
