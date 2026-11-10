"""System checks for installation and configuration mistakes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Warning, register

from .conf import CHOICES, SETTINGS_KEY, rtl_settings

if TYPE_CHECKING:
    from django.apps import AppConfig
    from django.core.checks import CheckMessage

APP_NAME = "django_rtl_admin"
ADMIN_APP = "django.contrib.admin"


def _configured_settings() -> Mapping[str, Any] | None:
    configured = getattr(settings, SETTINGS_KEY, None)
    if configured is None:
        return {}
    if isinstance(configured, Mapping):
        return configured
    return None


@register()
def check_app_order(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """``django_rtl_admin`` must shadow the contrib admin templates."""
    names = [config.name for config in apps.get_app_configs()]
    if APP_NAME not in names or ADMIN_APP not in names:
        return []
    if names.index(APP_NAME) < names.index(ADMIN_APP):
        return []
    return [
        Warning(
            f"{APP_NAME!r} is listed after {ADMIN_APP!r} in INSTALLED_APPS.",
            hint=(
                f"Template overrides are resolved in INSTALLED_APPS order, so "
                f"{APP_NAME!r} must come before {ADMIN_APP!r} for the "
                f"direction-aware admin templates to take effect."
            ),
            id="rtl_admin.W001",
        )
    ]


@register()
def check_settings_keys(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """Typos in ``RTL_ADMIN`` fail silently otherwise."""
    configured = _configured_settings()
    if configured is None:
        return []
    unknown = sorted(set(configured) - set(rtl_settings.defaults))
    if not unknown:
        return []
    return [
        Warning(
            f"Unknown {SETTINGS_KEY} keys: {', '.join(unknown)}.",
            hint=(
                "These keys are ignored. Supported keys are: "
                + ", ".join(sorted(rtl_settings.defaults))
                + "."
            ),
            id="rtl_admin.W002",
        )
    ]


@register()
def check_settings_values(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """Report invalid choices before settings are accessed while rendering."""
    configured = _configured_settings()
    if configured is None:
        return []
    issues: list[CheckMessage] = []
    for name, choices in CHOICES.items():
        if name in configured and configured[name] not in choices:
            issues.append(
                Error(
                    f"{SETTINGS_KEY}[{name!r}] must be one of "
                    f"{', '.join(repr(choice) for choice in choices)}, got {configured[name]!r}.",
                    id="rtl_admin.E001",
                )
            )
    return issues


@register()
def check_settings_types(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """Warn about values that would otherwise be coerced or misinterpreted."""
    configured = _configured_settings()
    if configured is None:
        return [
            Warning(
                f"{SETTINGS_KEY} must be a mapping or None.",
                hint=(
                    f"Set {SETTINGS_KEY} to a mapping of supported setting names and values, "
                    "or None to use the defaults."
                ),
                id="rtl_admin.W005",
            )
        ]
    issues: list[CheckMessage] = []
    for name, value in configured.items():
        expected = None
        if name == "EXTRA_RTL_LANGUAGES" and isinstance(value, str):
            expected = "a sequence of language codes, not a bare string"
        elif name == "FONT_STACK" and not (
            value is None
            or isinstance(value, str)
            or (
                isinstance(value, Sequence)
                and not isinstance(value, (bytes, bytearray))
                and all(isinstance(font, str) for font in value)
            )
        ):
            expected = "None, a string, or a sequence of strings"
        elif isinstance(rtl_settings.defaults.get(name), bool) and not isinstance(value, bool):
            expected = "a bool"
        if expected is not None:
            issues.append(
                Warning(
                    f"{SETTINGS_KEY}[{name!r}] must be {expected}.",
                    id="rtl_admin.W005",
                )
            )
    return issues


@register()
def check_language_switcher(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """The switcher needs ``set_language`` routed and ``LocaleMiddleware`` on."""
    configured = _configured_settings()
    if configured is None:
        return []
    if not configured.get("LANGUAGE_SWITCHER", rtl_settings.defaults["LANGUAGE_SWITCHER"]):
        return []
    issues: list[CheckMessage] = []

    from django.urls import NoReverseMatch, reverse

    try:
        reverse("set_language")
    except (NoReverseMatch, Exception):
        issues.append(
            Warning(
                "The admin language switcher is enabled but 'set_language' "
                "cannot be reversed.",
                hint=(
                    "Add `path('i18n/', include('django.conf.urls.i18n'))` to "
                    "your root URLconf, or set "
                    f'{SETTINGS_KEY}["LANGUAGE_SWITCHER"] = False.'
                ),
                id="rtl_admin.W003",
            )
        )

    middleware = list(getattr(settings, "MIDDLEWARE", []))
    if "django.middleware.locale.LocaleMiddleware" not in middleware:
        issues.append(
            Warning(
                "django.middleware.locale.LocaleMiddleware is not installed, so "
                "a language chosen in the admin will not stick.",
                hint=(
                    "Add 'django.middleware.locale.LocaleMiddleware' to "
                    "MIDDLEWARE, after SessionMiddleware and before "
                    "CommonMiddleware."
                ),
                id="rtl_admin.W004",
            )
        )
    return issues
