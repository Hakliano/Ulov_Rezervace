"""Reputace e-mailu — pouze v rámci jednoho salonu (GDPR)."""

from django.db.models import Q

from rezervace.models import NoShowZaznam, Zakaznik
from rezervace.services.gdpr import email_hash

PROBLEMATICKY_OD = 2
BLOKOVAN_OD = 3


def normalize_email(email):
    return (email or '').strip().lower()


def _najdi_zakaznik(salon_id, email):
    e = normalize_email(email)
    if not e or not salon_id:
        return None
    h = email_hash(e)
    zak = Zakaznik.objects.filter(salon_id=salon_id, email__iexact=e).first()
    if zak:
        return zak
    if h:
        return Zakaznik.objects.filter(salon_id=salon_id, email_hash=h).first()
    return None


def _noshow_filter(email, salon_id):
    e = normalize_email(email)
    h = email_hash(e) if e else ''
    if not salon_id or (not e and not h):
        return NoShowZaznam.objects.none()
    q = Q(salon_id=salon_id)
    if e and h:
        return NoShowZaznam.objects.filter(q & (Q(email__iexact=e) | Q(email_hash=h)))
    if e:
        return NoShowZaznam.objects.filter(q, email__iexact=e)
    return NoShowZaznam.objects.filter(q, email_hash=h)


def pocet_noshow_v_salonu(email, salon_id):
    return _noshow_filter(email, salon_id).count()


def je_blokovan_v_salonu(email, salon_id):
    zak = _najdi_zakaznik(salon_id, email)
    return bool(zak and zak.blokovan)


def blokovat_v_salonu(email, salon_id):
    """Zablokuje e-mail v daném salonu (vytvoří zákazníka pokud neexistuje)."""
    e = normalize_email(email)
    if not e:
        raise ValueError('E-mail je povinný.')
    from salons.models import Salon
    salon = Salon.objects.get(pk=salon_id)
    h = email_hash(e)
    zak = _najdi_zakaznik(salon_id, e)
    if not zak:
        zak = Zakaznik.objects.create(
            salon=salon,
            email=e,
            email_hash=h,
            nick=e.split('@')[0],
            gdpr_souhlas=True,
        )
    elif not zak.email_hash:
        zak.email_hash = h
        zak.save(update_fields=['email_hash'])
    zak.blokovan = True
    zak.save(update_fields=['blokovan'])
    return zak


def odblokovat_v_salonu(email, salon_id):
    """Odblokuje e-mail v daném salonu (počet NO-show zůstává)."""
    zak = _najdi_zakaznik(salon_id, email)
    if not zak:
        raise ValueError('V tomto salonu není zákaznický účet s tímto e-mailem.')
    if zak.blokovan:
        zak.blokovan = False
        zak.save(update_fields=['blokovan'])
    return zak


def aktualizuj_po_noshow(email, salon_id):
    """Po NO-show: problematický od 2× a auto-blokace od 3× — jen v daném salonu."""
    e = normalize_email(email)
    if not e or not salon_id:
        return {
            'pocet': 0,
            'problematicky': False,
            'blokovan_v_salonu': False,
        }

    pocet = pocet_noshow_v_salonu(e, salon_id)
    blokovan_v_salonu = False

    if pocet >= BLOKOVAN_OD:
        blokovat_v_salonu(e, salon_id)
        blokovan_v_salonu = True

    return {
        'pocet': pocet,
        'problematicky': pocet >= PROBLEMATICKY_OD,
        'blokovan_v_salonu': blokovan_v_salonu or je_blokovan_v_salonu(e, salon_id),
        'limit_problematicky': PROBLEMATICKY_OD,
        'limit_blokovani': BLOKOVAN_OD,
    }


def hledat_hrisniky(q='', page=1, page_size=25, salon_id=None):
    from collections import defaultdict

    if not salon_id:
        return {
            'vysledky': [],
            'stranka': 1,
            'celkem_stranek': 1,
            'celkem': 0,
            'pravidlo_problematicky': PROBLEMATICKY_OD,
            'pravidlo_blokovani': BLOKOVAN_OD,
        }

    qs = NoShowZaznam.objects.filter(salon_id=salon_id)
    if q:
        qs = qs.filter(Q(jmeno__icontains=q) | Q(email__icontains=q))

    by_key = defaultdict(lambda: {
        'email': '', 'jmeno': '', 'pocet': 0, 'posledni': None, 'hash': '',
    })
    for z in qs.order_by('-vytvoreno'):
        key = normalize_email(z.email) or z.email_hash or f'row-{z.id}'
        rec = by_key[key]
        if z.email:
            rec['email'] = z.email
        rec['hash'] = z.email_hash or rec['hash']
        rec['pocet'] += 1
        if not rec['jmeno']:
            rec['jmeno'] = z.jmeno
        if rec['posledni'] is None:
            rec['posledni'] = z.vytvoreno

    hrisnici = list(by_key.values())
    hrisnici.sort(key=lambda x: (-x['pocet'], -(x['posledni'].timestamp() if x['posledni'] else 0)))

    total = len(hrisnici)
    page = max(1, page)
    start = (page - 1) * page_size
    page_items = hrisnici[start:start + page_size]

    vysledky = []
    for item in page_items:
        e = normalize_email(item['email'])
        pocet = item['pocet']
        blokovan = je_blokovan_v_salonu(e, salon_id) if e else False
        if not blokovan and item['hash']:
            blokovan = Zakaznik.objects.filter(
                salon_id=salon_id, email_hash=item['hash'], blokovan=True,
            ).exists()
        vysledky.append({
            'email': item['email'],
            'jmeno': item['jmeno'],
            'pocet_no_show': pocet,
            'problematicky': pocet >= PROBLEMATICKY_OD,
            'kriticky': pocet >= BLOKOVAN_OD,
            'blokovan_v_salonu': blokovan,
            'posledni': item['posledni'],
        })

    celkem_stranek = max(1, (total + page_size - 1) // page_size) if total else 1
    return {
        'vysledky': vysledky,
        'stranka': page,
        'celkem_stranek': celkem_stranek,
        'celkem': total,
        'pravidlo_problematicky': PROBLEMATICKY_OD,
        'pravidlo_blokovani': BLOKOVAN_OD,
    }
