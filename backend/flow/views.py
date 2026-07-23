from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import (
    HEADER,
    flow_user_do_dict,
    get_flow_user_from_request,
    odhlasit_flow,
    prihlasit_flow,
    zrusit_vsechny_sessiony,
)
from flow.emails import email_flow_pristup, generate_heslo
from flow.models import FlowUser, heslo_je_platne
from flow.serializers import (
    FlowChangePasswordSerializer,
    FlowCreateSerializer,
    FlowLoginSerializer,
    FlowPatchSerializer,
    FlowUserPublicSerializer,
)
from rezervace.models import Zamestnanec
from salons.models import Salon
from salons.permissions import MajitelPermission


class FlowUctyListCreateView(APIView):
    """Majitelka: seznam FLOW účtů / vytvoření přístupu."""

    permission_classes = [MajitelPermission]

    def get(self, request, pk):
        qs = FlowUser.objects.filter(salon_id=pk).select_related('zamestnanec').order_by('email')
        return Response(FlowUserPublicSerializer(qs, many=True).data)

    def post(self, request, pk):
        salon = get_object_or_404(Salon, pk=pk)
        ser = FlowCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        zam = get_object_or_404(Zamestnanec, pk=data['zamestnanec_id'], salon=salon)
        if hasattr(zam, 'flow_ucet'):
            return Response(
                {'detail': 'Tento pracovník už má přístup do FLOW. Použijte reset hesla.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = data['email'].strip().lower()
        if FlowUser.objects.filter(email__iexact=email).exists():
            return Response(
                {'detail': 'Tento e-mail už je použit u jiného FLOW účtu.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        heslo = generate_heslo(12)
        # generate_heslo už obsahuje písmena i číslice; pojistka pravidel
        if not heslo_je_platne(heslo):
            heslo = generate_heslo(12) + '1a'

        user = FlowUser(
            salon=salon,
            zamestnanec=zam,
            email=email,
            visible_overview=bool(data.get('visible_overview')),
            aktivni=True,
        )
        user.set_password(heslo)
        user.save()

        email_ok = email_flow_pristup(user, heslo, reset=False)
        return Response(
            {
                'ucet': FlowUserPublicSerializer(user).data,
                'email_odeslan': bool(email_ok),
                'detail': (
                    'Přístup vytvořen. Dočasné heslo bylo odesláno e-mailem.'
                    if email_ok
                    else 'Přístup vytvořen, ale e-mail se nepodařilo odeslat. Zkontrolujte SMTP a použijte reset hesla.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class FlowUcetDetailView(APIView):
    permission_classes = [MajitelPermission]

    def patch(self, request, pk, ucet_id):
        user = get_object_or_404(FlowUser, pk=ucet_id, salon_id=pk)
        ser = FlowPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        if 'visible_overview' in data:
            user.visible_overview = data['visible_overview']
        if 'aktivni' in data:
            user.aktivni = data['aktivni']
            if not user.aktivni:
                zrusit_vsechny_sessiony(user)
        user.save()
        return Response(FlowUserPublicSerializer(user).data)


class FlowUcetResetHeslaView(APIView):
    permission_classes = [MajitelPermission]

    def post(self, request, pk, ucet_id):
        user = get_object_or_404(FlowUser, pk=ucet_id, salon_id=pk)
        heslo = generate_heslo(12)
        if not heslo_je_platne(heslo):
            heslo = generate_heslo(12) + '1a'
        user.set_password(heslo)
        user.save(update_fields=['password_hash', 'upraveno'])
        zrusit_vsechny_sessiony(user)
        email_ok = email_flow_pristup(user, heslo, reset=True)
        return Response(
            {
                'email_odeslan': bool(email_ok),
                'detail': (
                    'Nové heslo odesláno e-mailem.'
                    if email_ok
                    else 'Heslo bylo resetováno, ale e-mail se nepodařilo odeslat.'
                ),
            }
        )


class FlowUcetProZamestnanceView(APIView):
    """Stav FLOW u konkrétního pracovníka (pro UI v rezervacích)."""

    permission_classes = [MajitelPermission]

    def get(self, request, pk, zamestnanec_id):
        zam = get_object_or_404(Zamestnanec, pk=zamestnanec_id, salon_id=pk)
        try:
            user = zam.flow_ucet
        except FlowUser.DoesNotExist:
            return Response({'ma_flow': False, 'ucet': None})
        return Response({'ma_flow': True, 'ucet': FlowUserPublicSerializer(user).data})


class FlowPrihlaseniView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = FlowLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            session, user = prihlasit_flow(ser.validated_data['email'], ser.validated_data['password'])
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'token': str(session.token), 'user': flow_user_do_dict(user)})


class FlowOdhlaseniView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        odhlasit_flow(request.headers.get(HEADER, ''))
        return Response({'ok': True})


class FlowMeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_flow_user_from_request(request)
        if not user:
            return Response({'detail': 'Nejste přihlášeni.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(flow_user_do_dict(user))


class FlowZmenaHeslaView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_flow_user_from_request(request)
        if not user:
            return Response({'detail': 'Nejste přihlášeni.'}, status=status.HTTP_401_UNAUTHORIZED)
        ser = FlowChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not user.check_password(ser.validated_data['current_password']):
            return Response({'detail': 'Současné heslo nesedí.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(ser.validated_data['new_password'])
        user.save(update_fields=['password_hash', 'upraveno'])
        return Response({'detail': 'Heslo bylo změněno.'})
