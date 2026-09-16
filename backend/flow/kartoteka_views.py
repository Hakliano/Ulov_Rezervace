"""FLOW kartotéka proxy — čtení i zápis archivnik.models, auth X-Flow-Token."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import get_flow_user_from_request
from flow.kartoteka_services import (
    LIST_PAGE_SIZE_DEFAULT,
    KartotekaError,
    create_customer_from_flow,
    create_entry_from_flow,
    create_object_from_flow,
    customer_detail,
    customer_for_email,
    list_assignable_object_types,
    list_customers,
    serialize_customer_list_item,
)
from flow.permissions import FlowPermission


def _user(request):
    return get_flow_user_from_request(request)


def _page_params(request):
    try:
        page = int(request.query_params.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size') or LIST_PAGE_SIZE_DEFAULT)
    except (TypeError, ValueError):
        page_size = LIST_PAGE_SIZE_DEFAULT
    return page, page_size


class KartotekaCustomerListView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        page, page_size = _page_params(request)
        payload = list_customers(
            user.salon_id,
            q=request.query_params.get('q') or '',
            stav=request.query_params.get('stav') or '',
            page=page,
            page_size=page_size,
        )
        return Response(payload)

    def post(self, request):
        user = _user(request)
        try:
            result = create_customer_from_flow(user, request.data)
        except KartotekaError as exc:
            return exc.as_response()
        return Response(result['body'], status=result['status'])


class KartotekaCustomerLookupView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        email = request.query_params.get('email') or ''
        customer = customer_for_email(user.salon_id, email)
        if not customer:
            return Response({'uuid': None})
        return Response(serialize_customer_list_item(customer))


class KartotekaCustomerDetailView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request, customer_uuid):
        user = _user(request)
        payload = customer_detail(user.salon_id, customer_uuid)
        if not payload:
            return Response({'detail': 'Zákazník nenalezen.'}, status=404)
        return Response(payload)


class KartotekaEntryCreateView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, customer_uuid):
        user = _user(request)
        try:
            payload = create_entry_from_flow(user, customer_uuid, request.data)
        except KartotekaError as exc:
            return exc.as_response()
        return Response(payload, status=201)


class KartotekaObjectCreateView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, customer_uuid):
        user = _user(request)
        try:
            payload = create_object_from_flow(user, customer_uuid, request.data)
        except KartotekaError as exc:
            return exc.as_response()
        return Response(payload, status=201)


class KartotekaObjectTypeListView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        return Response(list_assignable_object_types(user.salon))
