import csv
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, When
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.urls import reverse

from partner_hub.models import create_partner_session
from rezervace.models import Rezervace, SalonAuditLog, Zamestnanec
from salons.models import Salon

from .forms import (
    BlokaceForm,
    ExtraFakturaForm,
    FakturaEditForm,
    FakturaPlatbyForm,
    HromadnyEmailForm,
    KeyAccountManagerForm,
    NovyPartnerForm,
    PartnerNastaveniForm,
    PartnerTarifForm,
    PlatbaForm,
    ResetHeslaForm,
    UlovCisloUctuForm,
    UpozorneniForm,
    VydajForm,
)
from .evidence import data_souhrnu, parse_datum, seznam_faktur, vychozi_obdobi
from .extra_faktury import oznacit_extra_uhrazeno, vytvor_extra_fakturu
from .loga import logo_url_pro_tarif, tarif_loga_pro_sablonu
from .models import (
    MODUL_MATERIALNIK,
    ExtraFaktura,
    HromadnyEmail,
    KeyAccountManager,
    PartnerModul,
    PartnerNastaveni,
    PartnerTarif,
    PlatbaPartnera,
    TechnickaChyba,
    UlovCisloUctu,
    UpozorneniPlatby,
    Vydaj,
    VydajSablona,
    vychozi_variabilni_symbol,
)
from .prehled import data_prehledu, prijemci_hromadneho_emailu
from .pristupy import karty_testovacich_pristupu, prostredi_navesti
from .services import (
    kam_vydelal_celkem,
    kam_vydelal_mesic,
    kam_vypis_data,
    log_superadmin,
    oznac_kam_mesic_vyplaceny,
    oznac_platbu,
    resetuj_heslo_majitele,
    seznam_ulov_uctu,
    synchronizuj_ulov_ucty,
    vygeneruj_demo_heslo,
    vytvor_noveho_partnera,
)
from .services_moduly import nastav_modul, partner_modul
from rezervace.services.staff_auth import ensure_owner_flow_user, owner_flow_stav


superadmin_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_active and user.is_superuser,
    login_url='/admin/login/',
)

DETAIL_TABS = {
    'partner',
    'parovani',
    'platby',
    'upozorneni',
    'pristupy',
    'stav',
    'audit',
    'chyby',
    'web',
    'banner',
    'cenik',
    'novinky',
    'personal',
    'rezervace',
    'emaily',
    'smtp',
    'odkazy',
    'extra',
}


def _tab_z_request(request, default='partner'):
    tab = (request.POST.get('tab') or request.GET.get('tab') or default).strip()
    return tab if tab in DETAIL_TABS else default


def _detail_redirect(salon_id, tab='partner'):
    url = reverse('partner_admin:detail', args=[salon_id])
    if tab and tab in DETAIL_TABS:
        url = f'{url}?tab={tab}'
    return redirect(url)


def _partner(salon):
    partner, created = PartnerNastaveni.objects.get_or_create(
        salon=salon,
        defaults={
            'fakturacni_email': salon.email,
            'variabilni_symbol': vychozi_variabilni_symbol(salon.id) or None,
        },
    )
    if not created and not partner.variabilni_symbol:
        partner.variabilni_symbol = vychozi_variabilni_symbol(salon.id) or None
        if partner.variabilni_symbol:
            partner.save(update_fields=['variabilni_symbol', 'aktualizovano'])
    return partner


def _zajisti_partner_nastaveni():
    """Doplní PartnerNastaveni u salonů, které vznikly bez signalu (stub / seed)."""
    existujici = PartnerNastaveni.objects.values_list('salon_id', flat=True)
    chybejici = list(Salon.objects.exclude(id__in=existujici).only('id', 'email'))
    if not chybejici:
        return
    PartnerNastaveni.objects.bulk_create(
        [
            PartnerNastaveni(
                salon_id=salon.id,
                fakturacni_email=salon.email or '',
                variabilni_symbol=vychozi_variabilni_symbol(salon.id) or None,
            )
            for salon in chybejici
        ]
    )


def _vychozi_upozorneni(salon, partner):
    predmet = f'Upozornění na platbu za služby — {salon.name}'
    text = (
        f'Dobrý den,\n\n'
        f'evidujeme platbu {partner.castka:.2f} Kč se splatností '
        f'{partner.dalsi_splatnost:%d.%m.%Y} a variabilním symbolem '
        f'{partner.variabilni_symbol or "neuveden"} jako neuhrazenou.\n\n'
        f'Pokud jste již platbu odeslali, považujte prosím tuto zprávu za bezpředmětnou.\n'
    )
    return predmet, text


def _sablony_upozorneni(salon, partner):
    if not partner.dalsi_splatnost:
        return []
    castka = f'{partner.castka:.2f}'
    splatnost = partner.dalsi_splatnost.strftime('%d.%m.%Y')
    vs = partner.variabilni_symbol or 'neuveden'
    dni = partner.dni_po_splatnosti
    po_splatnosti = (
        f'Platba je {dni} dní po splatnosti.\n\n' if partner.je_po_splatnosti else ''
    )
    return [
        {
            'id': 'prvni',
            'label': '1. upomínka',
            'predmet': f'Upozornění na platbu — {salon.name}',
            'text': (
                f'Dobrý den,\n\n'
                f'dovolujeme si připomenout platbu {castka} Kč za služby '
                f'se splatností {splatnost} a variabilním symbolem {vs}.\n\n'
                f'{po_splatnosti}'
                f'Pokud jste již platbu odeslali, považujte prosím tuto zprávu za bezpředmětnou.\n\n'
                f'S pozdravem\nULOV KLIENTY\n'
            ),
        },
        {
            'id': 'druha',
            'label': '2. upomínka',
            'predmet': f'2. upomínka platby — {salon.name}',
            'text': (
                f'Dobrý den,\n\n'
                f'opětovně upozorňujeme na neuhrazenou platbu {castka} Kč '
                f'se splatností {splatnost} (VS {vs}).\n\n'
                f'{po_splatnosti}'
                f'Prosím o brzké uhrazení nebo potvrzení, že platba již byla odeslána.\n\n'
                f'S pozdravem\nULOV KLIENTY\n'
            ),
        },
        {
            'id': 'pred_blokaci',
            'label': 'Před blokací',
            'predmet': f'Poslední výzva před pozastavením služby — {salon.name}',
            'text': (
                f'Dobrý den,\n\n'
                f'evidujeme stále neuhrazenou platbu {castka} Kč se splatností {splatnost} '
                f'a VS {vs}.\n\n'
                f'{po_splatnosti}'
                f'Pokud platba nebude uhrazena v nejbližších dnech, budeme nuceni '
                f'dočasně pozastavit službu rezervací.\n\n'
                f'Po uhrazení službu ihned obnovíme.\n\n'
                f'S pozdravem\nULOV KLIENTY\n'
            ),
        },
    ]


