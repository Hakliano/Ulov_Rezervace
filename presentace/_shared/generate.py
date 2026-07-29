# -*- coding: utf-8 -*-
"""
Shared homepage generator for presentace verticals.

Source of truth:
  presentace/_shared/templates/   — shared HTML/CSS/JS
  presentace/_shared/brands/*.json — colors + demos per vertical

Usage:
  python presentace/_shared/generate.py            # render all verticals
  python presentace/_shared/generate.py --bootstrap # (re)extract brands + rebuild templates, then render
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
SHARED = Path(__file__).resolve().parent
BRANDS_DIR = SHARED / "brands"
TEMPLATES_DIR = SHARED / "templates"
VERTICALS = ["beauty", "zdravi", "remesla", "provozovny"]

UNIFIED_REPLACEMENTS = [
    ("Partner pro váš salon", "Partner pro vaši provozovnu"),
    ("Partner pro vaši ordinaci", "Partner pro vaši provozovnu"),
    ("Partner pro vaši živnost", "Partner pro vaši provozovnu"),
    ("právě váš salon", "právě vaše provozovna"),
    ("právě vaše ordinace", "právě vaše provozovna"),
    ("právě vaše živnost", "právě vaše provozovna"),
    ("digitální chod salonu", "digitální chod provozovny"),
    ("digitální chod ordinace", "digitální chod provozovny"),
    ("digitální chod živnosti", "digitální chod provozovny"),
    ("digitální zázemí salonu", "digitální zázemí provozovny"),
    ("digitální zázemí ordinace", "digitální zázemí provozovny"),
    ("digitální zázemí živnosti", "digitální zázemí provozovny"),
    ("péči o celé digitální zázemí salonu", "péči o celé digitální zázemí provozovny"),
    ("péči o celé digitální zázemí ordinace", "péči o celé digitální zázemí provozovny"),
    ("péči o celé digitální zázemí živnosti", "péči o celé digitální zázemí provozovny"),
    ("vašemu salonu", "vaší provozovně"),
    ("vaší ordinaci", "vaší provozovně"),
    ("vaší živnosti", "vaší provozovně"),
    ("vašeho salonu", "vaší provozovny"),
    ("vaší ordinace", "vaší provozovny"),
    ("vašem salonu", "vaší provozovně"),
    ("svém salonu", "své provozovně"),
    ("své ordinaci", "své provozovně"),
    ("své živnosti", "své provozovně"),
    ("k vašemu salonu", "k vaší provozovně"),
    ("k vaší ordinaci", "k vaší provozovně"),
    ("k vaší živnosti", "k vaší provozovně"),
    ("ve stylu vašeho salonu", "ve stylu vaší provozovny"),
    ("ve stylu vaší ordinace", "ve stylu vaší provozovny"),
    ("ve stylu vaší živnosti", "ve stylu vaší provozovny"),
    ("jak váš salon funguje", "jak vaše provozovna funguje"),
    ("jak vaše ordinace funguje", "jak vaše provozovna funguje"),
    ("jak vaše živnost funguje", "jak vaše provozovna funguje"),
    ("posouváme váš salon", "posouváme vaše podnikání"),
    ("posouváme vaši ordinaci", "posouváme vaše podnikání"),
    ("posouváme vaši živnost", "posouváme vaše podnikání"),
    ("posouváme vaši provozovnu", "posouváme vaše podnikání"),
    ("váš salon", "vaši provozovnu"),
    ("vaši ordinaci", "vaši provozovnu"),
    ("vaši živnost", "vaši provozovnu"),
    ("pro váš salon", "pro vaši provozovnu"),
    ("pro vaši ordinaci", "pro vaši provozovnu"),
    ("pro vaši živnost", "pro vaši provozovnu"),
    ("rozvoji salonu", "rozvoji provozovny"),
    ("rozvoji ordinace", "rozvoji provozovny"),
    ("rozvoji živnosti", "rozvoji provozovny"),
    ("marketing salonu", "marketing provozovny"),
    ("marketing ordinace", "marketing provozovny"),
    ("marketing živnosti", "marketing provozovny"),
    ("zviditelnění salonu", "zviditelnění provozovny"),
    ("zviditelnění ordinace", "zviditelnění provozovny"),
    ("zviditelnění živnosti", "zviditelnění provozovny"),
    ("cesty k salonu", "cesty k provozovně"),
    ("cesty k ordinaci", "cesty k provozovně"),
    ("cesty k živnosti", "cesty k provozovně"),
    ("k salonu", "k provozovně"),
    ("k ordinaci", "k provozovně"),
    ("k živnosti", "k provozovně"),
    ("Video salonu", "Video provozovny"),
    ("Video ordinace", "Video provozovny"),
    ("Video živnosti", "Video provozovny"),
    ("Videa cesty k salonu", "Videa cesty k provozovně"),
    ("Videa cesty k ordinaci", "Videa cesty k provozovně"),
    ("Videa cesty k živnosti", "Videa cesty k provozovně"),
    ("vývoje salonu", "vývoje provozovny"),
    ("vývoje ordinace", "vývoje provozovny"),
    ("vývoje živnosti", "vývoje provozovny"),
    ("Název salonu / podniku", "Název provozovny / podniku"),
    ("Název ordinace / podniku", "Název provozovny / podniku"),
    ("Název živnosti / podniku", "Název provozovny / podniku"),
    ("Např. Studio Krása", "Např. Studio / provozovna"),
    ("Např. Movium", "Např. Studio / provozovna"),
    ("Např. Ateliér řemesla", "Např. Studio / provozovna"),
    ("Např. Provozovna Centrum", "Např. Studio / provozovna"),
    ("pracovní prostředí ordinace", "pracovní prostředí provozovny"),
    ("pracovní prostředí živnosti", "pracovní prostředí provozovny"),
    ("FLOW pro ordinaci a tým", "FLOW pro provozovnu a tým"),
    ("FLOW pro živnost a tým", "FLOW pro provozovnu a tým"),
    ("FLOW CRM pro ordinaci a tým", "FLOW CRM pro provozovnu a tým"),
    ("FLOW CRM pro živnost a tým", "FLOW CRM pro provozovnu a tým"),
    ("Salon postupně rozvíjíme", "Provozovnu postupně rozvíjíme"),
    ("Ordinaci postupně rozvíjíme", "Provozovnu postupně rozvíjíme"),
    ("Živnost postupně rozvíjíme", "Provozovnu postupně rozvíjíme"),
    ("prezentace salonu", "prezentace provozovny"),
    ("prezentace ordinace", "prezentace provozovny"),
    ("prezentace živnosti", "prezentace provozovny"),
    ("Partnerství pro salon:", "Partnerství pro provozovnu:"),
    ("Partnerství pro ordinaci:", "Partnerství pro provozovnu:"),
    ("Partnerství pro živnost:", "Partnerství pro provozovnu:"),
    ("Řekněte nám něco o svém salonu", "Řekněte nám něco o svém podnikání"),
    ("Řekněte nám něco o své ordinaci", "Řekněte nám něco o svém podnikání"),
    ("Řekněte nám něco o své živnosti", "Řekněte nám něco o svém podnikání"),
    ("Řekněte nám něco o své provozovně", "Řekněte nám něco o svém podnikání"),
]


def apply_unified(text: str) -> str:
    for old, new in UNIFIED_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def extract_demo_section(html: str) -> str:
    m = re.search(r'<section class="demos-section" id="demo">.*?</section>', html, re.S)
    if not m:
        raise SystemExit("demo section missing")
    return m.group(0)


def parse_demos(demo_html: str) -> tuple[dict, list[dict]]:
    head: dict = {"title": "", "lead": "", "cta": None}
    sm = re.search(r'<div class="section-head">(.*?)</div>', demo_html, re.S)
    if sm:
        hm = re.search(r"<h2>(.*?)</h2>", sm.group(1), re.S)
        if hm:
            head["title"] = re.sub(r"\s+", " ", hm.group(1)).strip()
        for attrs, content in re.findall(r"<p([^>]*)>(.*?)</p>", sm.group(1), re.S):
            content = re.sub(r"\s+", " ", content).strip()
            if "demos-cta" in attrs:
                head["cta"] = content
            elif not head["lead"]:
                head["lead"] = content

    demos = []
    for i, art in enumerate(
        re.finditer(r'<article class="demo-card">(.*?)</article>', demo_html, re.S), start=1
    ):
        block = art.group(1)
        thumb_m = re.search(r'<div class="demo-thumb\s*([^"]*)">\s*(.*?)</div>', block, re.S)
        thumb_class = (thumb_m.group(1).strip() if thumb_m else f"s{i}") or f"s{i}"
        inner = thumb_m.group(2) if thumb_m else ""
        img: dict = {}
        img_m = re.search(r"<img\s+([^>]+)>", inner, re.S)
        if img_m:
            tag = img_m.group(1)
            src = re.search(r'src="([^"]+)"', tag)
            alt = re.search(r'alt="([^"]*)"', tag)
            img = {
                "src": src.group(1) if src else "",
                "alt": alt.group(1) if alt else "",
                "onerror": "this.remove()" if "onerror=" in tag else None,
            }
        badge_m = re.search(r"<span>(.*?)</span>", inner, re.S)
        badge = badge_m.group(1).strip() if badge_m else None
        name = re.search(r"<h3>(.*?)</h3>", block, re.S)
        dtype = re.search(r'class="demo-type">(.*?)</p>', block, re.S)
        desc = re.search(r'class="demo-desc">(.*?)</p>', block, re.S)
        demo_id = re.search(r'data-demo="(\d+)"', block)
        web_href = re.search(r'href="([^"]+)"[^>]*data-page="web"', block)
        demos.append(
            {
                "id": int(demo_id.group(1)) if demo_id else i,
                "thumb_class": thumb_class,
                "img": img,
                "badge": badge,
                "name": name.group(1).strip() if name else "",
                "type": dtype.group(1).strip() if dtype else "",
                "desc": desc.group(1).strip() if desc else "",
                "web_href": web_href.group(1) if web_href else "#",
            }
        )
    return head, demos


def extract_hero_continuum(css: str) -> dict:
    m = re.search(r"\.hero-continuum\s*\{(.*?)\}", css, re.S)
    out: dict = {}
    if not m:
        return out
    block = m.group(1)
    for key in (
        "background-color",
        "background-image",
        "background-size",
        "background-position",
        "background-repeat",
    ):
        km = re.search(rf"{re.escape(key)}\s*:\s*([^;]+);", block)
        if km:
            out[key] = km.group(1).strip()
    return out


def detect_demo_mode(app_js: str) -> dict:
    fm = re.search(r"const DEMO_FOLDERS\s*=\s*\{(.*?)\};", app_js, re.S)
    if fm:
        folders = {
            int(m.group(1)): m.group(2)
            for m in re.finditer(r"(\d+)\s*:\s*'([^']+)'", fm.group(1))
        }
        return {"type": "folders", "folders": folders}
    return {"type": "salon_ports"}


def build_brand_json(vertical: str) -> dict:
    html = (ROOT / vertical / "index.html").read_text(encoding="utf-8")
    css = (ROOT / vertical / "style.css").read_text(encoding="utf-8")
    app_js = (ROOT / vertical / "app.js").read_text(encoding="utf-8")
    head, demos = parse_demos(extract_demo_section(html))
    head["title"] = "Podívejte se, jak může vypadat právě vaše provozovna."
    if vertical == "beauty":
        head["lead"] = "Každý web připravujeme podle značky, služeb a stylu konkrétní provozovny."
        head["cta"] = None
    elif not head.get("lead"):
        head["lead"] = "Váš design vymyslíme spolu na přání!"

    root_m = re.search(r":root\s*\{(.*?)\}", css, re.S)
    vars_: dict = {}
    if root_m:
        for vm in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);", root_m.group(1)):
            vars_[vm.group(1)] = vm.group(2).strip()

    body_m = re.search(r"body\s*\{(.*?)\}", css, re.S)
    body: dict = {}
    if body_m:
        block = body_m.group(1)
        for key in (
            "background-color",
            "background-image",
            "background-size",
            "background-position",
            "background-repeat",
            "background-attachment",
            "line-height",
            "font-family",
        ):
            km = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*([^;]+);", block)
            if km:
                body[key] = km.group(1).strip()
        # plain `color:` must not match `background-color:`
        km = re.search(r"(?m)^\s*color\s*:\s*([^;]+);", block)
        if km:
            body["color"] = km.group(1).strip()
        else:
            body["color"] = "var(--text)"

    return {
        "id": vertical,
        "css_version": 100,
        "js_version": 20,
        "demo_head": head,
        "demos": demos,
        "css_vars": vars_,
        "body": body,
        "hero_continuum": extract_hero_continuum(css),
        "demo_mode": detect_demo_mode(app_js),
    }


def write_brand_configs() -> None:
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    for v in VERTICALS:
        cfg = build_brand_json(v)
        path = BRANDS_DIR / f"{v}.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"brand: {path.name} ({len(cfg['demos'])} demos)")


def build_html_template() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    html = apply_unified((ROOT / "beauty" / "index.html").read_text(encoding="utf-8"))
    html = re.sub(
        r"<title>.*?</title>",
        "<title>ULOV KLIENTY — Partner pro vaši provozovnu</title>",
        html,
        count=1,
    )
    html = re.sub(
        r'<meta name="description" content=".*?">',
        '<meta name="description" content="Partnerství pro provozovnu: web na míru, online rezervace, FLOW pro tým, Program růstu a osobní podpora. Od 499 Kč / měsíc pro nové partnery do 31. 12. 2026.">',
        html,
        count=1,
    )
    html = re.sub(r"style\.css\?v=\d+", "style.css?v={{ css_version }}", html, count=1)
    html = re.sub(r"app\.js\?v=\d+", "app.js?v={{ js_version }}", html, count=1)

    demos_tpl = """  <section class="demos-section" id="demo">
    <div class="container">
      <div class="section-head">
        <h2>{{ demo_head.title }}</h2>
        {% if demo_head.lead %}<p>{{ demo_head.lead }}</p>{% endif %}
        {% if demo_head.cta %}<p class="demos-cta">{{ demo_head.cta }}</p>{% endif %}
      </div>
      <div class="demo-grid demos-grid">
        {% for d in demos %}
        <article class="demo-card">
          <div class="demo-thumb {{ d.thumb_class }}">
            {% if d.img and d.img.src %}
            <img src="{{ d.img.src }}" alt="{{ d.img.alt }}" loading="lazy" decoding="async"{% if d.img.onerror %} onerror="{{ d.img.onerror }}"{% endif %}>
            {% endif %}
            {% if d.badge %}<span>{{ d.badge }}</span>{% endif %}
          </div>
          <div class="demo-body">
            <h3>{{ d.name }}</h3>
            <p class="demo-type">{{ d.type }}</p>
            <p class="demo-desc">{{ d.desc }}</p>
            <div class="demo-links">
              <a href="{{ d.web_href }}" data-demo="{{ d.id }}" data-page="web" target="_blank" rel="noopener">Web</a>
              <a href="#" data-demo="{{ d.id }}" data-page="rezervace" target="_blank" rel="noopener">Rezervace</a>
            </div>
          </div>
        </article>
        {% endfor %}
      </div>
    </div>
  </section>"""

    html = re.sub(
        r'<section class="demos-section" id="demo">.*?</section>',
        demos_tpl,
        html,
        count=1,
        flags=re.S,
    )
    (TEMPLATES_DIR / "index.html.j2").write_text(html, encoding="utf-8", newline="\n")
    print("template: index.html.j2")


def build_css_template() -> None:
    css = (ROOT / "beauty" / "style.css").read_text(encoding="utf-8")
    css = re.sub(
        r":root\s*\{.*?\}",
        "/* === GENERATED_ROOT === */\n:root {\n{{ root_vars }}\n}",
        css,
        count=1,
        flags=re.S,
    )
    css = re.sub(
        r"body\s*\{.*?\}",
        "body {\n{{ body_rules }}\n}",
        css,
        count=1,
        flags=re.S,
    )
    css = re.sub(
        r"\.hero-continuum\s*\{.*?\}",
        ".hero-continuum {\n{{ hero_continuum_rules }}\n}",
        css,
        count=1,
        flags=re.S,
    )
    (TEMPLATES_DIR / "style.css.j2").write_text(css, encoding="utf-8", newline="\n")
    print("template: style.css.j2")


def build_app_js_template() -> None:
    beauty_js = (ROOT / "beauty" / "app.js").read_text(encoding="utf-8")
    rest_start = beauty_js.find("document.querySelectorAll('a[data-package]')")
    if rest_start < 0:
        raise SystemExit("data-package block missing")
    shared_tail = beauty_js[rest_start:]
    tpl = """{% if demo_mode.type == "folders" %}
