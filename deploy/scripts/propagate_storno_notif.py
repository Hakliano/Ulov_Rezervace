from pathlib import Path

root = Path(r'c:\Users\Jirka\Projekty\weby_s_externi_DTB')
files = [f for f in root.rglob('rezervace.js') if 'node_modules' not in str(f)]

old_max = """const MAX_NOTIFIKACE = 4;

const NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show, bez automatického času',
  'Žádost o úhradu na účet s QR kódem — pouze ručně u rezervace (tlačítko Požádat o platbu)',
];"""

new_max = """const MAX_NOTIFIKACE = 5;

const NOTIF_POPISY = [
  'Připomínka před termínem (doporučeno +24 h) — odesílá se automaticky',
  'Poděkování po návštěvě a prosba o recenzi (doporučeno -2 h po službě) — automaticky',
  'Upozornění na neuskutečněnou rezervaci — pouze ručně u NO-show, bez automatického času',
  'Žádost o úhradu na účet s QR kódem — pouze ručně u rezervace (tlačítko Požádat o platbu)',
  'Storno rezervace — odešle se při zrušení rezervace salonem / ve FLOW (ne automaticky v čase)',
];"""

replacements = [
    (old_max, new_max),
    (
        "const manualTyp = n.manual_typ || (i === 3 ? 'platba' : 'noshow');",
        "const manualTyp = n.manual_typ || (i === 4 ? 'storno' : i === 3 ? 'platba' : 'noshow');",
    ),
    (
        """    manualHint.textContent = manualTyp === 'platba'
      ? 'Tento e-mail se neodesílá automaticky. Personál ho odešle tlačítkem „Požádat o platbu na účet“ u rezervace — v e-mailu bude QR kód pro platbu.'
      : 'Tento e-mail se neodesílá automaticky. Text si připravíte zde, odešle se až po stisknutí NO-show u konkrétní rezervace v kalendáři.';""",
        """    if (manualTyp === 'platba') {
      manualHint.textContent = 'Tento e-mail se neodesílá automaticky. Personál ho odešle tlačítkem „Požádat o platbu na účet“ u rezervace — v e-mailu bude QR kód pro platbu.';
    } else if (manualTyp === 'storno') {
      manualHint.textContent = 'Tento e-mail se odešle zákazníkovi při stornu rezervace (admin / FLOW). Tag {{ kdo }} = salon nebo zákazník.';
    } else {
      manualHint.textContent = 'Tento e-mail se neodesílá automaticky. Text si připravíte zde, odešle se až po stisknutí NO-show u konkrétní rezervace v kalendáři.';
    }""",
    ),
    (
        "const manualTyp = card.dataset.manualTyp || (i === 3 ? 'platba' : 'noshow');",
        "const manualTyp = card.dataset.manualTyp || (i === 4 ? 'storno' : i === 3 ? 'platba' : 'noshow');",
    ),
    (
        "aktivni: manualTyp === 'platba',",
        "aktivni: manualTyp === 'platba' || manualTyp === 'storno',",
    ),
]

for f in files:
    t = f.read_text(encoding='utf-8')
    orig = t
    for a, b in replacements:
        t = t.replace(a, b)
    if t != orig:
        f.write_text(t, encoding='utf-8')
        print('updated', f.relative_to(root))
    elif 'MAX_NOTIFIKACE = 5' in t:
        print('already', f.relative_to(root))
    else:
        print('SKIP', f.relative_to(root))
