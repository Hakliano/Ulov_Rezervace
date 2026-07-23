"""Fix brand color save: don't persist shared placeholders; keep empty empty."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OLD_SYNC = (
    "  syncColorInputs('primary', d.primary_color || '#080808');\n"
    "  syncColorInputs('accent', d.accent_color || '#c9a962');"
)

NEW_SYNC = """  window.__brandColorsLoaded = {
    primary: (d.primary_color || '').trim(),
    accent: (d.accent_color || '').strip(),
  };
  // type=color musí mít hodnotu; placeholder se neukládá, pokud DB byla prázdná
  syncColorInputs('primary', d.primary_color || '#080808');
  syncColorInputs('accent', d.accent_color || '#c9a962');"""

# typo fix - I used strip wrongly on accent in NEW_SYNC above, use trim for both
NEW_SYNC = """  window.__brandColorsLoaded = {
    primary: (d.primary_color || '').trim(),
    accent: (d.accent_color || '').trim(),
  };
  // type=color musí mít hodnotu; placeholder se neukládá, pokud DB byla prázdná
  syncColorInputs('primary', d.primary_color || '#080808');
  syncColorInputs('accent', d.accent_color || '#c9a962');"""

OLD_COLLECT = (
    "    primary_color: document.getElementById('edit-primary-color')?.value || '',\n"
    "    accent_color: document.getElementById('edit-accent-color')?.value || '',"
)

NEW_COLLECT = """    primary_color: (() => {
      const v = (document.getElementById('edit-primary-color')?.value || '').trim();
      const loaded = (window.__brandColorsLoaded?.primary || '').trim();
      if (!loaded && v.toLowerCase() === '#080808') return '';
      return v;
    })(),
    accent_color: (() => {
      const v = (document.getElementById('edit-accent-color')?.value || '').trim();
      const loaded = (window.__brandColorsLoaded?.accent || '').trim();
      if (!loaded && v.toLowerCase() === '#c9a962') return '';
      return v;
    })(),"""


def main():
    skip = {'backend', 'flow', 'deploy', 'presentace', 'node_modules', '.git', '.cursor'}
    for app in ROOT.rglob('app.js'):
        if any(p in skip for p in app.parts):
            continue
        text = app.read_text(encoding='utf-8')
        orig = text
        if 'window.__brandColorsLoaded' not in text and OLD_SYNC in text:
            text = text.replace(OLD_SYNC, NEW_SYNC, 1)
        if 'window.__brandColorsLoaded?.primary' not in text and OLD_COLLECT in text:
            text = text.replace(OLD_COLLECT, NEW_COLLECT, 1)
        text = text.replace(
            '  applySalonBrand(data);\n  applySalonBanner(data);\n',
            '  applySalonBrand(data);\n',
        )
        if text != orig:
            app.write_text(text, encoding='utf-8')
            print('patched', app.relative_to(ROOT))
        else:
            print('skip', app.relative_to(ROOT))


if __name__ == '__main__':
    main()