def _salon_queryset(dnes=None):
    dnes = dnes or timezone.localdate()
    zacatek_mesice = dnes.replace(day=1)
    return Salon.objects.select_related(
        'partner_nastaveni',
        'partner_nastaveni__kam',
    ).annotate(
        rezervace_celkem=Count('rezervace', distinct=True),
        rezervace_mesic=Count(
            'rezervace',
            filter=Q(rezervace__vytvoreno__date__gte=zacatek_mesice),
            distinct=True,
        ),
        rezervace_budouci=Count(
            'rezervace',
            filter=Q(
                rezervace__zacatek__date__gte=dnes,
                rezervace__stav__in=['ceka', 'potvrzeno'],
            ),
            distinct=True,
        ),
        no_show_celkem=Count(
            'rezervace',
            filter=Q(rezervace__stav='no_show'),
            distinct=True,
        ),
        materialnik_aktivni=Exists(
            PartnerModul.objects.filter(
                salon_id=OuterRef('pk'),
                modul__kod=MODUL_MATERIALNIK,
                status=PartnerModul.STAV_ACTIVE,
            )
        ),
        platebni_priorita=Case(
            When(partner_nastaveni__dalsi_splatnost__lt=dnes, then=0),
            When(partner_nastaveni__dalsi_splatnost__isnull=True, then=2),
            default=1,
            output_field=IntegerField(),
        ),
    )


def _nacti_filtry(request):
    return {
        'q': request.GET.get('q', '').strip(),
        'stav': request.GET.get('stav', '').strip(),
        'platba': request.GET.get('platba', '').strip(),
    }


def _aplikuj_filtry(salons, filtry, dnes=None):
    dnes = dnes or timezone.localdate()
    hledat = filtry.get('q', '')
    stav = filtry.get('stav', '')
    platba = filtry.get('platba', '')

    if hledat:
        shoda = (
            Q(name__icontains=hledat)
            | Q(partner_nastaveni__domena__icontains=hledat)
            | Q(partner_nastaveni__variabilni_symbol__icontains=hledat)
            | Q(partner_nastaveni__fakturacni_email__icontains=hledat)
        )
        if hledat.isdigit():
            shoda |= Q(pk=int(hledat))
        salons = salons.filter(shoda)
    if stav in {PartnerNastaveni.STAV_ACTIVE, PartnerNastaveni.STAV_BLOCKED}:
        salons = salons.filter(partner_nastaveni__stav=stav)
    if platba == 'po_splatnosti':
        salons = salons.filter(partner_nastaveni__dalsi_splatnost__lt=dnes)
    elif platba == 'v_poradku':
        salons = salons.filter(partner_nastaveni__dalsi_splatnost__gte=dnes)
    elif platba == 'nenastaveno':
        salons = salons.filter(partner_nastaveni__dalsi_splatnost__isnull=True)
    elif platba == 'bez_vs':
        salons = salons.filter(
            Q(partner_nastaveni__variabilni_symbol__isnull=True)
            | Q(partner_nastaveni__variabilni_symbol='')
        )
    return salons


def _export_querystring(filtry):
    return urlencode({key: value for key, value in filtry.items() if value})


