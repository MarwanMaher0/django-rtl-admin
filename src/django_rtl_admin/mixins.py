"""``ModelAdmin`` mixins."""

from __future__ import annotations

from django.contrib.admin.utils import (
    display_for_field,
    display_for_value,
    label_for_field,
    lookup_field,
)

from .bidi import isolate, mark_isolated
from .conf import rtl_settings

#: Field types whose changelist representation is an icon or a bare number and
#: therefore has nothing to isolate.
_SKIPPED_FIELD_TYPES = ("BooleanField", "NullBooleanField")


class BidiSafeAdminMixin:
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bidi_wrappers: dict[str, object] = {}

    # -- configuration -----------------------------------------------------

    def bidi_isolation_enabled(self, request=None) -> bool:
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

    def get_list_display(self, request):
        display = super().get_list_display(request)
        if not self.bidi_isolation_enabled(request):
            return display
        return tuple(self._bidi_entry(entry) for entry in display)

    def get_list_display_links(self, request, list_display):
        links = super().get_list_display_links(request, list_display)
        if links is None or not self.bidi_isolation_enabled(request):
            return links
        return tuple(self._bidi_entry(entry) for entry in links)

    def get_sortable_by(self, request):
        sortable = super().get_sortable_by(request)
        if sortable is None or not self.bidi_isolation_enabled(request):
            return sortable
        return tuple(self._bidi_entry(entry) for entry in sortable)

    # -- internals ---------------------------------------------------------

    def _bidi_entry(self, entry):
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

    def _bidi_model_field(self, name: str):
        try:
            return self.model._meta.get_field(name)
        except Exception:
            return None

    def _make_bidi_wrapper(self, name: str):
        field = self._bidi_model_field(name)
        if field is not None and field.get_internal_type() in _SKIPPED_FIELD_TYPES:
            return None

        original = getattr(self, name, None) or getattr(self.model, name, None)
        if getattr(original, "boolean", False):
            return None

        model_admin = self
        direction = self.bidi_isolation_direction

        def wrapper(obj):
            resolved_field, attr, value = lookup_field(name, obj, model_admin)
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
        wrapper.short_description = label_for_field(name, self.model, self)
        wrapper.admin_order_field = self._bidi_order_field(name, field, original)
        boolean = getattr(original, "boolean", False)
        if boolean:
            wrapper.boolean = boolean
        return wrapper

    def _bidi_order_field(self, name, field, original):
        if field is not None:
            return field.name
        return getattr(original, "admin_order_field", None)

    def response_delete(self, request, obj_display, obj_id):
        # Isolate the object display name inside the success sentence so
        # identifiers such as ISBNs are not reordered in an RTL admin.
        # isolate (not mark_isolated) is used because the messages
        # framework HTML-escapes the string afterwards.
        if obj_display:
            obj_display = isolate(str(obj_display), self.bidi_isolation_direction)
        return super().response_delete(request, obj_display, obj_id)
