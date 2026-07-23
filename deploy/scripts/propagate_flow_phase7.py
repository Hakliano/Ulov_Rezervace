"""Propagate FLOW phase 7: IMAP settings in website admin email panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

IMAP_BLOCK = """
          <hr class="admin-sep">
          <h4 class="admin-sub">FLOW Mail (IMAP)</h4>
          <p class="admin-hint">Personál ve FLOW uvidí schránku (číst / odpovědět / nový). Stejné přihlášení jako SMTP.</p>
          <label class="checkbox"><input type="checkbox" id="imap-enabled"> Zapnout schránku ve FLOW</label>
          <label for="imap-host">IMAP server</label>
          <input type="text" id="imap-host" placeholder="imap.forpsi.com">
          <label for="imap-port">IMAP port</label>
          <input type="number" id="imap-port" placeholder="993">
          <label class="checkbox"><input type="checkbox" id="imap-ssl" checked> IMAP SSL (port 993)</label>
          <p id="imap-status" class="admin-hint"></p>
"""

OLD_SAVE_TAIL = """  const payload = {
    smtp_host: document.getElementById('smtp-host').value.trim(),
    smtp_port: parseInt(document.getElementById('smtp-port').value, 10) || 465,
    smtp_use_ssl: document.getElementById('smtp-ssl').checked,
    smtp_user: document.getElementById('smtp-user').value.trim(),
    web_rezervace_url: document.getElementById('web-rezervace-url').value.trim(),
  };
  const pwd = document.getElementById('smtp-password').value;
  if (pwd) payload.smtp_password = pwd;"""

NEW_SAVE_TAIL = """  const payload = {
    smtp_host: document.getElementById('smtp-host').value.trim(),
    smtp_port: parseInt(document.getElementById('smtp-port').value, 10) || 465,
    smtp_use_ssl: document.getElementById('smtp-ssl').checked,
    smtp_user: document.getElementById('smtp-user').value.trim(),
    web_rezervace_url: document.getElementById('web-rezervace-url').value.trim(),
    imap_enabled: !!document.getElementById('imap-enabled')?.checked,
    imap_host: document.getElementById('imap-host')?.value.trim() || 'imap.forpsi.com',
    imap_port: parseInt(document.getElementById('imap-port')?.value, 10) || 993,
    imap_use_ssl: document.getElementById('imap-ssl')?.checked !== false,
  };
  const pwd = document.getElementById('smtp-password').value;
  if (pwd) payload.smtp_password = pwd;"""

LOAD_INJECT = """
    const imapEnabled = document.getElementById('imap-enabled');
    const imapHost = document.getElementById('imap-host');
    const imapPort = document.getElementById('imap-port');
    const imapSsl = document.getElementById('imap-ssl');
    const imapStatus = document.getElementById('imap-status');
    if (imapEnabled) imapEnabled.checked = !!data.imap_enabled;
    if (imapHost) imapHost.value = data.imap_host || 'imap.forpsi.com';
    if (imapPort) imapPort.value = data.imap_port || 993;
    if (imapSsl) imapSsl.checked = data.imap_use_ssl !== false;
    if (imapStatus) {
      imapStatus.textContent = data.imap_aktivni
        ? '✓ FLOW Mail aktivní — personál vidí schránku po přihlášení.'
        : 'FLOW Mail vypnutý — zapněte IMAP a uložte (vyžaduje SMTP heslo).';
      imapStatus.className = data.imap_aktivni ? 'admin-hint success' : 'admin-hint';
    }
"""

CSS_EXTRA = """
.admin-sep {
  margin: 1.25rem 0 1rem;
  border: 0;
  border-top: 1px solid var(--line, rgba(255,255,255,0.12));
}
.admin-sub {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gold, #c9a962);
}
"""


def demo_dirs():
    skip = {'backend', 'deploy', 'flow', 'presentace', 'node_modules', '.git', '.cursor'}
    for p in ROOT.iterdir():
        if p.is_dir() and p.name not in skip and (p / 'index.html').exists() and (p / 'app.js').exists():
            yield p


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'id="imap-enabled"' in text:
        return False
    marker = '<p id="email-save-msg" class="status-msg"></p>'
    if marker not in text:
        print('SKIP html (no email-save-msg):', path)
        return False
    path.write_text(text.replace(marker, IMAP_BLOCK + '\n' + marker, 1), encoding='utf-8')
    return True


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    changed = False
    if 'imap_enabled:' not in text and OLD_SAVE_TAIL in text:
        text = text.replace(OLD_SAVE_TAIL, NEW_SAVE_TAIL, 1)
        changed = True
    if 'imap-enabled' not in text and "document.getElementById('smtp-password').placeholder" in text:
        # inject after placeholder assignment block ends (before status.textContent)
        needle = "document.getElementById('smtp-password').placeholder = data.smtp_password_nastaveno\n"
        if needle in text and LOAD_INJECT.strip() not in text:
            # find end of placeholder ternary
            idx = text.find(needle)
            if idx >= 0:
                # find the next status.textContent after this
                rest = text[idx:]
                status_idx = rest.find('status.textContent = data.smtp_aktivni')
                if status_idx > 0:
                    insert_at = idx + status_idx
                    text = text[:insert_at] + LOAD_INJECT + text[insert_at:]
                    changed = True
    if changed:
        path.write_text(text, encoding='utf-8')
    return changed


def patch_css(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if '.admin-sep' in text:
        return False
    path.write_text(text.rstrip() + '\n' + CSS_EXTRA, encoding='utf-8')
    return True


def main():
    for d in demo_dirs():
        h = patch_html(d / 'index.html')
        j = patch_js(d / 'app.js')
        c = patch_css(d / 'style.css')
        print(f"{d.name}: html={h} js={j} css={c}")


if __name__ == '__main__':
    main()
