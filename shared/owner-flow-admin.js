/**
 * Schválené chování majitele ze salon2 — FLOW aktivace + změna sdíleného hesla
 * + tick box „Manager také pracuje“.
 *
 * Zapojení (povinné u každého partner webu):
 *   1) <script src="../shared/owner-flow-admin.js"></script> před app.js
 *   2) window.UlovOwnerFlowConfig = { getSalonId, getApiBase, getToken, isMajitel, getEmail }
 *   3) po přihlášení majitele: UlovOwnerFlow.onAdminShown()
 *
 * UI si modul doplní sám do #edit-section (záložka Základ + Heslo).
 */
(function (global) {
  'use strict';

  const CFG = () => global.UlovOwnerFlowConfig || {};

  /** Zlatý štítek Manager — funguje i bez --gold v CSS konkrétního webu. */
  function ensureRolePillStyles() {
    if (document.getElementById('ulov-role-pill-css')) return;
    const style = document.createElement('style');
    style.id = 'ulov-role-pill-css';
    style.textContent = `
      .role-pill {
        display: inline-block;
        margin-left: 0.45rem;
        padding: 0.15rem 0.5rem;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        vertical-align: middle;
        color: #1a1a1a !important;
        background: var(--gold, #c9a962) !important;
        border: 1px solid var(--gold, #c9a962) !important;
      }
    `;
    document.head.appendChild(style);
  }

  function flowAppUrl() {
    const h = location.hostname;
    if (h.includes('staging')) return 'https://www.staging.ulovklienty.cz/flow/';
    if (['localhost', '127.0.0.1', '::1'].includes(h)) {
      return `${location.protocol}//${h}${location.port ? `:${location.port}` : ''}/flow/`;
    }
    return 'https://www.ulovklienty.cz/flow/';
  }

  function apiBase() {
    const c = CFG();
    if (typeof c.getApiBase === 'function') return c.getApiBase();
    return c.apiBase || 'https://api.ulovklienty.cz/api';
  }

  function salonId() {
    const c = CFG();
    if (typeof c.getSalonId === 'function') return c.getSalonId();
    return c.salonId;
  }

  function token() {
    const c = CFG();
    if (typeof c.getToken === 'function') return c.getToken();
    return '';
  }

  function isMajitel() {
    const c = CFG();
    if (typeof c.isMajitel === 'function') return !!c.isMajitel();
    return true;
  }

  function looksLikeEmail(v) {
    const s = String(v || '').trim();
    if (!s.includes('@')) return false;
    const domain = s.split('@').pop() || '';
    return domain.includes('.');
  }

  /**
   * E-mail pro aktivaci FLOW = login majitele, ne kontakt na webu.
   * Preferuje session (staffUser); z login pole bere jen platný e-mail.
   */
  function emailHint() {
    const c = CFG();
    const raw = typeof c.getEmail === 'function'
      ? (c.getEmail() || '').trim()
      : (document.getElementById('staff-login')?.value || '').trim();
    if (looksLikeEmail(raw)) return raw;
    return '';
  }

  async function api(path, opts = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    };
    const t = token();
    if (t) headers['X-Staff-Token'] = t;
    const res = await fetch(`${apiBase()}${path}`, { ...opts, headers });
    const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
    if (!res.ok) throw new Error(data?.detail || 'Chyba API');
    return data;
  }

  function ensureUi() {
    ensureRolePillStyles();
    const edit = document.getElementById('edit-section');
    if (!edit) return false;

    const tabs = edit.querySelector('.admin-tabs');
    if (tabs && !tabs.querySelector('[data-tab="heslo"]')) {
      const emailTab = tabs.querySelector('[data-tab="email"]');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tab';
      btn.dataset.tab = 'heslo';
      btn.textContent = 'Heslo';
      if (emailTab && emailTab.nextSibling) tabs.insertBefore(btn, emailTab.nextSibling);
      else if (emailTab) emailTab.after(btn);
      else tabs.appendChild(btn);
    }

    let zaklad = edit.querySelector('[data-panel="zaklad"]');
    if (!zaklad) {
      zaklad = edit.querySelector('.tab-panel.active') || edit;
    }
    if (zaklad && !document.getElementById('flow-onboard-box')) {
      const box = document.createElement('div');
      box.id = 'flow-onboard-box';
      box.className = 'upload-box';
      box.innerHTML = `
        <h4>Provozní den — FLOW</h4>
        <p class="admin-hint" id="flow-onboard-hint">
          Web můžete mít i bez rezervací. Až budete chtít kalendář a Staff v provozu,
          aktivujte FLOW — přihlášení stejným e-mailem a heslem.
        </p>
        <p id="flow-onboard-msg" class="status-msg"></p>
        <button type="button" id="btn-goto-flow" class="btn btn-primary btn-block">Přejít do FLOW</button>
      `;
      zaklad.insertBefore(box, zaklad.firstChild);
    }

    if (zaklad && !document.getElementById('owner-works-box')) {
      const box = document.createElement('div');
      box.id = 'owner-works-box';
      box.className = 'upload-box';
      box.innerHTML = `
        <h4>Manager také pracuje</h4>
        <p class="admin-hint">
          Zapne pracovní profil na webu (Staff + rezervace) a přepínač
          Manager / Staff ve FLOW — jeden login, bez druhého hesla.
        </p>
        <label class="checkbox" style="display:flex;gap:0.5rem;align-items:flex-start;margin:0.75rem 0;">
          <input type="checkbox" id="owner-works-check">
          <span>Ano — Manager také obsluhuje zákazníky</span>
        </label>
        <p id="owner-works-detail" class="admin-hint"></p>
        <p id="owner-works-msg" class="status-msg"></p>
      `;
      const flowBox = document.getElementById('flow-onboard-box');
      if (flowBox && flowBox.nextSibling) zaklad.insertBefore(box, flowBox.nextSibling);
      else if (flowBox) flowBox.after(box);
      else zaklad.insertBefore(box, zaklad.firstChild);
    }

    if (!edit.querySelector('[data-panel="heslo"]')) {
      const panel = document.createElement('div');
      panel.className = 'tab-panel';
      panel.dataset.panel = 'heslo';
      panel.innerHTML = `
        <p class="admin-hint">
          Změna sdíleného hesla Manager. Stejné heslo platí pro webovou administraci i pro FLOW.
          Nejde o reset — reset hesla zaměstnanců bude jen ve FLOW.
        </p>
        <form id="form-owner-password" class="login-form">
          <label for="owner-pwd-current">Současné heslo</label>
          <input type="password" id="owner-pwd-current" autocomplete="current-password" required>
          <label for="owner-pwd-new">Nové heslo</label>
          <input type="password" id="owner-pwd-new" autocomplete="new-password" required minlength="8">
          <label for="owner-pwd-new2">Nové heslo znovu</label>
          <input type="password" id="owner-pwd-new2" autocomplete="new-password" required minlength="8">
          <p class="admin-hint">Min. 8 znaků, alespoň jedno písmeno a jedno číslo.</p>
          <div id="owner-pwd-msg" class="status-msg"></div>
          <button type="submit" class="btn btn-primary btn-block">Změnit sdílené heslo</button>
        </form>
      `;
      edit.appendChild(panel);
    }

    wireOnce();
    return true;
  }

  let wired = false;
  function wireOnce() {
    if (wired) return;
    const btn = document.getElementById('btn-goto-flow');
    const form = document.getElementById('form-owner-password');
    const works = document.getElementById('owner-works-check');
    if (!btn && !form && !works) return;
    wired = true;

    btn?.addEventListener('click', handleGotoFlow);
    form?.addEventListener('submit', handlePasswordChange);
    works?.addEventListener('change', handleOwnerWorksToggle);

    // Záložka Heslo — pokud app.js nezná panel, přepneme sami
    document.getElementById('edit-section')?.addEventListener('click', (e) => {
      const tab = e.target.closest?.('[data-tab="heslo"]');
      if (!tab) return;
      const edit = document.getElementById('edit-section');
      edit.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === tab));
      edit.querySelectorAll('.tab-panel').forEach((p) => {
        p.classList.toggle('active', p.dataset.panel === 'heslo');
      });
    });
  }

  function escHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function applyOwnerWorksUi(payload) {
    const check = document.getElementById('owner-works-check');
    const detail = document.getElementById('owner-works-detail');
    if (!check) return;
    const ano = !!payload?.ano;
    check.checked = ano;
    if (detail) {
      if (ano && payload.pracovni) {
        detail.innerHTML =
          `Pracovní profil: <strong>${escHtml(payload.pracovni.jmeno)}</strong> ` +
          `<span class="role-pill" title="Manager">Manager</span>. ` +
          'Upravte rozvrh ve Personálu / Staff; ve FLOW nahoře přepnete Manager / Staff.';
      } else {
        detail.textContent =
          'Vypnuto — účet Manager zůstává jen pro správu, na webu se nezobrazuje.';
      }
    }
  }

  async function refreshOwnerWorks() {
    const sid = salonId();
    if (!token() || !sid) return;
    try {
      const data = await api(`/salon/${sid}/flow/majitelka-pracuje/`);
      applyOwnerWorksUi(data);
    } catch (_) {
      /* FLOW ještě nemusí být aktivní — checkbox stejně půjde zapnout (API zajistí FLOW) */
    }
  }

  async function handleOwnerWorksToggle() {
    const check = document.getElementById('owner-works-check');
    const msg = document.getElementById('owner-works-msg');
    const sid = salonId();
    if (!check || !sid || !token() || !isMajitel()) return;
    const ano = !!check.checked;
    if (msg) {
      msg.textContent = ano ? 'Zapínám…' : 'Vypínám…';
      msg.className = 'status-msg';
    }
    check.disabled = true;
    try {
      const data = await api(`/salon/${sid}/flow/majitelka-pracuje/`, {
        method: 'PUT',
        body: JSON.stringify({ ano }),
      });
      applyOwnerWorksUi(data);
      if (msg) {
        msg.textContent = ano
          ? 'Zapnuto. Doplňte rozvrh u pracovního profilu ve Staff.'
          : 'Vypnuto.';
        msg.className = 'status-msg success';
      }
      await refreshFlowOnboard();
    } catch (err) {
      check.checked = !ano;
      if (msg) {
        msg.textContent = err.message || 'Uložení selhalo.';
        msg.className = 'status-msg error';
      }
    } finally {
      check.disabled = false;
    }
  }

  async function refreshFlowOnboard() {
    const hint = document.getElementById('flow-onboard-hint');
    const btn = document.getElementById('btn-goto-flow');
    const sid = salonId();
    if (!hint || !btn || !token() || !sid) return;
    try {
      const data = await api(`/salon/${sid}/flow/aktivace/`);
      if (data.aktivni) {
        hint.textContent = `FLOW je aktivní${data.email ? ` (${data.email})` : ''}. Přihlášení stejným e-mailem a heslem jako sem.`;
        btn.textContent = 'Otevřít FLOW';
      } else {
        hint.textContent =
          'Web můžete mít i bez rezervací. Až budete chtít kalendář a Staff v provozu, aktivujte FLOW — přihlášení stejným e-mailem a heslem.';
        btn.textContent = 'Přejít do FLOW';
      }
      if (data.majitelka_pracuje) applyOwnerWorksUi(data.majitelka_pracuje);
    } catch (err) {
      hint.textContent = err.message || 'Stav FLOW se nepodařilo načíst.';
    }
  }

  async function handleGotoFlow() {
    const msg = document.getElementById('flow-onboard-msg');
    const btn = document.getElementById('btn-goto-flow');
    const sid = salonId();
    if (!token() || !isMajitel() || !sid) return;
    if (msg) {
      msg.textContent = 'Připravuji FLOW…';
      msg.className = 'status-msg';
    }
    if (btn) btn.disabled = true;
    try {
      const email = emailHint();
      const data = await api(`/salon/${sid}/flow/aktivace/`, {
        method: 'POST',
        body: JSON.stringify(email ? { email } : {}),
      });
      if (msg) {
        msg.textContent = data.detail || 'FLOW je připraven.';
        msg.className = 'status-msg success';
      }
      await refreshFlowOnboard();
      window.open(flowAppUrl(), '_blank', 'noopener');
    } catch (err) {
      if (msg) {
        msg.textContent = err.message || 'Aktivace FLOW selhala.';
        msg.className = 'status-msg error';
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function handlePasswordChange(e) {
    e.preventDefault();
    const msg = document.getElementById('owner-pwd-msg');
    const sid = salonId();
    const cur = document.getElementById('owner-pwd-current')?.value || '';
    const neu = document.getElementById('owner-pwd-new')?.value || '';
    const neu2 = document.getElementById('owner-pwd-new2')?.value || '';
    if (!msg || !sid) return;
    if (neu !== neu2) {
      msg.textContent = 'Nová hesla se neshodují.';
      msg.className = 'status-msg error';
      return;
    }
    msg.textContent = 'Ukládám…';
    msg.className = 'status-msg';
    try {
      const data = await api(`/salon/${sid}/rezervace/staff/zmena-hesla/`, {
        method: 'POST',
        body: JSON.stringify({
          current_password: cur,
          new_password: neu,
        }),
      });
      msg.textContent = data.detail || 'Heslo změněno.';
      msg.className = 'status-msg success';
      document.getElementById('form-owner-password')?.reset();
    } catch (err) {
      msg.textContent = err.message || 'Změna hesla selhala.';
      msg.className = 'status-msg error';
    }
  }

  function onAdminShown() {
    if (!isMajitel()) return;
    ensureUi();
    refreshFlowOnboard();
    refreshOwnerWorks();
  }

  function boot() {
    ensureUi();
    if (token() && isMajitel()) {
      refreshFlowOnboard();
      refreshOwnerWorks();
    }
  }

  global.UlovOwnerFlow = {
    ensureUi,
    refreshFlowOnboard,
    refreshOwnerWorks,
    onAdminShown,
    flowAppUrl,
    handleGotoFlow,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(window);
