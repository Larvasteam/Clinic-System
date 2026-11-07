import os
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env file if present (it is never committed to GitHub)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


# ---------- core ----------
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key-never-use-in-production'
    else:
        raise ImproperlyConfigured(
            'Set DJANGO_SECRET_KEY (in the .env file locally, or in your host settings).')

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')  # e.g. https://yourapp.onrender.com

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'patients',
    'pharmacy',
    'billing',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'reports.context_processors.nav',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------- database: PostgreSQL when DATABASE_URL is set, SQLite otherwise ----------
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------- locale ----------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Harare'
USE_I18N = True
USE_TZ = True

# ---------- static files (served by WhiteNoise on the server) ----------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
try:
    STATIC_ROOT.mkdir(exist_ok=True)  # keeps WhiteNoise quiet before the first collectstatic
except OSError:
    pass
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------- login ----------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'
SESSION_COOKIE_AGE = 60 * 60 * 8  # staff are signed out after 8 hours

# ---------- clinic rules ----------
CONTRACEPTIVE_MAX_AGE = 49  # placeholder: confirm the real limit with the clinic

# ---------- consultation fee ----------
# Every new visit is charged this fixed amount in US dollars. Staff cannot change it on the form.
# To change the price, edit this number (or set CONSULTATION_FEE_USD in .env) and restart the server.
CONSULTATION_FEE_USD = Decimal(os.environ.get('CONSULTATION_FEE_USD', '5.00'))

# ---------- ZiG exchange rate ----------
ALLRATES_API_KEY = os.environ.get('ALLRATES_API_KEY', '')   # free key from allratestoday.com (RBZ official rate)
RATE_MAX_AGE_DAYS = 3     # the rate chip turns amber when the newest rate is older than this
RATE_MAX_CHANGE = 0.25    # automatic updates that move the rate by more than 25% need a human to confirm

# ---------- extra security when DEBUG is off (i.e. on the live server) ----------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600  # raise to 31536000 (1 year) once HTTPS is confirmed working
