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
  no_show: 'Hříšníci',
};

const DEN_SHORT = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];
const OWNER_MENU_TABS = ['personal', 'persona', 'volno', 'hrisnici', 'platby', 'pravidla', 'sablony', 'audit'];
const TABS_WITH_NOVA = ['mujden', 'mesic', 'overview', 'karty'];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let ownerPersonalCache = [];
let ownerPersonalSelectedId = null;
let ownerStaffOptionsCache = null;
let ownerSluzbyCache = [];

let currentUser = null;
let dayOffset = 0;
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

/** Interní navigace FLOW (záložky) — nezávislá na historii prohlížeče. */
let flowNavStack = [];
let flowNavCurrent = null;
let flowNavSilent = false;

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

let flowConfirmResolver = null;

function askFlowConfirm({
  title = 'Potvrdit',
  text = '',
  okLabel = 'Ano',
  cancelLabel = 'Zpět',
} = {}) {
  return new Promise((resolve) => {
    if (flowConfirmResolver) flowConfirmResolver(false);
    const modal = $('#flow-confirm-modal');
    const titleEl = $('#flow-confirm-title');
    const textEl = $('#flow-confirm-text');
    const okBtn = $('#flow-confirm-ok');
    const cancelBtn = $('#flow-confirm-cancel');
    if (!modal || !okBtn) {
      resolve(window.confirm(text || title));
      return;
    }
    if (titleEl) titleEl.textContent = title;
    if (textEl) textEl.textContent = text;
    okBtn.textContent = okLabel;
    if (cancelBtn) cancelBtn.textContent = cancelLabel;
    flowConfirmResolver = resolve;
    modal.classList.remove('hidden');
    okBtn.focus();
  });
}

function closeFlowConfirm(ok) {
  $('#flow-confirm-modal')?.classList.add('hidden');
  const resolve = flowConfirmResolver;
  flowConfirmResolver = null;
  if (resolve) resolve(!!ok);
}

/** Výrazné varování po stornu rezervace se zaplacenou zálohou (partner ↔ zákazník). */
function showZalohaStornoBanner(data = {}) {
  const box = $('#storno-zaloha-banner');
  if (!box) return;
  const castka = data.zaloha_castka ? ` ${data.zaloha_castka} Kč` : '';
  const emailOk = data.email_odeslan === true;
  const emailLine = emailOk
    ? 'Zákazníkovi byl odeslán e-mail s žádostí, aby zavolal a domluvil vrácení nebo přesun zálohy.'
    : 'E-mail se nepodařilo doručit (např. localhost bez SMTP) — zavolejte zákazníkovi sami.';
  box.hidden = false;
  box.classList.remove('hidden');
  box.innerHTML = `
    <div class="flow-alert-text">
      <strong>!! POZOR — zaplacená záloha${esc(castka)}</strong>
      <span>Informujeme zákazníka, aby se domluvil na vrácení / přesunu zálohy. ${esc(emailLine)}</span>
    </div>
    <button type="button" class="btn tiny ghost" id="btn-dismiss-zaloha-storno">OK</button>
  `;
  $('#btn-dismiss-zaloha-storno')?.addEventListener('click', () => {
    box.hidden = true;
    box.classList.add('hidden');
    box.innerHTML = '';
  });
}

let emailPreviewResolve = null;

function closeEmailPreviewSheet(result = null) {
  const sheet = $('#email-preview-sheet');
  if (sheet) {
    sheet.classList.add('hidden');
  }
  const msg = $('#email-preview-msg');
  if (msg) {
    msg.hidden = true;
    msg.textContent = '';
  }
  const resolve = emailPreviewResolve;
  emailPreviewResolve = null;
  if (resolve) resolve(result);
}

function openEmailPreviewSheet({
  title = 'Náhled e-mailu',
  to = '',
  predmet = '',
  text = '',
  hint = '',
  confirmLabel = 'Odeslat e-mail',
  skipSend = false,
} = {}) {
  return new Promise((resolve) => {
    emailPreviewResolve = resolve;
    $('#email-preview-title').textContent = title;
    $('#email-preview-to').textContent = to || '— (bez e-mailu)';
    $('#email-preview-predmet').value = predmet || '';
    $('#email-preview-text').value = text || '';
    const hintEl = $('#email-preview-hint');
    if (hintEl) {
      if (hint) {
        hintEl.hidden = false;
        hintEl.textContent = hint;
      } else {
        hintEl.hidden = true;
        hintEl.textContent = '';
      }
    }
    const sendBtn = $('#email-preview-send');
    if (sendBtn) {
      sendBtn.textContent = skipSend || !to
        ? 'Potvrdit bez e-mailu'
        : (confirmLabel || 'Odeslat e-mail');
    }
    $('#email-preview-sheet')?.classList.remove('hidden');
    $('#email-preview-text')?.focus();
  });
}

async function previewFlowEmail(rezervaceId, typ, extra = {}) {
  return api(`/flow/rezervace/${rezervaceId}/email-preview/`, {
    method: 'POST',
    body: JSON.stringify({ typ, ...extra }),
  });
}

/** Náhled → úprava → výsledek { predmet, text } | null (zrušeno). */
async function reviewCustomerEmail(rezervaceId, typ, extra = {}, sheetOpts = {}) {
  const draft = await previewFlowEmail(rezervaceId, typ, extra);
  if (!draft?.ma_email && typ !== 'storno' && typ !== 'platba' && typ !== 'zaloha') {
    throw new Error('Rezervace nemá e-mail zákazníka.');
  }
  let hint = sheetOpts.hint || '';
  if (draft.zaloha_zaplacena) {
    hint = (hint ? `${hint} ` : '')
      + '!! Zaplacená záloha — v textu musí zůstat výzva k telefonické domluvě.';
  }
  if (draft.qr_note) {
    hint = (hint ? `${hint} ` : '') + draft.qr_note;
  }
  const result = await openEmailPreviewSheet({
    title: draft.title || sheetOpts.title || 'Náhled e-mailu',
    to: draft.to,
    predmet: draft.predmet,
    text: draft.text,
    hint,
    confirmLabel: sheetOpts.confirmLabel,
    skipSend: !draft.ma_email,
  });
  return result;
}

function wireEmailPreviewSheet() {
  const send = () => {
    const to = ($('#email-preview-to')?.textContent || '').trim();
    const hasEmail = to && to !== '—' && !to.includes('bez e-mailu');
    closeEmailPreviewSheet({
      predmet: $('#email-preview-predmet')?.value || '',
      text: $('#email-preview-text')?.value || '',
      sendEmail: !!hasEmail,
    });
  };
  $('#email-preview-send')?.addEventListener('click', send);
  $('#email-preview-cancel')?.addEventListener('click', () => closeEmailPreviewSheet(null));
  $('#email-preview-close')?.addEventListener('click', () => closeEmailPreviewSheet(null));
  $('#email-preview-sheet')?.addEventListener('click', (e) => {
    if (e.target?.id === 'email-preview-sheet') closeEmailPreviewSheet(null);
  });
}


/** Jednorázové zobrazení dočasného FLOW hesla majiteli (i po úspěšném e-mailu). */
function showFlowAccessResult(el, data, fallbackDetail) {
  if (!el) return;
  const detail = data?.detail || fallbackDetail || 'Hotovo.';
  const heslo = (data?.docasne_heslo || '').trim();
  el.hidden = false;
  el.className = 'msg ok';
  if (!heslo) {
    el.textContent = detail;
    return;
  }
  el.innerHTML = `
    <span>${esc(detail)}</span>
    <span class="flow-temp-pass">
      Dočasné heslo:
      <code class="flow-temp-pass-val">${esc(heslo)}</code>
      <button type="button" class="btn tiny ghost btn-copy-flow-pass">Kopírovat</button>
    </span>
  `;
  el.querySelector('.btn-copy-flow-pass')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    try {
      await navigator.clipboard.writeText(heslo);
      if (btn) btn.textContent = 'Zkopírováno';
    } catch {
      if (btn) btn.textContent = 'Nepodařilo se';
    }
  });
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

function dayRange(offset) {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + offset);
  const ymd = toYmd(d);
  return { od: ymd, do: ymd, start: d, end: d };
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

function formatDayLabel(range) {
  const d = range.start;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const label = d.toLocaleDateString('cs-CZ', {
    weekday: 'long',
    day: 'numeric',
    month: 'numeric',
    year: 'numeric',
  });
  if (toYmd(d) === toYmd(today)) return `Dnes · ${label}`;
  return label;
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

function isOwnerUser(user = currentUser) {
  const z = user?.zamestnanec;
  return z?.je_owner === true || z?.je_majitel === true || z?.role === 'majitel';
}

function isManagerAccount(user = currentUser) {
  return !!user?.persona?.muze_prepinat
    || !!user?.persona?.pracovnik?.id
    || isOwnerUser(user);
}

function hasManagerWorkPersona(user = currentUser) {
  return !!user?.persona?.pracovnik?.id;
}

function applyAbsenceFormUi(user = currentUser) {
  const form = $('#form-absence');
  const hint = $('#abs-manager-hint');
  const absBtn = $('#abs-submit');
  if (!form) return;
  if (isManagerAccount(user) && !hasManagerWorkPersona(user)) {
    form.classList.add('hidden');
    if (hint) {
      hint.classList.remove('hidden');
      hint.textContent = 'Účet Manager nepracuje — dovolená sem nepatří. Zapněte „Manager obsluhuje“, nebo zadejte absenci ve Volno.';
    }
    return;
  }
  form.classList.remove('hidden');
  if (isManagerAccount(user) && hasManagerWorkPersona(user)) {
    if (hint) {
      hint.classList.remove('hidden');
      const jmeno = user.persona.pracovnik.jmeno || 'pracovní profil';
      hint.textContent = `Dovolená platí pro váš pracovní profil (${jmeno}) — jeden člověk, jeden kalendář obsluhy. Uloží se hned bez schvalování.`;
    }
    if (absBtn) absBtn.textContent = 'Uložit absenci';
  } else {
    if (hint) {
      hint.classList.add('hidden');
      hint.textContent = '';
    }
    if (absBtn) absBtn.textContent = 'Požádat o volno';
  }
}

function canSwitchPersona(user = currentUser) {
  return !!user?.persona?.muze_prepinat;
}

function renderPersonaSwitch(user = currentUser) {
  const box = $('#persona-switch');
  if (!box) return;
  if (!canSwitchPersona(user)) {
    box.classList.add('hidden');
    return;
  }
  box.classList.remove('hidden');
  const aktivni = user?.persona?.aktivni || 'majitel';
  $$('#persona-switch .persona-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.persona === aktivni);
  });
}

async function switchPersona(persona) {
  const data = await api('/flow/prepnout-personu/', {
    method: 'POST',
    body: JSON.stringify({ persona }),
  });
  showLoggedIn(data);
}

function applyPersonaUi(user = currentUser) {
  renderPersonaSwitch(user);
}

function updateFlowBackBtn() {
  const btn = $('#btn-flow-back');
  if (!btn) return;
  const can = flowNavStack.length > 0;
  btn.disabled = !can;
  btn.setAttribute('aria-disabled', can ? 'false' : 'true');
}

function resetFlowNav(tab = 'mujden') {
  flowNavStack = [];
  flowNavCurrent = tab;
  flowNavSilent = false;
  updateFlowBackBtn();
}

function pushFlowNav(tab) {
  if (flowNavSilent) return;
  if (flowNavCurrent && flowNavCurrent !== tab) {
    flowNavStack.push(flowNavCurrent);
    if (flowNavStack.length > 40) flowNavStack.shift();
  }
  flowNavCurrent = tab;
  updateFlowBackBtn();
}

function goFlowBack() {
  const prev = flowNavStack.pop();
  updateFlowBackBtn();
  if (!prev) return;
  flowNavSilent = true;
  try {
    setTab(prev);
    flowNavCurrent = prev;
  } finally {
    flowNavSilent = false;
    updateFlowBackBtn();
  }
}

