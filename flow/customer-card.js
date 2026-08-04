/**
 * feature/flow-customer-card — FLOW UI pro Kartu zákazníka.
 * Samostatný soubor: při rollbacku stačí odstranit tento script + tab v index.html.
 */
(function () {
  'use strict';

  let ccSelectedId = null;
  let ccSearchTimer = null;

  function todayYmd() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
  }

  async function loadCustomerCards() {
    const list = $('#cc-list');
    const detail = $('#cc-detail');
    if (!list) return;
    const q = ($('#cc-search')?.value || '').trim();
    const stav = $('#cc-filter-stav')?.value || '';
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (stav) params.set('stav', stav);
    list.innerHTML = '<p class="empty">Načítám…</p>';
    try {
      const rows = await api(`/flow/zakaznicke-karty/?${params}`);
      if (!rows.length) {
        list.innerHTML = '<p class="empty">Zatím žádné zákaznické karty.</p>';
      } else {
        list.innerHTML = rows.map((c) => `
          <button type="button" class="cc-list-item${c.id === ccSelectedId ? ' active' : ''}" data-cc-id="${c.id}">
            <strong>${esc(c.jmeno || c.email)}</strong>
            <span class="meta">${esc(c.email)}</span>
            <span class="badge">${esc(c.stav_label || c.stav)}</span>
          </button>
        `).join('');
      }
      if (ccSelectedId) {
        await openCustomerCard(ccSelectedId);
      } else if (detail && !detail.querySelector('#cc-form-new')) {
        detail.innerHTML = '<p class="empty">Vyberte kartu nebo vytvořte novou.</p>';
      }
    } catch (e) {
      list.innerHTML = `<p class="empty">${esc(e.message || 'Chyba načtení')}</p>`;
    }
  }

  function renderNewCardForm() {
    ccSelectedId = null;
    $$('.cc-list-item').forEach((el) => el.classList.remove('active'));
    const detail = $('#cc-detail');
    if (!detail) return;
    detail.innerHTML = `
      <h2 class="section-title">Nová zákaznická karta</h2>
      <form id="cc-form-new" class="cc-form">
        <label>E-mail *<input class="input" name="email" type="email" required></label>
        <label>Jméno<input class="input" name="jmeno" type="text"></label>
        <label>Telefon<input class="input" name="telefon" type="text"></label>
        <label>Poznámka o zákazníkovi<textarea class="input" name="poznamka" rows="2"></textarea></label>
        <hr class="cc-hr">
        <h3>První zápis návštěvy</h3>
        <label>Datum *<input class="input" name="visit_datum" type="date" value="${todayYmd()}" required></label>
        <label>Text zápisu *<textarea class="input" name="visit_text" rows="5" required placeholder="Co proběhlo, na co navázat…"></textarea></label>
        <label class="cc-check"><input type="checkbox" name="odeslat_potvrzeni" checked> Odeslat žádost o potvrzení zákaznické karty</label>
        <div class="actions">
          <button type="submit" class="btn primary">Uložit návrh karty</button>
        </div>
        <p id="cc-form-msg" class="msg" hidden></p>
      </form>
    `;
  }

  async function openCustomerCard(id) {
    ccSelectedId = id;
    $$('.cc-list-item').forEach((el) => {
      el.classList.toggle('active', Number(el.dataset.ccId) === Number(id));
    });
    const detail = $('#cc-detail');
    if (!detail) return;
    detail.innerHTML = '<p class="empty">Načítám kartu…</p>';
    try {
      const c = await api(`/flow/zakaznicke-karty/${id}/`);
      const canAddVisit = c.stav === 'aktivni';
      const visits = (c.visits || []).map((v) => `
        <article class="item">
          <div class="item-top">
            <time>${esc(v.datum)}</time>
            <span class="meta">${esc(v.autor_jmeno || '')}</span>
          </div>
          <p class="cc-visit-text">${esc(v.text)}</p>
        </article>
      `).join('') || '<p class="empty">Bez zápisů.</p>';

      detail.innerHTML = `
        <div class="row between wrap gap">
          <h2 class="section-title">${esc(c.jmeno || c.email)}</h2>
          <span class="badge">${esc(c.stav_label || c.stav)}</span>
        </div>
        <p class="meta">${esc(c.email)}${c.telefon ? ' · ' + esc(c.telefon) : ''}</p>
        ${c.poznamka ? `<p class="cc-note">${esc(c.poznamka)}</p>` : ''}
        ${c.confirmed_at ? `<p class="meta">Potvrzeno: ${esc(String(c.confirmed_at).replace('T', ' ').slice(0, 19))}${c.confirmed_ip ? ' · IP ' + esc(c.confirmed_ip) : ''}</p>` : ''}
        <div class="actions" style="margin: .75rem 0">
          ${c.stav === 'ceka_na_potvrzeni' ? `<button type="button" class="btn primary" data-cc-send="${c.id}">Odeslat žádost o potvrzení zákaznické karty</button>` : ''}
          <button type="button" class="btn ghost" data-cc-edit="${c.id}">Upravit údaje</button>
          <button type="button" class="btn danger" data-cc-delete="${c.id}">Vyřadit zákazníka</button>
        </div>
        <div id="cc-edit-box" class="hidden"></div>
        <h3>Historie</h3>
        <div class="list">${visits}</div>
        ${canAddVisit ? `
          <form id="cc-visit-form" class="cc-form" data-card="${c.id}">
            <h3>Nový zápis</h3>
            <label>Datum *<input class="input" name="datum" type="date" value="${todayYmd()}" required></label>
            <label>Text *<textarea class="input" name="text" rows="4" required></textarea></label>
            <button type="submit" class="btn primary">Přidat zápis</button>
            <p id="cc-visit-msg" class="msg" hidden></p>
          </form>
        ` : `<p class="hint">Další zápisy až po potvrzení karty zákazníkem.</p>`}
      `;
    } catch (e) {
      detail.innerHTML = `<p class="empty">${esc(e.message || 'Chyba')}</p>`;
    }
  }

  function showEditForm(card) {
    const box = $('#cc-edit-box');
    if (!box) return;
    box.classList.remove('hidden');
    box.innerHTML = `
      <form id="cc-edit-form" class="cc-form">
        <label>Jméno<input class="input" name="jmeno" value="${esc(card.jmeno || '')}"></label>
        <label>Telefon<input class="input" name="telefon" value="${esc(card.telefon || '')}"></label>
        <label>Poznámka<textarea class="input" name="poznamka" rows="3">${esc(card.poznamka || '')}</textarea></label>
        <button type="submit" class="btn primary">Uložit</button>
      </form>
    `;
    box.querySelector('#cc-edit-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      await api(`/flow/zakaznicke-karty/${card.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({
          jmeno: fd.get('jmeno'),
          telefon: fd.get('telefon'),
          poznamka: fd.get('poznamka'),
        }),
      });
      await openCustomerCard(card.id);
      await loadCustomerCards();
    });
  }

  // —— hooks into app.js globals ——
  if (typeof setTab === 'function') {
    const _setTab = setTab;
    // eslint-disable-next-line no-global-assign
    setTab = function (name) {
      _setTab(name);
      if (name === 'karty') loadCustomerCards();
    };
  }

  if (typeof renderRezervaceList === 'function') {
    const _render = renderRezervaceList;
    // eslint-disable-next-line no-global-assign
    renderRezervaceList = function (container, items, options) {
      _render(container, items, options);
      const byId = new Map((items || []).map((r) => [String(r.id), r]));
      container.querySelectorAll('article.item[data-id]').forEach((art) => {
        const r = byId.get(String(art.dataset.id));
        if (!r || !r.customer_card_id) return;
        if (art.querySelector('[data-cc-open]')) return;
        const wrap = document.createElement('div');
        wrap.className = 'actions';
        wrap.innerHTML = `<button type="button" class="btn tiny ghost" data-cc-open="${r.customer_card_id}">Otevřít kartu zákazníka</button>`;
        art.appendChild(wrap);
      });
    };
  }

  document.addEventListener('click', async (ev) => {
    const openBtn = ev.target.closest('[data-cc-open]');
    if (openBtn) {
      const id = Number(openBtn.dataset.ccOpen);
      setTab('karty');
      ccSelectedId = id;
      await loadCustomerCards();
      await openCustomerCard(id);
      return;
    }
    const listBtn = ev.target.closest('[data-cc-id]');
    if (listBtn && listBtn.closest('#cc-list')) {
      await openCustomerCard(Number(listBtn.dataset.ccId));
      return;
    }
    if (ev.target.id === 'cc-btn-new') {
      renderNewCardForm();
      return;
    }
    const sendBtn = ev.target.closest('[data-cc-send]');
    if (sendBtn) {
      const id = Number(sendBtn.dataset.ccSend);
      sendBtn.disabled = true;
      try {
        const res = await api(`/flow/zakaznicke-karty/${id}/odeslat-potvrzeni/`, { method: 'POST', body: '{}' });
        alert(res.detail || 'Odesláno.');
        await openCustomerCard(id);
      } catch (e) {
        alert(e.message || 'Chyba odeslání');
      } finally {
        sendBtn.disabled = false;
      }
      return;
    }
    const delBtn = ev.target.closest('[data-cc-delete]');
    if (delBtn) {
      const id = Number(delBtn.dataset.ccDelete);
      if (!confirm('Vyřadit zákazníka? Karta i historie se trvale smažou. Operace je nevratná.')) return;
      await api(`/flow/zakaznicke-karty/${id}/`, { method: 'DELETE' });
      ccSelectedId = null;
      await loadCustomerCards();
      $('#cc-detail').innerHTML = '<p class="empty">Zákazník byl vyřazen.</p>';
      return;
    }
    const editBtn = ev.target.closest('[data-cc-edit]');
    if (editBtn) {
      const id = Number(editBtn.dataset.ccEdit);
      const c = await api(`/flow/zakaznicke-karty/${id}/`);
      showEditForm(c);
    }
  });

  document.addEventListener('submit', async (ev) => {
    if (ev.target.id === 'cc-form-new') {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      const msg = $('#cc-form-msg');
      try {
        const created = await api('/flow/zakaznicke-karty/', {
          method: 'POST',
          body: JSON.stringify({
            email: fd.get('email'),
            jmeno: fd.get('jmeno') || '',
            telefon: fd.get('telefon') || '',
            poznamka: fd.get('poznamka') || '',
            visit_datum: fd.get('visit_datum'),
            visit_text: fd.get('visit_text'),
            odeslat_potvrzeni: fd.get('odeslat_potvrzeni') === 'on',
          }),
        });
        ccSelectedId = created.id;
        await loadCustomerCards();
        await openCustomerCard(created.id);
        if (msg) {
          msg.hidden = false;
          msg.textContent = created.email_odeslan
            ? 'Karta uložena, potvrzovací e-mail odeslán.'
            : 'Karta uložena. E-mail se nepodařilo odeslat (zkontrolujte SMTP).';
        }
      } catch (e) {
        if (msg) {
          msg.hidden = false;
          msg.textContent = e.message || 'Chyba uložení';
        }
      }
      return;
    }
    if (ev.target.id === 'cc-visit-form') {
      ev.preventDefault();
      const cardId = Number(ev.target.dataset.card);
      const fd = new FormData(ev.target);
      try {
        await api(`/flow/zakaznicke-karty/${cardId}/navstevy/`, {
          method: 'POST',
          body: JSON.stringify({
            datum: fd.get('datum'),
            text: fd.get('text'),
          }),
        });
        await openCustomerCard(cardId);
      } catch (e) {
        const m = $('#cc-visit-msg');
        if (m) {
          m.hidden = false;
          m.textContent = e.message || 'Chyba';
        }
      }
    }
  });

  document.addEventListener('input', (ev) => {
    if (ev.target.id === 'cc-search' || ev.target.id === 'cc-filter-stav') {
      clearTimeout(ccSearchTimer);
      ccSearchTimer = setTimeout(loadCustomerCards, 250);
    }
  });
  document.addEventListener('change', (ev) => {
    if (ev.target.id === 'cc-filter-stav') loadCustomerCards();
  });
})();
