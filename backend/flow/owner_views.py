"""FLOW owner — provozní nastavení salonu (dříve rezervace-admin)."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import flow_je_owner, flow_zam, get_flow_user_from_request, zrusit_vsechny_sessiony
from flow.emails import email_flow_pristup, flow_pristup_payload, generate_heslo
from flow.models import FlowUser, heslo_je_platne
from flow.permissions import FlowPermission
from flow.serializers import FlowUserPublicSerializer
from rezervace.models import Rezervace, RezervacniNastaveni, Zamestnanec, ZamestnanecAbsence
from rezervace.serializers import (
    RezervacniNastaveniSerializer,
    ZamestnanecAbsenceSerializer,
    ZamestnanecDetailSerializer,
    ZamestnanecWriteSerializer,
)
from rezervace.services.audit import log_audit


def require_flow_owner(request):
    user = get_flow_user_from_request(request)
    if not user:
        return None, Response({'detail': 'Nejste přihlášeni.'}, status=status.HTTP_401_UNAUTHORIZED)
    if not flow_je_owner(user):
        return None, Response(
            {'detail': 'Tuto část Správy může používat jen Manager.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return user, None


def require_technicke_nastaveni(user):
    """Technická zóna FLOW jen když ji Ulov povolí v partner-adminu."""
    from partner_admin.models import PartnerNastaveni

    ok = PartnerNastaveni.objects.filter(
        salon_id=user.salon_id,
        povolit_technicke_nastaveni=True,
    ).exists()
    if not ok:
        return Response(
            {
                'detail': (
                    'Technické nastavení není pro tento salon povoleno. '
                    'Zapíná se v partner-adminu.'
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _personal_payload(z):
    data = ZamestnanecDetailSerializer(z).data
    try:
        fu = z.flow_ucet
        data['flow'] = {
            'ma_flow': True,
            'ucet': FlowUserPublicSerializer(fu).data,
        }
    except FlowUser.DoesNotExist:
        data['flow'] = {'ma_flow': False, 'ucet': None}
    return data


def _actor(user):
    return f'FLOW:{flow_zam(user).jmeno}'


class FlowOwnerNastaveniSerializer(RezervacniNastaveniSerializer):
    """Stejná data jako admin nastavení, bez GDPR verze (ta zůstává v partner-adminu)."""

    class Meta(RezervacniNastaveniSerializer.Meta):
        fields = [
            f for f in RezervacniNastaveniSerializer.Meta.fields
            if f != 'gdpr_zasady_verze'
        ]


class FlowOwnerNastaveniView(APIView):
    """GET/PUT rezervační pravidla + e-mailové šablony pro FLOW ownera."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        tech_err = require_technicke_nastaveni(user)
        if tech_err:
            return tech_err
        nastaveni, _ = RezervacniNastaveni.objects.get_or_create(salon=user.salon)
        return Response(FlowOwnerNastaveniSerializer(nastaveni).data)

    def put(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        tech_err = require_technicke_nastaveni(user)
        if tech_err:
            return tech_err
        data = dict(request.data or {})
        data.pop('gdpr_zasady_verze', None)
        nastaveni, _ = RezervacniNastaveni.objects.get_or_create(salon=user.salon)
        pred = FlowOwnerNastaveniSerializer(nastaveni).data
        ser = FlowOwnerNastaveniSerializer(nastaveni, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        po = ser.data
        log_audit(
            user.salon,
            _actor(user),
            'nastaveni',
            'změna nastavení rezervací ve FLOW',
            pred=pred,
            po=po,
        )
        return Response(po)


class FlowOwnerPersonalListCreateView(APIView):
    """Seznam / založení personálu ve FLOW Správě."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        qs = (
            Zamestnanec.objects.filter(salon=user.salon)
            .prefetch_related('rozvrh', 'absence', 'prirazene_sluzby')
            .order_by('poradi', 'id')
        )
        return Response({'zamestnanci': [_personal_payload(z) for z in qs]})

    def post(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        ser = ZamestnanecWriteSerializer(
            data=request.data,
            context={'salon': user.salon},
        )
        ser.is_valid(raise_exception=True)
        z = ser.save()
        po = _personal_payload(z)
        log_audit(
            user.salon,
            _actor(user),
            'zamestnanec',
            f'FLOW: přidání zaměstnance ({z.jmeno})',
            objekt_typ='zamestnanec',
            objekt_id=z.id,
            po=po,
        )
        return Response(po, status=status.HTTP_201_CREATED)


class FlowOwnerPersonalDetailView(APIView):
    """Úprava provozních údajů personálu (číslo účtu, rozvrh, jméno…)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def put(self, request, zamestnanec_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        z = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=user.salon)
        # Webová deaktivace / prezentace zůstává ve web-adminu
        data = dict(request.data or {})
        data.pop('aktivni', None)
        data.pop('zobrazit_na_webu', None)
        data.pop('fotka', None)
        data.pop('popis', None)
        pred = _personal_payload(z)
        ser = ZamestnanecWriteSerializer(
            z, data=data, partial=True, context={'salon': user.salon},
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        z.refresh_from_db()
        po = _personal_payload(z)
        log_audit(
            user.salon,
            _actor(user),
            'zamestnanec',
            f'FLOW: změna zaměstnance ({z.jmeno})',
            objekt_typ='zamestnanec',
            objekt_id=z.id,
            pred=pred,
            po=po,
        )
        return Response(po)


class FlowOwnerPersonalFlowCreateView(APIView):
    """Vytvoření FLOW přístupu pro staff."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, zamestnanec_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=user.salon)
        if zam.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Manager už má FLOW přístup přes svůj účet.'},
                status=400,
            )
        try:
            zam.flow_ucet
            return Response(
                {'detail': 'Tento pracovník už má přístup do FLOW. Použijte reset hesla.'},
                status=400,
            )
        except FlowUser.DoesNotExist:
            pass
        email = (request.data.get('email') or '').strip().lower()
        if not email or '@' not in email:
            return Response({'detail': 'Zadejte e-mail pro FLOW přístup.'}, status=400)
        if FlowUser.objects.filter(email__iexact=email).exists():
            return Response(
                {'detail': 'Tento e-mail už je použit u jiného FLOW účtu.'},
                status=400,
            )
        heslo = generate_heslo(12)
        if not heslo_je_platne(heslo):
            heslo = generate_heslo(12) + '1a'
        flow_user = FlowUser(
            salon=user.salon,
            zamestnanec=zam,
            email=email,
            visible_overview=bool(request.data.get('visible_overview')),
            aktivni=True,
        )
        flow_user.set_password(heslo)
        flow_user.save()
        # Sjednotit web/staff login s FLOW e-mailem, pokud je volný
        conflict = (
            Zamestnanec.objects.filter(salon=user.salon, prihlasovaci_jmeno__iexact=email)
            .exclude(pk=zam.pk)
            .exists()
        )
        if not conflict and (zam.prihlasovaci_jmeno or '').strip().lower() != email:
            zam.prihlasovaci_jmeno = email
            zam.save(update_fields=['prihlasovaci_jmeno'])
        email_ok = email_flow_pristup(flow_user, heslo, reset=False)
        payload = {
            'zamestnanec': _personal_payload(zam),
            **flow_pristup_payload(heslo, email_ok, reset=False),
        }
        return Response(payload, status=201)


class FlowOwnerPersonalFlowPatchView(APIView):
    """Blokace FLOW přihlášení / overview — neovlivní Zamestnanec.aktivni."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def patch(self, request, zamestnanec_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=user.salon)
        try:
            flow_user = zam.flow_ucet
        except FlowUser.DoesNotExist:
            return Response({'detail': 'Pracovník nemá FLOW účet.'}, status=404)
        if 'visible_overview' in request.data:
            flow_user.visible_overview = bool(request.data.get('visible_overview'))
        if 'aktivni' in request.data:
            flow_user.aktivni = bool(request.data.get('aktivni'))
            if not flow_user.aktivni:
                zrusit_vsechny_sessiony(flow_user)
        flow_user.save()
        return Response(_personal_payload(zam))


class FlowOwnerPersonalFlowResetView(APIView):
    """Reset hesla staff FLOW účtu (jen owner → staff)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, zamestnanec_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon=user.salon)
        if zam.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Heslo majitele se mění ve webové administraci, ne resetem.'},
                status=400,
            )
        try:
            flow_user = zam.flow_ucet
        except FlowUser.DoesNotExist:
            return Response({'detail': 'Pracovník nemá FLOW účet.'}, status=404)
        heslo = generate_heslo(12)
        if not heslo_je_platne(heslo):
            heslo = generate_heslo(12) + '1a'
        flow_user.set_password(heslo)
        flow_user.save(update_fields=['password_hash', 'upraveno'])
        zrusit_vsechny_sessiony(flow_user)
        email_ok = email_flow_pristup(flow_user, heslo, reset=True)
        return Response(flow_pristup_payload(heslo, email_ok, reset=True))


def _absence_owner_payload(absence):
    data = ZamestnanecAbsenceSerializer(absence).data
    data['zamestnanec_id'] = absence.zamestnanec_id
    data['zamestnanec_jmeno'] = absence.zamestnanec.jmeno
    return data


def _absence_konflikty(absence):
    from flow.provoz_views import _konflikt_payload

    qs = Rezervace.objects.filter(
        salon_id=absence.zamestnanec.salon_id,
        zamestnanec_id=absence.zamestnanec_id,
        stav__in=('ceka', 'potvrzeno'),
        zacatek__date__gte=absence.datum_od,
        zacatek__date__lte=absence.datum_do,
    ).select_related('salon', 'zamestnanec').prefetch_related('polozky__sluzba').order_by('zacatek')
    return [
        _konflikt_payload(r, exclude_zamestnanec_id=absence.zamestnanec_id)
        for r in qs
    ]


class FlowOwnerAbsenceListView(APIView):
    """Seznam žádostí o volno + volitelně založení schválené absence za staff."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        from datetime import timedelta

        from django.db.models import Q
        from django.utils import timezone

        stav = (request.query_params.get('stav') or '').strip()
        qs = ZamestnanecAbsence.objects.filter(
            zamestnanec__salon=user.salon,
        ).select_related('zamestnanec')
        if stav:
            qs = qs.filter(stav=stav)
        else:
            cutoff = timezone.now().date() - timedelta(days=60)
            qs = qs.filter(
                Q(stav=ZamestnanecAbsence.STAV_CEKA) | Q(datum_do__gte=cutoff)
            )
        qs = qs.order_by('-vytvoreno')
        ceka = ZamestnanecAbsence.objects.filter(
            zamestnanec__salon=user.salon,
            stav=ZamestnanecAbsence.STAV_CEKA,
        ).count()
        return Response({
            'zadosti': [_absence_owner_payload(a) for a in qs[:100]],
            'ceka_pocet': ceka,
        })

    def post(self, request):
        """Majitel založí absenci za pracovníka — hned schváleno."""
        user, err = require_flow_owner(request)
        if err:
            return err
        try:
            zam_id = int(request.data.get('zamestnanec_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'Vyberte pracovníka.'}, status=400)
        zam = get_object_or_404(
            Zamestnanec, pk=zam_id, salon=user.salon,
        )
        if zam.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Vlastní volno majitele zakládejte v záložce Dovolená.'},
                status=400,
            )
        ser = ZamestnanecAbsenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        absence = ZamestnanecAbsence.objects.create(
            zamestnanec=zam,
            stav=ZamestnanecAbsence.STAV_SCHVALENO,
            **ser.validated_data,
        )
        konflikty = _absence_konflikty(absence)
        return Response({
            'absence': _absence_owner_payload(absence),
            'konfliktni_rezervace': konflikty,
            'pocet_konfliktu': len(konflikty),
            'detail': 'Absence schválena.',
        }, status=201)


class FlowOwnerAbsenceSchvalitView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, absence_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        absence = get_object_or_404(
            ZamestnanecAbsence.objects.select_related('zamestnanec'),
            pk=absence_id,
            zamestnanec__salon=user.salon,
        )
        if absence.stav != ZamestnanecAbsence.STAV_CEKA:
            return Response({'detail': 'Tuto žádost už nelze schválit.'}, status=400)
        absence.stav = ZamestnanecAbsence.STAV_SCHVALENO
        absence.save(update_fields=['stav'])
        konflikty = _absence_konflikty(absence)
        return Response({
            'absence': _absence_owner_payload(absence),
            'konfliktni_rezervace': konflikty,
            'pocet_konfliktu': len(konflikty),
            'detail': (
                'Absence schválena.'
                if not konflikty
                else f'Absence schválena. Vyřešte {len(konflikty)} kolizí rezervací.'
            ),
        })


class FlowOwnerAbsenceZamitnoutView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, absence_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        absence = get_object_or_404(
            ZamestnanecAbsence.objects.select_related('zamestnanec'),
            pk=absence_id,
            zamestnanec__salon=user.salon,
        )
        if absence.stav != ZamestnanecAbsence.STAV_CEKA:
            return Response({'detail': 'Tuto žádost už nelze zamítnout.'}, status=400)
        absence.stav = ZamestnanecAbsence.STAV_ZAMITNUTO
        absence.save(update_fields=['stav'])
        return Response({
            'absence': _absence_owner_payload(absence),
            'detail': 'Žádost zamítnuta.',
        })


class FlowOwnerAbsenceDeleteView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def delete(self, request, absence_id):
        user, err = require_flow_owner(request)
        if err:
            return err
        absence = get_object_or_404(
            ZamestnanecAbsence,
            pk=absence_id,
            zamestnanec__salon=user.salon,
        )
        absence.delete()
        return Response(status=204)


def _partner_platby_payload(salon):
    """Read-only payload pro FLOW majitele — prázdná data bez chyb."""
    import base64

    from partner_admin.models import PartnerNastaveni, PlatbaPartnera

    try:
        nast = PartnerNastaveni.objects.get(salon=salon)
    except PartnerNastaveni.DoesNotExist:
        return {
            'nastaveno': False,
            'ulov_cislo_uctu': '',
            'variabilni_symbol': '',
            'castka': None,
            'periodicita': '',
            'periodicita_label': '',
            'dalsi_splatnost': None,
            'platebni_stav': 'nenastaveno',
            'je_po_splatnosti': False,
            'dni_po_splatnosti': 0,
            'qr': None,
            'historie': [],
        }

    historie = []
    for p in PlatbaPartnera.objects.filter(salon=salon).order_by('-splatnost', '-id')[:40]:
        historie.append({
            'id': p.id,
            'splatnost': p.splatnost.isoformat(),
            'zaplaceno_dne': p.zaplaceno_dne.isoformat(),
            'castka': str(p.prijata_castka if p.prijata_castka is not None else p.ocekavana_castka),
            'variabilni_symbol': p.variabilni_symbol or '',
            'ma_fakturu': bool(p.faktura_pdf),
        })

    qr = None
    ucet = (nast.ulov_cislo_uctu or '').strip()
    vs = (nast.variabilni_symbol or '').strip()
    if ucet and vs and nast.castka and nast.castka > 0:
        try:
            from rezervace.services.platba_qr import generuj_platbu_qr

            data = generuj_platbu_qr(
                ucet,
                nast.castka,
                vs,
                zprava=f'ULOV {salon.name}',
            )
            qr = {
                'ucet': data['ucet'],
                'iban': data['iban'],
                'castka': data['castka'],
                'castka_display': data['castka_display'],
                'variabilni_symbol': data['variabilni_symbol'],
                'qr_png_base64': base64.b64encode(data['qr_png']).decode('ascii'),
            }
        except Exception:
            qr = None

    ma_platbu = bool(
        vs
        or ucet
        or nast.dalsi_splatnost
        or (nast.castka and nast.castka > 0)
    )
    return {
        'nastaveno': ma_platbu,
        'ulov_cislo_uctu': nast.ulov_cislo_uctu or '',
        'variabilni_symbol': nast.variabilni_symbol or '',
        'castka': str(nast.castka),
        'periodicita': nast.periodicita,
        'periodicita_label': nast.get_periodicita_display(),
        'dalsi_splatnost': nast.dalsi_splatnost.isoformat() if nast.dalsi_splatnost else None,
        'platebni_stav': nast.platebni_stav,
        'je_po_splatnosti': nast.je_po_splatnosti,
        'dni_po_splatnosti': nast.dni_po_splatnosti,
        'qr': qr,
        'historie': historie,
    }


class FlowOwnerPlatbyView(APIView):
    """Read-only platby partnera pro FLOW majitele."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        return Response(_partner_platby_payload(user.salon))


class FlowOwnerPlatbaFakturaView(APIView):
    """Stažení PDF faktury k zaplacenému období."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request, platba_id):
        from django.http import FileResponse

        from partner_admin.models import PlatbaPartnera

        user, err = require_flow_owner(request)
        if err:
            return err
        platba = get_object_or_404(PlatbaPartnera, pk=platba_id, salon=user.salon)
        if not platba.faktura_pdf:
            return Response({'detail': 'K této platbě není nahraná faktura.'}, status=404)
        return FileResponse(
            platba.faktura_pdf.open('rb'),
            as_attachment=True,
            filename=platba.faktura_pdf.name.rsplit('/', 1)[-1],
            content_type='application/pdf',
        )


class FlowOwnerAuditLogView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        from rezervace.models import SalonAuditLog
        from rezervace.serializers import SalonAuditLogSerializer

        user, err = require_flow_owner(request)
        if err:
            return err
        tech_err = require_technicke_nastaveni(user)
        if tech_err:
            return tech_err
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        page_size = 50
        qs = SalonAuditLog.objects.filter(salon=user.salon)
        total = qs.count()
        items = qs[(page - 1) * page_size:page * page_size]
        celkem_stranek = max(1, (total + page_size - 1) // page_size) if total else 1
        return Response({
            'vysledky': SalonAuditLogSerializer(items, many=True).data,
            'stranka': page,
            'celkem_stranek': celkem_stranek,
            'celkem': total,
        })


class FlowOwnerNoShowArchivView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        from rezervace.services.email_reputace import hledat_hrisniky

        user, err = require_flow_owner(request)
        if err:
            return err
        q = (request.query_params.get('q') or '').strip()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        return Response(hledat_hrisniky(q=q, page=page, page_size=25, salon_id=user.salon_id))


class FlowOwnerNoShowBlokovatView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request):
        from rezervace.services.email_reputace import blokovat_v_salonu

        user, err = require_flow_owner(request)
        if err:
            return err
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'E-mail je povinný.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            blokovat_v_salonu(email, user.salon_id)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_audit(
            user.salon,
            _actor(user),
            'noshow',
            f'blokace e-mailu v salonu ({email})',
        )
        return Response({'ok': True, 'detail': f'E-mail {email} zablokován v tomto salonu.'})


class FlowOwnerNoShowOdblokovatView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request):
        from rezervace.services.email_reputace import odblokovat_v_salonu

        user, err = require_flow_owner(request)
        if err:
            return err
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'E-mail je povinný.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            odblokovat_v_salonu(email, user.salon_id)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_audit(
            user.salon,
            _actor(user),
            'noshow',
            f'odblokování e-mailu v salonu ({email})',
        )
        return Response({'ok': True, 'detail': f'E-mail {email} odblokován v tomto salonu.'})


class FlowOwnerStatistikyView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        from django.db.models import Count

        from rezervace.models import Rezervace, RezervaceSluzba

        user, err = require_flow_owner(request)
        if err:
            return err
        qs = Rezervace.objects.filter(salon=user.salon)
        total = qs.count()
        dokonceno = qs.filter(stav='dokonceno').count()
        storno = qs.filter(stav__in=('zakaznik_storno', 'salon_storno')).count()
        no_show = qs.filter(stav='no_show').count()
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


class FlowOwnerPrirazeniSluzebView(APIView):
    """GET/PUT matice přiřazení služeb k personálu (bez majitele)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        from rezervace.models import ZamestnanecSluzba
        from salons.models import CenikPolozka

        user, err = require_flow_owner(request)
        if err:
            return err
        salon = user.salon
        staff = list(
            Zamestnanec.objects.filter(salon=salon, aktivni=True)
            .exclude(role=Zamestnanec.ROLE_MAJITEL)
            .order_by('poradi', 'id'),
        )
        sluzby = list(
            CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id'),
        )
        pairs = ZamestnanecSluzba.objects.filter(
            zamestnanec__salon=salon,
            zamestnanec__in=staff,
        ).values_list('zamestnanec_id', 'sluzba_id')
        by_staff = {}
        for zid, sid in pairs:
            by_staff.setdefault(zid, []).append(sid)
        return Response({
            'zamestnanci': [{'id': z.id, 'jmeno': z.jmeno} for z in staff],
            'sluzby': [
                {'id': s.id, 'nazev': s.nazev, 'delka_minut': s.delka_minut}
                for s in sluzby
            ],
            'prirazeni': {
                str(z.id): by_staff.get(z.id, [])
                for z in staff
            },
            'hint': (
                'Bez zaškrtnutí u pracovníka = umí všechny služby. '
                'Po zaškrtnutí alespoň jedné umí jen označené.'
            ),
        })

    def put(self, request):
        from django.db import transaction

        from rezervace.models import ZamestnanecSluzba
        from salons.models import CenikPolozka

        user, err = require_flow_owner(request)
        if err:
            return err
        salon = user.salon
        staff_qs = Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(
            role=Zamestnanec.ROLE_MAJITEL,
        )
        staff_ids = set(staff_qs.values_list('id', flat=True))
        sluzba_ids = set(
            CenikPolozka.objects.filter(salon=salon, aktivni=True).values_list('id', flat=True),
        )
        raw = request.data.get('prirazeni')
        if not isinstance(raw, dict):
            return Response(
                {'detail': 'Očekáváno pole prirazeni: {zamestnanec_id: [sluzba_id, …]}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized = {}
        for key, vals in raw.items():
            try:
                zid = int(key)
            except (TypeError, ValueError):
                return Response({'detail': f'Neplatné ID pracovníka: {key}'}, status=400)
            if zid not in staff_ids:
                return Response({'detail': f'Pracovník {zid} nepatří k salonu.'}, status=400)
            if not isinstance(vals, list):
                return Response({'detail': f'Seznam služeb pro {zid} musí být pole.'}, status=400)
            clean = []
            for sid in vals:
                try:
                    sid_i = int(sid)
                except (TypeError, ValueError):
                    return Response({'detail': f'Neplatné ID služby: {sid}'}, status=400)
                if sid_i not in sluzba_ids:
                    return Response({'detail': f'Služba {sid_i} nepatří k salonu.'}, status=400)
                if sid_i not in clean:
                    clean.append(sid_i)
            normalized[zid] = clean

        with transaction.atomic():
            ZamestnanecSluzba.objects.filter(zamestnanec_id__in=staff_ids).delete()
            bulk = [
                ZamestnanecSluzba(zamestnanec_id=zid, sluzba_id=sid)
                for zid, sids in normalized.items()
                for sid in sids
            ]
            if bulk:
                ZamestnanecSluzba.objects.bulk_create(bulk)

        log_audit(
            salon,
            _actor(user),
            'nastaveni',
            'změna přiřazení služeb k personálu',
            po={'prirazeni': {str(k): v for k, v in normalized.items()}},
        )
        return self.get(request)


class FlowOwnerPracovniPersonaView(APIView):
    """
    Propojení majitelky s pracovní personou (stejný login, přepínač ve FLOW).
    GET — stav. POST — zapnout (vytvorit / zamestnanec_id). DELETE — vypnout.
    """

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        from flow.persona_service import majitelka_pracuje_payload

        return Response(majitelka_pracuje_payload(user))

    def post(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        from flow.auth import flow_ucet_je_majitel, flow_user_do_dict
        from flow.persona_service import set_majitelka_pracuje

        if not flow_ucet_je_majitel(user):
            return Response({'detail': 'Jen účet majitelky.'}, status=403)

        zam_id = request.data.get('zamestnanec_id')
        vytvorit = bool(request.data.get('vytvorit', True))
        jmeno = (request.data.get('jmeno') or '').strip() or None
        ano = request.data.get('ano')
        if ano is None:
            ano = True if (vytvorit or zam_id) else False
        else:
            ano = bool(ano)

        try:
            payload = set_majitelka_pracuje(
                user.salon,
                ano=ano,
                jmeno=jmeno,
                zamestnanec_id=int(zam_id) if zam_id else None,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        user.refresh_from_db()
        log_audit(
            user.salon,
            _actor(user),
            'nastaveni',
            'majitelka také pracuje — zapnuto' if ano else 'majitelka také pracuje — vypnuto',
            po=payload,
        )
        data = flow_user_do_dict(user)
        data['majitelka_pracuje'] = payload
        return Response(data)

    def delete(self, request):
        user, err = require_flow_owner(request)
        if err:
            return err
        from flow.auth import flow_user_do_dict, prepnout_personu
        from flow.persona_service import set_majitelka_pracuje

        payload = set_majitelka_pracuje(user.salon, ano=False)
        user.refresh_from_db()
        try:
            prepnout_personu(user, 'majitel')
        except ValueError:
            pass
        log_audit(
            user.salon,
            _actor(user),
            'nastaveni',
            'majitelka také pracuje — vypnuto',
            po=payload,
        )
        data = flow_user_do_dict(user)
        data['majitelka_pracuje'] = payload
        return Response(data)

