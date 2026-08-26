from django.conf import settings

from .models import Alert, ShoppingListItem


def nav(request):
    if not getattr(request, 'materialnik_session', None):
        return {}
    session = request.materialnik_session
    name = session.staff_name or ''
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    else:
        initials = (name[:2] or 'M').upper()
    flow_url = (getattr(settings, 'FLOW_PUBLIC_URL', '') or '').rstrip('/')
    return {
        'nav_shopping': ShoppingListItem.objects.filter(status=ShoppingListItem.STAV_OPEN).count(),
        'nav_alerts': Alert.objects.filter(status=Alert.STAV_OPEN).count(),
        'staff_initials': initials,
        'staff_role': 'manažer' if session.je_majitel else 'personál',
        'flow_public_url': (flow_url + '/') if flow_url else '',
    }
