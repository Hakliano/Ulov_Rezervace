from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return JsonResponse({'status': 'ok'})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({'status': 'error', 'detail': exc.__class__.__name__}, status=503)
