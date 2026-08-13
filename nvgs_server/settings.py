import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_secret(name: str, default: str | None = None) -> str | None:
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()
    return os.getenv(name, default)


ENVIRONMENT = os.getenv("DJANGO_ENVIRONMENT", "development").lower()
DEBUG = env_bool("DJANGO_DEBUG", ENVIRONMENT == "development")

SECRET_KEY = env_secret("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT in {"development", "test", "build"}:
        SECRET_KEY = "development-only-secret-key"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE is required."
        )

local_hosts_default = (
    "localhost,127.0.0.1" if ENVIRONMENT in {"development", "test", "build"} else ""
)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", local_hosts_default)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain the server host.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if "https://localhost:8443" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://localhost:8443")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "tickets",
    "core",
    "downloads",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if ENVIRONMENT in {"production", "build"}:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "nvgs_server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nvgs_server.wsgi.application"
ASGI_APPLICATION = "nvgs_server.asgi.application"

DATABASE_ENGINE = os.getenv("DATABASE_ENGINE", "sqlite").lower()
if DATABASE_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "nvgs_ticketing"),
            "USER": os.getenv("POSTGRES_USER", "nvgs_app"),
            "PASSWORD": env_secret("POSTGRES_PASSWORD"),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    sqlite_database_path = os.getenv("SQLITE_DATABASE_PATH", "").strip()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_database_path or BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Singapore")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if ENVIRONMENT in {"production", "build"}
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DOWNLOAD_LIBRARY_DIR = Path(
    os.getenv(
        "DOWNLOAD_LIBRARY_DIR",
        str(BASE_DIR / "download-server" / "downloads"),
    )
)
DOWNLOAD_UPLOAD_MAX_BYTES = int(
    os.getenv("DOWNLOAD_UPLOAD_MAX_BYTES", str(2 * 1024 * 1024 * 1024))
)
DOWNLOAD_UPLOAD_MAX_FILES = int(os.getenv("DOWNLOAD_UPLOAD_MAX_FILES", "50"))
FILE_UPLOAD_TEMP_DIR = os.getenv("FILE_UPLOAD_TEMP_DIR") or None
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

ALLOWED_EMAIL_DOMAINS = [
    domain.lower() for domain in env_list("ALLOWED_EMAIL_DOMAINS", "nvidia.com")
]

APPSCRIPT_SSO_ENABLED = env_bool("APPSCRIPT_SSO_ENABLED", False)
APPSCRIPT_SSO_URL = os.getenv("APPSCRIPT_SSO_URL", "").strip()
APPSCRIPT_SSO_SECRET = env_secret("APPSCRIPT_SSO_SECRET", "") or ""
APPSCRIPT_SSO_ISSUER = os.getenv(
    "APPSCRIPT_SSO_ISSUER",
    "nvgs-appscript",
).strip()
APPSCRIPT_SSO_AUDIENCE = os.getenv(
    "APPSCRIPT_SSO_AUDIENCE",
    "nvgs-server",
).strip()
APPSCRIPT_SSO_AUTO_CREATE_USERS = env_bool(
    "APPSCRIPT_SSO_AUTO_CREATE_USERS",
    True,
)
APPSCRIPT_SSO_SUCCESS_REDIRECT = os.getenv(
    "APPSCRIPT_SSO_SUCCESS_REDIRECT",
    "/tickets/",
).strip()
APPSCRIPT_SSO_TOKEN_TTL_SECONDS = 60
APPSCRIPT_SSO_STATE_TTL_SECONDS = 300
APPSCRIPT_SSO_ONBOARDING_TTL_SECONDS = 900
APPSCRIPT_SSO_CLOCK_SKEW_SECONDS = 15

TICKET_NOTIFICATION_WEBHOOK_URL = (
    env_secret("TICKET_NOTIFICATION_WEBHOOK_URL", "") or ""
).strip()
if TICKET_NOTIFICATION_WEBHOOK_URL:
    notification_url = urlsplit(TICKET_NOTIFICATION_WEBHOOK_URL)
    if (
        notification_url.scheme != "https"
        or not notification_url.hostname
        or notification_url.username
        or notification_url.password
    ):
        raise ImproperlyConfigured(
            "TICKET_NOTIFICATION_WEBHOOK_URL must be a complete HTTPS URL."
        )
TICKET_NOTIFICATION_DELIVERY_MODE = os.getenv(
    "TICKET_NOTIFICATION_DELIVERY_MODE",
    "webhook" if TICKET_NOTIFICATION_WEBHOOK_URL else "disabled",
).strip().lower()
if TICKET_NOTIFICATION_DELIVERY_MODE not in {
    "disabled",
    "webhook",
    "email",
    "appscript",
}:
    raise ImproperlyConfigured(
        "TICKET_NOTIFICATION_DELIVERY_MODE must be disabled, webhook, "
        "email, or appscript."
    )
