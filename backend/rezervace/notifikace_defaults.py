import uuid
from datetime import timedelta

from django.utils import timezone


MAX_NOTIFIKACE = 7
MANUAL_OFFSET = 'manual'
MANUAL_TYP_NOSHOW = 'noshow'
MANUAL_TYP_PLATBA = 'platba'
MANUAL_TYP_STORNO = 'storno'
MANUAL_TYP_POTVRZENI = 'potvrzeni'
MANUAL_TYP_ZALOHA_OK = 'zaloha_ok'

DEFAULT_PREDMET_PRED = 'Připomínka rezervace – {{ salon.name }}'
DEFAULT_PREDMET_PO = 'Děkujeme za návštěvu – {{ salon.name }}'
DEFAULT_PREDMET_RECENZE = 'Jak se vám u nás líbilo? – {{ salon.name }}'
DEFAULT_PREDMET_NO_SHOW = 'Neuskutečněná rezervace – {{ salon.name }}'
DEFAULT_PREDMET_PLATBA = 'Žádost o úhradu – {{ salon.name }}'
DEFAULT_PREDMET_STORNO = 'Omlouváme se – zrušení rezervace ({{ salon.name }})'
DEFAULT_PREDMET_POTVRZENI = 'Potvrzení rezervace – {{ salon.name }}'
DEFAULT_PREDMET_ZALOHA_OK = 'Záloha přijata – rezervace potvrzena ({{ salon.name }})'

DEFAULT_TEXT_PRED = """Dobrý den {{ jmeno }},

připomínáme vaši rezervaci v salonu {{ salon.name }}.

Termín: {{ termin }}
Služby: {{ sluzby }}
{% if zamestnanec %}Pracovník: {{ zamestnanec }}{% endif %}

Adresa: {{ adresa }}
Telefon: {{ telefon }}

Těšíme se na vás!
{{ salon.name }}"""

DEFAULT_TEXT_PO = """Dobrý den {{ jmeno }},

děkujeme, že jste navštívili {{ salon.name }}!

Těšíme se na vás příště!
{{ salon.name }}"""

DEFAULT_TEXT_RECENZE = """Dobrý den {{ jmeno }},

děkujeme, že jste navštívili {{ salon.name }}!

Doufáme, že jste s naší péčí spokojeni. Budeme moc rádi za krátkou recenzi — stačí kliknout zde:

{{ recenze_url }}

Těšíme se na vás příště!
{{ salon.name }}"""

DEFAULT_TEXT_NO_SHOW = """Dobrý den {{ jmeno }},

zaznamenali jsme, že jste se nedostavili na rezervaci v salonu {{ salon.name }}.

Termín: {{ termin }}
Služby: {{ sluzby }}
{% if zamestnanec %}Pracovník: {{ zamestnanec }}{% endif %}

Prosíme o kontakt pro případné přeobjednání: {{ telefon }}

Důležité upozornění: Při dvou neuskutečněných rezervacích v salonu {{ salon.name }} bude váš e-mail veden jako problematický. Po třetí neuskutečněné rezervaci v tomto salonu bude váš účet automaticky zablokován pro online rezervace v salonu {{ salon.name }}.

Děkujeme za pochopení.
{{ salon.name }}"""

DEFAULT_TEXT_PLATBA = """Dobrý den {{ jmeno }},

děkujeme za návštěvu salonu {{ salon.name }}.

Prosíme o úhradu za služby: {{ sluzby }}

Termín: {{ termin }}
Částka k úhradě: {{ castka }} Kč
Číslo účtu: {{ ucet }}
Variabilní symbol: {{ variabilni_symbol }}

Platbu můžete provést naskenováním QR kódu v příloze e-mailu, nebo bankovním převodem dle údajů výše.

Děkujeme.
{{ salon.name }}"""

DEFAULT_TEXT_STORNO = """Dobrý den {{ jmeno }},

velice se omlouváme, ale vaši rezervaci v salonu {{ salon.name }} bohužel musíme zrušit.

Původní termín: {{ termin }}
Služby: {{ sluzby }}
{% if zamestnanec %}Pracovník: {{ zamestnanec }}{% endif %}
{% if duvod %}
Důvod zrušení: {{ duvod }}
{% endif %}
Je nám líto za komplikace, které vám tím vznikají. Rádi vám pomůžeme vybrat jiný termín — ozvěte se nám prosím na {{ telefon }}{% if adresa %}, nebo nás navštivte na adrese {{ adresa }}{% endif %}.

Děkujeme za pochopení.
S pozdravem
{{ salon.name }}"""

