"""Health check endpoint pro monitoring (Uptime Kuma, load balancer).

GET /health/ → 200 když DB (a případně Redis) odpovídá,
              503 když kritická závislost selže.

Při REDIS_URL navíc hlásí hloubku Celery fronty (informační, ne 503).
"""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def _celery_queue_depth(redis_url: str):
    """Počet čekajících úloh ve výchozí frontě Celery (klíč `celery`)."""
    try:
        import redis

        client = redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        depth = int(client.llen('celery') or 0)
        client.close()
        return depth, None
    except Exception as exc:  # noqa: BLE001
        return None, exc.__class__.__name__


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
    queue_depth = None
    if redis_url:
        try:
            cache.set('healthcheck', '1', timeout=5)
            redis_ok = cache.get('healthcheck') == '1'
            redis_detail = 'ok' if redis_ok else 'error: readback failed'
        except Exception as exc:  # noqa: BLE001
            redis_ok = False
            redis_detail = f'error: {exc.__class__.__name__}'

        depth, q_err = _celery_queue_depth(redis_url)
        if q_err:
            queue_detail = f'error: {q_err}'
        else:
            queue_depth = depth
            # Informační stav — vysoká fronta neháže 503 (Uptime by falešně alarmoval).
            queue_detail = 'ok' if depth < 50 else f'backlog:{depth}'
    else:
        redis_ok = True
        redis_detail = 'skipped'
        queue_detail = 'skipped'

    email_via_celery = bool(getattr(settings, 'EMAIL_VIA_CELERY', False))
    critical_ok = db_ok and redis_ok

    payload = {
        'status': 'ok' if critical_ok else 'error',
        'database': db_detail,
        'redis': redis_detail,
        'celery_queue': queue_detail,
        'email_via_celery': email_via_celery,
    }
    if queue_depth is not None:
        payload['celery_queue_depth'] = queue_depth

    return JsonResponse(payload, status=200 if critical_ok else 503)
