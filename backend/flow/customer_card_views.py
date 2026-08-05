"""REST + veřejné potvrzení — FLOW Karta zákazníka."""
from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import get_flow_user_from_request
from flow.customer_card_emails import email_customer_card_confirm
from flow.customer_card_models import CustomerCard, CustomerVisit
from flow.customer_card_serializers import (
    CustomerCardCreateSerializer,
    CustomerCardDetailSerializer,
    CustomerCardListSerializer,
    CustomerCardUpdateSerializer,
    CustomerVisitCreateSerializer,
)
from flow.customer_card_services import (
    card_with_visits,
    client_ip,
    normalize_email,
)
from flow.permissions import FlowPermission


def _user(request):
    return get_flow_user_from_request(request)


def _card_for_salon(user, card_id: int) -> CustomerCard | None:
    return CustomerCard.objects.filter(salon_id=user.salon_id, pk=card_id).first()


class CustomerCardListCreateView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        qs = CustomerCard.objects.filter(salon_id=user.salon_id).order_by('-upraveno')
        q = (request.query_params.get('q') or '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(email__icontains=q) | Q(jmeno__icontains=q))
        stav = (request.query_params.get('stav') or '').strip()
        if stav in (CustomerCard.STAV_CEKA, CustomerCard.STAV_AKTIVNI):
            qs = qs.filter(stav=stav)
        return Response(CustomerCardListSerializer(qs, many=True).data)

    def post(self, request):
        user = _user(request)
        ser = CustomerCardCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        email = normalize_email(data['email'])

        if CustomerCard.objects.filter(salon_id=user.salon_id, email__iexact=email).exists():
            return Response(
                {'detail': 'Pro tento e-mail už u vás zákaznická karta existuje.'},
                status=status.HTTP_409_CONFLICT,
            )

        autor_jmeno = user.zamestnanec.jmeno if user.zamestnanec_id else user.email
        try:
            with transaction.atomic():
                card = CustomerCard(
                    salon_id=user.salon_id,
                    email=email,
                    jmeno=(data.get('jmeno') or '').strip(),
                    telefon=(data.get('telefon') or '').strip(),
                    poznamka=(data.get('poznamka') or '').strip(),
                    stav=CustomerCard.STAV_CEKA,
                    vytvoril=user,
                )
                if data.get('odeslat_potvrzeni', True):
                    card.issue_confirm_token()
                card.save()
                CustomerVisit.objects.create(
                    card=card,
                    datum=data['visit_datum'],
                    text=data['visit_text'].strip(),
                    autor=user,
                    autor_jmeno=autor_jmeno,
                )
        except IntegrityError:
            return Response(
                {'detail': 'Pro tento e-mail už u vás zákaznická karta existuje.'},
                status=status.HTTP_409_CONFLICT,
            )

        email_ok = False
        if data.get('odeslat_potvrzeni', True) and card.confirm_token:
            email_ok = email_customer_card_confirm(card)

        detail = card_with_visits(user.salon_id, card.id)
        payload = CustomerCardDetailSerializer(detail).data
        payload['email_odeslan'] = email_ok
        return Response(payload, status=status.HTTP_201_CREATED)


class CustomerCardDetailView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request, card_id):
        user = _user(request)
        card = card_with_visits(user.salon_id, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        return Response(CustomerCardDetailSerializer(card).data)

    def patch(self, request, card_id):
        user = _user(request)
        card = _card_for_salon(user, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        ser = CustomerCardUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for field in ('jmeno', 'telefon', 'poznamka'):
            if field in ser.validated_data:
                setattr(card, field, (ser.validated_data[field] or '').strip())
        card.save()
        return Response(CustomerCardDetailSerializer(card_with_visits(user.salon_id, card.id)).data)

    def delete(self, request, card_id):
        """Vyřadit zákazníka — nevratné smazání karty i historie."""
        user = _user(request)
        card = _card_for_salon(user, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerCardSendConfirmView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, card_id):
        user = _user(request)
        card = _card_for_salon(user, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        if card.stav == CustomerCard.STAV_AKTIVNI:
            return Response({'detail': 'Karta je již aktivní.'}, status=400)
        card.issue_confirm_token()
        card.save(update_fields=[
            'confirm_token', 'confirm_token_expires_at', 'confirm_token_used_at', 'upraveno',
        ])
        email_ok = email_customer_card_confirm(card)
        return Response({
            'detail': 'Žádost o potvrzení odeslána.' if email_ok else 'Token připraven; e-mail se nepodařilo odeslat (SMTP).',
            'email_odeslan': email_ok,
            'stav': card.stav,
        })


class CustomerCardActivateLocalView(APIView):
    """Lokální / DEBUG: aktivace karty bez e-mailového potvrzení."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, card_id):
        if not settings.DEBUG:
            return Response({'detail': 'Jen při DEBUG=True (lokální vývoj).'}, status=403)
        user = _user(request)
        card = _card_for_salon(user, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        if card.stav == CustomerCard.STAV_AKTIVNI:
            return Response(CustomerCardDetailSerializer(
                card_with_visits(user.salon_id, card.id)
            ).data)
        now = timezone.now()
        card.stav = CustomerCard.STAV_AKTIVNI
        card.confirmed_at = now
        card.confirmed_ip = '127.0.0.1'
        card.confirm_token_used_at = now
        card.save(update_fields=[
            'stav', 'confirmed_at', 'confirmed_ip', 'confirm_token_used_at', 'upraveno',
        ])
        return Response(CustomerCardDetailSerializer(
            card_with_visits(user.salon_id, card.id)
        ).data)


class CustomerCardVisitCreateView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, card_id):
        user = _user(request)
        card = _card_for_salon(user, card_id)
        if not card:
            return Response({'detail': 'Karta nenalezena.'}, status=404)
        if card.stav != CustomerCard.STAV_AKTIVNI:
            return Response(
                {'detail': 'Další zápisy lze přidávat jen u aktivní (potvrzené) karty.'},
                status=400,
            )
        ser = CustomerVisitCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        autor_jmeno = user.zamestnanec.jmeno if user.zamestnanec_id else user.email
        CustomerVisit.objects.create(
            card=card,
            datum=ser.validated_data['datum'],
            text=ser.validated_data['text'].strip(),
            autor=user,
            autor_jmeno=autor_jmeno,
        )
        card.save(update_fields=['upraveno'])
        return Response(
            CustomerCardDetailSerializer(card_with_visits(user.salon_id, card.id)).data,
            status=201,
        )


class CustomerCardLookupView(APIView):
    """Ověření existence aktivní karty podle e-mailu (pro rezervace UI)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        email = normalize_email(request.query_params.get('email') or '')
        if not email:
            return Response({'customer_card_id': None})
        card = CustomerCard.objects.filter(
            salon_id=user.salon_id,
            email__iexact=email,
            stav=CustomerCard.STAV_AKTIVNI,
        ).first()
        return Response({
            'customer_card_id': card.id if card else None,
            'jmeno': card.jmeno if card else '',
            'stav': card.stav if card else None,
        })


@method_decorator(csrf_exempt, name='dispatch')
class CustomerCardConfirmPublicView(APIView):
    """Veřejná stránka potvrzení (GET HTML, POST souhlas). Bez FLOW tokenu."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        card = CustomerCard.objects.select_related('salon').filter(confirm_token=token).first()
        if not card or not card.token_je_platny():
            return render(request, 'flow/customer_card_confirm_page.html', {
                'error': 'Odkaz je neplatný, vypršel, nebo už byl použit.',
            })
        return render(request, 'flow/customer_card_confirm_page.html', {
            'salon_name': card.salon.name,
            'token': token,
        })

    def post(self, request, token):
        card = CustomerCard.objects.select_related('salon').filter(confirm_token=token).first()
        if not card or not card.token_je_platny():
            return render(request, 'flow/customer_card_confirm_page.html', {
                'error': 'Odkaz je neplatný, vypršel, nebo už byl použit.',
            })
        now = timezone.now()
        card.stav = CustomerCard.STAV_AKTIVNI
        card.confirmed_at = now
        card.confirmed_ip = client_ip(request)
        card.confirm_token_used_at = now
        card.save(update_fields=[
            'stav', 'confirmed_at', 'confirmed_ip', 'confirm_token_used_at', 'upraveno',
        ])
        return render(request, 'flow/customer_card_confirm_page.html', {
            'success': True,
            'salon_name': card.salon.name,
        })
