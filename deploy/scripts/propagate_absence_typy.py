from pathlib import Path

root = Path(r'c:\Users\Jirka\Projekty\weby_s_externi_DTB')
old = """                    <select id="absence-typ">
                      <option value="dovolena">Dovolená</option>
                      <option value="volno">Volno</option>
                      <option value="nemoc">Nemoc</option>"""
new = """                    <select id="absence-typ">
                      <option value="dovolena">Dovolená</option>
                      <option value="nemoc">Nemoc</option>
                      <option value="technicke">Technické problémy</option>"""
old_h = '<div class="settings-card-head"><h4>Volno / dovolená / nemoc</h4></div>'
new_h = '<div class="settings-card-head"><h4>Dovolená / nemoc / technické problémy</h4></div>'

for f in root.rglob('rezervace.html'):
    if 'node_modules' in str(f):
        continue
    t = f.read_text(encoding='utf-8')
    orig = t
    t = t.replace(old, new)
    t = t.replace(old_h, new_h)
    if t != orig:
        f.write_text(t, encoding='utf-8')
        print('updated', f.relative_to(root))
    else:
        print('skip', f.relative_to(root))
