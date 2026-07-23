from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import get_flow_user_from_request
from flow.permissions import FlowPermission
from rezervace.models import NoShowZaznam, Rezervace, RezervaceHistorie, Zamestnanec, ZamestnanecAbsence, ZamestnanecRozvrh
from rezervace.notifikace_defaults import MANUAL_TYP_NOSHOW, MANUAL_TYP_PLATBA, get_manual_notifikace
from rezervace.serializers import (
    AdminRezervaceSerializer,
    NoShowZaznamSerializer,
    ZamestnanecAbsenceSerializer,
    ZamestnanecRozvrhSerializer,
    dopln_rozvrh_7_dni,
)
from rezervace.services.audit import log_audit, log_rezervace_audit
from rezervace.services.emails import email_storno


def _flow_user(request):
    return get_flow_user_from_request(request)


def _log_flow(user, rezervace, popis, pred=None, po=None):
    actor = f'FLOW:{user.zamestnanec.jmeno}'
    RezervaceHistorie.objects.create(
        rezervace=rezervace, kdo=actor, popis=popis,
        data_pred=pred, data_po=po,
    )
    log_rezervace_audit(rezervace, actor, popis, pred=pred, po=po)


def _own_rezervace_or_403(user, rezervace):
    if rezervace.salon_id != user.salon_id:
        return Response({'detail': 'Rezervace nepatří k vašemu salonu.'}, status=403)
    if rezervace.zamestnanec_id != user.zamestnanec_id:
        return Response({'detail': 'Můžete spravovat jen vlastní rezervace.'}, status=403)
    return None


def _parse_range(request):
    od = request.query_params.get('od')
    do = request.query_params.get('do')
    return od, do


def _filter_rezervace_qs(qs, od, do):
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
    return qs


def _filter_absence_qs(qs, od, do):
    if od:
        qs = qs.filter(datum_do__gte=od[:10])
    if do:
        qs = qs.filter(datum_od__lte=do[:10])
    return qs