DEFAULT_TEXT_POTVRZENI = """Dobrý den {{ jmeno }},

vaše rezervace v salonu {{ salon.name }} je potvrzena.

Termín: {{ termin }}
Služby: {{ sluzby }}
{% if zamestnanec %}Pracovník: {{ zamestnanec }}{% endif %}

Adresa: {{ adresa }}
Telefon: {{ telefon }}

{% if rizikova %}
━━━━━━━━━━━━━━━━━━━━━━━━
DŮLEŽITÉ — možná záloha
Vaše rezervace je na službu, u které obsluha často vyžaduje zálohovou platbu.
Prosím vyčkejte, zda vám obsluha vypíše zálohovou platbu (e-mail s QR kódem).
Pokud zálohu nevyžaduje, je vše v pořádku a tato rezervace platí.
Pokud zálohu vyžádá, uhradíte ji podle pokynů v daném e-mailu (typicky nejpozději několik hodin před službou).
Dotazy řešte telefonicky: {{ telefon }}
━━━━━━━━━━━━━━━━━━━━━━━━
{% endif %}

Zrušení rezervace: {{ storno_url }}

Těšíme se na vás!
{{ salon.name }}"""

DEFAULT_TEXT_ZALOHA_OK = """Dobrý den {{ jmeno }},

děkujeme — zálohovou platbu jsme zaregistrovali.

Vaše rezervace v salonu {{ salon.name }} zůstává potvrzena.

Termín: {{ termin }}
Služby: {{ sluzby }}
{% if zamestnanec %}Pracovník: {{ zamestnanec }}{% endif %}
{% if castka %}Přijatá záloha: {{ castka }} Kč{% endif %}

Těšíme se na vaši návštěvu!
{{ salon.name }}"""

NOTIFIKACE_TAGY = [
    {'tag': '{{ jmeno }}', 'popis': 'Jméno zákazníka', 'priklad': 'Petra Nováková'},
    {'tag': '{{ salon.name }}', 'popis': 'Název salonu', 'priklad': 'Salon Elegance'},
    {'tag': '{{ termin }}', 'popis': 'Datum a čas rezervace', 'priklad': '15. 3. 2026 v 10:00'},
    {'tag': '{{ termin_datum }}', 'popis': 'Jen datum rezervace', 'priklad': '15. 3. 2026'},
    {'tag': '{{ termin_cas }}', 'popis': 'Jen čas rezervace', 'priklad': '10:00'},
    {'tag': '{{ sluzby }}', 'popis': 'Objednané služby', 'priklad': 'Střih, barvení'},
    {'tag': '{{ zamestnanec }}', 'popis': 'Jméno kadeřnice / pracovníka', 'priklad': 'Jana'},
    {'tag': '{{ adresa }}', 'popis': 'Adresa salonu', 'priklad': 'Hlavní 12, Praha'},
    {'tag': '{{ telefon }}', 'popis': 'Telefon salonu', 'priklad': '+420 123 456 789'},
    {'tag': '{{ storno_url }}', 'popis': 'Odkaz pro zrušení rezervace', 'priklad': 'https://…/rezervace.html?storno=…'},
    {'tag': '{{ recenze_url }}', 'popis': 'Odkaz na recenze (nastavíte v Nastavení)', 'priklad': 'https://g.page/…/review'},
    {'tag': '{{ castka }}', 'popis': 'Částka k úhradě (platba / záloha)', 'priklad': '850'},
    {'tag': '{{ ucet }}', 'popis': 'Číslo účtu (platba)', 'priklad': '123456789/0100'},
    {'tag': '{{ variabilni_symbol }}', 'popis': 'Variabilní symbol (platba)', 'priklad': '20260705'},
    {'tag': '{{ kdo }}', 'popis': 'Kdo rezervaci zrušil (salon / zákazník)', 'priklad': 'salon'},
    {'tag': '{{ duvod }}', 'popis': 'Důvod storna (např. dovolená / nezaplacená záloha)', 'priklad': 'Nezaplacená záloha'},
    {'tag': '{% if rizikova %}…{% endif %}', 'popis': 'Blok jen u rizikové služby (záloha možná)', 'priklad': 'viz výchozí potvrzení'},
]

PLACEHOLDER_HINT = (
    'Do textu e-mailu vkládejte tagy z tabulky níže — systém je při odeslání nahradí skutečnými údaji.'
)

