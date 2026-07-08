from datetime import datetime, timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rezervace.models import (
    BlokaceCasu,
    NoShowZaznam,
    Rezervace,
    RezervaceHistorie,
    RezervacniNastaveni,
    RezervaceSluzba,
    SalonAuditLog,
    SalonVyjimka,
    SouhlasGDPR,
    Zakaznik,
    ZakaznikSession,
    Zamestnanec,
    ZamestnanecAbsence,
)
from rezervace.notifikace_defaults import (
    MANUAL_TYP_NOSHOW,
    MANUAL_TYP_PLATBA,
    get_manual_notifikace,
)
from rezervace.serializers import (
    AdminRezervaceCreateSerializer,
    AdminRezervaceSerializer,
    BlokaceCasuSerializer,
    EmailNastaveniSerializer,
    NoShowZaznamSerializer,
    RezervaceCreateSerializer,
    RezervaceHistorieSerializer,
    RezervaceSerializer,
    RezervacniNastaveniSerializer,
    SalonAuditLogSerializer,
    SalonVyjimkaSerializer,
    SluzbaPublicSerializer,
    ZakaznikRegistraceSerializer,
    ZakaznikPrihlaseniSerializer,
    ZamestnanecAbsenceSerializer,
    ZamestnanecDetailSerializer,
    ZamestnanecPublicSerializer,
    ZamestnanecSerializer,
    ZamestnanecWriteSerializer,
)
from rezervace.services.audit import audit_actor, log_audit, log_rezervace_audit
from rezervace.services.availability import (
    celkova_delka_sluzby,
    generuj_terminy,
    prirad_zamestnance,
    salon_je_zavreny,
)
from rezervace.services.emails import (
    email_nove_heslo,
    email_potvrzeni,
    email_storno,
    email_test,
    email_vyzva_k_potvrzeni,
    generate_heslo,
    get_email_config,
    _potvrzeni_url,
    _storno_url,
)
from rezervace.services.ics import generuj_ics
from salons.models import CenikPolozka, Salon
from salons.permissions import MajitelPermission, StaffPermission
from rezervace.services.gdpr_admin import export_zakaznik_data, vymaz_zakaznik_na_zadost
from rezervace.services.gdpr_audit import log_gdpr_audit
from rezervace.services.gdpr_consent import aktualni_zasady_verze, zaloguj_souhlas_gdpr
from rezervace.throttles import (
    EmailPotvrzeniRateThrottle,
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RezervaceRateThrottle,
)
from rezervace.services.staff_auth import (
    deaktivovat_zamestnance,
    get_staff_from_request,
    je_majitel,
    muze_rezervaci,
    odhlasit_staff,
    prihlasit_staff,
    staff_do_dict,
)


def get_salon(pk):
    return get_object_or_404(Salon, pk=pk)


def log_historie(rezervace, kdo, popis, pred=None, po=None, request=None):
    actor = audit_actor(request, rezervace.salon_id) if request else kdo
    RezervaceHistorie.objects.create(
        rezervace=rezervace, kdo=actor, popis=popis,
        data_pred=pred, data_po=po,
    )
    log_rezervace_audit(rezervace, actor, popis, pred=pred, po=po)


def _audit(request, salon, kategorie, popis, objekt_typ='', objekt_id=None, pred=None, po=None):
    actor = audit_actor(request, salon.pk)
    text = popis if popis.startswith(actor) else f'{actor}: {popis}'
    log_audit(salon, actor, kategorie, text, objekt_typ=objekt_typ, objekt_id=objekt_id, pred=pred, po=po)


def _kontrola_rezervace(request, salon_pk, rezervace):
    staff = get_staff_from_request(request, salon_pk)
    if staff and not muze_rezervaci(staff, rezervace):
        return Response({'detail': 'K této rezervaci nemáte přístup.'}, status=403)
    return None


