"""Remove demo username placeholders (eva, majitelka, spravce) from HTML."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPLACEMENTS = (
    ' placeholder="eva"',
    " placeholder='eva'",
    ' placeholder="majitelka"',
    " placeholder='majitelka'",
    ' placeholder="spravce"',
    " placeholder='spravce'",
)


def main():
    changed = []
    for path in ROOT.rglob("*.html"):
        if any(p in path.parts for p in (".git", "node_modules", "venv", ".venv")):
            continue
        text = path.read_text(encoding="utf-8")
        orig = text
        for old in REPLACEMENTS:
            text = text.replace(old, "")
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
    for c in changed:
        print(c)
    print(f"files={len(changed)}")


if __name__ == "__main__":
    main()
