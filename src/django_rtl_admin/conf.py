"""Settings namespace for django-rtl-admin.

Everything the app does is configured through a single ``RTL_ADMIN`` dict in
project settings.  Every key is optional and every feature can be turned off::

    RTL_ADMIN = {
        "LANGUAGE_SWITCHER": False,
    }
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from django.utils.functional import Promise

SETTINGS_KEY = "RTL_ADMIN"

#: Default values for every supported key.
DEFAULTS: dict[str, Any] = {
    # -- styling -------------------------------------------------------
    # Load the logical-property stylesheet into the admin <head>.
    "ENABLE_CSS": True,
    # Extra font-family stack used for the admin in RTL locales.  ``None``
    # keeps the stack shipped with the package.
    "FONT_STACK": None,
    # Languages treated as right-to-left on top of the ones in Django's
    # ``settings.LANGUAGES_BIDI``.
    "EXTRA_RTL_LANGUAGES": (),

    # -- bidirectional text --------------------------------------------
    # Default isolation direction used by ``bidi_isolate`` and the mixin.
    # One of "auto" (FSI), "ltr" (LRI) or "rtl" (RLI).
    "ISOLATION_DIRECTION": "auto",
    # Let ``BidiSafeAdminMixin`` isolate changelist cells.
    "ISOLATE_CHANGELIST": True,
    # CSS-level safety net: ``unicode-bidi: isolate`` on changelist cells and
    # read-only values, so a stray mixed-direction value cannot drag its
    # neighbours around.
    "ISOLATE_TABLE_CELLS": True,
    # ``unicode-bidi: plaintext`` on admin text inputs and textareas: each
    # field picks its own direction from what the user actually typed, which
    # is what a bilingual data-entry form needs.
    "PLAINTEXT_FORM_FIELDS": True,

    # -- localisation ---------------------------------------------------
    # Numbering system for the locale-aware formatting helpers.
    # "auto" follows the active locale, otherwise force a CLDR numbering
    # system key: "latn", "arab" or "arabext".
    "NUMERALS": "auto",
    # Use Babel when it is installed.  Set to False to always use Django's
    # own l10n machinery.
    "USE_BABEL": True,
    # Default currency for ``{{ value|l10n_currency }}``.
    "CURRENCY": "USD",

    # -- language switcher ----------------------------------------------
    "LANGUAGE_SWITCHER": True,
    # ``None`` means "use settings.LANGUAGES".  Otherwise a sequence of
    # ``(code, label)`` pairs, or a sequence of codes.
    "LANGUAGE_SWITCHER_LANGUAGES": None,
    # Show each language in its own script ("native"), in the active
    # language ("translated"), or both ("both").
    "LANGUAGE_SWITCHER_LABELS": "native",
}

#: Keys whose value must be one of a fixed set.
CHOICES: dict[str, tuple[str, ...]] = {
    "ISOLATION_DIRECTION": ("auto", "ltr", "rtl"),
    "NUMERALS": ("auto", "latn", "arab", "arabext"),
    "LANGUAGE_SWITCHER_LABELS": ("native", "translated", "both"),
}


class RTLAdminSettings:
    """Lazy, ``override_settings``-aware accessor for ``settings.RTL_ADMIN``."""

    if TYPE_CHECKING:
        # What each key in DEFAULTS holds, for type checkers only.  Nothing is
        # assigned here: at runtime every key still goes through __getattr__.
        ENABLE_CSS: bool
        FONT_STACK: str | Sequence[str] | None
        EXTRA_RTL_LANGUAGES: Iterable[str]
        ISOLATION_DIRECTION: str
        ISOLATE_CHANGELIST: bool
        ISOLATE_TABLE_CELLS: bool
        PLAINTEXT_FORM_FIELDS: bool
        NUMERALS: str
        USE_BABEL: bool
        CURRENCY: str
        LANGUAGE_SWITCHER: bool
        LANGUAGE_SWITCHER_LANGUAGES: (
            Iterable[str | tuple[str, str | Promise]] | None
        )
        LANGUAGE_SWITCHER_LABELS: str

    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = DEFAULTS if defaults is None else defaults
        self._cache: dict[str, Any] = {}

    @property
    def user_settings(self) -> dict[str, Any]:
        return getattr(settings, SETTINGS_KEY, None) or {}

    def __getattr__(self, name: str) -> Any:
        if name not in self.defaults:
            raise AttributeError(f"Invalid {SETTINGS_KEY} setting: {name!r}")
        if name in self._cache:
            return self._cache[name]
        value = self.user_settings.get(name, self.defaults[name])
        value = self._validate(name, value)
        self._cache[name] = value
        return value

    def __getitem__(self, name: str) -> Any:
        return getattr(self, name)

    def _validate(self, name: str, value: Any) -> Any:
        choices = CHOICES.get(name)
        if choices is not None and value not in choices:
            raise ImproperlyConfigured(
                f"{SETTINGS_KEY}[{name!r}] must be one of "
                f"{', '.join(repr(c) for c in choices)}, got {value!r}."
            )
        return value

    def unknown_keys(self) -> list[str]:
        """Keys present in the project settings that we do not understand."""
        return sorted(set(self.user_settings) - set(self.defaults))

    def reset(self) -> None:
        self._cache.clear()


rtl_settings = RTLAdminSettings()


@receiver(setting_changed)
def _reset_rtl_settings(*, setting: str, **kwargs: Any) -> None:
    if setting in {SETTINGS_KEY, "LANGUAGES", "LANGUAGE_CODE"}:
        rtl_settings.reset()
