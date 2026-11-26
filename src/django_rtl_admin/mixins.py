"""``ModelAdmin`` mixins."""

from __future__ import annotations

import html
import re
from contextlib import contextmanager
from functools import lru_cache, reduce
from operator import and_, or_
from typing import TYPE_CHECKING, Any, Protocol, cast

import django
from django import forms
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import (
    display_for_field,
    display_for_value,
    get_fields_from_path,
    label_for_field,
    lookup_field,
    lookup_spawns_duplicates,
)
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.utils.datastructures import MultiValueDict
from django.utils.formats import get_format
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import SafeData, mark_safe
from django.utils.text import smart_split, unescape_string_literal
from django.utils.translation import gettext

from .bidi import PDI, current_direction, isolate, mark_isolated, mark_isolated_runs, text_direction
from .conf import rtl_settings
from .formatting import (
    _has_arabic_search_chars,
    _has_foldable_search_chars,
    arabic_search_regex,
    arabic_slugify,
    arabic_sort_expression,
    normalize_numeric_input,
    numbering_system,
    transliterate_digits,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

    from django.contrib.admin import ModelAdmin
    from django.db.models import Field, Model, QuerySet
    from django.db.models.expressions import Combinable
    from django.db.models.fields.reverse_related import ForeignObjectRel
    from django.db.models.options import Options
    from django.forms.models import BaseInlineFormSet
    from django.http import HttpRequest, HttpResponse
    from django.utils.functional import Promise
    from django.utils.safestring import SafeString

    #: One ``list_display`` entry, and the list or tuple of them the admin
    #: passes around.
    _Display = str | Callable[[Any], str | bool]
    _ListDisplay = list[_Display] | tuple[_Display, ...]
    _ReadonlyEntry = str | Callable[[Any], object]
    _ModelField = Field[Any, Any] | ForeignObjectRel
    _SlugTargets = dict[str, tuple[Sequence[str], bool, int | None]]

    # The mixin calls ``super()`` hooks and reads attributes that only exist
    # once it is combined with a ``ModelAdmin``.  Type checkers are told so;
    # at runtime it stays a plain class, importable before the app registry
    # is ready and with nothing added to the MRO.
    _Base = ModelAdmin[Any]
    _ModelFormBase = forms.ModelForm[Any]
else:
    _Base = _ModelFormBase = object

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

#: ``admin/delete_confirmation.html`` shortens the breadcrumb label with
#: ``truncatewords:"18"``.  The regex matches everything up to the end of the
#: 18th word, the point where that filter would cut.
_BREADCRUMB_WORDS = 18
_BREADCRUMB_CUTOFF_RE = re.compile(rf"\s*(?:\S+\s+){{{_BREADCRUMB_WORDS - 1}}}\S+")

#: Set on the request while ``response_add``/``response_change`` run for a user
#: who cannot change the object: ``(verbose_name, str(obj))``, the two values
#: Django formats into its success message.
_PLAIN_NAME_ATTR = "_bidi_plain_object_name"

#: The msgids of the success messages ``ModelAdmin.response_add`` and
#: ``response_change`` build (Django 4.2 to 6.1) that can carry the object name
#: as plain text.  The "You may edit it again below." variant of the add
#: message is only used with change permission, where the name is a link.
_SUCCESS_MESSAGES = (
    "The {name} “{obj}” was added successfully.",
    "The {name} “{obj}” was added successfully. You may add another {name} below.",
    "The {name} “{obj}” was changed successfully.",
    "The {name} “{obj}” was changed successfully. You may edit it again below.",
    "The {name} “{obj}” was changed successfully. You may add another {name} below.",
)

_WRAPPED_CONTAINERS = (
    helpers.InlineAdminFormSet,
    helpers.AdminForm,
    helpers.Fieldset,
    helpers.Fieldline,
)

#: Model field types whose changelist cells have digits localized when
#: ``LOCALIZE_CHANGELIST_DIGITS`` / ``bidi_local_digits`` is enabled.
_LOCAL_DIGIT_FIELD_TYPES: tuple[type[models.Field[Any, Any]], ...] = (
    models.IntegerField,
    models.DecimalField,
    models.FloatField,
    models.DateField,
    models.DateTimeField,
    models.TimeField,
    models.DurationField,
)

_HTML_TAG_OR_NUM_ENTITY_RE = re.compile(r"(<[^>]*>|&#[xX]?[0-9a-fA-F]+;)")


def _is_related_lookup(name: str) -> bool:
    return _SUPPORTS_RELATED_LOOKUPS and LOOKUP_SEP in name


def _is_local_digit_field(field: _ModelField | None) -> bool:
    if not isinstance(field, _LOCAL_DIGIT_FIELD_TYPES):
        return False
    return not (getattr(field, "choices", None) or getattr(field, "flatchoices", None))


def _localize_cell_digits(text: str) -> str:
    system = numbering_system()
    if system == "latn":
        return text
    if isinstance(text, SafeData):
        if "<" not in text and "&#" not in text:
            return mark_safe(transliterate_digits(text, system))
        parts = _HTML_TAG_OR_NUM_ENTITY_RE.split(text)
        rewritten = "".join(
            part if index % 2 else transliterate_digits(part, system)
            for index, part in enumerate(parts)
        )
        return mark_safe(rewritten)
    return transliterate_digits(text, system)


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


def _isolate_plain_object_name(message: Any, verbose_name: Any, obj_display: str) -> Any:
    """Isolate the object name in one of Django's plain-text success messages.

    ``message`` is rewritten only when it is exactly what Django formats from
    one of ``_SUCCESS_MESSAGES`` with the plain name -- as printed, or stripped
    the way Django 6.1 displays it.  The linked form of the message and any
    message written by the project differ from that and are returned
    untouched, so no character is ever inserted into text this module did not
    recognise.  ``format_html`` escapes the name; isolates are plain
    characters and pass through it.
    """
    for msgid in _SUCCESS_MESSAGES:
        template = gettext(msgid)
        for name in dict.fromkeys((obj_display, obj_display.strip())):
            if message != format_html(template, name=verbose_name, obj=name):
                continue
            isolated = isolate(name)
            if not isolated:
                return message
            return format_html(template, name=verbose_name, obj=isolated)
    return message


def _isolate_deleted_entry(entry: Any) -> Any:
    """Isolate the object name in a plain-text ``get_deleted_objects`` entry.

    Django formats an unlinked entry as ``"<Verbose name>: <str(obj)>"``
    (plain ``str``) and a linked entry with ``format_html`` (``SafeString``).
    Nested lists are walked recursively; linked entries, empty/whitespace-only
    names and entries without ``": "`` are returned untouched; the result for
    a plain entry stays a plain ``str`` so Django's ``unordered_list`` filter
    still escapes any HTML in the name.
    """
    if isinstance(entry, list):
        return [_isolate_deleted_entry(item) for item in entry]
    if not isinstance(entry, str) or isinstance(entry, SafeData) or hasattr(entry, "__html__"):
        return entry
    prefix, sep, name = entry.partition(": ")
    if not sep or not name.strip():
        return entry
    isolated = isolate(name)
    if not isolated:
        return entry
    return f"{prefix}{sep}{isolated}"


# DecimalField and FloatField are both IntegerField subclasses.
_NORMALIZED_FIELD_TYPES: tuple[type[forms.Field], ...] = (
    forms.IntegerField,
    forms.DateField,
    forms.TimeField,
    forms.DateTimeField,
)


@lru_cache
def _normalized_field_class(field_class: type[forms.Field]) -> type[forms.Field]:
    """Extend the configured form field, not Django's shared field class.

    Django copies the fields for each form (and each formset row). A method
    on a subclass reads that copy's localize, input_formats and error_messages;
    wrapping a bound method on the prototype would keep using the prototype.
    """

    def to_python(self: forms.Field, value: Any) -> Any:
        separator = get_format("DECIMAL_SEPARATOR") if self.localize else "."
        return field_class.to_python(
            self, normalize_numeric_input(value, decimal_separator=separator)
        )

    return type(
        f"Normalized{field_class.__name__}",
        (field_class,),
        {"to_python": to_python, "__slots__": ()},
    )


def _enable_input_normalization(field: forms.Field) -> None:
    if isinstance(field, forms.SplitDateTimeField):
        for part in field.fields:
            _enable_input_normalization(part)
    elif isinstance(field, _NORMALIZED_FIELD_TYPES):
        # Classes are hashable cache keys; mypy checks the instance's __hash__.
        field.__class__ = _normalized_field_class(type(field))  # type: ignore[arg-type]
        widget = field.widget
        if isinstance(widget, forms.NumberInput) and widget.input_type == "number":
            # A number input can discard localized text before POST or when
            # redisplaying an invalid value. Keep the numeric keyboard hint.
            widget.input_type = "text"
            fractional = isinstance(field, (forms.DecimalField, forms.FloatField))
            widget.attrs.setdefault("inputmode", "decimal" if fractional else "numeric")


class _PrepopulatedSlugForm(_ModelFormBase):
    _slug_targets: _SlugTargets
    _needs_slug_media: bool

    @property
    def media(self) -> forms.Media:
        media = super().media
        if self._needs_slug_media:
            media += forms.Media(js=[_PREPOPULATE_SCRIPT, _SLUG_SCRIPT])
        return media

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name, (_, allow_unicode, max_length) in self._slug_targets.items():
            field = self.fields.get(name)
            if field is None:
                continue
            widget = field.widget
            if self.instance._state.adding and not field.disabled:
                widget.attrs["data-rtl-slug"] = "unicode" if allow_unicode else "ascii"
                widget.attrs["data-rtl-slug-length"] = "" if max_length is None else max_length
                # Let the browser submit an empty slug even without JS.
                widget.use_required_attribute = lambda _initial: False
            else:
                widget.attrs["data-rtl-slug"] = "off"

    def full_clean(self) -> None:
        if (
            self.is_bound
            and self.instance._state.adding
            and (not self.empty_permitted or self.has_changed())
        ):
            updates = {}
            for name, (sources, allow_unicode, max_length) in self._slug_targets.items():
                field = self.fields.get(name)
                if field is None or field.disabled:
                    continue
                submitted = self[name].data
                if submitted is not None and str(submitted).strip():
                    continue
                values = [self[source].value() for source in sources if source in self.fields]
                slug = arabic_slugify(
                    " ".join(str(value) for value in values if value not in (None, "")),
                    allow_unicode=allow_unicode,
                    max_length=max_length,
                )
                if slug:
                    updates[self.add_prefix(name)] = slug
            if updates:
                # Keep request.POST and other inline rows untouched. Django
                # validates the generated slug just like a submitted one.
                data = (
                    self.data.copy() if isinstance(self.data, MultiValueDict) else dict(self.data)
                )
                for key, value in updates.items():
                    data[key] = value
                self.data = data
        super().full_clean()


def _slug_form(
    form: type[forms.ModelForm[Any]],
    prepopulated: Mapping[str, Sequence[str]],
    opts: Options[Any],
    *,
    needs_media: bool,
) -> type[forms.ModelForm[Any]]:
    targets: _SlugTargets = {}
    for name, sources in prepopulated.items():
        field = form.base_fields.get(name)
        if (
            field is None
            or not sources
            or any(source not in form.base_fields for source in sources)
        ):
            continue
        try:
            model_field = opts.get_field(name)
        except FieldDoesNotExist:
            continue
        if isinstance(model_field, models.SlugField):
            limits = [
                limit
                for limit in (model_field.max_length, getattr(field, "max_length", None))
                if limit is not None
            ]
            # django-stubs doesn't declare SlugField.allow_unicode.
            targets[name] = (
                sources,
                bool(getattr(model_field, "allow_unicode", False)),
                min(limits, default=None),
            )
    if not targets:
        return form
    wrapped = cast(
        "type[forms.ModelForm[Any]]",
        type(
            form.__name__,
            (_PrepopulatedSlugForm, form),
            {
                "_slug_targets": targets,
                "_needs_slug_media": needs_media,
                "media": _PrepopulatedSlugForm.media,
            },
        ),
    )
    # The ModelForm metaclass rebuilds base_fields. Keep the fields selected
    # and customized by the admin's original get_form()/get_formset().
    wrapped.base_fields = form.base_fields
    return wrapped


_PREPOPULATE_SCRIPT = "admin/js/prepopulate.js"
_SLUG_SCRIPT = "django_rtl_admin/js/slug.js"


_EXPLICIT_TEXT_LOOKUPS: dict[str, str] = {
    "icontains": "contains",
    "contains": "contains",
    "istartswith": "startswith",
    "startswith": "startswith",
    "iendswith": "endswith",
    "endswith": "endswith",
    "iexact": "exact",
    "exact": "exact",
}


def _anchor_search_regex(pattern: str, mode: str) -> str:
    if mode == "startswith":
        return f"^{pattern}"
    if mode == "endswith":
        return f"{pattern}$"
    if mode == "exact":
        return f"^{pattern}$"
    return pattern


_STRICT_BOOL_VALUES: dict[str, bool | None] = {
    "true": True,
    "1": True,
    "false": False,
    "0": False,
    "none": None,
    "null": None,
}


def _coerce_exact_search_value(field: Field[Any, Any], bit: str) -> tuple[bool, Any]:
    if isinstance(field, models.BooleanField):
        lowered = bit.lower()
        if lowered in _STRICT_BOOL_VALUES and (
            field.null or _STRICT_BOOL_VALUES[lowered] is not None
        ):
            return True, _STRICT_BOOL_VALUES[lowered]
        return False, None
    try:
        return True, field.to_python(bit)
    except (ValidationError, ValueError, TypeError):
        return False, None


def _classify_search_field(
    opts: Options[Any], field_name: str
) -> tuple[tuple[str, Field[Any, Any] | None], tuple[str, str] | None]:
    if field_name.startswith("@"):
        return (f"{field_name[1:]}__search", None), None

    prefix = field_name[0] if field_name.startswith(("^", "=")) else ""
    path = field_name[1:] if prefix else field_name
    cur_opts = opts
    prev_field: _ModelField | None = None
    parts = path.split(LOOKUP_SEP)
    for index, part in enumerate(parts):
        resolved = cur_opts.pk.name if part == "pk" and cur_opts.pk is not None else part
        try:
            db_field = cur_opts.get_field(resolved)
        except FieldDoesNotExist:
            if not prefix and isinstance(prev_field, models.Field) and prev_field.get_lookup(part):
                is_text = isinstance(prev_field, (models.CharField, models.TextField))
                validate = prev_field if part == "exact" and not is_text else None
                regex_spec: tuple[str, str] | None = None
                if index == len(parts) - 1 and is_text and part in _EXPLICIT_TEXT_LOOKUPS:
                    base_path = LOOKUP_SEP.join(parts[:index])
                    regex_spec = (f"{base_path}__iregex", _EXPLICIT_TEXT_LOOKUPS[part])
                return (path, validate), regex_spec
            prev_field = None
            break
        prev_field = db_field
        if hasattr(db_field, "path_infos"):
            cur_opts = db_field.path_infos[-1].to_opts

    if prefix:
        stock_lookup = f"{path}__istartswith" if prefix == "^" else f"{path}__iexact"
        mode = "startswith" if prefix == "^" else "exact"
    else:
        stock_lookup = f"{path}__icontains"
        mode = "contains"
    if isinstance(prev_field, (models.CharField, models.TextField)):
        return (stock_lookup, None), (f"{path}__iregex", mode)
    return (stock_lookup, None), None


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


class _BidiDeleteObjectProxy:
    """Wrap ``context["object"]`` on the delete confirmation page.

    ``__str__`` returns the object's display name (computed once by
    ``render_delete_form``) wrapped in an isolate; every other attribute
    (the breadcrumb's ``object.pk``, ``_meta``, ...) is delegated to the real
    object.  Isolates are plain characters, so the template's autoescaping
    keeps them and still escapes any HTML in the name.
    """

    def __init__(self, obj: Any, display: str) -> None:
        self._obj = obj
        self._display = display

    def __getattr__(self, name: str) -> Any:
        return getattr(self._obj, name)

    def __str__(self) -> str:
        text = self._display
        # Empty and whitespace-only names render as stock (the breadcrumb's
        # ``display_for_value`` shows its "-" placeholder for them).
        if not text.strip():
            return text
        isolated = isolate(text)
        if not isolated:
            return isolated
        opener, body = isolated[0], isolated[1:-1]
        match = _BREADCRUMB_CUTOFF_RE.match(body)
        if match is None or not body[match.end() :].strip():
            return isolated
        # The breadcrumb applies ``truncatewords:"18"``.  A closing PDI beyond
        # word 18 would be truncated away, leaving an unbalanced isolate, so
        # close and reopen the isolate at that boundary, reusing the original
        # whitespace as the separator: whatever the filter keeps still ends
        # with a PDI.
        cut = match.end()
        rest = body[cut:]
        tail = rest.lstrip()
        gap = rest[: len(rest) - len(tail)]
        return f"{opener}{body[:cut]}{PDI}{gap}{opener}{tail}{PDI}"


class _DisplayWrapper(Protocol):
    """A changelist display callable, with the attributes the admin reads."""

    __name__: str
    short_description: str | Promise
    admin_order_field: object
    boolean: bool

    def __call__(self, obj: Model) -> str: ...


class _ArabicOrderingChangeList(ChangeList):
    def get_ordering(self, request: HttpRequest, queryset: QuerySet[Any]) -> list[str | Combinable]:
        # Let Django resolve header indexes, display callables, the admin's
        # ordering and sort directions before substituting the actual SQL key.
        ordering = list(super().get_ordering(request, queryset))
        model_admin = cast("BidiSafeAdminMixin", self.model_admin)
        changed = False
        for i, term in enumerate(ordering):
            field = term.expression if isinstance(term, models.OrderBy) else term
            if type(field) is models.F:
                name = field.name  # type: ignore[attr-defined]  # missing from django-stubs
            elif isinstance(field, str):
                name = field.removeprefix("-")
            else:
                continue
            if name not in model_admin.bidi_arabic_ordering or not isinstance(
                model_admin._bidi_model_field(name), (models.CharField, models.TextField)
            ):
                continue
            key = arabic_sort_expression(name)
            if isinstance(term, models.OrderBy):
                # Keep descending and explicit NULL placement on F() orderings.
                order_by = term.copy()
                order_by.expression = key
                ordering[i] = order_by
            else:
                ordering[i] = key.desc() if isinstance(term, str) and term.startswith("-") else key
            changed = True
        # Even a unique text column may cease to be unique once folded.
        if changed and "-pk" not in ordering and "pk" not in ordering:
            ordering.append("-pk")
        return ordering


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
    in ``list_editable`` are not wrapped for display. Numeric and date/time
    form fields accept Arabic-Indic and Persian digits in any UI language.

    The delete confirmation page, the plain-text entries of
    ``get_deleted_objects`` (on the delete and delete-selected confirmation
    pages) and the delete success message wrap the object's ``__str__`` in an
    isolate as well, following the same changelist switch.  So do the "added"
    and "changed" success messages when they print the name as plain text,
    which Django does for a user without change permission; linked names are
    left to ``rtl-admin.css``.

    Class-level knobs:

    ``bidi_normalize_input``
        ``True``/``False`` to override ``RTL_ADMIN["NORMALIZE_INPUT_DIGITS"]``
        when cleaning numeric and Gregorian date/time form fields.
    ``bidi_local_digits``
        ``True``/``False`` to override
        ``RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"]`` when rendering numeric and
        temporal model fields on the changelist.
    ``bidi_arabic_ordering``
        Text fields to sort by their folded Arabic keys on the changelist.
        The default is empty; ``RTL_ADMIN["ARABIC_ORDERING"] = False`` disables it.
    ``bidi_fold_search``
        ``True``/``False`` to override ``RTL_ADMIN["FOLD_ARABIC_SEARCH"]``
        when searching text fields on the changelist or in autocompletes.
    ``bidi_transliterate_slugs``
        ``True``/``False`` to override ``RTL_ADMIN["TRANSLITERATE_SLUGS"]``
        for prepopulated slug fields on add forms and new inline rows.
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

    bidi_normalize_input: bool | None = None
    bidi_local_digits: bool | None = None
    bidi_fold_search: bool | None = None
    bidi_transliterate_slugs: bool | None = None
    bidi_arabic_ordering: tuple[str, ...] = ()
    bidi_isolate_changelist: bool | None = None
    bidi_isolate_readonly: bool | None = None
    bidi_isolate_fields: tuple[str, ...] | None = None
    bidi_isolate_exclude: tuple[str | Callable[[Any], object], ...] = ()
    bidi_isolation_direction: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._bidi_wrappers: dict[str, _DisplayWrapper] = {}
        self._bidi_digit_wrappers: dict[str, _DisplayWrapper] = {}

    # -- configuration -----------------------------------------------------

    def bidi_isolation_enabled(self, request: HttpRequest | None = None) -> bool:
        if self.bidi_isolate_changelist is None:
            return bool(rtl_settings.ISOLATE_CHANGELIST)
        return bool(self.bidi_isolate_changelist)

    def bidi_readonly_isolation_enabled(self, request: HttpRequest | None = None) -> bool:
        if self.bidi_isolate_readonly is None:
            return bool(rtl_settings.ISOLATE_READONLY_FIELDS)
        return bool(self.bidi_isolate_readonly)

    def _bidi_local_digits_enabled(self) -> bool:
        if self.bidi_local_digits is None:
            return rtl_settings.LOCALIZE_CHANGELIST_DIGITS
        return bool(self.bidi_local_digits)

    def _bidi_should_localize_digits(self, name: str) -> bool:
        if name in (getattr(self, "list_editable", ()) or ()):
            return False
        return _is_local_digit_field(self._bidi_model_field(name))

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

    # -- ModelAdmin and InlineModelAdmin form hooks ------------------------

    def _bidi_slug_prepopulation_enabled(self) -> bool:
        enabled = self.bidi_transliterate_slugs
        if enabled is None:
            enabled = rtl_settings.TRANSLITERATE_SLUGS
        return enabled

    @property
    def media(self) -> forms.Media:
        media = super().media
        if self.prepopulated_fields and self._bidi_slug_prepopulation_enabled():
            # ModelAdmin supplies the stock plugin even for inline-only
            # prepopulation. Express the order in both model and inline media.
            media += forms.Media(js=[_PREPOPULATE_SCRIPT, _SLUG_SCRIPT])
        return media

    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> type[forms.ModelForm[Any]]:
        form = super().get_form(request, obj, change=change, **kwargs)
        if self._bidi_slug_prepopulation_enabled():
            return _slug_form(
                form,
                self.get_prepopulated_fields(request, obj),
                self.opts,
                # Media is otherwise request-independent, so the wrapped form
                # supplies the script when only the request-aware hook adds targets.
                needs_media=not self.prepopulated_fields,
            )
        return form

    def get_formset(
        self, request: HttpRequest, obj: Any = None, **kwargs: Any
    ) -> type[BaseInlineFormSet[Any, Any]]:
        formset: type[BaseInlineFormSet[Any, Any]] = super().get_formset(  # type: ignore[misc]
            request, obj, **kwargs
        )
        if self._bidi_slug_prepopulation_enabled():
            formset.form = _slug_form(
                formset.form,
                self.get_prepopulated_fields(request, obj),
                self.opts,
                needs_media=not self.prepopulated_fields,
            )
        return formset

    # -- ModelAdmin hooks --------------------------------------------------

    def get_changelist(self, request: HttpRequest, **kwargs: Any) -> type[ChangeList]:
        base = super().get_changelist(request, **kwargs)
        if not self.bidi_arabic_ordering or not rtl_settings.ARABIC_ORDERING:
            return base
        if base is ChangeList:
            return _ArabicOrderingChangeList
        # Compose with (rather than replace) a project's custom ChangeList.
        return type(f"ArabicOrdered{base.__name__}", (_ArabicOrderingChangeList, base), {})

    def formfield_for_dbfield(
        self, db_field: Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        enabled = self.bidi_normalize_input
        if enabled is None:
            enabled = rtl_settings.NORMALIZE_INPUT_DIGITS
        if enabled and field is not None:
            _enable_input_normalization(field)
        return field

    def get_search_results(
        self, request: HttpRequest, queryset: QuerySet[Any], search_term: str
    ) -> tuple[QuerySet[Any], bool]:
        base_queryset = queryset
        results, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        enabled = self.bidi_fold_search
        if enabled is None:
            enabled = rtl_settings.FOLD_ARABIC_SEARCH
        if not enabled or not search_term:
            return results, may_have_duplicates

        if not _has_arabic_search_chars(search_term):
            return results, may_have_duplicates

        search_fields = self.get_search_fields(request)
        if not search_fields:
            return results, may_have_duplicates

        opts = base_queryset.model._meta
        stock_specs: list[tuple[str, Field[Any, Any] | None]] = []
        regex_specs: list[tuple[str, str]] = []
        for field in search_fields:
            stock_spec, regex_spec = _classify_search_field(opts, str(field))
            stock_specs.append(stock_spec)
            if regex_spec is not None:
                regex_specs.append(regex_spec)
        if not regex_specs:
            return results, may_have_duplicates

        bits = [
            unescape_string_literal(raw_bit)
            if raw_bit.startswith(('"', "'")) and raw_bit[0] == raw_bit[-1]
            else raw_bit
            for raw_bit in smart_split(search_term)
        ]

        if len(bits) == 1:
            single_pattern = arabic_search_regex(bits[0])
            folded_query = reduce(
                or_,
                (
                    models.Q(**{lookup: _anchor_search_regex(single_pattern, mode)})
                    for lookup, mode in regex_specs
                ),
            )
        else:
            term_queries: list[models.Q] = []
            for bit in bits:
                clauses: list[models.Q] = []
                for lookup, validate_field in stock_specs:
                    if validate_field is not None:
                        valid, value = _coerce_exact_search_value(validate_field, bit)
                        if not valid:
                            continue
                    else:
                        value = bit
                    clauses.append(models.Q(**{lookup: value}))
                if _has_foldable_search_chars(bit):
                    term_pattern = arabic_search_regex(bit)
                    clauses.extend(
                        models.Q(**{lookup: _anchor_search_regex(term_pattern, mode)})
                        for lookup, mode in regex_specs
                    )
                term_queries.append(reduce(or_, clauses))
            folded_query = reduce(and_, term_queries)

        folded_base = base_queryset.distinct() if results.query.distinct else base_queryset
        folded_results = folded_base.filter(folded_query)
        may_have_duplicates |= any(
            lookup_spawns_duplicates(self.opts, lookup) for lookup, _ in regex_specs
        )
        return results | folded_results, may_have_duplicates

    def get_list_display(self, request: HttpRequest) -> _ListDisplay:
        return self._bidi_map_entries(request, super().get_list_display(request))

    def get_list_display_links(
        self, request: HttpRequest, list_display: _ListDisplay
    ) -> _ListDisplay:
        links = super().get_list_display_links(request, list_display)
        if links is None:
            return links
        return self._bidi_map_entries(request, links)

    def get_sortable_by(self, request: HttpRequest) -> _ListDisplay:
        sortable = super().get_sortable_by(request)
        if sortable is None:
            return sortable
        return self._bidi_map_entries(request, sortable)

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

    def get_deleted_objects(
        self, objs: Sequence[Any] | QuerySet[Any], request: HttpRequest
    ) -> tuple[list[Any], dict[str, int], set[str], list[Any]]:
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        if not self.bidi_isolation_enabled(request):
            return deleted_objects, model_count, perms_needed, protected
        return (
            [_isolate_deleted_entry(item) for item in deleted_objects],
            model_count,
            perms_needed,
            [_isolate_deleted_entry(item) for item in protected],
        )

    def render_delete_form(self, request: HttpRequest, context: dict[str, Any]) -> HttpResponse:
        obj = context.get("object")
        if obj is not None and self.bidi_isolation_enabled(request):
            obj_display = str(obj)
            context["object"] = _BidiDeleteObjectProxy(obj, obj_display)
            # Django 6.1 renders the confirmation question from a precomputed
            # display string instead of ``object``.  Isolate the value Django
            # already computed, keeping its "-" placeholder for empty and
            # whitespace-only names untouched.
            if "escaped_object" in context and obj_display.strip():
                context["escaped_object"] = isolate(context["escaped_object"])
        return super().render_delete_form(request, context)

    def response_delete(self, request: HttpRequest, obj_display: str, obj_id: Any) -> HttpResponse:
        if self.bidi_isolation_enabled(request):
            obj_display = isolate(obj_display)
        return super().response_delete(request, obj_display, obj_id)

    def response_add(
        self, request: HttpRequest, obj: Any, post_url_continue: str | None = None
    ) -> HttpResponse:
        with self._bidi_plain_object_name(request, obj, obj._meta.verbose_name):
            return super().response_add(request, obj, post_url_continue)

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        # Django 4.2 to 6.1 link the name here whatever the permission, so
        # their message is never rewritten; this covers a base class (or a
        # later Django) that prints the name as plain text instead.
        with self._bidi_plain_object_name(request, obj, self.opts.verbose_name):
            return super().response_change(request, obj)

    def message_user(
        self,
        request: HttpRequest,
        message: Any,
        level: int | str = messages.INFO,
        extra_tags: str = "",
        fail_silently: bool = False,
    ) -> None:
        pending = getattr(request, _PLAIN_NAME_ATTR, None)
        if pending is not None:
            message = _isolate_plain_object_name(message, *pending)
        super().message_user(request, message, level, extra_tags, fail_silently)

    # -- internals ---------------------------------------------------------

    @contextmanager
    def _bidi_plain_object_name(
        self, request: HttpRequest, obj: Any, verbose_name: Any
    ) -> Iterator[None]:
        """Let ``message_user`` isolate the plain-text name of ``obj``.

        Django builds the success message inside ``response_add`` and
        ``response_change`` and only hands it over through ``message_user``,
        so the name is passed to that hook on the request for the duration of
        the call.  The object itself goes on to Django untouched: the
        redirect, the popup response and the linked message are its own.

        Nothing is passed on for a popup (it shows no message), for a user
        with change permission (Django links the name) or for an empty or
        whitespace-only name, which renders as stock.
        """
        obj_display = ""
        if (
            self.bidi_isolation_enabled(request)
            and IS_POPUP_VAR not in request.POST
            and not self.has_change_permission(request, obj)
        ):
            obj_display = str(obj)
        if not obj_display.strip():
            yield
            return
        setattr(request, _PLAIN_NAME_ATTR, (verbose_name, obj_display))
        try:
            yield
        finally:
            request.__dict__.pop(_PLAIN_NAME_ATTR, None)

    def _bidi_map_entries(self, request: HttpRequest, entries: _ListDisplay) -> _ListDisplay:
        isolate_enabled = self.bidi_isolation_enabled(request)
        digits_enabled = self._bidi_local_digits_enabled() and numbering_system() != "latn"
        if not isolate_enabled and not digits_enabled:
            return entries
        return tuple(
            self._bidi_entry(
                entry,
                isolate_enabled=isolate_enabled,
                digits_enabled=digits_enabled,
            )
            for entry in entries
        )

    def _bidi_entry(
        self,
        entry: _Display,
        *,
        isolate_enabled: bool = True,
        digits_enabled: bool = False,
    ) -> _Display:
        """Map one ``list_display`` entry to its changelist wrapper."""
        if not isinstance(entry, str):
            return entry
        should_isolate = isolate_enabled and self._bidi_should_isolate(entry)
        should_localize = digits_enabled and self._bidi_should_localize_digits(entry)
        if not should_isolate and not should_localize:
            return entry
        cache = self._bidi_wrappers if should_isolate else self._bidi_digit_wrappers
        try:
            return cache[entry]
        except KeyError:
            pass
        wrapper = self._make_bidi_wrapper(entry, isolate_cell=should_isolate)
        if wrapper is None:
            return entry
        cache[entry] = wrapper
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

    def _make_bidi_wrapper(self, name: str, *, isolate_cell: bool = True) -> _DisplayWrapper | None:
        field = self._bidi_model_field(name)
        if field is not None and field.get_internal_type() in _SKIPPED_FIELD_TYPES:
            return None

        original = getattr(self, name, None) or getattr(self.model, name, None)
        if getattr(original, "boolean", False):
            return None

        model_admin = self
        direction = self.bidi_isolation_direction
        localize_digits = _is_local_digit_field(field)
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
            if localize_digits and model_admin._bidi_local_digits_enabled():
                text = _localize_cell_digits(text)
            if not isolate_cell:
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
