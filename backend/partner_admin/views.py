import csv
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rezervace.models import Rezervace, SalonAuditLog, Zamestnanec
from salons.models import Salon

from .forms import (
    BlokaceForm,
    PartnerNastaveniForm,
    PlatbaForm,
    ResetHeslaForm,
    UpozorneniForm,
)
from .models import PartnerNastaveni, PlatbaPartnera, TechnickaChyba, UpozorneniPlatby
from .services import log_superadmin, oznac_platbu


superadmin_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_active and user.is_superuser,
    login_url='/admin/login/',
)


def _partner(salon):
    partner, _ = PartnerNastaveni.objects.get_or_create(
        salon=salon,
        defaults={'fakturacni_email': salon.email},
    )
    return partner


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
    return Salon.objects.select_related('partner_nastaveni').annotate(
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
        salons = salons.filter(
            Q(name__icontains=hledat)
            | Q(partner_nastaveni__domena__icontains=hledat)
            | Q(partner_nastaveni__variabilni_symbol__icontains=hledat)
            | Q(partner_nastaveni__fakturacni_email__icontains=hledat)
        )
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
def dashboard(request):
    dnes = timezone.localdate()
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
        'partner_admin/dashboard.html',
        {
            'salony': salons,
            'souhrn': souhrn,
            'dnes': dnes,
            'filtry': filtry,
            'export_qs': _export_querystring(filtry),
            'chyby': TechnickaChyba.objects.select_related('salon').filter(vyreseno=False)[:20],
        },
    )


@superadmin_required
def export_csv(request):
    dnes = timezone.localdate()
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


@superadmin_required
def detail_partnera(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
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
    return render(
        request,
        'partner_admin/detail.html',
        {
            'salon': salon,
            'partner': partner,
            'dnes': dnes,
            'statistiky': statistiky,
            'nastaveni_form': PartnerNastaveniForm(instance=partner),
            'platba_form': PlatbaForm(initial={'prijata_castka': partner.castka}),
            'upozorneni_form': UpozorneniForm(
                initial={'predmet': vychozi_predmet, 'text': vychozi_text},
            ),
            'sablony_upozorneni': sablony,
            'email_jen_konzole': settings.EMAIL_BACKEND.endswith('console.EmailBackend'),
            'blokace_form': BlokaceForm(),
            'majitele': salon.zamestnanci.filter(role=Zamestnanec.ROLE_MAJITEL).order_by('jmeno'),
            'reset_form': ResetHeslaForm(),
            'platby': salon.partnerske_platby.select_related('oznacil')[:24],
            'posledni_platba': salon.partnerske_platby.select_related('oznacil').first(),
            'upozorneni': salon.upozorneni_plateb.select_related('odeslal')[:20],
            'audity': SalonAuditLog.objects.filter(salon=salon)[:50],
            'chyby': TechnickaChyba.objects.filter(salon=salon)[:50],
        },
    )


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
    }
    form = PartnerNastaveniForm(request.POST, instance=partner)
    if form.is_valid():
        form.save()
        log_superadmin(salon, request.user, 'Upraveno nastavení partnera.', pred=pred)
        messages.success(request, 'Nastavení partnera bylo uloženo.')
    else:
        messages.error(request, 'Nastavení se nepodařilo uložit: ' + '; '.join(
            error for errors in form.errors.values() for error in errors
        ))
    return redirect('partner_admin:detail', salon_id=salon.id)


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
        return redirect('partner_admin:detail', salon_id=salon.id)
    if partner.stav != PartnerNastaveni.STAV_BLOCKED:
        partner.stav = PartnerNastaveni.STAV_BLOCKED
        partner.duvod_blokace = form.cleaned_data['duvod']
        partner.save()
        log_superadmin(salon, request.user, 'Salon ručně přepnut na BLOCKED.', po={'stav': 'blocked'})
    messages.warning(request, 'Salon je BLOCKED. Jeho API nyní vrací stav 423.')
    return redirect('partner_admin:detail', salon_id=salon.id)


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
    return redirect('partner_admin:detail', salon_id=salon.id)


@superadmin_required
@require_POST
def potvrdit_platbu(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    form = PlatbaForm(request.POST)
    if form.is_valid():
        try:
            oznac_platbu(
                salon,
                request.user,
                form.cleaned_data['zaplaceno_dne'],
                form.cleaned_data['prijata_castka'],
                form.cleaned_data['poznamka'],
            )
            messages.success(
                request,
                'Hotovo: období označeno jako ZAPLACENO. Aktuální období je nové NEZAPLACENO.',
            )
        except Exception as exc:
            messages.error(request, f'Platbu nelze uložit: {exc}')
    else:
        messages.error(request, 'Zkontrolujte datum a částku platby.')
    return redirect('partner_admin:detail', salon_id=salon.id)


@superadmin_required
@require_POST
def odeslat_upozorneni(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    partner = _partner(salon)
    if not partner.fakturacni_email:
        messages.error(request, 'Doplňte fakturační e-mail.')
        return redirect('partner_admin:detail', salon_id=salon.id)

    form = UpozorneniForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Doplňte předmět a text upozornění.')
        return redirect('partner_admin:detail', salon_id=salon.id)
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
    return redirect('partner_admin:detail', salon_id=salon.id)


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
        majitel.set_password(form.cleaned_data['nove_heslo'])
        majitel.save(update_fields=['password_hash'])
        majitel.sessiony.all().delete()
        log_superadmin(
            salon,
            request.user,
            f'Resetováno heslo účtu {majitel.prihlasovaci_jmeno}; všechny relace zrušeny.',
            kategorie='ucty',
            objekt_typ='Zamestnanec',
            objekt_id=majitel.id,
        )
        messages.success(request, f'Heslo účtu {majitel.prihlasovaci_jmeno} bylo resetováno.')
    else:
        messages.error(request, 'Heslo musí mít alespoň 10 znaků.')
    return redirect('partner_admin:detail', salon_id=salon.id)


@superadmin_required
@require_POST
def vyresit_chybu(request, chyba_id):
    chyba = get_object_or_404(TechnickaChyba, pk=chyba_id)
    chyba.vyreseno = True
    chyba.save(update_fields=['vyreseno'])
    if not chyba.salon_id:
        return redirect('partner_admin:dashboard')
    return redirect('partner_admin:detail', salon_id=chyba.salon_id)