TICKET_NOTIFICATION_PUBLIC_BASE_URL = os.getenv(
    "TICKET_NOTIFICATION_PUBLIC_BASE_URL",
    "",
).strip().rstrip("/")
if TICKET_NOTIFICATION_PUBLIC_BASE_URL:
    ticket_public_url = urlsplit(TICKET_NOTIFICATION_PUBLIC_BASE_URL)
    if (
        ticket_public_url.scheme != "https"
        or not ticket_public_url.hostname
        or ticket_public_url.username
        or ticket_public_url.password
        or ticket_public_url.query
        or ticket_public_url.fragment
    ):
        raise ImproperlyConfigured(
            "TICKET_NOTIFICATION_PUBLIC_BASE_URL must be a complete HTTPS URL."
        )
TICKET_NOTIFICATION_EMAIL_TO = env_list("TICKET_NOTIFICATION_EMAIL_TO")
TICKET_NOTIFICATION_EMAIL_TARGET_NAME = os.getenv(
    "TICKET_NOTIFICATION_EMAIL_TARGET_NAME",
    "OpsGroupChat",
).strip()
TICKET_NOTIFICATION_TEAMS_CHAT_ID = os.getenv(
    "TICKET_NOTIFICATION_TEAMS_CHAT_ID",
    "",
).strip()
TICKET_NOTIFICATION_APPSCRIPT_URL = os.getenv(
    "TICKET_NOTIFICATION_APPSCRIPT_URL",
    "",
).strip()
TICKET_NOTIFICATION_APPSCRIPT_SECRET = (
    env_secret("TICKET_NOTIFICATION_APPSCRIPT_SECRET", "") or ""
).strip()
if TICKET_NOTIFICATION_APPSCRIPT_URL:
    notification_appscript_url = urlsplit(TICKET_NOTIFICATION_APPSCRIPT_URL)
    if (
        notification_appscript_url.scheme != "https"
        or notification_appscript_url.hostname != "script.google.com"
        or not notification_appscript_url.path.endswith("/exec")
        or notification_appscript_url.username
        or notification_appscript_url.password
        or notification_appscript_url.query
        or notification_appscript_url.fragment
    ):
        raise ImproperlyConfigured(
            "TICKET_NOTIFICATION_APPSCRIPT_URL must be a deployed "
            "https://script.google.com/.../exec URL."
        )

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = env_secret("EMAIL_HOST_PASSWORD", "") or ""
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = 8
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "nvgs-ticketing@localhost",
).strip()
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true.")
TICKET_NOTIFICATION_TIMEOUT_SECONDS = 8
TICKET_NOTIFICATION_MAX_ATTEMPTS = 8

if APPSCRIPT_SSO_ENABLED:
    appscript_url = urlsplit(APPSCRIPT_SSO_URL)
    if (
        appscript_url.scheme != "https"
        or appscript_url.hostname != "script.google.com"
        or not appscript_url.path.endswith("/exec")
        or appscript_url.username
        or appscript_url.password
        or appscript_url.fragment
    ):
        raise ImproperlyConfigured(
            "APPSCRIPT_SSO_URL must be a deployed "
            "https://script.google.com/.../exec URL."
        )
    if len(APPSCRIPT_SSO_SECRET) < 32:
        raise ImproperlyConfigured(
            "APPSCRIPT_SSO_SECRET must contain at least 32 characters."
        )
    if not APPSCRIPT_SSO_ISSUER or not APPSCRIPT_SSO_AUDIENCE:
        raise ImproperlyConfigured(
            "The Apps Script SSO issuer and audience must not be blank."
        )
    if not APPSCRIPT_SSO_SUCCESS_REDIRECT.startswith("/") or (
        APPSCRIPT_SSO_SUCCESS_REDIRECT.startswith("//")
    ):
        raise ImproperlyConfigured(
            "APPSCRIPT_SSO_SUCCESS_REDIRECT must be a local absolute path."
        )

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
    },
    "NUM_PROXIES": 1,
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    ENVIRONMENT == "production",
)
SECURE_HSTS_SECONDS = int(
    os.getenv(
        "DJANGO_SECURE_HSTS_SECONDS",
        "31536000" if ENVIRONMENT == "production" else "0",
    )
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# NVGS is addressed by a private hostname or IP. Public-domain subdomain HSTS
# and browser preload submission do not apply to this deployment model.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}
