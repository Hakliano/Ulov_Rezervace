"""Propagate FLOW phase 5 branding UI (Vizuál tab) to all demos except salon1."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

VIZUAL_TAB = (
    '          <button type="button" class="tab" data-tab="obrazky">Obrázky</button>\n'
    '          <button type="button" class="tab" data-tab="vizual">Vizuál</button>'
)
VIZUAL_TAB_SALON4 = (
    '            <button type="button" class="tab" data-tab="obrazky">Obrázky</button>\n'
    '            <button type="button" class="tab" data-tab="vizual">Vizuál</button>'
)

VIZUAL_PANEL = """
        <div class="tab-panel" data-panel="vizual">
          <p class="admin-hint">Logo, favicon a 2 barvy pro web salonu.</p>
          <div class="upload-box">
            <h4>Logo</h4>
            <div class="hero-preview" id="logo-preview"></div>
            <label class="btn btn-secondary btn-upload">
              Nahrát logo
              <input type="file" id="upload-logo" accept="image/*" hidden>
            </label>
            <button type="button" id="btn-clear-logo" class="btn btn-secondary btn-sm">Odebrat logo</button>
          </div>
          <div class="upload-box">
            <h4>Favicon</h4>
            <div class="hero-preview" id="favicon-preview"></div>
            <label class="btn btn-secondary btn-upload">
              Nahrát favicon
              <input type="file" id="upload-favicon" accept="image/*" hidden>
            </label>
            <button type="button" id="btn-clear-favicon" class="btn btn-secondary btn-sm">Odebrat favicon</button>
          </div>
          <label for="edit-primary-color">Primární barva (pozadí / hlavní)</label>
          <div class="color-row">
            <input type="color" id="edit-primary-color" value="#080808">
            <input type="text" id="edit-primary-color-hex" maxlength="7" placeholder="#080808">
          </div>
          <label for="edit-accent-color">Akcentová barva (zvýraznění)</label>
          <div class="color-row">
            <input type="color" id="edit-accent-color" value="#c9a962">
            <input type="text" id="edit-accent-color-hex" maxlength="7" placeholder="#c9a962">
          </div>
        </div>
