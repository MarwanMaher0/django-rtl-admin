"""Settings for the django-rtl-admin demo project."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

_LOCAL_DEV_SECRET_KEY = "local-dev-only-key-not-for-production"
_HAS_WHITENOISE = importlib.util.find_spec("whitenoise") is not None
_PRODUCTION_ENV_KEYS = {
    "ALLOWED_HOSTS",
    "DJANGO_ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "PORT",
    "WEB_CONCURRENCY",
    "RENDER",
    "FLY_APP_NAME",
    "FLY_MACHINE_ID",
    "DYNO",
    "K_SERVICE",
}


def _is_insecure_secret_key(value: str) -> bool:
    normalized = value.strip()
    return (
        not normalized
        or normalized == _LOCAL_DEV_SECRET_KEY
        or normalized.startswith("django-insecure-")
    )


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        raw = os.environ.get(f"DJANGO_{name}")
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, *, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        raw = os.environ.get(f"DJANGO_{name}")
    if raw is None or not raw.strip():
        return list(default) if default is not None else []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_database_url(url: str, *, default_sqlite_path: Path) -> dict[str, object]:
    raw = url.strip()
    if not raw:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": default_sqlite_path,
        }
    try:
        import dj_database_url  # type: ignore[import-not-found]

        return dict(dj_database_url.parse(raw))
    except ImportError:
        pass

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if scheme in {"sqlite", "sqlite3"}:
        if raw.startswith(("sqlite:////", "sqlite3:////")):
            db_path = "/" + parsed.path.lstrip("/")
        elif parsed.path in {"", "/", "/:memory:"}:
            db_path = ":memory:"
        else:
            db_path = unquote(parsed.path.lstrip("/"))
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db_path,
        }

    engine_map = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "pgsql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
    }
    engine = engine_map.get(scheme)
    if engine is None:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")

    config: dict[str, object] = {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port) if parsed.port else "",
    }
    query = parse_qs(parsed.query)
    if query:
        config["OPTIONS"] = {key: values[-1] for key, values in query.items() if values}
    return config


DEBUG = _env_bool("DEBUG", default=False)
DJANGO_ENV = (os.environ.get("DJANGO_ENV") or "production").strip().lower()
LOCAL_DEV = (
    DJANGO_ENV in {"development", "dev", "local"}
    and not any(os.environ.get(key) is not None for key in _PRODUCTION_ENV_KEYS)
)

_raw_secret_key = (
    os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY") or ""
).strip()
if not _raw_secret_key:
    if LOCAL_DEV:
        SECRET_KEY = _LOCAL_DEV_SECRET_KEY
    else:
        raise ImproperlyConfigured(
            "The SECRET_KEY environment variable must be set to a strong, "
            "non-default value when LOCAL_DEV is False."
        )
elif not LOCAL_DEV and _is_insecure_secret_key(_raw_secret_key):
    raise ImproperlyConfigured(
        "The SECRET_KEY environment variable must not use an insecure or "
        "default value when LOCAL_DEV is False."
    )
else:
    SECRET_KEY = _raw_secret_key

USING_LOCAL_DEV_SECRET_KEY = _is_insecure_secret_key(SECRET_KEY)

ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]", ".localhost"],
)
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS", default=[])
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo")

INSTALLED_APPS = [
    # Must come before django.contrib.admin so the direction-aware admin
    # templates shadow the contrib ones.
    "django_rtl_admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["whitenoise.middleware.WhiteNoiseMiddleware"] if _HAS_WHITENOISE else []),
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Required for the language switcher to stick.
    "django.middleware.locale.LocaleMiddleware",
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
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": _parse_database_url(
        DATABASE_URL,
        default_sqlite_path=BASE_DIR / "db.sqlite3",
    )
}

AUTH_PASSWORD_VALIDATORS = []

# -- internationalisation --------------------------------------------------

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("ar", "Arabic"),
    ("ar-eg", "Arabic (Egypt)"),
]

USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT") or (BASE_DIR / "staticfiles"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedStaticFilesStorage"
            if _HAS_WHITENOISE
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}
WHITENOISE_USE_FINDERS = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -- django-rtl-admin ------------------------------------------------------

RTL_ADMIN = {
    "CURRENCY": "EGP",
    "LANGUAGE_SWITCHER_LABELS": "both",
}
