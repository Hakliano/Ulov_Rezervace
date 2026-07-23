from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FLOW_HTML = """
              <section class="settings-card staff-flow-block">
                <div class="settings-card-head"><h4>Přístup do FLOW</h4></div>
                <div class="settings-card-body">
                  <p class="hint">FLOW je denní provoz personálu (kalendář, mail…). Nastavení systému zůstává zde v rezervacích.</p>
                  <p id="staff-flow-status" class="hint">Načítám…</p>
                  <div id="staff-flow-create" class="hidden">
                    <label>E-mail pro FLOW (osobní e-mail pracovníka)
                      <input type="email" id="staff-flow-email" placeholder="marie@email.cz" autocomplete="off">
                    </label>
                    <label class="checkbox">
                      <input type="checkbox" id="staff-flow-overview"> Visible Overview (vidí celý provoz, bez úprav za druhé)
                    </label>
                    <button type="button" id="btn-flow-create" class="btn btn-primary btn-sm">Vytvořit přístup do FLOW</button>
                  </div>
                  <div id="staff-flow-manage" class="hidden">
                    <label class="checkbox">
                      <input type="checkbox" id="staff-flow-overview-edit"> Visible Overview
                    </label>
                    <div class="btn-row" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
                      <button type="button" id="btn-flow-save-overview" class="btn btn-secondary btn-sm">Uložit Overview</button>
                      <button type="button" id="btn-flow-reset" class="btn btn-secondary btn-sm">Reset hesla (e-mailem)</button>
                      <button type="button" id="btn-flow-deactivate" class="btn btn-danger btn-sm">Deaktivovat FLOW</button>
                    </div>
                  </div>
                  <p id="staff-flow-msg" class="status-msg"></p>
                </div>
              </section>

"""

FLOW_JS_FUNCS = r"""
async function loadStaffFlow(zamestnanecId) {
  const status = $('#staff-flow-status');
  const createBox = $('#staff-flow-create');
  const manageBox = $('#staff-flow-manage');
  const msg = $('#staff-flow-msg');
  if (!status || !createBox || !manageBox) return;
  status.textContent = 'Načítám FLOW…';
  status.className = 'hint';
  createBox.classList.add('hidden');
  manageBox.classList.add('hidden');
  if (msg) {
    msg.textContent = '';
    msg.className = 'status-msg';
  }
  try {
    const data = await api(`/salon/${SALON_ID}/flow/zamestnanci/${zamestnanecId}/`);
    if (!data.ma_flow) {
      status.textContent = 'Zatím bez přístupu do FLOW.';
      createBox.classList.remove('hidden');
      $('#staff-flow-email').value = '';
      $('#staff-flow-overview').checked = false;
      return;
    }
    const u = data.ucet;
    status.textContent = u.aktivni
      ? `FLOW aktivní: ${u.email}`
      : `FLOW deaktivován: ${u.email}`;
    status.className = u.aktivni ? 'hint success' : 'hint error';
    manageBox.classList.remove('hidden');
    manageBox.dataset.flowId = String(u.id);
    $('#staff-flow-overview-edit').checked = !!u.visible_overview;
    $('#btn-flow-deactivate').textContent = u.aktivni ? 'Deaktivovat FLOW' : 'Znovu aktivovat FLOW';
    $('#btn-flow-deactivate').dataset.aktivni = u.aktivni ? '1' : '0';
  } catch (err) {
    status.textContent = err.message;
    status.className = 'hint error';
  }
}

async function createStaffFlow() {
  const staff = getSelectedStaff();
  if (!staff) return;
  const msg = $('#staff-flow-msg');
  const email = ($('#staff-flow-email').value || '').trim();
  if (!email) {
    msg.textContent = 'Zadejte e-mail.';
    msg.className = 'status-msg error';
    return;
  }
  if (!confirm(`Vytvořit přístup do FLOW pro ${staff.jmeno}?\nE-mail: ${email}\n\nDočasné heslo odejde na tento e-mail.`)) return;
  msg.textContent = 'Vytvářím…';
  msg.className = 'status-msg';
  try {
    const data = await api(`/salon/${SALON_ID}/flow/ucty/`, {
      method: 'POST',
      body: JSON.stringify({
        zamestnanec_id: staff.id,
        email,
        visible_overview: $('#staff-flow-overview').checked,
      }),
    });
    msg.textContent = data.detail || 'Hotovo.';
    msg.className = data.email_odeslan ? 'status-msg success' : 'status-msg error';
    await loadStaffFlow(staff.id);
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function saveStaffFlowOverview() {
  const manageBox = $('#staff-flow-manage');
  const flowId = manageBox?.dataset.flowId;
  const msg = $('#staff-flow-msg');
  if (!flowId) return;
  msg.textContent = 'Ukládám…';
  msg.className = 'status-msg';
  try {
    await api(`/salon/${SALON_ID}/flow/ucty/${flowId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ visible_overview: $('#staff-flow-overview-edit').checked }),
    });
    msg.textContent = 'Overview uložen.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function resetStaffFlowPassword() {
  const staff = getSelectedStaff();
  const manageBox = $('#staff-flow-manage');
  const flowId = manageBox?.dataset.flowId;
  const msg = $('#staff-flow-msg');
  if (!flowId || !staff) return;
  if (!confirm(`Resetovat heslo FLOW pro ${staff.jmeno}?\nNové heslo přijde e-mailem (heslo sami nezadáte).`)) return;
  msg.textContent = 'Resetuji…';
  msg.className = 'status-msg';
  try {
    const data = await api(`/salon/${SALON_ID}/flow/ucty/${flowId}/reset-hesla/`, { method: 'POST' });
    msg.textContent = data.detail || 'Hotovo.';
    msg.className = data.email_odeslan ? 'status-msg success' : 'status-msg error';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

async function toggleStaffFlowActive() {
  const manageBox = $('#staff-flow-manage');
  const flowId = manageBox?.dataset.flowId;
  const msg = $('#staff-flow-msg');
  const staff = getSelectedStaff();
  if (!flowId || !staff) return;
  const currentlyActive = $('#btn-flow-deactivate').dataset.aktivni === '1';
  const next = !currentlyActive;
  if (!confirm(next
    ? `Znovu aktivovat FLOW pro ${staff.jmeno}?`
    : `Deaktivovat FLOW pro ${staff.jmeno}? Přihlášení do FLOW nebude možné.`)) return;
  msg.textContent = 'Ukládám…';
  msg.className = 'status-msg';
  try {
    await api(`/salon/${SALON_ID}/flow/ucty/${flowId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ aktivni: next }),
    });
    msg.textContent = next ? 'FLOW znovu aktivní.' : 'FLOW deaktivován.';
    msg.className = 'status-msg success';
    await loadStaffFlow(staff.id);
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

"""