VychoZI_NOTIFIKACE = [
    {'offset': '+24', 'aktivni': True, 'manual': False, 'predmet': DEFAULT_PREDMET_PRED, 'text': DEFAULT_TEXT_PRED},
    {'offset': '-2', 'aktivni': True, 'manual': False, 'predmet': DEFAULT_PREDMET_RECENZE, 'text': DEFAULT_TEXT_RECENZE},
    {
        'offset': MANUAL_OFFSET, 'aktivni': False, 'manual': True,
        'manual_typ': MANUAL_TYP_NOSHOW,
        'predmet': DEFAULT_PREDMET_NO_SHOW, 'text': DEFAULT_TEXT_NO_SHOW,
    },
    {
        'offset': MANUAL_OFFSET, 'aktivni': True, 'manual': True,
        'manual_typ': MANUAL_TYP_PLATBA,
        'predmet': DEFAULT_PREDMET_PLATBA, 'text': DEFAULT_TEXT_PLATBA,
    },
    {
        'offset': MANUAL_OFFSET, 'aktivni': True, 'manual': True,
        'manual_typ': MANUAL_TYP_STORNO,
        'predmet': DEFAULT_PREDMET_STORNO, 'text': DEFAULT_TEXT_STORNO,
    },
    {
        'offset': MANUAL_OFFSET, 'aktivni': True, 'manual': True,
        'manual_typ': MANUAL_TYP_POTVRZENI,
        'predmet': DEFAULT_PREDMET_POTVRZENI, 'text': DEFAULT_TEXT_POTVRZENI,
    },
    {
        'offset': MANUAL_OFFSET, 'aktivni': True, 'manual': True,
        'manual_typ': MANUAL_TYP_ZALOHA_OK,
        'predmet': DEFAULT_PREDMET_ZALOHA_OK, 'text': DEFAULT_TEXT_ZALOHA_OK,
    },
]


def je_manualni(notifikace):
    return bool(notifikace.get('manual')) or str(notifikace.get('offset', '')) == MANUAL_OFFSET


def nova_notifikace(offset='+24', aktivni=False, predmet=None, text=None, manual=False, manual_typ=None):
    if manual or offset == MANUAL_OFFSET:
        mt = manual_typ or MANUAL_TYP_NOSHOW
        defaults = {
            MANUAL_TYP_NOSHOW: (DEFAULT_PREDMET_NO_SHOW, DEFAULT_TEXT_NO_SHOW),
            MANUAL_TYP_PLATBA: (DEFAULT_PREDMET_PLATBA, DEFAULT_TEXT_PLATBA),
            MANUAL_TYP_STORNO: (DEFAULT_PREDMET_STORNO, DEFAULT_TEXT_STORNO),
            MANUAL_TYP_POTVRZENI: (DEFAULT_PREDMET_POTVRZENI, DEFAULT_TEXT_POTVRZENI),
            MANUAL_TYP_ZALOHA_OK: (DEFAULT_PREDMET_ZALOHA_OK, DEFAULT_TEXT_ZALOHA_OK),
        }
        dp, dt = defaults.get(mt, defaults[MANUAL_TYP_NOSHOW])
        return {
            'id': str(uuid.uuid4()),
            'offset': MANUAL_OFFSET,
            'manual': True,
            'manual_typ': mt,
            'aktivni': aktivni,
            'predmet': predmet or dp,
            'text': text or dt,
        }
    pred = offset.startswith('-')
    if predmet is None and text is None and offset == '-2':
        predmet = DEFAULT_PREDMET_RECENZE
        text = DEFAULT_TEXT_RECENZE
    return {
        'id': str(uuid.uuid4()),
        'offset': offset,
        'manual': False,
        'aktivni': aktivni,
        'predmet': predmet or (DEFAULT_PREDMET_PO if pred else DEFAULT_PREDMET_PRED),
        'text': text or (DEFAULT_TEXT_PO if pred else DEFAULT_TEXT_PRED),
    }


def vychozi_notifikace():
    return [
        nova_notifikace(
            item['offset'], aktivni=item['aktivni'], manual=item.get('manual', False),
            manual_typ=item.get('manual_typ'),
            predmet=item['predmet'], text=item['text'],
        )
        for item in VychoZI_NOTIFIKACE
    ]