def vytvor_rezervaci(salon, data, typ_vytvoreni='online', stav=None, kdo='systém', request=None):
    sluzby_ids = data['sluzby']
    sluzby = list(CenikPolozka.objects.filter(salon=salon, pk__in=sluzby_ids, aktivni=True))
    if len(sluzby) != len(sluzby_ids):
        raise ValueError('Neplatné služby.')

    datum = data['datum']
    if isinstance(datum, str):
        datum = datetime.strptime(datum, '%Y-%m-%d').date()

    cas_parts = data['cas'].split(':')
    start_naive = datetime.combine(datum, datetime.strptime(data['cas'], '%H:%M').time())
    start = timezone.make_aware(start_naive)
    delka = celkova_delka_sluzby(sluzby)
    end = start + timedelta(minutes=delka)

    if start <= timezone.now():
        raise ValueError('Nelze rezervovat v minulosti.')

    zamestnanec_id = data.get('zamestnanec_id')
    zamestnanec = prirad_zamestnance(salon, datum, start, end, zamestnanec_id)
    if not zamestnanec:
        raise ValueError('Termín není dostupný.')

    zakaznik = None
    email = data.get('email', '')
    nick = data.get('nick', '')

    if data.get('session_token'):
        try:
            session = ZakaznikSession.objects.select_related('zakaznik').get(
                token=data['session_token'], expirace__gt=timezone.now(),
            )
            if session.zakaznik.salon_id == salon.id:
                zakaznik = session.zakaznik
        except ZakaznikSession.DoesNotExist:
            pass

    if email:
        from rezervace.services.email_reputace import je_blokovan_v_salonu
        if je_blokovan_v_salonu(email, salon.id):
            raise ValueError('Váš účet je blokován. Kontaktujte salon.')

    if not zakaznik and email:
        from rezervace.services.gdpr import email_hash
        eh = email_hash(email)
        zakaznik, created = Zakaznik.objects.get_or_create(
            salon=salon, email=email,
            defaults={
                'nick': nick or email.split('@')[0],
                'email_hash': eh,
                'gdpr_souhlas': bool(data.get('ochrana_udaju_souhlas', True)),
                'gdpr_datum': timezone.now(),
                'marketing_souhlas': False,
            },
        )
        if created is False:
            upd = []
            if nick:
                zakaznik.nick = nick
                upd.append('nick')
            if eh and not zakaznik.email_hash:
                zakaznik.email_hash = eh
                upd.append('email_hash')
            if upd:
                zakaznik.save(update_fields=upd)

    if zakaznik and zakaznik.blokovan:
        raise ValueError('Váš účet je blokován. Kontaktujte salon.')

    try:
        nastaveni = salon.rezervacni_nastaveni
        if stav is None:
            if typ_vytvoreni == 'online':
                stav = 'ceka'
            else:
                stav = 'potvrzeno' if nastaveni.auto_potvrzeni else 'ceka'
    except RezervacniNastaveni.DoesNotExist:
        stav = stav or ('ceka' if typ_vytvoreni == 'online' else 'potvrzeno')

    potvrzeni_exspirace = None
    if stav == 'ceka' and typ_vytvoreni == 'online':
        try:
            platnost = salon.rezervacni_nastaveni.potvrzeni_platnost_hodin or 24
        except Exception:
            platnost = 24
        potvrzeni_exspirace = timezone.now() + timedelta(hours=platnost)

    rezervace = Rezervace.objects.create(
        salon=salon,
        zakaznik=zakaznik,
        zamestnanec=zamestnanec,
        zacatek=start,
        konec=end,
        stav=stav,
        poznamka_zakaznika=data.get('poznamka') or data.get('poznamka_zakaznika', ''),
        poznamka_interni=data.get('poznamka_interni', ''),
        typ_vytvoreni=typ_vytvoreni,
        jmeno_host=nick if not zakaznik else '',
        email_host=email if not zakaznik else '',
        potvrzeni_exspirace=potvrzeni_exspirace,
    )

    for i, s in enumerate(sluzby):
        RezervaceSluzba.objects.create(rezervace=rezervace, sluzba=s, poradi=i)

    log_historie(rezervace, kdo, f'Vytvoření rezervace ({typ_vytvoreni})', request=request)
    email_odeslan = False
    try:
        if rezervace.stav == 'ceka' and typ_vytvoreni == 'online':
            email_odeslan = email_vyzva_k_potvrzeni(rezervace)
        elif rezervace.stav == 'potvrzeno':
            email_odeslan = email_potvrzeni(rezervace)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('E-mail se nepodařilo odeslat: %s', exc)

    rezervace._email_odeslan = email_odeslan
    return rezervace


def muze_stornovat(rezervace):
    if rezervace.stav not in ('ceka', 'potvrzeno'):
        return False, 'Rezervaci nelze stornovat.'
    try:
        nastaveni = rezervace.salon.rezervacni_nastaveni
        if nastaveni.storno_do_hodin is None:
            return False, 'Salon neumožňuje storno.'
        limit = rezervace.zacatek - timedelta(hours=nastaveni.storno_do_hodin)
        if timezone.now() > limit:
            return False, f'Storno je možné nejpozději {nastaveni.storno_do_hodin} h před termínem.'
    except RezervacniNastaveni.DoesNotExist:
        pass
    return True, ''


def muze_potvrdit(rezervace):
    if rezervace.stav != 'ceka':
        if rezervace.stav == 'potvrzeno':
            return False, 'Rezervace je již potvrzena.'
        return False, 'Rezervaci nelze potvrdit.'
    if rezervace.potvrzeni_exspirace and timezone.now() > rezervace.potvrzeni_exspirace:
        return False, 'Odkaz pro potvrzení vypršel. Vytvořte prosím novou rezervaci.'
    if rezervace.zacatek <= timezone.now():
        return False, 'Termín již nelze potvrdit.'
    return True, ''


class PersonelPublicView(APIView):
    """Veřejný seznam personálu pro web salonu."""

    def get(self, request, pk):
        salon = get_salon(pk)
        qs = Zamestnanec.objects.filter(
            salon=salon, zobrazit_na_webu=True,
        ).exclude(role=Zamestnanec.ROLE_MAJITEL).prefetch_related('rozvrh').order_by('poradi', 'id')
        return Response(ZamestnanecPublicSerializer(qs, many=True).data)


class RezervaceInfoView(APIView):
    def get(self, request, pk):
        salon = get_salon(pk)
        try:
            nastaveni = salon.rezervacni_nastaveni
            nast_data = RezervacniNastaveniSerializer(nastaveni).data
        except RezervacniNastaveni.DoesNotExist:
            nast_data = None

        sluzby = CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi')
        zamestnanci = Zamestnanec.objects.filter(
            salon=salon, aktivni=True,
        ).exclude(role=Zamestnanec.ROLE_MAJITEL).order_by('poradi')
        from rezervace.services.emails import get_email_config
        email_cfg = get_email_config(salon)

        return Response({
            'salon': {'id': salon.id, 'name': salon.name, 'address': salon.address, 'phone': salon.phone, 'email': salon.email},
            'nastaveni': nast_data,
            'sluzby': SluzbaPublicSerializer(sluzby, many=True).data,
            'zamestnanci': ZamestnanecSerializer(zamestnanci, many=True).data,
            'email_smtp': email_cfg['smtp_ready'],
            'email_odesilatel': email_cfg['from_email'],
            'gdpr': {
                'zasady_verze': aktualni_zasady_verze(salon),
                'jazyk': 'cs',
            },
        })


