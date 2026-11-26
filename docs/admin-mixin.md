---
title: BidiSafeAdminMixin | django-rtl-admin
description: Add opt-in Unicode isolation to Django changelist cells and change-form read-only fields with allowlists, exclusions, direction controls, sorting guidance, and safe rendering behavior.
---

# BidiSafeAdminMixin

`BidiSafeAdminMixin` adds Unicode isolates around eligible changelist cells and
embedded opposite-direction runs inside change-form `readonly_fields`, and around
the object's name on the delete confirmation page and in the messages that print
it as plain text.
Use it for mixed-direction names, identifiers, emails, paths, and other data
that should not disturb surrounding text. Isolation affects presentation, not
stored model values. The mixin also accepts Arabic-Indic and Persian digits in
[numeric and date input](#numeric-and-date-input), optionally rewrites numeric
and temporal cells on the changelist via
[changelist digit localization](#changelist-digit-localization), and folds
equivalent Arabic letter forms, diacritics, tatweel, and digits in
[admin search](#arabic-search-folding), in any UI language. It can also
[prepopulate slugs from Arabic-script titles](#arabic-slug-prepopulation).

## Add it to a ModelAdmin

Import from the package root and put the mixin **before** `admin.ModelAdmin`:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    readonly_fields = ("archive_note",)
```

This example assumes `Book` has `title`, `isbn`, `published_on`, and
`archive_note` fields.
Importing directly from the implementation module is also supported:

```python
from django_rtl_admin.mixins import BidiSafeAdminMixin
```

No isolation is automatically installed on a plain `ModelAdmin`. For the admin
shell and CSS setup, follow [Installation](installation.md) and
[Quick start](quick-start.md).

## Per-admin configuration

| Attribute | Default | Effect |
| --- | --- | --- |
| `bidi_normalize_input` | `None` | Inherit `RTL_ADMIN["NORMALIZE_INPUT_DIGITS"]`; `True` or `False` overrides input normalization for this admin. |
| `bidi_local_digits` | `None` | Inherit `RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"]`; `True` or `False` overrides [changelist digit localization](#changelist-digit-localization) for this admin. |
| `bidi_fold_search` | `None` | Inherit `RTL_ADMIN["FOLD_ARABIC_SEARCH"]`; `True` or `False` overrides [Arabic search folding](#arabic-search-folding) for this admin. |
| `bidi_transliterate_slugs` | `None` | Inherit `RTL_ADMIN["TRANSLITERATE_SLUGS"]`; `True` or `False` overrides [Arabic slug prepopulation](#arabic-slug-prepopulation) for this admin or inline. |
| `bidi_isolate_changelist` | `None` | Follow `RTL_ADMIN["ISOLATE_CHANGELIST"]`; `True` or `False` overrides it for this admin. The same switch covers [object names](#object-names-in-messages-and-on-the-delete-page) on the delete page and in messages. |
| `bidi_isolate_readonly` | `None` | Follow `RTL_ADMIN["ISOLATE_READONLY_FIELDS"]`; `True` or `False` overrides it for this admin. |
| `bidi_isolate_fields` | `None` | Consider all eligible string `list_display` entries; otherwise isolate only names in this iterable on the changelist. An empty tuple isolates none. |
| `bidi_isolate_exclude` | `()` | Leave these `list_display` or `readonly_fields` entries unchanged, even if they are in the changelist allowlist. |
| `bidi_isolation_direction` | `None` | Follow `RTL_ADMIN["ISOLATION_DIRECTION"]` for changelist cells; use `"auto"`, `"ltr"`, or `"rtl"` to override it. |

For example, isolate only ISBN values in the changelist and force their direction to LTR:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

Use this as an alternative to the first registration, not an additional one.
There is no built-in per-field direction mapping: the direction attribute applies
to every changelist value the mixin wraps. For other policies, exclude a column and call
`mark_isolated(value, direction="ltr")` in its display method yourself.

Set `bidi_isolate_changelist=False` or `bidi_isolate_readonly=False` to disable
either kind of isolation for one admin. A local `True` can re-enable it even
when the corresponding global switch is off. Global defaults and independent CSS
protection are described in [Configuration](configuration.md).

## Numeric and date input

A price submitted as `١٬٢٣٤٫٥٠` is parsed as `1234.50` even in an English
admin. The mixin calls [`normalize_numeric_input`](api.md#normalizing-numeric-input)
in `to_python()` on admin-generated `IntegerField`, `DecimalField`, `FloatField`,
`DateField`, `TimeField`, and `DateTimeField` form fields, including the date and
time components of `SplitDateTimeField`. This applies on add and change forms,
for `list_editable` columns, and in inlines **when the inline class itself uses
the mixin**. Text fields such as an ISBN are not normalized.

`normalize_numeric_input(value, *, decimal_separator=".")` returns non-strings
unchanged. In text, it maps Arabic-Indic and Persian digits to ASCII, `−` to
`-`, and `٫` to the decimal separator. It strips `٬`, bidi controls, and outer
whitespace. Inside the text, it removes nonbreaking, narrow nonbreaking, and
thin spaces only between digits. It leaves letters and other punctuation alone.

For localized numeric fields, the mixin maps `٫` to Django's active decimal
separator rather than forcing a dot. Django still parses and validates the
result using the field's usual rules. Only the value passed to the parser
changes: bound form data retains the original input if validation fails.

Dates must use the Gregorian calendar and a format the field accepts. For
example, `۲۰۲۴-۰۳-۰۵` becomes `2024-03-05`. Django does **not** convert dates
from the Jalali (Solar Hijri) or Islamic (lunar Hijri) calendar.

## Changelist digit localization

Enable `RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"] = True` globally or
`bidi_local_digits = True` on a single `ModelAdmin` to rewrite digits in
changelist cells of eligible numeric and temporal model fields for the active
language (`bidi_local_digits = False` disables it on one admin when the global
setting is `True`; plain `ModelAdmin` classes are unaffected):

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on", "price")
    bidi_local_digits = True
```

When enabled, the mixin rewrites changelist cells of `IntegerField` (including
integer and auto-field subclasses), `DecimalField`, `FloatField`, `DateField`,
`DateTimeField`, `TimeField`, and `DurationField` model fields—including across
related lookups on Django 5.1+—with
[`transliterate_digits(text, numbering_system())`](api.md#locale-aware-formatting)
before applying Unicode isolation. Only digit characters change and **separators
stay as Django renders them** (for example, `1234,50` in `ar-eg` becomes
`١٢٣٤,٥٠` and `1234.50` in `fa` becomes `۱۲۳۴.۵۰`). Locales whose numbering
system is `latn` (`en`, `ar`, `he`) remain byte-identical, and
`RTL_ADMIN["NUMERALS"]` (`"latn"`, `"arab"`, or `"arabext"`) forces the
numbering system.

`CharField` and `TextField` columns (such as an ISBN or title), `ForeignKey`
columns, fields with `choices`, boolean icons, and callable or property columns
are left untouched, as are `None` and `empty_value_display`, and characters
inside HTML tags are never rewritten. Sort links, `admin_order_field`, and
change-form links stay intact, and digit localization continues to work when
`ISOLATE_CHANGELIST = False` or `bidi_isolate_changelist = False`.
`list_editable` inputs, filters (`list_filter` and `date_hierarchy`), the
paginator, and the action counter are not covered and stay unchanged.

## Arabic search folding

Stock admin search compares raw Unicode code points, so `احمد` misses `أحمد`,
`محمد` misses `مُحَمَّدٌ` or `مـحمد`, `مدرسه` misses `مدرسة`, `علي` misses `على`
or `علی`, `كتاب` misses `کتاب`, and `٢٦٢` or `۲۶۲` misses `262`. On a
mixin-enabled admin, `get_search_results()` keeps `super().get_search_results()`
and, for each `smart_split()` term containing an Arabic letter or an
Arabic-Indic or Persian digit, ORs in `field__iregex` built with
[`arabic_search_regex`](api.md#arabic-search-folding) across eligible text
`search_fields`.

Folding covers `CharField` and `TextField` columns (including subclasses such as
`EmailField`, `SlugField`, and `URLField`, as well as forward and reverse
related paths), honours `"^"` (anchored at start) and `"="` (anchored at both
ends), skips `"@"` full-text lookups and non-text fields, ANDs multiple search
terms together, and updates `may_have_duplicates` when a regex lookup traverses
a multi-valued relation. Django's `AutocompleteJsonView` delegates to the target
admin's `get_search_results()`, so `autocomplete_fields` pointing to a
mixin-enabled admin automatically gain the same folding.

Queries containing only ASCII or Hebrew characters, or terms that strip down to
empty (such as lone harakat, tatweel, or bidi controls), leave stock search
results and SQL untouched. Disable folding globally with
`RTL_ADMIN["FOLD_ARABIC_SEARCH"] = False` or on a single admin with
`bidi_fold_search = False`; set `bidi_fold_search = True` to keep folding on one
admin when the global setting is `False`.

## Arabic slug prepopulation

Use Django's `prepopulated_fields` to choose the target `SlugField` and its
source fields. An inline must use `BidiSafeAdminMixin` itself, even when its
parent admin also uses the mixin:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book, Chapter


class ChapterInline(BidiSafeAdminMixin, admin.TabularInline):
    model = Chapter
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title", "subtitle")}
    inlines = [ChapterInline]
```

This is an alternative to the earlier registration. It assumes `Book` has
`title`, `subtitle`, and `slug` fields and `Chapter` has `title`, `slug`, and a
foreign key to `Book`. Multiple source values are joined with spaces in the
configured order before slugification. For example, a title of `مُقَدِّمَة` and
a subtitle of `١٢` produce `mqdmh-12` on an ASCII `SlugField` or `مقدمة-12`
when `allow_unicode=True`. The generated slug also respects the field's length
limit; see [`arabic_slugify`](api.md#arabic-slugify) for the truncation rules.

The browser preview and server-side fill apply only to add forms and new inline
rows, including new rows on a parent's change form. For those new records, the
server fills a blank slug before validation even without JavaScript. It never
replaces a nonblank slug. On a change form for an existing record or inline row,
the mixin does not fill an emptied slug: Django still rejects it if the field is
required. Generated slugs must pass normal Django field, model, and uniqueness
validation. Enter a different slug if validation reports a collision; the mixin
does not add a suffix.

To leave prepopulation to Django, set `RTL_ADMIN["TRANSLITERATE_SLUGS"] = False`
globally or `bidi_transliterate_slugs = False` on the relevant admin or inline.
Set `bidi_transliterate_slugs = True` on a class to enable it there even if the
global setting is off.

## Named fields and display methods

Only string entries in `list_display` are candidates. Direct model field names,
named model/admin display methods and, on Django 5.1+,
[related lookups](#related-lookups-and-sorting) are supported. Callable objects
placed directly in `list_display` pass through unchanged; use the method's name
to opt in:

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
model fields, named display methods with explicit ordering metadata and, on
Django 5.1+, related lookups. Changelist links and `sortable_by` entries are mapped to
the same cached wrapper objects; this mapping does not itself make a column sortable.

The following entries are not wrapped for display:

- Names in `bidi_isolate_exclude` or outside a non-`None` allowlist.
- Names in `list_editable`, even when explicitly allowlisted.
- `BooleanField`/`NullBooleanField` columns, including related lookups that end
  in one, and named attributes marked `boolean=True`, preserving boolean icons.
- Non-string callable entries.

Numeric fields are not generally skipped. Empty display values, including the
admin's empty-value placeholder, are returned without isolate characters.
Keep normal Django `list_display`, sorting, and `list_editable` rules in place;
the mixin does not make otherwise-invalid admin configuration valid.

### Related lookups and sorting

Django 5.1 accepts related lookups such as `publisher__name_en` in
`list_display`. On Django 5.1 and later the mixin resolves the lookup with
Django's `get_fields_from_path()`, sets the wrapper's `admin_order_field` to the
lookup itself so the column keeps its sort link and `?o=` ordering, and isolates
the final field's display value:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher__name_en")
```

A missing related object renders the empty-value placeholder without isolates.
A lookup that ends in a `BooleanField` or `NullBooleanField`, such as
`publisher__is_active`, is left to Django unchanged. Exclude a lookup with
`bidi_isolate_exclude` to opt it out like any other column.

Django 4.2 and 5.0 do not support related lookups in `list_display` (the admin
rejects them), and the mixin does not resolve them there either. On those
versions use a named display method with explicit ordering, which keeps both
isolation and sorting on every supported Django:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher_name")

    @admin.display(description="Publisher", ordering="publisher__name_en")
    def publisher_name(self, obj):
        return obj.publisher.name_en if obj.publisher is not None else None
```

These are alternative definitions for a `Book` with a `publisher` foreign key
whose related model has `name_en` and `is_active` fields. Register only the
chosen definition. If you use an isolation allowlist, include the lookup or
`publisher_name` to wrap it.

## Read-only fields on the change form

On the change form (and in view-only mode and inlines that also mix in
`BidiSafeAdminMixin`), `render_change_form()` wraps `context["adminform"]` so
each eligible `readonly_fields` value has its embedded opposite-direction runs
isolated with `mark_isolated_runs()` without overriding
`admin/includes/fieldset.html`. Field labels, model/form help text, and
`field-<name>` CSS classes match the stock admin.

Because `.rtl-admin div.readonly` has `unicode-bidi: plaintext`, the browser
resolves each paragraph line's base direction from its first strong character in
both RTL and LTR admins. The mixin uses that same per-line first-strong
direction (falling back to the active UI direction on neutral-only lines) when
calling `mark_isolated_runs()`, so an Arabic note such as
`نُقل الملف إلى /srv/archive/2024-03-05` keeps `/srv/archive/2024-03-05`
isolated in `LRI...PDI` whether the admin UI is `ar-eg` or `en`.

Model fields, named admin/model methods, and callables in `readonly_fields` are
all supported. Boolean fields and `boolean=True` display methods, empty-value
placeholders, read-only form widgets, and values that are already `SafeString`
(including `ForeignKey` / `OneToOneField` admin links) are left untouched. Exclude
a field name or callable (by object or `__name__`) with `bidi_isolate_exclude`,
disable per admin with `bidi_isolate_readonly = False`, or disable globally with
`RTL_ADMIN["ISOLATE_READONLY_FIELDS"] = False`.

## Object names in messages and on the delete page

The admin also quotes an object's `__str__` inside sentences and headings. In an
RTL admin, an identifier such as `978-0-262-03561-3` or `v1.2.3` between those
quotes is reordered unless it is isolated. The mixin handles the places where
Django prints the name as plain text; the package stylesheet handles the places
where the name has an element of its own:

| Where the name appears | Isolated by | Switch |
| --- | --- | --- |
| Delete confirmation question and breadcrumb | Mixin, `render_delete_form()` | `ISOLATE_CHANGELIST` or `bidi_isolate_changelist` |
| Plain-text related and protected entries on the delete and delete-selected pages | Mixin, `get_deleted_objects()` | `ISOLATE_CHANGELIST` or `bidi_isolate_changelist` |
| Delete success message | Mixin, `response_delete()` | `ISOLATE_CHANGELIST` or `bidi_isolate_changelist` |
| "Added" message without change permission (plain text) | Mixin, `response_add()` | `ISOLATE_CHANGELIST` or `bidi_isolate_changelist` |
| "Added" and "changed" messages with a linked name | Stylesheet | `ISOLATE_TABLE_CELLS` |
| Change-form subtitle | Stylesheet | `ISOLATE_TABLE_CELLS` |
| Object links in the lists on the delete and delete-selected confirmation pages | Stylesheet | `ISOLATE_TABLE_CELLS` |

The mixin wraps the whole name with `isolate()`, in the direction set by
`RTL_ADMIN["ISOLATION_DIRECTION"]`. The per-admin `bidi_isolation_direction`,
`bidi_isolate_fields` and `bidi_isolate_exclude` attributes do not apply to
object names. Django escapes the name afterwards as it always does, so HTML in
`__str__` stays escaped, and existing `Bidi_Control` characters are stripped
from the name first. On the delete confirmation page and in the "added" message,
an empty or whitespace-only name renders exactly as in the stock admin.

The stylesheet rules insert no characters. They need the package CSS
(`ENABLE_CSS`) and follow the stock admin markup:

```css
.rtl-admin--isolate-cells ul.messagelist li a,
.rtl-admin--isolate-cells #content > h2,
.rtl-admin--isolate-cells #content > .titles-and-tools > .titles > h2,
.rtl-admin--isolate-cells.delete-confirmation #content ul li a {
  unicode-bidi: isolate;
}
```

### Delete confirmation page and message

`render_delete_form()` replaces `context["object"]` with a thin proxy whose
`__str__` returns the isolated name and which delegates every other attribute to
the real object, so the breadcrumb still links to the object's change page. The
breadcrumb's `truncatewords:"18"` cannot cut off the closing PDI: in a longer
name the isolate is closed after the 18th word and reopened for the rest. Django
6.1 renders the question from a precomputed `escaped_object`, and the mixin
isolates that value as well.

`response_delete()` passes the isolated name on to Django, which builds the
"deleted successfully" message from it. The `LogEntry` keeps the plain name.

The lists of objects to be deleted and of protected objects on this page, and on
the confirmation page of the "delete selected" action, come from Django's
`get_deleted_objects()`. Linked entries (`SafeString` values with an admin link)
stay byte-identical and are isolated by the stylesheet. Plain-text entries—such
as a related object without an admin page of its own, which Django formats as
`<Verbose name>: <str(obj)>`—have the name after the first `": "` wrapped with
`isolate()` as a plain string so Django still escapes any HTML in it, leaving
list nesting, `model_count` and `perms_needed` unchanged.

### Add and change messages

When the user may change the object, Django links its name in the success
message. The stylesheet isolates that link, and the mixin leaves the message
exactly as Django built it.

A user without change permission gets the "added" message with the name as plain
text, which no selector can reach, so the mixin wraps the name with `isolate()`,
whichever save button was used.
Only the message Django itself builds is rewritten. The redirect, the popup
response of a related-object window, the `LogEntry` and any message your own code
sends with `message_user()` stay exactly as they are.

On Django 4.2 to 6.1, `response_change()` links the name whatever the user's
permissions, so the "changed" message has no plain-text form and is never
rewritten. The mixin's `response_change()` only acts when a base class sends
Django's "changed" message with a plain name instead.

### Change-form subtitle

The change form, also in view-only mode, repeats the object's name in a subtitle
`<h2>` under the page title. Up to Django 6.0 that heading is a child of
`#content`; Django 6.1 moved it into `.titles-and-tools > .titles`. The
stylesheet has a rule for each. The history page has no subtitle: its name is
part of the `<h1>` sentence, which is isolated only as a whole.

## Escaping and formatting

Changelist wrappers call Django's `display_for_field` or `display_for_value`, then
`mark_isolated`; read-only field wrappers isolate embedded runs per paragraph line
with `mark_isolated_runs` and join lines with `<br>`, matching Django's
`linebreaksbr`. Ordinary HTML-looking text is escaped, and both helpers strip
any existing Unicode `Bidi_Control` characters before wrapping so embedded `PDI`
or directional override characters cannot break out of an isolate. Values
already marked safe, or exposing `__html__`, are not re-escaped or
HTML-sanitized (and `mark_isolated_runs` leaves already-safe HTML untouched).
Build custom HTML with Django's `format_html`, not by marking untrusted text
safe.

Because `mark_isolated` strips existing `Bidi_Control` characters before
wrapping, a column whose display method calls `mark_isolated_runs` (or sets an
explicit `mark_isolated` direction that differs from the admin's default) will
have its inner isolates replaced unless you exclude that named column with
`bidi_isolate_exclude` or place the callable directly in `list_display`.
Unicode controls can survive copy/paste; apply them when rendering rather than
saving them into identifiers.

Even with [changelist digit localization](#changelist-digit-localization)
enabled, the mixin only transliterates digits on Django's rendered field text
and does not automatically invoke this package's Babel or CLDR separator/currency
formatters. Call `format_number` or `format_currency` in a named display method
when locale-specific separators or currency patterns are required, then let the
mixin isolate its result. See the [Python API](api.md) or
[template filters](template-tags.md) for explicit formatting.

## Scope and customization

The mixin hooks into changelist display methods, `get_search_results` for
changelist and autocomplete search, `render_change_form` for
read-only fields, and `get_deleted_objects`, `render_delete_form`,
`response_delete`, `response_add`, `response_change` and `message_user` for
object names. With input normalization enabled, number inputs use `type="text"`
with `inputmode="numeric"` or `inputmode="decimal"`. This lets the browser
suggest a numeric keyboard without clearing a localized value on entry or
redisplay, as `type="number"` can. Django still validates the field on the
server; other widgets stay as configured. Exports are unchanged. CSS isolation
remains independent, including on columns and fields the mixin skips.

Keep attributes stable after the admin starts serving requests: wrappers are
cached per admin instance, and explicit per-admin direction is captured when
created. Labels and ordering metadata are also established at that point.
No general copying of all custom callable or property metadata is promised;
verify specialized columns against your Django version.

Override `bidi_isolation_enabled(request=None)` or
`bidi_readonly_isolation_enabled(request=None)` for request-dependent
enablement; their default implementations ignore the request. Preserve
cooperative `super()` calls when overriding initialization or the standard
`ModelAdmin` hooks below. The generated reference lists their signatures without
repeating the class usage prose. In them, `_ListDisplay` is a list or tuple of
`list_display` entries (field names or callables), the same shape django-stubs
gives Django's own hooks.

::: django_rtl_admin.mixins.BidiSafeAdminMixin
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      show_bases: false
      show_source: false
      show_if_no_docstring: true
      show_docstring_description: false
      show_docstring_attributes: false
      show_docstring_examples: false
      members:
        - bidi_isolation_enabled
        - bidi_readonly_isolation_enabled
        - formfield_for_dbfield
        - get_search_results
        - get_list_display
        - get_list_display_links
        - get_sortable_by
        - render_change_form
        - get_deleted_objects
        - render_delete_form
        - response_delete
        - response_add
        - response_change
        - message_user
