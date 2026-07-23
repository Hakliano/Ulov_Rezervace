from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from partner_hub.models import get_partner_user, partner_login
from salons.models import Salon
from salons.serializers import SalonSerializer


class PartnerPrihlaseniView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        try:
            session = partner_login(username, password)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({
            'token': str(session.token),
            'user': {
                'username': session.user.username,
                'is_superuser': session.user.is_superuser,
            },
        })


class PartnerMeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_partner_user(request)
        if not user:
            return Response({'detail': 'Nejste přihlášeni.'}, status=401)
        return Response({
            'username': user.username,
            'is_superuser': user.is_superuser,
        })


class PartnerSalonyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_partner_user(request)
        if not user:
            return Response({'detail': 'Nejste přihlášeni.'}, status=401)
        qs = Salon.objects.all().order_by('id')
        data = [{'id': s.id, 'name': s.name, 'email': s.email, 'phone': s.phone} for s in qs]
        return Response(data)


class PartnerSalonDetailView(APIView):
    """Čtení veřejného payloadu salonu (stejné jako majitelka web admin GET)."""
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        user = get_partner_user(request)
        if not user:
            return Response({'detail': 'Nejste přihlášeni.'}, status=401)
        try:
            salon = Salon.objects.get(pk=pk)
        except Salon.DoesNotExist:
            return Response({'detail': 'Salon nenalezen.'}, status=404)
        return Response(SalonSerializer(salon).data)
