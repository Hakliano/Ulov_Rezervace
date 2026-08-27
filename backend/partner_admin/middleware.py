import re
import traceback

from django.http import JsonResponse

from .models import PartnerNastaveni, TechnickaChyba


SALON_API_RE = re.compile(r'^/api/salon/(\d+)(?:/|$)')
SKIP_PREFIXES = ('/static/', '/favicon', '/admin/jsi18n/')
CITLIVE_PARAMETRY = ('password', 'token', 'secret', 'key', 'csrf', 'session', 'auth')


def _salon_id_z_cesty(path):
    match = SALON_API_RE.match(path or '')
    return int(match.group(1)) if match else None


def _bezpecny_query(request):
    casti = []
    for klic, hodnota in request.GET.items():
        lower = klic.lower()
        if any(slovo in lower for slovo in CITLIVE_PARAMETRY):
            casti.append(f'{klic}=***')
        else:
            casti.append(f'{klic}={str(hodnota)[:80]}')
    return '&'.join(casti)[:400]


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
    """Ukládá traceback a zprávu výjimky. Nikdy request body, hesla ani HTTP hlavičky."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            response.status_code >= 500
            and not getattr(request, '_technical_error_logged', False)
        ):
            self._uloz(
                request,
                typ_chyby=f'HTTP {response.status_code}',
                detail=f'Server vrátil {response.status_code} na {request.path}.',
                status_kod=response.status_code,
            )
        return response

    def process_exception(self, request, exception):
        request._technical_error_logged = True
        self._uloz(
            request,
            typ_chyby=exception.__class__.__name__,
            detail=str(exception)[:4000] or exception.__class__.__name__,
            status_kod=500,
            exception=exception,
        )
        return None

    @staticmethod
    def _uloz(request, typ_chyby, detail, status_kod=None, exception=None):
        cesta = request.path or ''
        if cesta.startswith(SKIP_PREFIXES):
            return
        stopa = ''
        if exception is not None:
            stopa = ''.join(
                traceback.format_exception(exception.__class__, exception, exception.__traceback__)
            )[:12000]
        try:
            salon_id = _salon_id_z_cesty(cesta)
            TechnickaChyba.objects.create(
                salon_id=salon_id,
                metoda=(request.method or '')[:10],
                cesta=cesta[:500],
                query=_bezpecny_query(request),
                status_kod=status_kod,
                typ_chyby=typ_chyby[:200],
                detail=detail[:8000],
                stopa=stopa,
            )
        except Exception:
            # Chybový logger nesmí nikdy způsobit další chybu aplikace.
            pass
