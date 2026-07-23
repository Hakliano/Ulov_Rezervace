"""Propagate FLOW phase 4: staff daily ops only in FLOW; rezervace.html = majitelka."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

LOGIN_OLD = """        <h2>Přihlášení personálu</h2>
        <form id="form-admin-login">
          <label>Přihlašovací jméno<input type="text" id="staff-login" required autocomplete="username" placeholder="eva"></label>
          <label>Heslo<input type="password" id="staff-password" required autocomplete="current-password"></label>
          <p class="hint">Každý zaměstnanec má vlastní účet. Majitelka vidí celý salon včetně nastavení a NO-show archivu.</p>"""

LOGIN_NEW = """        <h2>Přihlášení majitelky</h2>
        <p class="hint">Denní provoz personálu je ve <a id="admin-login-flow-link" href="/flow/" target="_blank" rel="noopener">FLOW</a>. Zde se přihlašuje majitelka (pracovníci, nastavení, FLOW účty).</p>
        <form id="form-admin-login">
          <label>Přihlašovací jméno<input type="text" id="staff-login" required autocomplete="username"></label>
          <label>Heslo<input type="password" id="staff-password" required autocomplete="current-password"></label>"""

# salon4 may differ slightly — fallback without hint paragraph
LOGIN_OLD_ALT = """        <h2>Přihlášení personálu</h2>
        <form id="form-admin-login">"""

LOGIN_NEW_ALT = """        <h2>Přihlášení majitelky</h2>
        <p class="hint">Denní provoz personálu je ve <a id="admin-login-flow-link" href="/flow/" target="_blank" rel="noopener">FLOW</a>. Zde se přihlašuje majitelka (pracovníci, nastavení, FLOW účty).</p>
        <form id="form-admin-login">"""

REDIRECT_BLOCK = """        <div id="admin-flow-redirect" class="admin-section hidden">
          <div class="settings-card">
            <div class="settings-card-head"><h3>Denní provoz je ve FLOW</h3></div>
            <div class="settings-card-body">
              <p>Kalendář, rezervace, dovolená a Overview máte v aplikaci FLOW. Tato stránka je jen pro majitelku (nastavení salonu).</p>
              <p class="btn-row" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:1rem">
                <a id="btn-open-flow" class="btn btn-primary" href="/flow/" target="_blank" rel="noopener">Otevřít FLOW</a>
              </p>
            </div>
          </div>
        </div>
"""

OLD_APPLY = re.compile(
    r"function applyStaffUI\(\) \{.*?\n\}\n\nfunction updateActorBadge\(\)",
    re.DOTALL,
)

NEW_APPLY = """function flowAppUrl() {
  const h = location.hostname;
  if (h.includes('staging')) return 'https://www.staging.ulovklienty.cz/flow/';
  if (['localhost', '127.0.0.1', '::1'].includes(h)) {
    return `${location.protocol}//${h}${location.port ? `:${location.port}` : ''}/flow/`;
  }
  return 'https://www.ulovklienty.cz/flow/';
}

function applyStaffUI() {
  const badge = $('#admin-actor-badge');
  if (badge && staffUser) {
    badge.textContent = staffUser.je_majitel
      ? `${staffUser.jmeno} · majitelka`
      : staffUser.jmeno;
  }
  const flowUrl = flowAppUrl();
  ['admin-login-flow-link', 'btn-open-flow'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.href = flowUrl;
  });

  // Fáze 4: personál denní práci jen ve FLOW; rezervace.html = majitelka.
  const majitel = isMajitel();
  const majitelOnly = ['kalendar', 'kadernice', 'statistiky', 'noshow', 'nastaveni', 'audit'];
  $$('[data-admin]').forEach((btn) => {
    btn.classList.toggle('hidden', !majitel && majitelOnly.includes(btn.dataset.admin));
  });
  if ($('#btn-staff-add')) $('#btn-staff-add').classList.toggle('hidden', !majitel);

  const redirect = $('#admin-flow-redirect');
  const sections = $$('.admin-section');
  if (redirect) {
    redirect.classList.toggle('hidden', majitel);
  }
  sections.forEach((sec) => {
    if (sec.id === 'admin-flow-redirect') return;
    if (!majitel) sec.classList.add('hidden');
  });
}

function showMajitelDefaultView() {
  $$('.admin-section').forEach((sec) => {
    sec.classList.toggle('hidden', sec.id !== 'admin-kalendar');
  });
}

