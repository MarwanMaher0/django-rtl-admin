"""``ModelAdmin`` mixins."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any, Protocol, cast

import django
from django.contrib.admin import helpers
from django.contrib.admin.utils import (
    display_for_field,
    display_for_value,
    get_fields_from_path,
    label_for_field,
    lookup_field,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.constants import LOOKUP_SEP
from django.utils.html import conditional_escape
from django.utils.safestring import SafeData, mark_safe

from .bidi import current_direction, mark_isolated, mark_isolated_runs, text_direction
from .conf import rtl_settings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from django.contrib.admin import ModelAdmin
    from django.db.models import Field, Model
    from django.db.models.fields.reverse_related import ForeignObjectRel
    from django.http import HttpRequest, HttpResponse
    from django.utils.functional import Promise
    from django.utils.safestring import SafeString

    #: One ``list_display`` entry, and the list or tuple of them the admin
    #: passes around.
    _Display = str | Callable[[Any], str | bool]
    _ListDisplay = list[_Display] | tuple[_Display, ...]
    _ReadonlyEntry = str | Callable[[Any], object]
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

#: Stock ``linebreaksbr`` escapes ``<`` and joins paragraph lines with ``<br>``.
#: Any other HTML tag in ``contents()`` came from pre-marked safe markup
#: (boolean icons, admin links, custom ``format_html`` badges, read-only widgets).
_NON_BR_TAG_RE = re.compile(r"<(?!br>)")

_WRAPPED_CONTAINERS = (
    helpers.InlineAdminFormSet,
    helpers.AdminForm,
    helpers.Fieldset,
    helpers.Fieldline,
)


def _is_related_lookup(name: str) -> bool:
    return _SUPPORTS_RELATED_LOOKUPS and LOOKUP_SEP in name


def _isolate_rendered_lines(rendered: SafeString, empty_value_display: Any) -> SafeString:
    if (
        not rendered
        or rendered == conditional_escape(empty_value_display)
        or _NON_BR_TAG_RE.search(rendered)
    ):
        return rendered
    default_dir = current_direction()
    lines = []
    for line in rendered.split("<br>"):
        raw = html.unescape(line)
        lines.append(mark_isolated_runs(raw, base=text_direction(raw, default=default_dir)))
    return mark_safe("<br>".join(lines))


class _ResolvedLookup:
    boolean: bool

    def __init__(self, value: Any, *, is_boolean: bool) -> None:
        self._value = value
        if is_boolean:
            self.boolean = True

    def __call__(self, _obj: Model) -> Any:
        return self._value


class _BidiAdminReadonlyField:
    """Wrap an ``AdminReadonlyField`` and isolate embedded runs in plain-text values.

    Read-only values are styled with ``unicode-bidi: plaintext`` in
    ``rtl-admin.css``, so the browser resolves each ``<br>``-separated paragraph
    from its first strong character in both LTR and RTL admins.  Using that same
    first-strong direction as ``base`` (falling back to the active UI direction
    for neutral-only lines) wraps embedded paths, versions and punctuated dates
    inside Arabic prose in ``LRI...PDI`` even on an English page, while embedded
    Arabic runs inside English prose are wrapped in ``RLI...PDI``.
    """

    def __init__(self, readonly: helpers.AdminReadonlyField) -> None:
        self._readonly = readonly

    def __getattr__(self, name: str) -> Any:
        return getattr(self._readonly, name)

    def contents(self) -> SafeString:
        readonly = self._readonly
        if type(readonly).contents is not helpers.AdminReadonlyField.contents:
            return _isolate_rendered_lines(readonly.contents(), readonly.empty_value_display)

        field = readonly.field["field"]
        try:
            f, attr, value = lookup_field(field, readonly.form.instance, readonly.model_admin)
        except (AttributeError, ValueError, ObjectDoesNotExist):
            return conditional_escape(readonly.empty_value_display)

        is_boolean = (
            bool(getattr(attr, "boolean", False))
            if f is None
            else f.get_internal_type() in _SKIPPED_FIELD_TYPES
        )
        is_safe_html = isinstance(value, SafeData) or hasattr(value, "__html__")

        if f is None:
            readonly.field["field"] = _ResolvedLookup(value, is_boolean=is_boolean)
            try:
                rendered = readonly.contents()
            finally:
                readonly.field["field"] = field
        else:
            rendered = readonly.contents()

        if is_boolean or is_safe_html:
            return rendered
        return _isolate_rendered_lines(rendered, readonly.empty_value_display)


class _BidiAdminProxy:
    """Iterate an admin form, fieldset or fieldline, replacing ``AdminReadonlyField`` items."""

    def __init__(
        self,
        wrapped: Any,
        should_isolate: Callable[[_ReadonlyEntry], bool],
    ) -> None:
        self._wrapped = wrapped
        self._should_isolate = should_isolate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def __repr__(self) -> str:
        return repr(self._wrapped)

    def __iter__(self) -> Iterator[Any]:
        for item in self._wrapped:
            if isinstance(item, helpers.AdminReadonlyField):
                if self._should_isolate(item.field["field"]):
                    yield _BidiAdminReadonlyField(item)
                else:
                    yield item
            elif isinstance(item, _WRAPPED_CONTAINERS):
                yield _BidiAdminProxy(item, self._should_isolate)
            else:
                yield item


class _DisplayWrapper(Protocol):
    """A changelist display callable, with the attributes the admin reads."""

    __name__: str
    short_description: str | Promise
    admin_order_field: object
    boolean: bool

    def __call__(self, obj: Model) -> str: ...


class BidiSafeAdminMixin(_Base):
    """Isolate changelist cells and change-form read-only field values.

    Mix it into a ``ModelAdmin`` and mixed-direction values -- reference
    numbers, emails, URLs, file paths, version strings, hyphenated dates --
    stop being visually reordered when the admin is displayed in Arabic,
    Hebrew, Persian or Urdu::

        @admin.register(Book)
        class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
            list_display = ("title", "isbn", "published_on")
            readonly_fields = ("archive_note",)

    Columns keep their labels, their ``column-<name>``/``field-<name>`` CSS
    classes, their sort links and their links to the change form.  On the
    change form, read-only field values have embedded opposite-direction runs
    isolated while labels, help text and CSS classes stay untouched.  Boolean
    fields (rendered as icons), ``SafeString`` HTML values and anything listed
    in ``list_editable`` are left alone.

    Class-level knobs:

    ``bidi_isolate_changelist``
        ``True``/``False`` to override ``RTL_ADMIN["ISOLATE_CHANGELIST"]``.
    ``bidi_isolate_readonly``
        ``True``/``False`` to override ``RTL_ADMIN["ISOLATE_READONLY_FIELDS"]``.
    ``bidi_isolate_fields``
        Restrict changelist isolation to these ``list_display`` entries.
    ``bidi_isolate_exclude``
        Leave these ``list_display`` or ``readonly_fields`` entries alone.
    ``bidi_isolation_direction``
        ``"auto"``, ``"ltr"`` or ``"rtl"``; overrides
        ``RTL_ADMIN["ISOLATION_DIRECTION"]`` for changelist cells.
    """

    bidi_isolate_changelist: bool | None = None
    bidi_isolate_readonly: bool | None = None
    bidi_isolate_fields: tuple[str, ...] | None = None
    bidi_isolate_exclude: tuple[str | Callable[[Any], object], ...] = ()
    bidi_isolation_direction: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._bidi_wrappers: dict[str, _DisplayWrapper] = {}

    # -- configuration -----------------------------------------------------

    def bidi_isolation_enabled(self, request: HttpRequest | None = None) -> bool:
        if self.bidi_isolate_changelist is None:
            return bool(rtl_settings.ISOLATE_CHANGELIST)
        return bool(self.bidi_isolate_changelist)

    def bidi_readonly_isolation_enabled(self, request: HttpRequest | None = None) -> bool:
        if self.bidi_isolate_readonly is None:
            return bool(rtl_settings.ISOLATE_READONLY_FIELDS)
        return bool(self.bidi_isolate_readonly)

    def _bidi_should_isolate(self, name: str) -> bool:
        if name in self.bidi_isolate_exclude:
            return False
        if name in (getattr(self, "list_editable", ()) or ()):
            return False
        if self.bidi_isolate_fields is not None:
            return name in self.bidi_isolate_fields
        return True

    def _bidi_should_isolate_readonly(self, field: _ReadonlyEntry) -> bool:
        if field in self.bidi_isolate_exclude:
            return False
        if callable(field):
            name = getattr(field, "__name__", None)
            if isinstance(name, str) and name in self.bidi_isolate_exclude:
                return False
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

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: Any = None,
    ) -> HttpResponse:
        adminform = context.get("adminform")
        if isinstance(adminform, helpers.AdminForm) and self.bidi_readonly_isolation_enabled(
            request
        ):
            context["adminform"] = _BidiAdminProxy(adminform, self._bidi_should_isolate_readonly)
        inline_formsets = context.get("inline_admin_formsets")
        if inline_formsets:
            wrapped_inlines: list[Any] = []
            changed = False
            for inline_formset in inline_formsets:
                inline = getattr(inline_formset, "opts", None)
                if (
                    isinstance(inline_formset, helpers.InlineAdminFormSet)
                    and isinstance(inline, BidiSafeAdminMixin)
                    and inline.bidi_readonly_isolation_enabled(request)
                ):
                    wrapped_inlines.append(
                        _BidiAdminProxy(inline_formset, inline._bidi_should_isolate_readonly)
                    )
                    changed = True
                else:
                    wrapped_inlines.append(inline_formset)
            if changed:
                context["inline_admin_formsets"] = wrapped_inlines
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )

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
        lookup_target = cast("Field[Any, Any] | None", field) if _is_related_lookup(name) else None

        def wrapper(obj: Model) -> str:
            resolved_field, attr, value = lookup_field(name, obj, model_admin)
            if resolved_field is None and lookup_target is not None:
                resolved_field = lookup_target
            empty = getattr(attr, "empty_value_display", model_admin.get_empty_value_display())
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
        display.short_description = label_for_field(name, self.model, self, return_attr=False)
        display.admin_order_field = self._bidi_order_field(name, field, original)
        boolean = getattr(original, "boolean", False)
        if boolean:
            display.boolean = boolean
        return display

    def _bidi_order_field(self, name: str, field: _ModelField | None, original: object) -> object:
        if field is not None:
            return name if _is_related_lookup(name) else field.name
        return getattr(original, "admin_order_field", None)
