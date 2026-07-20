# -*- coding: utf-8 -*-
from pathlib import Path

body = Path(__file__).with_name("podklady-body.html").read_text(encoding="utf-8")

replacements = [
    ('class="hero-bubble brief-hero"', 'class="brief-hero"'),
    ('<div class="hero-bubble__bg" aria-hidden="true"></div>\n      ', ""),
    ('class="container hero-bubble__grid"', 'class="container"'),
    ('class="hero-bubble__copy"', 'class="brief-hero-copy"'),
    ('class="hero-bubble__title"', ""),
    ('class="hero-bubble__lead"', 'class="brief-lead"'),
    ('class="hero-bubble__cta"', 'class="brief-hero-actions"'),
    ('class="btn btn--ghost"', 'class="btn btn-secondary"'),
    ('class="btn btn--small"', 'class="btn btn-secondary btn-sm"'),
    ('class="btn btn--primary btn--large"', 'class="btn btn-primary"'),
    ('class="btn btn--primary"', 'class="btn btn-primary"'),
    ('class="sec sec--light section"', 'class="brief-section"'),
    ('class="sec sec--alt section"', 'class="brief-section brief-section--alt"'),
    ('class="sec__title"', 'class="brief-h2"'),
    ('class="sec__intro"', 'class="brief-intro"'),
    ('class="contact-card"', 'class="brief-card"'),
    ('href="../index.html"', 'href="index.html"'),
    ('href="../"', 'href="index.html"'),
]
for a, b in replacements:
    body = body.replace(a, b)

body = body.replace("<h1 >", "<h1>").replace('<h1 class="">', "<h1>")

# Local thank-you page for presentace preview; production can use absolute URL
body = body  # redirect handled in JS

head = """<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Podklady pro váš web — vyplnění pro klienta | ULOV KLIENTY</title>
  <meta name="description" content="Interní stránka pro doplnění podkladů k tvorbě webu. Vyplňte texty, barvy, doménu a další informace.">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="https://ulovklienty.cz/podklady-pro-vas-web/">
  <link rel="icon" type="image/png" href="https://haklweb.b-cdn.net/ULOV_KLIENTA/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v=34">
</head>
<body>
  <header class="site-header">
    <div class="container header-inner">
      <a href="index.html" class="brand-lockup">
        <img src="https://haklweb.b-cdn.net/ULOV_KLIENTA/logo_080226.webp" alt="ULOV KLIENTY" width="180" height="180">
        <span>ULOV KLIENTY</span>
      </a>
      <div class="header-actions">
        <a href="index.html#ceny" class="nav-link">Balíčky</a>
        <a href="podklady-pro-vas-web.html" class="nav-link">Podklady</a>
        <a href="index.html#poptavka" class="nav-cta">Chci nezávazný návrh</a>
      </div>
    </div>
  </header>

"""

foot = """
  <footer class="site-footer">
    <div class="container site-footer-inner">
      <a class="site-footer-brand" href="https://www.ulovklienty.cz" target="_blank" rel="noopener noreferrer">
        <img src="https://haklweb.b-cdn.net/ULOV_KLIENTA/logo_080226.webp" alt="" width="40" height="40" loading="lazy">
        <span>ULOV KLIENTY</span>
      </a>
      <p class="site-footer-legal">© 2026 ULOV KLIENTY</p>
      <p class="site-footer-meta">
        Vytvořeno Jiřím Haklem ·
        <a href="https://www.ulovklienty.cz" target="_blank" rel="noopener noreferrer">ulovklienty.cz</a>
      </p>
    </div>
  </footer>
  <script src="brief-klient-form.js" defer></script>
</body>
</html>
"""

out_path = Path(__file__).with_name("podklady-pro-vas-web.html")
out_path.write_text(head + body + foot, encoding="utf-8")
print("written", out_path, "chars", len(head + body + foot))
