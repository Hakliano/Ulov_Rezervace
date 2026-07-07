"""Získání IP adresy klienta (včetně reverse proxy)."""


def get_client_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        ip = xff.split(',')[0].strip()
        if ip:
            return ip
    return request.META.get('REMOTE_ADDR') or None


def get_user_agent(request):
    if not request:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:300]