const DEMO_FOLDERS = {
{% for id, folder in demo_mode.folders.items() %}  {{ id }}: '{{ folder }}',
{% endfor %}};

const host = window.location.hostname;
const isLocal = host === 'localhost' || host === '127.0.0.1';
const API_BASE = isLocal
  ? `http://${host}:8000/api`
  : 'https://api.ulovklienty.cz/api';

function salonDemoUrl(demoId, page) {
  const folder = DEMO_FOLDERS[demoId];
  if (!folder) return '#';
  if (!isLocal) {
    const base = `/${folder}`;
    return page === 'web' ? `${base}/` : `${base}/rezervace.html`;
  }
  const base = `../../${folder}`;
  return page === 'web' ? `${base}/index.html` : `${base}/rezervace.html`;
}

document.querySelectorAll('[data-demo]').forEach((link) => {
  const demoId = Number(link.dataset.demo);
  const page = link.dataset.page || 'web';
  if (DEMO_FOLDERS[demoId]) {
    link.href = salonDemoUrl(demoId, page);
    link.target = '_blank';
    link.rel = 'noopener';
  }
});
{% else %}
const SALON_PORTS = { 1: 5500, 2: 5501, 3: 5502, 4: 5503, 5: 5504, 6: 5505, 7: 5506, 8: 5507 };
const DEMO_URLS = {
  1: 'https://demo1.ulovklienty.cz',
  2: 'https://demo2.ulovklienty.cz',
  3: 'https://demo3.ulovklienty.cz',
  4: 'https://demo4.ulovklienty.cz',
  5: 'https://demo5.ulovklienty.cz',
  6: 'https://demo6.ulovklienty.cz',
  7: 'https://demo7.ulovklienty.cz',
  8: 'https://demo8.ulovklienty.cz',
};