class FlowKalendarView(APIView):
    """Můj kalendář + moje absence. ?od=&do=&overview=1 pro Visible Overview (jen čtení)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        od, do = _parse_range(request)
        overview = str(request.query_params.get('overview', '')).lower() in ('1', 'true', 'yes')
        if overview and not user.visible_overview:
            return Response({'detail': 'Nemáte zapnuté Visible Overview.'}, status=403)

        salon = user.salon
        qs = Rezervace.objects.filter(salon=salon).prefetch_related('polozky__sluzba', 'zamestnanec')
        if overview:
            mode = 'overview'
        else:
            mode = 'mine'
            qs = qs.filter(zamestnanec_id=user.zamestnanec_id)
        qs = _filter_rezervace_qs(qs, od, do)

        if overview:
            abs_qs = ZamestnanecAbsence.objects.filter(
                zamestnanec__salon=salon
            ).select_related('zamestnanec')
        else:
            abs_qs = ZamestnanecAbsence.objects.filter(zamestnanec_id=user.zamestnanec_id)
        abs_qs = _filter_absence_qs(abs_qs, od, do)

        absence_data = []
        for a in abs_qs.order_by('datum_od'):
            item = ZamestnanecAbsenceSerializer(a).data
            item['zamestnanec_id'] = a.zamestnanec_id
            item['zamestnanec_jmeno'] = a.zamestnanec.jmeno
            absence_data.append(item)

        return Response({
            'mode': mode,
            'visible_overview': user.visible_overview,
            'rezervace': AdminRezervaceSerializer(qs.order_by('zacatek'), many=True).data,
            'absence': absence_data,
        })


class FlowRezervaceDokoncenoView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
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
        _log_flow(user, rezervace, 'rezervace proběhla', pred, po)
        return Response(po)


class FlowRezervaceNoShowView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze označit jako NO-show.'}, status=400)

        # FLOW: žádná blokace e-mailu — to zůstává majitelce v rezervacích
        odeslat_upozorneni = bool(request.data.get('odeslat_upozorneni'))

        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'no_show'
        rezervace.save(update_fields=['stav', 'aktualizovano'])

        sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
        from rezervace.services.gdpr import email_hash

        email_val = rezervace.kontaktni_email or ''
        zaznam = NoShowZaznam.objects.create(
            salon=user.salon,
            rezervace=rezervace,
            zakaznik=rezervace.zakaznik,
            jmeno=rezervace.kontaktni_jmeno,
            email=email_val,
            email_hash=email_hash(email_val) if email_val else '',
            zacatek=rezervace.zacatek,
            zamestnanec_jmeno=rezervace.zamestnanec.jmeno if rezervace.zamestnanec else '',
            sluzby=sluzby,
            zakaznik_blokovan=False,
        )
        if rezervace.zakaznik:
            rezervace.zakaznik.no_show_pocet += 1
            rezervace.zakaznik.save(update_fields=['no_show_pocet'])

        from rezervace.services.email_reputace import aktualizuj_po_noshow

        reputace = aktualizuj_po_noshow(rezervace.kontaktni_email or '', user.salon_id)

        email_odeslan = False
        if odeslat_upozorneni and rezervace.kontaktni_email:
            try:
                nastaveni = user.salon.rezervacni_nastaveni
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
        _log_flow(user, rezervace, 'NO-show', pred, po)
        return Response({
            'rezervace': po,
            'zaznam': NoShowZaznamSerializer(zaznam).data,
            'email_odeslan': email_odeslan,
            'reputace': reputace,
        })


class FlowRezervaceStornoView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def delete(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze stornovat.'}, status=400)
        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'salon_storno'
        rezervace.save(update_fields=['stav', 'aktualizovano'])
        po = AdminRezervaceSerializer(rezervace).data
        _log_flow(user, rezervace, 'storno salonu', pred, po)
        try:
            duvod = (request.data.get('duvod') or request.headers.get('X-Absence-Duvod') or '').strip()[:100]
            email_storno(
                rezervace,
                kdo='salon',
                duvod=duvod,
            )
        except Exception:
            pass
        return Response({'ok': True, 'rezervace': po})


class FlowRezervacePlatbaView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
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
            nastaveni = user.salon.rezervacni_nastaveni
            platba = get_manual_notifikace(nastaveni.notifikace, MANUAL_TYP_PLATBA)
            if not platba:
                return Response({'detail': 'Chybí nastavení 4. e-mailu (platba).'}, status=400)
            from rezervace.services.notifikace_email import email_platba_qr
            from rezervace.services.platba_qr import generuj_platbu_qr
            import base64

            platba_data = generuj_platbu_qr(ucet, castka, vs, zprava=user.salon.name)
            email_platba_qr(rezervace, platba, castka, ucet, vs, platba_data=platba_data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception as exc:
            return Response({'detail': f'E-mail se nepodařilo odeslat: {exc}'}, status=502)

        _log_flow(user, rezervace, f'odeslání žádosti o platbu {castka} Kč')
        return Response({
            'ok': True,
            'message': 'E-mail s QR platbou odeslán.',
            'qr_png_base64': base64.b64encode(platba_data['qr_png']).decode('ascii'),
            'castka': platba_data['castka_display'],
            'ucet': platba_data['ucet'],
            'variabilni_symbol': platba_data['variabilni_symbol'],
        })


class FlowAbsenceView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        qs = ZamestnanecAbsence.objects.filter(zamestnanec_id=user.zamestnanec_id)
        od, do = _parse_range(request)
        qs = _filter_absence_qs(qs, od, do)
        return Response(ZamestnanecAbsenceSerializer(qs.order_by('datum_od'), many=True).data)

    def post(self, request):
        user = _flow_user(request)
        ser = ZamestnanecAbsenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        absence = ZamestnanecAbsence.objects.create(
            zamestnanec_id=user.zamestnanec_id,
            **ser.validated_data,
        )
        od = ser.validated_data['datum_od']
        do = ser.validated_data['datum_do']
        konflikty = Rezervace.objects.filter(
            salon_id=user.salon_id,
            zamestnanec_id=user.zamestnanec_id,
            stav__in=('ceka', 'potvrzeno'),
            zacatek__date__gte=od,
            zacatek__date__lte=do,
        ).prefetch_related('polozky__sluzba').order_by('zacatek')
        return Response({
            'absence': ZamestnanecAbsenceSerializer(absence).data,
            'konfliktni_rezervace': AdminRezervaceSerializer(konflikty, many=True).data,
            'pocet_konfliktu': konflikty.count(),
        }, status=status.HTTP_201_CREATED)


class FlowAbsenceDetailView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def delete(self, request, absence_id):
        user = _flow_user(request)
        absence = get_object_or_404(
            ZamestnanecAbsence, pk=absence_id, zamestnanec_id=user.zamestnanec_id
        )
        absence.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FlowSluzbyView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        from rezervace.serializers import SluzbaPublicSerializer
        from salons.models import CenikPolozka

        sluzby = CenikPolozka.objects.filter(
            salon_id=user.salon_id, aktivni=True,
        ).order_by('poradi', 'id')
        return Response(SluzbaPublicSerializer(sluzby, many=True).data)


class FlowVolneTerminyView(APIView):
    """Volné termíny jen pro přihlášeného pracovníka."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        from rezervace.services.availability import generuj_terminy, salon_je_zavreny
        from salons.models import CenikPolozka

        datum_str = request.query_params.get('datum')
        sluzby_str = request.query_params.get('sluzby', '')
        if not datum_str or not sluzby_str:
            return Response({'detail': 'Parametry datum a sluzby jsou povinné.'}, status=400)

        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        if salon_je_zavreny(user.salon, datum):
            return Response({
                'datum': datum_str, 'zavreno': True, 'terminy': [],
                'duvod': 'Salon je tento den zavřený.',
            })

        sluzby_ids = [int(x) for x in sluzby_str.split(',') if x.strip()]
        if not sluzby_ids:
            return Response({'detail': 'Vyberte alespoň jednu službu.'}, status=400)

        terminy = generuj_terminy(user.salon, datum, sluzby_ids, user.zamestnanec_id)
        duvod = ''
        if not terminy:
            aktivni = CenikPolozka.objects.filter(
                salon_id=user.salon_id, pk__in=sluzby_ids, aktivni=True,
            ).count()
            if aktivni != len(sluzby_ids):
                duvod = 'Vybraná služba není dostupná.'
            else:
                duvod = 'Pro tento den u vás není volný žádný termín.'

        return Response({
            'datum': datum_str,
            'zavreno': False,
            'terminy': terminy,
            'duvod': duvod,
            'zamestnanec_id': user.zamestnanec_id,
        })


