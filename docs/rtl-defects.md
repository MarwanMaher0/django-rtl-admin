# Stock admin RTL defects

Django already supports right-to-left languages. Its admin sets the page direction
and loads RTL styles for recognized languages. `django-rtl-admin` supplements that
support with logical spacing rules, text-direction handling, and optional display
helpers; it does not introduce RTL support from scratch.

## Scope of this comparison

This page compares the package stylesheet with Django's **`stable/5.2.x` source**.
It describes matching selectors and declarations, not a fresh browser measurement
or a verification of every supported Django release. Desktop rules are the
baseline unless stated otherwise. Responsive styles, custom markup, browser bidi
behavior, and later Django versions can change the result.

The main package source is
`src/django_rtl_admin/static/django_rtl_admin/css/rtl-admin.css`. The stock sources
used for comparison are Django's
[base.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/base.css),
[rtl.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/rtl.css),
[forms.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/forms.css),
[widgets.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/widgets.css),
and [changelists.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/changelists.css).

The package loads its stylesheet after Django's styles in the `responsive`
template block. Follow [Installation](installation.md) if a project-level template
override prevents that integration.

## Concrete before and after

In RTL, inline-start is the right side and inline-end is the left side. The
following changes apply when the package CSS is enabled and the matching stock
markup is present. Source locations refer to `rtl-admin.css`.

| Element | Stock Django 5.2 RTL | Package behavior | Source lines |
| --- | --- | --- | --- |
| Object-tools Add/view-site icon | Icon remains on the right, with `padding-right: 26px`. | Icon moves to `left 7px center`; icon space becomes 26px at inline-end, with 12px on the opposite side. | 290–301 |
| Desktop object-tools items | Items retain `float: left` and `margin-left: 5px`. | Items and anchors use inline-start floats; the 5px item gap moves to inline-start. | 278–288 |
| Desktop action dropdown | Select retains `margin-left: 10px`. | Both physical margins are reset; the 10px gap moves to inline-start. | 547–551 |
| Date/time inputs | Combined widget rules leave a 5px left margin and a 2px right margin. | Specific datetime selectors reset both sides and retain only 5px at inline-end: left 5px, right 0 in RTL. | 683–696 |
| Aligned help text | Left padding can survive alongside RTL right padding; more-specific input/help sibling rules can also retain left indentation. | Both sides are reset before applying 160px start indentation and 10px start padding, with exceptions for adjacent content and narrow screens. | 582–633, 915–926 |
| Alternate `.colSM` columns | Physical column margins and more-specific sidebar floats lack matching RTL overrides. | Reserved column space, floats, and the negative sidebar offset use logical sides. This concerns pages using `.colSM`, not every dashboard. | 361–376 |
| Recent-action list items | The specific action-list rule retains left padding despite icon mirroring elsewhere. | Both sides are cleared and 18px is reserved at inline-start. | 383–387 |
| Inline view/change links | Generic RTL icon rules omit `.inlineviewlink` and `.inlinechangelink`. | Those classes receive start-side icon padding and RTL background positioning. | 307–328 |
| Related lookup and file-delete links | Matching links retain a physical 5px left margin. | Their gap moves to inline-start. | 668–673 |
| Radio-list entries | `form div.radiolist div` retains 7px right padding. | Padding moves to inline-end. | 639–643 |
| Blockquotes | Border, padding, and indentation remain on the left. | These move to inline-start, including the module-specific indentation. | 167–182 |
| Sort-removal decoration | Its pseudo-element remains anchored with `left: 3px`. | Physical sides are reset and the anchor becomes `inset-inline-start: 3px`. | 482–486 |
| Selected filter entry | Stock RTL leaves padding on both sides. | Only start-side padding remains, alongside the start-side border and negative margin. | 503–513 |
| Search icon | Image retains a physical right margin. | The 4px gap moves to inline-end. The package also makes the search form flex-based with a 6px gap. | 522–537 |
| Focused skip link | Focus position is physically left-anchored. | It is anchored at inline-start. | 188–192 |
| Tabular inline original label | Stock adds `right: 0` without removing `left: 0`. | Dual physical anchoring is replaced by a single inline-start anchor. | 783–787 |

The M2M choose-all/clear-all rules also change `text-align: left` to `start`
(lines 822–825). That is a verified declaration change, not proof of a noticeable
visual difference for every button width.

### Punctuation and mixed-direction form content

Physical layout mirroring does not determine the direction of application text.
An English label in an RTL form can place its colon on the opposite side; English
help text can resolve its final punctuation against the page direction.

The package applies `unicode-bidi: plaintext` and `text-align: start` to labels,
help text, descriptions, and readonly values. These resolve their bidi paragraphs
from the first strong character instead. Direct children are included because
`unicode-bidi` is not inherited and Django wraps help text in another element.
See stylesheet lines 82–104.

For text-like inputs and textareas, the conditional plaintext rules provide the
same first-strong behavior. For example, an ASCII path beginning with `/archive/`
resolves its text direction from the Latin letters rather than the RTL page.
This does not force every arbitrary path or slug to LTR: Arabic-leading content
can legitimately resolve RTL. Dedicated LTR rules target URL widgets, username
and password inputs, UUID widgets, and code elements, not every slug field.

