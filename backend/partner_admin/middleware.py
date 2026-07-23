import re

from django.http import JsonResponse

from .models import PartnerNastaveni, TechnickaChyba


SALON_API_RE = re.compile(r'^/api/salon/(\d+)(?:/|$)')


def _salon_id_z_cesty(path):
    match = SALON_API_RE.match(path or '')
    return int(match.group(1)) if match else None


class BlokovanyPartnerMiddleware:
    """Zastaví API salonu, ale nikdy superadmin panel ani ostatní salony."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'OPTIONS':
            salon_id = _salon_id_z_cesty(request.path)
            if salon_id and PartnerNastaveni.objects.filter(
                salon_id=salon_id,
                stav=PartnerNastaveni.STAV_BLOCKED,
            ).exists():
                return JsonResponse(
                    {
                        'detail': 'Služba salonu je dočasně pozastavena.',
                        'kod': 'salon_blocked',
                    },
                    status=423,
                )
        return self.get_response(request)


class TechnickeChybyMiddleware:
    """Ukládá jen bezpečné minimum; nikdy request body, hesla ani hlavičky."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 500 and not getattr(request, '_technical_error_logged', False):
            self._uloz(
                request,
                typ_chyby=f'HTTP {response.status_code}',
                detail='Server vrátil chybovou odpověď.',
            )
        return response

    def process_exception(self, request, exception):
        request._technical_error_logged = True
        self._uloz(
            request,
            typ_chyby=exception.__class__.__name__,
            detail='Neočekávaná serverová chyba.',
        )
        return None

    @staticmethod
    def _uloz(request, typ_chyby, detail):
        try:
            salon_id = _salon_id_z_cesty(request.path)
            TechnickaChyba.objects.create(
                salon_id=salon_id,
                metoda=(request.method or '')[:10],
                cesta=(request.path or '')[:500],
                typ_chyby=typ_chyby[:200],
                detail=detail[:500],
            )
        except Exception:
            # Chybový logger nesmí nikdy způsobit další chybu aplikace.
            pass