@superadmin_required
def novy_partner(request):
    """Založení nového partnera — jen základní data do DB."""
    if request.method == 'POST':
        form = NovyPartnerForm(request.POST)
        if form.is_valid():
            try:
                salon, partner, majitel, flow_user = vytvor_noveho_partnera(
                    data=form.cleaned_data,
                    actor=request.user,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            except Exception as exc:
                messages.error(request, f'Partnera se nepodařilo založit: {exc}')
            else:
                flow_note = ' FLOW aktivováno.' if flow_user else ' FLOW zatím neaktivní.'
                messages.success(
                    request,
                    f'Partner „{salon.name}“ založen (ID {salon.id}). '
                    f'Login majitele: {majitel.prihlasovaci_jmeno}.{flow_note}',
                )
                return _detail_redirect(salon.id, 'partner')
    else:
        form = NovyPartnerForm()
    return render(request, 'partner_admin/novy.html', {'form': form})


@superadmin_required
def tarify(request):
    if request.method == 'POST':
        akce = request.POST.get('akce')
        if akce == 'smazat':
            tarif = get_object_or_404(PartnerTarif, pk=request.POST.get('id'))
            nazev = tarif.nazev
            tarif.delete()
            messages.success(
                request,
                f'Tarif „{nazev}“ byl smazán. U partnerů zůstává dříve uložený název a cena.',
            )
            return redirect('partner_admin:tarify')
        instance = None
        if akce == 'ulozit':
            instance = get_object_or_404(PartnerTarif, pk=request.POST.get('id'))
        form = PartnerTarifForm(request.POST, instance=instance)
        if form.is_valid():
            ulozeno = form.save()
            messages.success(request, f'Tarif „{ulozeno.nazev}“ je uložený.')
            return redirect('partner_admin:tarify')
        messages.error(request, 'Tarif se nepodařilo uložit: ' + _chyby_formulare(form))
        novy_form = form if akce != 'ulozit' else PartnerTarifForm()
    else:
        novy_form = PartnerTarifForm()
    radky = [
        (row, PartnerTarifForm(instance=row))
        for row in PartnerTarif.objects.all()
    ]
    return render(
        request,
        'partner_admin/tarify.html',
        {
            'radky': radky,
            'novy_form': novy_form,
        },
    )


def _katalog_crud(request, *, model, form_cls, template, redirect_name, smazat_ok=True, po_ulozeni=None):
    if request.method == 'POST':
        akce = request.POST.get('akce')
        if smazat_ok and akce == 'smazat':
            row = get_object_or_404(model, pk=request.POST.get('id'))
            nazev = str(row)
            row.delete()
            if po_ulozeni:
                po_ulozeni()
            messages.success(request, f'„{nazev}“ byl smazán.')
            return redirect(redirect_name)
        instance = None
        if akce == 'ulozit':
            instance = get_object_or_404(model, pk=request.POST.get('id'))
        form = form_cls(request.POST, instance=instance)
        if form.is_valid():
            ulozeno = form.save()
            if po_ulozeni:
                po_ulozeni()
            messages.success(request, f'„{ulozeno}“ je uložené.')
            return redirect(redirect_name)
        messages.error(request, 'Nepodařilo se uložit: ' + _chyby_formulare(form))
        novy_form = form if akce != 'ulozit' else form_cls()
    else:
        novy_form = form_cls()
    qs = model.objects.all()
    if model is KeyAccountManager:
        qs = qs.prefetch_related('partneri__salon')
    radky = [(row, form_cls(instance=row)) for row in qs]
    return render(request, template, {'radky': radky, 'novy_form': novy_form})


@superadmin_required
def testovaci_pristupy(request):
    nove_heslo = request.session.pop('demo_nove_heslo', '')
    nove_id = request.session.pop('demo_nove_heslo_salon_id', None)
    return render(
        request,
        'partner_admin/testovaci_pristupy.html',
        {
            'karty': karty_testovacich_pristupu(nove_id, nove_heslo),
            'prostredi': prostredi_navesti(),
        },
    )


@superadmin_required
@require_POST
def regenerovat_demo_heslo(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id, partner_nastaveni__je_testovaci=True)
    majitel = (
        salon.zamestnanci.filter(role=Zamestnanec.ROLE_MAJITEL)
        .order_by('id')
        .first()
    )
    if not majitel:
        messages.error(request, 'Tento testovací salon nemá účet majitele.')
        return redirect('partner_admin:testovaci_pristupy')
    nove = vygeneruj_demo_heslo()
    resetuj_heslo_majitele(majitel, nove, request.user)
    request.session['demo_nove_heslo'] = nove
    request.session['demo_nove_heslo_salon_id'] = salon.id
    messages.success(
        request,
        f'Nové heslo pro {salon.name} je vygenerované níže. Zkopíruj ho teď — znovu ho neuvidíš.',
    )
    return redirect('partner_admin:testovaci_pristupy')


@superadmin_required
def kamove(request):
    edit_form = None
    edit_id = None
    novy_form = KeyAccountManagerForm()
    if request.method == 'POST':
        akce = request.POST.get('akce')
        if akce == 'smazat':
            row = get_object_or_404(KeyAccountManager, pk=request.POST.get('id'))
            nazev = str(row)
            row.delete()
            messages.success(request, f'„{nazev}“ byl smazán.')
            return redirect('partner_admin:kam')
        instance = None
        if akce == 'ulozit':
            instance = get_object_or_404(KeyAccountManager, pk=request.POST.get('id'))
        form = KeyAccountManagerForm(request.POST, instance=instance)
        if form.is_valid():
            ulozeno = form.save()
            messages.success(request, f'„{ulozeno}“ je uložené.')
            return redirect('partner_admin:kam')
        messages.error(request, 'Nepodařilo se uložit: ' + _chyby_formulare(form))
        if akce == 'ulozit' and instance:
            edit_form = form
            edit_id = instance.pk
        else:
            novy_form = form
    else:
        try:
            edit_id = int(request.GET.get('upravit') or 0) or None
        except (TypeError, ValueError):
            edit_id = None

    karty = []
    for kam in KeyAccountManager.objects.prefetch_related('partneri__salon').all():
        if edit_id == kam.pk and edit_form is not None:
            form = edit_form
        else:
            form = KeyAccountManagerForm(instance=kam)
        karty.append({
            'kam': kam,
            'form': form,
            'edituje': edit_id == kam.pk,
            'partneri': list(kam.partneri.all()),
            'mesic': kam_vydelal_mesic(kam),
            'celkem': kam_vydelal_celkem(kam),
        })
    return render(
        request,
        'partner_admin/kam.html',
        {
            'karty': karty,
            'novy_form': novy_form,
            'edit_id': edit_id,
        },
    )


MESICE_CS = [
    '', 'leden', 'únor', 'březen', 'duben', 'květen', 'červen',
    'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec',
]


def _posun_mesic(rok, mesic, delta):
    mesic += delta
    while mesic < 1:
        mesic += 12
        rok -= 1
    while mesic > 12:
        mesic -= 12
        rok += 1
    return rok, mesic


@superadmin_required
def kam_vypis(request, kam_id):
    kam = get_object_or_404(KeyAccountManager, pk=kam_id)
    dnes = timezone.localdate()
    try:
        rok = int(request.GET.get('rok') or dnes.year)
        mesic = int(request.GET.get('mesic') or dnes.month)
    except (TypeError, ValueError):
        rok, mesic = dnes.year, dnes.month
    if mesic < 1 or mesic > 12 or rok < 2000 or rok > 2100:
        rok, mesic = dnes.year, dnes.month
    data = kam_vypis_data(kam, rok, mesic)
    pred_rok, pred_mesic = _posun_mesic(rok, mesic, -1)
    dalsi_rok, dalsi_mesic = _posun_mesic(rok, mesic, 1)
    data.update({
        'mesic_nazev': MESICE_CS[mesic],
        'pred_rok': pred_rok,
        'pred_mesic': pred_mesic,
        'dalsi_rok': dalsi_rok,
        'dalsi_mesic': dalsi_mesic,
    })
    return render(request, 'partner_admin/kam_vypis.html', data)


@superadmin_required
@require_POST
def kam_vyplatit(request, kam_id):
    kam = get_object_or_404(KeyAccountManager, pk=kam_id)
    dnes = timezone.localdate()
    try:
        rok = int(request.POST.get('rok') or dnes.year)
        mesic = int(request.POST.get('mesic') or dnes.month)
    except (TypeError, ValueError):
        rok, mesic = dnes.year, dnes.month
    castka = oznac_kam_mesic_vyplaceny(kam, rok, mesic)
    messages.success(
        request,
        f'Měsíc {mesic:02d}/{rok} u {kam.jmeno} označen jako vyplacený ({castka} Kč).',
    )
    return redirect(f"{reverse('partner_admin:kam_vypis', args=[kam.id])}?rok={rok}&mesic={mesic}")


def _po_ulozeni_ulov_uctu():
    if not UlovCisloUctu.objects.filter(aktivni=True, primarni=True).exists():
        prvni = UlovCisloUctu.objects.filter(aktivni=True).order_by('razeni', 'id').first()
        if prvni:
            UlovCisloUctu.objects.filter(pk=prvni.pk).update(primarni=True)
    synchronizuj_ulov_ucty()


@superadmin_required
def ulov_ucty(request):
    return _katalog_crud(
        request,
        model=UlovCisloUctu,
        form_cls=UlovCisloUctuForm,
        template='partner_admin/ucty.html',
        redirect_name='partner_admin:ucty',
        po_ulozeni=_po_ulozeni_ulov_uctu,
    )


@superadmin_required
def dashboard(request):
    _zajisti_partner_nastaveni()
    return render(request, 'partner_admin/dashboard.html', data_prehledu())


@superadmin_required
def partneri(request):
    dnes = timezone.localdate()
    _zajisti_partner_nastaveni()
    filtry = _nacti_filtry(request)
    salons = _aplikuj_filtry(_salon_queryset(dnes), filtry, dnes)
    salons = list(salons.order_by('platebni_priorita', 'partner_nastaveni__dalsi_splatnost', 'name'))
    souhrn = {
        'salonu': len(salons),
        'blokovanych': sum(
            s.partner_nastaveni.stav == PartnerNastaveni.STAV_BLOCKED for s in salons
        ),
        'po_splatnosti': sum(s.partner_nastaveni.je_po_splatnosti for s in salons),
        'rezervaci_mesic': sum(s.rezervace_mesic for s in salons),
        'nevyresenych_chyb': TechnickaChyba.objects.filter(vyreseno=False).count(),
    }
    return render(
        request,
        'partner_admin/partneri.html',
        {
            'salony': salons,
            'souhrn': souhrn,
            'dnes': dnes,
            'filtry': filtry,
            'export_qs': _export_querystring(filtry),
        },
    )


@superadmin_required
def export_csv(request):
    dnes = timezone.localdate()
    _zajisti_partner_nastaveni()
    filtry = _nacti_filtry(request)
    salons = _aplikuj_filtry(_salon_queryset(dnes), filtry, dnes).order_by(
        'platebni_priorita',
        'partner_nastaveni__dalsi_splatnost',
        'name',
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="partneri-{dnes.isoformat()}.csv"'
    )
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Salon',
        'Doména',
        'Stav služby',
        'VS',
        'Částka',
        'Periodicita',
        'Další splatnost',
        'Platební stav',
        'Dní po splatnosti',
        'Fakturační e-mail',
        'Tarif',
        'KAM',
        'Materiálník',
    ])
    for salon in salons:
        partner = salon.partner_nastaveni
        if partner.platebni_stav == 'po_splatnosti':
            platebni = 'Nezaplaceno · po splatnosti'
        elif partner.platebni_stav == 'v_poradku':
            platebni = 'Nezaplaceno'
        else:
            platebni = 'Nenastaveno'
        writer.writerow([
            salon.name,
            partner.domena,
            partner.get_stav_display(),
            partner.variabilni_symbol or '',
            f'{partner.castka:.2f}'.replace('.', ','),
            partner.get_periodicita_display(),
            partner.dalsi_splatnost.strftime('%d.%m.%Y') if partner.dalsi_splatnost else '',
            platebni,
            partner.dni_po_splatnosti if partner.je_po_splatnosti else '',
            partner.fakturacni_email,
            partner.tarif,
            partner.kam.jmeno if partner.kam_id else '',
            'ano' if getattr(salon, 'materialnik_aktivni', False) else 'ne',
        ])
    return response