## What Django already handles

Do not treat every logical-property restatement as a newly fixed defect. Stock
Django 5.2 already mirrors substantial parts of the interface:

- Navigation-sidebar placement, borders, and table padding in
  [nav_sidebar.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/nav_sidebar.css).
- Calendar previous/next placement and sprite slices in `rtl.css`.
- Several action icons, sorted-column controls, paginator gaps, and form controls.
- Select2 arrow/clear controls and multiple-choice spacing in
  [autocomplete.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/autocomplete.css).
- Additional object-tools and action-bar behavior at narrow widths in
  [responsive_rtl.css](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/admin/static/admin/css/responsive_rtl.css).

Some stock controls use flex layout. A float on a flex item, such as a selector
filter label, does not establish a visible layout defect merely because the
physical declaration lacks a literal RTL counterpart.

## Limitations and unverified claims

### Sidebar chevrons

The package swaps the literal `«` and `»` pseudo-content at stylesheet lines
432–440. Both characters have Unicode's mirrored property, so their rendered
appearance also depends on bidi resolution. The Arabic screenshot below shows
`«` beside the expanded right-hand sidebar. This page does **not** count the
content swap as a verified correction of the rendered arrow direction.

### Selectors that do not match stock page classes

Django's standard templates put `dashboard` or `change-list` on the same `<body>`
that receives `rtl-admin`. These package selectors instead require a descendant:

- `.rtl-admin .dashboard .module table td a` at lines 389–394.
- `.rtl-admin .change-list .filtered table` and its `tbody th` rule at lines
  446–456.

They do not match the standard body-class structure. In particular, the intended
filtered-table header-padding change is not an effective stock-admin fix through
that rule. These are limitations of the current selectors, not changes made by
this documentation.

### LTR, fonts, and theme compatibility

Rules scoped to `.rtl-admin` also run in English. Header gaps, search layout,
datetime margins, and plaintext handling mean the result is not byte-for-byte
stock admin plus a switcher. The package preserves the stock interface's overall
appearance rather than guaranteeing all LTR rules are no-ops.

The font stack names installed fallback fonts; it does not ship font files or
establish that stock Arabic or Hebrew rendering always lacks glyphs. Third-party
admin themes and custom markup are outside this stock-template comparison.

## CSS, Unicode isolation, and formatting are separate

| Mechanism | What it changes | How to control it |
| --- | --- | --- |
| Package CSS | Layout and presentation; does not insert characters into values. | `ENABLE_CSS` controls stylesheet loading. `ISOLATE_TABLE_CELLS` gates CSS isolation; `PLAINTEXT_FORM_FIELDS` gates plaintext input/textarea rules. |
| Unicode bidi helpers | Insert LRI, RLI, or FSI plus PDI around displayed text, or isolate embedded runs. | Explicitly use the Python helpers, template filters, or `BidiSafeAdminMixin`. |
| Locale formatting | Produces formatted number, currency, percentage, or date/time text with supported digit shapes. | Explicitly call helpers or filters; `NUMERALS` and optional Babel affect their output. |

The two CSS safety-net switches are not complete bidi off-switches: labels,
help text, readonly values, and dedicated machine-value rules remain while the
stylesheet is loaded. See [Configuration](configuration.md).

For an opaque identifier such as an ISBN in RTL prose, choose explicit LTR
isolation rather than assuming first-strong isolation determines the desired
direction of an all-numeric value. Isolation addresses display-time resolution,
not database corruption. Apply it when rendering; Unicode controls can survive
copy/paste and serialization. See [Template tags and filters](template-tags.md),
[the admin mixin](admin-mixin.md), and [the Python API](api.md).

Formatting is another explicit opt-in. Plain `ar` normally uses Latin digits,
`ar-eg` uses Arabic-Indic digits, and `fa` uses extended Arabic-Indic digits.
Babel provides richer locale patterns when installed. Without it, the helpers
use Django formats plus digit transliteration and simpler currency/percent
fallbacks. Installing the package does not convert every admin number or date.

## Existing example screenshots

These are two existing **package-enabled** changelist screenshots, not a
stock-before/package-after pair. No stock-before screenshots or fresh computed
style measurements accompany this comparison.

![Package-enabled English admin showing Arabic book data, identifiers, and the language switcher](admin-en.png)

*English interface in the example project. Arabic book data remains present;
the identifiers and custom price column are part of the demo configuration.*

![Package-enabled Arabic Egypt admin with right-hand navigation, left-hand filters, and Arabic-Indic prices](admin-ar.png)

*The same example project in Arabic (Egypt). The custom price column uses
Arabic-Indic digits, while identifiers and date/year displays still include Latin
digits. This illustrates language switching, not universal numeric conversion.*

Both PNGs are 3200 × 1800. The example `BookAdmin` explicitly uses the bidi mixin
and a `format_currency()` display method. These images therefore do not establish
CSS-only identifier handling or automatic price formatting.

The screenshots do not cover change forms, login, calendar popups, M2M selectors,
autocomplete dropdowns, mobile layouts, or dark mode. They are useful overview
illustrations, not a visual regression suite. Follow [Quick start](quick-start.md)
to check the mechanisms in your own project, and [Translations](translations.md)
for locale-specific manual checks.
