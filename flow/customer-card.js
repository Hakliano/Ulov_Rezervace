/**
 * P5.3 — FLOW Zákazníci nad Archivníkem (/api/flow/kartoteka/*).
 * Starou kartotéku (CustomerCard) odtud nevolá.
 */
(function () {
  'use strict';

  const PAGE_SIZE = 50;
  let ktSelectedUuid = null;
  let ktPage = 1;
  let ktSearchTimer = null;

  function fmtDay(iso) {
    if (!iso) return '';
    const raw = String(iso);
    const d = raw.length <= 10 ? new Date(`${raw}T00:00:00`) : new Date(raw);
    if (Number.isNaN(d.getTime())) return esc(raw);
    return `${d.getDate()}. ${d.getMonth() + 1}. ${d.getFullYear()}`;
  }

  function displayName(c) {
    return (c.display_name || `${c.jmeno || ''} ${c.prijmeni || ''}`).trim() || c.email || 'Zákazník';
  }

  function isArchived(c) {
    return c && c.stav === 'archivovany';
  }

  async function loadCustomers() {
    const list = $('#cc-list');
    const pager = $('#cc-pager');
    if (!list) return;
    const q = ($('#cc-search')?.value || '').trim();
    const stav = $('#cc-filter-stav')?.value || '';
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (stav) params.set('stav', stav);
    params.set('page', String(ktPage));
    params.set('page_size', String(PAGE_SIZE));
    list.innerHTML = '<p class="empty">Načítám…</p>';
    if (pager) pager.innerHTML = '';
    try {
      const data = await api(`/flow/kartoteka/zakaznici/?${params}`);
      const rows = data.vysledky || [];
      if (!rows.length) {
        list.innerHTML = '<p class="empty">Zatím žádní zákazníci v kartotéce.</p>';
      } else {
        list.innerHTML = rows.map((c) => `
          <button type="button" class="cc-list-item${c.uuid === ktSelectedUuid ? ' active' : ''}" data-kt-uuid="${esc(c.uuid)}">
            <strong>${esc(displayName(c))}</strong>
            <span class="meta">${esc(c.email || 'bez e-mailu')}${c.telefon ? ' · ' + esc(c.telefon) : ''}</span>
            ${isArchived(c) ? '<span class="badge">archivovaný</span>' : ''}
          </button>
        `).join('');
      }
      if (pager && data.celkem_stranek > 1) {
        pager.innerHTML = `
          <button type="button" class="btn tiny ghost" data-kt-page="prev" ${ktPage <= 1 ? 'disabled' : ''}>←</button>
          <span class="meta">Stránka ${esc(data.stranka)} / ${esc(data.celkem_stranek)}</span>
          <button type="button" class="btn tiny ghost" data-kt-page="next" ${ktPage >= data.celkem_stranek ? 'disabled' : ''}>→</button>
        `;
      }
      const detail = $('#cc-detail');
      if (ktSelectedUuid) {
        await openCustomer(ktSelectedUuid);
      } else if (detail && !detail.querySelector('#kt-entry-form, #kt-object-form')) {
        detail.innerHTML = '<p class="empty">Vyberte zákazníka v seznamu, nebo ho založte z rezervace.</p>';
      }
    } catch (e) {
      list.innerHTML = `<p class="empty">${esc(e.message || 'Chyba načtení')}</p>`;
    }
  }

  async function openCustomer(uuid) {
    if (!uuid) return;
    ktSelectedUuid = uuid;
    $$('.cc-list-item').forEach((el) => {
      el.classList.toggle('active', el.dataset.ktUuid === uuid);
    });
    const detail = $('#cc-detail');
    if (!detail) return;
    detail.innerHTML = '<p class="empty">Načítám kartu…</p>';
    try {
      const c = await api(`/flow/kartoteka/zakaznici/${uuid}/`);
      renderDetail(c);
    } catch (e) {
      const msg = e.message || 'Zákazník nenalezen.';
      detail.innerHTML = `<p class="empty">${esc(msg)}</p>`;
    }
  }

  function renderDetail(c) {
    const detail = $('#cc-detail');
    if (!detail) return;
    const archived = isArchived(c);
    const objects = c.objekty || [];
    const entries = c.posledni_zapisy || [];
    const reminders = c.pripominky || [];
    const contact = [c.email, c.telefon].filter(Boolean).join(' · ');
    const objHtml = objects.length
      ? `<ul class="kt-objects">${objects.map((o) => `<li>${esc(o.display_name || o.nazev || 'Objekt')} · ${esc(o.typ_nazev || '')}</li>`).join('')}</ul>`
      : '<p class="empty">Zákazník zatím nemá žádný objekt.</p>';
    const entryHtml = entries.length
      ? `<div class="list">${entries.map((e) => `
          <article class="item">
            <div class="item-top">
              <time>${esc(fmtDay(e.nastalo))}</time>
              <span class="meta">${esc(e.typ_zapisu || 'Poznámka')}${e.objekt_nazev ? ' · ' + esc(e.objekt_nazev) : ''}</span>
            </div>
            ${e.nadpis ? `<p class="meta">${esc(e.nadpis)}</p>` : ''}
            <p class="cc-visit-text">${esc(e.text)}</p>
          </article>
        `).join('')}</div>`
      : '<p class="empty">Zatím žádné zápisy.</p>';
    const remHtml = reminders.length
      ? `<div class="kt-reminders">${reminders.map((r) => {
          const mark = r.prosla ? '⚠ ' : '';
          const obj = r.objekt_nazev ? ` · ${r.objekt_nazev}` : '';
          const when = r.termin ? ` · ${fmtDay(r.termin)}` : '';
          return `<p class="kt-remind${r.prosla ? ' warn' : ''}">${esc(mark + (r.text || 'Připomínka') + obj)}${esc(when)}</p>`;
        }).join('')}</div>`
      : '';
    const writeBlock = archived
      ? '<p class="hint">Archivovaný zákazník je ve FLOW jen ke čtení. Zápis a objekt se zakládají v Archivníku po případné reaktivaci.</p>'
      : `
        <div class="actions" style="margin:.75rem 0">
          <button type="button" class="btn primary" data-kt-entry="${esc(c.uuid)}">Přidat zápis</button>
          <button type="button" class="btn ghost" data-kt-object="${esc(c.uuid)}">Založit objekt</button>
        </div>
        <div id="kt-write-box"></div>
      `;
    detail.innerHTML = `
      <div class="row between wrap gap">
        <h2 class="section-title">${esc(displayName(c))}</h2>
        ${archived ? '<span class="badge">archivovaný</span>' : ''}
      </div>
      <p class="meta">${esc(contact || 'Bez e-mailu a telefonu')}</p>
      ${c.poznamka ? `<p class="cc-note">${esc(c.poznamka)}</p>` : ''}
      ${writeBlock}
      <h3>Objekty</h3>
      ${objHtml}
      <h3>Poslední zápisy</h3>
      ${entryHtml}
      ${remHtml}
      <div class="actions" style="margin-top:1rem">
        <button type="button" class="btn primary" data-kt-nova-rez="${esc(c.uuid)}">Nová rezervace</button>
        ${c.archivnik_url ? `<a class="btn ghost" href="${esc(c.archivnik_url)}" target="_blank" rel="noopener noreferrer" data-kt-archivnik>Otevřít kompletní kartu v Archivníku</a>` : ''}
      </div>
    `;
  }

  function showEntryForm(c) {
    const box = $('#kt-write-box');
    if (!box) return;
    const opts = (c.objekty || []).map((o) =>
      `<option value="${esc(o.uuid)}">${esc(o.display_name || o.nazev)} · ${esc(o.typ_nazev || '')}</option>`
    ).join('');
    box.innerHTML = `
      <form id="kt-entry-form" class="cc-form" data-uuid="${esc(c.uuid)}">
        <h3>Nový zápis</h3>
        <label>Zápis<textarea class="input" name="text" rows="4" required></textarea></label>
        <label>Objekt
          <select class="input" name="objekt_uuid">
            <option value="">Bez objektu</option>
            ${opts}
          </select>
        </label>
        <div class="actions">
          <button type="submit" class="btn primary">Přidat</button>
          <button type="button" class="btn ghost" data-kt-cancel-write>Zpět</button>
        </div>
        <p id="kt-write-msg" class="msg" hidden></p>
      </form>
    `;
  }

  async function showObjectForm(uuid) {
    const box = $('#kt-write-box');
    if (!box) return;
    box.innerHTML = '<p class="empty">Načítám typy…</p>';
    try {
      const typy = await api('/flow/kartoteka/typy-objektu/');
      if (!typy.length) {
        box.innerHTML = '<p class="empty">Nejsou k dispozici typy objektů. Doplňte je v Archivníku.</p>';
        return;
      }
      const opts = typy.map((t) =>
        `<option value="${esc(t.uuid)}" data-need-name="${t.vyzaduje_nazev ? '1' : '0'}">${esc(t.nazev)}</option>`
      ).join('');
      box.innerHTML = `
        <form id="kt-object-form" class="cc-form" data-uuid="${esc(uuid)}">
          <h3>Nový objekt</h3>
          <label>Typ<select class="input" name="typ_uuid" id="kt-typ">${opts}</select></label>
          <label id="kt-nazev-wrap">Název<input class="input" name="nazev" id="kt-nazev" type="text"></label>
          <div class="actions">
            <button type="submit" class="btn primary">Založit</button>
            <button type="button" class="btn ghost" data-kt-cancel-write>Zpět</button>
          </div>
          <p id="kt-write-msg" class="msg" hidden></p>
        </form>
      `;
      syncObjectNameRequired();
      box.querySelector('#kt-typ')?.addEventListener('change', syncObjectNameRequired);
    } catch (e) {
      box.innerHTML = `<p class="empty">${esc(e.message || 'Typy se nepodařilo načíst.')}</p>`;
    }
  }

  function syncObjectNameRequired() {
    const sel = $('#kt-typ');
    const input = $('#kt-nazev');
    const wrap = $('#kt-nazev-wrap');
    if (!sel || !input) return;
    const need = sel.options[sel.selectedIndex]?.dataset.needName === '1';
    input.required = need;
    if (wrap) wrap.classList.toggle('kt-optional', !need);
  }

  function showWriteMsg(text) {
    const m = $('#kt-write-msg');
    if (!m) return;
    m.hidden = false;
    m.textContent = text;
  }

  function attachCalendarButtons(container, items) {
    const byId = new Map((items || []).map((r) => [String(r.id), r]));
    container.querySelectorAll('article.item[data-id]').forEach((art) => {
      if (art.querySelector('[data-kt-open], [data-kt-create], [data-kt-noemail]')) return;
      const r = byId.get(String(art.dataset.id));
      if (!r) return;
      let actions = art.querySelector('.actions');
      if (!actions) {
        actions = document.createElement('div');
        actions.className = 'actions';
        art.appendChild(actions);
      }
      const uuid = r.archivnik_customer_uuid;
      const email = (r.kontaktni_email || '').trim();
      if (uuid) {
        actions.insertAdjacentHTML(
          'beforeend',
          `<button type="button" class="btn tiny ghost" data-kt-open="${esc(uuid)}">Otevřít kartu zákazníka</button>`,
        );
      } else if (email) {
        actions.insertAdjacentHTML(
          'beforeend',
          `<button type="button" class="btn tiny ghost" data-kt-create="${r.id}">Založit zákazníka</button>`,
        );
      } else {
        actions.insertAdjacentHTML(
          'beforeend',
          '<p class="meta" data-kt-noemail>Zákazníka nelze automaticky propojit – rezervace nemá e-mail.</p>',
        );
      }
    });
  }

  if (typeof window.setTab === 'function') {
    const _setTab = window.setTab;
    window.setTab = function (name) {
      _setTab(name);
      if (name === 'karty') loadCustomers();
    };
  }

  if (typeof window.renderRezervaceList === 'function') {
    const _render = window.renderRezervaceList;
    window.renderRezervaceList = function (container, items, options) {
      _render(container, items, options);
      attachCalendarButtons(container, items);
    };
  }

  document.addEventListener('click', async (ev) => {
    const pageBtn = ev.target.closest('[data-kt-page]');
    if (pageBtn && !pageBtn.disabled) {
      ktPage += pageBtn.dataset.ktPage === 'next' ? 1 : -1;
      if (ktPage < 1) ktPage = 1;
      await loadCustomers();
      return;
    }
    const openBtn = ev.target.closest('[data-kt-open]');
    if (openBtn) {
      ktSelectedUuid = openBtn.dataset.ktOpen;
      window.setTab('karty');
      await openCustomer(ktSelectedUuid);
      return;
    }
    const createBtn = ev.target.closest('[data-kt-create]');
    if (createBtn) {
      createBtn.disabled = true;
      try {
        const created = await api('/flow/kartoteka/zakaznici/', {
          method: 'POST',
          body: JSON.stringify({ rezervace_id: Number(createBtn.dataset.ktCreate) }),
        });
        const uuid = created.zakaznik?.uuid;
        if (!uuid) throw new Error(created.detail || 'Zákazníka se nepodařilo založit.');
        createBtn.outerHTML = `<button type="button" class="btn tiny ghost" data-kt-open="${esc(uuid)}">Otevřít kartu zákazníka</button>`;
        ktSelectedUuid = uuid;
        window.setTab('karty');
        await openCustomer(uuid);
      } catch (e) {
        alert(e.message || 'Založení selhalo');
        createBtn.disabled = false;
      }
      return;
    }
    const listBtn = ev.target.closest('[data-kt-uuid]');
    if (listBtn && listBtn.closest('#cc-list')) {
      await openCustomer(listBtn.dataset.ktUuid);
      return;
    }
    const entryBtn = ev.target.closest('[data-kt-entry]');
    if (entryBtn) {
      try {
        const c = await api(`/flow/kartoteka/zakaznici/${entryBtn.dataset.ktEntry}/`);
        showEntryForm(c);
      } catch (e) {
        alert(e.message || 'Chyba');
      }
      return;
    }
    const objBtn = ev.target.closest('[data-kt-object]');
    if (objBtn) {
      await showObjectForm(objBtn.dataset.ktObject);
      return;
    }
    if (ev.target.closest('[data-kt-cancel-write]')) {
      if (ktSelectedUuid) await openCustomer(ktSelectedUuid);
      return;
    }
    const novaRezBtn = ev.target.closest('[data-kt-nova-rez]');
    if (novaRezBtn) {
      if (typeof openNova !== 'function') {
        alert('Formulář rezervace není dostupný.');
        return;
      }
      try {
        const c = await api(`/flow/kartoteka/zakaznici/${novaRezBtn.dataset.ktNovaRez}/`);
        await openNova('', {
          nick: displayName(c),
          email: c.email || '',
          telefon: c.telefon || '',
          poznamka: c.poznamka || '',
        });
      } catch (e) {
        alert(e.message || 'Nelze otevřít rezervaci');
      }
    }
  });

  document.addEventListener('submit', async (ev) => {
    if (ev.target.id === 'kt-entry-form') {
      ev.preventDefault();
      const uuid = ev.target.dataset.uuid;
      const fd = new FormData(ev.target);
      const objekt = (fd.get('objekt_uuid') || '').trim();
      try {
        await api(`/flow/kartoteka/zakaznici/${uuid}/zapisy/`, {
          method: 'POST',
          body: JSON.stringify({
            text: fd.get('text'),
            objekt_uuid: objekt || null,
          }),
        });
        await openCustomer(uuid);
      } catch (e) {
        showWriteMsg(e.message || 'Zápis se nepodařilo uložit.');
      }
      return;
    }
    if (ev.target.id === 'kt-object-form') {
      ev.preventDefault();
      const uuid = ev.target.dataset.uuid;
      const fd = new FormData(ev.target);
      try {
        await api(`/flow/kartoteka/zakaznici/${uuid}/objekty/`, {
          method: 'POST',
          body: JSON.stringify({
            typ_uuid: fd.get('typ_uuid'),
            nazev: fd.get('nazev') || '',
          }),
        });
        await openCustomer(uuid);
      } catch (e) {
        showWriteMsg(e.message || 'Objekt se nepodařilo založit.');
      }
    }
  });

  document.addEventListener('input', (ev) => {
    if (ev.target.id === 'cc-search') {
      clearTimeout(ktSearchTimer);
      ktSearchTimer = setTimeout(() => {
        ktPage = 1;
        loadCustomers();
      }, 250);
    }
  });
  document.addEventListener('change', (ev) => {
    if (ev.target.id === 'cc-filter-stav') {
      ktPage = 1;
      loadCustomers();
    }
  });
})();