FLOW_LISTENERS = """$('#btn-staff-deaktivovat')?.addEventListener('click', deactivateStaffAccount);
$('#btn-flow-create')?.addEventListener('click', createStaffFlow);
$('#btn-flow-save-overview')?.addEventListener('click', saveStaffFlowOverview);
$('#btn-flow-reset')?.addEventListener('click', resetStaffFlowPassword);
$('#btn-flow-deactivate')?.addEventListener('click', toggleStaffFlowActive);"""

ANCHOR_HTML = """                <p class="hint">Při odchodu zaměstnance účet deaktivujte — historie rezervací a audit zůstanou, přihlášení nebude možné.</p>
                </div>
              </section>

              <section class="settings-card staff-block">
                <div class="settings-card-head"><h4>Platby</h4></div>"""

REPL_HTML = """                <p class="hint">Při odchodu zaměstnance účet deaktivujte — historie rezervací a audit zůstanou, přihlášení nebude možné.</p>
                </div>
              </section>
""" + FLOW_HTML + """              <section class="settings-card staff-block">
                <div class="settings-card-head"><h4>Platby</h4></div>"""

SELECT_END = "  updateStaffServiceUi(staff);\n}\n\nfunction collectStaffRozvrh()"
SELECT_END_NEW = "  updateStaffServiceUi(staff);\n  loadStaffFlow(staff.id);\n}" + FLOW_JS_FUNCS + "function collectStaffRozvrh()"

OLD_LISTENER = "$('#btn-staff-deaktivovat')?.addEventListener('click', deactivateStaffAccount);"


def main():
    dirs = []
    for p in ROOT.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if name.startswith(('salon', 'zdravi-', 'remesla-', 'provoz-')):
            dirs.append(p)
    dirs.sort(key=lambda x: x.name)

    html_ok, js_ok, skipped = [], [], []

    for d in dirs:
        html = d / 'rezervace.html'
        js = d / 'rezervace.js'
        if not html.exists() or not js.exists():
            skipped.append(f'{d.name}: missing files')
            continue

        h = html.read_text(encoding='utf-8')
        if 'staff-flow-block' in h:
            html_ok.append(f'{d.name}: html already')
        elif ANCHOR_HTML in h:
            html.write_text(h.replace(ANCHOR_HTML, REPL_HTML, 1), encoding='utf-8')
            html_ok.append(f'{d.name}: html patched')
        else:
            skipped.append(f'{d.name}: html anchor not found')

        j = js.read_text(encoding='utf-8')
        changed = False

        if 'function loadStaffFlow' not in j:
            if SELECT_END in j:
                j = j.replace(SELECT_END, SELECT_END_NEW, 1)
                changed = True
            else:
                skipped.append(f'{d.name}: js selectStaff end not found')
                continue

        if "$('#btn-flow-create')" not in j:
            if OLD_LISTENER in j:
                j = j.replace(OLD_LISTENER, FLOW_LISTENERS, 1)
                changed = True
            else:
                skipped.append(f'{d.name}: js listeners anchor not found')

        if changed:
            js.write_text(j, encoding='utf-8')
            js_ok.append(f'{d.name}: js patched')
        elif 'function loadStaffFlow' in j and "$('#btn-flow-create')" in j:
            js_ok.append(f'{d.name}: js already')

    print('HTML:')
    for x in html_ok:
        print(' ', x)
    print('JS:')
    for x in js_ok:
        print(' ', x)
    print('SKIP/ERR:')
    for x in skipped:
        print(' ', x)
    print('dirs', len(dirs))


if __name__ == '__main__':
    main()
