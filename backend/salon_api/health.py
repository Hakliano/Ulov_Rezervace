"""Health check endpoint pro monitoring (Uptime Kuma, load balancer).

GET /health/ → 200 když DB (a případně Redis) odpovídá,
              503 když kritická závislost selže.
"""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def health(request):
    db_ok = True
    db_detail = 'ok'
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 — health check nesmí nikdy spadnout
        db_ok = False
        db_detail = f'error: {exc.__class__.__name__}'

    redis_url = getattr(settings, 'REDIS_URL', '') or ''
    if redis_url:
        try:
            cache.set('healthcheck', '1', timeout=5)
            redis_ok = cache.get('healthcheck') == '1'
            redis_detail = 'ok' if redis_ok else 'error: readback failed'
        except Exception as exc:  # noqa: BLE001
            redis_ok = False
            redis_detail = f'error: {exc.__class__.__name__}'
    else:
        redis_ok = True
        redis_detail = 'skipped'

    email_via_celery = bool(getattr(settings, 'EMAIL_VIA_CELERY', False))
    critical_ok = db_ok and redis_ok

    payload = {
        'status': 'ok' if critical_ok else 'error',
        'database': db_detail,
        'redis': redis_detail,
        'email_via_celery': email_via_celery,
    }
    return JsonResponse(payload, status=200 if critical_ok else 503)
