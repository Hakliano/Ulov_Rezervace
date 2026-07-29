/**
 * Schválené chování majitele ze salon2 — FLOW aktivace + změna sdíleného hesla.
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

  function emailHint() {
    const c = CFG();
    if (typeof c.getEmail === 'function') return (c.getEmail() || '').trim();
    return (document.getElementById('staff-login')?.value || '').trim();
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
          Web můžete mít i bez rezervací. Až budete chtít kalendář a personál v provozu,
          aktivujte FLOW — přihlášení stejným e-mailem a heslem.
        </p>
        <p id="flow-onboard-msg" class="status-msg"></p>
        <button type="button" id="btn-goto-flow" class="btn btn-primary btn-block">Přejít do FLOW</button>
      `;
      zaklad.insertBefore(box, zaklad.firstChild);
    }

    if (!edit.querySelector('[data-panel="heslo"]')) {
      const panel = document.createElement('div');
      panel.className = 'tab-panel';
      panel.dataset.panel = 'heslo';
      panel.innerHTML = `
        <p class="admin-hint">
          Změna sdíleného hesla majitele. Stejné heslo platí pro webovou administraci i pro FLOW.
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
    if (!btn && !form) return;
    wired = true;

    btn?.addEventListener('click', handleGotoFlow);
    form?.addEventListener('submit', handlePasswordChange);

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
          'Web můžete mít i bez rezervací. Až budete chtít kalendář a personál v provozu, aktivujte FLOW — přihlášení stejným e-mailem a heslem.';
        btn.textContent = 'Přejít do FLOW';
      }
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
  }

  function boot() {
    ensureUi();
    if (token() && isMajitel()) refreshFlowOnboard();
  }

  global.UlovOwnerFlow = {
    ensureUi,
    refreshFlowOnboard,
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
