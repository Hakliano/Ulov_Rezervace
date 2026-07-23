"""Bezpečnostní HTTP hlavičky pro API odpovědi."""


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        if not response.get('Content-Security-Policy'):
            content_type = response.get('Content-Type', '')
            if 'text/html' in content_type:
                # Admin UI (/partner-admin/, /admin/) potřebuje same-origin CSS/JS.
                response['Content-Security-Policy'] = (
                    "default-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "font-src 'self' data:; "
                    "frame-ancestors 'none'"
                )
            else:
                response['Content-Security-Policy'] = (
                    "default-src 'none'; frame-ancestors 'none'"
                )
        return response
