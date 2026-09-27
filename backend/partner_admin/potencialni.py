"""Potenciální klienti — izolovaný seznam, bez vazby na partnery a tarify."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import PotencialniKontakt, PotencialniSektor
from .permissions import partner_admin_perm

STRANKA = 50
PREFIX_VET = re.compile(r'^\s*VET\s*[-–—]\s*', re.IGNORECASE)
PREFIX_SALON = re.compile(r'^\s*SALON\s*[-–—]\s*', re.IGNORECASE)
JSON_NAPOVEDA = '''[
  {
    "email": "info@veterina-havirov.cz",
    "company_name": "VET - Veterinární ordinace u Nemocnice",
    "ico": "",
    "phone": "596 810 050, 603 842 823",
    "website": "",
    "address": "",
    "description": "Astronautů 5, 736 01 Havířov",
    "status": "lead"
  },
  {
    "email": "xxxx@salon.cz",
    "company_name": "SALON - Studio Krása",
    "phone": "+420 777 000 000",
    "website": "https://studio.cz"
  }
]'''


def sektor_nezarazeno():
    sektor, _ = PotencialniSektor.objects.get_or_create(
        nazev=PotencialniSektor.KOD_NEZARAZENO,
        defaults={'razeni': 90},
    )
    return sektor


def sektor_podle_nazvu(nazev: str):
    nazev = (nazev or '').strip()
    if PREFIX_VET.match(nazev):
        sektor, _ = PotencialniSektor.objects.get_or_create(nazev='Veterina', defaults={'razeni': 20})
        return sektor
    if PREFIX_SALON.match(nazev):
        sektor, _ = PotencialniSektor.objects.get_or_create(nazev='Beauty', defaults={'razeni': 10})
        return sektor
    return sektor_nezarazeno()


def _text(hodnota) -> str:
    if hodnota is None:
        return ''
    return str(hodnota).strip()


def _prvni(raw: dict, *klice) -> str:
    for klic in klice:
        if klic in raw and raw[klic] not in (None, ''):
            return _text(raw[klic])
    return ''


def normalizuj_radek(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValidationError('Položka musí být objekt.')
    jmeno = _prvni(raw, 'company_name', 'jmeno', 'name', 'nazev', 'firma')
    email = _prvni(raw, 'email', 'e-mail', 'mail').lower()
    if not jmeno or not email:
        raise ValidationError('Každý záznam musí mít jméno a e-mail.')
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError(f'Neplatný e-mail: {email}') from exc
    adresa = _prvni(raw, 'address', 'adresa')
    popis = _prvni(raw, 'description', 'popis', 'poznamka', 'note')
    if not adresa and popis:
        adresa, popis = popis, ''
    sablona = _prvni(raw, 'email_template')
    if sablona:
        popis = f'{popis}\n{sablona}'.strip() if popis else sablona
    return {
        'jmeno': jmeno[:200],
        'email': email,
        'telefon': _prvni(raw, 'phone', 'telefon', 'tel')[:200],
        'web': _prvni(raw, 'website', 'web', 'url', 'webove_stranky')[:400],
        'adresa': adresa,
        'ico': _prvni(raw, 'ico', 'ičo', 'IČO')[:20],
        'poznamka': popis,
        'sektor': sektor_podle_nazvu(jmeno),
        'stav': PotencialniKontakt.STAV_LEAD_PRED,
    }


def parse_import_json(payload) -> list:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict):
        for klic in ('items', 'data', 'contacts', 'kontakty', 'leads'):
            if isinstance(payload.get(klic), list):
                payload = payload[klic]
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        raise ValidationError('JSON musí být seznam objektů.')
    return payload


def importuj_kontakty(payload) -> dict:
    radky = parse_import_json(payload)
    existujici = set(PotencialniKontakt.objects.values_list('email', flat=True))
    vytvoreno = 0
    duplicita = 0
    neplatne = []
    for i, raw in enumerate(radky, start=1):
        try:
            data = normalizuj_radek(raw)
        except (ValidationError, TypeError, ValueError) as exc:
            neplatne.append(f'řádek {i}: {exc}')
            continue
        if data['email'] in existujici:
            duplicita += 1
            continue
        PotencialniKontakt.objects.create(**data)
        existujici.add(data['email'])
        vytvoreno += 1
    return {'vytvoreno': vytvoreno, 'duplicita': duplicita, 'neplatne': neplatne, 'celkem': len(radky)}


def export_dict(kontakt: PotencialniKontakt) -> dict:
    return {
        'email': kontakt.email,
        'company_name': kontakt.jmeno,
        'jmeno': kontakt.jmeno,
        'ico': kontakt.ico or '',
        'phone': kontakt.telefon or '',
        'website': kontakt.web or '',
        'address': kontakt.adresa or '',
        'description': kontakt.poznamka or '',
        'sektor': kontakt.sektor.nazev if kontakt.sektor_id else PotencialniSektor.KOD_NEZARAZENO,
        'status': kontakt.get_stav_display(),
    }


def filtruj_kontakty(request):
    qs = PotencialniKontakt.objects.select_related('sektor')
    q = (request.GET.get('q') or '').strip()
    stav = (request.GET.get('stav') or '').strip()
    sektor = (request.GET.get('sektor') or '').strip()
    web = (request.GET.get('web') or '').strip()
    telefon = (request.GET.get('telefon') or '').strip()
    if q:
        qs = qs.filter(Q(jmeno__icontains=q) | Q(email__icontains=q))
    if stav:
        qs = qs.filter(stav=stav)
    if sektor.isdigit():
        qs = qs.filter(sektor_id=int(sektor))
    if web == 'ano':
        qs = qs.exclude(web='')
    elif web == 'ne':
        qs = qs.filter(web='')
    if telefon == 'ano':
        qs = qs.exclude(telefon='')
    elif telefon == 'ne':
        qs = qs.filter(telefon='')
    filtry = {'q': q, 'stav': stav, 'sektor': sektor, 'web': web, 'telefon': telefon}
    return qs, filtry


def graf_stavu():
    """Podíl stavů ze všech potenciálních klientů (ne z aktuálního filtru)."""
    celkem = PotencialniKontakt.objects.count()
    pocty = dict(
        PotencialniKontakt.objects.values('stav').annotate(n=Count('id')).values_list('stav', 'n')
    )
    radky = []
    for kod, label in PotencialniKontakt.STAVY:
        pocet = pocty.get(kod, 0)
        sirka = (100.0 * pocet / celkem) if celkem else 0
        radky.append({
            'kod': kod,
            'label': label,
            'pocet': pocet,
            'procento': round(sirka, 1),
            'sirka_css': format(sirka, '.4f'),
        })
    return radky, celkem


def query_filtry(filtry, stranka_cislo=None):
    data = {k: v for k, v in filtry.items() if v}
    try:
        cislo = int(stranka_cislo or 0)
    except (TypeError, ValueError):
        cislo = 0
    if cislo > 1:
        data['stranka'] = str(cislo)
    return urlencode(data)


def cisla_stranek(aktualni, celkem, okno=2):
    """např. strana 12/33 → 1 … 10 11 12 13 14 … 33"""
    if celkem <= 1:
        return []
    strany = {1, celkem, aktualni}
    for i in range(aktualni - okno, aktualni + okno + 1):
        if 1 <= i <= celkem:
            strany.add(i)
    vysledek = []
    pred = 0
    for n in sorted(strany):
        if pred and n - pred > 1:
            vysledek.append(None)
        vysledek.append(n)
        pred = n
    return vysledek


def stranka_pro_kontakt(qs, pk):
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return 1
    if not qs.filter(pk=pk).exists():
        return 1
    return qs.filter(id__gt=pk).count() // STRANKA + 1


def _filtry_query(request, extra=None):
    params = {
        'q': request.POST.get('q') or request.GET.get('q') or '',
        'stav': request.POST.get('filtr_stav') or request.GET.get('stav') or '',
        'sektor': request.POST.get('filtr_sektor') or request.GET.get('sektor') or '',
        'web': request.POST.get('web') or request.GET.get('web') or '',
        'telefon': request.POST.get('filtr_telefon') or request.GET.get('telefon') or '',
        'stranka': request.GET.get('stranka') or '',
    }
    if extra:
        params.update(extra)
    return urlencode({k: v for k, v in params.items() if v})


def _redirect_seznam(request, extra=None, kotva=None):
    extra = extra or {}
    if kotva is None and extra.get('edit'):
        kotva = extra['edit']
    qs = _filtry_query(request, extra)
    url = reverse('partner_admin:potencialni')
    if qs:
        url = f'{url}?{qs}'
    if kotva:
        url = f'{url}#lead-{kotva}'
    return redirect(url)


@partner_admin_perm('potencialni')
def seznam(request):
    qs, filtry = filtruj_kontakty(request)
    edit_id = str(request.GET.get('edit') or '')
    page_num = request.GET.get('stranka') or 1
    if edit_id.isdigit():
        page_num = stranka_pro_kontakt(qs, edit_id)
    stranka = Paginator(qs, STRANKA).get_page(page_num)
    export_qs = query_filtry(filtry)
    list_qs = query_filtry(filtry, stranka.number)
    graf_stavy, graf_celkem = graf_stavu()
    return render(request, 'partner_admin/potencialni.html', {
        'stranka': stranka,
        'lead_filtry': filtry,
        'export_qs': export_qs,
        'list_qs': list_qs,
        'stranky': cisla_stranek(stranka.number, stranka.paginator.num_pages),
        'stavy': PotencialniKontakt.STAVY,
        'sektory': list(PotencialniSektor.objects.all()),
        'graf_stavy': graf_stavy,
        'graf_celkem': graf_celkem,
        'souhrn': {
            'celkem': qs.count(),
            'bez_webu': qs.filter(web='').count(),
            'bez_telefonu': qs.filter(telefon='').count(),
            'pred_webu': qs.filter(stav=PotencialniKontakt.STAV_LEAD_PRED).count(),
        },
        'edit_id': edit_id,
        'json_napoveda': JSON_NAPOVEDA,
    })


@partner_admin_perm('potencialni')
@require_POST
def pridat(request):
    jmeno = (request.POST.get('jmeno') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    if not jmeno or not email:
        messages.error(request, 'Jméno a e-mail jsou povinné.')
        return _redirect_seznam(request)
    if PotencialniKontakt.objects.filter(email=email).exists():
        messages.error(request, f'E-mail {email} už v seznamu je.')
        return _redirect_seznam(request)
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, f'Neplatný e-mail: {email}')
        return _redirect_seznam(request)
    sektor_id = (request.POST.get('sektor_id') or '').strip()
    sektor = PotencialniSektor.objects.filter(pk=sektor_id).first() if sektor_id.isdigit() else None
    if sektor is None:
        sektor = sektor_podle_nazvu(jmeno)
    PotencialniKontakt.objects.create(
        jmeno=jmeno,
        email=email,
        telefon=(request.POST.get('telefon') or '').strip()[:200],
        web=(request.POST.get('web_new') or '').strip()[:400],
        adresa=(request.POST.get('adresa') or '').strip(),
        ico=(request.POST.get('ico') or '').strip()[:20],
        poznamka=(request.POST.get('poznamka') or '').strip(),
        sektor=sektor,
        stav=PotencialniKontakt.STAV_LEAD_PRED,
    )
    messages.success(request, f'Přidáno: {jmeno}.')
    return _redirect_seznam(request)


@partner_admin_perm('potencialni')
@require_POST
def ulozit(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt, pk=pk)
    jmeno = (request.POST.get('jmeno') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    if not jmeno or not email:
        messages.error(request, 'Jméno a e-mail jsou povinné.')
        return _redirect_seznam(request, {'edit': str(pk)})
    if PotencialniKontakt.objects.exclude(pk=pk).filter(email=email).exists():
        messages.error(request, f'E-mail {email} už používá jiný záznam.')
        return _redirect_seznam(request, {'edit': str(pk)})
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, f'Neplatný e-mail: {email}')
        return _redirect_seznam(request, {'edit': str(pk)})
    sektor_id = (request.POST.get('sektor_id') or '').strip()
    kontakt.jmeno = jmeno
    kontakt.email = email
    kontakt.telefon = (request.POST.get('telefon') or '').strip()[:200]
    kontakt.web = (request.POST.get('web_new') or '').strip()[:400]
    kontakt.adresa = (request.POST.get('adresa') or '').strip()
    kontakt.ico = (request.POST.get('ico') or '').strip()[:20]
    kontakt.poznamka = (request.POST.get('poznamka') or '').strip()
    kontakt.sektor = PotencialniSektor.objects.filter(pk=sektor_id).first() if sektor_id.isdigit() else kontakt.sektor
    kontakt.save()
    messages.success(request, f'Uloženo: {kontakt.jmeno}.')
    return _redirect_seznam(request, kotva=pk)


@partner_admin_perm('potencialni')
@require_POST
def zmenit_stav(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt, pk=pk)
    stav = (request.POST.get('stav') or '').strip()
    platne = {kod for kod, _ in PotencialniKontakt.STAVY}
    if stav not in platne:
        return JsonResponse({'ok': False, 'detail': 'Neznámý stav.'}, status=400)
    kontakt.stav = stav
    kontakt.save(update_fields=['stav', 'upraveno'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'stav': stav, 'label': kontakt.get_stav_display()})
    messages.success(request, 'Stav uložen.')
    return _redirect_seznam(request, kotva=pk)


@partner_admin_perm('potencialni')
@require_POST
def zmenit_web(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt, pk=pk)
    kontakt.web = (request.POST.get('web_new') or '').strip()[:400]
    kontakt.save(update_fields=['web', 'upraveno'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'web': kontakt.web})
    messages.success(request, 'Web uložen.')
    return _redirect_seznam(request, kotva=pk)


@partner_admin_perm('potencialni')
@require_POST
def pridat_sektor(request):
    nazev = (request.POST.get('sektor_nazev') or '').strip()[:80]
    if not nazev:
        messages.error(request, 'Název sektoru je povinný.')
        return _redirect_seznam(request)
    sektor, created = PotencialniSektor.objects.get_or_create(
        nazev=nazev,
        defaults={'razeni': 100},
    )
    if created:
        messages.success(request, f'Sektor „{sektor.nazev}“ je v nabídce.')
    else:
        messages.info(request, f'Sektor „{sektor.nazev}“ už existuje.')
    return _redirect_seznam(request)


@partner_admin_perm('potencialni')
@require_POST
def import_json(request):
    raw = (request.POST.get('json_text') or '').strip()
    soubor = request.FILES.get('json_file')
    if soubor and not raw:
        try:
            raw = soubor.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            messages.error(request, 'Soubor musí být UTF-8 JSON.')
            return _redirect_seznam(request)
    if not raw:
        messages.error(request, 'Vlož JSON nebo nahraj soubor.')
        return _redirect_seznam(request)
    try:
        vysledek = importuj_kontakty(raw)
    except (ValidationError, json.JSONDecodeError) as exc:
        messages.error(request, f'JSON nejde načíst: {exc}')
        return _redirect_seznam(request)
    zprava = (
        f'Import: {vysledek["vytvoreno"]} nových z {vysledek["celkem"]}. '
        f'Přeskočeno duplicit: {vysledek["duplicita"]}.'
    )
    if vysledek['neplatne']:
        zprava += ' Chyby: ' + '; '.join(vysledek['neplatne'][:8])
        messages.warning(request, zprava)
    else:
        messages.success(request, zprava)
    return _redirect_seznam(request)


@partner_admin_perm('potencialni')
def export_json(request):
    qs, _filtry = filtruj_kontakty(request)
    data = [export_dict(k) for k in qs.iterator()]
    odpoved = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8',
    )
    odpoved['Content-Disposition'] = 'attachment; filename="potencialni-klienti.json"'
    return odpoved