@superadmin_required
def export_platby_csv(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    dnes = timezone.localdate()
    platby = (
        PlatbaPartnera.objects.filter(salon=salon)
        .select_related('oznacil')
        .order_by('-splatnost', '-id')
    )

    safe_name = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in salon.name)[:40]
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="platby-{safe_name or salon.id}-{dnes.isoformat()}.csv"'
    )
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Salon',
        'Stav',
        'Splatnost období',
        'Zaplaceno dne',
        'Očekávaná částka',
        'Přijatá částka',
        'VS',
        'Poznámka',
        'Označil',
        'Zaznamenáno',
    ])
    for platba in platby:
        writer.writerow([
            salon.name,
            'ZAPLACENO',
            platba.splatnost.strftime('%d.%m.%Y'),
            platba.zaplaceno_dne.strftime('%d.%m.%Y'),
            f'{platba.ocekavana_castka:.2f}'.replace('.', ','),
            (
                f'{platba.prijata_castka:.2f}'.replace('.', ',')
                if platba.prijata_castka is not None
                else ''
            ),
            platba.variabilni_symbol or '',
            platba.poznamka,
            platba.oznacil.username if platba.oznacil_id else '',
            timezone.localtime(platba.vytvoreno).strftime('%d.%m.%Y %H:%M'),
        ])
    return response


def _chyby_formulare(form):
    return '; '.join(error for errors in form.errors.values() for error in errors)


def _zobraz_ulozenou_hodnotu(value):
    if value in (None, ''):
        return '—'
    return str(value)


def _render_detail_partnera(request, salon, nastaveni_form=None):
    partner = _partner(salon)
    dnes = timezone.localdate()
    zacatek_mesice = dnes.replace(day=1)
    rezervace = Rezervace.all_objects.filter(salon=salon)
    statistiky = {
        'celkem': rezervace.count(),
        'mesic': rezervace.filter(vytvoreno__date__gte=zacatek_mesice).count(),
        'budouci': rezervace.filter(
            zacatek__date__gte=dnes,
            stav__in=['ceka', 'potvrzeno'],
        ).count(),
        'dokoncene': rezervace.filter(stav='dokonceno').count(),
        'zrusene': rezervace.filter(stav__in=['zakaznik_storno', 'salon_storno']).count(),
        'no_show': rezervace.filter(stav='no_show').count(),
    }
    sablony = _sablony_upozorneni(salon, partner)
    vychozi_predmet = ''
    vychozi_text = ''
    if sablony:
        vychozi_predmet = sablony[0]['predmet']
        vychozi_text = sablony[0]['text']
    api_session = create_partner_session(request.user, days=1)
    form = nastaveni_form or PartnerNastaveniForm(instance=partner)
    tarif_nazev = form['tarif'].value() or partner.tarif or ''
    je_prvni_platba = not salon.partnerske_platby.exists()
    if je_prvni_platba and partner.prvni_platba and partner.prvni_platba > 0:
        castka_platby = partner.prvni_platba
    else:
        castka_platby = partner.castka
    return render(
        request,
        'partner_admin/detail.html',
        {
            'salon': salon,
            'partner': partner,
            'active_tab': _tab_z_request(request),
            'partner_api_token': str(api_session.token),
            'dnes': dnes,
            'statistiky': statistiky,
            'nastaveni_form': form,
            'tarif_logo_url': logo_url_pro_tarif(tarif_nazev),
            'tarif_logo_nazev': tarif_nazev or '—',
            'tarif_loga': tarif_loga_pro_sablonu(),
            'je_prvni_platba': je_prvni_platba,
            'platba_form': PlatbaForm(initial={'prijata_castka': castka_platby}),
            'upozorneni_form': UpozorneniForm(
                initial={'predmet': vychozi_predmet, 'text': vychozi_text},
            ),
            'sablony_upozorneni': sablony,
            'email_jen_konzole': settings.EMAIL_BACKEND.endswith('console.EmailBackend'),
            'blokace_form': BlokaceForm(),
            'majitele': salon.zamestnanci.filter(role=Zamestnanec.ROLE_MAJITEL).order_by('jmeno'),
            'reset_form': ResetHeslaForm(),
            'owner_flow': owner_flow_stav(salon),
            'materialnik_modul': partner_modul(salon, MODUL_MATERIALNIK),
            'materialnik_public_url': (getattr(settings, 'MATERIALNIK_PUBLIC_URL', '') or '').rstrip('/'),
            'ulov_ucty': seznam_ulov_uctu(),
            'platby': salon.partnerske_platby.select_related('oznacil')[:24],
            'posledni_platba': salon.partnerske_platby.select_related('oznacil').first(),
            'extra_faktury': salon.extra_faktury.all()[:40],
            'extra_form': ExtraFakturaForm(),
            'upozorneni': salon.upozorneni_plateb.select_related('odeslal')[:20],
            'audity': SalonAuditLog.objects.filter(salon=salon)[:50],
            'chyby': TechnickaChyba.objects.filter(salon=salon)[:50],
        },
    )


