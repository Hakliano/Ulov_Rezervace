from pathlib import Path

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .dokumentace_models import REZIM_MOJE, REZIM_SDILENE, DokumentSlozka, DokumentSoubor
from .dokumentace_services import (
    assert_cisteni,
    assert_sprava,
    precti_obsah,
    duplicitni_slozka,
    duplicitni_soubor,
    lze_presunout_slozku,
    muze_cist_soubor,
    muze_spravovat_rezim,
    muze_spravovat_soubor,
    nove_ulozene_jmeno,
    over_soubor,
    pocet_polozek_ve_slozce,
    queryset_slozek,
    rezim_vlastnik,
    soubor_mime,
    strom_slozek,
    vycisti_nazev,
)
from .views import login_required_view


def _dok_url(rezim, vlastnik, slozka=None):
    q = f'rezim={rezim}'
    if rezim == REZIM_MOJE:
        q += f'&vlastnik={vlastnik.pk}'
    if slozka:
        q += f'&slozka={slozka.pk}'
    return f'{reverse("dokumentace")}?{q}'


@login_required_view
def dokumentace(request):
    rezim, vlastnik = rezim_vlastnik(
        request.user,
        (request.GET.get('rezim') or REZIM_SDILENE).strip(),
        request.GET.get('vlastnik'),
    )
    slozka = None
    raw_slozka = request.GET.get('slozka')
    if raw_slozka and str(raw_slozka).isdigit():
        slozka = get_object_or_404(DokumentSlozka, pk=int(raw_slozka))
        assert_cisteni(request.user, slozka)
        if slozka.rezim != rezim:
            raise PermissionDenied
        if rezim == REZIM_MOJE and slozka.vlastnik_id != vlastnik.pk:
            raise PermissionDenied

    vsechny = list(queryset_slozek(rezim, vlastnik))
    strom = strom_slozek(vsechny)
    soubory = []
    if slozka:
        soubory = list(
            DokumentSoubor.objects.filter(slozka=slozka).select_related('vlastnik').order_by('nazev'),
        )

    uzivatele_volba = []
    if request.user.is_superuser:
        uzivatele_volba = list(User.objects.filter(is_active=True).order_by('username'))

    return render(request, 'dokumentace.html', {
        'rezim': rezim,
        'vlastnik_kontext': vlastnik,
        'aktualni_slozka': slozka,
        'strom': strom,
        'soubory': soubory,
        'muze_spravovat': muze_spravovat_rezim(request.user, rezim, vlastnik),
        'uzivatele_volba': uzivatele_volba,
        'slozky_k_presunu': vsechny,
        'REZIM_SDILENE': REZIM_SDILENE,
        'REZIM_MOJE': REZIM_MOJE,
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def dokumentace_slozka_nova(request):
    rezim, vlastnik = rezim_vlastnik(
        request.user,
        request.POST.get('rezim') or request.GET.get('rezim') or REZIM_SDILENE,
        request.POST.get('vlastnik') or request.GET.get('vlastnik'),
    )
    if not muze_spravovat_rezim(request.user, rezim, vlastnik):
        raise PermissionDenied
    parent = None
    parent_id = request.POST.get('parent') or request.GET.get('parent')
    if parent_id and str(parent_id).isdigit():
        parent = get_object_or_404(DokumentSlozka, pk=int(parent_id))
        assert_sprava(request.user, parent)
        rezim = parent.rezim
        if rezim == REZIM_MOJE:
            vlastnik = parent.vlastnik
    elif request.method == 'GET':
        raw_slozka = request.GET.get('slozka')
        if raw_slozka and str(raw_slozka).isdigit():
            parent = get_object_or_404(DokumentSlozka, pk=int(raw_slozka))
            assert_sprava(request.user, parent)

    if request.method != 'POST':
        return redirect(_dok_url(rezim, vlastnik, parent))
    try:
        nazev = vycisti_nazev(request.POST.get('nazev'))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect(_dok_url(rezim, vlastnik, parent))
    vlastnik_id = vlastnik.pk if rezim == REZIM_MOJE else None
    if duplicitni_slozka(nazev, parent.pk if parent else None, rezim, vlastnik_id):
        messages.error(request, 'Složka s tímto názvem už existuje.')
        return redirect(_dok_url(rezim, vlastnik, parent))
    slozka = DokumentSlozka.objects.create(
        nazev=nazev,
        parent=parent,
        rezim=rezim,
        vlastnik_id=vlastnik_id,
        vytvoril=request.user,
    )
    messages.success(request, 'Složka je vytvořená.')
    return redirect(_dok_url(rezim, vlastnik, slozka))


@login_required_view
@require_POST
def dokumentace_slozka_prejmenovat(request, pk):
    slozka = get_object_or_404(DokumentSlozka, pk=pk)
    assert_sprava(request.user, slozka)
    vlastnik = slozka.vlastnik or request.user
    try:
        nazev = vycisti_nazev(request.POST.get('nazev'))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka.parent))
    vlastnik_id = slozka.vlastnik_id if slozka.rezim == REZIM_MOJE else None
    if duplicitni_slozka(nazev, slozka.parent_id, slozka.rezim, vlastnik_id, vynechat_pk=slozka.pk):
        messages.error(request, 'Složka s tímto názvem už existuje.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    slozka.nazev = nazev
    slozka.save(update_fields=['nazev', 'upraveno'])
    messages.success(request, 'Složka je přejmenovaná.')
    return redirect(_dok_url(slozka.rezim, vlastnik, slozka))


@login_required_view
@require_POST
def dokumentace_slozka_presunout(request, pk):
    slozka = get_object_or_404(DokumentSlozka, pk=pk)
    assert_sprava(request.user, slozka)
    vlastnik = slozka.vlastnik or request.user
    raw_cil = (request.POST.get('cil_parent') or '').strip()
    cil_parent = None
    if raw_cil and raw_cil.isdigit():
        cil_parent = get_object_or_404(DokumentSlozka, pk=int(raw_cil))
        assert_sprava(request.user, cil_parent)
        if cil_parent.rezim != slozka.rezim:
            messages.error(request, 'Nelze přesunout mezi různými režimy.')
            return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    if not lze_presunout_slozku(slozka, cil_parent):
        messages.error(request, 'Složku nelze přesunout do sebe nebo do vlastní podsložky.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    vlastnik_id = slozka.vlastnik_id if slozka.rezim == REZIM_MOJE else None
    if duplicitni_slozka(slozka.nazev, cil_parent.pk if cil_parent else None, slozka.rezim, vlastnik_id, vynechat_pk=slozka.pk):
        messages.error(request, 'V cíli už složka se stejným názvem existuje.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    slozka.parent = cil_parent
    slozka.save(update_fields=['parent', 'upraveno'])
    messages.success(request, 'Složka je přesunutá.')
    return redirect(_dok_url(slozka.rezim, vlastnik, slozka))


@login_required_view
@require_POST
def dokumentace_slozka_smazat(request, pk):
    slozka = get_object_or_404(DokumentSlozka, pk=pk)
    assert_sprava(request.user, slozka)
    vlastnik = slozka.vlastnik or request.user
    ma_obsah = pocet_polozek_ve_slozce(slozka) > 0
    if ma_obsah and request.POST.get('potvrdit') != '1':
        messages.error(request, 'Potvrďte smazání neprázdné složky včetně veškerého obsahu.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    parent = slozka.parent
    rezim_del = slozka.rezim
    _smaz_slozku_rekurzivne(slozka)
    messages.success(request, 'Složka je smazaná.')
    return redirect(_dok_url(rezim_del, vlastnik, parent))


def _smaz_slozku_rekurzivne(slozka: DokumentSlozka):
    for child in list(slozka.deti.all()):
        _smaz_slozku_rekurzivne(child)
    for soubor in list(slozka.soubory.all()):
        _smaz_soubor_ze_disku(soubor)
        soubor.delete()
    slozka.delete()


def _smaz_soubor_ze_disku(soubor: DokumentSoubor):
    if soubor.soubor:
        soubor.soubor.delete(save=False)


@login_required_view
@require_POST
def dokumentace_nahrat(request):
    slozka_id = request.POST.get('slozka')
    if not slozka_id or not str(slozka_id).isdigit():
        messages.error(request, 'Vyberte složku pro nahrání.')
        return redirect(reverse('dokumentace'))
    slozka = get_object_or_404(DokumentSlozka, pk=int(slozka_id))
    assert_sprava(request.user, slozka)
    vlastnik = slozka.vlastnik or request.user
    upload = request.FILES.get('soubor')
    if not upload:
        messages.error(request, 'Vyberte soubor.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    nazev = Path(upload.name).name
    if duplicitni_soubor(nazev, slozka.pk):
        messages.error(request, 'Soubor se stejným názvem už ve složce je. Přejmenujte ho nebo smažte původní.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    try:
        pripona, data = over_soubor(upload, nazev)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    ulozene = nove_ulozene_jmeno(pripona)
    zaznam = DokumentSoubor(
        slozka=slozka,
        nazev=nazev,
        ulozene_jmeno=ulozene,
        pripona=pripona,
        velikost=len(data),
        vlastnik=request.user,
    )
    zaznam.soubor.save(ulozene, ContentFile(data), save=False)
    zaznam.save()
    messages.success(request, 'Soubor je nahraný.')
    return redirect(_dok_url(slozka.rezim, vlastnik, slozka))


@login_required_view
@require_GET
def dokumentace_stahnout(request, pk):
    soubor = get_object_or_404(DokumentSoubor.objects.select_related('slozka'), pk=pk)
    if not muze_cist_soubor(request.user, soubor):
        raise PermissionDenied
    response = HttpResponse(precti_obsah(soubor), content_type=soubor_mime(soubor.pripona))
    response['Content-Disposition'] = f'attachment; filename="{soubor.nazev}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required_view
@require_POST
def dokumentace_soubor_prejmenovat(request, pk):
    soubor = get_object_or_404(DokumentSoubor.objects.select_related('slozka'), pk=pk)
    if not muze_spravovat_soubor(request.user, soubor):
        raise PermissionDenied
    slozka = soubor.slozka
    vlastnik = slozka.vlastnik or request.user
    raw = (request.POST.get('nazev') or '').strip()
    if not raw:
        messages.error(request, 'Zadejte název.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    nazev = Path(raw).name
    try:
        vycisti_nazev(nazev)
        ext = Path(nazev).suffix.lower().lstrip('.')
        if ext != soubor.pripona and not (ext == 'jpeg' and soubor.pripona == 'jpg'):
            raise ValidationError('Příponu nelze změnit — použijte stejný typ souboru.')
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    if duplicitni_soubor(nazev, slozka.pk, vynechat_pk=soubor.pk):
        messages.error(request, 'Soubor s tímto názvem už ve složce je.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    soubor.nazev = nazev
    soubor.save(update_fields=['nazev', 'upraveno'])
    messages.success(request, 'Soubor je přejmenovaný.')
    return redirect(_dok_url(slozka.rezim, vlastnik, slozka))


@login_required_view
@require_POST
def dokumentace_soubor_presunout(request, pk):
    soubor = get_object_or_404(DokumentSoubor.objects.select_related('slozka'), pk=pk)
    if not muze_spravovat_soubor(request.user, soubor):
        raise PermissionDenied
    slozka = soubor.slozka
    vlastnik = slozka.vlastnik or request.user
    raw_cil = (request.POST.get('cil_slozka') or '').strip()
    if not raw_cil.isdigit():
        messages.error(request, 'Vyberte cílovou složku.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    cil = get_object_or_404(DokumentSlozka, pk=int(raw_cil))
    assert_sprava(request.user, cil)
    if cil.rezim != slozka.rezim:
        messages.error(request, 'Nelze přesunout mezi různými režimy.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    if rezim_moje_odlisny(cil, slozka):
        messages.error(request, 'Nelze přesunout do cizího soukromého prostoru.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    if duplicitni_soubor(soubor.nazev, cil.pk, vynechat_pk=soubor.pk):
        messages.error(request, 'V cílové složce už soubor se stejným názvem je.')
        return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
    soubor.slozka = cil
    soubor.save(update_fields=['slozka', 'upraveno'])
    messages.success(request, 'Soubor je přesunutý.')
    return redirect(_dok_url(slozka.rezim, vlastnik, cil))


def rezim_moje_odlisny(a: DokumentSlozka, b: DokumentSlozka) -> bool:
    if a.rezim == REZIM_MOJE and b.rezim == REZIM_MOJE:
        return a.vlastnik_id != b.vlastnik_id
    return False


@login_required_view
@require_POST
def dokumentace_soubor_smazat(request, pk):
    soubor = get_object_or_404(DokumentSoubor.objects.select_related('slozka'), pk=pk)
    if not muze_spravovat_soubor(request.user, soubor):
        raise PermissionDenied
    slozka = soubor.slozka
    vlastnik = slozka.vlastnik or request.user
    _smaz_soubor_ze_disku(soubor)
    soubor.delete()
    messages.success(request, 'Soubor je smazaný.')
    return redirect(_dok_url(slozka.rezim, vlastnik, slozka))
