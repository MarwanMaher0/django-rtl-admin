"""``ModelAdmin`` mixins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

import django
from django.contrib.admin.utils import (
    display_for_field,
    display_for_value,
    get_fields_from_path,
    label_for_field,
    lookup_field,
)
from django.db.models.constants import LOOKUP_SEP

from .bidi import mark_isolated
from .conf import rtl_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.admin import ModelAdmin
    from django.db.models import Field, Model
    from django.db.models.fields.reverse_related import ForeignObjectRel
    from django.http import HttpRequest
    from django.utils.functional import Promise

    #: One ``list_display`` entry, and the list or tuple of them the admin
    #: passes around.
    _Display = str | Callable[[Any], str | bool]
    _ListDisplay = list[_Display] | tuple[_Display, ...]
    _ModelField = Field[Any, Any] | ForeignObjectRel

    # The mixin calls ``super()`` hooks and reads attributes that only exist
    # once it is combined with a ``ModelAdmin``.  Type checkers are told so;
    # at runtime it stays a plain class, importable before the app registry
    # is ready and with nothing added to the MRO.
    _Base = ModelAdmin[Any]
else:
    _Base = object

#: Field types whose changelist representation is an icon or a bare number and
#: therefore has nothing to isolate.
_SKIPPED_FIELD_TYPES = ("BooleanField", "NullBooleanField")

#: Django 5.1 added related lookups such as ``publisher__name`` to
#: ``list_display``.
_SUPPORTS_RELATED_LOOKUPS = django.VERSION >= (5, 1)


def _is_related_lookup(name: str) -> bool:
    return _SUPPORTS_RELATED_LOOKUPS and LOOKUP_SEP in name


class _DisplayWrapper(Protocol):
    """A changelist display callable, with the attributes the admin reads."""

    __name__: str
    short_description: str | Promise
    admin_order_field: object
    boolean: bool

    def __call__(self, obj: Model) -> str: ...


class BidiSafeAdminMixin(_Base):
    """Wrap every changelist cell in a Unicode isolate.

    Mix it into a ``ModelAdmin`` and mixed-direction values -- reference
    numbers, emails, URLs, file paths, version strings, hyphenated dates --
    stop being visually reordered when the admin is displayed in Arabic,
    Hebrew, Persian or Urdu::

        @admin.register(Book)
        class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
            list_display = ("title", "isbn", "published_on")

    Columns keep their labels, their ``column-<name>``/``field-<name>`` CSS
    classes, their sort links and their links to the change form.  Boolean
    columns (rendered as icons) and anything listed in ``list_editable`` are
    left alone.

    Class-level knobs:

    ``bidi_isolate_changelist``
        ``True``/``False`` to override ``RTL_ADMIN["ISOLATE_CHANGELIST"]``.
    ``bidi_isolate_fields``
        Restrict isolation to these ``list_display`` entries.
    ``bidi_isolate_exclude``
        Leave these ``list_display`` entries alone.
    ``bidi_isolation_direction``
        ``"auto"``, ``"ltr"`` or ``"rtl"``; overrides
        ``RTL_ADMIN["ISOLATION_DIRECTION"]``.
    """

    bidi_isolate_changelist: bool | None = None
    bidi_isolate_fields: tuple[str, ...] | None = None
    bidi_isolate_exclude: tuple[str, ...] = ()
    bidi_isolation_direction: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._bidi_wrappers: dict[str, _DisplayWrapper] = {}

    # -- configuration -----------------------------------------------------

    def bidi_isolation_enabled(self, request: HttpRequest | None = None) -> bool:
        if self.bidi_isolate_changelist is None:
            return bool(rtl_settings.ISOLATE_CHANGELIST)
        return bool(self.bidi_isolate_changelist)

    def _bidi_should_isolate(self, name: str) -> bool:
        if name in self.bidi_isolate_exclude:
            return False
        if name in (getattr(self, "list_editable", ()) or ()):
            return False
        if self.bidi_isolate_fields is not None:
            return name in self.bidi_isolate_fields
        return True

    # -- ModelAdmin hooks --------------------------------------------------

    def get_list_display(self, request: HttpRequest) -> _ListDisplay:
        display = super().get_list_display(request)
        if not self.bidi_isolation_enabled(request):
            return display
        return tuple(self._bidi_entry(entry) for entry in display)

    def get_list_display_links(
        self, request: HttpRequest, list_display: _ListDisplay
    ) -> _ListDisplay:
        links = super().get_list_display_links(request, list_display)
        if links is None or not self.bidi_isolation_enabled(request):
            return links
        return tuple(self._bidi_entry(entry) for entry in links)

    def get_sortable_by(self, request: HttpRequest) -> _ListDisplay:
        sortable = super().get_sortable_by(request)
        if sortable is None or not self.bidi_isolation_enabled(request):
            return sortable
        return tuple(self._bidi_entry(entry) for entry in sortable)

    # -- internals ---------------------------------------------------------

    def _bidi_entry(self, entry: _Display) -> _Display:
        """Map one ``list_display`` entry to its isolating wrapper."""
        if not isinstance(entry, str):
            return entry
        if not self._bidi_should_isolate(entry):
            return entry
        try:
            return self._bidi_wrappers[entry]
        except KeyError:
            pass
        wrapper = self._make_bidi_wrapper(entry)
        if wrapper is None:
            return entry
        self._bidi_wrappers[entry] = wrapper
        return wrapper

    def _bidi_model_field(self, name: str) -> _ModelField | None:
        try:
            field: _ModelField = self.model._meta.get_field(name)
            return field
        except Exception:
            pass
        if not _is_related_lookup(name):
            return None
        try:
            return get_fields_from_path(self.model, name)[-1]
        except Exception:
            return None

    def _make_bidi_wrapper(self, name: str) -> _DisplayWrapper | None:
        field = self._bidi_model_field(name)
        if field is not None and field.get_internal_type() in _SKIPPED_FIELD_TYPES:
            return None

        original = getattr(self, name, None) or getattr(self.model, name, None)
        if getattr(original, "boolean", False):
            return None

        model_admin = self
        direction = self.bidi_isolation_direction
        # The stubs type this slot as a concrete ``Field``.  A related lookup
        # may also end on a reverse relation, which ``display_for_field`` only
        # ever inspects with ``isinstance``/``getattr``.
        lookup_target = (
            cast("Field[Any, Any] | None", field) if _is_related_lookup(name) else None
        )

        def wrapper(obj: Model) -> str:
            resolved_field, attr, value = lookup_field(name, obj, model_admin)
            if resolved_field is None and lookup_target is not None:
                resolved_field = lookup_target
            empty = getattr(
                attr, "empty_value_display", model_admin.get_empty_value_display()
            )
            if resolved_field is None:
                text = display_for_value(value, empty, getattr(attr, "boolean", False))
            else:
                text = display_for_field(value, resolved_field, empty)
            if text is None or text == "" or text == empty:
                return text
            return mark_isolated(text, direction)

        # Keep the admin's own naming conventions intact: ``__name__`` drives
        # the ``column-<name>``/``field-<name>`` CSS classes, and
        # ``short_description`` drives the column header.
        wrapper.__name__ = name
        display = cast("_DisplayWrapper", wrapper)
        # ``return_attr=False`` is Django's default; spelling it out selects
        # the overload that returns the label alone.
        display.short_description = label_for_field(
            name, self.model, self, return_attr=False
        )
        display.admin_order_field = self._bidi_order_field(name, field, original)
        boolean = getattr(original, "boolean", False)
        if boolean:
            display.boolean = boolean
        return display

    def _bidi_order_field(
        self, name: str, field: _ModelField | None, original: object
    ) -> object:
        if field is not None:
            return name if _is_related_lookup(name) else field.name
        return getattr(original, "admin_order_field", None)