class VolneTerminyView(APIView):
    def get(self, request, pk):
        salon = get_salon(pk)
        datum_str = request.query_params.get('datum')
        sluzby_str = request.query_params.get('sluzby', '')
        zamestnanec_id = request.query_params.get('zamestnanec')

        if not datum_str or not sluzby_str:
            return Response({'detail': 'Parametry datum a sluzby jsou povinné.'}, status=400)

        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        if salon_je_zavreny(salon, datum):
            return Response({'datum': datum_str, 'zavreno': True, 'terminy': [], 'duvod': 'Salon je tento den zavřený.'})

        if not Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(role=Zamestnanec.ROLE_MAJITEL).exists():
            return Response({
                'datum': datum_str, 'zavreno': False, 'terminy': [],
                'duvod': 'Salon nemá nastavené zaměstnance. Doplňte je v administraci (Personál) nebo spusťte: python manage.py seed_rezervace',
            })

        sluzby_ids = [int(x) for x in sluzby_str.split(',') if x.strip()]
        z_id = int(zamestnanec_id) if zamestnanec_id and zamestnanec_id != 'any' else None

        terminy = generuj_terminy(salon, datum, sluzby_ids, z_id)
        duvod = ''
        if not terminy:
            aktivni = CenikPolozka.objects.filter(salon=salon, pk__in=sluzby_ids, aktivni=True).count()
            if aktivni != len(sluzby_ids):
                duvod = 'Vybraná služba není dostupná. Obnovte stránku a vyberte službu znovu.'
            else:
                duvod = 'Pro tento den není volný žádný termín. Zkuste jiný den nebo jiného pracovníka.'

        return Response({'datum': datum_str, 'zavreno': False, 'terminy': terminy, 'duvod': duvod})


class RezervaceCreateView(APIView):
    throttle_classes = [RezervaceRateThrottle]

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = RezervaceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            rezervace = vytvor_rezervaci(salon, d, typ_vytvoreni='online', kdo='zákazník', request=request)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        zaloguj_souhlas_gdpr(
            salon,
            SouhlasGDPR.TYP_REZERVACE,
            request,
            zakaznik=rezervace.zakaznik,
            rezervace=rezervace,
            email=d.get('email', ''),
            zasady_verze=d.get('zasady_verze'),
            jazyk=d.get('jazyk', 'cs'),
        )

        data = RezervaceSerializer(rezervace).data
        data['storno_url'] = _storno_url(rezervace)
        if rezervace.stav == 'ceka':
            data['potvrzeni_url'] = _potvrzeni_url(rezervace)
        from rezervace.services.emails import get_email_config
        email_cfg = get_email_config(salon)
        data['email_smtp'] = email_cfg['smtp_ready']
        data['email_odesilatel'] = email_cfg['from_email']
        data['email_odeslan'] = getattr(rezervace, '_email_odeslan', False)
        return Response(data, status=201)


class RezervaceStornoView(APIView):
    def post(self, request, pk, token):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, salon=salon, cancel_token=token)

        ok, msg = muze_stornovat(rezervace)
        if not ok:
            return Response({'detail': msg}, status=400)

        pred = {'stav': rezervace.stav}
        rezervace.stav = 'zakaznik_storno'
        rezervace.save(update_fields=['stav', 'aktualizovano'])
        log_historie(rezervace, 'zákazník', 'Storno přes odkaz', pred, {'stav': rezervace.stav}, request=request)

        try:
            email_storno(rezervace)
        except Exception:
            pass

        return Response({'ok': True, 'message': 'Rezervace byla zrušena.'})


class RezervacePotvrditView(APIView):
    throttle_classes = [EmailPotvrzeniRateThrottle]

    def post(self, request, pk, token):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, salon=salon, potvrzeni_token=token)

        ok, msg = muze_potvrdit(rezervace)
        if not ok:
            return Response({'detail': msg}, status=400)

        pred = {'stav': rezervace.stav}
        rezervace.stav = 'potvrzeno'
        rezervace.potvrzeni_exspirace = None
        rezervace.save(update_fields=['stav', 'potvrzeni_exspirace', 'aktualizovano'])
        log_historie(rezervace, 'zákazník', 'Potvrzení přes e-mail', pred, {'stav': rezervace.stav}, request=request)

        try:
            email_potvrzeni(rezervace)
        except Exception:
            pass

        data = RezervaceSerializer(rezervace).data
        data['storno_url'] = _storno_url(rezervace)
        return Response({'ok': True, 'message': 'Rezervace byla potvrzena.', 'rezervace': data})


class RezervacePotvrditInfoView(APIView):
    def get(self, request, pk, token):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, salon=salon, potvrzeni_token=token)
        ok, msg = muze_potvrdit(rezervace)
        return Response({
            'lze_potvrdit': ok,
            'detail': msg,
            'rezervace': RezervaceSerializer(rezervace).data,
            'jiz_potvrzeno': rezervace.stav == 'potvrzeno',
        })


class RezervaceStornoInfoView(APIView):
    def get(self, request, pk, token):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, salon=salon, cancel_token=token)
        ok, msg = muze_stornovat(rezervace)
        return Response({
            'rezervace': RezervaceSerializer(rezervace).data,
            'lze_stornovat': ok,
            'duvod': msg if not ok else '',
        })


class RezervaceIcsView(APIView):
    def get(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, salon=salon, pk=rezervace_id)
        if rezervace.stav != 'potvrzeno':
            return Response({'detail': 'Kalendář je dostupný až po potvrzení rezervace.'}, status=400)
        ics = generuj_ics(rezervace)
        response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="rezervace-{rezervace.id}.ics"'
        return response


class ZakaznikRegistraceView(APIView):
    def post(self, request, pk):
        salon = get_salon(pk)
        ser = ZakaznikRegistraceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        if not d['ochrana_udaju_souhlas']:
            return Response({'detail': 'Potvrzení Zásad ochrany osobních údajů je povinné.'}, status=400)

        from rezervace.services.gdpr import email_hash
        eh = email_hash(d['email'])
        zakaznik, created = Zakaznik.objects.update_or_create(
            salon=salon, email=d['email'],
            defaults={
                'nick': d['nick'],
                'email_hash': eh,
                'gdpr_souhlas': True,
                'gdpr_datum': timezone.now(),
                'marketing_souhlas': False,
            },
        )
        zakaznik.set_password(d['password'])
        zakaznik.save()

        zaloguj_souhlas_gdpr(
            salon,
            SouhlasGDPR.TYP_REGISTRACE,
            request,
            zakaznik=zakaznik,
            email=d['email'],
            zasady_verze=d.get('zasady_verze'),
            jazyk=d.get('jazyk', 'cs'),
        )

        session = ZakaznikSession.objects.create(
            zakaznik=zakaznik,
            expirace=timezone.now() + timedelta(days=30),
        )

        return Response({
            'ok': True,
            'token': str(session.token),
            'zakaznik': {'nick': zakaznik.nick, 'email': zakaznik.email},
        }, status=201 if created else 200)