const host = window.location.hostname;
const isLocal = host === 'localhost' || host === '127.0.0.1';
const API_BASE = isLocal
  ? `http://${host}:8000/api`
  : 'https://api.ulovklienty.cz/api';

function salonDemoUrl(salonId, page) {
  if (!isLocal) {
    const base = DEMO_URLS[salonId];
    return page === 'web' ? `${base}/` : `${base}/rezervace.html`;
  }
  const port = window.location.port;
  const useSalonPorts = port === '5510';
  if (useSalonPorts) {
    const p = SALON_PORTS[salonId];
    return page === 'web'
      ? `http://${host}:${p}/`
      : `http://${host}:${p}/rezervace.html`;
  }
  const base = `../../salon${salonId}`;
  return page === 'web' ? `${base}/index.html` : `${base}/rezervace.html`;
}

document.querySelectorAll('[data-demo]').forEach((link) => {
  const salonId = Number(link.dataset.demo);
  const page = link.dataset.page || 'web';
  if (SALON_PORTS[salonId]) {
    link.href = salonDemoUrl(salonId, page);
    link.target = '_blank';
    link.rel = 'noopener';
  }
});
{% endif %}

"""
    (TEMPLATES_DIR / "app.js.j2").write_text(tpl + shared_tail, encoding="utf-8", newline="\n")
    print("template: app.js.j2")


def render_brand(cfg: dict) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    out_dir = ROOT / cfg["id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_head = dict(cfg["demo_head"])
    demo_head["title"] = "Podívejte se, jak může vypadat právě vaše provozovna."

    html = env.get_template("index.html.j2").render(
        css_version=cfg["css_version"],
        js_version=cfg["js_version"],
        demo_head=demo_head,
        demos=cfg["demos"],
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8", newline="\n")

    root_vars = "\n".join(f"  --{k}: {v};" for k, v in cfg["css_vars"].items())
    body_rules = "\n".join(f"  {k}: {v};" for k, v in cfg["body"].items())
    hero_cont = cfg.get("hero_continuum") or {
        "background-color": "var(--navy-dark)",
        "background-image": cfg["body"].get("background-image", "none"),
        "background-size": "cover",
        "background-position": "center top",
        "background-repeat": "no-repeat",
    }
    hero_continuum_rules = "\n".join(f"  {k}: {v};" for k, v in hero_cont.items())
    css = env.get_template("style.css.j2").render(
        root_vars=root_vars,
        body_rules=body_rules,
        hero_continuum_rules=hero_continuum_rules,
    )
    (out_dir / "style.css").write_text(css, encoding="utf-8", newline="\n")

    demo_mode = cfg["demo_mode"]
    if demo_mode.get("type") == "folders":
        demo_mode = {
            "type": "folders",
            "folders": {int(k): v for k, v in demo_mode["folders"].items()},
            "live_urls": {
                int(k): v for k, v in (demo_mode.get("live_urls") or {}).items()
            },
        }
    js = env.get_template("app.js.j2").render(demo_mode=demo_mode)
    (out_dir / "app.js").write_text(js, encoding="utf-8", newline="\n")
    print(f"generated {cfg['id']}/")


def generate_all() -> None:
    for name in VERTICALS:
        cfg = json.loads((BRANDS_DIR / f"{name}.json").read_text(encoding="utf-8"))
        render_brand(cfg)


def bootstrap() -> None:
    write_brand_configs()
    build_html_template()
    build_css_template()
    build_app_js_template()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate presentace vertical homepages")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Re-extract brand JSON + rebuild templates from current beauty/verticals",
    )
    args = parser.parse_args()

    if args.bootstrap or not (TEMPLATES_DIR / "index.html.j2").exists():
        bootstrap()
    if not BRANDS_DIR.exists() or not any(BRANDS_DIR.glob("*.json")):
        write_brand_configs()
    generate_all()
    print("OK — edit _shared/templates + _shared/brands, then re-run generate.py")


if __name__ == "__main__":
    main()