@superadmin_required
def detail_partnera(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    return _render_detail_partnera(request, salon)


@superadmin_required
@require_POST
def ulozit_nastaveni(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    partner = _partner(salon)
    pred = {
        'domena': partner.domena,
        'tarif': partner.tarif,
        'fakturacni_email': partner.fakturacni_email,
        'variabilni_symbol': partner.variabilni_symbol,
        'periodicita': partner.periodicita,
        'castka': str(partner.castka),
        'dalsi_splatnost': partner.dalsi_splatnost.isoformat() if partner.dalsi_splatnost else None,
        'kam': partner.kam_id,
        'prvni_platba': str(partner.prvni_platba),
        'kam_provize': str(partner.kam_provize),
        'kam_procento': str(partner.kam_procento),
        'ico': partner.ico,
        'je_testovaci': partner.je_testovaci,
    }
    form = PartnerNastaveniForm(request.POST, instance=partner)
    if not form.is_valid():
        messages.error(request, 'Nastavení se nepodařilo uložit: ' + _chyby_formulare(form))
        return _render_detail_partnera(request, salon, nastaveni_form=form)
    try:
        ulozeno = form.save()
    except ValidationError as exc:
        form.add_error(None, exc)
        messages.error(request, 'Nastavení se nepodařilo uložit: ' + _chyby_formulare(form))
        return _render_detail_partnera(request, salon, nastaveni_form=form)
    ulozeno.refresh_from_db()
    po = {
        'domena': ulozeno.domena,
        'tarif': ulozeno.tarif,
        'fakturacni_email': ulozeno.fakturacni_email,
        'variabilni_symbol': ulozeno.variabilni_symbol,
        'periodicita': ulozeno.periodicita,
        'castka': str(ulozeno.castka),
        'dalsi_splatnost': ulozeno.dalsi_splatnost.isoformat() if ulozeno.dalsi_splatnost else None,
        'kam': ulozeno.kam_id,
        'prvni_platba': str(ulozeno.prvni_platba),
        'kam_provize': str(ulozeno.kam_provize),
        'kam_procento': str(ulozeno.kam_procento),
        'ico': ulozeno.ico,
        'je_testovaci': ulozeno.je_testovaci,
    }
    log_superadmin(salon, request.user, 'Upraveno nastavení partnera.', pred=pred, po=po)
    messages.success(
        request,
        (
            'Nastavení partnera bylo uloženo. '
            f'Doména: {_zobraz_ulozenou_hodnotu(ulozeno.domena)}; '
            f'tarif: {_zobraz_ulozenou_hodnotu(ulozeno.tarif)}; '
            f'e-mail: {_zobraz_ulozenou_hodnotu(ulozeno.fakturacni_email)}; '
            f'VS: {_zobraz_ulozenou_hodnotu(ulozeno.variabilni_symbol)}.'
        ),
    )
    return _detail_redirect(salon.id, _tab_z_request(request, 'partner'))


@superadmin_required
@require_POST
def nastavit_materialnik(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    zapnout = request.POST.get('zapnout') == '1'
    row = nastav_modul(salon, MODUL_MATERIALNIK, zapnout, request.user)
    if zapnout and row.status == row.STAV_ACTIVE:
        messages.success(request, 'Materiálník je zapnutý. Partner se přihlásí stejným účtem.')
    elif zapnout and row.status == row.STAV_ERROR:
        messages.error(request, f'Materiálník se nepodařilo zapnout: {row.provisioning_error}')
    elif not zapnout:
        messages.success(request, 'Materiálník je vypnutý. Data skladu zůstávají, ve FLOW o něm není zmínka.')
    else:
        messages.info(request, f'Stav Materiálníku: {row.get_status_display()}.')
    return _detail_redirect(salon.id, 'partner')


@superadmin_required
@require_POST
def blokovat(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    partner = _partner(salon)
    form = BlokaceForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Salon nebyl zablokován: ' + '; '.join(
            error for errors in form.errors.values() for error in errors
        ))
        return _detail_redirect(salon.id, 'stav')
    if partner.stav != PartnerNastaveni.STAV_BLOCKED:
        partner.stav = PartnerNastaveni.STAV_BLOCKED
        partner.duvod_blokace = form.cleaned_data['duvod']
        partner.save()
        log_superadmin(salon, request.user, 'Salon ručně přepnut na BLOCKED.', po={'stav': 'blocked'})
    messages.warning(request, 'Salon je BLOCKED. Jeho API nyní vrací stav 423.')
    return _detail_redirect(salon.id, 'stav')


@superadmin_required
@require_POST
def aktivovat(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    partner = _partner(salon)
    if partner.stav != PartnerNastaveni.STAV_ACTIVE:
        partner.stav = PartnerNastaveni.STAV_ACTIVE
        partner.save()
        log_superadmin(salon, request.user, 'Salon ručně přepnut na ACTIVE.', po={'stav': 'active'})
    messages.success(request, 'Salon je ACTIVE.')
    return _detail_redirect(salon.id, 'stav')


@superadmin_required
@require_POST
def potvrdit_platbu(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    form = PlatbaForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            platba = oznac_platbu(
                salon,
                request.user,
                form.cleaned_data['zaplaceno_dne'],
                form.cleaned_data['prijata_castka'],
                form.cleaned_data['poznamka'],
                faktura_pdf=form.cleaned_data.get('faktura_pdf'),
            )
            zprava = 'Hotovo: období označeno jako ZAPLACENO. Aktuální období je nové NEZAPLACENO.'
            if platba.faktura_pdf:
                from .faktura import odesli_fakturu_partnerovi
                ok, detail = odesli_fakturu_partnerovi(platba)
                if ok:
                    zprava += f' Faktura {platba.cislo_faktury} je vygenerovaná a odeslaná na {detail}.'
                elif detail == 'chybí fakturační e-mail':
                    zprava += f' Faktura {platba.cislo_faktury} je vygenerovaná. Doplňte fakturační e-mail, ať ji můžeme poslat.'
                else:
                    zprava += f' Faktura {platba.cislo_faktury} je vygenerovaná, e-mail se nepodařilo odeslat: {detail}.'
            else:
                zprava += ' PDF faktury se nepodařilo vygenerovat — použijte tlačítko níže.'
            messages.success(request, zprava)
        except Exception as exc:
            messages.error(request, f'Platbu nelze uložit: {exc}')
    else:
        messages.error(request, 'Zkontrolujte datum, částku a případně PDF faktury.')
    return _detail_redirect(salon.id, 'parovani')


@superadmin_required
@require_POST
def nahrat_fakturu_platby(request, salon_id, platba_id):
    """Zpětně nahrát / nahradit PDF faktury u existující platby."""
    salon = get_object_or_404(Salon, pk=salon_id)
    platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=salon)
    form = FakturaPlatbyForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Nahrajte platný PDF soubor faktury.')
        return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))

    pdf = form.cleaned_data['faktura_pdf']
    if platba.faktura_pdf:
        platba.faktura_pdf.close()
        platba.faktura_pdf.delete(save=False)
    platba.faktura_pdf = pdf
    platba.save(update_fields=['faktura_pdf'])
    log_superadmin(
        salon,
        request.user,
        f'Nahrána/nahrazena faktura PDF u platby splatnost {platba.splatnost:%d.%m.%Y}.',
        kategorie='platby',
        objekt_typ='PlatbaPartnera',
        objekt_id=platba.id,
        po={'soubor': getattr(pdf, 'name', '')},
    )
    messages.success(request, 'Faktura PDF uložena.')
    return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))