function updateActorBadge()"""

OLD_LOGIN_TAIL = """    applyStaffUI();
    adminCalMonth = new Date();
    adminCalMonth.setDate(1);
    loadAdminKalendar();
    if (isMajitel()) loadNastaveni();
    msg.textContent = '';"""

NEW_LOGIN_TAIL = """    applyStaffUI();
    if (isMajitel()) {
      showMajitelDefaultView();
      adminCalMonth = new Date();
      adminCalMonth.setDate(1);
      loadAdminKalendar();
      loadNastaveni();
    }
    msg.textContent = '';"""

OLD_RESTORE_TAIL = """    applyStaffUI();
    adminCalMonth = new Date();
    adminCalMonth.setDate(1);
    loadAdminKalendar();
    if (isMajitel()) loadNastaveni();
  } catch {"""

NEW_RESTORE_TAIL = """    applyStaffUI();
    if (isMajitel()) {
      showMajitelDefaultView();
      adminCalMonth = new Date();
      adminCalMonth.setDate(1);
      loadAdminKalendar();
      loadNastaveni();
    }
  } catch {"""

OLD_DATA_ADMIN = """$$('[data-admin]').forEach(btn => {
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
});"""

NEW_DATA_ADMIN = """$$('[data-admin]').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!isMajitel()) return;
    $$('.admin-section').forEach((s) => {
      if (s.id === 'admin-flow-redirect') return;
      s.classList.add('hidden');
    });
    const sec = $(`#admin-${btn.dataset.admin}`);
    if (sec) sec.classList.remove('hidden');
    if (btn.dataset.admin === 'kalendar') loadAdminKalendar();
    if (btn.dataset.admin === 'kadernice') loadStaff();
    if (btn.dataset.admin === 'statistiky') loadStats();
    if (btn.dataset.admin === 'noshow') loadNoShowArchiv();
    if (btn.dataset.admin === 'nastaveni') loadNastaveni();
    if (btn.dataset.admin === 'audit') loadAuditLog();
  });
});"""


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    if "admin-flow-redirect" in text:
        return False
    if LOGIN_OLD in text:
        text = text.replace(LOGIN_OLD, LOGIN_NEW, 1)
    elif LOGIN_OLD_ALT in text:
        text = text.replace(LOGIN_OLD_ALT, LOGIN_NEW_ALT, 1)
        # drop old hint if still present right after password
        text = text.replace(
            '          <p class="hint">Každý zaměstnanec má vlastní účet. Majitelka vidí celý salon včetně nastavení a NO-show archivu.</p>\n',
            "",
            1,
        )
    else:
        print(f"  HTML login pattern miss: {path.parent.name}")
        return False

    marker = '          <button type="button" id="btn-staff-logout" class="btn btn-secondary btn-sm">Odhlásit</button>\n        </div>\n        <div id="admin-kalendar"'
    insert = (
        '          <button type="button" id="btn-staff-logout" class="btn btn-secondary btn-sm">Odhlásit</button>\n'
        "        </div>\n"
        + REDIRECT_BLOCK
        + '        <div id="admin-kalendar"'
    )
    if marker not in text:
        print(f"  HTML redirect insert miss: {path.parent.name}")
        return False
    text = text.replace(marker, insert, 1)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    if "function flowAppUrl()" in text and "admin-flow-redirect" in text:
        return False

    m = OLD_APPLY.search(text)
    if not m:
        print(f"  JS applyStaffUI miss: {path.parent.name}")
        return False
    text = OLD_APPLY.sub(NEW_APPLY, text, count=1)

    if OLD_LOGIN_TAIL not in text:
        print(f"  JS login tail miss: {path.parent.name}")
        return False
    # replace both login and restore (same block appears twice)
    text = text.replace(OLD_LOGIN_TAIL, NEW_LOGIN_TAIL)
    # restore may still have old if login was already new from partial — handle restore separately
    if OLD_RESTORE_TAIL in text:
        text = text.replace(OLD_RESTORE_TAIL, NEW_RESTORE_TAIL)

    if OLD_DATA_ADMIN in text:
        text = text.replace(OLD_DATA_ADMIN, NEW_DATA_ADMIN, 1)
    else:
        print(f"  JS data-admin miss: {path.parent.name}")

    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    demos = sorted(
        p for p in ROOT.iterdir()
        if p.is_dir() and (p / "rezervace.html").exists() and p.name != "salon1"
    )
    for demo in demos:
        html = demo / "rezervace.html"
        js = demo / "rezervace.js"
        h = patch_html(html)
        j = patch_js(js)
        print(f"{demo.name}: html={'ok' if h else 'skip'} js={'ok' if j else 'skip'}")


if __name__ == "__main__":
    main()
