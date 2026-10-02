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


class KalkulaceRateThrottle(IPRateThrottle):
    """POST odeslání kalkulace — 10 / 10 minut / IP.

    Živé přepočítávání běží jen v prohlížeči. Načtení stránky a jiné
    než POST metody se do limitu nepočítají. Scope je oddělený od poptávky,
    aby obchodník mohl během schůzky poslat několik variant.
    """
    scope = 'kalkulace'
    rate = '10/10min'

    def allow_request(self, request, view):
        if getattr(request, 'method', '').upper() != 'POST':
            return True
        return super().allow_request(request, view)

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        num, period = rate.split('/', 1)
        period = period.strip().lower()
        if period in ('10min', '10m', '10minutes'):
            return (int(num), 600)
        return super().parse_rate(rate)
