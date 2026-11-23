---
title: Stock admin RTL defects | django-rtl-admin
description: Review Django admin RTL fixes with computed-style coverage on Django 5.2 and 6.1, stock parity for all measured English properties, version gates, and documented limitations.
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
markup is present. Source references identify selectors or line ranges in
`rtl-admin.css`.

The object-tools `li` float/margin rules, including the CSS media-query override,
are scoped to the body class `rtl-admin--pre-6-0`. They do not replace Django 6.0+
inline-block/no-float layout in either language, including on 6.1. The separate
`rtl-admin--pre-6-1` body class gates the older datetime spacing, aligned-form
label and help padding, and (via `:not(.rtl-admin--pre-6-1)`) Django 6.1's
radio-label padding; newer versions retain their own stock LTR values and exact
RTL mirrors.

| Element | Stock Django 5.2 RTL | Package behavior | Source reference |
| --- | --- | --- | --- |
| Object-tools Add/view-site icon | Icon remains on the right, with `padding-right: 26px`. | Icon moves to `left 7px center`; icon space becomes 26px at inline-end, with 12px on the opposite side. | 290–301 |
| Desktop object-tools items | Items retain `float: left` and `margin-left: 5px`. | Before Django 6.0, items float right with a 5px right margin in RTL; LTR retains the stock left float and 5px left margin. On 6.0+, stock inline-block/no-float layout remains in both languages, with zero first-item margins. | `.object-tools li` |
| Desktop action dropdown | Select retains `margin-left: 10px`. | Both physical margins are reset; the 10px gap moves to inline-start. | 547–551 |
| Date/time inputs | Combined widget rules leave a 5px left margin and a 2px right margin. | Both split inputs exactly mirror stock LTR margins: RTL left/right 2px/5px before Django 6.1 and 2px/0 on 6.1+. LTR stays 5px/2px and 0/2px, respectively. | `.datetime input` |
| Aligned help text | Left/right padding is 10px/10px, not the mirror of stock LTR's 10px/3px; more-specific input/help sibling rules can also retain left indentation. | Before Django 6.1, RTL left/right padding becomes 3px/10px and LTR keeps 10px/3px, alongside version-aware indentation and responsive rules. On 6.1+, padding remains 0/0 in both languages. | `form .aligned p.help`, `form .aligned div.help` |
| Alternate `.colSM` columns | Physical column margins and more-specific sidebar floats lack matching RTL overrides. | Reserved column space, floats, and the negative sidebar offset use logical sides. This concerns pages using `.colSM`, not every dashboard. | 361–376 |
| Recent-action list items | The specific action-list rule retains left padding despite icon mirroring elsewhere. | Both sides are cleared and 18px is reserved at inline-start. | 383–387 |
| Inline view/change links | Generic RTL icon rules omit `.inlineviewlink` and `.inlinechangelink`. | Those classes receive start-side icon padding and RTL background positioning. | 307–328 |
| Related lookup and file-delete links | Matching links retain a physical 5px left margin. | Their gap moves to inline-start. | 668–673 |
| Radio-list entries | `form div.radiolist div` retains 7px right padding. | Padding moves to inline-end. | 639–643 |
| Radio inputs | `form div.radiolist input[type="radio"]` retains a 4px right margin. | Both physical horizontal margins are reset; the 4px gap moves to inline-end. | `form div.radiolist input[type="radio"]` |
| Radio labels | Before Django 6.1, `rtl.css` gives `.aligned label` 1em (13px) left padding instead of mirroring stock LTR's 10px; Django 6.1 moves `padding: 4px 10px 0 0` onto `form div.radiolist label` with no RTL mirror. | Version-gated logical rules keep stock LTR's 10px right padding and mirror it to 10px left padding in RTL on both pre-6.1 and 6.1+. | `.aligned label`, `form div.radiolist label` |
| Aligned checkbox labels (above 767px) | `.aligned .vCheckboxLabel` retains 5px left padding above 767px (`responsive_rtl.css` mirrors it only at or below 767px). | Horizontal physical sides are reset and 5px moves to inline-start while preserving stock vertical padding across versions. | `.aligned .vCheckboxLabel` |
| Delete confirmation cancel link | `.delete-confirmation form .cancel-link` retains `margin: 0 0 0 10px` on both delete confirmation pages. | A compound `.rtl-admin.delete-confirmation` rule resets horizontal margins and moves the 10px gap to inline-start. | `.delete-confirmation form .cancel-link` |
| Stacked (`filter_vertical`) selector chooser | `.stacked ul.selector-chooser` retains a 40% left margin and `.stacked .selector-chooser li` retains 5px left padding. | Physical sides are reset; the 40% offset moves to inline-start in RTL (scoped to `.rtl-admin--rtl` so English keeps Django 4.2's `margin: 15px auto` centering at or below 1024px; on Django 4.2 at or below 1024px, RTL keeps the 40% start margin instead of centering) and the 5px item padding moves to inline-start (keeping the 3px reset at or below 1024px). | `.stacked ul.selector-chooser`, `.stacked .selector-chooser li` |
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
both languages with CSS on and off, and **all measured English computed properties
must match stock**. A stock RTL negative control is required except for the
documented parity cases: 2 on Django 6.0+, 5 on all versions, and 6 and 10's
`aligned-label` on Django 6.1+.
The object-tools test also runs at 800px to cover the media-query rule: stock
Django 5.2 already mirrors the float there, but not the first item's margin.

| README defect | Test | Measured contract |
| --- | --- | --- |
| 1 — Add icon and padding | `test_defect_1_addlink_icon_and_padding` | RTL background position changes from `calc(100% - 7px) 50%` to `7px 50%`; inline-start/end padding changes from 26px/12px to 12px/26px. |
| 2 — Object-tools items | `test_defect_2_object_tools_float_and_margin` | Before Django 6.0, the first item's RTL float changes from left to right and its left/right margins from 5px/0 to 0/5px; English keeps the stock left float and 5px/0 margins. Django 6.0+ (including 6.1) retains stock inline-block/no-float layout and zero first-item margins in both languages: a parity case with no negative control. |
| 3 — Action dropdown | `test_defect_3_actions_select_margin` | RTL left/right margins change from 10px/0 to 0/10px. |
| 4 — Date/time inputs | `test_defect_4_datetime_input_margins` | Both halves retain stock LTR left/right margins of 5px/2px before Django 6.1 and 0/2px on 6.1+. Stock RTL has those same unmirrored values; the fix mirrors them exactly to 2px/5px and 2px/0, respectively. |
| 5 — Sidebar chevrons | `test_defect_5_sidebar_toggle_chevrons` | Expanded and collapsed `::before` content, direction, `unicode-bidi` and transform remain stock; no negative control is claimed. See [Sidebar chevrons](#sidebar-chevrons). |
| 6 — Help padding | `test_defect_6_help_text_padding` | Before Django 6.1, RTL left/right padding changes from 10px/10px to 3px/10px, exactly mirroring stock LTR's preserved 10px/3px. On Django 6.1+ both sides remain 0 with CSS on or off in both languages: a stock-parity check, not a negative control. |
| 8 — Help text and descriptions | `test_defect_8_inner_help_text_unicode_bidi` | Outer `.help`, its actual inner `<div>` (`.field-title #id_title_helptext > div`), and `fieldset .description` change from `unicode-bidi: isolate` to `plaintext` only in RTL; English retains stock `isolate`. This checks the non-inherited property, not the rendered position of a full stop. |
| 10 — Selected unmirrored rules | `test_defect_10_unmirrored_rules` | Parameters: `colsm` (column margins, main/sidebar floats and sidebar offset), `related-lookup` (5px margin), `chooseall` and `clearall` (text alignment), `radiolist` (7px padding), `radio-input` (4px margin), `radio-label` (10px end padding), `aligned-label` (four-side padding parity and 10px RTL mirror on a plain aligned label before 6.1; stock-parity zero padding on 6.1+), `checkbox-label` (5px start padding above 767px), `delete-cancel` (10px start margin), `stacked-chooser` (40% chooser margin and 5px/3px item padding), `sortremove` (`::after` inset: left 3px stock, right 3px with RTL package CSS). |

Defect 10 covers those twelve parameters, not every selector listed in the README.
The `.colSM` case uses a tiny test template extending the stock index and overriding
only its `coltype` block. Raw-ID lookup and radio cases temporarily monkeypatch the
existing `BookAdmin` to use `Book.category` and `Book.status`; the checkbox case
uses the auth `User` change form, the delete-cancel case uses the `Book` delete
confirmation page, and the horizontal/vertical M2M cases reuse the existing auth
`Group.permissions` widget (monkeypatching `filter_vertical` for the stacked
variant). Defect 8 temporarily wraps the existing first fieldset description in a
`<div>` to check the direct child as well as its container, just as it checks both
help-text wrappers. No new model fields are needed.

README defects **7 (label punctuation)** and **9 (input-path punctuation)** are
outside this computed-style suite: computed declarations alone do not establish
visual punctuation correctness. The existing `test_change_form` checks label
alignment and geometry relative to fields; it does not establish input-path
punctuation coverage. The source-level examples below are not additional visual
assertions.

Two tests in the same module cover object-name isolation rather than numbered README defects:
`test_issue_2_message_link_and_subtitle_are_isolated` and
`test_issue_2_delete_page_object_links_are_isolated` check `unicode-bidi: isolate`
on the object names the admin quotes (see
[Object names in messages and on the delete page](admin-mixin.md#object-names-in-messages-and-on-the-delete-page)).
They run in both languages with the package CSS on, with it off, and with
`ISOLATE_TABLE_CELLS` off. That rule is not tied to the direction, so English
differs from stock there by design. The links compute `normal` without the rule.
Chromium already isolates headings, so the subtitle computes `isolate` either way;
for it, the tests read which selector of the loaded package stylesheet matches.

The same `ISOLATE_TABLE_CELLS` setting covers linked names in the dashboard's
Recent actions list and related-object labels beside `raw_id_fields`. For a
deletion, Recent actions renders the name as bare text, so CSS cannot isolate it
from the rest of the entry. In the object history table's data cells and in
Select2 selections and dropdown options, `plaintext` lets each value take its
base direction from its own text without changing the column or widget alignment.

### Punctuation and mixed-direction form content

Physical layout mirroring does not determine the direction of application text.
An English label in an RTL form can place its colon on the opposite side; English
help text can resolve its final punctuation against the page direction.

Labels, legends and readonly values retain their existing `unicode-bidi: plaintext`
safety nets in both languages; labels and legends still align with the form.
Help text (both the outer element and its inner wrapper) and fieldset descriptions
use `plaintext` **only in RTL**, resolving bidi paragraphs from the first strong
character. English keeps stock `unicode-bidi: isolate` on these help and description
elements. The RTL selectors include `.help > *` and `fieldset .description > *`
because `unicode-bidi` is not inherited. This scope change does not restrict the
label, legend, readonly or input safety nets to RTL.

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

Rules scoped to `.rtl-admin` also run in English. **All measured English computed
properties match stock**, after resolving logical float and text-alignment keywords
to physical sides. There are no LTR exception allowances in the computed suite.

| Measured element | Stock and package LTR |
| --- | --- |
| Both split date/time inputs | Left/right margins: 5px/2px before Django 6.1; 0/2px on 6.1+. |
| Aligned help text | Left/right padding: 10px/3px before Django 6.1; 0/0 on 6.1+. |
| Outer and inner help text, fieldset descriptions | `unicode-bidi: isolate`; the package's plaintext rules for these elements are RTL-only. |
| First object-tools item | Before Django 6.0: left float and left/right margins of 5px/0. On 6.0+ (including 6.1): stock inline-block layout, `float: none` and both margins 0. |

This claim covers every measured property, not every package rule: header gaps,
search layout and other unmeasured properties remain outside this comparison.
Labels, legends, readonly values and input safety nets are unchanged by the
RTL-only scoping of help text and descriptions.

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
legends, readonly values, RTL help text and fieldset descriptions, and dedicated
machine-value rules remain while the stylesheet is loaded.
See [Configuration](configuration.md).

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
