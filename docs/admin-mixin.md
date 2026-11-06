---
title: BidiSafeAdminMixin | django-rtl-admin
description: Add opt-in Unicode isolation to Django changelist values with field allowlists, exclusions, direction controls, sorting guidance, and safe rendering behavior.
---

# BidiSafeAdminMixin

`BidiSafeAdminMixin` adds Unicode isolates around eligible changelist values.
Use it for mixed-direction names, identifiers, emails, paths, and other data
that should not disturb surrounding text. It affects presentation, not stored
model values, and works in both LTR and RTL admins.

## Add it to a ModelAdmin

Import from the package root and put the mixin **before** `admin.ModelAdmin`:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
```

This example assumes `Book` has `title`, `isbn`, and `published_on` fields.
Importing directly from the implementation module is also supported:

```python
from django_rtl_admin.mixins import BidiSafeAdminMixin
```

No isolation is automatically installed on a plain `ModelAdmin`. For the admin
shell and CSS setup, follow [Installation](installation.md) and
[Quick start](quick-start.md).

## Per-admin configuration

These are all four supported configuration attributes:

| Attribute | Default | Effect |
| --- | --- | --- |
| `bidi_isolate_changelist` | `None` | Follow `RTL_ADMIN["ISOLATE_CHANGELIST"]`; `True` or `False` overrides it for this admin. |
| `bidi_isolate_fields` | `None` | Consider all eligible string entries; otherwise isolate only names in this iterable. An empty tuple isolates none. |
| `bidi_isolate_exclude` | `()` | Leave these named entries unchanged, even if they are in the allowlist. |
| `bidi_isolation_direction` | `None` | Follow `RTL_ADMIN["ISOLATION_DIRECTION"]`; use `"auto"`, `"ltr"`, or `"rtl"` to override it. |

For example, isolate only ISBN values and force their direction to LTR:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

Use this as an alternative to the first registration, not an additional one.
There is no built-in per-field direction mapping: the direction attribute applies
to every value the mixin wraps. For other policies, exclude a column and call
`mark_isolated(value, direction="ltr")` in its display method yourself.

Set `bidi_isolate_changelist=False` to disable the mixin for one admin. A local
`True` can re-enable it even when the global switch is off. Global defaults and
independent CSS protection are described in [Configuration](configuration.md).

## Named fields and display methods

Only string entries in `list_display` are candidates. Direct model field names and
named model/admin display methods are supported. Related lookups have a
[sorting limitation](#related-lookups-and-sorting). Callable objects placed directly
in `list_display` pass through unchanged; use the method's name to opt in:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "upper_title")

    @admin.display(description="Upper title", ordering="title")
    def upper_title(self, obj):
        return obj.title.upper()
```

This is another alternative admin definition for a `Book` with a `title` field.
Django still resolves each named entry and produces its normal display value.
The wrapper retains the column name and label. Sorting is preserved for direct
model fields and named display methods with explicit ordering metadata, but not
for raw related lookups. Changelist links and `sortable_by` entries are mapped to
the same cached wrapper objects; this mapping does not itself make a column sortable.

The following entries are left alone:

- Names in `bidi_isolate_exclude` or outside a non-`None` allowlist.
- Names in `list_editable`, even when explicitly allowlisted.
- `BooleanField`/`NullBooleanField` columns and named attributes marked
  `boolean=True`, preserving boolean icons.
- Non-string callable entries.

Numeric fields are not generally skipped. Empty display values, including the
admin's empty-value placeholder, are returned without isolate characters.
Keep normal Django `list_display`, sorting, and `list_editable` rules in place;
the mixin does not make otherwise-invalid admin configuration valid.

### Related lookups and sorting

A related lookup such as `publisher__name_en` in `list_display` **loses sorting
when wrapped**. `_bidi_model_field()` only resolves direct model fields and
returns `None` for this lookup. With no named method supplying ordering metadata,
`_bidi_order_field()` sets the wrapper's `admin_order_field` to `None`, so Django
cannot offer a sort link for that column.

Either leave the lookup out of the mixin's isolation allowlist or explicitly
exclude it, keeping Django's normal handling on versions that support related
lookups in `list_display`:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher__name_en")
    bidi_isolate_exclude = ("publisher__name_en",)
```

Alternatively, replace the lookup with a named display method and declare its
ordering explicitly. This keeps both isolation and sorting:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher_name")

    @admin.display(description="Publisher", ordering="publisher__name_en")
    def publisher_name(self, obj):
        return obj.publisher.name_en if obj.publisher is not None else None
```

These are alternative definitions for a `Book` with a `publisher` foreign key
whose related model has a `name_en` field. Register only the chosen definition.
If you use an isolation allowlist, include `publisher_name` to wrap the method.

## Escaping and formatting

Wrappers call Django's `display_for_field` or `display_for_value`, then
`mark_isolated`. Ordinary HTML-looking text is escaped before isolation.
Values already marked safe, or exposing `__html__`, are trusted rather than
sanitized. Build custom HTML with Django's `format_html`, not by marking
untrusted text safe.

Do not manually isolate a display result that the mixin will isolate again:
whole-value isolation is not idempotent. Either let the mixin handle the value,
exclude that named column, or provide an already-handled callable directly.
Unicode controls can survive copy/paste; apply them when rendering rather than
saving them into identifiers.

The mixin does not automatically use this package's Babel or numeral formatters.
Call `format_number` or `format_currency` in a named display method if required,
then let the mixin isolate its result. See the [Python API](api.md) or
[template filters](template-tags.md) for explicit formatting.

## Scope and customization

The mixin rewrites changelist display hooks only. It does not rewrite edit
widgets, all read-only fields, or exports. CSS isolation remains independent,
including on columns the mixin skips.

Keep attributes stable after the admin starts serving requests: wrappers are
cached per admin instance, and explicit per-admin direction is captured when
created. Labels and ordering metadata are also established at that point.
No general copying of all custom callable or property metadata is promised;
verify specialized columns against your Django version.

Override `bidi_isolation_enabled(request=None)` for request-dependent enablement;
its default implementation ignores the request. Preserve cooperative `super()`
calls when overriding initialization or the standard changelist hooks below.
The generated reference lists their signatures without repeating the class
usage prose.

::: django_rtl_admin.mixins.BidiSafeAdminMixin
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      show_source: false
      show_if_no_docstring: true
      show_docstring_description: false
      show_docstring_attributes: false
      show_docstring_examples: false
      members:
        - bidi_isolation_enabled
        - get_list_display
        - get_list_display_links
        - get_sortable_by
