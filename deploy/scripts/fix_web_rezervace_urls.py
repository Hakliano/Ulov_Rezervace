"""Oprava web_rezervace_url na LIVE — pryč localhost / prázdno."""
from rezervace.models import RezervacniNastaveni

LIVE_URLS = {
    1: 'https://demo1.ulovklienty.cz/rezervace.html',
    2: 'https://demo2.ulovklienty.cz/rezervace.html',
    3: 'https://demo3.ulovklienty.cz/rezervace.html',
    4: 'https://demo4.ulovklienty.cz/rezervace.html',
    5: 'https://demo5.ulovklienty.cz/rezervace.html',
    6: 'https://demo6.ulovklienty.cz/rezervace.html',
    7: 'https://demo7.ulovklienty.cz/rezervace.html',
    8: 'https://demo8.ulovklienty.cz/rezervace.html',
    9: 'https://www.ulovklienty.cz/zdravi-fyzio/rezervace.html',
    10: 'https://www.ulovklienty.cz/zdravi-veterina/rezervace.html',
    11: 'https://www.ulovklienty.cz/zdravi-dental/rezervace.html',
    12: 'https://www.ulovklienty.cz/remesla-instalater/rezervace.html',
    13: 'https://www.ulovklienty.cz/remesla-elektrikar/rezervace.html',
    14: 'https://www.ulovklienty.cz/remesla-rekonstrukce/rezervace.html',
    15: 'https://www.ulovklienty.cz/provoz-autoservis/rezervace.html',
    16: 'https://www.ulovklienty.cz/provoz-pujcovna/rezervace.html',
    17: 'https://www.ulovklienty.cz/provoz-studio/rezervace.html',
}

fixed = 0
for n in RezervacniNastaveni.objects.select_related('salon').order_by('salon_id'):
    u = (n.web_rezervace_url or '').strip()
    want = LIVE_URLS.get(n.salon_id)
    bad = (not u) or ('localhost' in u.lower()) or u.startswith('http://127.')
    print(f'{n.salon_id:2d} {n.salon.name[:24]:24s} bad={bad} {u!r}')
    if want and bad:
        n.web_rezervace_url = want
        n.save(update_fields=['web_rezervace_url'])
        fixed += 1
        print(f'   FIXED -> {want}')
print(f'DONE fixed={fixed}')
