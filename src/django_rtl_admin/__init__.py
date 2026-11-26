"""django-rtl-admin: a properly bilingual, right-to-left Django admin.

Public API::

    from django_rtl_admin import (
        BidiSafeAdminMixin,
        arabic_search_regex,
        arabic_slugify,
        arabic_sort_expression,
        arabic_sort_key,
        isolate,
        isolate_runs,
        mark_isolated,
        format_number,
        normalize_numeric_input,
        format_currency,
        format_percent,
        format_timedelta,
        format_filesize,
        format_date,
        format_datetime,
        format_hijri_date,
        from_hijri,
        to_hijri,
        HijriDate,
        export_as_csv,
        make_csv_export_action,
    )

``BidiSafeAdminMixin``, ``export_as_csv`` and ``make_csv_export_action`` are
imported lazily: this package is imported while ``INSTALLED_APPS`` is still
being populated, and reaching into ``django.contrib.admin`` that early would
trip ``AppRegistryNotReady``.
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
    arabic_search_regex,
    arabic_slugify,
    arabic_sort_expression,
    arabic_sort_key,
    format_currency,
    format_date,
    format_datetime,
    format_filesize,
    format_hijri_date,
    format_number,
    format_percent,
    format_time,
    format_timedelta,
    normalize_numeric_input,
    numbering_system,
    transliterate_digits,
)
from .hijri import HijriDate, from_hijri, to_hijri

if TYPE_CHECKING:
    # Resolved lazily at runtime (see ``__getattr__``); imported here so type
    # checkers see the real objects rather than whatever ``__getattr__`` returns.
    from .actions import export_as_csv, make_csv_export_action
    from .mixins import BidiSafeAdminMixin

__version__ = "0.2.0"

_LAZY = {
    "BidiSafeAdminMixin": ".mixins",
    "export_as_csv": ".actions",
    "make_csv_export_action": ".actions",
}


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
    "HijriDate",
    "__version__",
    "arabic_search_regex",
    "arabic_slugify",
    "arabic_sort_expression",
    "arabic_sort_key",
    "current_direction",
    "export_as_csv",
    "format_currency",
    "format_date",
    "format_datetime",
    "format_filesize",
    "format_hijri_date",
    "format_number",
    "format_percent",
    "format_time",
    "format_timedelta",
    "from_hijri",
    "has_mixed_direction",
    "is_isolated",
    "is_rtl_language",
    "isolate",
    "isolate_runs",
    "make_csv_export_action",
    "mark_isolated",
    "mark_isolated_runs",
    "normalize_numeric_input",
    "numbering_system",
    "rtl_settings",
    "strip_isolates",
    "text_direction",
    "to_hijri",
    "transliterate_digits",
]