class ZakaznikPrihlaseniView(APIView):
    throttle_classes = [LoginRateThrottle]

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = ZakaznikPrihlaseniSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            zakaznik = Zakaznik.objects.get(salon=salon, email=d['email'])
        except Zakaznik.DoesNotExist:
            return Response({
                'detail': 'Účet nenalezen. Zaregistrujte se, nebo použijte e-mail z vaší rezervace a „Zapomenuté heslo“.',
            }, status=404)

        if not zakaznik.ma_heslo:
            return Response({
                'detail': 'Účet ještě nemá heslo. Klikněte na „Zapomenuté heslo“ – nové heslo vám přijde e-mailem.',
            }, status=400)

        if not zakaznik.check_password(d['password']):
            return Response({'detail': 'Nesprávné heslo.'}, status=401)

        session = ZakaznikSession.objects.create(
            zakaznik=zakaznik,
            expirace=timezone.now() + timedelta(days=30),
        )

        return Response({
            'ok': True,
            'token': str(session.token),
            'zakaznik': {'nick': zakaznik.nick, 'email': zakaznik.email},
        })


class ZakaznikZapomenuteHesloView(APIView):
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request, pk):
        salon = get_salon(pk)
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'detail': 'E-mail je povinný.'}, status=400)

        message = (
            'Pokud je účet u tohoto salonu registrován, nové heslo bylo odesláno na e-mail.'
        )

        try:
            zakaznik = Zakaznik.objects.get(salon=salon, email=email)
        except Zakaznik.DoesNotExist:
            return Response({'ok': True, 'message': message})

        nove_heslo = generate_heslo()
        zakaznik.set_password(nove_heslo)
        zakaznik.save(update_fields=['password_hash'])

        email_odeslan = False
        email_chyba = ''
        try:
            email_odeslan = email_nove_heslo(zakaznik, nove_heslo)
        except Exception as exc:
            email_chyba = str(exc)

        if not email_odeslan:
            return Response({
                'ok': True,
                'message': (
                    'E-mail se nepodařilo odeslat. Nové heslo zobrazujeme níže – '
                    'zkontrolujte SMTP v administraci webu (záložka E-mail).'
                ),
                'email_odeslan': False,
                'email_chyba': email_chyba,
                'heslo': nove_heslo,
            })

        return Response({
            'ok': True,
            'message': message,
            'email_odeslan': True,
        })


class ZakaznikMojeView(APIView):
    def get(self, request, pk):
        salon = get_salon(pk)
        token = request.query_params.get('token')
        if not token:
            return Response({'detail': 'Token je povinný.'}, status=400)

        try:
            session = ZakaznikSession.objects.select_related('zakaznik').get(
                token=token, expirace__gt=timezone.now(),
            )
        except ZakaznikSession.DoesNotExist:
            return Response({'detail': 'Neplatný nebo expirovaný token.'}, status=401)

        if session.zakaznik.salon_id != salon.id:
            return Response({'detail': 'Token nepatří tomuto salonu.'}, status=403)

        budouci = Rezervace.objects.filter(
            zakaznik=session.zakaznik,
            zacatek__gte=timezone.now(),
            stav__in=('ceka', 'potvrzeno'),
        ).order_by('zacatek')
        historie = Rezervace.objects.filter(
            zakaznik=session.zakaznik,
        ).exclude(stav__in=('ceka', 'potvrzeno')).order_by('-zacatek')[:20]

        return Response({
            'zakaznik': {'nick': session.zakaznik.nick, 'email': session.zakaznik.email},
            'budouci': RezervaceSerializer(budouci, many=True).data,
            'historie': RezervaceSerializer(historie, many=True).data,
        })


# --- Admin views ---