@superadmin_required
@require_POST
def vygenerovat_fakturu(request, salon_id, platba_id):
    """Jedno kliknutí po spárování. K platbě vznikne nejvýš jedna faktura."""
    from .faktura import odesli_fakturu_partnerovi, zajisti_fakturu

    salon = get_object_or_404(Salon, pk=salon_id)
    platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=salon)
    try:
        platba, nova = zajisti_fakturu(platba)
    except Exception as exc:
        messages.error(request, f'PDF se nepodařilo vygenerovat: {exc}')
        return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))
    if not nova:
        messages.info(request, f'Faktura {platba.cislo_faktury} k této platbě už existuje.')
        return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))
    log_superadmin(
        salon,
        request.user,
        f'Vygenerována faktura {platba.cislo_faktury} k platbě {platba.splatnost:%d.%m.%Y}.',
        kategorie='platby',
        objekt_typ='PlatbaPartnera',
        objekt_id=platba.id,
        po={'cislo': platba.cislo_faktury},
    )
    ok, detail = odesli_fakturu_partnerovi(platba)
    if ok:
        messages.success(request, f'Faktura {platba.cislo_faktury} je vygenerovaná a odeslaná na {detail}.')
    else:
        messages.success(request, f'Faktura {platba.cislo_faktury} je vygenerovaná. E-mail: {detail}.')
    return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))


@superadmin_required
def pripravit_fakturu(request, salon_id, platba_id):
    """Šablona faktury k úpravě. PDF vznikne až po potvrzení."""
    from .faktura import uloz_fakturu_k_platbe, vychozi_data_faktury

    salon = get_object_or_404(Salon, pk=salon_id)
    platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=salon)
    if request.method == 'POST':
        form = FakturaEditForm(request.POST)
        if form.is_valid():
            try:
                uloz_fakturu_k_platbe(platba, form.data_pro_pdf())
            except Exception as exc:
                messages.error(request, f'PDF se nepodařilo vygenerovat: {exc}')
                return render(
                    request,
                    'partner_admin/faktura_form.html',
                    {'salon': salon, 'platba': platba, 'form': form},
                )
            log_superadmin(
                salon,
                request.user,
                f'Vygenerována faktura {platba.cislo_faktury} k platbě {platba.splatnost:%d.%m.%Y}.',
                kategorie='platby',
                objekt_typ='PlatbaPartnera',
                objekt_id=platba.id,
                po={'cislo': platba.cislo_faktury},
            )
            messages.success(request, f'Faktura {platba.cislo_faktury} je vygenerovaná.')
            return _detail_redirect(salon.id, _tab_z_request(request, 'parovani'))
        messages.error(request, 'Upravte červená pole a zkuste to znovu.')
    else:
        form = FakturaEditForm(initial=vychozi_data_faktury(platba))
    return render(
        request,
        'partner_admin/faktura_form.html',
        {'salon': salon, 'platba': platba, 'form': form},
    )


@superadmin_required
def stahnout_fakturu_platby(request, salon_id, platba_id):
    """Stažení PDF přes přihlášený partner-admin (ne veřejné /media/)."""
    from django.http import FileResponse, Http404

    salon = get_object_or_404(Salon, pk=salon_id)
    platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=salon)
    if not platba.faktura_pdf:
        raise Http404('Faktura neexistuje.')
    try:
        handle = platba.faktura_pdf.open('rb')
    except FileNotFoundError as exc:
        raise Http404('Soubor faktury na disku chybí.') from exc
    filename = platba.faktura_pdf.name.rsplit('/', 1)[-1]
    return FileResponse(handle, as_attachment=False, filename=filename, content_type='application/pdf')


@superadmin_required
@require_POST
def smazat_fakturu_platby(request, salon_id, platba_id):
    """Smazat PDF faktury u existující platby."""
    salon = get_object_or_404(Salon, pk=salon_id)
    platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=salon)
    if not platba.faktura_pdf:
        messages.error(request, 'U této platby není žádná faktura.')
        return _detail_redirect(salon.id, 'platby')

    platba.faktura_pdf.close()
    platba.faktura_pdf.delete(save=False)
    platba.faktura_pdf = None
    platba.save(update_fields=['faktura_pdf'])
    log_superadmin(
        salon,
        request.user,
        f'Smazána faktura PDF u platby splatnost {platba.splatnost:%d.%m.%Y}.',
        kategorie='platby',
        objekt_typ='PlatbaPartnera',
        objekt_id=platba.id,
    )
    messages.success(request, 'Faktura PDF smazána.')
    return _detail_redirect(salon.id, _tab_z_request(request, 'platby'))