def _defaulty_pro_offset(offset, manual=False):
    if manual or offset == MANUAL_OFFSET:
        return DEFAULT_PREDMET_NO_SHOW, DEFAULT_TEXT_NO_SHOW
    if offset == '-2':
        return DEFAULT_PREDMET_RECENZE, DEFAULT_TEXT_RECENZE
    if offset.startswith('-'):
        return DEFAULT_PREDMET_PO, DEFAULT_TEXT_PO
    return DEFAULT_PREDMET_PRED, DEFAULT_TEXT_PRED


def normalizuj_notifikace(raw):
    if not raw:
        return vychozi_notifikace()

    result = []
    for item in raw[:MAX_NOTIFIKACE]:
        if not isinstance(item, dict):
            continue
        manual = bool(item.get('manual')) or str(item.get('offset', '')).strip() == MANUAL_OFFSET
        if manual:
            offset = MANUAL_OFFSET
        else:
            offset = str(item.get('offset', '+24')).strip()
            if not offset.startswith(('+', '-')):
                try:
                    h = int(offset)
                    offset = f'+{h}' if h >= 0 else str(h)
                except (TypeError, ValueError):
                    offset = '+24'
        default_predmet, default_text = _defaulty_pro_offset(offset, manual=manual)
        mt = item.get('manual_typ')
        if manual and not mt:
            mt = MANUAL_TYP_NOSHOW
        result.append({
            'id': str(item.get('id') or uuid.uuid4()),
            'offset': offset,
            'manual': manual,
            'manual_typ': mt,
            'aktivni': bool(item.get('aktivni', False)),
            'predmet': item.get('predmet') or default_predmet,
            'text': item.get('text') or default_text,
        })

    if not result:
        return vychozi_notifikace()
    return result


def _je_duplicitni_pripominka(notif):
    if je_manualni(notif):
        return False
    predmet = (notif.get('predmet') or '').strip()
    text = (notif.get('text') or '').strip()
    offset = str(notif.get('offset', '')).strip()
    if predmet == DEFAULT_PREDMET_PRED:
        return True
    if text == DEFAULT_TEXT_PRED.strip():
        return True
    if 'připomínáme vaši rezervaci' in text.lower():
        return True
    return offset.startswith('+') and predmet != DEFAULT_PREDMET_RECENZE


def _vynut_druhou_notifikaci(result):
    """Druhá notifikace = poděkování a recenze (-2 h). Opraví stará data s duplicitní připomínkou."""
    if len(result) < 2:
        return result
    druha = result[1]
    if je_manualni(druha):
        return result
    duplicitni = (
        _je_duplicitni_pripominka(druha)
        or druha.get('text') == result[0].get('text')
        or druha.get('predmet') == result[0].get('predmet')
    )
    if not duplicitni:
        return result
    vzor = vychozi_notifikace()[1]
    aktivni = druha.get('aktivni', vzor['aktivni'])
    druha.update({
        'offset': '-2',
        'manual': False,
        'aktivni': aktivni,
        'predmet': vzor['predmet'],
        'text': vzor['text'],
    })
    return result


def _vynut_manualni_sloty(result):
    vychozi = vychozi_notifikace()
    sloty = [
        (2, MANUAL_TYP_NOSHOW, DEFAULT_PREDMET_NO_SHOW),
        (3, MANUAL_TYP_PLATBA, DEFAULT_PREDMET_PLATBA),
        (4, MANUAL_TYP_STORNO, DEFAULT_PREDMET_STORNO),
        (5, MANUAL_TYP_POTVRZENI, DEFAULT_PREDMET_POTVRZENI),
        (6, MANUAL_TYP_ZALOHA_OK, DEFAULT_PREDMET_ZALOHA_OK),
    ]
    for idx, typ, default_predmet in sloty:
        if len(result) <= idx:
            continue
        n = result[idx]
        n['manual'] = True
        n['offset'] = MANUAL_OFFSET
        n['manual_typ'] = typ
        if not n.get('predmet') or n.get('predmet') in (
            DEFAULT_PREDMET_PRED, DEFAULT_PREDMET_PO, DEFAULT_PREDMET_RECENZE, '',
        ):
            n['predmet'] = vychozi[idx]['predmet'] if idx < len(vychozi) else default_predmet
        if typ == MANUAL_TYP_NOSHOW and idx < len(vychozi):
            if not n.get('text') or 'připomínáme vaši rezervaci' in (n.get('text') or ''):
                n['text'] = vychozi[idx]['text']
        if typ == MANUAL_TYP_PLATBA and idx < len(vychozi):
            if not n.get('text') or 'QR kód' not in (n.get('text') or ''):
                if 'castka' not in (n.get('text') or ''):
                    n['text'] = vychozi[idx]['text']
        if typ == MANUAL_TYP_STORNO and idx < len(vychozi):
            if not n.get('text') or 'připomínáme vaši rezervaci' in (n.get('text') or ''):
                n['text'] = vychozi[idx]['text']
            if not n.get('predmet') or n.get('predmet') == DEFAULT_PREDMET_PRED:
                n['predmet'] = DEFAULT_PREDMET_STORNO
        if typ == MANUAL_TYP_POTVRZENI and idx < len(vychozi):
            if not n.get('text') or 'připomínáme vaši rezervaci' in (n.get('text') or ''):
                n['text'] = vychozi[idx]['text']
            if not n.get('predmet') or n.get('predmet') == DEFAULT_PREDMET_PRED:
                n['predmet'] = DEFAULT_PREDMET_POTVRZENI
        if typ == MANUAL_TYP_ZALOHA_OK and idx < len(vychozi):
            if not n.get('text') or 'připomínáme vaši rezervaci' in (n.get('text') or ''):
                n['text'] = vychozi[idx]['text']
            if not n.get('predmet') or n.get('predmet') == DEFAULT_PREDMET_PRED:
                n['predmet'] = DEFAULT_PREDMET_ZALOHA_OK
    return result


