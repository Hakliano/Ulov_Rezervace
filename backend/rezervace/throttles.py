"""Rate limiting podle IP adresy."""

from rest_framework.throttling import SimpleRateThrottle

from rezervace.services.client_ip import get_client_ip


class IPRateThrottle(SimpleRateThrottle):
    """Základní throttle podle IP (ne podle uživatele)."""

    def get_cache_key(self, request, view):
        ident = get_client_ip(request) or 'unknown'
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class LoginRateThrottle(IPRateThrottle):
    scope = 'login'
    rate = '5/min'


class RezervaceRateThrottle(IPRateThrottle):
    scope = 'rezervace'
    rate = '20/hour'


class PasswordResetRateThrottle(IPRateThrottle):
    scope = 'password_reset'
    rate = '3/hour'


class EmailPotvrzeniRateThrottle(IPRateThrottle):
    scope = 'email_potvrzeni'
    rate = '10/hour'


class PoptavkaRateThrottle(IPRateThrottle):
    scope = 'poptavka'
    rate = '5/hour'
