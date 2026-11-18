---
title: Stock admin RTL defects | django-rtl-admin
description: Review Django admin RTL fixes with computed-style coverage on Django 5.2 and 6.1, explicit stock-parity and LTR exceptions, and documented limitations.
---

# Stock admin RTL defects

Django already supports right-to-left languages. Its admin sets the page direction
and loads RTL styles for recognized languages. `django-rtl-admin` supplements that
support with logical spacing rules, text-direction handling, and optional display
helpers; it does not introduce RTL support from scratch.

## Scope of this comparison

The source comparison below uses Django's **`stable/5.2.x` source**. It is now
complemented by `getComputedStyle` assertions in
`tests/e2e/test_computed_styles.py` (issue #3), using the existing live-server and
Chromium suite at **1280px**, in **`ar-eg` and `en`**, with `ENABLE_CSS` both enabled
and disabled. The nox/CI browser matrix runs **Django 5.2 and the newest series,
currently 6.1, on Python 3.14**.

The numbered coverage table distinguishes measured corrections from stock-parity
checks and records version differences. It does not verify every supported Django
release, responsive breakpoint, custom template, or rendered punctuation sequence.
Disabling `ENABLE_CSS` supplies the stock CSS baseline; other package integration
remains in place.

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
| Dashboard action links | Stock desktop RTL mirrors the link spacing; the stock responsive sheets drop the end gap below 1024px. | A compound rule restates the spacing logically: 16px of icon room at inline-start, 0.6em at inline-end, with a matching media query dropping the end gap below 1024px. | 472–488 |
| Filtered changelist header cells | `changelists.css` widens `tbody th` with an unmirrored `padding-right: 1em`, which lands on the start edge in RTL. | Cells keep the stock base padding on both physical sides — 8px, widened to the responsive 10px at or below 1024px by a matching media query — and move the 1em to inline-end. | 549–564 |

The M2M choose-all/clear-all rules also change `text-align: left` to `start`
(lines 822–825). The computed suite verifies right alignment in RTL and stock
left alignment in LTR, not a noticeable visual difference for every button width.

The dashboard and changelist rules above must compound `rtl-admin` with the stock
body classes: Django puts `dashboard` or `change-list` on the same `<body>` that
receives `rtl-admin`, so a descendant selector such as `.rtl-admin .dashboard …`
matches nothing. The browser suite asserts the rendered geometry of both rules —
the gaps their boxes actually paint, measured with probe and text-range
rectangles rather than computed styles — in Arabic and English, in both colour
schemes, at 360px and 1280px
(`test_dashboard_action_link_padding`, `test_filtered_changelist_table_geometry`).

### Computed-style coverage

The README numbers below map to `tests/e2e/test_computed_styles.py`. These are
explicit computed-value contracts, not screenshot comparisons. Each test checks
both languages with CSS on and off; a stock RTL negative control is required
except for the documented parity cases (5, and 6 on Django 6.1).

| README defect | Test | Measured contract |
| --- | --- | --- |
| 1 — Add icon and padding | `test_defect_1_addlink_icon_and_padding` | RTL background position changes from `calc(100% - 7px) 50%` to `7px 50%`; inline-start/end padding changes from 26px/12px to 12px/26px. |
| 2 — Object-tools items | `test_defect_2_object_tools_float_and_margin` | The first item's float becomes inline-start and its 5px margin moves to inline-start. Django 5.2 stock uses `float: left` and a 5px left margin; Django 6.1 stock uses `float: none` and zero margins. |
| 3 — Action dropdown | `test_defect_3_actions_select_margin` | RTL left/right margins change from 10px/0 to 0/10px. |
| 4 — Date/time inputs | `test_defect_4_datetime_input_margins` | Both halves of the split widget get RTL left/right margins of 5px/0, replacing stock 5px/2px on Django 5.2 or 0/2px on Django 6.1. |
| 5 — Sidebar chevrons | `test_defect_5_sidebar_toggle_chevrons` | Expanded and collapsed `::before` content, direction, `unicode-bidi` and transform remain stock; no negative control is claimed. See [Sidebar chevrons](#sidebar-chevrons). |
| 6 — Help padding | `test_defect_6_help_text_padding` | Django 5.2 RTL left/right padding changes from 10px/10px to 0/10px. Django 6.1 is already corrected upstream: both sides remain 0 with CSS on or off in both languages, so this is a parity check, not a negative control. |
| 8 — Inner help text | `test_defect_8_inner_help_text_unicode_bidi` | The actual inner help `<div>` changes from `unicode-bidi: isolate` to `plaintext` in both languages. This checks the non-inherited property, not the rendered position of a full stop. |
| 10 — Selected unmirrored rules | `test_defect_10_unmirrored_rules` | Parameters: `colsm` (column margins, main/sidebar floats and sidebar offset), `related-lookup` (5px margin), `chooseall` and `clearall` (text alignment), `radiolist` (7px padding), `sortremove` (`::after` inset: left 3px stock, right 3px with RTL package CSS). |

Defect 10 covers those six parameters, not every selector listed in the README.
The `.colSM` case uses a tiny test template extending the stock index and overriding
only its `coltype` block. Raw-ID lookup and radio cases temporarily monkeypatch the
existing `BookAdmin` to use `Book.category` and `Book.status`; the M2M cases use the
existing auth `Group.permissions` widget. No new model fields are needed.

README defects **7 (label punctuation)** and **9 (input-path punctuation)** are
outside this computed-style suite: computed declarations alone do not establish
visual punctuation correctness. The existing `test_change_form` checks label
alignment and geometry relative to fields; it does not establish input-path
punctuation coverage. The source-level examples below are not additional visual
assertions.

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

The package deliberately does **not** swap the literal `«` and `»` pseudo-content:
the browser already mirrors these Unicode characters in RTL. In both languages,
with package CSS enabled or disabled, `#toggle-nav-sidebar::before` computes
`content: "«"` when expanded and `content: "»"` when collapsed. Its `direction` is
`rtl` in `ar-eg` and `ltr` in `en`, with `unicode-bidi: normal` and `transform: none`.

`test_defect_5_sidebar_toggle_chevrons` pins both states and their stock parity.
This corrects the historical README claim that an unswapped content declaration
is itself a defect; it is not a negative control or a claim that computed content
alone measures the painted glyph direction.

### LTR, fonts, and theme compatibility

Rules scoped to `.rtl-admin` also run in English. The computed suite explicitly
pins these LTR deviations rather than claiming the result is exactly stock:

| Measured element | Stock LTR | Package LTR |
| --- | --- | --- |
| Both split date/time inputs | Left/right margins: 5px/2px on Django 5.2; 0/2px on Django 6.1. | Left/right margins: 0/5px on both versions. |
| Title help text on Django 5.2 | Left/right padding: 10px/3px. | Left/right padding: 10px/0. |
| Inner help `<div>` | `unicode-bidi: isolate` in both languages and versions. | `unicode-bidi: plaintext` in both languages and versions. |
| First object-tools item on Django 6.1 | `float: none`; both margins 0. | `float: inline-start` (left in LTR); 5px inline-start margin, 0 at inline-end. |

Django 5.2's stock object-tools item already floats left with a 5px left margin,
so that LTR case matches. All other **tested LTR values** match stock after
resolving logical float and text-alignment keywords to physical sides. This is
not a guarantee that every package rule is an LTR no-op: header gaps, search
layout and other unmeasured properties remain outside that parity claim.

The font stack names installed fallback fonts; it does not ship font files or
establish that stock Arabic or Hebrew rendering always lacks glyphs. Third-party
admin themes and custom markup are outside this stock-template comparison.

## CSS, Unicode isolation, and formatting are separate

| Mechanism | What it changes | How to control it |
| --- | --- | --- |
| Package CSS | Layout and presentation; does not insert characters into values. | `ENABLE_CSS` controls stylesheet loading. `ISOLATE_TABLE_CELLS` gates CSS isolation; `PLAINTEXT_FORM_FIELDS` gates plaintext input/textarea rules. |
| Unicode bidi helpers | Strip existing `Bidi_Control` characters and insert LRI, RLI, or FSI plus PDI around displayed text, or isolate embedded runs. | Explicitly use the Python helpers, template filters, or `BidiSafeAdminMixin`. |
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
Babel provides full CLDR currency, percentage, date, and time patterns when
installed. Without it, numbers use built-in CLDR tables (falling back to Django
formats plus digit transliteration for uncovered locales), dates and times use
Django formats plus digit transliteration, and currency and percentage output
uses simpler fallbacks. Installing the package does not convert every admin
number or date.

## Existing example screenshots

These are two existing **package-enabled** changelist screenshots, not a
stock-before/package-after pair. They are not the evidence for the computed-style
contracts above; those use live browser measurements with CSS enabled and disabled.

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
