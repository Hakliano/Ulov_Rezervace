"""Remove salon primary/accent color settings from all demos (keep logo/favicon)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SKIP = {'backend', 'flow', 'deploy', 'presentace', 'node_modules', '.git', '.cursor'}

COLOR_HTML_RE = re.compile(
    r'\s*<label for="edit-primary-color">.*?</div>\s*'
    r'<label for="edit-accent-color">.*?</div>\s*',
    re.DOTALL,
)

# Also handle salon4 indented variants / slight text differences
COLOR_HTML_RE2 = re.compile(
    r'\s*<label[^>]*for="edit-primary-color"[^>]*>.*?'
    r'<div class="color-row">.*?</div>\s*'
    r'<label[^>]*for="edit-accent-color"[^>]*>.*?'
    r'<div class="color-row">.*?</div>\s*',
    re.DOTALL,
)


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'edit-primary-color' not in text:
        return False
    new, n = COLOR_HTML_RE2.subn('\n', text, count=1)
    if n == 0:
        new, n = COLOR_HTML_RE.subn('\n', text, count=1)
    if n == 0:
        print('HTML pattern miss', path)
        return False
    # update hint if it mentions 2 barvy
    new = new.replace(
        'Logo, favicon a 2 barvy pro web salonu.',
        'Logo a favicon pro web salonu.',
    )
    new = new.replace(
        'Logo, favicon a 2 barvy pro web.',
        'Logo a favicon pro web.',
    )
    path.write_text(new, encoding='utf-8')
    return True


def strip_apply_colors(fn_body: str) -> str:
    """Remove primary/accent CSS var logic from applySalonBrand."""
    # Remove blocks that set --bg/--surface/--gold/--accent from colors
    fn_body = re.sub(
        r'\s*if \(data\.primary_color\) \{[^}]+\}\s*'
        r'(?:else \{\s*root\.style\.removeProperty\(\'--bg\'\);\s*'
        r'root\.style\.removeProperty\(\'--surface\'\);\s*\}\s*)?',
        '\n',
        fn_body,
        count=1,
        flags=re.DOTALL,
    )
    fn_body = re.sub(
        r'\s*if \(data\.accent_color\) \{[^}]+\}\s*'
        r'(?:else \{\s*root\.style\.removeProperty\(\'--gold\'\);\s*'
        r'(?:root\.style\.removeProperty\(\'--accent\'\);\s*)?\}\s*)?',
        '\n',
        fn_body,
        count=1,
        flags=re.DOTALL,
    )
    return fn_body


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'edit-primary-color' not in text and 'primary_color' not in text:
        return False
    orig = text

    # applySalonBrand: drop color branches
    m = re.search(r'function applySalonBrand\(data\) \{', text)
    if m:
        start = m.start()
        # find matching close of function - naive brace count
        i = m.end() - 1
        depth = 0
        end = None
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end:
            old_fn = text[start:end]
            new_fn = strip_apply_colors(old_fn)
            # ensure we still remove leftover color props if any
            new_fn = re.sub(r'\s*root\.style\.setProperty\(\'--bg\'[^;]+;\s*', '\n  ', new_fn)
            new_fn = re.sub(r'\s*root\.style\.setProperty\(\'--surface\'[^;]+;\s*', '\n  ', new_fn)
            new_fn = re.sub(r'\s*root\.style\.setProperty\(\'--gold\'[^;]+;\s*', '\n  ', new_fn)
            new_fn = re.sub(r'\s*root\.style\.setProperty\(\'--accent\'[^;]+;\s*', '\n  ', new_fn)
            text = text[:start] + new_fn + text[end:]

    # Remove brand color load block
    text = re.sub(
        r'\s*window\.__brandColorsLoaded = \{[^}]+\};\s*'
        r'//[^\n]*\n\s*'
        r'syncColorInputs\(\'primary\'[^;]+;\s*'
        r'syncColorInputs\(\'accent\'[^;]+;\s*',
        '\n',
        text,
        count=1,
    )
    # older without comment
    text = re.sub(
        r'\s*window\.__brandColorsLoaded = \{[^}]+\};\s*'
        r'syncColorInputs\(\'primary\'[^;]+;\s*'
        r'syncColorInputs\(\'accent\'[^;]+;\s*',
        '\n',
        text,
        count=1,
    )
    text = re.sub(
        r'\s*syncColorInputs\(\'primary\'[^;]+;\s*'
        r'syncColorInputs\(\'accent\'[^;]+;\s*',
        '\n',
        text,
        count=1,
    )

    # collectFormData: always clear colors (wipe DB leftovers on next save)
    text = re.sub(
        r'\s*primary_color: \(\(\) => \{.*?\}\) \(\),\s*'
        r'accent_color: \(\(\) => \{.*?\}\) \(\),\s*',
        '\n    primary_color: \'\',\n    accent_color: \'\',\n',
        text,
        count=1,
        flags=re.DOTALL,
    )
    # simpler form
    text = re.sub(
        r'\s*primary_color: document\.getElementById\(\'edit-primary-color\'\)\?\.value \|\| \'\',\s*'
        r'accent_color: document\.getElementById\(\'edit-accent-color\'\)\?\.value \|\| \'\',\s*',
        '\n    primary_color: \'\',\n    accent_color: \'\',\n',
        text,
        count=1,
    )
    # IIFE form from previous fix
    text = re.sub(
        r'\s*primary_color: \(\(\) => \{[\s\S]*?\}\) \(\),\s*'
        r'accent_color: \(\(\) => \{[\s\S]*?\}\) \(\),\s*',
        '\n    primary_color: \'\',\n    accent_color: \'\',\n',
        text,
        count=1,
    )

    # Remove wireColorPair calls and function if present
    text = re.sub(r'\nwireColorPair\(\'primary\'\);\nwireColorPair\(\'accent\'\);\n', '\n', text)
    text = re.sub(
        r'\nfunction wireColorPair\(kind\) \{[\s\S]*?\n\}\n',
        '\n',
        text,
        count=1,
    )
    text = re.sub(
        r'\nfunction syncColorInputs\(kind, hex\) \{[\s\S]*?\n\}\n',
        '\n',
        text,
        count=1,
    )

    if text != orig:
        path.write_text(text, encoding='utf-8')
        return True
    return False


def main():
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name in SKIP:
            continue
        html, js = d / 'index.html', d / 'app.js'
        if html.exists():
            print(('html OK ' if patch_html(html) else 'html -- '), d.name)
        if js.exists():
            print(('js OK  ' if patch_js(js) else 'js --  '), d.name)


if __name__ == '__main__':
    main()