@superadmin_required
@require_POST
def odeslat_upozorneni(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    partner = _partner(salon)
    if not partner.fakturacni_email:
        messages.error(request, 'Doplňte fakturační e-mail.')
        return _detail_redirect(salon.id, 'upozorneni')

    form = UpozorneniForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Doplňte předmět a text upozornění.')
        return _detail_redirect(salon.id, 'upozorneni')
    predmet = form.cleaned_data['predmet']
    zprava = form.cleaned_data['text']
    splatnost = partner.dalsi_splatnost or timezone.localdate()
    uspesne = False
    chyba = ''
    try:
        send_mail(
            predmet,
            zprava,
            settings.DEFAULT_FROM_EMAIL,
            [partner.fakturacni_email],
            fail_silently=False,
        )
        uspesne = True
    except Exception as exc:
        chyba = str(exc)[:500]

    UpozorneniPlatby.objects.create(
        salon=salon,
        splatnost=splatnost,
        prijemce=partner.fakturacni_email,
        predmet=predmet,
        text=zprava,
        uspesne=uspesne,
        chyba=chyba,
        odeslal=request.user,
    )
    log_superadmin(
        salon,
        request.user,
        'Odesláno upozornění na platbu.' if uspesne else 'Pokus o upozornění na platbu selhal.',
        kategorie='platby',
    )
    if uspesne:
        messages.success(request, 'Upozornění bylo odesláno.')
    else:
        messages.error(request, f'Upozornění se nepodařilo odeslat: {chyba}')
    return _detail_redirect(salon.id, 'upozorneni')


@superadmin_required
@require_POST
def reset_hesla(request, salon_id, zamestnanec_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    majitel = get_object_or_404(
        Zamestnanec,
        pk=zamestnanec_id,
        salon=salon,
        role=Zamestnanec.ROLE_MAJITEL,
    )
    form = ResetHeslaForm(request.POST)
    if form.is_valid():
        nove = form.cleaned_data['nove_heslo']
        resetuj_heslo_majitele(majitel, nove, request.user)
        messages.success(request, f'Heslo účtu {majitel.prihlasovaci_jmeno} bylo resetováno.')
    else:
        messages.error(request, 'Heslo musí mít alespoň 10 znaků.')
    return _detail_redirect(salon.id, 'pristupy')


@superadmin_required
@require_POST
def aktivovat_flow(request, salon_id):
    """I7 — založí FLOW účet majitele (sdílené heslo + e-mail)."""
    salon = get_object_or_404(Salon, pk=salon_id)
    email = (request.POST.get('email') or '').strip() or None
    try:
        user, created = ensure_owner_flow_user(salon, email=email)
    except ValueError as exc:
        messages.error(request, str(exc))
        return _detail_redirect(salon.id, 'pristupy')
    log_superadmin(
        salon,
        request.user,
        'Aktivován FLOW přístup majitele.' if created else 'FLOW majitele už existoval — ověřeno.',
        kategorie='ucty',
        objekt_typ='FlowUser',
        objekt_id=user.id,
        po={'email': user.email, 'vytvoreno': created},
    )
    if created:
        messages.success(
            request,
            f'FLOW aktivován pro {user.email}. Majitelka se přihlásí stejným heslem jako do webu.',
        )
    else:
        messages.success(request, f'FLOW už je aktivní ({user.email}).')
    return _detail_redirect(salon.id, 'pristupy')


@superadmin_required
@require_POST
def vyresit_chybu(request, chyba_id):
    chyba = get_object_or_404(TechnickaChyba, pk=chyba_id)
    chyba.vyreseno = True
    chyba.save(update_fields=['vyreseno'])
    if request.POST.get('zpet') == 'seznam' or not chyba.salon_id:
        return redirect('partner_admin:chyby')
    return _detail_redirect(chyba.salon_id, 'chyby')


@superadmin_required
def seznam_chyb(request):
    qs = TechnickaChyba.objects.select_related('salon')
    jen_nove = request.GET.get('stav') != 'vse'
    if jen_nove:
        qs = qs.filter(vyreseno=False)
    return render(
        request,
        'partner_admin/chyby.html',
        {
            'chyby': qs[:80],
            'jen_nove': jen_nove,
            'pocet': qs.count(),
        },
    )


@superadmin_required
def detail_chyby(request, chyba_id):
    chyba = get_object_or_404(TechnickaChyba.objects.select_related('salon'), pk=chyba_id)
    return render(request, 'partner_admin/chyba_detail.html', {'chyba': chyba})


@superadmin_required
def hromadne_emaily(request):
    tarify = PartnerTarif.objects.filter(aktivni=True)
    if request.method == 'POST':
        form = HromadnyEmailForm(request.POST, tarify=tarify)
        if form.is_valid():
            prijemci, preskoceno = prijemci_hromadneho_emailu(
                form.cleaned_data['okruh'],
                form.cleaned_data.get('tarif') or '',
            )
            if not prijemci:
                messages.error(request, 'V tomto okruhu není žádný partner s e-mailem.')
            else:
                odeslano = 0
                chyby_pocet = 0
                predmet = form.cleaned_data['predmet']
                zprava = form.cleaned_data['text']
                for _partner, adresa in prijemci:
                    try:
                        send_mail(
                            predmet,
                            zprava,
                            settings.DEFAULT_FROM_EMAIL,
                            [adresa],
                            fail_silently=False,
                        )
                        odeslano += 1
                    except Exception:
                        chyby_pocet += 1
                HromadnyEmail.objects.create(
                    predmet=predmet,
                    text=zprava,
                    okruh=form.cleaned_data['okruh'],
                    tarif=form.cleaned_data.get('tarif') or '',
                    odeslano_pocet=odeslano,
                    preskoceno_pocet=preskoceno,
                    chyba_pocet=chyby_pocet,
                    odeslal=request.user,
                )
                if odeslano:
                    messages.success(
                        request,
                        f'E-mail odeslán na {odeslano} adres.'
                        + (f' Bez e-mailu: {preskoceno}.' if preskoceno else '')
                        + (f' Selhalo: {chyby_pocet}.' if chyby_pocet else ''),
                    )
                    return redirect('partner_admin:emaily')
                messages.error(request, 'E-mail se nepodařilo odeslat na žádnou adresu.')
    else:
        form = HromadnyEmailForm(tarify=tarify)
        if request.GET.get('okruh'):
            form.fields['okruh'].initial = request.GET.get('okruh')
    okruh = request.POST.get('okruh') or form['okruh'].value() or HromadnyEmail.OKRUH_VSICHNI
    tarif = request.POST.get('tarif') or form['tarif'].value() or ''
    prijemci, preskoceno = prijemci_hromadneho_emailu(okruh, tarif)
    return render(
        request,
        'partner_admin/emaily.html',
        {
            'form': form,
            'prijemcu': len(prijemci),
            'preskoceno': preskoceno,
            'historie': HromadnyEmail.objects.select_related('odeslal')[:8],
        },
    )


def _pdf_response(soubor, filename):
    if not soubor:
        raise Http404('PDF není uložené.')
    return FileResponse(
        soubor.open('rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/pdf',
    )


@superadmin_required
def evidence_faktur(request):
    dnes = timezone.localdate()
    vychozi_od, vychozi_do = vychozi_obdobi(dnes)
    od_dne = parse_datum(request.GET.get('od'), vychozi_od)
    do_dne = parse_datum(request.GET.get('do'), vychozi_do)
    if od_dne > do_dne:
        od_dne, do_dne = do_dne, od_dne
    podle = 'uhrada' if request.GET.get('podle') == 'uhrada' else 'vystaveni'
    radky = seznam_faktur(od_dne=od_dne, do_dne=do_dne, podle=podle)
    souhrn = data_souhrnu(od_dne=od_dne, do_dne=do_dne, podle=podle)
    if request.GET.get('souhrn') == 'pdf':
        from .faktura import vygeneruj_souhrn_pdf

        pdf = vygeneruj_souhrn_pdf(souhrn)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="souhrn-{od_dne.isoformat()}-{do_dne.isoformat()}.pdf"'
        )
        return response
    return render(
        request,
        'partner_admin/faktury.html',
        {
            'radky': radky,
            'souhrn': souhrn,
            'od_dne': od_dne,
            'do_dne': do_dne,
            'podle': podle,
        },
    )


@superadmin_required
def stahnout_fakturu_evidence(request, zdroj, pk):
    if zdroj == 'partnerstvi':
        platba = get_object_or_404(PlatbaPartnera, pk=pk)
        nazev = f'faktura-{platba.cislo_faktury or platba.id}.pdf'
        return _pdf_response(platba.faktura_pdf, nazev)
    if zdroj == 'extra':
        faktura = get_object_or_404(ExtraFaktura, pk=pk)
        nazev = f'faktura-{faktura.cislo_faktury}.pdf'
        return _pdf_response(faktura.faktura_pdf, nazev)
    raise Http404()


@superadmin_required
def vydaje(request):
    form = VydajForm(request.POST or None)
    if request.method == 'GET' and request.GET.get('sablona'):
        sablona = get_object_or_404(VydajSablona, pk=request.GET.get('sablona'))
        form = VydajForm(initial={
            'castka': sablona.castka,
            'ucet': sablona.ucet_id,
            'salon': sablona.salon_id,
            'poznamka': sablona.poznamka or sablona.nazev,
        })
    if request.method == 'POST':
        if form.is_valid():
            vydaj = Vydaj.objects.create(
                datum=form.cleaned_data['datum'],
                castka=form.cleaned_data['castka'],
                ucet=form.cleaned_data['ucet'],
                salon=form.cleaned_data.get('salon'),
                poznamka=form.cleaned_data['poznamka'].strip(),
                vytvoril=request.user,
            )
            if form.cleaned_data.get('ulozit_sablonu'):
                VydajSablona.objects.update_or_create(
                    nazev=form.cleaned_data['nazev_sablony'],
                    defaults={
                        'castka': vydaj.castka,
                        'ucet': vydaj.ucet,
                        'salon': vydaj.salon,
                        'poznamka': vydaj.poznamka,
                    },
                )
            messages.success(request, f'Výdaj {vydaj.castka} Kč uložen.')
            return redirect('partner_admin:vydaje')
        messages.error(request, 'Výdaj se nepodařilo uložit.')
    od_dne = parse_datum(request.GET.get('od'), timezone.localdate().replace(day=1))
    do_dne = parse_datum(request.GET.get('do'), timezone.localdate())
    if od_dne > do_dne:
        od_dne, do_dne = do_dne, od_dne
    seznam = Vydaj.objects.filter(datum__gte=od_dne, datum__lte=do_dne).select_related(
        'ucet', 'salon',
    )
    return render(
        request,
        'partner_admin/vydaje.html',
        {
            'form': form,
            'radky': seznam,
            'sablony': VydajSablona.objects.select_related('ucet', 'salon'),
            'od_dne': od_dne,
            'do_dne': do_dne,
        },
    )


@superadmin_required
@require_POST
def vytvorit_extra_fakturu(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    form = ExtraFakturaForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Fakturu nelze vystavit: ' + _chyby_formulare(form))
        return _detail_redirect(salon.id, 'extra')
    pred_splatnost = salon.partner_nastaveni.dalsi_splatnost
    faktura, mail_ok, mail_detail = vytvor_extra_fakturu(
        salon,
        request.user,
        popis=form.cleaned_data['popis'],
        castka=form.cleaned_data['castka'],
        stav=form.cleaned_data['stav'],
        poznamka=form.cleaned_data.get('poznamka') or '',
        odeslat_email=form.cleaned_data.get('odeslat_email'),
    )
    po_splatnost = salon.partner_nastaveni.dalsi_splatnost
    if pred_splatnost != po_splatnost:
        messages.error(request, 'Chyba: extra faktura změnila splatnost tarifu.')
    zprava = f'Faktura {faktura.cislo_faktury} je vystavená (VS {faktura.variabilni_symbol}).'
    if faktura.stav == ExtraFaktura.STAV_K_UHRADE or form.cleaned_data.get('odeslat_email'):
        if mail_ok:
            zprava += f' E-mail odeslán na {mail_detail}.'
        else:
            zprava += f' E-mail se nepodařilo odeslat: {mail_detail}.'
    messages.success(request, zprava)
    return _detail_redirect(salon.id, 'extra')


@superadmin_required
@require_POST
def extra_faktura_uhrazena(request, salon_id, faktura_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    faktura = get_object_or_404(ExtraFaktura, pk=faktura_id, salon=salon)
    pred = salon.partner_nastaveni.dalsi_splatnost
    oznacit_extra_uhrazeno(faktura, request.user)
    salon.partner_nastaveni.refresh_from_db()
    if salon.partner_nastaveni.dalsi_splatnost != pred:
        messages.error(request, 'Chyba: extra faktura změnila splatnost tarifu.')
    else:
        messages.success(request, f'Faktura {faktura.cislo_faktury} je označená jako uhrazená.')
    return _detail_redirect(salon.id, 'extra')

