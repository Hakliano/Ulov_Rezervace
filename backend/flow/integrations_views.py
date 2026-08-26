"""SSO a katalog pro Materiálník. Veřejné jen přes m2m klíč z Materiálníku."""

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from django.conf import settings

from partner_admin.models import MODUL_MATERIALNIK, PartnerModul
from partner_admin.services_moduly import partner_modul
from rezervace.models import Zamestnanec
from rezervace.services.staff_auth import normalizuj_prihlasovaci_jmeno
from salons.models import CenikPolozka


def _m2m_ok(request):
    expected = (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()
    got = (request.headers.get('X-Ulov-M2M-Key') or '').strip()
    if not expected or not got or expected != got:
        return False
    return True


def _najdi_staff(email):
    from flow.models import FlowUser

    login = normalizuj_prihlasovaci_jmeno(email)
    if not login or '@' not in login:
        return None
    try:
        flow = FlowUser.objects.select_related('zamestnanec', 'salon').get(email__iexact=login)
        return flow.zamestnanec
    except FlowUser.DoesNotExist:
        pass
    except FlowUser.MultipleObjectsReturned:
        return None
    try:
        return Zamestnanec.objects.select_related('salon').get(prihlasovaci_jmeno=login)
    except (Zamestnanec.DoesNotExist, Zamestnanec.MultipleObjectsReturned):
        return None


def _heslo_ok(staff, password):
    from flow.models import FlowUser

    if not password:
        return False
    if staff.password_hash and staff.check_password(password):
        return True
    try:
        fu = staff.flow_ucet
    except FlowUser.DoesNotExist:
        return False
    return bool(fu.password_hash and fu.check_password(password))


class MaterialnikSessionView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not _m2m_ok(request):
            return Response({'detail': 'Neplatný klíč.'}, status=status.HTTP_401_UNAUTHORIZED)
        email = request.data.get('email') or ''
        password = request.data.get('password') or ''
        staff = _najdi_staff(email)
        if staff is None or not _heslo_ok(staff, password):
            return Response({'detail': 'Nesprávný e-mail nebo heslo.'}, status=status.HTTP_401_UNAUTHORIZED)
        if staff.role != 'majitel' and not staff.aktivni:
            return Response({'detail': 'Účet je deaktivován.'}, status=status.HTTP_403_FORBIDDEN)

        row = partner_modul(staff.salon, MODUL_MATERIALNIK)
        if not row or row.status != PartnerModul.STAV_ACTIVE:
            return Response(
                {'detail': 'Nesprávný e-mail nebo heslo.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        partner = staff.salon.partner_nastaveni
        return Response({
            'tenant_uuid': str(partner.tenant_uuid),
            'salon_id': staff.salon_id,
            'salon_name': staff.salon.name,
            'staff': {
                'id': staff.id,
                'jmeno': staff.jmeno,
                'role': staff.role,
                'je_majitel': staff.role == 'majitel',
            },
        })


class MaterialnikCatalogView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not _m2m_ok(request):
            return Response({'detail': 'Neplatný klíč.'}, status=status.HTTP_401_UNAUTHORIZED)
        tenant_uuid = (request.query_params.get('tenant_uuid') or '').strip()
        if not tenant_uuid:
            return Response({'detail': 'Chybí tenant.'}, status=status.HTTP_400_BAD_REQUEST)
        from partner_admin.models import PartnerNastaveni

        try:
            partner = PartnerNastaveni.objects.select_related('salon').get(tenant_uuid=tenant_uuid)
        except PartnerNastaveni.DoesNotExist:
            return Response({'detail': 'Nenalezeno.'}, status=status.HTTP_404_NOT_FOUND)
        row = partner_modul(partner.salon, MODUL_MATERIALNIK)
        if not row or row.status != PartnerModul.STAV_ACTIVE:
            return Response({'detail': 'Nenalezeno.'}, status=status.HTTP_404_NOT_FOUND)

        sluzby = CenikPolozka.objects.filter(salon=partner.salon).order_by('poradi', 'id')
        return Response({
            'tenant_uuid': str(partner.tenant_uuid),
            'services': [
                {
                    'external_service_id': f'cenik:{s.id}',
                    'name': s.nazev,
                    'active': s.aktivni,
                }
                for s in sluzby
            ],
        })