def dopln_na_notifikace(notifikace):
    result = normalizuj_notifikace(notifikace)
    vychozi = vychozi_notifikace()
    while len(result) < MAX_NOTIFIKACE:
        idx = len(result)
        vzor = vychozi[idx] if idx < len(vychozi) else nova_notifikace('+24', aktivni=False)
        result.append({
            'id': str(uuid.uuid4()),
            'offset': vzor['offset'],
            'manual': vzor.get('manual', False),
            'manual_typ': vzor.get('manual_typ'),
            'aktivni': vzor['aktivni'],
            'predmet': vzor['predmet'],
            'text': vzor['text'],
        })
    result = result[:MAX_NOTIFIKACE]
    result = _vynut_druhou_notifikaci(result)
    return _vynut_manualni_sloty(result)


def dopln_na_tri(notifikace):
    """Zpětná kompatibilita."""
    return dopln_na_notifikace(notifikace)


def get_manual_notifikace(notifikace_list, typ=MANUAL_TYP_NOSHOW):
    items = dopln_na_notifikace(notifikace_list)
    for i, notif in enumerate(items):
        if not je_manualni(notif):
            continue
        mt = notif.get('manual_typ')
        if not mt:
            if i == 2:
                mt = MANUAL_TYP_NOSHOW
            elif i == 3:
                mt = MANUAL_TYP_PLATBA
            elif i == 4:
                mt = MANUAL_TYP_STORNO
            elif i == 5:
                mt = MANUAL_TYP_POTVRZENI
            elif i == 6:
                mt = MANUAL_TYP_ZALOHA_OK
            else:
                mt = MANUAL_TYP_NOSHOW
        if mt == typ:
            return notif
    return None


def parse_offset(offset_str):
    s = str(offset_str).strip()
    if s == MANUAL_OFFSET:
        raise ValueError('manual')
    if s.startswith('+'):
        return int(s[1:])
    if s.startswith('-'):
        return -int(s[1:])
    return int(s)


def cas_odeslani(rezervace, offset_parsed):
    if offset_parsed > 0:
        return rezervace.zacatek - timedelta(hours=offset_parsed)
    return rezervace.konec + timedelta(hours=abs(offset_parsed))


def je_v_okne(cilovy_cas, now=None):
    now = now or timezone.now()
    return cilovy_cas <= now <= cilovy_cas + timedelta(hours=1)


def muze_odeslat_notifikaci(rezervace, offset_parsed):
    storno = ('zakaznik_storno', 'salon_storno')
    if rezervace.stav in storno:
        return False
    if offset_parsed > 0:
        return rezervace.stav == 'potvrzeno' and rezervace.zacatek > timezone.now()
    return rezervace.stav in ('ceka', 'potvrzeno', 'dokonceno', 'no_show')


def rezervace_je_rizikova(rezervace):
    """True pokud obsahuje aspoň jednu službu s rizikovy=True."""
    for p in rezervace.polozky.select_related('sluzba').all():
        if p.sluzba_id and getattr(p.sluzba, 'rizikovy', False):
            return True
    return False