class StaffPrihlaseniView(APIView):
    throttle_classes = [LoginRateThrottle]

    def post(self, request, pk):
        salon = get_salon(pk)
        try:
            session, staff = prihlasit_staff(
                salon,
                request.data.get('prihlasovaci_jmeno', ''),
                request.data.get('password', ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({
            'ok': True,
            'token': str(session.token),
            'staff': staff_do_dict(staff),
        })


class StaffOdhlaseniView(APIView):
    def post(self, request, pk):
        odhlasit_staff(request.headers.get('X-Staff-Token', ''))
        return Response({'ok': True})


class StaffMeView(APIView):
    permission_classes = [StaffPermission]

    def get(self, request, pk):
        staff = get_staff_from_request(request, pk)
        if not staff:
            return Response({'detail': 'Nepřihlášen.'}, status=401)
        return Response(staff_do_dict(staff))


class AdminEmailNastaveniView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        if not nast.smtp_user and salon.email:
            nast.smtp_user = salon.email
        data = EmailNastaveniSerializer(nast).data
        cfg = get_email_config(salon)
        data['email_odesilatel'] = cfg['from_email']
        data['smtp_aktivni'] = cfg['smtp_ready']
        return Response(data)

    def put(self, request, pk):
        salon = get_salon(pk)
        nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        pred = EmailNastaveniSerializer(nast).data
        ser = EmailNastaveniSerializer(nast, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        nast.email_odesilatel = salon.email
        nast.email_jmeno_odesilatele = salon.name
        nast.save(update_fields=['email_odesilatel', 'email_jmeno_odesilatele'])
        data = EmailNastaveniSerializer(nast).data
        data['email_odesilatel'] = get_email_config(salon)['from_email']
        data['smtp_aktivni'] = get_email_config(salon)['smtp_ready']
        _audit(request, salon, 'email', 'změna nastavení e-mailu', pred=pred, po=data)
        return Response(data)


class AdminEmailTestView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        prijemce = request.data.get('email', '').strip() or salon.email
        if not prijemce:
            return Response({'detail': 'Zadejte e-mail pro test.'}, status=400)
        try:
            email_test(salon, prijemce)
        except Exception as exc:
            return Response({'detail': f'Odeslání selhalo: {exc}'}, status=400)
        _audit(request, salon, 'email', f'odeslání testovacího e-mailu na {prijemce}')
        return Response({'ok': True, 'message': f'Test odeslán na {prijemce}.'})


class AdminNastaveniView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        nastaveni, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        return Response(RezervacniNastaveniSerializer(nastaveni).data)

    def put(self, request, pk):
        salon = get_salon(pk)
        nastaveni, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        pred = RezervacniNastaveniSerializer(nastaveni).data
        ser = RezervacniNastaveniSerializer(nastaveni, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        po = ser.data
        _audit(request, salon, 'nastaveni', 'změna nastavení rezervací', pred=pred, po=po)
        return Response(po)


class AdminZamestnanciView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        qs = Zamestnanec.objects.filter(salon=salon).prefetch_related('rozvrh', 'absence')
        from rezervace.services.oteviraci_doba import vypocti_oteviraci_dobu_tydne
        from salons.serializers import OteviraciDobaSerializer
        return Response({
            'zamestnanci': ZamestnanecDetailSerializer(qs, many=True).data,
            'oteviraci_doba_salonu': OteviraciDobaSerializer(
                vypocti_oteviraci_dobu_tydne(salon), many=True,
            ).data,
        })

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = ZamestnanecWriteSerializer(data=request.data, context={'salon': salon})
        ser.is_valid(raise_exception=True)
        z = ser.save()
        po = ZamestnanecDetailSerializer(z).data
        _audit(request, salon, 'zamestnanec', f'přidání zaměstnance ({z.jmeno})',
               objekt_typ='zamestnanec', objekt_id=z.id, po=po)
        return Response(po, status=201)


class AdminZamestnanecDetailView(APIView):
    permission_classes = [MajitelPermission]

    def put(self, request, pk, zamestnanec_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        pred = ZamestnanecDetailSerializer(z).data
        byl_aktivni = z.aktivni
        ser = ZamestnanecWriteSerializer(z, data=request.data, partial=True, context={'salon': salon})
        ser.is_valid(raise_exception=True)
        ser.save()
        z.refresh_from_db()
        po = ZamestnanecDetailSerializer(z).data
        if byl_aktivni and not z.aktivni:
            log_gdpr_audit(
                request, salon, 'deaktivace účtu', z.jmeno,
                objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po,
            )
        elif not byl_aktivni and z.aktivni:
            log_gdpr_audit(
                request, salon, 'aktivace účtu', z.jmeno,
                objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po,
            )
        if 'rozvrh' in request.data:
            _audit(request, salon, 'oteviraci_doba', f'změna otevírací doby ({z.jmeno})',
                   objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po)
        else:
            _audit(request, salon, 'zamestnanec', f'změna zaměstnance ({z.jmeno})',
                   objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po)
        return Response(po)

    def delete(self, request, pk, zamestnanec_id):
        """Místo smazání deaktivuje účet — audit a historie rezervací zůstanou."""
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        pred = ZamestnanecDetailSerializer(z).data
        try:
            deaktivovat_zamestnance(z)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        po = ZamestnanecDetailSerializer(z).data
        _audit(request, salon, 'zamestnanec', f'deaktivace účtu ({z.jmeno})',
               objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po)
        log_gdpr_audit(
            request, salon, 'deaktivace účtu', z.jmeno,
            objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po,
        )
        return Response({'ok': True, 'deaktivovan': True, 'zamestnanec': po})


class AdminZamestnanecDeaktivovatView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk, zamestnanec_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        pred = ZamestnanecDetailSerializer(z).data
        try:
            deaktivovat_zamestnance(z)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        po = ZamestnanecDetailSerializer(z).data
        _audit(request, salon, 'zamestnanec', f'deaktivace účtu ({z.jmeno})',
               objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po)
        log_gdpr_audit(
            request, salon, 'deaktivace účtu', z.jmeno,
            objekt_typ='zamestnanec', objekt_id=z.id, pred=pred, po=po,
        )
        return Response({'ok': True, 'zamestnanec': po})


class AdminZamestnanecAbsenceView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk, zamestnanec_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        return Response(ZamestnanecAbsenceSerializer(z.absence.all(), many=True).data)

    def post(self, request, pk, zamestnanec_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        ser = ZamestnanecAbsenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        absence = ZamestnanecAbsence.objects.create(zamestnanec=z, **ser.validated_data)
        po = ZamestnanecAbsenceSerializer(absence).data
        _audit(request, salon, 'absence', f'přidání absence ({z.jmeno})',
               objekt_typ='absence', objekt_id=absence.id, po=po)
        return Response(po, status=201)


class AdminZamestnanecAbsenceDetailView(APIView):
    permission_classes = [MajitelPermission]

    def delete(self, request, pk, zamestnanec_id, absence_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=salon)
        absence = get_object_or_404(ZamestnanecAbsence, pk=absence_id, zamestnanec=z)
        pred = ZamestnanecAbsenceSerializer(absence).data
        absence.delete()
        _audit(request, salon, 'absence', f'smazání absence ({z.jmeno})',
               objekt_typ='absence', objekt_id=absence_id, pred=pred)
        return Response(status=204)


class AdminKalendarView(APIView):
    permission_classes = [StaffPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        staff = get_staff_from_request(request, pk)
        od = request.query_params.get('od')
        do = request.query_params.get('do')
        qs = Rezervace.objects.filter(salon=salon).prefetch_related('polozky__sluzba', 'zamestnanec')
        if staff and not je_majitel(staff):
            qs = qs.filter(zamestnanec=staff)
        if od:
            if len(od) <= 10:
                qs = qs.filter(zacatek__date__gte=datetime.strptime(od, '%Y-%m-%d').date())
            else:
                qs = qs.filter(zacatek__gte=od)
        if do:
            if len(do) <= 10:
                qs = qs.filter(zacatek__date__lte=datetime.strptime(do, '%Y-%m-%d').date())
            else:
                qs = qs.filter(zacatek__lte=do)
        blokace = BlokaceCasu.objects.filter(salon=salon)
        if od:
            blokace = blokace.filter(zacatek__gte=od)
        if do:
            blokace = blokace.filter(zacatek__lte=do)

        return Response({
            'rezervace': AdminRezervaceSerializer(qs.order_by('zacatek'), many=True).data,
            'blokace': BlokaceCasuSerializer(blokace, many=True).data,
        })


class AdminRezervaceCreateView(APIView):
    permission_classes = [StaffPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = AdminRezervaceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            rezervace = vytvor_rezervaci(
                salon, d,
                typ_vytvoreni=d.get('typ_vytvoreni', 'zamestnanec'),
                stav=d.get('stav', 'potvrzeno'),
                kdo='admin',
                request=request,
            )
            if d.get('poznamka_interni'):
                rezervace.poznamka_interni = d['poznamka_interni']
                rezervace.save(update_fields=['poznamka_interni'])
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        return Response(AdminRezervaceSerializer(rezervace).data, status=201)


class AdminRezervaceDetailView(APIView):
    permission_classes = [StaffPermission]

    def patch(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon=salon)
        denied = _kontrola_rezervace(request, pk, rezervace)
        if denied:
            return denied
        if request.data.get('stav') == 'no_show':
            return Response(
                {'detail': 'NO-show nastavte v kalendáři — zobrazí se volby pro e-mail a blokaci.'},
                status=400,
            )
        pred = AdminRezervaceSerializer(rezervace).data

        allowed = ['stav', 'poznamka_interni', 'poznamka_zakaznika', 'zamestnanec',
                   'skutecna_delka_minut', 'dokonceno_at']
        stary_stav = rezervace.stav
        for field in allowed:
            if field in request.data:
                setattr(rezervace, field, request.data[field])

        if rezervace.zamestnanec and rezervace.zamestnanec.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Majitel neprovádí služby — rezervaci přiřaďte zaměstnanci.'},
                status=400,
            )

        if request.data.get('stav') == 'dokonceno' and not rezervace.dokonceno_at:
            rezervace.dokonceno_at = timezone.now()

        if stary_stav == 'ceka' and rezervace.stav == 'potvrzeno':
            rezervace.potvrzeni_exspirace = None

        rezervace.save()
        po = AdminRezervaceSerializer(rezervace).data
        log_historie(rezervace, 'admin', 'změna rezervace', pred, po, request=request)
        if stary_stav == 'ceka' and rezervace.stav == 'potvrzeno':
            try:
                email_potvrzeni(rezervace)
            except Exception:
                pass
        return Response(po)

    def delete(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon=salon)
        denied = _kontrola_rezervace(request, pk, rezervace)
        if denied:
            return denied
        pred = {'stav': rezervace.stav}
        rezervace.stav = 'salon_storno'
        rezervace.save(update_fields=['stav', 'aktualizovano'])
        log_historie(rezervace, 'admin', 'zrušení rezervace (salon)', pred, request=request)
        try:
            email_storno(rezervace, kdo='salon')
        except Exception:
            pass
        return Response({'ok': True})


class AdminRezervaceDokoncenoView(APIView):
    permission_classes = [StaffPermission]

    def post(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon=salon)
        denied = _kontrola_rezervace(request, pk, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze dokončit.'}, status=400)

        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'dokonceno'
        if not rezervace.dokonceno_at:
            rezervace.dokonceno_at = timezone.now()
        rezervace.save(update_fields=['stav', 'dokonceno_at', 'aktualizovano'])
        po = AdminRezervaceSerializer(rezervace).data
        log_historie(rezervace, 'admin', 'rezervace proběhla', pred, po, request=request)
        return Response(po)


class AdminRezervaceNoShowView(APIView):
    permission_classes = [StaffPermission]

    def post(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(
            Rezervace, pk=rezervace_id, salon=salon,
        )
        denied = _kontrola_rezervace(request, pk, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze označit jako NO-show.'}, status=400)

        odeslat_upozorneni = bool(request.data.get('odeslat_upozorneni'))
        blokovat_email = bool(request.data.get('blokovat_email'))
        if blokovat_email and not je_majitel(get_staff_from_request(request, pk)):
            return Response({'detail': 'Blokaci e-mailu může provést jen majitelka.'}, status=403)

        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'no_show'
        rezervace.save(update_fields=['stav', 'aktualizovano'])

        sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
        from rezervace.services.gdpr import email_hash
        email_val = rezervace.kontaktni_email or ''
        zaznam = NoShowZaznam.objects.create(
            salon=salon,
            rezervace=rezervace,
            zakaznik=rezervace.zakaznik,
            jmeno=rezervace.kontaktni_jmeno,
            email=email_val,
            email_hash=email_hash(email_val) if email_val else '',
            zacatek=rezervace.zacatek,
            zamestnanec_jmeno=rezervace.zamestnanec.jmeno if rezervace.zamestnanec else '',
            sluzby=sluzby,
            zakaznik_blokovan=blokovat_email,
        )

        if rezervace.zakaznik:
            rezervace.zakaznik.no_show_pocet += 1
            rezervace.zakaznik.save(update_fields=['no_show_pocet'])

        from rezervace.services.email_reputace import aktualizuj_po_noshow, blokovat_v_salonu
        reputace = aktualizuj_po_noshow(rezervace.kontaktni_email or '', salon.id)
        if blokovat_email and rezervace.kontaktni_email:
            blokovat_v_salonu(rezervace.kontaktni_email, salon.id)
            reputace['blokovan_v_salonu'] = True
            zaznam.zakaznik_blokovan = True
            zaznam.save(update_fields=['zakaznik_blokovan'])

        email_odeslan = False
        if odeslat_upozorneni and rezervace.kontaktni_email:
            try:
                nastaveni = salon.rezervacni_nastaveni
                manual = get_manual_notifikace(nastaveni.notifikace, MANUAL_TYP_NOSHOW)
                if manual:
                    from rezervace.services.notifikace_email import email_notifikace
                    email_notifikace(rezervace, manual)
                    odeslane = list(rezervace.notifikace_odeslane or [])
                    nid = str(manual['id'])
                    if nid not in odeslane:
                        odeslane.append(nid)
                        rezervace.notifikace_odeslane = odeslane
                        rezervace.save(update_fields=['notifikace_odeslane'])
                    email_odeslan = True
                    zaznam.email_upozorneni_odeslan = True
                    zaznam.save(update_fields=['email_upozorneni_odeslan'])
            except Exception as exc:
                return Response({
                    'detail': f'NO-show uložen, ale e-mail se nepodařilo odeslat: {exc}',
                    'rezervace': AdminRezervaceSerializer(rezervace).data,
                    'zaznam': NoShowZaznamSerializer(zaznam).data,
                }, status=502)

        po = AdminRezervaceSerializer(rezervace).data
        log_historie(rezervace, 'admin', 'NO-show', pred, po, request=request)
        return Response({
            'rezervace': po,
            'zaznam': NoShowZaznamSerializer(zaznam).data,
            'email_odeslan': email_odeslan,
            'zakaznik_blokovan': blokovat_email or reputace.get('blokovan_v_salonu', False),
            'reputace': reputace,
        })


class AdminRezervacePlatbaView(APIView):
    permission_classes = [StaffPermission]

    def post(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon=salon)
        denied = _kontrola_rezervace(request, pk, rezervace)
        if denied:
            return denied
        if not rezervace.kontaktni_email:
            return Response({'detail': 'Rezervace nemá e-mail zákazníka.'}, status=400)

        castka = request.data.get('castka')
        ucet = (request.data.get('ucet') or request.data.get('cislo_uctu') or '').strip()
        vs = request.data.get('variabilni_symbol') or request.data.get('vs')
        if not castka or not ucet or vs is None or str(vs).strip() == '':
            return Response({'detail': 'Vyplňte částku, číslo účtu a variabilní symbol.'}, status=400)

        try:
            nastaveni = salon.rezervacni_nastaveni
            platba = get_manual_notifikace(nastaveni.notifikace, MANUAL_TYP_PLATBA)
            if not platba:
                return Response({'detail': 'Chybí nastavení 4. e-mailu (platba).'}, status=400)
            from rezervace.services.notifikace_email import email_platba_qr
            from rezervace.services.platba_qr import generuj_platbu_qr
            import base64

            platba_data = generuj_platbu_qr(ucet, castka, vs, zprava=salon.name)
            email_platba_qr(rezervace, platba, castka, ucet, vs, platba_data=platba_data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception as exc:
            return Response({'detail': f'E-mail se nepodařilo odeslat: {exc}'}, status=502)

        log_historie(rezervace, 'admin', f'odeslání žádosti o platbu {castka} Kč', request=request)
        return Response({
            'ok': True,
            'message': 'E-mail s QR platbou odeslán.',
            'qr_png_base64': base64.b64encode(platba_data['qr_png']).decode('ascii'),
            'castka': platba_data['castka_display'],
            'ucet': platba_data['ucet'],
            'variabilni_symbol': platba_data['variabilni_symbol'],
        })


class AdminNoShowBlokovatView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'E-mail je povinný.'}, status=400)
        from rezervace.services.email_reputace import blokovat_v_salonu
        try:
            blokovat_v_salonu(email, salon.id)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=400)
        _audit(request, salon, 'noshow', f'blokace e-mailu v salonu ({email})')
        return Response({'ok': True, 'message': f'E-mail {email} zablokován v tomto salonu.'})


class AdminNoShowOdblokovatView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'E-mail je povinný.'}, status=400)
        from rezervace.services.email_reputace import odblokovat_v_salonu
        try:
            odblokovat_v_salonu(email, salon.id)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=400)
        _audit(request, salon, 'noshow', f'odblokování e-mailu v salonu ({email})')
        return Response({'ok': True, 'message': f'E-mail {email} odblokován v tomto salonu.'})


class AdminNoShowArchivView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        q = request.query_params.get('q', '').strip()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        from rezervace.services.email_reputace import hledat_hrisniky
        return Response(hledat_hrisniky(q=q, page=page, page_size=25, salon_id=salon.id))


class AdminBlokaceView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = BlokaceCasuSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        z_id = ser.validated_data.get('zamestnanec')
        if z_id:
            get_object_or_404(Zamestnanec, pk=z_id.id if hasattr(z_id, 'id') else z_id, salon=salon)
        blokace = BlokaceCasu.objects.create(salon=salon, **ser.validated_data)
        po = BlokaceCasuSerializer(blokace).data
        _audit(request, salon, 'blokace', 'přidání blokace času',
               objekt_typ='blokace', objekt_id=blokace.id, po=po)
        return Response(po, status=201)

    def delete(self, request, pk, blokace_id):
        salon = get_salon(pk)
        b = get_object_or_404(BlokaceCasu, pk=blokace_id, salon=salon)
        pred = BlokaceCasuSerializer(b).data
        b.delete()
        _audit(request, salon, 'blokace', 'smazání blokace času',
               objekt_typ='blokace', objekt_id=blokace_id, pred=pred)
        return Response(status=204)


class AdminStatistikyView(APIView):
    permission_classes = [StaffPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        staff = get_staff_from_request(request, pk)
        qs = Rezervace.objects.filter(salon=salon)
        if staff and not je_majitel(staff):
            qs = qs.filter(zamestnanec=staff)
        total = qs.count()
        storno = qs.filter(stav__in=('zakaznik_storno', 'salon_storno')).count()
        dokonceno = qs.filter(stav='dokonceno').count()
        no_show = qs.filter(stav='no_show').count()

        from django.db.models import Count
        sluzby_stats = (
            RezervaceSluzba.objects.filter(rezervace__in=qs)
            .values('sluzba__nazev')
            .annotate(pocet=Count('id'))
            .order_by('-pocet')[:5]
        )
        zamestnanec_stats = (
            qs.filter(zamestnanec__isnull=False)
            .values('zamestnanec__jmeno')
            .annotate(pocet=Count('id'))
            .order_by('-pocet')[:5]
        )

        return Response({
            'celkem_rezervaci': total,
            'dokonceno': dokonceno,
            'storno': storno,
            'storno_procent': round(storno / total * 100, 1) if total else 0,
            'no_show': no_show,
            'nejprodavanejsi_sluzby': list(sluzby_stats),
            'nejvytizenejsi_zamestnanci': list(zamestnanec_stats),
        })


class AdminExportHodinView(APIView):
    permission_classes = [StaffPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        staff = get_staff_from_request(request, pk)
        od = request.query_params.get('od')
        do = request.query_params.get('do')
        qs = Rezervace.objects.filter(salon=salon, stav='dokonceno').select_related('zamestnanec')
        if staff and not je_majitel(staff):
            qs = qs.filter(zamestnanec=staff)
        if od:
            qs = qs.filter(zacatek__gte=od)
        if do:
            qs = qs.filter(zacatek__lte=do)

        radky = []
        for r in qs:
            delka = r.skutecna_delka_minut or int((r.konec - r.zacatek).total_seconds() / 60)
            radky.append({
                'datum': r.zacatek.strftime('%Y-%m-%d'),
                'zamestnanec': r.zamestnanec.jmeno if r.zamestnanec else '—',
                'minuty': delka,
                'hodiny': round(delka / 60, 2),
            })

        return Response({'radky': radky, 'celkem_hodin': round(sum(x['minuty'] for x in radky) / 60, 2)})


class AdminOdblokovatZakaznikaView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk, zakaznik_id):
        salon = get_salon(pk)
        z = get_object_or_404(Zakaznik, pk=zakaznik_id, salon=salon)
        z.blokovan = False
        z.no_show_pocet = 0
        z.save()
        _audit(request, salon, 'zakaznik', f'odblokování zákazníka ({z.nick})',
               objekt_typ='zakaznik', objekt_id=z.id)
        return Response({'ok': True})


class AdminVyjimkyView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        return Response(SalonVyjimkaSerializer(salon.vyjimky.all(), many=True).data)

    def post(self, request, pk):
        salon = get_salon(pk)
        ser = SalonVyjimkaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = SalonVyjimka.objects.create(salon=salon, **ser.validated_data)
        po = SalonVyjimkaSerializer(v).data
        _audit(request, salon, 'vyjimka', f'přidání výjimky otevírací doby ({v.datum_od}–{v.datum_do})',
               objekt_typ='vyjimka', objekt_id=v.id, po=po)
        return Response(po, status=201)


class AdminHistorieView(APIView):
    permission_classes = [StaffPermission]

    def get(self, request, pk, rezervace_id):
        salon = get_salon(pk)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon=salon)
        hist = rezervace.historie.all()
        return Response(RezervaceHistorieSerializer(hist, many=True).data)


class AdminAuditLogView(APIView):
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        page_size = 50
        qs = SalonAuditLog.objects.filter(salon=salon)
        total = qs.count()
        items = qs[(page - 1) * page_size:page * page_size]
        celkem_stranek = max(1, (total + page_size - 1) // page_size) if total else 1
        return Response({
            'vysledky': SalonAuditLogSerializer(items, many=True).data,
            'stranka': page,
            'celkem_stranek': celkem_stranek,
            'celkem': total,
        })


class AdminGdprExportView(APIView):
    """Export osobních údajů zákazníka na žádost (jen majitelka)."""
    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        salon = get_salon(pk)
        email = (request.query_params.get('email') or '').strip().lower()
        zakaznik_id = request.query_params.get('zakaznik_id')
        if zakaznik_id:
            zakaznik = get_object_or_404(Zakaznik, pk=zakaznik_id, salon=salon)
        elif email:
            zakaznik = get_object_or_404(Zakaznik, salon=salon, email__iexact=email)
        else:
            return Response({'detail': 'Zadejte email nebo zakaznik_id.'}, status=400)

        data = export_zakaznik_data(zakaznik)
        log_gdpr_audit(
            request, salon, 'export údajů',
            f'zákazník id={zakaznik.id}, e-mail dříve {zakaznik.email}',
            objekt_typ='zakaznik', objekt_id=zakaznik.id,
        )
        return Response(data)


class AdminGdprVymazView(APIView):
    """Výmaz osobních údajů zákazníka na žádost (jen majitelka)."""
    permission_classes = [MajitelPermission]

    def post(self, request, pk):
        salon = get_salon(pk)
        email = (request.data.get('email') or '').strip().lower()
        zakaznik_id = request.data.get('zakaznik_id')
        if zakaznik_id:
            zakaznik = get_object_or_404(Zakaznik, pk=zakaznik_id, salon=salon)
        elif email:
            zakaznik = get_object_or_404(Zakaznik, salon=salon, email__iexact=email)
        else:
            return Response({'detail': 'Zadejte email nebo zakaznik_id.'}, status=400)

        email_pred = zakaznik.email
        zak_id = zakaznik.id
        pred, po = vymaz_zakaznik_na_zadost(zakaznik)
        log_gdpr_audit(
            request, salon, 'výmaz na žádost',
            f'zákazník id={zak_id}, e-mail {email_pred}',
            objekt_typ='zakaznik', objekt_id=zak_id, pred=pred, po=po,
        )
        return Response({'ok': True, 'message': 'Osobní údaje zákazníka byly vymazány.', 'zakaznik_id': zak_id})
