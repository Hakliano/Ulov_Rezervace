import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    if os.environ.get('POSTAK_SKIP_DOTENV') == '1':
        return
    path = BASE_DIR / '.env'
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()


def _env_bool(key, default=False):
    return os.environ.get(key, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(key, default=''):
    return [part.strip() for part in os.environ.get(key, default).split(',') if part.strip()]


def _prefix():
    raw = os.environ.get('FORCE_SCRIPT_NAME', '').strip()
    if not raw or raw == '/':
        return ''
    return '/' + raw.strip('/')


DEBUG = _env_bool('DEBUG', True)
SECRET_KEY = os.environ.get('SECRET_KEY', '').strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-postak-local-only'
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('SECRET_KEY is required when DEBUG is off.')

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Vlastní prefix. Django FORCE_SCRIPT_NAME nenasazujeme: při přímém
# otevření /postak/ by zdvojil cestu. Prázdný prefix = kořen domény.
POSTAK_PREFIX = _prefix()

POSTAK_LOGO_URL = (
    'https://haklweb.b-cdn.net/modernik/Cheerful%20Pigeon%20Mail%20Carrier%20Logo.webp'
)
# Volitelné — jinak odvozeno z POSTAK_PUBLIC_LOGIN_URL + /static/postak-logo-email.png
POSTAK_EMAIL_LOGO_URL = os.environ.get('POSTAK_EMAIL_LOGO_URL', '').strip()

MODERNIK_API_BASE = os.environ.get(
    'MODERNIK_API_BASE',
    'http://127.0.0.1:8000/partner-admin/api/postak/v1',
).strip().rstrip('/')
MODERNIK_API_TOKEN = os.environ.get('MODERNIK_API_TOKEN', '').strip()
if DEBUG and not MODERNIK_API_TOKEN:
    MODERNIK_API_TOKEN = 'dev-postak-local'

HYA_API_BASE = os.environ.get(
    'HYA_API_BASE',
    'http://127.0.0.1:8000/internal/postak/v1',
).strip().rstrip('/')
HYA_POSTAK_API_TOKEN = os.environ.get('HYA_POSTAK_API_TOKEN', '').strip()
# CRM zápisy do Moderníku/HYA — na LIVE výchozí vypnuto (jen čtení + lokální cache).
POSTAK_MODERNIK_CRM_WRITE = _env_bool('POSTAK_MODERNIK_CRM_WRITE', DEBUG)
POSTAK_HYA_CRM_WRITE = _env_bool('POSTAK_HYA_CRM_WRITE', False)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'jadro.apps.JadroConfig',
    'phone_scripts.apps.PhoneScriptsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'postak_site.middleware.PostakStaticMiddleware',
    'postak_site.middleware.ScriptPrefixMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'jadro.middleware.VynutitZmenuHeslaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'postak_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'jadro.context_processors.chat_badge',
            ],
        },
    },
]

WSGI_APPLICATION = 'postak_site.wsgi.application'

def _database_config():
    if os.environ.get('POSTGRES_HOST', '').strip():
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ['POSTGRES_HOST'].strip(),
            'PORT': os.environ.get('POSTGRES_PORT', '5432').strip(),
            'NAME': os.environ.get('POSTGRES_DB', 'postak').strip(),
            'USER': os.environ.get('POSTGRES_USER', 'postak').strip(),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'CONN_MAX_AGE': 60,
        }
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
    }


DATABASES = {'default': _database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'cs'
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))
MEDIA_URL = '/media/'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

POSTAK_BUNNY_ENABLED = _env_bool('POSTAK_BUNNY_ENABLED', False)
POSTAK_BUNNY_STORAGE_ZONE = os.environ.get('POSTAK_BUNNY_STORAGE_ZONE', 'wwweb').strip()
POSTAK_BUNNY_ACCESS_KEY = os.environ.get('POSTAK_BUNNY_ACCESS_KEY', '').strip()
POSTAK_BUNNY_API_BASE = os.environ.get('POSTAK_BUNNY_API_BASE', 'https://storage.bunnycdn.com').strip().rstrip('/')
_default_bunny_root = 'postak/local' if DEBUG else 'postak'
POSTAK_BUNNY_ROOT_PREFIX = os.environ.get('POSTAK_BUNNY_ROOT_PREFIX', _default_bunny_root).strip().strip('/')

POSTAK_PUBLIC_LOGIN_URL = os.environ.get(
    'POSTAK_PUBLIC_LOGIN_URL',
    'https://www.ulovklienty.cz/postak/',
).strip()
POSTAK_SYSTEM_SCHRANKA_ID = os.environ.get('POSTAK_SYSTEM_SCHRANKA_ID', '').strip()

STORAGES = {
    'default': {'BACKEND': 'jadro.postak_storage.PostakBunnyStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_NAME = 'postak_session'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_PATH = f'{POSTAK_PREFIX}/' if POSTAK_PREFIX else '/'
CSRF_COOKIE_NAME = 'postak_csrf'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_PATH = f'{POSTAK_PREFIX}/' if POSTAK_PREFIX else '/'
CSRF_TRUSTED_ORIGINS = _env_list(
    'CSRF_TRUSTED_ORIGINS',
    'http://127.0.0.1:8015,http://localhost:8015',
)

LOGIN_URL = f'{POSTAK_PREFIX}/prihlaseni/'
LOGIN_REDIRECT_URL = 'prehled'
LOGOUT_REDIRECT_URL = 'prihlaseni'

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'DENY'

POSTAK_MAIL_ENCRYPTION_KEY = os.environ.get('POSTAK_MAIL_ENCRYPTION_KEY', '').strip()
if not POSTAK_MAIL_ENCRYPTION_KEY:
    if DEBUG and SECRET_KEY:
        import base64
        import hashlib

        digest = hashlib.sha256(f'{SECRET_KEY}:postak-mail-v1'.encode()).digest()
        POSTAK_MAIL_ENCRYPTION_KEY = base64.urlsafe_b64encode(digest).decode()
    elif not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('POSTAK_MAIL_ENCRYPTION_KEY is required when DEBUG is off.')