class FlowRezervaceCreateView(APIView):
    """Zadat rezervaci na sebe (telefon / osobně) — stejná logika jako admin."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request):
        user = _flow_user(request)
        from rezervace.serializers import AdminRezervaceCreateSerializer
        from rezervace.views import vytvor_rezervaci

        payload = dict(request.data)
        payload['zamestnanec_id'] = user.zamestnanec_id
        if not payload.get('typ_vytvoreni'):
            payload['typ_vytvoreni'] = 'telefon'
        if not payload.get('stav'):
            payload['stav'] = 'potvrzeno'

        ser = AdminRezervaceCreateSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        d['zamestnanec_id'] = user.zamestnanec_id

        try:
            rezervace = vytvor_rezervaci(
                user.salon,
                d,
                typ_vytvoreni=d.get('typ_vytvoreni', 'telefon'),
                stav=d.get('stav', 'potvrzeno'),
                kdo=f'FLOW:{user.zamestnanec.jmeno}',
                request=request,
            )
            if d.get('poznamka_interni'):
                rezervace.poznamka_interni = d['poznamka_interni']
                rezervace.save(update_fields=['poznamka_interni'])
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        return Response(AdminRezervaceSerializer(rezervace).data, status=status.HTTP_201_CREATED)


class FlowRozvrhView(APIView):
    """Týdenní pracovní doba přihlášeného zaměstnance — stejná data jako web a rezervace."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        z = get_object_or_404(
            Zamestnanec.objects.prefetch_related('rozvrh'),
            pk=user.zamestnanec_id,
            salon_id=user.salon_id,
        )
        return Response({'rozvrh': dopln_rozvrh_7_dni(z)})

    def put(self, request):
        user = _flow_user(request)
        z = get_object_or_404(
            Zamestnanec.objects.prefetch_related('rozvrh'),
            pk=user.zamestnanec_id,
            salon_id=user.salon_id,
        )
        if z.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Účet majitelky nemá pracovní rozvrh pro rezervace.'},
                status=400,
            )

        raw = request.data.get('rozvrh')
        if not isinstance(raw, list) or len(raw) != 7:
            return Response({'detail': 'Očekávám rozvrh pro všech 7 dní týdne.'}, status=400)

        by_den = {}
        for item in raw:
            ser = ZamestnanecRozvrhSerializer(data=item)
            ser.is_valid(raise_exception=True)
            data = ser.validated_data
            den = data['den']
            if den in by_den:
                return Response({'detail': f'Duplicitní den {den}.'}, status=400)
            if data.get('volno'):
                data['od'] = None
                data['do'] = None
            elif not data.get('od') or not data.get('do'):
                return Response(
                    {'detail': f'Den {den}: vyplňte od–do, nebo označte volno.'},
                    status=400,
                )
            elif data['do'] <= data['od']:
                return Response(
                    {'detail': f'Den {den}: konec musí být později než začátek.'},
                    status=400,
                )
            by_den[den] = data

        if set(by_den.keys()) != set(range(7)):
            return Response({'detail': 'Rozvrh musí obsahovat dny 0–6 (Po–Ne).'}, status=400)

        pred = {'rozvrh': dopln_rozvrh_7_dni(z)}
        z.rozvrh.all().delete()
        for den in range(7):
            ZamestnanecRozvrh.objects.create(zamestnanec=z, **by_den[den])
        z.refresh_from_db()
        po = {'rozvrh': dopln_rozvrh_7_dni(z)}
        log_audit(
            user.salon,
            f'FLOW:{z.jmeno}',
            'oteviraci_doba',
            f'FLOW:{z.jmeno}: změna vlastní pracovní doby',
            objekt_typ='zamestnanec',
            objekt_id=z.id,
            pred=pred,
            po=po,
        )
        return Response(po)
