"""CSV export actions for the Django admin.

Arabic admin users open changelist exports in Excel, which needs a UTF-8 BOM
to detect the encoding, reads Unicode bidi controls as garbage, treats
Arabic-Indic digits as text and executes cells that start like formulas.
These actions produce a spreadsheet-safe UTF-8 CSV stream from the selected
rows, on any ``ModelAdmin`` -- ``BidiSafeAdminMixin`` is not required.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import html
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.utils import get_fields_from_path, label_for_field, lookup_field
from django.core.exceptions import (
    FieldDoesNotExist,
    FieldError,
    ObjectDoesNotExist,
    PermissionDenied,
)
from django.db.models.constants import LOOKUP_SEP
from django.http import StreamingHttpResponse
from django.utils import timezone, translation
from django.utils.encoding import force_str
from django.utils.html import strip_tags
from django.utils.safestring import SafeData
from django.utils.translation import gettext_lazy

from .bidi import strip_isolates
from .formatting import arabic_slugify, numbering_system, transliterate_digits

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from typing import Protocol

    from django.contrib.admin import ModelAdmin
    from django.db.models import Field, Model, QuerySet
    from django.http import HttpRequest

    #: One export column: a ``list_display``-style name or a display callable.
    _Entry = str | Callable[[Model], Any]

    class _CsvAction(Protocol):
        """An admin action function, with the attributes the admin reads."""

        __name__: str
        short_description: str

        def __call__(
            self,
            modeladmin: ModelAdmin[Any],
            request: HttpRequest,
            queryset: QuerySet[Any],
        ) -> StreamingHttpResponse: ...


#: Cells starting with one of these are executed as formulas by Excel and
#: LibreOffice; a leading apostrophe forces them back to text.
_FORMULA_PREFIXES = frozenset("=+-@\t\r")

#: Rows per database fetch inside ``QuerySet.iterator()``.
_CHUNK_SIZE = 2000

#: The action label, translated in the active language.
_DESCRIPTION = gettext_lazy("Export selected rows as CSV")


class _EchoBuffer:
    """``csv.writer`` target whose ``write()`` returns the formatted row."""

    def write(self, value: str) -> str:
        return value


def _cell_text(field: Field[Any, Any] | None, value: Any) -> tuple[str, bool]:
    """Plain-text representation of one raw value, plus a temporal flag.

    The flag is ``True`` for ``date``/``datetime``/``time`` values, which are
    rendered as ISO 8601 and must keep ASCII digits even under ``digits="native"``.
    """
    if value is None:
        return "", False
    if isinstance(value, datetime.datetime):
        moment = value
        if settings.USE_TZ and timezone.is_aware(moment):
            moment = timezone.localtime(moment)
        return moment.isoformat(), True
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat(), True
    if field is not None and getattr(field, "choices", None):
        value = dict(field.flatchoices).get(value, value)
    if isinstance(value, SafeData) or hasattr(value, "__html__"):
        # Display methods may return HTML (boolean icons, badges, isolates).
        text = value.__html__() if hasattr(value, "__html__") else force_str(value)
        return html.unescape(strip_tags(text)), False
    return force_str(value), False


def _resolve_related(name: str, obj: Model) -> tuple[Field[Any, Any] | None, Any]:
    """Walk a ``field__subfield`` path, None- and ObjectDoesNotExist-safe.

    Django's ``lookup_field`` only resolves related lookups in ``list_display``
    on 5.1+, so the path is walked here on every supported version.  A missing
    intermediate object yields an empty cell rather than an error.
    """
    value: Any = obj
    for part in name.split(LOOKUP_SEP):
        if value is None:
            return None, None
        try:
            value = getattr(value, part)
            if callable(value):
                value = value()
        except (AttributeError, ObjectDoesNotExist):
            return None, None
    field: Field[Any, Any] | None = None
    try:
        field = get_fields_from_path(obj._meta.model, name)[-1]
    except (FieldDoesNotExist, FieldError, IndexError, AttributeError, TypeError):
        field = None
    return field, value


def _resolve(entry: _Entry, obj: Model, modeladmin: ModelAdmin[Any]) -> tuple[str, bool]:
    """Raw value of one column for ``obj``, as plain text plus a temporal flag.

    Named entries go through Django's ``lookup_field``, which resolves model
    fields, admin methods and model properties; related ``field__subfield``
    paths are walked explicitly so they work on every supported Django.  A
    callable whose ``__name__`` still names such an attribute -- the changelist
    wrappers ``BidiSafeAdminMixin`` puts in ``list_display`` -- is resolved by
    that name too, so the export reads the raw value instead of the rendered
    HTML cell.  Any other callable is simply called.
    """
    name = entry if isinstance(entry, str) else getattr(entry, "__name__", None)
    if isinstance(name, str):
        # A related path has non-empty parts; "__str__" also contains "__" but
        # is a plain display name, not a relation traversal.
        if LOOKUP_SEP in name and all(name.split(LOOKUP_SEP)):
            field, value = _resolve_related(name, obj)
            return _cell_text(field, value)
        try:
            field, attr, value = lookup_field(name, obj, modeladmin)
        except (AttributeError, FieldDoesNotExist, ObjectDoesNotExist):
            pass
        else:
            # lookup_field() reports an unresolvable name as (None, None, None).
            if field is not None or attr is not None:
                return _cell_text(field, value)
    if callable(entry):
        return _cell_text(None, entry(obj))
    return "", False


def _header(entry: _Entry, modeladmin: ModelAdmin[Any], header: str) -> str:
    if header == "name":
        if isinstance(entry, str):
            return entry
        return getattr(entry, "__name__", force_str(entry))
    try:
        return force_str(label_for_field(entry, modeladmin.model, modeladmin, return_attr=False))
    except AttributeError:
        # A name Django cannot label (not a field, method or property) still
        # exports its raw values; keep the name itself as the header.
        return entry if isinstance(entry, str) else getattr(entry, "__name__", force_str(entry))


def _neutralize(text: str) -> str:
    """Prefix formula-looking cells with an apostrophe so Excel reads text."""
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def _clean(text: str, digits_to: str) -> str:
    """Strip bidi controls, convert digits, neutralise formula injection."""
    return _neutralize(transliterate_digits(strip_isolates(text), digits_to))


def _content_disposition(filename: str) -> str:
    """RFC 6266 attachment header: ASCII fallback plus ``filename*=UTF-8``."""
    name = filename.replace("\r", "").replace("\n", "")
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        stem = name[:-4] if name.lower().endswith(".csv") else name
        ascii_name = (arabic_slugify(stem) or "export") + ".csv"
    else:
        ascii_name = name
    ascii_name = ascii_name.replace("\\", "").replace('"', "") or "export.csv"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"


def _action_name(
    fields: tuple[_Entry, ...] | None,
    filename: str | None,
    digits: str,
    header: str,
    bom: bool,
    delimiter: str,
) -> str:
    """A distinct ``__name__`` per option set, so factory actions can coexist.

    Django keys ``get_actions`` by the callable's ``__name__``; two factory
    actions sharing one name would overwrite each other on a ``ModelAdmin``.
    """
    field_key = (
        None
        if fields is None
        else tuple(f if isinstance(f, str) else getattr(f, "__name__", repr(f)) for f in fields)
    )
    key = repr((field_key, filename, digits, header, bom, delimiter))
    return "export_csv_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def make_csv_export_action(
    fields: Sequence[_Entry] | None = None,
    *,
    filename: str | None = None,
    digits: str = "latn",
    header: str = "verbose",
    bom: bool = True,
    delimiter: str = ",",
) -> _CsvAction:
    """Build a CSV export admin action with custom options.

    ``fields``
        Column names or display callables to export, in order.  ``None``
        (the default) uses the admin's ``list_display`` for the request.
    ``filename``
        Download filename.  ``None`` uses the model's translated
        ``verbose_name_plural`` plus ``.csv``.  Non-ASCII names are sent
        RFC 6266 encoded (``filename*=UTF-8``) with an ASCII fallback.
    ``digits``
        ``"latn"`` (the default) converts Arabic-Indic and Persian digits to
        ASCII so spreadsheets read numbers as numbers; ``"native"`` converts
        every digit to the active locale's numbering system instead.  Both
        call ``transliterate_digits()`` on non-temporal text only: ISO 8601
        date, datetime and time cells always keep ASCII digits.
    ``header``
        ``"verbose"`` (the default) uses each column's ``short_description``
        or verbose name, translated in the active language; ``"name"`` uses
        the raw field or callable name.
    ``bom``
        Write a UTF-8 BOM first (the default) so Excel detects the encoding.
    ``delimiter``
        Single-character CSV field delimiter; defaults to ``","``.

    The returned action exports only the selected rows, streams them with
    ``QuerySet.iterator()`` inside a ``StreamingHttpResponse``, strips Unicode
    bidi control characters, formats dates and datetimes as ISO 8601 in the
    current time zone, prefixes cells that start with ``=``, ``+``, ``-``,
    ``@``, tab or carriage return with an apostrophe, and raises
    ``PermissionDenied`` unless the user has the view permission.  It is
    decorated with ``admin.action(permissions=["view"])`` so the admin also
    hides it from users without that permission, and it gets a distinct
    ``__name__`` derived from its options so several factory actions can be
    registered on one ``ModelAdmin``.
    """
    if digits not in ("latn", "native"):
        raise ValueError(f"digits must be 'latn' or 'native'; got {digits!r}")
    if header not in ("verbose", "name"):
        raise ValueError(f"header must be 'verbose' or 'name'; got {header!r}")
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValueError(f"delimiter must be a single character; got {delimiter!r}")
    selected = tuple(fields) if fields is not None else None

    @admin.action(permissions=["view"], description=_DESCRIPTION)
    def export_csv(
        modeladmin: ModelAdmin[Any], request: HttpRequest, queryset: QuerySet[Any]
    ) -> StreamingHttpResponse:
        if not modeladmin.has_view_permission(request):
            raise PermissionDenied
        entries: tuple[_Entry, ...] = (
            selected if selected is not None else tuple(modeladmin.get_list_display(request))
        )
        # The stream is consumed after the response middleware has run, so
        # capture the request's language and time zone for the generator.
        language = translation.get_language()
        current_tz = timezone.get_current_timezone()
        download_name = filename or f"{force_str(modeladmin.opts.verbose_name_plural)}.csv"

        def rows() -> Iterator[str]:
            with translation.override(language), timezone.override(current_tz):
                digits_to = "latn" if digits == "latn" else numbering_system()
                writer = csv.writer(_EchoBuffer(), delimiter=delimiter, lineterminator="\r\n")
                if bom:
                    yield "\ufeff"
                yield writer.writerow(
                    [_clean(_header(entry, modeladmin, header), digits_to) for entry in entries]
                )
                for obj in queryset.iterator(chunk_size=_CHUNK_SIZE):
                    cells = []
                    for entry in entries:
                        text, temporal = _resolve(entry, obj, modeladmin)
                        text = strip_isolates(text)
                        if not temporal:
                            text = transliterate_digits(text, digits_to)
                        cells.append(_neutralize(text))
                    yield writer.writerow(cells)

        response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = _content_disposition(download_name)
        return response

    action = cast("_CsvAction", export_csv)
    action.__name__ = _action_name(selected, filename, digits, header, bom, delimiter)
    return action


@admin.action(permissions=["view"], description=_DESCRIPTION)
def export_as_csv(
    modeladmin: ModelAdmin[Any], request: HttpRequest, queryset: QuerySet[Any]
) -> StreamingHttpResponse:
    """Export the selected rows as a UTF-8 CSV file with the default options.

    Add it to any ``ModelAdmin``'s ``actions``; ``BidiSafeAdminMixin`` is not
    required.  Columns follow ``list_display`` (callables, admin methods and
    properties included), headers use the translated verbose names, digits
    become ASCII, dates and datetimes are ISO 8601 in the current time zone,
    bidi controls are stripped, formula-looking cells get a leading
    apostrophe, and the response streams with a UTF-8 BOM and an RFC 6266
    ``Content-Disposition`` filename.  See ``make_csv_export_action()``
    for the configurable variant.
    """
    return _default_export(modeladmin, request, queryset)


_default_export = make_csv_export_action()
