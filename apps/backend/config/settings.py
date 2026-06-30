"""
Sentinel Django Configuration.

Single settings file. All values come from environment variables.
Never use separate settings/local.py or settings/production.py files.
The environment determines behavior, not the settings file name.

See docs/coding-standards.md for the reasoning behind this pattern.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import dj_database_url
import structlog
from decouple import Csv, config

# =============================================================================
# Paths
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SENTINEL_APPS_DIR = BASE_DIR / "sentinel"

# =============================================================================
# Environment
# =============================================================================
ENVIRONMENT: str = config("ENVIRONMENT", default="development")
DEBUG: bool = config("DEBUG", default=False, cast=bool)

# Fail fast if SECRET_KEY is the example value in production
SECRET_KEY: str = config("SECRET_KEY")
if not DEBUG and "change-me" in SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY must be changed from the example value in non-debug environments."
    )

ALLOWED_HOSTS: list[str] = config("ALLOWED_HOSTS", cast=Csv(), default="localhost,127.0.0.1")

# =============================================================================
# Application Definition
# =============================================================================
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_prometheus",
    "drf_spectacular",
    "axes",
]

SENTINEL_APPS = [
    "sentinel.core",
    "sentinel.auth_service",
    "sentinel.audit",
    "sentinel.api_keys",
    "sentinel.risk",
    "sentinel.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + SENTINEL_APPS

# =============================================================================
# Custom User Model
# =============================================================================
# Must be set before the first migration. Changing this after migrations exist
# requires a painful database rebuild. See ADR-002 and auth_service/models.py.
AUTH_USER_MODEL = "sentinel_auth.SentinelUser"

# =============================================================================
# Middleware
# =============================================================================
# Order matters. SecurityMiddleware must be first.
# django_prometheus wraps the stack for metrics.
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",  # Must be first
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Sentinel custom middleware
    "sentinel.core.middleware.request_id.RequestIDMiddleware",
    "sentinel.core.middleware.trace_context.TraceContextMiddleware",
    "sentinel.core.middleware.structured_logging.StructuredLoggingMiddleware",
    "axes.middleware.AxesMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",  # Must be last
]

ROOT_URLCONF = "config.urls"

# =============================================================================
# Templates
# =============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# =============================================================================
# Database
# =============================================================================
DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL"),
        conn_max_age=config("DATABASE_CONN_MAX_AGE", default=60, cast=int),
        conn_health_checks=True,
    )
}

# =============================================================================
# Cache
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": False,
        },
        "KEY_PREFIX": "sentinel",
    }
}

# =============================================================================
# Password Validation
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Use argon2 for password hashing (more secure than PBKDF2)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # Fallback for existing hashes
]

# =============================================================================
# Internationalization
# =============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# =============================================================================
# Static Files
# =============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOWED_ORIGINS: list[str] = config(
    "CORS_ALLOWED_ORIGINS",
    cast=Csv(),
    default="http://localhost:3000",
)
CORS_ALLOW_CREDENTIALS = True

# =============================================================================
# Security Headers
# =============================================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Only enforce HTTPS in production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =============================================================================
# Django REST Framework
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "sentinel.api_keys.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "sentinel.core.pagination.cursor.CursorPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "sentinel.core.exceptions.handlers.sentinel_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON_RATE", default="60/minute"),
        "user": config("THROTTLE_USER_RATE", default="1000/minute"),
    },
}

# =============================================================================
# JWT (djangorestframework-simplejwt)
# =============================================================================
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": False,  # We handle rotation manually in AuthService
    "BLACKLIST_AFTER_ROTATION": False,  # We blacklist in Redis, not the DB table
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SIGNING_KEY", default=config("SECRET_KEY")),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_PAIR_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
}

# =============================================================================
# DRF Spectacular (OpenAPI)
# =============================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Sentinel API",
    "DESCRIPTION": "Event-Driven Security, Audit & Risk Intelligence Platform",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
    ],
}

# =============================================================================
# Celery
# =============================================================================
CELERY_BROKER_URL: str = config("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND: str = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes soft limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Disable prefetch for fair task distribution

# =============================================================================
# Logging — Structured JSON via structlog
# =============================================================================
LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
        "console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if not DEBUG else "console",
            "stream": sys.stdout,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "sentinel": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# =============================================================================
# OpenTelemetry
# =============================================================================
OTEL_ENABLED: bool = config("OTEL_ENABLED", default=True, cast=bool)
OTEL_SERVICE_NAME: str = config("OTEL_SERVICE_NAME", default="sentinel-backend")
OTEL_SERVICE_VERSION = "1.0.0"
OTEL_EXPORTER_OTLP_ENDPOINT: str = config(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    default="http://otel-collector:4317",
)

# =============================================================================
# django-axes (brute force protection)
# =============================================================================
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 1  # Unlock after 1 hour
AXES_LOCKOUT_TEMPLATE = None  # Use DRF response, not template
AXES_LOCKOUT_CALLABLE = "sentinel.core.security.axes_lockout_response"
AXES_RESET_ON_SUCCESS = True
AXES_BACKEND = "axes.backends.AxesStandaloneBackend"

# =============================================================================
# Application-specific
# =============================================================================
SENTINEL_REQUEST_ID_HEADER = "X-Request-ID"
SENTINEL_MAX_AUDIT_EXPORT_ROWS = 100_000
