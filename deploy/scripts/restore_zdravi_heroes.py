"""Restore missing hero_image for zdravi demos 9–11 (files already on Bunny)."""
from salons.models import Salon

FIXES = {
    9: 'https://haklweb.b-cdn.net/webs/salon-9/hero/6f62a85e65d240539a2da8d2c68c79ed.webp',
    10: 'https://haklweb.b-cdn.net/webs/salon-10/hero/13cc0049decf40628112240c86ab8fd7.webp',
    11: 'https://haklweb.b-cdn.net/webs/salon-11/hero/a8b4349199cb45d9b91413d48c18dcc0.webp',
}

for pk, url in FIXES.items():
    salon = Salon.objects.get(pk=pk)
    before = salon.hero_image or ''
    if before:
        print(f'KEEP {pk} {salon.name}: already set')
        continue
    salon.hero_image = url
    salon.save(update_fields=['hero_image'])
    print(f'RESTORED {pk} {salon.name}')
