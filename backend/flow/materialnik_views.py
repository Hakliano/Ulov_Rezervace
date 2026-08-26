"""FLOW proxy na spotřebu v Materiálníku — rezervace už je uložená, timeout krátký."""

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.permissions import FlowPermission
from flow.provoz_views import _flow_user, _own_rezervace_or_403
from partner_admin.materialnik_client import (
    MaterialnikRejected,
    MaterialnikUnavailable,
    confirm_consume,
    consume_preview,
    stock_summary,
)
from partner_admin.models import MODUL_MATERIALNIK, PartnerModul
from partner_admin.services_moduly import partner_modul
from rezervace.models import Rezervace


def _aktivni_modul_nebo_404(salon):
    row = partner_modul(salon, MODUL_MATERIALNIK)
    if not row or row.status != PartnerModul.STAV_ACTIVE:
        return None, Response({'detail': 'Nenalezeno.'}, status=404)
    return row, None


def _payload_z_rezervace(rezervace):
    partner = rezervace.salon.partner_nastaveni
    return {
        'reservation_ref': f'rezervace:{rezervace.pk}',
        'completed_at': (rezervace.dokonceno_at.isoformat() if rezervace.dokonceno_at else None),
        'services': [
            {
                'external_service_id': f'cenik:{p.sluzba_id}',
                'name': p.sluzba.nazev,
                'quantity': 1,
            }
            for p in rezervace.polozky.select_related('sluzba').all()
        ],
        'tenant_external_id': f'salon:{rezervace.salon_id}',
    }


class FlowMaterialnikSpotrebaView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        row, err = _aktivni_modul_nebo_404(user.salon)
        if err:
            return err
        partner = rezervace.salon.partner_nastaveni
        try:
            data = consume_preview(
                tenant_uuid=partner.tenant_uuid,
                hmac_key=row.hmac_key,
                payload=_payload_z_rezervace(rezervace),
            )
        except MaterialnikUnavailable:
            return Response(
                {
                    'detail': 'Spotřebu teď nelze načíst. Rezervaci to neovlivní.',
                    'unavailable': True,
                    'lines': [],
                },
                status=200,
            )
        except MaterialnikRejected as exc:
            return Response({'detail': exc.detail, 'lines': []}, status=200)
        return Response(data)

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        row, err = _aktivni_modul_nebo_404(user.salon)
        if err:
            return err
        partner = rezervace.salon.partner_nastaveni
        lines = request.data.get('lines')
        if not isinstance(lines, list):
            return Response({'detail': 'Chybí řádky spotřeby.'}, status=400)
        payload = _payload_z_rezervace(rezervace)
        payload['lines'] = lines
        payload['confirmed'] = True
        try:
            data = confirm_consume(
                tenant_uuid=partner.tenant_uuid,
                hmac_key=row.hmac_key,
                payload=payload,
            )
        except MaterialnikUnavailable:
            return Response(
                {'detail': 'Spotřebu teď nelze uložit. Rezervace platí, zkuste to v Materiálníku.'},
                status=503,
            )
        except MaterialnikRejected as exc:
            return Response({'detail': exc.detail}, status=exc.status_code if exc.status_code < 500 else 400)
        return Response(data)


class FlowMaterialnikPrehledView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        row, err = _aktivni_modul_nebo_404(user.salon)
        if err:
            return err
        partner = user.salon.partner_nastaveni
        empty = {
            'unavailable': True,
            'kpi': {'below': 0, 'critical': 0, 'shopping': 0, 'total': 0},
            'items': [],
        }
        try:
            data = stock_summary(
                tenant_uuid=partner.tenant_uuid,
                hmac_key=row.hmac_key,
            )
        except MaterialnikUnavailable:
            return Response(empty, status=200)
        except MaterialnikRejected:
            return Response(empty, status=200)
        data = data or {}
        data.setdefault('unavailable', False)
        data.setdefault('items', [])
        data.setdefault('kpi', empty['kpi'])
        return Response(data)
