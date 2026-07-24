(function () {
  const bootEl = document.getElementById('salon-ops-boot');
  const tokenEl = document.getElementById('partner-api-token');
  if (!bootEl || !tokenEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const token = JSON.parse(tokenEl.textContent);
  const salonId = boot.salonId;
  const activeTab = boot.activeTab;
  const OPS_TABS = new Set([
    'web', 'banner', 'cenik', 'novinky', 'personal', 'rezervace', 'emaily', 'smtp', 'odkazy',
  ]);
  if (!OPS_TABS.has(activeTab)) return;

  const API_BASE = '/api';
  const $ = (sel) => document.querySelector(sel);
  let salonCache = null;
  let nastaveniCache = null;

  function setMsg(text, ok) {
    const el = $('#ops-msg');
    if (!el) return;
    el.hidden = !text;
    el.textContent = text || '';
    el.className = 'ops-msg ' + (ok ? 'ok' : 'err');
  }

  async function api(path, opts = {}) {
    const headers = {
      Accept: 'application/json',
      'X-Partner-Token': token,
      ...(opts.headers || {}),
    };
    if (opts.body && !(opts.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(`${API_BASE}${path}`, {
      ...opts,
      headers,
      credentials: 'omit',
    });
    let data = null;
    const raw = await res.text();
    try { data = raw ? JSON.parse(raw) : null; } catch { data = { detail: raw }; }
    if (!res.ok) {
      const detail = data?.detail || data?.non_field_errors?.[0] || res.statusText;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }
  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fillWeb(s) {
    if (!$('#w-name')) return;
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
    if (!$('#b-text')) return;
    $('#b-text').value = s.banner_text || '';
    $('#b-od').value = s.banner_od || '';
    $('#b-do').value = s.banner_do || '';
    $('#b-on').checked = !!s.banner_enabled;
  }

  function renderCenik(items) {
    const box = $('#cenik-list');
    if (!box) return;
    box.innerHTML = '';
    (items || []).forEach((item, idx) => {
      const row = document.createElement('div');
      row.className = 'ops-block';
      row.innerHTML = `
        <div class="form-grid">
          <label>Název <input data-f="nazev" value="${escapeAttr(item.nazev || '')}"></label>
          <label>Cena <input data-f="cena" type="number" step="0.01" value="${item.cena ?? ''}"></label>
          <label>Délka min <input data-f="delka_minut" type="number" value="${item.delka_minut ?? ''}"></label>
          <label>Pořadí <input data-f="poradi" type="number" value="${item.poradi ?? idx}"></label>
          <label class="check"><span><input data-f="aktivni" type="checkbox" ${item.aktivni !== false ? 'checked' : ''}> Aktivní</span></label>
          <label class="check"><span><input data-f="rizikovy" type="checkbox" ${item.rizikovy ? 'checked' : ''}> Rizikový</span></label>
          <input type="hidden" data-f="id" value="${item.id || ''}">
        </div>`;
      box.appendChild(row);
    });
  }

  function collectCenik() {
    return [...($('#cenik-list')?.children || [])].map((row) => {
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
    if (!box) return;
    box.innerHTML = '';
    (items || []).forEach((item) => {
      const row = document.createElement('div');
      row.className = 'ops-block';
      row.innerHTML = `
        <label>Nadpis <input data-f="nadpis" value="${escapeAttr(item.nadpis || '')}"></label>
        <label class="full">Text <textarea data-f="text" rows="3">${escapeHtml(item.text || '')}</textarea></label>
        <input type="hidden" data-f="id" value="${item.id || ''}">`;
      box.appendChild(row);
    });
  }

  function collectNovinky() {
    return [...($('#novinky-list')?.children || [])].map((row) => {
      const get = (f) => row.querySelector(`[data-f="${f}"]`);
      const idVal = get('id')?.value;
      const out = { nadpis: get('nadpis').value.trim(), text: get('text').value };
      if (idVal) out.id = Number(idVal);
      return out;
    }).filter((x) => x.nadpis);
  }

  function fillRez(n) {
    if (!$('#r-interval')) return;
    $('#r-interval').value = n.interval_minut ?? '';
    $('#r-min').value = n.min_predstih_hodin ?? '';
    $('#r-max').value = n.max_predstih_mesicu ?? '';
    $('#r-storno').value = n.storno_do_hodin ?? '';
    $('#r-potv').value = n.potvrzeni_platnost_hodin ?? '';
    $('#r-gdpr').value = n.gdpr_zasady_verze || '';
    $('#r-auto').checked = !!n.auto_potvrzeni;
  }

  const MAX_NOTIFIKACE = 8;
  const NOTIF_POPISY = [
    'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
    'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
    'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show',
    'Žádost o úhradu po návštěvě (QR) — FLOW: Platba QR',
    'Žádost o zálohu před termínem (QR) — FLOW: Požádat o zálohu',
    'Storno rezervace — při zrušení salonem / ve FLOW',
    'Potvrzení rezervace — automaticky při potvrzení (včetně textu o možné záloze u rizikových služeb)',
    'Záloha přijata — odešle se tlačítkem Záloha OK ve FLOW',
  ];

  function manualTypForIndex(i, n) {
    return n.manual_typ || (
      i === 7 ? 'zaloha_ok'
        : i === 6 ? 'potvrzeni'
          : i === 5 ? 'storno'
            : i === 4 ? 'zaloha'
              : i === 3 ? 'platba'
                : 'noshow'
    );
  }

  function renderTagGuide(tagy) {
    const el = $('#e-tag-guide');
    if (!el) return;
    el.replaceChildren();
    if (!tagy?.length) return;
    const table = document.createElement('table');
    table.className = 'tag-table';
    table.innerHTML = '<thead><tr><th>Tag</th><th>Co se vypíše</th><th>Příklad</th></tr></thead>';
    const tbody = document.createElement('tbody');
    tagy.forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><code>${escapeHtml(row.tag || '')}</code></td><td>${escapeHtml(row.popis || '')}</td><td class="muted">${escapeHtml(row.priklad || '')}</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    el.appendChild(table);
  }

  function buildNotifCard(n, i) {
    const isManual = i >= 2 || n.manual || n.offset === 'manual';
    const manualTyp = manualTypForIndex(i, n);
    const card = document.createElement('article');
    card.className = 'notif-card' + (isManual ? ' notif-manual' : '') + ((!n.aktivni && !isManual) ? ' notif-inactive' : '');
    card.dataset.idx = String(i);
    card.dataset.manualTyp = manualTyp;

    let headerHtml = '';
    if (isManual) {
      const hints = {
        platba: 'Ručně: Platba QR ve FLOW po návštěvě — v e-mailu bude QR kód.',
        zaloha: 'Ručně: Požádat o zálohu ve FLOW — QR + částka.',
        storno: 'Odešle se při stornu (admin / FLOW).',
        potvrzeni: 'Odešle se automaticky při potvrzení rezervace.',
        zaloha_ok: 'Odešle se tlačítkem Záloha OK ve FLOW.',
        noshow: 'Ručně: NO-show u rezervace v kalendáři / FLOW.',
      };
      headerHtml = `<p class="notif-manual-hint">${escapeHtml(hints[manualTyp] || hints.noshow)}</p>`;
    } else {
      headerHtml = `
        <label class="check"><span><input type="checkbox" class="notif-aktivni" ${n.aktivni ? 'checked' : ''}> Odesílat automaticky</span></label>
        <label>Čas odeslání <input type="text" class="notif-offset" value="${escapeAttr(n.offset || '+24')}" placeholder="+24 nebo -2"></label>`;
    }

    card.innerHTML = `
      <div class="notif-card-head">
        <h3>Notifikace ${i + 1}</h3>
        <p class="muted">${escapeHtml(NOTIF_POPISY[i] || '')}</p>
      </div>
      <div class="notif-header form-grid">${headerHtml}</div>
      <label>Předmět e-mailu <input type="text" class="notif-predmet" value="${escapeAttr(n.predmet || '')}"></label>
      <label class="full">Text e-mailu <textarea class="notif-text" rows="8">${escapeHtml(n.text || '')}</textarea></label>
      <input type="hidden" class="notif-id" value="${escapeAttr(n.id || '')}">`;

    if (!isManual) {
      const cb = card.querySelector('.notif-aktivni');
      cb?.addEventListener('change', () => {
        card.classList.toggle('notif-inactive', !cb.checked);
      });
    }
    return card;
  }

  function renderNotifikace(notifikace, tagy, hint) {
    const hintEl = $('#notif-hint');
    if (hintEl) hintEl.textContent = hint || '';
    renderTagGuide(tagy);
    const list = $('#notifikace-list');
    if (!list) return;
    list.replaceChildren();
    const items = [...(notifikace || [])];
    while (items.length < MAX_NOTIFIKACE) {
      items.push({ id: '', offset: 'manual', manual: true, aktivni: false, predmet: '', text: '' });
    }
    items.slice(0, MAX_NOTIFIKACE).forEach((n, i) => list.appendChild(buildNotifCard(n, i)));
  }

  function collectNotifikace() {
    return [...document.querySelectorAll('#notifikace-list .notif-card')].map((card, i) => {
      const manual = card.classList.contains('notif-manual') || i >= 2;
      const id = card.querySelector('.notif-id')?.value || undefined;
      if (manual) {
        const manualTyp = card.dataset.manualTyp || manualTypForIndex(i, {});
        return {
          id,
          manual: true,
          offset: 'manual',
          manual_typ: manualTyp,
          aktivni: manualTyp !== 'noshow',
          predmet: card.querySelector('.notif-predmet')?.value ?? '',
          text: card.querySelector('.notif-text')?.value ?? '',
        };
      }
      return {
        id,
        manual: false,
        offset: card.querySelector('.notif-offset')?.value || '+24',
        aktivni: !!card.querySelector('.notif-aktivni')?.checked,
        predmet: card.querySelector('.notif-predmet')?.value ?? '',
        text: card.querySelector('.notif-text')?.value ?? '',
      };
    });
  }

  function fillEmaily(n) {
    if (!$('#e-recenze')) return;
    $('#e-recenze').value = n.recenze_url || '';
    renderNotifikace(n.notifikace || [], n.notifikace_tagy, n.notifikace_placeholders);
  }

  function fillSmtp(e) {
    if (!$('#s-host')) return;
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

  function fillLinks() {
    if (!$('#link-web')) return;
    const isStaging = location.hostname.includes('staging');
    const demoUrl = isStaging
      ? `https://www.staging.ulovklienty.cz/salon${salonId}/`
      : (salonId <= 8
        ? `https://demo${salonId}.ulovklienty.cz/`
        : `https://www.ulovklienty.cz/salon${salonId}/`);
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

  async function flowStatus(zamestnanecId) {
    try {
      const data = await api(`/salon/${salonId}/flow/zamestnanci/${zamestnanecId}/`);
      if (data && data.ma_flow && data.ucet) return data.ucet;
      return null;
    } catch {
      return null;
    }
  }

  async function renderStaff() {
    const box = $('#staff-list');
    if (!box) return;
    const data = await api(`/salon/${salonId}/rezervace/admin/zamestnanci/`);
    box.innerHTML = '';
    for (const z of (data.zamestnanci || [])) {
      const flow = await flowStatus(z.id);
      const row = document.createElement('div');
      row.className = 'ops-block';
      const flowHtml = flow && flow.id
        ? `
          <p class="muted">FLOW: ${escapeHtml(flow.email || '')}
            ${flow.aktivni === false ? ' · neaktivní' : ' · aktivní'}
            ${flow.visible_overview ? ' · vidí přehled' : ''}</p>
          <label class="check"><span><input data-flow-overview type="checkbox" ${flow.visible_overview ? 'checked' : ''}> Vidí všechny rezervace (přehled)</span></label>
          <div class="form-actions-row">
            <button type="button" class="btn btn-secondary" data-flow-save="${flow.id}">Uložit FLOW</button>
            <button type="button" class="btn btn-warning" data-flow-reset="${flow.id}">Reset FLOW hesla</button>
          </div>`
        : `
          <label>E-mail pro FLOW <input data-flow-email type="email" placeholder="jmeno@salon.cz" value="${escapeAttr(z.email || '')}"></label>
          <label class="check"><span><input data-flow-overview-new type="checkbox"> Vidí všechny rezervace</span></label>
          <button type="button" class="btn btn-primary" data-flow-create="${z.id}">Vytvořit FLOW přístup</button>`;
      row.innerHTML = `
        <strong>${escapeHtml(z.jmeno || '')}</strong>
        <span class="muted"> · ${escapeHtml(z.role || '')}</span>
        <label>Číslo účtu / IBAN
          <input data-ucet value="${escapeAttr(z.cislo_uctu || '')}" placeholder="CZ… nebo 123456789/0100">
        </label>
        <button type="button" class="btn btn-secondary" data-save-staff="${z.id}">Uložit účet</button>
        <hr class="ops-hr">
        ${flowHtml}`;
      box.appendChild(row);
    }

    box.querySelectorAll('[data-save-staff]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-save-staff');
        const ucet = btn.parentElement.querySelector('[data-ucet]').value.trim();
        try {
          await api(`/salon/${salonId}/rezervace/admin/zamestnanci/${id}/`, {
            method: 'PUT',
            body: JSON.stringify({ cislo_uctu: ucet }),
          });
          setMsg('Účet pracovníka uložen.', true);
        } catch (err) {
          setMsg(err.message, false);
        }
      });
    });

    box.querySelectorAll('[data-flow-create]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-flow-create'));
        const wrap = btn.closest('.ops-block');
        const email = wrap.querySelector('[data-flow-email]')?.value.trim();
        const visible = !!wrap.querySelector('[data-flow-overview-new]')?.checked;
        if (!email) {
          setMsg('Zadej e-mail pro FLOW.', false);
          return;
        }
        try {
          await api(`/salon/${salonId}/flow/ucty/`, {
            method: 'POST',
            body: JSON.stringify({
              zamestnanec_id: id,
              email,
              visible_overview: visible,
            }),
          });
          setMsg('FLOW přístup vytvořen (heslo e-mailem).', true);
          await renderStaff();
        } catch (err) {
          setMsg(err.message, false);
        }
      });
    });

    box.querySelectorAll('[data-flow-save]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const ucetId = btn.getAttribute('data-flow-save');
        const wrap = btn.closest('.ops-block');
        const visible = !!wrap.querySelector('[data-flow-overview]')?.checked;
        try {
          await api(`/salon/${salonId}/flow/ucty/${ucetId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ visible_overview: visible, aktivni: true }),
          });
          setMsg('FLOW nastavení uloženo.', true);
        } catch (err) {
          setMsg(err.message, false);
        }
      });
    });

    box.querySelectorAll('[data-flow-reset]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const ucetId = btn.getAttribute('data-flow-reset');
        try {
          await api(`/salon/${salonId}/flow/ucty/${ucetId}/reset-hesla/`, { method: 'POST', body: '{}' });
          setMsg('FLOW heslo resetováno (e-mailem).', true);
        } catch (err) {
          setMsg(err.message, false);
        }
      });
    });
  }

  function bindForms() {
    $('#form-web')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const payload = {
          name: $('#w-name').value.trim(),
          email: $('#w-email').value.trim(),
          phone: $('#w-phone').value.trim(),
          address: $('#w-address').value.trim(),
          description: $('#w-desc').value,
        };
        if (!$('#w-logo').value.trim()) payload.logo_url = '';
        if (!$('#w-favicon').value.trim()) payload.favicon_url = '';
        salonCache = await api(`/salon/${salonId}/`, { method: 'PUT', body: JSON.stringify(payload) });
        fillWeb(salonCache);
        setMsg('Web uložen.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });

    $('#form-banner')?.addEventListener('submit', async (e) => {
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
        setMsg('Banner uložen.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });

    $('#btn-add-cenik')?.addEventListener('click', () => {
      renderCenik([...(collectCenik()), {
        nazev: '', cena: 0, delka_minut: 60, poradi: 0, aktivni: true, rizikovy: false,
      }]);
    });
    $('#btn-save-cenik')?.addEventListener('click', async () => {
      try {
        salonCache = await api(`/salon/${salonId}/`, {
          method: 'PUT',
          body: JSON.stringify({ cenik: collectCenik() }),
        });
        renderCenik(salonCache.cenik || []);
        setMsg('Ceník uložen.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });

    $('#btn-add-novinka')?.addEventListener('click', () => {
      renderNovinky([...(collectNovinky()), { nadpis: '', text: '' }]);
    });
    $('#btn-save-novinky')?.addEventListener('click', async () => {
      try {
        salonCache = await api(`/salon/${salonId}/`, {
          method: 'PUT',
          body: JSON.stringify({ novinky: collectNovinky() }),
        });
        renderNovinky(salonCache.novinky || []);
        setMsg('Novinky uloženy.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });

    $('#form-rez')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`, {
          method: 'PUT',
          body: JSON.stringify({
            interval_minut: Number($('#r-interval').value) || 15,
            min_predstih_hodin: Number($('#r-min').value) || 0,
            max_predstih_mesicu: Number($('#r-max').value) || 3,
            storno_do_hodin: Number($('#r-storno').value) || 24,
            potvrzeni_platnost_hodin: Number($('#r-potv').value) || 24,
            gdpr_zasady_verze: $('#r-gdpr').value.trim(),
            auto_potvrzeni: $('#r-auto').checked,
            notifikace: nastaveniCache?.notifikace || [],
          }),
        });
        fillRez(nastaveniCache);
        setMsg('Pravidla rezervací uložena.', true);
      } catch (err) {
        setMsg(err.message, false);
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

    $('#btn-save-emaily')?.addEventListener('click', async () => {
      try {
        nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`, {
          method: 'PUT',
          body: JSON.stringify({
            ...nastaveniCache,
            recenze_url: $('#e-recenze').value.trim(),
            notifikace: collectNotifikace(),
          }),
        });
        fillEmaily(nastaveniCache);
        setMsg('E-mailové šablony uloženy.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });

    $('#form-smtp')?.addEventListener('submit', async (e) => {
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
        setMsg('SMTP/IMAP uloženo.', true);
      } catch (err) {
        setMsg(err.message, false);
      }
    });
  }

  async function bootOps() {
    setMsg('Načítám data salonu…', true);
    try {
      salonCache = await api(`/partner/salony/${salonId}/`);
      if (['web', 'banner', 'cenik', 'novinky'].includes(activeTab)) {
        fillWeb(salonCache);
        fillBanner(salonCache);
        renderCenik(salonCache.cenik || []);
        renderNovinky(salonCache.novinky || []);
      }
      if (['rezervace', 'emaily'].includes(activeTab)) {
        nastaveniCache = await api(`/salon/${salonId}/rezervace/admin/nastaveni/`);
        fillRez(nastaveniCache);
        fillEmaily(nastaveniCache);
      }
      if (activeTab === 'smtp') {
        fillSmtp(await api(`/salon/${salonId}/admin/email/`));
      }
      if (activeTab === 'personal') {
        await renderStaff();
      }
      if (activeTab === 'odkazy') {
        fillLinks();
      }
      bindForms();
      setMsg('', true);
    } catch (err) {
      setMsg(err.message, false);
    }
  }

  bootOps();
})();
