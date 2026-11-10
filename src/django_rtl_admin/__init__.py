"""django-rtl-admin: a properly bilingual, right-to-left Django admin.

Public API::

    from django_rtl_admin import (
        BidiSafeAdminMixin,
        isolate,
        isolate_runs,
        mark_isolated,
        format_number,
        format_currency,
        format_date,
    )

``BidiSafeAdminMixin`` is imported lazily: this package is imported while
``INSTALLED_APPS`` is still being populated, and reaching into
``django.contrib.admin`` that early would trip ``AppRegistryNotReady``.
"""

from typing import TYPE_CHECKING

from .bidi import (
    FSI,
    LRI,
    PDI,
    RLI,
    current_direction,
    has_mixed_direction,
    is_isolated,
    is_rtl_language,
    isolate,
    isolate_runs,
    mark_isolated,
    mark_isolated_runs,
    strip_isolates,
    text_direction,
)
from .conf import DEFAULTS, rtl_settings
from .formatting import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    format_percent,
    format_time,
    numbering_system,
    transliterate_digits,
)

if TYPE_CHECKING:
    # Resolved lazily at runtime (see ``__getattr__``); imported here so type
    # checkers see the real class rather than whatever ``__getattr__`` returns.
    from .mixins import BidiSafeAdminMixin

__version__ = "0.1.0"

_LAZY = {"BidiSafeAdminMixin": ".mixins"}


def __getattr__(name: str) -> object:
    if name in _LAZY:
        from importlib import import_module

        module = import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    "DEFAULTS",
    "FSI",
    "LRI",
    "PDI",
    "RLI",
    "BidiSafeAdminMixin",
    "__version__",
    "current_direction",
    "format_currency",
    "format_date",
    "format_datetime",
    "format_number",
    "format_percent",
    "format_time",
    "has_mixed_direction",
    "is_isolated",
    "is_rtl_language",
    "isolate",
    "isolate_runs",
    "mark_isolated",
    "mark_isolated_runs",
    "numbering_system",
    "rtl_settings",
    "strip_isolates",
    "text_direction",
    "transliterate_digits",
]