function setTab(name) {
  if (name === 'sprava') name = isOwnerUser() ? 'personal' : 'mujden';
  if (OWNER_MENU_TABS.includes(name) && !isOwnerUser()) {
    name = 'mujden';
  }
  pushFlowNav(name);
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.pane').forEach((p) => p.classList.add('hidden'));
  $('#btn-nova-rez')?.classList.toggle('hidden', !TABS_WITH_NOVA.includes(name));
  if (OWNER_MENU_TABS.includes(name)) {
    $('#pane-sprava')?.classList.remove('hidden');
    openOwnerSection(name);
    return;
  }
  const pane = $(`#pane-${name}`);
  if (pane) pane.classList.remove('hidden');
  if (name === 'mujden') loadWeekList(false);
  if (name === 'mesic') loadMonth();
  if (name === 'rozvrh') loadRozvrh();
  if (name === 'overview') loadOverview();
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
  const owner = isOwnerUser(user);
  // UI: Manager účet vždy jako „Manager“ (ne DB jméno typu Majitelka); Staff = jméno.
  $('#home-name').textContent = owner
    ? 'Manager'
    : (user.zamestnanec?.jmeno || 'Staff');
  $('#home-salon').textContent = user.salon?.name || '—';
  const displayName = $('#home-name').textContent;
  const salonName = $('#home-salon').textContent;
  if ($('#sidebar-name')) $('#sidebar-name').textContent = displayName;
  if ($('#sidebar-salon')) $('#sidebar-salon').textContent = salonName;
  if ($('#sidebar-initials')) {
    const parts = displayName.split(/\s+/).filter(Boolean);
    $('#sidebar-initials').textContent = parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : displayName.slice(0, 2).toUpperCase();
  }
  $('#home-email').textContent = user.email || '—';
  $('#home-overview').textContent = user.visible_overview ? 'zapnuto' : 'vypnuto';
  applyFlowBanner(user.salon);
  const ovTab = $('#tab-overview');
  if (ovTab) {
    const showOv = owner || !!user.visible_overview;
    ovTab.classList.toggle('hidden', !showOv);
  }
  $('#pwd-box-staff')?.classList.toggle('hidden', owner);
  $('#pwd-box-owner')?.classList.toggle('hidden', !owner);
  $$('.tab-owner').forEach((t) => {
    const tech = t.classList.contains('tab-tech');
    const allow = owner && (!tech || !!user.povolit_technicke_nastaveni);
    t.classList.toggle('hidden', !allow);
  });
  $('#tab-sprava')?.classList.add('hidden');
  $('#tab-rozvrh')?.classList.toggle('hidden', owner);
  // Badge vedle salonu je redundantní, když je nadpis už „Manager“.
  $('#home-role-badge')?.classList.add('hidden');
  // Manager: dovolená ve Volno. Staff má záložku Dovolená.
  const absTab = $('#tab-absence');
  if (absTab) {
    absTab.classList.toggle('hidden', owner);
    if (owner && flowNavCurrent === 'absence') {
      flowNavSilent = true;
      setTab('mujden');
      flowNavSilent = false;
      flowNavCurrent = 'mujden';
    }
  }
  applyAbsenceFormUi(user);
  refreshOwnerVolnoBadge(user);
  const roleEl = $('#home-role');
  if (roleEl) roleEl.textContent = owner ? 'Manager' : 'Staff';
  applyPersonaUi(user);
  applyTechnickeNastaveniUi(user);
  applyMaterialnikUi(user);
  // Staff: pracovní doba jen view; majitel ji mění ve Staff
  const rozHint = $('#rozvrh-hint');
  const rozSave = $('#btn-rozvrh-save');
  if (!owner) {
    if (rozHint) {
      rozHint.textContent = 'Vaše pracovní doba (jen náhled). Změnu může udělat jen Manager ve Staff.';
    }
    rozSave?.classList.add('hidden');
  } else {
    if (rozHint) {
      rozHint.textContent = 'Účet Manager nemá vlastní rozvrh služeb. Rozvrh Staff upravíte v Personál → Staff.';
    }
    rozSave?.classList.add('hidden');
  }
  resetFlowNav(null);
  flowNavSilent = true;
  const startTab = (owner || user.visible_overview) ? 'overview' : 'mujden';
  setTab(startTab);
  flowNavSilent = false;
  flowNavCurrent = startTab;
  updateFlowBackBtn();
  refreshTopAlerts();
}

function showLogin() {
  currentUser = null;
  riskyAlertItems = [];
  mailUnseenCount = 0;
  resetFlowNav(null);
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
  $('#btn-materialnik')?.classList.add('hidden');
  closeMaterialnikModal();
}

function renderRezervaceList(container, items, { readonly = false, emptyText = 'Žádné rezervace.', withStaff = false } = {}) {
  if (!items.length) {
    container.innerHTML = `<p class="empty">${esc(emptyText)}</p>`;
    return;
  }
  const showStaff = withStaff || isOwnerUser();
  container.innerHTML = items.map((r) => {
    const badges = [];
    const riskyOpen = r.je_rizikova && !r.zaloha_ok_at && !r.zaloha_nepozadovana_at;
    if (riskyOpen) badges.push('<span class="badge warn">riziková</span>');
    if (r.zaloha_nepozadovana_at && !r.zaloha_ok_at) {
      badges.push('<span class="badge ok">bez zálohy</span>');
    }
    if (r.zaloha_vyzadana_at && !r.zaloha_ok_at && !r.zaloha_nepozadovana_at) {
      badges.push('<span class="badge warn">čeká záloha</span>');
    }
    if (r.zaloha_ok_at) badges.push('<span class="badge ok">záloha OK</span>');
    const staffLine = (showStaff || readonly) && r.zamestnanec_jmeno
      ? `<p class="meta">u ${esc(r.zamestnanec_jmeno)}</p>`
      : '';
    const showZalohaAsk = (r.je_rizikova || r.zaloha_vyzadana_at) && !r.zaloha_ok_at;
    const showZalohaSkip = r.je_rizikova && !r.zaloha_ok_at && !r.zaloha_nepozadovana_at;
    const actions = (!readonly && canAct(r))
      ? `<div class="actions">
          <button type="button" class="btn tiny primary" data-act="done" data-id="${r.id}">Proběhla</button>
          <button type="button" class="btn tiny danger" data-act="noshow" data-id="${r.id}">Hříšníci</button>
          <button type="button" class="btn tiny ghost" data-act="platba" data-id="${r.id}">Platba QR</button>
          ${showZalohaAsk ? `<button type="button" class="btn tiny ghost" data-act="zaloha" data-id="${r.id}">Požádat o zálohu</button>` : ''}
          ${showZalohaSkip ? `<button type="button" class="btn tiny ghost" data-act="zaloha-skip" data-id="${r.id}">Nepožadujeme zálohu</button>` : ''}
          ${r.zaloha_vyzadana_at && !r.zaloha_ok_at && !r.zaloha_nepozadovana_at ? `<button type="button" class="btn tiny primary" data-act="zaloha-ok" data-id="${r.id}">Záloha OK</button>` : ''}
          <button type="button" class="btn tiny ${r.zaloha_ok_at ? 'danger' : 'ghost'}" data-act="storno" data-id="${r.id}">${r.zaloha_ok_at ? 'Storno · záloha!' : 'Storno'}</button>
        </div>`
      : (readonly && !showStaff
        ? `<p class="meta">u ${esc(r.zamestnanec_jmeno || '—')}</p>`
        : '');
    return `<article class="item stav-${esc(r.stav)}${riskyOpen ? ' risky' : ''}" data-id="${r.id}">
      <div class="item-top">
        <time>${esc(formatDateTime(r.zacatek))}</time>
        <span class="badge">${esc(STAV_LABEL[r.stav] || r.stav)}</span>
        ${badges.join(' ')}
      </div>
      <p class="item-title">${esc(r.kontaktni_jmeno || r.jmeno_host || 'Zákazník')}</p>
      <p class="meta">${esc(sluzbyText(r))}</p>
      ${r.kontaktni_email ? `<p class="meta">${esc(r.kontaktni_email)}</p>` : ''}
      ${staffLine}
      ${actions}
    </article>`;
  }).join('');
}

function renderAbsenceBlocks(absences, { withName = false, canDelete = false } = {}) {
  if (!absences.length) return '';
  return absences.map((a) => {
    const who = withName ? `<span class="meta"> — ${esc(a.zamestnanec_jmeno || '')}</span>` : '';
    const canDel = canDelete && (a.stav !== 'schvaleno' || isOwnerUser());
    const delLabel = a.stav === 'ceka' ? 'Stáhnout žádost' : 'Smazat';
    const del = canDel
      ? `<div class="actions" data-abs-del-wrap="${a.id}">
          <button type="button" class="btn tiny ghost" data-abs-del="${a.id}">${delLabel}</button>
        </div>`
      : '';
    const stavBadge = a.stav === 'ceka'
      ? '<span class="badge warn-soft">čeká na schválení</span>'
      : (a.stav === 'zamitnuto' ? '<span class="badge">zamítnuto</span>' : '');
    return `<article class="item absence stav-${esc(a.stav || 'schvaleno')}">
      <div class="item-top">
        <time>${esc(formatDate(a.datum_od))} – ${esc(formatDate(a.datum_do))}</time>
        <span class="badge">${esc(a.typ_label || a.typ)}</span>
        ${stavBadge}
      </div>
      <p class="meta">${esc(a.poznamka || 'Absence')}${who}</p>
      ${del}
    </article>`;
  }).join('');
}

function renderOverviewStats(data) {
  const setText = (id, n) => {
    const el = $(id);
    if (el) el.textContent = n;
  };
  setText('#ov-kpi-dnes', String(data.dnes ?? '—'));
  setText('#ov-kpi-tyden', String(data.tyden ?? '—'));
  setText('#ov-kpi-zaloha', String(data.ceka_zaloha ?? '—'));
  setText('#ov-kpi-hotovo', String(data.dokonceno ?? '—'));
  const hotovoHint = $('#ov-kpi-hotovo-hint');
  if (hotovoHint && data.dokonceno_mesic != null) {
    hotovoHint.textContent = `tento měsíc ${data.dokonceno_mesic}`;
  }
  setText('#ov-kpi-trzba-mesic', fmtMoneyCz(data.trzba_mesic));
  setText('#ov-kpi-trzba', fmtMoneyCz(data.trzba_celkem));

  const chart = $('#ov-chart');
  if (chart) {
    const counts = Array.isArray(data.tyden_pocty) ? data.tyden_pocty : [0, 0, 0, 0, 0, 0, 0];
    const max = Math.max(1, ...counts);
    chart.innerHTML = counts.map((n, i) => {
      const h = Math.max(4, Math.round((n / max) * 100));
      return `<div class="col"><b style="height:${h}px"></b><span>${DEN_SHORT[i]}</span></div>`;
    }).join('');
  }

  const sluzbyEl = $('#ov-sluzby');
  if (sluzbyEl) {
    const rows = data.nejprodavanejsi_sluzby || [];
    if (!rows.length) {
      sluzbyEl.innerHTML = '<p class="empty">Zatím žádné dokončené služby.</p>';
    } else {
      sluzbyEl.innerHTML = rows.map((s) => (
        `<div class="rank-row"><b>${esc(s.sluzba__nazev || '—')}</b>`
        + `<span>${esc(s.pocet)}× · ${fmtMoneyCz(s.trzba)}</span></div>`
      )).join('');
    }
  }

  const staffEl = $('#ov-staff');
  if (staffEl) {
    const people = data.zamestnanci || [];
    if (!people.length) {
      staffEl.innerHTML = '<p class="empty">Žádný personál.</p>';
    } else {
      staffEl.innerHTML = people.map((p) => {
        const name = p.jmeno || '—';
        const parts = String(name).split(/\s+/).filter(Boolean);
        const ini = parts.length >= 2
          ? (parts[0][0] + parts[1][0]).toUpperCase()
          : String(name).slice(0, 2).toUpperCase();
        const avatar = p.fotka
          ? `<img src="${esc(p.fotka)}" alt="" width="44" height="44">`
          : `<span class="ph">${esc(ini)}</span>`;
        return `<article class="staff-stat">${avatar}<div>
          <strong>${esc(name)}</strong>
          <span>${esc(p.dokonceno_mesic || 0)} tento měsíc · ${fmtMoneyCz(p.trzba_mesic)}</span>
          <span>celkem ${esc(p.dokonceno || 0)} · ${fmtMoneyCz(p.trzba)}</span>
        </div></article>`;
      }).join('');
    }
  }
}

async function loadOverviewStats() {
  try {
    const data = await api('/flow/owner/statistiky/');
    renderOverviewStats(data);
  } catch (err) {
    const msg = $('#ov-msg');
    if (msg) showMsg(msg, err.message, false);
  }
}

async function loadOverviewToday() {
  const range = dayRange(0);
  const listEl = $('#ov-list');
  const msgEl = $('#ov-msg');
  if (!listEl) return;
  if (msgEl) msgEl.hidden = true;
  listEl.innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const q = new URLSearchParams({ od: range.od, do: range.do });
    if (!isOwnerUser()) q.set('overview', '1');
    const data = await api(`/flow/kalendar/?${q}`);
    rememberRez(data.rezervace);
    listEl.innerHTML = '';
    const holder = document.createElement('div');
    renderRezervaceList(holder, data.rezervace || [], {
      readonly: !isOwnerUser(),
      withStaff: true,
      emptyText: 'Dnes v kalendáři nikdo není.',
    });
    listEl.appendChild(holder);
    if (isOwnerUser()) bindCalActions(holder, () => loadOverview());
  } catch (err) {
    listEl.innerHTML = '';
    if (msgEl) showMsg(msgEl, err.message, false);
  }
}

function loadOverview() {
  loadOverviewStats();
  loadOverviewToday();
}

