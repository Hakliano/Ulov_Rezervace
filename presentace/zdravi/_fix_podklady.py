# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(__file__).with_name("podklady-pro-vas-web.html")
t = p.read_text(encoding="utf-8")
t = t.replace('class="sec sec--light"', 'class="brief-section"')
t = t.replace('class="sec sec--white"', 'class="brief-section"')
t = t.replace('class="btn btn--large"', 'class="btn btn-primary"')
t = t.replace(
    'class="btn" href="https://colorhunt.co/"',
    'class="btn btn-primary" href="https://colorhunt.co/"',
)
t = t.replace(
    'class="btn" href="https://uschovna.cz/poslat-zasilku"',
    'class="btn btn-primary" href="https://uschovna.cz/poslat-zasilku"',
)
# submit button width hint from spec
t = t.replace(
    'class="btn btn-primary" type="submit"',
    'class="btn btn-primary brief-submit" type="submit"',
)
# if submit is different order
t = t.replace(
    'type="submit" class="btn btn--primary btn--large"',
    'type="submit" class="btn btn-primary brief-submit"',
)
t = t.replace(
    'type="submit" class="btn btn-primary"',
    'type="submit" class="btn btn-primary brief-submit"',
)
p.write_text(t, encoding="utf-8")
print("ok")
