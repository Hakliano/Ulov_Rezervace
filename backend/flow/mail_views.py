from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import get_flow_user_from_request
from flow.mail_service import MailError, get_imap_config, get_message, list_messages, send_mail_message
from flow.permissions import FlowPermission


def _user(request):
    return get_flow_user_from_request(request)


class FlowMailStavView(APIView):
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        cfg = get_imap_config(user.salon)
        return Response({
            'ready': cfg['ready'],
            'enabled': cfg['enabled'],
            'mailbox': cfg['mailbox'],
            'imap_host': cfg['host'],
        })


class FlowMailListView(APIView):
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _user(request)
        try:
            limit = int(request.query_params.get('limit') or 40)
            offset = int(request.query_params.get('offset') or 0)
            data = list_messages(user.salon, limit=limit, offset=offset)
            return Response(data)
        except MailError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception:
            return Response({'detail': 'Načtení schránky selhalo.'}, status=502)


class FlowMailDetailView(APIView):
    permission_classes = [FlowPermission]

    def get(self, request, uid):
        user = _user(request)
        try:
            data = get_message(user.salon, uid, mark_seen=True)
            return Response(data)
        except MailError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception:
            return Response({'detail': 'Načtení zprávy selhalo.'}, status=502)


class FlowMailOdeslatView(APIView):
    permission_classes = [FlowPermission]

    def post(self, request):
        user = _user(request)
        data = request.data or {}
        try:
            result = send_mail_message(
                user.salon,
                to=data.get('to'),
                subject=data.get('subject'),
                body=data.get('body'),
                reply_uid=data.get('reply_uid') or None,
            )
            return Response(result)
        except MailError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception:
            return Response({'detail': 'Odeslání selhalo.'}, status=502)
