"""Health check endpoint pro monitoring (Uptime Kuma, load balancer).

GET /health/ → 200 {"status": "ok", "database": "ok"} když je vše v pořádku,
              503 {"status": "error", "database": "..."} když DB neodpovídá.
"""

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

    payload = {
        'status': 'ok' if db_ok else 'error',
        'database': db_detail,
    }
    return JsonResponse(payload, status=200 if db_ok else 503)
