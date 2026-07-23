"""Propagate FLOW phase 6: website banner admin + public strip."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

BANNER_TAB = (
    '          <button type="button" class="tab" data-tab="vizual">Vizuál</button>\n'
    '          <button type="button" class="tab" data-tab="banner">Banner</button>'
)
BANNER_TAB_SALON4 = (
    '            <button type="button" class="tab" data-tab="vizual">Vizuál</button>\n'
    '            <button type="button" class="tab" data-tab="banner">Banner</button>'
)

BANNER_PANEL = """
        <div class="tab-panel" data-panel="banner">
          <p class="admin-hint">Krátký pruh nad úvodem webu (akce, dovolená, upozornění). Prázdné datum = bez omezení.</p>
          <label class="checkbox">
            <input type="checkbox" id="edit-banner-enabled"> Banner zapnutý
          </label>
          <label for="edit-banner-text">Text</label>
          <input type="text" id="edit-banner-text" maxlength="300" placeholder="Např. Letní dovolená 1.–15. 8. — objednávky od 16. 8.">
          <label for="edit-banner-od">Zobrazit od</label>
          <input type="date" id="edit-banner-od">
          <label for="edit-banner-do">Zobrazit do</label>
          <input type="date" id="edit-banner-do">
        </div>
"""

BANNER_PANEL_SALON4 = BANNER_PANEL.replace('        <div class="tab-panel"', '          <div class="tab-panel"').replace(
    '\n          ', '\n            '
).replace('\n        </div>\n', '\n          </div>\n')

CSS_BANNER = """
.site-banner {
  margin: 0 0 1.25rem;
  padding: 0.85rem 1.1rem;
  background: color-mix(in srgb, var(--gold, #c9a962) 18%, var(--surface, #111));
  border: 1px solid var(--line, rgba(201,169,98,0.25));
  border-left: 3px solid var(--gold, #c9a962);
  color: var(--text, #f2ece4);
  font-size: 0.95rem;
  line-height: 1.45;
}
"""

JS_BANNER_FN = r'''
function applySalonBanner(data) {
  const el = document.getElementById('site-banner');
  if (!el) return;
  const text = (data.banner_text || '').trim();
  const enabled = !!data.banner_enabled;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const od = data.banner_od ? new Date(`${data.banner_od}T00:00:00`) : null;
  const doDate = data.banner_do ? new Date(`${data.banner_do}T00:00:00`) : null;
  const inRange = (!od || today >= od) && (!doDate || today <= doDate);
  if (enabled && text && inRange) {
    el.textContent = text;
    el.classList.remove('hidden');
  } else {
    el.textContent = '';
    el.classList.add('hidden');
  }
}

'''


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'data-tab="banner"' in text and 'id="site-banner"' in text:
        return False
    orig = text

    # public strip — try common content openers
    if 'id="site-banner"' not in text:
        for marker in (
            '<div id="content" class="page hidden">\n',
            '<div id="content" class="hidden">\n',
            '<main id="content" class="hidden">\n',
            '<div id="content">\n',
        ):
            if marker in text:
                text = text.replace(
                    marker,
                    marker + '    <div id="site-banner" class="site-banner hidden" role="status"></div>\n',
                    1,
                )
                break
        else:
            # before hero
            m = re.search(r'(\s*)(<(?:section|header)[^>]*class="[^"]*hero)', text)
            if m:
                indent = m.group(1)
                text = text.replace(
                    m.group(0),
                    f'{indent}<div id="site-banner" class="site-banner hidden" role="status"></div>\n{m.group(0)}',
                    1,
                )

    if path.parent.name == 'salon4':
        if 'data-tab="banner"' not in text:
            text = text.replace(
                '            <button type="button" class="tab" data-tab="vizual">Vizuál</button>\n'
                '            <button type="button" class="tab" data-tab="personel">Personál</button>',
                BANNER_TAB_SALON4 + '\n            <button type="button" class="tab" data-tab="personel">Personál</button>',
                1,
            )
        if 'data-panel="banner"' not in text:
            marker = '          <div class="tab-panel" data-panel="personel">'
            if marker in text:
                text = text.replace(marker, BANNER_PANEL_SALON4 + marker, 1)
    else:
        if 'data-tab="banner"' not in text:
            text = text.replace(
                '          <button type="button" class="tab" data-tab="vizual">Vizuál</button>\n'
                '          <button type="button" class="tab" data-tab="personel">Personál</button>',
                BANNER_TAB + '\n          <button type="button" class="tab" data-tab="personel">Personál</button>',
                1,
            )
        if 'data-panel="banner"' not in text:
            marker = '        <div class="tab-panel" data-panel="personel">'
            if marker in text:
                text = text.replace(marker, BANNER_PANEL + marker, 1)

    if text == orig:
        print(f'  HTML miss: {path.parent.name}')
        return False
    path.write_text(text, encoding='utf-8')
    return True


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'function applySalonBanner(' in text and 'banner_enabled:' in text:
        return False
    orig = text

    if 'function applySalonBanner(' not in text:
        if 'function applySalonBrand(' in text:
            text = text.replace('function applySalonBrand(', JS_BANNER_FN + 'function applySalonBrand(', 1)
        elif 'function renderSalon(data)' in text:
            text = text.replace('function renderSalon(data)', JS_BANNER_FN + 'function renderSalon(data)', 1)

    if 'applySalonBanner(data)' not in text:
        # after applySalonBrand or at start of renderSalon after title
        if 'applySalonBrand(data);' in text:
            text = text.replace('applySalonBrand(data);', 'applySalonBrand(data);\n  applySalonBanner(data);', 1)
        else:
            text = text.replace(
                'function renderSalon(data) {\n  document.title = data.name;',
                'function renderSalon(data) {\n  document.title = data.name;\n  applySalonBanner(data);',
                1,
            )

    if "edit-banner-enabled" not in text:
        needle = "  renderBrandPreview('favicon-preview', d.favicon_url, 'Žádný favicon');\n"
        insert = (
            needle
            + "\n"
            + "  const bannerEnabled = document.getElementById('edit-banner-enabled');\n"
            + "  const bannerText = document.getElementById('edit-banner-text');\n"
            + "  const bannerOd = document.getElementById('edit-banner-od');\n"
            + "  const bannerDo = document.getElementById('edit-banner-do');\n"
            + "  if (bannerEnabled) bannerEnabled.checked = !!d.banner_enabled;\n"
            + "  if (bannerText) bannerText.value = d.banner_text || '';\n"
            + "  if (bannerOd) bannerOd.value = d.banner_od || '';\n"
            + "  if (bannerDo) bannerDo.value = d.banner_do || '';\n"
        )
        if needle in text:
            text = text.replace(needle, insert, 1)
        else:
            # after edit-email
            email_line = "  document.getElementById('edit-email').value = d.email;\n"
            if email_line in text:
                text = text.replace(
                    email_line,
                    email_line
                    + "\n"
                    + "  const bannerEnabled = document.getElementById('edit-banner-enabled');\n"
                    + "  const bannerText = document.getElementById('edit-banner-text');\n"
                    + "  const bannerOd = document.getElementById('edit-banner-od');\n"
                    + "  const bannerDo = document.getElementById('edit-banner-do');\n"
                    + "  if (bannerEnabled) bannerEnabled.checked = !!d.banner_enabled;\n"
                    + "  if (bannerText) bannerText.value = d.banner_text || '';\n"
                    + "  if (bannerOd) bannerOd.value = d.banner_od || '';\n"
                    + "  if (bannerDo) bannerDo.value = d.banner_do || '';\n",
                    1,
                )

    if 'banner_enabled:' not in text:
        old = (
            "    accent_color: document.getElementById('edit-accent-color')?.value || '',\n"
            "    cenik, novinky, obrazky,\n"
            "  };"
        )
        new = (
            "    accent_color: document.getElementById('edit-accent-color')?.value || '',\n"
            "    banner_enabled: !!document.getElementById('edit-banner-enabled')?.checked,\n"
            "    banner_text: document.getElementById('edit-banner-text')?.value.trim() || '',\n"
            "    banner_od: document.getElementById('edit-banner-od')?.value || null,\n"
            "    banner_do: document.getElementById('edit-banner-do')?.value || null,\n"
            "    cenik, novinky, obrazky,\n"
            "  };"
        )
        if old in text:
            text = text.replace(old, new, 1)
        else:
            old2 = (
                "    email: document.getElementById('edit-email').value,\n"
                "    cenik, novinky, obrazky,\n"
                "  };"
            )
            new2 = (
                "    email: document.getElementById('edit-email').value,\n"
                "    banner_enabled: !!document.getElementById('edit-banner-enabled')?.checked,\n"
                "    banner_text: document.getElementById('edit-banner-text')?.value.trim() || '',\n"
                "    banner_od: document.getElementById('edit-banner-od')?.value || null,\n"
                "    banner_do: document.getElementById('edit-banner-do')?.value || null,\n"
                "    cenik, novinky, obrazky,\n"
                "  };"
            )
            if old2 in text:
                text = text.replace(old2, new2, 1)
            else:
                print(f'  JS collect miss: {path.parent.name}')

    if text == orig:
        print(f'  JS no change: {path.parent.name}')
        return False
    path.write_text(text, encoding='utf-8')
    return True


def patch_css(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    if '.site-banner' in text:
        return False
    path.write_text(text.rstrip() + '\n' + CSS_BANNER + '\n', encoding='utf-8')
    return True


def main():
    skip = {'salon1', 'flow', 'backend', 'deploy', 'presentace', 'node_modules'}
    demos = sorted(
        p for p in ROOT.iterdir()
        if p.is_dir()
        and p.name not in skip
        and (p / 'index.html').exists()
        and (p / 'app.js').exists()
        and (p / 'rezervace.html').exists()
    )
    for demo in demos:
        h = patch_html(demo / 'index.html')
        j = patch_js(demo / 'app.js')
        c = patch_css(demo / 'style.css')
        print(f"{demo.name}: html={'ok' if h else 'skip'} js={'ok' if j else 'skip'} css={'ok' if c else 'skip'}")


if __name__ == '__main__':
    main()
