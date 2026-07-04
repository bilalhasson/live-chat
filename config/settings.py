"""
Django settings for the live-chat project (Phase 0 — walking skeleton).

Everything environment-driven so the same code runs locally (SQLite + local Redis)
and on Railway (Postgres + Redis services). See README.md for the env vars.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(key: str) -> list[str]:
    return [item.strip() for item in os.environ.get(key, "").split(",") if item.strip()]


# --- Core -----------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DEBUG", default=True)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (["*"] if DEBUG else ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Railway injects the service's public domain here — trust it automatically so we
# don't have to hardcode the generated *.up.railway.app hostname.
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")
    # Railway's internal healthcheck hits the app with this Host header.
    ALLOWED_HOSTS.append("healthcheck.railway.app")

# Railway (and most PaaS) terminate TLS at a proxy and forward over http.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production hardening — only when DEBUG is off, so local http dev is unaffected.
# The proxy header above lets these coexist with Railway's TLS-terminating edge.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # Don't redirect the healthcheck — Railway probes it internally over http.
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600  # modest; no includeSubDomains on shared *.railway.app

INSTALLED_APPS = [
    # daphne must precede staticfiles/admin so runserver serves over ASGI.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files (incl. the widget loader) in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

# HTTP is handled by Django via ASGI; WebSocket is handled by Channels.
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"  # retained but unused under Daphne.

# --- Database -------------------------------------------------------------
# Local default: SQLite. Railway: DATABASE_URL points at Postgres.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# --- Channel layer (Redis) ------------------------------------------------
# Redis is REQUIRED — it fans WebSocket messages out across processes/tabs.
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# --- Auth / i18n ----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Operator auth redirects.
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/sites/"
LOGOUT_REDIRECT_URL = "/login/"

# --- Static files ---------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Non-manifest compressed storage: avoids hashed-filename lookups that
    # would break the widget's stable /static/widget/loader.js URL.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
