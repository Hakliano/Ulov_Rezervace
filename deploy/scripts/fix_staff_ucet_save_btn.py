"""Add explicit save button for staff QR bank account in rezervace admin."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OLD_HTML = """                <label class="full">Číslo účtu pro QR platby
                  <input type="text" id="staff-cislo-uctu" placeholder="123456789/0100">
                </label>
                <p class="hint">Předvyplní se při odeslání žádosti o platbu u rezervací tohoto pracovníka.</p>
                </div>"""

NEW_HTML = """                <label class="full">Číslo účtu pro QR platby
                  <input type="text" id="staff-cislo-uctu" placeholder="123456789/0100 nebo CZ… IBAN">
                </label>
                <p class="hint">Ukládá se k pracovníkovi do databáze a předvyplní se při žádosti o QR platbu. Samotné napsání nestačí — uložte tlačítkem.</p>
                <button type="button" id="btn-staff-save-ucet" class="btn btn-primary btn-sm">Uložit číslo účtu</button>
                <p id="staff-ucet-msg" class="status-msg"></p>
                </div>"""

OLD_SAVE = """async function saveStaffRozvrh() {
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
    msg.textContent = 'Údaje pracovníka uloženy.';
    msg.className = 'status-msg success';
    await loadStaff();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}"""

NEW_SAVE = """async function saveStaffRozvrh() {
  const staff = getSelectedStaff();
  if (!staff || staff.role === 'majitel') return;
  const msgs = [$('#staff-rozvrh-msg'), $('#staff-ucet-msg')].filter(Boolean);
  msgs.forEach((msg) => {
    msg.textContent = 'Ukládám…';
    msg.className = 'status-msg';
  });
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
    msgs.forEach((msg) => {
      msg.textContent = 'Údaje pracovníka uloženy.';
      msg.className = 'status-msg success';
    });
    await loadStaff();
  } catch (err) {
    msgs.forEach((msg) => {
      msg.textContent = err.message;
      msg.className = 'status-msg error';
    });
  }
}"""

OLD_LISTENER = "$('#btn-staff-save-rozvrh').addEventListener('click', saveStaffRozvrh);"
NEW_LISTENER = """$('#btn-staff-save-rozvrh')?.addEventListener('click', saveStaffRozvrh);
$('#btn-staff-save-ucet')?.addEventListener('click', saveStaffRozvrh);"""


def main():
    html_ok = js_ok = 0
    for html in sorted(ROOT.glob("*/rezervace.html")):
        text = html.read_text(encoding="utf-8")
        if OLD_HTML not in text:
            print(f"HTML skip {html.parent.name}")
            continue
        html.write_text(text.replace(OLD_HTML, NEW_HTML), encoding="utf-8")
        html_ok += 1
        print(f"HTML {html.parent.name}")

    for js in sorted(ROOT.glob("*/rezervace.js")):
        text = js.read_text(encoding="utf-8")
        changed = False
        if OLD_SAVE in text:
            text = text.replace(OLD_SAVE, NEW_SAVE)
            changed = True
        elif "staff-ucet-msg" in text:
            print(f"JS already patched {js.parent.name}")
        else:
            print(f"JS save fn skip {js.parent.name}")
        if OLD_LISTENER in text:
            text = text.replace(OLD_LISTENER, NEW_LISTENER)
            changed = True
        elif NEW_LISTENER in text:
            pass
        else:
            print(f"JS listener skip {js.parent.name}")
        if changed:
            js.write_text(text, encoding="utf-8")
            js_ok += 1
            print(f"JS {js.parent.name}")
    print(f"done html={html_ok} js={js_ok}")


if __name__ == "__main__":
    main()
