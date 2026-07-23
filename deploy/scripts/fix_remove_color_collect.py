from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SKIP = {'backend', 'flow', 'deploy', 'presentace', 'node_modules', '.git', '.cursor'}

IIFE = re.compile(
    r"primary_color: \(\(\) => \{.*?\}\) \(\),\s*"
    r"accent_color: \(\(\) => \{.*?\}\) \(\),",
    re.DOTALL,
)
# real JS uses })(), not \) (),
IIFE2 = re.compile(
    r"primary_color: \(\(\) => \{.*?\}\) \(\),",
    re.DOTALL,
)

# Correct pattern for: primary_color: (() => { ... })(),
PAT = re.compile(
    r"primary_color: \(\(\) => \{.*?\}\) \(\),\s*\n\s*"
    r"accent_color: \(\(\) => \{.*?\}\) \(\),",
    re.DOTALL,
)

# Actually in file it's: })(),  which is `})(),`
PAT = re.compile(
    r"primary_color: \(\(\) => \{.*?\}\) \(\),[\r\n]+\s*"
    r"accent_color: \(\(\) => \{.*?\}\) \(\),",
    re.DOTALL,
)

# Wait - in JS source: })(), 
# characters: } ) ( ) ,
# In my regex I had `\) \(\)` which is ) ( )  - WRONG
# Correct: `\}\)\(\),` 

PAT = re.compile(
    r"primary_color: \(\(\) => \{.*?\}\)\(\),[\r\n]+\s*"
    r"accent_color: \(\(\) => \{.*?\}\)\(\),",
    re.DOTALL,
)

REPL = "primary_color: '',\n    accent_color: '',"

for p in ROOT.rglob('app.js'):
    if any(x in p.parts for x in SKIP):
        continue
    t = p.read_text(encoding='utf-8')
    if 'edit-primary-color' not in t and '__brandColorsLoaded' not in t and "(() => {" not in t:
        # still may have IIFE
        pass
    newt, n = PAT.subn(REPL, t, count=1)
    if n:
        # also tidy applySalonBrand leading whitespace
        newt = newt.replace(
            'function applySalonBrand(data) {\n  const root = document.documentElement;\nlet icon',
            'function applySalonBrand(data) {\n  let icon',
        )
        newt = newt.replace(
            'function applySalonBrand(data) {\n  const root = document.documentElement;\n  let icon',
            'function applySalonBrand(data) {\n  let icon',
        )
        newt = newt.replace(
            'function applySalonBrand(data) {\nlet icon',
            'function applySalonBrand(data) {\n  let icon',
        )
        p.write_text(newt, encoding='utf-8')
        print('fixed collect', p.relative_to(ROOT))
    else:
        if 'primary_color: (() =>' in t:
            print('MISS', p.relative_to(ROOT))
            # show snippet
            i = t.index('primary_color: (() =>')
            print(repr(t[i:i+120]))
