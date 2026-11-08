from django.conf import settings
from django.urls import set_script_prefix
from whitenoise.middleware import WhiteNoiseMiddleware


def static_candidates(path):
    """Odkaz v HTML má prefix (/postak/static/…), soubor leží na /static/…"""
    prefix = (settings.POSTAK_PREFIX or '').rstrip('/')
    found = [path]
    marker = f'{prefix}/static/'
    if prefix and path.startswith(marker):
        found.append('/static/' + path[len(marker):])
    elif prefix and path.startswith('/static/'):
        found.append(prefix + path)
    return found


class PostakStaticMiddleware(WhiteNoiseMiddleware):
    def __call__(self, request):
        original = request.path_info
        try:
            for candidate in static_candidates(original):
                if self.autorefresh:
                    static_file = self.find_file(candidate)
                else:
                    static_file = self.files.get(candidate)
                if static_file is not None:
                    request.path_info = candidate
                    return self.serve(static_file, request)
            return self.get_response(request)
        finally:
            request.path_info = original


class ScriptPrefixMiddleware:
    """Složí /postak i cestu, kterou už nginx o prefix zkrátil."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = (settings.POSTAK_PREFIX or '').rstrip('/')
        if not prefix:
            set_script_prefix('/')
            return self.get_response(request)

        path = request.path_info or '/'
        if path == prefix or path.startswith(prefix + '/'):
            path = path[len(prefix):] or '/'
            request.path_info = path
            request.META['PATH_INFO'] = path
        if not path.startswith('/'):
            path = '/' + path
            request.path_info = path
        request.path = prefix + path
        request.META['SCRIPT_NAME'] = prefix
        set_script_prefix(prefix)
        try:
            return self.get_response(request)
        finally:
            set_script_prefix('/')