"""

VIZUAL_PANEL_SALON4 = VIZUAL_PANEL.replace('        <div class="tab-panel"', '          <div class="tab-panel"').replace(
    '\n          ', '\n            '
).replace('\n        </div>\n', '\n          </div>\n')

JS_HELPERS = r'''
function applySalonBrand(data) {
  const root = document.documentElement;
  if (data.primary_color) {
    root.style.setProperty('--bg', data.primary_color);
    root.style.setProperty('--surface', data.primary_color);
  }
  if (data.accent_color) {
    root.style.setProperty('--gold', data.accent_color);
    root.style.setProperty('--accent', data.accent_color);
  }

  let icon = document.querySelector('link[data-salon-favicon]');
  if (data.favicon_url) {
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      icon.setAttribute('data-salon-favicon', '1');
      document.head.appendChild(icon);
    }
    icon.href = data.favicon_url;
  } else if (icon) {
    icon.remove();
  }

  const nav = document.getElementById('nav-logo');
  if (!nav) return;
  if (data.logo_url) {
    nav.innerHTML = `<img class="nav-logo-img" src="${esc(data.logo_url)}" alt="${esc(data.name || 'Logo')}">`;
  } else if (!nav.querySelector('img.nav-logo-img') && !(nav.textContent || '').trim()) {
    nav.textContent = data.name || '';
  } else if (data.logo_url === '' || data.logo_url == null) {
    if (nav.dataset.brandFallback) {
      nav.textContent = nav.dataset.brandFallback;
    } else if (!nav.querySelector('img')) {
      /* keep existing text set by renderSalon */
    }
  }
}

function renderBrandPreview(elId, url, emptyText) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = url
    ? `<img src="${esc(url)}" alt="">`
    : `<span class="placeholder">${emptyText}</span>`;
}

function syncColorInputs(kind, hex) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl) return;
  const value = /^#[0-9A-Fa-f]{6}$/.test(hex || '') ? hex : colorEl.value;
  colorEl.value = value;
  hexEl.value = value.toUpperCase();
}

function wireColorPair(kind) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl || colorEl.dataset.wired) return;
  colorEl.dataset.wired = '1';
  colorEl.addEventListener('input', () => {
    hexEl.value = colorEl.value.toUpperCase();
  });
  hexEl.addEventListener('change', () => {
    let v = (hexEl.value || '').trim();
    if (v && !v.startsWith('#')) v = `#${v}`;
    if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
      colorEl.value = v;
      hexEl.value = v.toUpperCase();
    } else {
      hexEl.value = colorEl.value.toUpperCase();
    }
  });
}

async function handleBrandUpload(e, typ) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = await uploadImage(file, typ);
    if (typ === 'logo') {
      salonData.logo_url = data.url;
      renderBrandPreview('logo-preview', data.url, 'Žádné logo');
    } else {
      salonData.favicon_url = data.url;
      renderBrandPreview('favicon-preview', data.url, 'Žádný favicon');
    }
    renderSalon(salonData);
    const msg = document.getElementById('status-msg');
    msg.textContent = typ === 'logo' ? 'Logo nahráno.' : 'Favicon nahrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    const msg = document.getElementById('status-msg');
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function clearBrandAsset(field) {
  if (!staffToken || !isMajitel()) return;
  const msg = document.getElementById('status-msg');
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/`, {
      method: 'PUT',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ [field]: '' }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || JSON.stringify(err));
    }
    salonData = await fetchSalon();
    renderSalon(salonData);
    showEditForm();
    msg.textContent = field === 'logo_url' ? 'Logo odebráno.' : 'Favicon odebrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

'''

# Simpler applySalonBrand for demos: always set text fallback then logo overrides
JS_HELPERS_SIMPLE_BRAND = r'''
function applySalonBrand(data) {
  const root = document.documentElement;
  if (data.primary_color) {
    root.style.setProperty('--bg', data.primary_color);
    root.style.setProperty('--surface', data.primary_color);
  }
  if (data.accent_color) {
    root.style.setProperty('--gold', data.accent_color);
    root.style.setProperty('--accent', data.accent_color);
  }

  let icon = document.querySelector('link[data-salon-favicon]');
  if (data.favicon_url) {
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      icon.setAttribute('data-salon-favicon', '1');
      document.head.appendChild(icon);
    }
    icon.href = data.favicon_url;
  } else if (icon) {
    icon.remove();
  }

  const nav = document.getElementById('nav-logo');
  if (!nav) return;
  if (data.logo_url) {
    nav.innerHTML = `<img class="nav-logo-img" src="${esc(data.logo_url)}" alt="${esc(data.name || 'Logo')}">`;
  } else {
    const fallback = nav.dataset.fallbackText || data.name || '';
    nav.textContent = fallback;
  }
}

function renderBrandPreview(elId, url, emptyText) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = url
    ? `<img src="${esc(url)}" alt="">`
    : `<span class="placeholder">${emptyText}</span>`;
}

function syncColorInputs(kind, hex) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl) return;
  const value = /^#[0-9A-Fa-f]{6}$/.test(hex || '') ? hex : colorEl.value;
  colorEl.value = value;
  hexEl.value = value.toUpperCase();
}

function wireColorPair(kind) {
  const colorEl = document.getElementById(`edit-${kind}-color`);
  const hexEl = document.getElementById(`edit-${kind}-color-hex`);
  if (!colorEl || !hexEl || colorEl.dataset.wired) return;
  colorEl.dataset.wired = '1';
  colorEl.addEventListener('input', () => {
    hexEl.value = colorEl.value.toUpperCase();
  });
  hexEl.addEventListener('change', () => {
    let v = (hexEl.value || '').trim();
    if (v && !v.startsWith('#')) v = `#${v}`;
    if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
      colorEl.value = v;
      hexEl.value = v.toUpperCase();
    } else {
      hexEl.value = colorEl.value.toUpperCase();
    }
  });
}

async function handleBrandUpload(e, typ) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = await uploadImage(file, typ);
    if (typ === 'logo') {
      salonData.logo_url = data.url;
      renderBrandPreview('logo-preview', data.url, 'Žádné logo');
    } else {
      salonData.favicon_url = data.url;
      renderBrandPreview('favicon-preview', data.url, 'Žádný favicon');
    }
    renderSalon(salonData);
    const msg = document.getElementById('status-msg');
    msg.textContent = typ === 'logo' ? 'Logo nahráno.' : 'Favicon nahrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    const msg = document.getElementById('status-msg');
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
  e.target.value = '';
}

async function clearBrandAsset(field) {
  if (!staffToken || !isMajitel()) return;
  const msg = document.getElementById('status-msg');
  try {
    const res = await fetch(`${API_BASE}/salon/${SALON_ID}/`, {
      method: 'PUT',
      headers: staffHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ [field]: '' }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || JSON.stringify(err));
    }
    salonData = await fetchSalon();
    renderSalon(salonData);
    showEditForm();
    msg.textContent = field === 'logo_url' ? 'Logo odebráno.' : 'Favicon odebrán.';
    msg.className = 'status-msg success';
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'status-msg error';
  }
}

'''

CSS_EXTRA = """
.nav-logo-img {
  display: block;
  max-height: 48px;
  max-width: 180px;
  width: auto;
  height: auto;
  object-fit: contain;
}