async function loadWeekList(overview) {
  if (overview) {
    loadOverview();
    return;
  }
  const range = overview ? weekRange(ovWeekOffset) : dayRange(dayOffset);
  const labelEl = overview ? $('#ov-week-label') : $('#week-label');
  const listEl = overview ? $('#ov-list') : $('#cal-list');
  const msgEl = overview ? $('#ov-msg') : $('#cal-msg');
  labelEl.textContent = overview ? formatWeekLabel(range) : formatDayLabel(range);
  msgEl.hidden = true;
  listEl.innerHTML = '<p class="empty">Načítám…</p>';
  try {
    const q = new URLSearchParams({ od: range.od, do: range.do });
    if (overview && !isOwnerUser()) q.set('overview', '1');
    const data = await api(`/flow/kalendar/?${q}`);
    rememberRez(data.rezervace);
    const absHtml = renderAbsenceBlocks(data.absence || [], {
      withName: overview || isOwnerUser(),
      canDelete: false,
    });
    listEl.innerHTML = '';
    if (absHtml) {
      listEl.innerHTML += `<h3 class="list-h">Absence</h3>${absHtml}`;
    }
    listEl.innerHTML += `<h3 class="list-h">Rezervace</h3>`;
    const holder = document.createElement('div');
    renderRezervaceList(holder, data.rezervace || [], {
      readonly: false,
      withStaff: isOwnerUser(),
      emptyText: 'Žádné rezervace v tento den.',
    });
    listEl.appendChild(holder);
    bindCalActions(holder, () => loadWeekList(false));
    refreshRiskyInbox();
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
        const ok = await askFlowConfirm({
          title: 'Proběhlá služba',
          text: 'Označit rezervaci jako proběhlou?',
          okLabel: 'Ano, proběhla',
          cancelLabel: 'Zpět',
        });
        if (!ok) return;
        try {
          await api(`/flow/rezervace/${id}/dokonceno/`, { method: 'POST', body: '{}' });
          onDone?.();
          if (materialnikInfo()) await openMaterialnikSpotreba(id);
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'storno') {
        const r = findRezervace(id);
        let duvod = '';
        if (r?.zaloha_vyzadana_at && !r?.zaloha_ok_at) {
          duvod = 'Nezaplacená zálohová platba';
        }
        try {
          const reviewed = await reviewCustomerEmail(id, 'storno', { duvod }, {
            confirmLabel: 'Stornovat a odeslat',
            hint: r?.zaloha_ok_at
              ? 'Po potvrzení se rezervace zruší a e-mail odejde zákazníkovi.'
              : 'Zkontrolujte text e-mailu. Po potvrzení se rezervace zruší.',
          });
          if (!reviewed) return;
          const data = await api(`/flow/rezervace/${id}/storno/`, {
            method: 'DELETE',
            body: JSON.stringify({
              duvod,
              email_predmet: reviewed.predmet,
              email_text: reviewed.text,
            }),
          });
          onDone?.();
          refreshTopAlerts();
          if (data?.zaloha_zaplacena || r?.zaloha_ok_at) {
            showZalohaStornoBanner(data || { zaloha_zaplacena: true, zaloha_castka: r?.zaloha_castka });
            showMsg($('#cal-msg'), 'Stornováno. !! POZOR — zaplacená záloha, domluvte vrácení se zákazníkem.', false);
          } else {
            showMsg($('#cal-msg'), 'Rezervace stornována.', true);
          }
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'noshow') {
        openNoshow(id);
      } else if (act === 'platba') {
        openPlatba(id, false);
      } else if (act === 'zaloha') {
        openPlatba(id, true);
      } else if (act === 'zaloha-skip') {
        try {
          await api(`/flow/rezervace/${id}/zaloha-nepozadovat/`, {
            method: 'POST',
            body: '{}',
          });
          onDone?.();
          refreshTopAlerts();
          showMsg($('#cal-msg'), 'Záloha se nepožaduje — rezervace je mimo rizikové.', true);
        } catch (err) {
          showMsg($('#cal-msg'), err.message, false);
        }
      } else if (act === 'zaloha-ok') {
        try {
          const reviewed = await reviewCustomerEmail(id, 'zaloha_ok', {}, {
            confirmLabel: 'Potvrdit zálohu a odeslat',
          });
          if (!reviewed) return;
          await api(`/flow/rezervace/${id}/zaloha-ok/`, {
            method: 'POST',
            body: JSON.stringify({
              email_predmet: reviewed.predmet,
              email_text: reviewed.text,
            }),
          });
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
  return (absences || []).some((a) =>
    (a.stav || 'schvaleno') === 'schvaleno'
    && a.datum_od <= ymd
    && a.datum_do >= ymd
  );
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
      : (abs
        ? '<span class="m-hours">absence</span>'
        : (isOwnerUser()
          ? (count ? `<span class="m-hours">${count} rez.</span>` : '<span class="m-hours">—</span>')
          : '<span class="m-hours">volno</span>'));
    html += `<button type="button" class="${classes.join(' ')}" data-day="${ymd}">
      <span class="m-num">${day}</span>
      ${hours}
      ${count && !isOwnerUser() ? `<span class="m-count">${count}</span>` : ''}
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
  const readonly = true; // I4: editace jen ve Správě majitele
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
          <td><input type="checkbox" class="roz-volno" ${volno ? 'checked' : ''} disabled></td>
          <td><input type="time" class="roz-od" value="${esc(formatTime(r.od))}" disabled></td>
          <td><input type="time" class="roz-do" value="${esc(formatTime(r.do))}" disabled></td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
  if (!readonly) {
    box.querySelectorAll('.roz-volno').forEach((cb) => {
      cb.addEventListener('change', () => {
        const row = cb.closest('tr');
        row.querySelector('.roz-od').disabled = cb.checked;
        row.querySelector('.roz-do').disabled = cb.checked;
      });
    });
  }
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

function maKontaktniEmail(r) {
  return !!(r && String(r.kontaktni_email || '').trim());
}

async function openPlatba(id, asZaloha = false) {
  const r = findRezervace(id);
  platbaTarget = r || { id };
  platbaIsZaloha = !!asZaloha;
  const hasEmail = maKontaktniEmail(r);
  const title = $('#platba-modal h2');
  if (title) title.textContent = asZaloha ? 'Žádost o zálohu' : 'Žádost o platbu';
  let extra = '';
  if (asZaloha && hasEmail) extra = ' · záloha (lhůtu uveďte v e-mailové šabloně)';
  else if (asZaloha && !hasEmail) extra = ' · záloha — QR ukážete na obrazovce';
  else if (!hasEmail) extra = ' · QR ukážete zákazníkovi na obrazovce';
  $('#platba-info').textContent = r
    ? `${r.kontaktni_jmeno || 'Zákazník'} — ${formatDateTime(r.zacatek)}${extra}`
    : `Rezervace #${id}`;
  $('#platba-castka').value = r?.zaloha_castka || '';
  $('#platba-ucet').value = r?.zamestnanec_cislo_uctu || '';
  $('#platba-vs').value = String(id);
  const submitBtn = $('#platba-submit') || $('#form-platba button[type=submit]');
  if (submitBtn) submitBtn.textContent = hasEmail ? 'Odeslat QR e-mail' : 'Zobrazit QR';
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
    && !r.zaloha_nepozadovana_at
    && ['ceka', 'potvrzeno'].includes(r.stav)
  ));
}

function renderTopAlerts(riskyN, mailN, mailOk, volnoN = 0, platbyDni = 0) {
  const box = $('#flow-alerts');
  if (!box) return;
  const parts = [];
  if (platbyDni > 0 && isOwnerUser()) {
    parts.push(`<div class="flow-alert platby">
      <div class="flow-alert-text">
        <strong>Platba ULOV po splatnosti: +${platbyDni} dní</strong>
        <span>Zkontrolujte účet, VS a splatnost v Platbách</span>
      </div>
      <button type="button" class="btn primary sm" id="alert-goto-platby">Otevřít</button>
    </div>`);
  }
  if (volnoN > 0 && isOwnerUser()) {
    parts.push(`<div class="flow-alert volno">
      <div class="flow-alert-text">
        <strong>Žádosti o volno: ${volnoN}</strong>
        <span>Ke schválení — dovolená / nemoc Staff</span>
      </div>
      <button type="button" class="btn primary sm" id="alert-goto-volno">Otevřít</button>
    </div>`);
  }
  if (riskyN > 0) {
    parts.push(`<div class="flow-alert warn">
      <div class="flow-alert-text">
        <strong>Rizikové rezervace: ${riskyN}</strong>
        <span>Ke kontrole — záloha, nebo „Nepožadujeme zálohu“ u známého hosta</span>
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
  $('#alert-goto-platby')?.addEventListener('click', () => setTab('platby'));
  $('#alert-goto-volno')?.addEventListener('click', () => setTab('volno'));
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
  let volnoN = Number(currentUser.ceka_volno_pocet || 0);
  let platbyDni = Number(currentUser.po_splatnosti_dni || 0);
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
  if (isOwnerUser()) {
    try {
      const volno = await api('/flow/owner/absence/?stav=ceka');
      volnoN = Number(volno.ceka_pocet || 0);
      currentUser.ceka_volno_pocet = volnoN;
      refreshOwnerVolnoBadge(currentUser);
    } catch {
      /* badge zůstane z last known */
    }
    try {
      const platby = await api('/flow/owner/platby/');
      platbyDni = platby.je_po_splatnosti ? Number(platby.dni_po_splatnosti || 0) : 0;
      currentUser.po_splatnosti_dni = platbyDni;
    } catch {
      /* last known */
    }
  }
  renderTopAlerts(risky.length, unseen, mailOk, volnoN, platbyDni);
  refreshRiskyInbox();
  const mailTab = $('#tab-mail');
  if (mailTab) {
    const label = mailTab.querySelector('.tab-label') || mailTab;
    label.textContent = (mailOk && unseen > 0) ? `Mail (${unseen})` : 'Mail';
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
    <p class="hint tiny">Služby označené jako rizikové. Požádejte o zálohu, nebo u důvěryhodného hosta zvolte „Nepožadujeme zálohu“.</p>
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
      btn.addEventListener('click', () => {
        const id = btn.dataset.absDel;
        const wrap = list.querySelector(`[data-abs-del-wrap="${id}"]`);
        if (!wrap) return;
        const label = btn.textContent.trim() || 'Smazat';
        const showAsk = () => {
          wrap.innerHTML = `
            <button type="button" class="btn tiny danger" data-abs-del-ok="${id}">Ano, smazat</button>
            <button type="button" class="btn tiny ghost" data-abs-del-back="${id}">Zpět</button>
          `;
          wrap.querySelector(`[data-abs-del-back="${id}"]`)?.addEventListener('click', showBtn);
          wrap.querySelector(`[data-abs-del-ok="${id}"]`)?.addEventListener('click', async () => {
            try {
              await api(`/flow/absence/${id}/`, { method: 'DELETE' });
              $('#abs-konflikt')?.classList.add('hidden');
              loadAbsence();
            } catch (err) {
              showMsg($('#abs-msg'), err.message, false);
            }
          });
        };
        const showBtn = () => {
          wrap.innerHTML = `<button type="button" class="btn tiny ghost" data-abs-del="${id}">${esc(label)}</button>`;
          wrap.querySelector('[data-abs-del]')?.addEventListener('click', showAsk);
        };
        showAsk();
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

async function loadOwnerStaffOptions() {
  if (ownerStaffOptionsCache) return ownerStaffOptionsCache;
  const data = await api('/flow/owner/personal/');
  ownerStaffOptionsCache = (data.zamestnanci || []).filter((z) => z.role !== 'majitel' && z.aktivni !== false);
  return ownerStaffOptionsCache;
}

function staffUmiVybraneSluzbyFlow(z, selectedIds) {
  if (!selectedIds.length) return true;
  const assigned = (z.sluzby_ids || []).map(Number);
  if (!assigned.length) return true;
  return selectedIds.every((id) => assigned.includes(Number(id)));
}

function refreshNovaStaffSelect() {
  if (!isOwnerUser()) return;
  const sel = $('#nova-staff');
  if (!sel || !ownerStaffOptionsCache) return;
  const prev = sel.value;
  const selectedIds = selectedSluzbyIds();
  const eligible = ownerStaffOptionsCache.filter((z) => staffUmiVybraneSluzbyFlow(z, selectedIds));
  sel.innerHTML = eligible.length
    ? eligible.map((z) => `<option value="${z.id}">${esc(z.jmeno)}</option>`).join('')
    : '<option value="">— nikdo neumí vybrané služby —</option>';
  if (prev && eligible.some((z) => String(z.id) === String(prev))) {
    sel.value = prev;
  }
}

async function openNova(prefillDate = '', contact = null) {
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
  const staffWrap = $('#nova-staff-wrap');
  const hint = $('#nova-hint');
  if (isOwnerUser()) {
    staffWrap?.classList.remove('hidden');
    if (hint) hint.textContent = 'Vyberte pracovníka — rezervace se uloží na něj.';
    try {
      const staff = await loadOwnerStaffOptions();
      const sel = $('#nova-staff');
      if (sel) {
        sel.innerHTML = staff.length
          ? staff.map((z) => `<option value="${z.id}">${esc(z.jmeno)}</option>`).join('')
          : '<option value="">— žádný Staff —</option>';
      }
      refreshNovaStaffSelect();
    } catch (err) {
      showMsg(msg, err.message, false);
    }
  } else {
    staffWrap?.classList.add('hidden');
    if (hint) hint.textContent = 'Rezervace se uloží na vás a hned se propíše do kalendáře.';
  }
  $('#nova-modal').classList.remove('hidden');
  try {
    const sluzby = await ensureSluzby();
    if (!sluzby.length) {
      $('#nova-sluzby').innerHTML = '<p class="empty">Žádné aktivní služby v salonu.</p>';
      $('#nova-terminy-msg').textContent = '';
      applyNovaContactPrefill(contact);
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
    $('#nova-terminy-msg').textContent = isOwnerUser()
      ? 'Vyberte pracovníka, služby a datum — pak se načtou volné časy.'
      : 'Vyberte služby a datum — pak se načtou volné časy.';
    $$('#nova-sluzby input').forEach((cb) => cb.addEventListener('change', () => {
      refreshNovaStaffSelect();
      loadNovaTerminy();
    }));
    refreshNovaStaffSelect();
    loadNovaTerminy();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
  // Až po asynchronním načtení — jinak by se mohlo přepsat / zůstat prázdné.
  applyNovaContactPrefill(contact);
}

/** Předvyplnění kontaktu ze zákaznické karty do stávajícího formuláře. */
function applyNovaContactPrefill(contact) {
  if (!contact || typeof contact !== 'object') return;
  const nick = (contact.nick || contact.jmeno || '').trim();
  const email = (contact.email || '').trim();
  const telefon = (contact.telefon || '').trim();
  const poznamka = (contact.poznamka || '').trim();
  if (nick) $('#nova-nick').value = nick;
  if (email) {
    $('#nova-no-email').checked = false;
    $('#nova-email').disabled = false;
    $('#nova-email').value = email;
  }
  // Formulář nemá pole telefon — tel. + popis zákazníka do interní poznámky.
  const interniParts = [];
  if (telefon) interniParts.push(`Tel. ${telefon}`);
  if (poznamka) interniParts.push(poznamka);
  if (interniParts.length) $('#nova-interni').value = interniParts.join('\n');
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
  refreshNovaStaffSelect();
  const sluzby = selectedSluzbyIds();
  const datum = $('#nova-datum').value;
  if (!sluzby.length || !datum) {
    msg.textContent = 'Vyberte služby a datum.';
    return;
  }
  if (isOwnerUser() && !$('#nova-staff')?.value) {
    msg.textContent = 'Vyberte pracovníka.';
    return;
  }
  msg.textContent = 'Načítám volné termíny…';
  try {
    const q = new URLSearchParams({
      datum,
      sluzby: sluzby.join(','),
    });
    if (isOwnerUser()) q.set('zamestnanec_id', $('#nova-staff').value);
    const data = await api(`/flow/volne-terminy/?${q}`);
    if (data.zavreno || !data.terminy?.length) {
      msg.textContent = data.duvod || 'Žádný volný termín.';
      return;
    }
    msg.textContent = `${data.terminy.length} volných termínů`;
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
  else if (active === 'overview') loadOverview();
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
$('#btn-flow-back')?.addEventListener('click', () => goFlowBack());

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

$('#week-prev')?.addEventListener('click', () => { dayOffset -= 1; loadWeekList(false); });
$('#week-next')?.addEventListener('click', () => { dayOffset += 1; loadWeekList(false); });
$('#week-today')?.addEventListener('click', () => { dayOffset = 0; loadWeekList(false); });
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
$('#nova-staff')?.addEventListener('change', loadNovaTerminy);
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
    const body = {
      sluzby,
      datum: $('#nova-datum').value,
      cas,
      nick: $('#nova-nick').value.trim(),
      email,
      poznamka_zakaznika: $('#nova-pozn').value.trim(),
      poznamka_interni: $('#nova-interni').value.trim(),
      typ_vytvoreni: $('#nova-typ').value,
      stav: 'potvrzeno',
    };
    if (isOwnerUser()) {
      const staffId = Number($('#nova-staff')?.value || 0);
      if (!staffId) {
        showMsg(msg, 'Vyberte pracovníka.', false);
        return;
      }
      body.zamestnanec_id = staffId;
    }
    await api('/flow/rezervace/', {
      method: 'POST',
      body: JSON.stringify(body),
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

function renderAbsenceKonflikt(items, absence = null, { boxSel = '#abs-konflikt', msgSel = '#abs-msg', onDone = null } = {}) {
  const box = $(boxSel);
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
      <h3>${esc(typLabel)} schválena</h3>
      <p class="hint">V tomto období nejsou žádné aktivní rezervace — není co řešit.</p>
    `;
    return;
  }
  const listId = boxSel === '#own-volno-konflikt' ? 'own-volno-konflikt-list' : 'abs-konflikt-list';
  box.innerHTML = `
    <h3>Pozor: ${items.length} aktivní rezervace při „${esc(typLabel)}“</h3>
    <p class="hint">Nové termíny se zablokují kvůli ${esc(duvodText)}. U každé rezervace můžete převést na volného kolegu, nebo stornovat s omluvou.</p>
    <div class="list" id="${listId}"></div>
  `;
  const list = $(`#${listId}`);
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
      <div class="actions" data-abs-actions="${r.id}">
        <button type="button" class="btn tiny danger" data-abs-storno="${r.id}">Stornovat s omluvou</button>
      </div>
    </article>`;
  }).join('');

  const refreshLeft = (id) => {
    const left = items.filter((r) => r.id !== id);
    renderAbsenceKonflikt(left, absence, { boxSel, msgSel, onDone });
    if (typeof onDone === 'function') onDone();
  };

  list.querySelectorAll('[data-abs-prevest]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.absPrevest);
      const sel = list.querySelector(`select[data-abs-kolega="${id}"]`);
      const kolegaId = Number(sel?.value || 0);
      if (!kolegaId) {
        showMsg($(msgSel), 'Vyberte kolegu.', false);
        return;
      }
      const jmeno = sel.options[sel.selectedIndex]?.textContent || 'kolegu';
      try {
        await api(`/flow/rezervace/${id}/prevest/`, {
          method: 'POST',
          body: JSON.stringify({ zamestnanec_id: kolegaId }),
        });
        showMsg($(msgSel), `Rezervace převedena na ${jmeno}.`, true);
        refreshLeft(id);
      } catch (err) {
        showMsg($(msgSel), err.message, false);
      }
    });
  });

  list.querySelectorAll('[data-abs-storno]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = Number(btn.dataset.absStorno);
      const actions = list.querySelector(`[data-abs-actions="${id}"]`);
      if (!actions) return;

      const showAsk = () => {
        actions.innerHTML = `
          <p class="hint tiny">Do e-mailu zákazníkovi: ${esc(duvodZakaznik)}</p>
          <button type="button" class="btn tiny danger" data-abs-storno-ok="${id}">Ano, stornovat</button>
          <button type="button" class="btn tiny ghost" data-abs-storno-back="${id}">Zpět</button>
        `;
        actions.querySelector(`[data-abs-storno-back="${id}"]`)?.addEventListener('click', showBtn);
        actions.querySelector(`[data-abs-storno-ok="${id}"]`)?.addEventListener('click', async () => {
          try {
            const left = items.find((x) => Number(x.id) === id);
            const reviewed = await reviewCustomerEmail(id, 'storno', { duvod: duvodZakaznik }, {
              confirmLabel: 'Stornovat a odeslat',
              hint: 'Storno kvůli absenci — zkontrolujte omluvný e-mail.',
            });
            if (!reviewed) return;
            const data = await api(`/flow/rezervace/${id}/storno/`, {
              method: 'DELETE',
              body: JSON.stringify({
                duvod: duvodZakaznik,
                email_predmet: reviewed.predmet,
                email_text: reviewed.text,
              }),
            });
            if (data?.zaloha_zaplacena || left?.zaloha_ok_at) {
              showZalohaStornoBanner(data || { zaloha_zaplacena: true, zaloha_castka: left?.zaloha_castka });
              showMsg($(msgSel), 'Stornováno. !! POZOR — zaplacená záloha.', false);
            } else {
              showMsg($(msgSel), 'Rezervace stornována.', true);
            }
            refreshLeft(id);
          } catch (err) {
            showMsg($(msgSel), err.message, false);
          }
        });
      };

      const showBtn = () => {
        actions.innerHTML = `<button type="button" class="btn tiny danger" data-abs-storno="${id}">Stornovat s omluvou</button>`;
        actions.querySelector('[data-abs-storno]')?.addEventListener('click', showAsk);
      };

      showAsk();
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
    showMsg(msg, data.detail || 'Uloženo.', true);
    e.target.reset();
    if (data.ceka_na_schvaleni) {
      $('#abs-konflikt')?.classList.add('hidden');
    } else {
      renderAbsenceKonflikt(data.konfliktni_rezervace || [], data.absence || null, {
        onDone: () => loadAbsence(),
      });
    }
    loadAbsence();
    if (isOwnerUser()) refreshOwnerVolnoBadge(currentUser);
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#noshow-cancel')?.addEventListener('click', closeNoshow);
$('#noshow-confirm')?.addEventListener('click', async () => {
  if (!noshowTargetId) return;
  const msg = $('#noshow-msg');
  const sendMail = $('#noshow-send-email')?.checked;
  const targetId = noshowTargetId;
  try {
    let emailPayload = { odeslat_upozorneni: !!sendMail };
    if (sendMail) {
      const reviewed = await reviewCustomerEmail(targetId, 'noshow', {}, {
        confirmLabel: 'Uložit Hříšníci a odeslat',
      });
      if (!reviewed) return;
      emailPayload = {
        odeslat_upozorneni: true,
        email_predmet: reviewed.predmet,
        email_text: reviewed.text,
      };
    }
    await api(`/flow/rezervace/${targetId}/noshow/`, {
      method: 'POST',
      body: JSON.stringify(emailPayload),
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
  const targetId = platbaTarget.id;
  const payload = {
    castka: $('#platba-castka').value.trim(),
    ucet: $('#platba-ucet').value.trim(),
    variabilni_symbol: $('#platba-vs').value.trim(),
    zaloha: platbaIsZaloha,
  };
  try {
    const hasEmail = maKontaktniEmail(platbaTarget);
    const body = { ...payload };
    if (hasEmail) {
      const reviewed = await reviewCustomerEmail(
        targetId,
        platbaIsZaloha ? 'zaloha' : 'platba',
        payload,
        { confirmLabel: 'Odeslat e-mail s QR' },
      );
      if (!reviewed) return;
      body.email_predmet = reviewed.predmet;
      body.email_text = reviewed.text;
    }
    const data = await api(`/flow/rezervace/${targetId}/platba/`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    closePlatba();
    const qrTitle = $('#platba-qr-title') || $('#platba-qr-modal h2');
    if (qrTitle) {
      qrTitle.textContent = data.email_odeslan
        ? 'QR platba odeslána'
        : 'Ukažte kód zákazníkovi';
    }
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

let ownerNastaveniCache = null;

const OWN_NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u Hříšníci',
  'Žádost o úhradu po návštěvě (QR) — FLOW: Platba QR',
  'Žádost o zálohu před termínem (QR) — FLOW: Požádat o zálohu',
  'Storno rezervace — při zrušení salonem / ve FLOW',
  'Potvrzení rezervace — automaticky při potvrzení',
  'Záloha přijata — odešle se tlačítkem Záloha OK ve FLOW',
];

function showOwnerAdminHome() {
  setTab('personal');
}

function applyTechnickeNastaveniUi(user = currentUser) {
  const allowed = !!user?.povolit_technicke_nastaveni && isOwnerUser(user);
  $$('.tab-tech').forEach((t) => t.classList.toggle('hidden', !allowed));
  $('#owner-zone-tech')?.classList.toggle('hidden', !allowed);
}

function materialnikInfo(user = currentUser) {
  return user?.moduly?.materialnik || null;
}

function applyMaterialnikUi(user = currentUser) {
  const btn = $('#btn-materialnik');
  if (!btn) return;
  const info = materialnikInfo(user);
  if (!info || !info.url) {
    btn.classList.add('hidden');
    btn.removeAttribute('href');
    return;
  }
  btn.classList.remove('hidden');
  btn.href = info.url;
}

function closeMaterialnikModal() {
  $('#materialnik-modal')?.classList.add('hidden');
  const body = $('#materialnik-body');
  if (body) body.innerHTML = '';
}

async function openMaterialnikSpotreba(rezervaceId) {
  if (!materialnikInfo()) return;
  const modal = $('#materialnik-modal');
  const body = $('#materialnik-body');
  const msg = $('#materialnik-msg');
  const saveBtn = $('#materialnik-save');
  if (!modal || !body) return;
  modal.dataset.rezervaceId = String(rezervaceId);
  modal.classList.remove('hidden');
  body.innerHTML = '<p class="hint">Načítám předpis…</p>';
  if (msg) {
    msg.hidden = true;
    msg.textContent = '';
  }
  if (saveBtn) saveBtn.disabled = true;
  try {
    const data = await api(`/flow/rezervace/${rezervaceId}/materialnik-spotreba/`);
    if (data?.unavailable) {
      body.innerHTML = `<p class="hint">${esc(data.detail || 'Spotřebu teď nelze načíst. Rezervaci to neovlivní.')}</p>`;
      return;
    }
    const lines = Array.isArray(data?.lines) ? data.lines : [];
    if (!lines.length) {
      body.innerHTML = '<p class="hint">Pro tuto službu zatím není seznam materiálů. Spotřebu zadejte v Materiálníku.</p>';
      return;
    }
    body.innerHTML = `
      <label class="mat-filter">Najít materiál
        <input type="search" id="mat-filter" placeholder="např. 6.1">
      </label>
      <div class="table-wrap">
        <table class="materialnik-table">
          <thead>
            <tr><th>Služba</th><th>Materiál</th><th>Kolik jste vzali</th></tr>
          </thead>
          <tbody>
            ${lines.map((line, i) => `
              <tr data-i="${i}" data-search="${esc(((line.material_name || '') + ' ' + (line.service_name || '')).toLowerCase())}">
                <td>${esc(line.service_name || '')}</td>
                <td>
                  ${esc(line.material_name || '')}
                  ${line.recipe_qty ? `<div class="muted">obvykle ${esc(line.recipe_qty)} ${esc(line.unit || '')}</div>` : ''}
                </td>
                <td>
                  <input type="number" step="any" min="0" class="mat-qty"
                    value=""
                    placeholder="${esc(line.recipe_qty || '')}"
                    data-material-id="${esc(line.material_id || '')}"
                    data-service-id="${esc(line.external_service_id || '')}"
                    data-unit="${esc(line.unit || '')}">
                  <span class="muted">${esc(line.unit || '')}</span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`;
    const filter = body.querySelector('#mat-filter');
    filter?.addEventListener('input', () => {
      const q = (filter.value || '').trim().toLowerCase();
      body.querySelectorAll('.materialnik-table tbody tr').forEach((tr) => {
        tr.hidden = !!(q && !(tr.dataset.search || '').includes(q));
      });
    });
    if (saveBtn) saveBtn.disabled = false;
  } catch (err) {
    body.innerHTML = `<p class="hint">${esc(err.message || 'Spotřebu teď nelze načíst.')}</p>`;
  }
}

async function saveMaterialnikSpotreba() {
  const modal = $('#materialnik-modal');
  const id = Number(modal?.dataset.rezervaceId || 0);
  const msg = $('#materialnik-msg');
  if (!id) return;
  const lines = [...(modal.querySelectorAll('.mat-qty') || [])]
    .map((inp) => ({
      material_id: inp.dataset.materialId,
      external_service_id: inp.dataset.serviceId,
      unit: inp.dataset.unit,
      quantity: inp.value,
    }))
    .filter((line) => String(line.quantity || '').trim() !== '' && Number(line.quantity) > 0);
  try {
    await api(`/flow/rezervace/${id}/materialnik-spotreba/`, {
      method: 'POST',
      body: JSON.stringify({ lines }),
    });
    closeMaterialnikModal();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

async function loadOwnerPersona() {
  const msg = $('#owner-admin-msg');
  const stav = $('#own-persona-stav');
  const check = $('#own-persona-check');
  const wrap = $('#own-persona-jmeno-wrap');
  const save = $('#own-persona-save');
  const lab = $('#own-persona-switch-label');
  try {
    const p = await api('/flow/owner/pracovni-persona/');
    const linked = !!p?.ano;
    if (check) check.checked = linked;
    if (lab) lab.textContent = linked ? 'Ano' : 'Ne';
    if (stav) {
      stav.textContent = linked && p.pracovni?.jmeno ? `Na webu: ${p.pracovni.jmeno}` : '';
    }
    wrap?.classList.add('hidden');
    save?.classList.add('hidden');
    if (!linked) {
      const inp = $('#own-persona-jmeno');
      if (inp && !inp.value) inp.value = '';
      inp?.setAttribute('placeholder', 'Jméno na webu a v rezervacích');
    }
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function refreshOwnerVolnoBadge(user = currentUser) {
  const n = Number(user?.ceka_volno_pocet || 0);
  const badge = $('#owner-volno-badge');
  if (badge) {
    badge.textContent = String(n);
    badge.classList.toggle('hidden', n <= 0);
  }
}

async function loadOwnerVolno() {
  const data = await api('/flow/owner/absence/');
  if (currentUser) currentUser.ceka_volno_pocet = data.ceka_pocet || 0;
  refreshOwnerVolnoBadge(currentUser);
  try {
    const staff = await loadOwnerStaffOptions();
    const sel = $('#own-volno-zam');
    if (sel) {
      const cur = sel.value;
      sel.innerHTML = '<option value="">— vyberte —</option>'
        + staff.map((z) => `<option value="${z.id}">${esc(z.jmeno)}</option>`).join('');
      if (cur) sel.value = cur;
    }
  } catch (_) { /* select zůstane */ }
  renderOwnerVolno(data.zadosti || []);
}

function renderOwnerVolno(list) {
  const box = $('#own-volno-list');
  if (!box) return;
  box.replaceChildren();
  if (!list.length) {
    box.innerHTML = '<p class="empty">Žádné žádosti ani nedávné absence.</p>';
    return;
  }
  list.forEach((a) => {
    const card = document.createElement('article');
    card.className = `own-volno-card stav-${esc(a.stav || '')}`;
    const stavLabel = a.stav_label || a.stav || '';
    const actions = a.stav === 'ceka'
      ? `<div class="actions" data-volno-actions>
          <button type="button" class="btn primary sm op-volno-ok">Schválit</button>
          <button type="button" class="btn ghost sm op-volno-no">Zamítnout</button>
        </div>`
      : (a.stav === 'schvaleno'
        ? `<div class="actions" data-volno-actions>
            <button type="button" class="btn ghost sm op-volno-del">Smazat absenci</button>
          </div>`
        : '');
    card.innerHTML = `
      <div class="item-top">
        <strong>${esc(a.zamestnanec_jmeno || '—')}</strong>
        <span class="badge">${esc(a.typ_label || a.typ)}</span>
        <span class="badge ${a.stav === 'ceka' ? 'warn-soft' : ''}">${esc(stavLabel)}</span>
      </div>
      <p class="meta">${esc(formatDate(a.datum_od))} – ${esc(formatDate(a.datum_do))}</p>
      <p class="meta">${esc(a.poznamka || '')}</p>
      ${actions}
    `;
    const actionsEl = card.querySelector('[data-volno-actions]');
    card.querySelector('.op-volno-ok')?.addEventListener('click', () => ownerSchvalitVolno(a.id));
    card.querySelector('.op-volno-no')?.addEventListener('click', () => {
      if (!actionsEl) return;
      const showAsk = () => {
        actionsEl.innerHTML = `
          <button type="button" class="btn danger sm op-volno-no-ok">Ano, zamítnout</button>
          <button type="button" class="btn ghost sm op-volno-no-back">Zpět</button>
        `;
        actionsEl.querySelector('.op-volno-no-back')?.addEventListener('click', showBtn);
        actionsEl.querySelector('.op-volno-no-ok')?.addEventListener('click', () => ownerZamitnoutVolno(a.id));
      };
      const showBtn = () => {
        actionsEl.innerHTML = `
          <button type="button" class="btn primary sm op-volno-ok">Schválit</button>
          <button type="button" class="btn ghost sm op-volno-no">Zamítnout</button>
        `;
        actionsEl.querySelector('.op-volno-ok')?.addEventListener('click', () => ownerSchvalitVolno(a.id));
        actionsEl.querySelector('.op-volno-no')?.addEventListener('click', showAsk);
      };
      showAsk();
    });
    card.querySelector('.op-volno-del')?.addEventListener('click', () => {
      if (!actionsEl) return;
      const showAsk = () => {
        actionsEl.innerHTML = `
          <button type="button" class="btn danger sm op-volno-del-ok">Ano, smazat</button>
          <button type="button" class="btn ghost sm op-volno-del-back">Zpět</button>
        `;
        actionsEl.querySelector('.op-volno-del-back')?.addEventListener('click', showBtn);
        actionsEl.querySelector('.op-volno-del-ok')?.addEventListener('click', async () => {
          try {
            await api(`/flow/owner/absence/${a.id}/`, { method: 'DELETE' });
            showMsg($('#owner-admin-msg'), 'Absence smazána.', true);
            await loadOwnerVolno();
            refreshTopAlerts();
          } catch (err) {
            showMsg($('#owner-admin-msg'), err.message, false);
          }
        });
      };
      const showBtn = () => {
        actionsEl.innerHTML = `<button type="button" class="btn ghost sm op-volno-del">Smazat absenci</button>`;
        actionsEl.querySelector('.op-volno-del')?.addEventListener('click', showAsk);
      };
      showAsk();
    });
    box.appendChild(card);
  });
}

async function ownerSchvalitVolno(id) {
  const msg = $('#owner-admin-msg');
  try {
    const data = await api(`/flow/owner/absence/${id}/schvalit/`, { method: 'POST', body: '{}' });
    showMsg(msg, data.detail || 'Schváleno.', true);
    renderAbsenceKonflikt(data.konfliktni_rezervace || [], data.absence || null, {
      boxSel: '#own-volno-konflikt',
      msgSel: '#owner-admin-msg',
      onDone: () => loadOwnerVolno(),
    });
    await loadOwnerVolno();
    refreshTopAlerts();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

async function ownerZamitnoutVolno(id) {
  const msg = $('#owner-admin-msg');
  try {
    const data = await api(`/flow/owner/absence/${id}/zamitnout/`, { method: 'POST', body: '{}' });
    showMsg(msg, data.detail || 'Zamítnuto.', true);
    $('#own-volno-konflikt')?.classList.add('hidden');
    await loadOwnerVolno();
    refreshTopAlerts();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

$('#form-own-add-volno')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#owner-admin-msg');
  const zamId = Number($('#own-volno-zam')?.value || 0);
  if (!zamId) {
    showMsg(msg, 'Vyberte pracovníka.', false);
    return;
  }
  try {
    const data = await api('/flow/owner/absence/', {
      method: 'POST',
      body: JSON.stringify({
        zamestnanec_id: zamId,
        datum_od: $('#own-volno-od').value,
        datum_do: $('#own-volno-do').value,
        typ: $('#own-volno-typ').value,
        poznamka: $('#own-volno-pozn').value.trim(),
      }),
    });
    showMsg(msg, data.detail || 'Absence uložena.', true);
    e.target.reset();
    renderAbsenceKonflikt(data.konfliktni_rezervace || [], data.absence || null, {
      boxSel: '#own-volno-konflikt',
      msgSel: '#owner-admin-msg',
      onDone: () => loadOwnerVolno(),
    });
    await loadOwnerVolno();
    refreshTopAlerts();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

async function openOwnerSection(section) {
  if (!isOwnerUser() && section !== 'persona') return;
  // persona setup jen jako Manager (aktivní persona owner)
  if (section === 'persona' && !isOwnerUser()) return;
  const techSections = ['pravidla', 'sablony', 'audit'];
  if (techSections.includes(section) && !currentUser?.povolit_technicke_nastaveni) {
    return;
  }
  const ok = ['persona', 'pravidla', 'sablony', 'personal', 'volno', 'platby', 'hrisnici', 'audit', 'statistiky'];
  if (!ok.includes(section)) return;
  $('#owner-admin-home')?.classList.add('hidden');
  $('#owner-admin-detail')?.classList.remove('hidden');
  $$('.owner-section').forEach((el) => el.classList.add('hidden'));
  $(`#owner-section-${section}`)?.classList.remove('hidden');
  try {
    if (section === 'persona') {
      await loadOwnerPersona();
      return;
    }
    if (section === 'personal') {
      await loadOwnerPersonal();
      return;
    }
    if (section === 'volno') {
      await loadOwnerVolno();
      return;
    }
    if (section === 'platby') {
      await loadOwnerPlatby();
      return;
    }
    if (section === 'hrisnici') {
      await loadOwnerHrisnici();
      return;
    }
    if (section === 'audit') {
      await loadOwnerAudit();
      return;
    }
    if (section === 'statistiky') {
      await loadOwnerStatistiky();
      return;
    }
    ownerNastaveniCache = await api('/flow/owner/nastaveni/');
    if (section === 'pravidla') fillOwnerPravidla(ownerNastaveniCache);
    if (section === 'sablony') renderOwnerSablony(ownerNastaveniCache);
  } catch (err) {
    showMsg($('#owner-admin-msg'), err.message, false);
  }
}

function fmtMoneyCz(v) {
  const n = Number(String(v ?? '').replace(',', '.'));
  if (!Number.isFinite(n)) return esc(v || '—');
  return `${n.toLocaleString('cs-CZ', { maximumFractionDigits: 0 })}\u00a0Kč`;
}

async function downloadOwnerFaktura(platbaId) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/flow/owner/platby/${platbaId}/faktura/`, {
    headers: token ? { 'X-Flow-Token': token } : {},
  });
  if (!res.ok) {
    let detail = 'Fakturu nelze stáhnout.';
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `faktura-ulov-${platbaId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function loadOwnerPlatby() {
  const data = await api('/flow/owner/platby/');
  if (currentUser) {
    currentUser.po_splatnosti_dni = data.je_po_splatnosti ? Number(data.dni_po_splatnosti || 0) : 0;
  }
  const overdue = $('#own-platby-overdue');
  if (overdue) {
    if (data.je_po_splatnosti) {
      overdue.classList.remove('hidden');
      overdue.innerHTML = `<strong>Po splatnosti · +${esc(data.dni_po_splatnosti)} dní</strong>
        <span> — uhradte platbu ULOV podle údajů níže.</span>`;
    } else {
      overdue.classList.add('hidden');
      overdue.innerHTML = '';
    }
  }

  const summary = $('#own-platby-summary');
  if (summary) {
    if (!data.nastaveno) {
      summary.innerHTML = '<p class="empty">Platební údaje ještě nejsou nastavené. Ozvěte se provozovateli ULOV.</p>';
    } else {
      const stavLabel = data.je_po_splatnosti
        ? `Nezaplaceno · +${esc(data.dni_po_splatnosti)} dní`
        : (data.platebni_stav === 'v_poradku' ? 'V pořádku' : 'Nenastaveno');
      summary.innerHTML = `<dl>
        <dt>Účet ULOV</dt><dd>${esc(data.ulov_cislo_uctu || '—')}</dd>
        <dt>Variabilní symbol</dt><dd>${esc(data.variabilni_symbol || '—')}</dd>
        <dt>Částka</dt><dd>${fmtMoneyCz(data.castka)}</dd>
        <dt>Periodicita</dt><dd>${esc(data.periodicita_label || data.periodicita || '—')}</dd>
        <dt>Další splatnost</dt><dd>${esc(data.dalsi_splatnost || '—')}</dd>
        <dt>Stav</dt><dd class="${data.je_po_splatnosti ? 'is-overdue' : ''}">${stavLabel}</dd>
      </dl>`;
    }
  }

  const qrBox = $('#own-platby-qr');
  if (qrBox) {
    if (data.qr?.qr_png_base64) {
      qrBox.classList.remove('hidden');
      qrBox.innerHTML = `
        <img src="data:image/png;base64,${data.qr.qr_png_base64}" alt="QR platba ULOV">
        <p>${esc(data.qr.castka_display)}\u00a0Kč · VS ${esc(data.qr.variabilni_symbol)} · ${esc(data.qr.ucet)}</p>`;
    } else {
      qrBox.classList.add('hidden');
      qrBox.innerHTML = '';
    }
  }

  const hist = $('#own-platby-historie');
  if (!hist) return;
  const rows = data.historie || [];
  if (!rows.length) {
    hist.innerHTML = '<p class="empty">Zatím žádná zaplacená období.</p>';
    return;
  }
  hist.replaceChildren();
  rows.forEach((p) => {
    const row = document.createElement('div');
    row.className = 'own-platby-row';
    const info = document.createElement('div');
    info.innerHTML = `<strong>${esc(fmtMoneyCz(p.castka))}</strong>
      <span>Splatnost ${esc(p.splatnost)} · zaplaceno ${esc(p.zaplaceno_dne)}${p.variabilni_symbol ? ` · VS ${esc(p.variabilni_symbol)}` : ''}</span>`;
    row.appendChild(info);
    if (p.ma_fakturu) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn ghost sm';
      btn.textContent = 'PDF';
      btn.addEventListener('click', async () => {
        try {
          await downloadOwnerFaktura(p.id);
        } catch (err) {
          showMsg($('#owner-admin-msg'), err.message, false);
        }
      });
      row.appendChild(btn);
    } else {
      const dash = document.createElement('span');
      dash.textContent = '—';
      row.appendChild(dash);
    }
    hist.appendChild(row);
  });
}

let ownerHrisniciPage = 1;
let ownerHrisniciQuery = '';
let ownerAuditPage = 1;

function formatOwnerDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return esc(iso);
  return d.toLocaleString('cs-CZ', { dateStyle: 'short', timeStyle: 'short' });
}

async function loadOwnerHrisnici(page = ownerHrisniciPage) {
  ownerHrisniciPage = page;
  const params = new URLSearchParams({ page: String(page) });
  if (ownerHrisniciQuery) params.set('q', ownerHrisniciQuery);
  const data = await api(`/flow/owner/no-show-archiv/?${params}`);
  const box = $('#own-hrisnici-list');
  const pager = $('#own-hrisnici-pager');
  if (!box) return;
  const rows = data.vysledky || [];
  if (!rows.length) {
    box.innerHTML = `<p class="empty">Žádný záznam${ownerHrisniciQuery ? ' pro hledání' : ''}.</p>`;
  } else {
    box.replaceChildren();
    rows.forEach((z) => {
      const row = document.createElement('div');
      row.className = 'own-platby-row';
      let stav = 'V seznamu';
      if (z.blokovan_v_salonu) stav = 'Blokován';
      else if (z.problematicky) stav = 'Problematický';
      const info = document.createElement('div');
      info.innerHTML = `<strong>${esc(z.email || '—')}</strong>
        <span>${esc(z.jmeno || '')} · ${esc(z.pocet_no_show)}× Hříšníci · ${esc(stav)} · ${formatOwnerDateTime(z.posledni)}</span>`;
      row.appendChild(info);
      if (z.email) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = z.blokovan_v_salonu ? 'btn ghost sm' : 'btn primary sm';
        btn.textContent = z.blokovan_v_salonu ? 'Odblokovat' : 'Zablokovat';
        btn.addEventListener('click', async () => {
          try {
            const path = z.blokovan_v_salonu
              ? '/flow/owner/no-show-odblokovat/'
              : '/flow/owner/no-show-blokovat/';
            const res = await api(path, { method: 'POST', body: JSON.stringify({ email: z.email }) });
            showMsg($('#owner-admin-msg'), res.detail || 'Uloženo.', true);
            await loadOwnerHrisnici(ownerHrisniciPage);
          } catch (err) {
            showMsg($('#owner-admin-msg'), err.message, false);
          }
        });
        row.appendChild(btn);
      }
      box.appendChild(row);
    });
  }
  if (pager) {
    pager.textContent = `Strana ${data.stranka || 1} / ${data.celkem_stranek || 1} (${data.celkem || 0})`;
  }
  const prev = $('#own-hrisnici-prev');
  const next = $('#own-hrisnici-next');
  if (prev) prev.disabled = (data.stranka || 1) <= 1;
  if (next) next.disabled = (data.stranka || 1) >= (data.celkem_stranek || 1);
}

async function loadOwnerAudit(page = ownerAuditPage) {
  ownerAuditPage = page;
  const data = await api(`/flow/owner/audit-log/?page=${page}`);
  const box = $('#own-audit-list');
  const pager = $('#own-audit-pager');
  if (!box) return;
  const rows = data.vysledky || [];
  if (!rows.length) {
    box.innerHTML = '<p class="empty">Zatím žádné záznamy.</p>';
  } else {
    box.replaceChildren();
    rows.forEach((r) => {
      const row = document.createElement('div');
      row.className = 'own-platby-row';
      row.innerHTML = `<div><strong>${esc(r.kdo || '—')}</strong>
        <span>${formatOwnerDateTime(r.kdy)} · ${esc(r.popis || '')}</span></div>`;
      box.appendChild(row);
    });
  }
  if (pager) {
    pager.textContent = `Strana ${data.stranka || 1} / ${data.celkem_stranek || 1} (${data.celkem || 0})`;
  }
  const prev = $('#own-audit-prev');
  const next = $('#own-audit-next');
  if (prev) prev.disabled = (data.stranka || 1) <= 1;
  if (next) next.disabled = (data.stranka || 1) >= (data.celkem_stranek || 1);
}

async function loadOwnerStatistiky() {
  const data = await api('/flow/owner/statistiky/');
  const box = $('#own-statistiky');
  if (!box) return;
  const sluzby = (data.nejprodavanejsi_sluzby || [])
    .map((s) => `${esc(s.sluzba__nazev || '—')} (${s.pocet})`)
    .join(', ') || '—';
  const staff = (data.nejvytizenejsi_zamestnanci || [])
    .map((s) => `${esc(s.zamestnanec__jmeno || '—')} (${s.pocet})`)
    .join(', ') || '—';
  box.innerHTML = `<dl>
    <dt>Rezervací celkem</dt><dd>${esc(data.celkem_rezervaci)}</dd>
    <dt>Dokončené</dt><dd>${esc(data.dokonceno)}</dd>
    <dt>Tržba celkem</dt><dd>${fmtMoneyCz(data.trzba_celkem)}</dd>
    <dt>Tržba tento měsíc</dt><dd>${fmtMoneyCz(data.trzba_mesic)}</dd>
    <dt>Storno</dt><dd>${esc(data.storno)} (${esc(data.storno_procent)} %)</dd>
    <dt>Hříšníci</dt><dd>${esc(data.no_show)}</dd>
    <dt>Top služby</dt><dd>${sluzby}</dd>
    <dt>Top Staff</dt><dd>${staff}</dd>
  </dl>`;
}

const DEN_LABELS = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];

async function loadOwnerPersonal() {
  const data = await api('/flow/owner/personal/');
  ownerSluzbyCache = data.sluzby || [];
  ownerStaffOptionsCache = (data.zamestnanci || []).filter((z) => z.role !== 'majitel');
  renderOwnerPersonal(data.zamestnanci || []);
}

function personalNavLabel(z) {
  if (!z) return '—';
  if (z.role === 'majitel') return 'Manager';
  const workId = currentUser?.persona?.pracovnik?.id;
  if (workId && Number(z.id) === Number(workId)) {
    return `${z.jmeno} (Staff · Manager)`;
  }
  return z.jmeno;
}

function staffAvatarHtml(z, name) {
  const label = name || z?.jmeno || '?';
  const parts = String(label).split(/\s+/).filter(Boolean);
  const ini = parts.length >= 2
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : String(label).slice(0, 2).toUpperCase();
  if (z?.fotka) {
    return `<img src="${esc(z.fotka)}" alt="" width="44" height="44">`;
  }
  return `<span class="ph">${esc(ini)}</span>`;
}

function staffFlowStatus(z) {
  const flow = z.flow || {};
  const ucet = flow.ucet || null;
  if (!flow.ma_flow || !ucet) return { cls: 'is-off', text: 'bez FLOW' };
  if (!ucet.aktivni) return { cls: 'is-blocked', text: 'zablokováno' };
  return { cls: 'is-on', text: 'přihlášení OK' };
}

function renderOwnerPersonal(list) {
  const nav = $('#own-staff-nav');
  const detail = $('#own-staff-detail');
  if (!nav || !detail) return;
  ownerPersonalCache = list || [];
  if (!ownerPersonalCache.length) {
    nav.innerHTML = '';
    detail.innerHTML = '<p class="empty">Zatím žádný Staff. Přidejte prvního pracovníka tlačítkem nahoře.</p>';
    return;
  }
  if (
    ownerPersonalSelectedId == null
    || !ownerPersonalCache.some((z) => z.id === ownerPersonalSelectedId)
  ) {
    const firstStaff = ownerPersonalCache.find((z) => z.role !== 'majitel');
    ownerPersonalSelectedId = (firstStaff || ownerPersonalCache[0]).id;
  }
  nav.replaceChildren();
  ownerPersonalCache.forEach((z) => {
    const isOwner = z.role === 'majitel';
    const name = isOwner ? 'Manager' : z.jmeno;
    const st = isOwner
      ? { cls: 'is-muted', text: 'správa' }
      : staffFlowStatus(z);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `staff-person${z.id === ownerPersonalSelectedId ? ' is-active' : ''}`;
    btn.innerHTML = `${staffAvatarHtml(z, name)}<span class="staff-person-copy">
      <strong>${esc(personalNavLabel(z))}</strong>
      <span class="staff-status ${st.cls}">${esc(st.text)}</span>
    </span>`;
    btn.addEventListener('click', () => {
      ownerPersonalSelectedId = z.id;
      renderOwnerPersonal(ownerPersonalCache);
    });
    nav.appendChild(btn);
  });
  const z = ownerPersonalCache.find((x) => x.id === ownerPersonalSelectedId);
  detail.replaceChildren();
  if (z) detail.appendChild(buildOwnerPersonalCard(z));
}

function buildOwnerPersonalCard(z) {
  const isOwner = z.role === 'majitel';
  const workId = currentUser?.persona?.pracovnik?.id;
  const isManagerStaff = !isOwner && workId && Number(z.id) === Number(workId);
  const flow = z.flow || {};
  const ucet = flow.ucet || null;
  const card = document.createElement('article');
  card.className = 'own-personal-card';
  card.dataset.id = String(z.id);

  const displayName = isOwner ? 'Manager' : z.jmeno;
  const roleBadge = isOwner
    ? ''
    : (isManagerStaff ? ' <span class="role-badge">Staff · Manager</span>' : '');

  const rozvrhRows = (z.rozvrh || []).map((r) => {
    const volno = !!r.volno;
    const od = (r.od || '').slice(0, 5);
    const doCas = (r.do || '').slice(0, 5);
    return `<tr data-den="${r.den}">
      <td>${DEN_LABELS[r.den] || r.den}</td>
      <td><label class="check-row tight"><input type="checkbox" class="op-volno" ${volno ? 'checked' : ''} ${isOwner ? 'disabled' : ''}> volno</label></td>
      <td><input type="time" class="op-od" value="${esc(od)}" ${volno || isOwner ? 'disabled' : ''}></td>
      <td><input type="time" class="op-do" value="${esc(doCas)}" ${volno || isOwner ? 'disabled' : ''}></td>
    </tr>`;
  }).join('');

  card.innerHTML = `
    <div class="own-personal-head">
      ${staffAvatarHtml(z, displayName)}
      <div>
        <h3>${esc(displayName)}${roleBadge}</h3>
        <p class="hint tiny">${esc(z.specializace || (isOwner ? 'Účet pro správu salonu' : ''))}</p>
      </div>
    </div>
    ${isOwner ? '<p class="hint tiny">Účet pro správu. Obsluhu zákazníků zapnete v menu Personál → Manager obsluhuje.</p>' : ''}
    ${isManagerStaff ? '<p class="hint tiny">Pracovní profil Managera — stejný login, nahoře přepínač Manager / Staff.</p>' : ''}
    ${isOwner ? '' : `
    <section class="own-block">
      <h4>Údaje</h4>
      <label>Jméno
        <input type="text" class="op-jmeno" value="${esc(z.jmeno || '')}">
      </label>
      <label>Specializace
        <input type="text" class="op-spec" value="${esc(z.specializace || '')}">
      </label>
      <label>Číslo účtu (QR pro zákazníky)
        <input type="text" class="op-ucet" value="${esc(z.cislo_uctu || '')}" placeholder="123456789/0100">
      </label>
      <button type="button" class="btn primary sm op-save">Uložit údaje</button>
    </section>
    <section class="own-block">
      <h4>Služby</h4>
      ${staffSluzbyBlockHtml(z)}
    </section>
    <section class="own-block">
      <h4>Pracovní doba</h4>
      <table class="own-rozvrh-table">
        <thead><tr><th>Den</th><th></th><th>Od</th><th>Do</th></tr></thead>
        <tbody>${rozvrhRows}</tbody>
      </table>
      <button type="button" class="btn primary sm op-save">Uložit pracovní dobu</button>
    </section>
    <section class="own-block">
      <h4>Přístup do FLOW</h4>
    ${ucet ? `
      <p class="hint tiny">E-mail: <strong>${esc(ucet.email)}</strong></p>
      <p class="hint tiny">Přihlášení: <strong>${ucet.aktivni ? 'povoleno' : 'zablokováno'}</strong>
        · přehled salonu ${ucet.visible_overview ? 'zapnutý' : 'vypnutý'}</p>
      <div class="owner-personal-actions">
        <div class="flow-access-btns" role="group" aria-label="Přihlášení do FLOW">
          <button type="button" class="btn sm op-flow-allow ${ucet.aktivni ? 'primary is-active' : 'ghost'}" ${ucet.aktivni ? 'disabled' : ''}>Povolit vstup</button>
          <button type="button" class="btn sm op-flow-block ${!ucet.aktivni ? 'danger is-active' : 'ghost'}" ${!ucet.aktivni ? 'disabled' : ''}>Zablokovat vstup</button>
        </div>
        <label class="check-row tight"><input type="checkbox" class="op-flow-overview" ${ucet.visible_overview ? 'checked' : ''}> Vidí přehled všech rezervací</label>
        <button type="button" class="btn ghost sm op-flow-save">Uložit přehled</button>
        <div class="owner-personal-actions" data-flow-reset-actions>
          <button type="button" class="btn ghost sm op-flow-reset">Resetovat heslo FLOW</button>
        </div>
      </div>
    ` : `
      <p class="hint tiny">Zatím bez FLOW přístupu — zadejte e-mail a vytvořte účet.</p>
      <label>E-mail pro FLOW
        <input type="email" class="op-flow-email" placeholder="pracovnik@salon.cz">
      </label>
      <label class="check-row tight"><input type="checkbox" class="op-flow-overview-new"> Vidí přehled všech rezervací</label>
      <div class="owner-personal-actions" data-flow-create-actions>
        <button type="button" class="btn primary sm op-flow-create">Vytvořit FLOW přístup</button>
      </div>
    `}
    </section>
    `}
  `;

  if (!isOwner) {
    card.querySelectorAll('.op-volno').forEach((cb) => {
      cb.addEventListener('change', () => {
        const row = cb.closest('tr');
        row.querySelector('.op-od').disabled = cb.checked;
        row.querySelector('.op-do').disabled = cb.checked;
      });
    });
    card.querySelectorAll('.op-save').forEach((btn) => {
      btn.addEventListener('click', () => saveOwnerStaff(card, z.id));
    });
    wireOwnerStaffSluzby(card, z.id);
    card.querySelector('.op-flow-create')?.addEventListener('click', () => askCreateOwnerStaffFlow(card, z.id));
    card.querySelector('.op-flow-save')?.addEventListener('click', () => patchOwnerStaffFlow(card, z.id));
    card.querySelector('.op-flow-allow')?.addEventListener('click', (e) => {
      askOwnerStaffFlowAccess(e.currentTarget.closest('.flow-access-btns'), z.id, true);
    });
    card.querySelector('.op-flow-block')?.addEventListener('click', (e) => {
      askOwnerStaffFlowAccess(e.currentTarget.closest('.flow-access-btns'), z.id, false);
    });
    card.querySelector('.op-flow-reset')?.addEventListener('click', () => {
      askResetOwnerStaffFlow(card.querySelector('[data-flow-reset-actions]'), z.id);
    });
  }
  return card;
}

function staffSluzbyBlockHtml(z) {
  const catalog = ownerSluzbyCache || [];
  if (!catalog.length) {
    return '<p class="hint tiny">V ceníku zatím nejsou aktivní služby. Přidejte je ve web-adminu.</p>';
  }
  const assigned = (z.sluzby_ids || []).map(Number);
  const allServices = assigned.length === 0;
  const items = catalog.map((s) => {
    const checked = !allServices && assigned.includes(Number(s.id)) ? ' checked' : '';
    return `<label class="op-sluzby-item">
      <input type="checkbox" class="op-sluzba-cb" value="${s.id}"${checked}>
      <span>${esc(s.nazev)} <span class="muted">(${s.delka_minut} min)</span></span>
    </label>`;
  }).join('');
  return `
    <label class="op-all-sluzby-row">
      <input type="checkbox" class="op-all-sluzby"${allServices ? ' checked' : ''}>
      <span>Všechny služby</span>
    </label>
    <div class="op-sluzby-list${allServices ? ' hidden' : ''}">${items}</div>
    <button type="button" class="btn primary sm op-save-sluzby">Uložit služby</button>
  `;
}

function wireOwnerStaffSluzby(card, id) {
  const allCb = card.querySelector('.op-all-sluzby');
  const list = card.querySelector('.op-sluzby-list');
  allCb?.addEventListener('change', () => {
    list?.classList.toggle('hidden', allCb.checked);
  });
  card.querySelector('.op-save-sluzby')?.addEventListener('click', () => saveOwnerStaffSluzby(card, id));
}

function collectOwnerStaffRozvrh(card) {
  return [...card.querySelectorAll('.own-rozvrh-table tbody tr')].map((row) => {
    const volno = !!row.querySelector('.op-volno')?.checked;
    return {
      den: Number(row.dataset.den),
      volno,
      od: volno ? null : (row.querySelector('.op-od')?.value || null),
      do: volno ? null : (row.querySelector('.op-do')?.value || null),
    };
  });
}

async function saveOwnerStaff(card, id) {
  const msg = $('#owner-admin-msg');
  try {
    await api(`/flow/owner/personal/${id}/`, {
      method: 'PUT',
      body: JSON.stringify({
        jmeno: card.querySelector('.op-jmeno')?.value.trim(),
        specializace: card.querySelector('.op-spec')?.value.trim(),
        cislo_uctu: card.querySelector('.op-ucet')?.value.trim(),
        rozvrh: collectOwnerStaffRozvrh(card),
      }),
    });
    showMsg(msg, 'Údaje pracovníka uloženy.', true);
    await loadOwnerPersonal();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

async function saveOwnerStaffSluzby(card, id) {
  const msg = $('#owner-admin-msg');
  const all = !!card.querySelector('.op-all-sluzby')?.checked;
  let ids = [];
  if (!all) {
    ids = [...card.querySelectorAll('.op-sluzba-cb:checked')].map((cb) => Number(cb.value));
    if (!ids.length) {
      showMsg(msg, 'Vyberte aspoň jednu službu, nebo zapněte Všechny služby.', false);
      return;
    }
  }
  try {
    await api(`/flow/owner/personal/${id}/`, {
      method: 'PUT',
      body: JSON.stringify({ sluzby_ids: ids }),
    });
    showMsg(msg, all ? 'Umí všechny služby.' : 'Služby uloženy.', true);
    await loadOwnerPersonal();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function askCreateOwnerStaffFlow(card, id) {
  const msg = $('#owner-admin-msg');
  const email = card.querySelector('.op-flow-email')?.value.trim();
  if (!email) {
    showMsg(msg, 'Zadejte e-mail pro FLOW.', false);
    return;
  }
  const actions = card.querySelector('[data-flow-create-actions]');
  if (!actions) {
    createOwnerStaffFlow(card, id);
    return;
  }
  const showAsk = () => {
    actions.innerHTML = `
      <p class="hint tiny">Vytvořit FLOW přístup pro <strong>${esc(email)}</strong>?</p>
      <button type="button" class="btn primary sm op-flow-create-ok">Ano, vytvořit</button>
      <button type="button" class="btn ghost sm op-flow-create-back">Zpět</button>
    `;
    actions.querySelector('.op-flow-create-back')?.addEventListener('click', showBtn);
    actions.querySelector('.op-flow-create-ok')?.addEventListener('click', () => createOwnerStaffFlow(card, id));
  };
  const showBtn = () => {
    actions.innerHTML = `<button type="button" class="btn primary sm op-flow-create">Vytvořit FLOW přístup</button>`;
    actions.querySelector('.op-flow-create')?.addEventListener('click', () => askCreateOwnerStaffFlow(card, id));
  };
  showAsk();
}

async function createOwnerStaffFlow(card, id) {
  const msg = $('#owner-admin-msg');
  const email = card.querySelector('.op-flow-email')?.value.trim();
  if (!email) {
    showMsg(msg, 'Zadejte e-mail pro FLOW.', false);
    return;
  }
  try {
    const data = await api(`/flow/owner/personal/${id}/flow/`, {
      method: 'POST',
      body: JSON.stringify({
        email,
        visible_overview: !!card.querySelector('.op-flow-overview-new')?.checked,
      }),
    });
    await loadOwnerPersonal();
    showFlowAccessResult(msg, data, 'FLOW přístup vytvořen.');
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

async function patchOwnerStaffFlow(card, id) {
  const msg = $('#owner-admin-msg');
  try {
    await api(`/flow/owner/personal/${id}/flow/patch/`, {
      method: 'PATCH',
      body: JSON.stringify({
        visible_overview: !!card.querySelector('.op-flow-overview')?.checked,
      }),
    });
    showMsg(msg, 'Overview uložen.', true);
    await loadOwnerPersonal();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function askOwnerStaffFlowAccess(actionsEl, id, allow) {
  if (!actionsEl) {
    setOwnerStaffFlowAccess(id, allow);
    return;
  }
  const original = actionsEl.innerHTML;
  const showAsk = () => {
    actionsEl.innerHTML = allow
      ? `
        <button type="button" class="btn primary sm op-flow-allow-ok">Ano, povolit</button>
        <button type="button" class="btn ghost sm op-flow-access-back">Zpět</button>
      `
      : `
        <button type="button" class="btn danger sm op-flow-block-ok">Ano, zablokovat</button>
        <button type="button" class="btn ghost sm op-flow-access-back">Zpět</button>
      `;
    actionsEl.querySelector('.op-flow-access-back')?.addEventListener('click', showBtn);
    actionsEl.querySelector('.op-flow-allow-ok')?.addEventListener('click', () => setOwnerStaffFlowAccess(id, true));
    actionsEl.querySelector('.op-flow-block-ok')?.addEventListener('click', () => setOwnerStaffFlowAccess(id, false));
  };
  const showBtn = () => {
    actionsEl.innerHTML = original;
    actionsEl.querySelector('.op-flow-allow')?.addEventListener('click', () => askOwnerStaffFlowAccess(actionsEl, id, true));
    actionsEl.querySelector('.op-flow-block')?.addEventListener('click', () => askOwnerStaffFlowAccess(actionsEl, id, false));
  };
  showAsk();
}

async function setOwnerStaffFlowAccess(id, allow) {
  const msg = $('#owner-admin-msg');
  try {
    await api(`/flow/owner/personal/${id}/flow/patch/`, {
      method: 'PATCH',
      body: JSON.stringify({ aktivni: !!allow }),
    });
    showMsg(msg, allow ? 'Vstup do FLOW povolen.' : 'Vstup do FLOW zablokován.', true);
    await loadOwnerPersonal();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

function askResetOwnerStaffFlow(actionsEl, id) {
  if (!actionsEl) {
    resetOwnerStaffFlow(id);
    return;
  }
  const showAsk = () => {
    actionsEl.innerHTML = `
      <button type="button" class="btn danger sm op-flow-reset-ok">Ano, resetovat heslo</button>
      <button type="button" class="btn ghost sm op-flow-reset-back">Zpět</button>
    `;
    actionsEl.querySelector('.op-flow-reset-back')?.addEventListener('click', showBtn);
    actionsEl.querySelector('.op-flow-reset-ok')?.addEventListener('click', () => resetOwnerStaffFlow(id));
  };
  const showBtn = () => {
    actionsEl.innerHTML = `<button type="button" class="btn ghost sm op-flow-reset">Resetovat heslo FLOW</button>`;
    actionsEl.querySelector('.op-flow-reset')?.addEventListener('click', () => askResetOwnerStaffFlow(actionsEl, id));
  };
  showAsk();
}

async function resetOwnerStaffFlow(id) {
  const msg = $('#owner-admin-msg');
  try {
    const data = await api(`/flow/owner/personal/${id}/flow/reset-hesla/`, { method: 'POST', body: '{}' });
    showFlowAccessResult(msg, data, 'Heslo resetováno.');
  } catch (err) {
    showMsg(msg, err.message, false);
  }
}

$('#btn-own-add-staff')?.addEventListener('click', () => {
  const form = $('#form-own-add-staff');
  form?.classList.remove('hidden');
  $('#own-add-jmeno')?.focus();
});

$('#btn-own-add-cancel')?.addEventListener('click', () => {
  const form = $('#form-own-add-staff');
  form?.classList.add('hidden');
  form?.reset();
});

$('#form-own-add-staff')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#owner-admin-msg');
  const jmeno = $('#own-add-jmeno')?.value.trim();
  const specializace = $('#own-add-spec')?.value.trim() || '';
  const flowEmail = ($('#own-add-flow-email')?.value.trim() || '').toLowerCase();
  if (!jmeno) {
    showMsg(msg, 'Zadejte jméno pracovníka.', false);
    return;
  }
  if (!flowEmail || !flowEmail.includes('@')) {
    showMsg(msg, 'Zadejte skutečný e-mail pracovníka — ten bude přihlášením do FLOW.', false);
    $('#own-add-flow-email')?.focus();
    return;
  }
  try {
    const created = await api('/flow/owner/personal/', {
      method: 'POST',
      body: JSON.stringify({
        jmeno,
        specializace,
        // skutečný e-mail = login (pokud se vejde do 50 znaků)
        prihlasovaci_jmeno: flowEmail.length <= 50 ? flowEmail : undefined,
      }),
    });
    const flowRes = await api(`/flow/owner/personal/${created.id}/flow/`, {
      method: 'POST',
      body: JSON.stringify({
        email: flowEmail,
        visible_overview: !!$('#own-add-flow-overview')?.checked,
      }),
    });
    const detail = flowRes.detail || (
      flowRes.email_odeslan
        ? `Pracovník přidán. Přihlašovací údaje odeslány na ${flowEmail}.`
        : `Pracovník přidán. FLOW: ${flowEmail}`
    );
    $('#form-own-add-staff')?.classList.add('hidden');
    $('#form-own-add-staff')?.reset();
    await loadOwnerPersonal();
    showFlowAccessResult(msg, { ...flowRes, detail }, detail);
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});


function fillOwnerPravidla(data) {
  $('#own-interval').value = String(data.interval_minut ?? 15);
  $('#own-min-h').value = data.min_predstih_hodin ?? 2;
  $('#own-max-m').value = data.max_predstih_mesicu ?? 3;
  $('#own-storno').value = data.storno_do_hodin ?? '';
  $('#own-potvrzeni-h').value = data.potvrzeni_platnost_hodin ?? 24;
  $('#own-auto-potvrzeni').checked = !!data.auto_potvrzeni;
  $('#own-recenze-url').value = data.recenze_url || '';
}

function renderOwnerTagGuide(tagy) {
  const el = $('#own-notif-tag-guide');
  if (!el) return;
  el.replaceChildren();
  if (!tagy?.length) return;
  const table = document.createElement('table');
  table.className = 'own-tag-table';
  table.innerHTML = '<thead><tr><th>Tag (kliknutím zkopírujete)</th><th>Co se vypíše</th><th>Příklad</th></tr></thead>';
  const tbody = document.createElement('tbody');
  tagy.forEach((row) => {
    const tr = document.createElement('tr');
    const tdTag = document.createElement('td');
    const code = document.createElement('code');
    code.className = 'own-tag-copy';
    code.textContent = row.tag;
    code.title = 'Kliknutím zkopírujete';
    code.addEventListener('click', async () => {
      try {
        await navigator.clipboard?.writeText(row.tag);
        code.classList.add('is-copied');
        setTimeout(() => code.classList.remove('is-copied'), 800);
      } catch (_) { /* ignore */ }
    });
    tdTag.appendChild(code);
    const tdPopis = document.createElement('td');
    tdPopis.textContent = row.popis || '';
    const tdPriklad = document.createElement('td');
    tdPriklad.className = 'own-tag-example';
    tdPriklad.textContent = row.priklad || '';
    tr.append(tdTag, tdPopis, tdPriklad);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

function renderOwnerSablony(data) {
  const hint = $('#own-notif-hint');
  if (hint) hint.textContent = data.notifikace_placeholders || '';
  renderOwnerTagGuide(data.notifikace_tagy || []);
  const list = $('#own-notif-list');
  if (!list) return;
  list.replaceChildren();
  const items = [...(data.notifikace || [])];
  while (items.length < 8) {
    items.push({ id: '', offset: 'manual', manual: true, aktivni: false, predmet: '', text: '' });
  }
  items.slice(0, 8).forEach((n, i) => {
    const isManual = i >= 2 || n.manual || n.offset === 'manual';
    const card = document.createElement('article');
    card.className = 'own-notif-card';
    card.dataset.idx = String(i);
    card.innerHTML = `
      <h4>Šablona ${i + 1}</h4>
      <p class="hint tiny">${esc(OWN_NOTIF_POPISY[i] || '')}</p>
      <label class="check-row"><input type="checkbox" class="own-n-aktivni" ${n.aktivni ? 'checked' : ''}> Aktivní</label>
      ${isManual ? '' : `<label>Offset (např. +24 nebo -2)
        <input type="text" class="own-n-offset" value="${esc(n.offset || '')}" placeholder="+24">
      </label>`}
      <input type="hidden" class="own-n-manual" value="${isManual ? '1' : '0'}">
      <input type="hidden" class="own-n-id" value="${esc(n.id || '')}">
      <input type="hidden" class="own-n-manual-typ" value="${esc(n.manual_typ || '')}">
      <label>Předmět
        <input type="text" class="own-n-predmet" value="${esc(n.predmet || '')}">
      </label>
      <label>Text
        <textarea class="own-n-text" rows="4">${esc(n.text || '')}</textarea>
      </label>
    `;
    list.appendChild(card);
  });
}

function collectOwnerSablony() {
  return [...$$('#own-notif-list .own-notif-card')].map((card, i) => {
    const isManual = card.querySelector('.own-n-manual')?.value === '1';
    const item = {
      id: card.querySelector('.own-n-id')?.value || undefined,
      aktivni: !!card.querySelector('.own-n-aktivni')?.checked,
      predmet: card.querySelector('.own-n-predmet')?.value || '',
      text: card.querySelector('.own-n-text')?.value || '',
      manual: isManual,
      offset: isManual ? 'manual' : (card.querySelector('.own-n-offset')?.value || '').trim(),
    };
    const mt = card.querySelector('.own-n-manual-typ')?.value;
    if (mt) item.manual_typ = mt;
    return item;
  });
}

$('#owner-admin-back')?.addEventListener('click', showOwnerAdminHome);

$('#form-own-blok-email')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = ($('#own-blok-email')?.value || '').trim();
  if (!email) return;
  try {
    const res = await api('/flow/owner/no-show-blokovat/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    showMsg($('#owner-admin-msg'), res.detail || 'Zablokováno.', true);
    e.target.reset();
    await loadOwnerHrisnici(1);
  } catch (err) {
    showMsg($('#owner-admin-msg'), err.message, false);
  }
});

$('#btn-own-hrisnici-search')?.addEventListener('click', () => {
  ownerHrisniciQuery = ($('#own-hrisnici-q')?.value || '').trim();
  loadOwnerHrisnici(1).catch((err) => showMsg($('#owner-admin-msg'), err.message, false));
});
$('#own-hrisnici-q')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    $('#btn-own-hrisnici-search')?.click();
  }
});
$('#own-hrisnici-prev')?.addEventListener('click', () => {
  if (ownerHrisniciPage > 1) loadOwnerHrisnici(ownerHrisniciPage - 1);
});
$('#own-hrisnici-next')?.addEventListener('click', () => loadOwnerHrisnici(ownerHrisniciPage + 1));
$('#own-audit-prev')?.addEventListener('click', () => {
  if (ownerAuditPage > 1) loadOwnerAudit(ownerAuditPage - 1);
});
$('#own-audit-next')?.addEventListener('click', () => loadOwnerAudit(ownerAuditPage + 1));

$$('#owner-admin-home [data-owner-section]').forEach((el) => {
  el.addEventListener('click', () => {
    if (el.classList.contains('is-disabled')) return;
    openOwnerSection(el.dataset.ownerSection);
  });
});

$$('#persona-switch .persona-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const persona = btn.dataset.persona;
    if (!persona || currentUser?.persona?.aktivni === persona) return;
    try {
      await switchPersona(persona);
    } catch (err) {
      alert(err.message || 'Přepnutí se nepodařilo.');
    }
  });
});

async function saveOwnerPersona(ano) {
  const msg = $('#owner-admin-msg');
  const check = $('#own-persona-check');
  const lab = $('#own-persona-switch-label');
  try {
    const data = await api('/flow/owner/pracovni-persona/', {
      method: ano ? 'POST' : 'DELETE',
      body: ano
        ? JSON.stringify({
            ano: true,
            vytvorit: true,
            jmeno: ($('#own-persona-jmeno')?.value || '').trim(),
          })
        : undefined,
    });
    currentUser = data;
    applyPersonaUi(data);
    showMsg(msg, ano ? 'Zapnuto — přepínač nahoře ve FLOW.' : 'Vypnuto.', true);
    await loadOwnerPersona();
    return true;
  } catch (err) {
    showMsg(msg, err.message, false);
    if (!ano && check) {
      check.checked = true;
      if (lab) lab.textContent = 'Ano';
    }
    return false;
  }
}

$('#own-persona-check')?.addEventListener('change', async () => {
  const check = $('#own-persona-check');
  const wrap = $('#own-persona-jmeno-wrap');
  const save = $('#own-persona-save');
  const lab = $('#own-persona-switch-label');
  const ano = !!check?.checked;
  if (lab) lab.textContent = ano ? 'Ano' : 'Ne';
  if (!ano) {
    wrap?.classList.add('hidden');
    save?.classList.add('hidden');
    await saveOwnerPersona(false);
    return;
  }
  wrap?.classList.remove('hidden');
  save?.classList.remove('hidden');
  $('#own-persona-jmeno')?.focus();
});

$('#form-owner-persona')?.addEventListener('submit', async (e) => {
  e.preventDefault();
});

$('#own-persona-save')?.addEventListener('click', async () => {
  await saveOwnerPersona(true);
});

$('#form-owner-pravidla')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#owner-admin-msg');
  const stornoRaw = $('#own-storno').value.trim();
  try {
    const payload = {
      interval_minut: parseInt($('#own-interval').value, 10),
      min_predstih_hodin: parseInt($('#own-min-h').value, 10),
      max_predstih_mesicu: parseInt($('#own-max-m').value, 10),
      potvrzeni_platnost_hodin: parseInt($('#own-potvrzeni-h').value, 10),
      auto_potvrzeni: !!$('#own-auto-potvrzeni').checked,
      recenze_url: $('#own-recenze-url').value.trim(),
      storno_do_hodin: stornoRaw === '' ? null : parseInt(stornoRaw, 10),
    };
    ownerNastaveniCache = await api('/flow/owner/nastaveni/', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    fillOwnerPravidla(ownerNastaveniCache);
    showMsg(msg, 'Pravidla uložena.', true);
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#btn-own-sablony-save')?.addEventListener('click', async () => {
  const msg = $('#owner-admin-msg');
  try {
    ownerNastaveniCache = await api('/flow/owner/nastaveni/', {
      method: 'PUT',
      body: JSON.stringify({ notifikace: collectOwnerSablony() }),
    });
    renderOwnerSablony(ownerNastaveniCache);
    showMsg(msg, 'Šablony uloženy.', true);
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

wireEmailPreviewSheet();
$('#flow-confirm-ok')?.addEventListener('click', () => closeFlowConfirm(true));
$('#flow-confirm-cancel')?.addEventListener('click', () => closeFlowConfirm(false));
$('#flow-confirm-modal')?.addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeFlowConfirm(false);
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#flow-confirm-modal')?.classList.contains('hidden')) {
    closeFlowConfirm(false);
  }
});
$('#materialnik-close')?.addEventListener('click', closeMaterialnikModal);
$('#materialnik-skip')?.addEventListener('click', closeMaterialnikModal);
$('#materialnik-save')?.addEventListener('click', () => {
  saveMaterialnikSpotreba().catch(() => {});
});
boot();
