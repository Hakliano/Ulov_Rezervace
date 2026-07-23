#!/usr/bin/env python3
"""Propagate soft-deposit UI: emails tab, cenik rizikovy, notif MAX=7."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --- rezervace.html: button + move notif to emails section ---
OLD_BTN = (
    '          <button type="button" class="btn btn-secondary btn-sm" data-admin="nastaveni">Nastavení</button>\n'
    '          <button type="button" class="btn btn-secondary btn-sm" data-admin="audit">Audit log</button>'
)
NEW_BTN = (
    '          <button type="button" class="btn btn-secondary btn-sm" data-admin="nastaveni">Nastavení</button>\n'
    '          <button type="button" class="btn btn-secondary btn-sm" data-admin="emaily">E-maily</button>\n'
    '          <button type="button" class="btn btn-secondary btn-sm" data-admin="audit">Audit log</button>'
)

OLD_NOTIF_OPEN = '''            <section class="settings-card notif-section">
              <div class="settings-card-head">
                <h3>E-mailové notifikace</h3>
                <p class="settings-card-desc">Můžete nastavit až <strong>4 různé e-maily</strong> — připomínku, poděkování/recenzi, NO-show a žádost o platbu s QR kódem.</p>
              </div>
              <div class="settings-card-body">
                <div class="settings-subcard notif-timing-hint">
                  <p><strong>Kdy se e-mail odešle?</strong></p>
                  <ul>
                    <li><strong>+24</strong> = 24 hodin <em>před</em> začátkem rezervace (připomínka)</li>
                    <li><strong>+2</strong> = 2 hodiny <em>před</em> termínem (krátká připomínka)</li>
                    <li><strong>-2</strong> = 2 hodiny <em>po skončení</em> služby (poděkování, recenze…)</li>
                    <li><strong>Notifikace 3</strong> = jen ručně u rezervace (NO-show) — bez automatického času</li>
                    <li><strong>Notifikace 4</strong> = žádost o platbu s QR kódem — ručně tlačítkem u rezervace</li>
                  </ul>
                </div>
                <div class="settings-subcard notif-tag-section">
                  <h5>Jak psát text e-mailu — dynamické tagy</h5>
                  <p class="hint">Do textu vložte „tag“ (slovo v dvojitých složených závorkách). Při odeslání se automaticky nahradí údaji zákazníka a rezervace. Text kolem tagů si složíte libovolně sami.</p>
                  <p class="hint" id="notif-hint"></p>
                  <div id="notif-tag-guide" class="notif-tag-guide"></div>
                </div>
                <div class="settings-subcard">
                  <label class="full notif-recenze-url">Odkaz na recenze (Google, Facebook…)
                    <input type="url" id="nast-recenze-url" placeholder="https://g.page/vas-salon/review">
                  </label>
                  <p class="hint">Do textu druhé notifikace vložte tag <code>{{ recenze_url }}</code> — zákazník uvidí tento odkaz.</p>
                </div>
                <div id="notifikace-list" class="notifikace-list"></div>
              </div>
            </section>

            <footer class="settings-form-footer">
              <p class="hint">E-mail odesílatele nastavte v administraci webu (⚙ → E-mail).</p>
              <button type="submit" class="btn btn-primary">Uložit nastavení</button>
            </footer>
          </form>
        </div>'''

NEW_AFTER_NAST = '''            <footer class="settings-form-footer">
              <p class="hint">Šablony e-mailů najdete v záložce <strong>E-maily</strong>. Odesílatele nastavte v administraci webu (⚙ → E-mail).</p>
              <button type="submit" class="btn btn-primary">Uložit nastavení</button>
            </footer>
          </form>
        </div>
        <div id="admin-emaily" class="admin-section hidden">
          <form id="form-emaily" class="settings-stack">
            <section class="settings-card notif-section">
              <div class="settings-card-head">
                <h3>E-mailové šablony</h3>
                <p class="settings-card-desc">Připomínka, poděkování, NO-show, QR platba/záloha, storno, <strong>potvrzení rezervace</strong> a <strong>záloha přijata</strong>.</p>
              </div>
              <div class="settings-card-body">
                <div class="settings-subcard notif-timing-hint">
                  <p><strong>Kdy se e-mail odešle?</strong></p>
                  <ul>
                    <li><strong>+24</strong> = 24 hodin <em>před</em> začátkem rezervace (připomínka)</li>
                    <li><strong>-2</strong> = 2 hodiny <em>po skončení</em> služby (poděkování, recenze…)</li>
                    <li><strong>NO-show / QR platba / storno / záloha OK</strong> = ručně z FLOW nebo adminu</li>
                    <li><strong>Potvrzení</strong> = automaticky při potvrzení rezervace (včetně bloku o možné záloze u rizikových služeb)</li>
                  </ul>
                </div>
                <div class="settings-subcard notif-tag-section">
                  <h5>Dynamická pole</h5>
                  <button type="button" id="btn-toggle-tag-help" class="btn btn-secondary btn-sm">Ukázat nápovědu dynamických polí</button>
                  <div id="notif-tag-help-panel" class="hidden" style="margin-top:0.75rem">
                    <p class="hint">Do textu vložte tag ve dvojitých složených závorkách. Při odeslání se nahradí údaji rezervace.</p>
                    <p class="hint" id="notif-hint"></p>
                    <div id="notif-tag-guide" class="notif-tag-guide"></div>
                  </div>
                </div>
                <div class="settings-subcard">
                  <label class="full notif-recenze-url">Odkaz na recenze (Google, Facebook…)
                    <input type="url" id="nast-recenze-url" placeholder="https://g.page/vas-salon/review">
                  </label>
                  <p class="hint">Do textu druhé notifikace vložte tag <code>{{ recenze_url }}</code>.</p>
                </div>
                <div id="notifikace-list" class="notifikace-list"></div>
              </div>
            </section>
            <footer class="settings-form-footer">
              <button type="submit" class="btn btn-primary">Uložit e-maily</button>
              <p id="emaily-msg" class="status-msg"></p>
            </footer>
          </form>
        </div>'''


def patch_html(path: Path) -> bool:
    t = path.read_text(encoding='utf-8')
    orig = t
    if 'data-admin="emaily"' not in t and OLD_BTN in t:
        t = t.replace(OLD_BTN, NEW_BTN)
    if 'id="admin-emaily"' not in t and OLD_NOTIF_OPEN in t:
        t = t.replace(OLD_NOTIF_OPEN, NEW_AFTER_NAST)
    if t != orig:
        path.write_text(t, encoding='utf-8')
        return True
    return False


OLD_MAX = 'const MAX_NOTIFIKACE = 5;'
NEW_MAX = 'const MAX_NOTIFIKACE = 7;'

OLD_POPISY = '''const NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show, bez automatického času',
  'Žádost o úhradu na účet s QR kódem — pouze ručně u rezervace (tlačítko Požádat o platbu)',
  'Storno rezervace — odešle se při zrušení rezervace salonem / ve FLOW (ne automaticky v čase)',
];'''

NEW_POPISY = '''const NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show',
  'Žádost o úhradu / zálohu s QR — FLOW: Platba QR nebo Požádat o zálohu',
  'Storno rezervace — při zrušení salonem / ve FLOW',
  'Potvrzení rezervace — automaticky při potvrzení (včetně textu o možné záloze u rizikových služeb)',
  'Záloha přijata — odešle se tlačítkem Záloha OK ve FLOW',
];'''

OLD_MANUAL_TYP = "  const manualTyp = n.manual_typ || (i === 4 ? 'storno' : i === 3 ? 'platba' : 'noshow');"
NEW_MANUAL_TYP = """  const manualTyp = n.manual_typ || (
    i === 6 ? 'zaloha_ok' : i === 5 ? 'potvrzeni' : i === 4 ? 'storno' : i === 3 ? 'platba' : 'noshow'
  );"""

OLD_HINT_BLOCK = '''    if (manualTyp === 'platba') {
      manualHint.textContent = 'Tento e-mail se neodesílá automaticky. Personál ho odešle tlačítkem „Požádat o platbu na účet“ u rezervace — v e-mailu bude QR kód pro platbu.';
    } else if (manualTyp === 'storno') {
      manualHint.textContent = 'Tento e-mail se odešle zákazníkovi při stornu rezervace (admin / FLOW). Tag {{ kdo }} = salon nebo zákazník.';
    } else {
      manualHint.textContent = 'Tento e-mail se neodesílá automaticky. Text si připravíte zde, odešle se až po stisknutí NO-show u konkrétní rezervace v kalendáři.';
    }'''

NEW_HINT_BLOCK = '''    if (manualTyp === 'platba') {
      manualHint.textContent = 'Ručně: Platba QR nebo Požádat o zálohu ve FLOW — v e-mailu bude QR kód. U zálohy napište do textu i lhůtu (např. 12 h před službou).';
    } else if (manualTyp === 'storno') {
      manualHint.textContent = 'Odešle se při stornu (admin / FLOW). Tag {{ kdo }} = salon nebo zákazník; {{ duvod }} = důvod.';
    } else if (manualTyp === 'potvrzeni') {
      manualHint.textContent = 'Odešle se automaticky při potvrzení rezervace. Blok {% if rizikova %}…{% endif %} se zobrazí jen u rizikových služeb.';
    } else if (manualTyp === 'zaloha_ok') {
      manualHint.textContent = 'Odešle se tlačítkem Záloha OK ve FLOW po kontrole banky.';
    } else {
      manualHint.textContent = 'Ručně: NO-show u rezervace v kalendáři / FLOW.';
    }'''

OLD_ADMIN_CLICK = '''    if (btn.dataset.admin === 'nastaveni') loadNastaveni();
    if (btn.dataset.admin === 'audit') loadAuditLog();'''

NEW_ADMIN_CLICK = '''    if (btn.dataset.admin === 'nastaveni') loadNastaveni();
    if (btn.dataset.admin === 'emaily') loadNastaveni();
    if (btn.dataset.admin === 'audit') loadAuditLog();'''


def patch_rez_js(path: Path) -> bool:
    t = path.read_text(encoding='utf-8')
    orig = t
    t = t.replace(OLD_MAX, NEW_MAX)
    if OLD_POPISY in t:
        t = t.replace(OLD_POPISY, NEW_POPISY)
    if OLD_MANUAL_TYP in t:
        t = t.replace(OLD_MANUAL_TYP, NEW_MANUAL_TYP)
    if OLD_HINT_BLOCK in t:
        t = t.replace(OLD_HINT_BLOCK, NEW_HINT_BLOCK)
    if OLD_ADMIN_CLICK in t:
        t = t.replace(OLD_ADMIN_CLICK, NEW_ADMIN_CLICK)
    if "btn-toggle-tag-help" not in t:
        inject = '''
$('#btn-toggle-tag-help')?.addEventListener('click', () => {
  const panel = $('#notif-tag-help-panel');
  const btn = $('#btn-toggle-tag-help');
  if (!panel || !btn) return;
  const open = panel.classList.toggle('hidden') === false;
  btn.textContent = open ? 'Skrýt nápovědu' : 'Ukázat nápovědu dynamických polí';
});

$('#form-emaily')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#emaily-msg');
  try {
    const current = await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`);
    await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`, {
      method: 'PUT',
      body: JSON.stringify({
        ...current,
        recenze_url: $('#nast-recenze-url')?.value.trim() || '',
        notifikace: collectNotifikace(),
      }),
    });
    if (msg) { msg.textContent = 'E-maily uloženy.'; msg.className = 'status-msg success'; }
    await loadNastaveni();
  } catch (err) {
    if (msg) { msg.textContent = err.message; msg.className = 'status-msg error'; }
  }
});
'''
        # insert before last restoreStaffSession or after form-nastaveni listener area
        marker = "$('#form-nastaveni').addEventListener('submit'"
        if marker in t and 'form-emaily' not in t:
            t = t.replace(marker, inject + '\n' + marker)

    # When saving nastaveni, still send notifikace if list exists (compat)
    if t != orig:
        path.write_text(t, encoding='utf-8')
        return True
    return False


OLD_CENIK_ROW = '''function cenikEditRow(item) {
  const url = item.obrazek || '';
  return `<div class="edit-block cenik-edit-item" data-id="${item.id || ''}" data-obrazek="${attrEsc(url)}">
    <div class="edit-row">
      <input type="text" class="cenik-nazev" value="${esc(item.nazev)}" placeholder="Služba">
      <input type="number" class="cenik-cena" value="${item.cena}" placeholder="Kč">
    </div>'''

NEW_CENIK_ROW = '''function cenikEditRow(item) {
  const url = item.obrazek || '';
  const riz = item.rizikovy ? 'checked' : '';
  return `<div class="edit-block cenik-edit-item" data-id="${item.id || ''}" data-obrazek="${attrEsc(url)}">
    <div class="edit-row">
      <input type="text" class="cenik-nazev" value="${esc(item.nazev)}" placeholder="Služba">
      <input type="number" class="cenik-cena" value="${item.cena}" placeholder="Kč">
    </div>
    <label class="checkbox" style="margin:0.4rem 0;display:flex;gap:0.4rem;align-items:center;font-size:0.85rem">
      <input type="checkbox" class="cenik-rizikovy" ${riz}>
      Rizikový produkt (možná záloha — upozorní FLOW)
    </label>'''


def patch_app_js(path: Path) -> bool:
    t = path.read_text(encoding='utf-8')
    orig = t
    if 'cenik-rizikovy' not in t and OLD_CENIK_ROW in t:
        t = t.replace(OLD_CENIK_ROW, NEW_CENIK_ROW)
    # save payload
    old_save = '      cena: parseInt(el.querySelector(\'.cenik-cena\').value, 10) || 0,'
    new_save = (
        '      cena: parseInt(el.querySelector(\'.cenik-cena\').value, 10) || 0,\n'
        '      rizikovy: !!el.querySelector(\'.cenik-rizikovy\')?.checked,'
    )
    if 'rizikovy:' not in t and old_save in t:
        t = t.replace(old_save, new_save)
    if t != orig:
        path.write_text(t, encoding='utf-8')
        return True
    return False


def main():
    html_n = js_n = app_n = 0
    for p in sorted(ROOT.glob('*/rezervace.html')):
        if patch_html(p):
            html_n += 1
            print('HTML', p.parent.name)
        else:
            print('HTML skip', p.parent.name)
    for p in sorted(ROOT.glob('*/rezervace.js')):
        if patch_rez_js(p):
            js_n += 1
            print('JS', p.parent.name)
        else:
            print('JS skip', p.parent.name)
    for p in sorted(ROOT.glob('*/app.js')):
        if p.parent.name in ('flow', 'partner', 'presentace', 'shared'):
            continue
        if patch_app_js(p):
            app_n += 1
            print('APP', p.parent.name)
        else:
            print('APP skip', p.parent.name)
    print(f'done html={html_n} rezjs={js_n} app={app_n}')


if __name__ == '__main__':
    main()