.color-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}

.color-row input[type="color"] {
  width: 48px;
  height: 36px;
  padding: 0;
  border: 1px solid rgba(128,128,128,0.35);
  background: transparent;
  cursor: pointer;
}

.color-row input[type="text"] {
  flex: 1;
}
"""


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'data-tab="vizual"' in text:
        return False
    orig = text
    if path.parent.name == 'salon4':
        text = text.replace(
            '            <button type="button" class="tab" data-tab="obrazky">Obrázky</button>\n'
            '            <button type="button" class="tab" data-tab="personel">Personál</button>',
            VIZUAL_TAB_SALON4 + '\n            <button type="button" class="tab" data-tab="personel">Personál</button>',
            1,
        )
        marker = '          <div class="tab-panel" data-panel="personel">'
        if marker in text and 'data-panel="vizual"' not in text:
            text = text.replace(marker, VIZUAL_PANEL_SALON4 + marker, 1)
    else:
        text = text.replace(
            '          <button type="button" class="tab" data-tab="obrazky">Obrázky</button>\n'
            '          <button type="button" class="tab" data-tab="personel">Personál</button>',
            VIZUAL_TAB + '\n          <button type="button" class="tab" data-tab="personel">Personál</button>',
            1,
        )
        marker = '        <div class="tab-panel" data-panel="personel">'
        if marker in text and 'data-panel="vizual"' not in text:
            text = text.replace(marker, VIZUAL_PANEL + marker, 1)
    if text == orig:
        print(f'  HTML miss: {path.parent.name}')
        return False
    path.write_text(text, encoding='utf-8')
    return True


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'function applySalonBrand(' in text:
        return False
    orig = text

    if 'function renderSalon(data)' not in text:
        print(f'  JS no renderSalon: {path.parent.name}')
        return False

    text = text.replace(
        'function renderSalon(data) {',
        JS_HELPERS_SIMPLE_BRAND + 'function renderSalon(data) {',
        1,
    )

    # Capture fallback text into dataset then apply brand
    # Replace common nav-logo assignments
    patterns = [
        (
            r"  const shortBrand = \(data\.name \|\| ''\)\.replace\(/\^Salon\\s\+/i, ''\)\.trim\(\) \|\| data\.name;\n"
            r"  document\.getElementById\('nav-logo'\)\.textContent = shortBrand;",
            "  const shortBrand = (data.name || '').replace(/^Salon\\s+/i, '').trim() || data.name;\n"
            "  const _nav = document.getElementById('nav-logo');\n"
            "  if (_nav) _nav.dataset.fallbackText = shortBrand;\n"
            "  applySalonBrand(data);",
        ),
        (
            r"  const navLogo = document\.getElementById\('nav-logo'\);\n"
            r"  if \(navLogo\) navLogo\.textContent = data\.name;",
            "  const navLogo = document.getElementById('nav-logo');\n"
            "  if (navLogo) navLogo.dataset.fallbackText = data.name;\n"
            "  applySalonBrand(data);",
        ),
        (
            r"  document\.getElementById\('nav-logo'\)\.textContent = data\.name\.split\(' '\)\.pop\(\)\?\.toUpperCase\(\) \|\| data\.name;",
            "  const _nav = document.getElementById('nav-logo');\n"
            "  if (_nav) _nav.dataset.fallbackText = data.name.split(' ').pop()?.toUpperCase() || data.name;\n"
            "  applySalonBrand(data);",
        ),
        (
            r"  document\.getElementById\('nav-logo'\)\.textContent = data\.name;",
            "  const _nav = document.getElementById('nav-logo');\n"
            "  if (_nav) _nav.dataset.fallbackText = data.name;\n"
            "  applySalonBrand(data);",
        ),
    ]
    replaced_nav = False
    for pat, repl in patterns:
        try:
            new_text, n = re.subn(pat, lambda _m, r=repl: r, text, count=1)
        except re.error as err:
            print(f'  JS regex error {path.parent.name}: {err}')
            n = 0
            new_text = text
        if n:
            text = new_text
            replaced_nav = True
            break
    if not replaced_nav:
        text = text.replace(
            'function renderSalon(data) {\n  document.title = data.name;',
            'function renderSalon(data) {\n  document.title = data.name;\n  applySalonBrand(data);',
            1,
        )

    insert_edit = (
        "  document.getElementById('edit-email').value = d.email;\n\n"
        "  syncColorInputs('primary', d.primary_color || '#080808');\n"
        "  syncColorInputs('accent', d.accent_color || '#c9a962');\n"
        "  renderBrandPreview('logo-preview', d.logo_url, 'Žádné logo');\n"
        "  renderBrandPreview('favicon-preview', d.favicon_url, 'Žádný favicon');\n"
    )
    if "document.getElementById('edit-email').value = d.email;" in text and "renderBrandPreview('logo-preview', d.logo_url" not in text:
        text = text.replace(
            "  document.getElementById('edit-email').value = d.email;\n",
            insert_edit,
            1,
        )

    old_return = (
        "    email: document.getElementById('edit-email').value,\n"
        "    cenik, novinky, obrazky,\n"
        "  };"
    )
    new_return = (
        "    email: document.getElementById('edit-email').value,\n"
        "    primary_color: document.getElementById('edit-primary-color')?.value || '',\n"
        "    accent_color: document.getElementById('edit-accent-color')?.value || '',\n"
        "    cenik, novinky, obrazky,\n"
        "  };"
    )
    if old_return in text:
        text = text.replace(old_return, new_return, 1)
    else:
        # variant without obrazky
        old2 = (
            "    email: document.getElementById('edit-email').value,\n"
            "    cenik, novinky,\n"
            "  };"
        )
        new2 = (
            "    email: document.getElementById('edit-email').value,\n"
            "    primary_color: document.getElementById('edit-primary-color')?.value || '',\n"
            "    accent_color: document.getElementById('edit-accent-color')?.value || '',\n"
            "    cenik, novinky,\n"
            "  };"
        )
        if old2 in text:
            text = text.replace(old2, new2, 1)
        else:
            print(f'  JS collectFormData miss: {path.parent.name}')

    listeners = (
        "document.getElementById('upload-gallery').addEventListener('change', handleGalleryUpload);\n"
        "document.getElementById('upload-logo')?.addEventListener('change', (e) => handleBrandUpload(e, 'logo'));\n"
        "document.getElementById('upload-favicon')?.addEventListener('change', (e) => handleBrandUpload(e, 'favicon'));\n"
        "document.getElementById('btn-clear-logo')?.addEventListener('click', () => clearBrandAsset('logo_url'));\n"
        "document.getElementById('btn-clear-favicon')?.addEventListener('click', () => clearBrandAsset('favicon_url'));\n"
        "wireColorPair('primary');\n"
        "wireColorPair('accent');"
    )
    if "upload-logo" not in text:
        text = text.replace(
            "document.getElementById('upload-gallery').addEventListener('change', handleGalleryUpload);",
            listeners,
            1,
        )

    if text == orig:
        print(f'  JS no change: {path.parent.name}')
        return False
    path.write_text(text, encoding='utf-8')
    return True


def patch_css(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    if '.color-row' in text and '.nav-logo-img' in text:
        return False
    path.write_text(text.rstrip() + '\n' + CSS_EXTRA + '\n', encoding='utf-8')
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
