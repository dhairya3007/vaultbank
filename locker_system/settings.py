"""
Django settings for VaultBank — production-hardened configuration.

All secrets are loaded from environment variables (or a .env file in local dev).
Never hardcode SECRET_KEY, DEBUG, or ALLOWED_HOSTS.

PythonAnywhere deployment:
  Set the variables below in Web tab → Environment Variables.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# ─── .env Loader (stdlib only — no third-party dependency) ────────────────────
def _load_env_file(env_path: Path) -> None:
    """
    Read key=value pairs from a .env file into os.environ.
    Only sets keys that are NOT already present in the environment,
    so real environment variables always win over the .env file.
    """
    try:
        with open(env_path, encoding='utf-8') as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass  # .env is optional; production uses real env vars


_load_env_file(BASE_DIR / '.env')


# ─── Core Security Settings ───────────────────────────────────────────────────

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is not set. "
        "Add it to your .env file (local) or environment variables (production). "
        "Generate one with: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('1', 'true', 'yes')

_raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]
if not ALLOWED_HOSTS:
    if DEBUG:
        ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
    else:
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")


# ─── Installed Apps ───────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'lockers',
]


# ─── Middleware ───────────────────────────────────────────────────────────────

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

ROOT_URLCONF = 'locker_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'locker_system.wsgi.application'


# ─── Database ─────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ─── Password Validation ──────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# ─── Static & Media Files ─────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files are served via an auth-gated Django view — NOT via the public
# static() URL helper. See locker_system/urls.py for the protected media route.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Auth & Login Routing ─────────────────────────────────────────────────────

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


# ─── Session & Cookie Security ────────────────────────────────────────────────

# Banking context: 15-minute idle timeout (PCI-DSS aligned)
SESSION_COOKIE_AGE = 900            # 15 minutes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Kill session when browser closes
SESSION_SAVE_EVERY_REQUEST = True   # Reset timeout on each request (sliding window)

SESSION_COOKIE_NAME = 'vaultbank_sessionid'
CSRF_COOKIE_NAME = 'vaultbank_csrftoken'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False        # Must be False for JS to read CSRF token
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Secure flag: True only when served over HTTPS
_is_secure = os.environ.get('DJANGO_SECURE_COOKIE', 'false').lower() in ('1', 'true', 'yes')
SESSION_COOKIE_SECURE = _is_secure
CSRF_COOKIE_SECURE = _is_secure


# ─── CSRF Trusted Origins ─────────────────────────────────────────────────────

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:8000,http://127.0.0.1:8000'
    ).split(',') if o.strip()
]


# ─── Security Headers (always on, even in DEBUG) ─────────────────────────────

X_FRAME_OPTIONS = 'DENY'                         # Blocks clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True               # Prevents MIME sniffing
SECURE_BROWSER_XSS_FILTER = True                 # Legacy IE XSS filter header


# ─── HTTPS / HSTS — only enforced in production ───────────────────────────────

if not DEBUG:
    # Redirect all HTTP → HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True

    # Strict-Transport-Security: tell browsers to always use HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ─── Cache (used for API Explorer rate limiting) ──────────────────────────────

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vaultbank-cache',
    }
}


# ─── Logging ─────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'lockers': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ─── Flash Message Storage ────────────────────────────────────────────────────

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
