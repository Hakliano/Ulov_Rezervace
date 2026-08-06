#!/usr/bin/env python3
"""Jednorázově napojí shared/owner-flow-admin.js do všech demo webů."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = [
    "salon1",
    "salon2",
    "salon3",
    "salon4",
    "salon5",
    "salon6",
    "salon7",
    "salon8",
    "provoz-autoservis",
    "provoz-pujcovna",
    "provoz-studio",
    "zdravi-dental",
    "zdravi-fyzio",
    "zdravi-veterina",
    "remesla-elektrikar",
    "remesla-instalater",
    "remesla-rekonstrukce",
]

CONFIG = """
window.UlovOwnerFlowConfig = {
  getSalonId: () => SALON_ID,
  getApiBase: () => API_BASE,
  getToken: () => staffToken,
  isMajitel: () => isMajitel(),
  getEmail: () => (
    document.getElementById('staff-login')?.value
    || staffUser?.prihlasovaci_jmeno
    || staffUser?.email
    || ''
  ).trim(),
};
"""

SCRIPT = '<script src="../shared/owner-flow-admin.js"></script>'


def patch_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    if "owner-flow-admin.js" not in text:
        m = re.search(r'[ \t]*<script[^>]+src="[^"]*app\.js[^"]*"[^>]*>\s*</script>', text)
        if not m:
            print(f"  ! no app.js script: {path}")
            return False
        indent = re.match(r"[ \t]*", m.group(0)).group(0)
        text = text[: m.start()] + f"{indent}{SCRIPT}\n{m.group(0)}" + text[m.end() :]
    if 'data-tab="heslo"' not in text and 'data-tab="email"' in text:
        text = re.sub(
            r'(<button type="button" class="tab" data-tab="email">E-mail</button>)',
            r'\1\n          <button type="button" class="tab" data-tab="heslo">Heslo</button>',
            text,
            count=1,
        )
    if text != orig:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def patch_js(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    if "UlovOwnerFlowConfig" not in text:
        m = re.search(r"const SALON_ID = \d+;\n", text)
        if not m:
            print(f"  ! no SALON_ID: {path}")
            return False
        text = text[: m.end()] + CONFIG + text[m.end() :]
    if "UlovOwnerFlow?.onAdminShown" not in text:
        needle = "document.getElementById('edit-section').classList.remove('hidden');"
        if needle in text:
            text = text.replace(
                needle,
                needle + "\n  window.UlovOwnerFlow?.onAdminShown?.();",
                1,
            )
        else:
            print(f"  ! no edit-section show: {path}")
    if text != orig:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def main() -> None:
    for name in DEMOS:
        html = ROOT / name / "index.html"
        js = ROOT / name / "app.js"
        h = patch_html(html) if html.exists() else None
        j = patch_js(js) if js.exists() else None
        print(f"{name}: html={h} js={j}")


if __name__ == "__main__":
    main()
