from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

_env_path = BASE_DIR / '.env'
if _env_path.exists():
    for line in _env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())


def _env_bool(key, default=False):
    return os.environ.get(key, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(key, default=''):
    return [x.strip() for x in os.environ.get(key, default).split(',') if x.strip()]


SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-materialnik-local-only-change-me',
)
DEBUG = _env_bool('DEBUG', True)
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'sklad.apps.SkladConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]
if not DEBUG:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
MIDDLEWARE += [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'sklad.middleware.TenantMiddleware',
]

ROOT_URLCONF = 'materialnik_site.urls'

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
                'sklad.context.nav',
            ],
        },
    },
]

WSGI_APPLICATION = 'materialnik_site.wsgi.application'

if os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DB_NAME'],
            'USER': os.environ.get('DB_USER', 'ulov'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'cs'
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_NAME = 'materialnik_session'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_NAME = 'materialnik_csrf'

FORCE_SCRIPT_NAME = os.environ.get('FORCE_SCRIPT_NAME', '').strip() or None
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if FORCE_SCRIPT_NAME:
    # FileSystemStorage by jinak dal STATIC_URL na /static/ a ignoroval prefix /sklad.
    STATIC_URL = f'{FORCE_SCRIPT_NAME.rstrip("/")}/static/'
    SESSION_COOKIE_PATH = FORCE_SCRIPT_NAME
    CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME
    LOGIN_URL = f'{FORCE_SCRIPT_NAME}/prihlaseni/'

CORS_ALLOW_ALL_ORIGINS = DEBUG
CSRF_TRUSTED_ORIGINS = _env_list(
    'CSRF_TRUSTED_ORIGINS',
    'http://127.0.0.1:8001,http://localhost:8001',
)

# FLOW / Ulov API — ověření hesla partnera. Materiálník hesla neukládá.
ULOV_API_URL = os.environ.get('ULOV_API_URL', 'http://127.0.0.1:8000').rstrip('/')
MATERIALNIK_M2M_KEY = os.environ.get('MATERIALNIK_M2M_KEY', '').strip()
FLOW_PUBLIC_URL = os.environ.get(
    'FLOW_PUBLIC_URL',
    'http://127.0.0.1:8090/flow' if DEBUG else '',
).strip()
if not FORCE_SCRIPT_NAME:
    LOGIN_URL = '/prihlaseni/'
