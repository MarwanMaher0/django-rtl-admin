"""Computed-style contracts for README defects 1–6, 8 and 10 (issue #3).

Use the existing live server and Chromium fixtures, not a second browser suite.
Each check reads the same stock markup with ENABLE_CSS on and off, in ar-eg and
en. Expectations are explicit, not inferred from the stylesheet under test.

Chevrons already mirror through bidi, Django 6.0 replaced floating object tools,
and Django 6.1 removed the double help padding. Those are stock-parity checks,
not claimed negative controls. Every measured LTR value must match stock.
"""

from __future__ import annotations

from types import ModuleType

import django
import pytest
from django.contrib import admin
from django.urls import path as url_path

from tests.testapp.admin import ChapterAdmin
from tests.testapp.models import Book, Chapter

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e

CHANGELIST = "/admin/testapp/book/"
ADD_FORM = "/admin/testapp/book/add/"
DJANGO_60 = django.VERSION >= (6, 0)
DJANGO_61 = django.VERSION >= (6, 1)


@pytest.fixture
def style_pages(settings, open_admin, live_server_app):
    """Four fresh contexts; disable CSS on the server, never by editing the DOM."""

    def _open(path):
        pages = {}
        for lang in ("ar-eg", "en"):
            for enabled in (True, False):
                live_server_app.wait_until_idle()
                settings.RTL_ADMIN = {"ENABLE_CSS": enabled}
                page = open_admin(path, lang=lang, width=1280)
                assert page.locator("html").get_attribute("lang") == lang
                direction = "rtl" if lang == "ar-eg" else "ltr"
                assert page.locator("html").get_attribute("dir") == direction
                assert (
                    page.locator("body").evaluate("el => getComputedStyle(el).direction")
                    == direction
                )
                sheet = page.locator('link[href$="django_rtl_admin/css/rtl-admin.css"]')
                assert sheet.count() == int(enabled)
                if enabled:
                    assert sheet.evaluate("el => el.sheet !== null"), "package CSS did not load"
                assert page.locator('link[href$="admin/css/base.css"]').evaluate(
                    "el => el.sheet !== null"
                ), "stock CSS did not load"
                if lang == "ar-eg":
                    assert page.locator('link[href$="admin/css/rtl.css"]').evaluate(
                        "el => el.sheet !== null"
                    ), "stock RTL CSS did not load"
                assert not page.js_errors, page.js_errors
                pages[lang, enabled] = page
        return pages

    return _open


def computed(page, selector, properties, *, pseudo=None):
    """Read a unique, visible element (including ::before/::after when requested).

    Chromium preserves logical float/text-align keywords in computed styles.
    Resolve only those keywords to physical sides so LTR parity compares their
    meaning, not e.g. ``inline-start`` against the equivalent stock ``left``.
    """
    locator = page.locator(selector)
    assert locator.count() == 1, f"{selector}: expected exactly one element"
    assert locator.is_visible(), f"{selector}: element is not visible"
    return locator.evaluate(
        """(el, args) => {
            const cs = getComputedStyle(el, args.pseudo);
            const start = cs.direction === 'rtl' ? 'right' : 'left';
            const end = cs.direction === 'rtl' ? 'left' : 'right';
            return Object.fromEntries(args.properties.map(property => {
                let value = cs.getPropertyValue(property);
                if (property === 'float' || property === 'text-align') {
                    if (value === 'inline-start' || value === 'start') value = start;
                    if (value === 'inline-end' || value === 'end') value = end;
                }
                return [property, value];
            }));
        }""",
        {"properties": list(properties), "pseudo": pseudo},
    )


def assert_contract(
    pages,
    selector,
    *,
    rtl,
    stock_rtl,
    stock_ltr,
    stock_parity_reason=None,
    pseudo=None,
):
    """Pin both baselines and the fix; require a real RTL negative control.

    LTR must match stock without allowances. An RTL stock-parity exception
    must be explicit (no skip, xfail, or caught assert).
    """
    expected = {
        ("ar-eg", True): rtl,
        ("ar-eg", False): stock_rtl,
        ("en", True): stock_ltr,
        ("en", False): stock_ltr,
    }
    measured = {}
    for key, values in expected.items():
        assert values.keys() == rtl.keys(), "all four cases must measure the same properties"
        measured[key] = computed(pages[key], selector, values, pseudo=pseudo)
        assert measured[key] == values, f"{selector}{pseudo or ''} [{key=}]"
    if stock_parity_reason:
        assert measured["ar-eg", True] == measured["ar-eg", False], stock_parity_reason
    else:
        assert measured["ar-eg", True] != measured["ar-eg", False], (
            f"{selector}: disabling ENABLE_CSS must expose the stock defect"
        )
    assert measured["en", True] == measured["en", False]


def test_defect_1_addlink_icon_and_padding(style_pages):
    """The + icon and its 26px padding belong at inline-end, not RTL start."""
    ltr = {
        "background-position": "calc(100% - 7px) 50%",
        "padding-inline-start": "12px",
        "padding-inline-end": "26px",
    }
    assert_contract(
        style_pages(CHANGELIST),
        ".object-tools a.addlink",
        rtl={**ltr, "background-position": "7px 50%"},
        stock_rtl={**ltr, "padding-inline-start": "26px", "padding-inline-end": "12px"},
        stock_ltr=ltr,
    )


def test_defect_2_object_tools_float_and_margin(style_pages):
    """Mirror legacy floats; retain Django 6.0+'s inline-block layout."""
    ltr = {"float": "left", "margin-left": "5px", "margin-right": "0px"}
    stock = {**ltr, "float": "none", "margin-left": "0px"} if DJANGO_60 else ltr
    rtl = stock if DJANGO_60 else {"float": "right", "margin-left": "0px", "margin-right": "5px"}
    pages = style_pages(CHANGELIST)
    # Also hit the media-query copy: it must not restore floats on modern Django.
    for width in (1280, 800):
        for page in pages.values():
            page.set_viewport_size({"width": width, "height": 900})
        # Stock responsive_rtl.css already flips the legacy float at 1024px,
        # but leaves the first item's margin on the wrong side.
        stock_rtl = {**stock, "float": "right"} if not DJANGO_60 and width <= 1024 else stock
        assert_contract(
            pages,
            ".object-tools li",
            rtl=rtl,
            stock_rtl=stock_rtl,
            stock_ltr=stock,
            stock_parity_reason="Django 6.0+ uses inline-block object tools" if DJANGO_60 else None,
        )
        if DJANGO_60:
            for page in pages.values():
                assert computed(page, ".object-tools li", ("display",)) == {
                    "display": "inline-block"
                }


def test_defect_3_actions_select_margin(style_pages):
    stock = {"margin-left": "10px", "margin-right": "0px"}
    assert_contract(
        style_pages(CHANGELIST),
        "#changelist .actions select",
        rtl={"margin-left": "0px", "margin-right": "10px"},
        stock_rtl=stock,
        stock_ltr=stock,
    )


def test_defect_4_datetime_input_margins(style_pages):
    pages = style_pages(ADD_FORM)
    stock = {"margin-left": "0px" if DJANGO_61 else "5px", "margin-right": "2px"}
    # Check BOTH halves of the split widget, not the standalone DateField.
    for field in (".datetime input#id_available_from_0", ".datetime input#id_available_from_1"):
        assert_contract(
            pages,
            field,
            rtl={"margin-left": "2px", "margin-right": "0px" if DJANGO_61 else "5px"},
            stock_rtl=stock,
            stock_ltr=stock,
        )


def test_defect_5_sidebar_toggle_chevrons(style_pages):
    """Do not double-mirror Unicode chevrons that stock Django already gets right."""
    pages = style_pages(CHANGELIST)
    for expanded, glyph in ((True, '"«"'), (False, '"»"')):
        for page in pages.values():
            assert (
                page.locator("#main").evaluate("el => el.classList.contains('shifted')") == expanded
            )
            # A transform on the button is not inherited by ::before, but
            # would still double-mirror the painted chevron.
            assert computed(page, "#toggle-nav-sidebar", ("transform",)) == {"transform": "none"}
        ltr = {"content": glyph, "direction": "ltr", "unicode-bidi": "normal", "transform": "none"}
        rtl = {**ltr, "direction": "rtl"}
        assert_contract(
            pages,
            "#toggle-nav-sidebar",
            rtl=rtl,
            stock_rtl=rtl,
            stock_ltr=ltr,
            pseudo="::before",
            stock_parity_reason="Unicode mirrors «/» in RTL; the package must not swap them again",
        )
        if expanded:
            for page in pages.values():
                page.locator("#toggle-nav-sidebar").click()
                page.wait_for_function(
                    "!document.getElementById('main').classList.contains('shifted')"
                )


def test_defect_6_help_text_padding(style_pages):
    if DJANGO_61:
        # The new stacked form layout removed this defect upstream.
        rtl = stock_rtl = stock_ltr = {"padding-left": "0px", "padding-right": "0px"}
    else:
        rtl = {"padding-left": "3px", "padding-right": "10px"}
        stock_rtl = {"padding-left": "10px", "padding-right": "10px"}
        stock_ltr = {"padding-left": "10px", "padding-right": "3px"}
    assert_contract(
        style_pages(ADD_FORM),
        ".field-title #id_title_helptext",
        rtl=rtl,
        stock_rtl=stock_rtl,
        stock_ltr=stock_ltr,
        stock_parity_reason="Django 6.1 stacked help text has no padding" if DJANGO_61 else None,
    )


def test_defect_8_inner_help_text_unicode_bidi(style_pages, monkeypatch):
    """unicode-bidi is not inherited: reading only .help misses this regression."""
    # Admin descriptions accept HTML. Exercise a block child as well as the
    # outer description without changing the existing page or model fields.
    book_admin = admin.site._registry[Book]
    title, options = book_admin.fieldsets[0]
    options = {**options, "description": f"<div>{options['description']}</div>"}
    monkeypatch.setattr(book_admin, "fieldsets", ((title, options), *book_admin.fieldsets[1:]))
    pages = style_pages(ADD_FORM)
    for selector in (
        ".field-title #id_title_helptext",
        ".field-title #id_title_helptext > div",
        "fieldset:has(.field-title) > .description",
        "fieldset:has(.field-title) > .description > div",
    ):
        assert_contract(
            pages,
            selector,
            rtl={"unicode-bidi": "plaintext"},
            stock_rtl={"unicode-bidi": "isolate"},
            stock_ltr={"unicode-bidi": "isolate"},
        )


@pytest.mark.parametrize(
    "rule", ["colsm", "related-lookup", "chooseall", "clearall", "radiolist", "sortremove"]
)
def test_defect_10_unmirrored_rules(style_pages, monkeypatch, rule):
    """Use existing pages and fields; only select the missing widget/layout variants."""
    if rule == "colsm":
        # Django's default dashboard uses colMS. Exercise its stock colSM
        # variant through the existing index view, changing only that block.
        monkeypatch.setattr(admin.site, "index_template", "admin/colsm_index.html")
        pages = style_pages("/admin/")
        for selector, rtl, stock in (
            (
                ".colSM",
                {"margin-left": "0px", "margin-right": "300px"},
                {"margin-left": "300px", "margin-right": "0px"},
            ),
            (".colSM #content-main", {"float": "left"}, {"float": "right"}),
            (
                ".colSM #content-related",
                {"float": "right", "margin-left": "0px", "margin-right": "-300px"},
                {"float": "left", "margin-left": "-300px", "margin-right": "0px"},
            ),
        ):
            assert_contract(pages, selector, rtl=rtl, stock_rtl=stock, stock_ltr=stock)
    elif rule == "related-lookup":
        # Reuse Book.category; no extra model, field, or migration is necessary.
        book_admin = admin.site._registry[Book]
        monkeypatch.setattr(book_admin, "autocomplete_fields", ())
        monkeypatch.setattr(book_admin, "raw_id_fields", ("category",))
        stock = {"margin-left": "5px", "margin-right": "0px"}
        assert_contract(
            style_pages(ADD_FORM),
            ".field-category .related-lookup",
            rtl={"margin-left": "0px", "margin-right": "5px"},
            stock_rtl=stock,
            stock_ltr=stock,
        )
    elif rule in {"chooseall", "clearall"}:
        # GroupAdmin.permissions already supplies a real filter_horizontal M2M.
        assert_contract(
            style_pages("/admin/auth/group/add/"),
            f".selector-{rule}",
            rtl={"text-align": "right"},
            stock_rtl={"text-align": "left"},
            stock_ltr={"text-align": "left"},
        )
    elif rule == "radiolist":
        monkeypatch.setattr(
            admin.site._registry[Book], "radio_fields", {"status": admin.HORIZONTAL}
        )
        stock = {"padding-left": "0px", "padding-right": "7px"}
        pages = style_pages(ADD_FORM)
        for index in (1, 2):
            assert_contract(
                pages,
                f"form div.radiolist#id_status > div:nth-child({index})",
                rtl={"padding-left": "7px", "padding-right": "0px"},
                stock_rtl=stock,
                stock_ltr=stock,
            )
    else:
        pages = style_pages(CHANGELIST)
        values = {}
        selector = "table thead th.sorted .sortoptions a.sortremove"
        for key, page in pages.items():
            # Stock hides the control until the header is hovered.
            page.locator("#result_list th.sorted").hover()
            values[key] = computed(page, selector, ("left", "right"), pseudo="::after")
        anchors = {
            ("ar-eg", True): "right",
            ("ar-eg", False): "left",
            ("en", True): "left",
            ("en", False): "left",
        }
        for key, side in anchors.items():
            assert values[key][side] == "3px", f"sortremove {key}: {side} anchor"
            # The opposite inset is a used pixel value, not 'auto', and
            # depends on glyph/font width. Ensure the old anchor was cleared
            # without hardcoding a font-dependent 4.29688px.
            opposite = "left" if side == "right" else "right"
            assert values[key][opposite] != "3px", f"sortremove {key}: stale {opposite} anchor"
        assert values["ar-eg", True] != values["ar-eg", False]
        assert values["en", True] == values["en", False]


# -- issue #2: object names quoted by the admin --------------------------------

MESSAGE_LINK_RULE = ".rtl-admin--isolate-cells ul.messagelist li a"
SUBTITLE_RULE = (
    ".rtl-admin--isolate-cells #content > .titles-and-tools > .titles > h2"
    if DJANGO_61
    else ".rtl-admin--isolate-cells #content > h2"
)
DELETE_LIST_LINK_RULE = ".rtl-admin--isolate-cells.delete-confirmation #content ul li a"

# (ENABLE_CSS, ISOLATE_TABLE_CELLS): is the package's isolation in force?
ISOLATION_CASES = {(True, True): True, (False, True): False, (True, False): False}


def unicode_bidi(locator):
    """Computed ``unicode-bidi`` of one element, and the package selectors that set it.

    The second value separates the package's rule from a browser default:
    it lists the selectors of rtl-admin.css that match the element in a rule
    declaring ``unicode-bidi``, read from the loaded stylesheet.
    """
    assert locator.count() == 1, "expected exactly one element"
    assert locator.is_visible(), "element is not visible"
    return locator.evaluate(
        """el => {
            const selectors = [];
            const walk = rules => {
                for (const rule of rules) {
                    if (rule.media && !matchMedia(rule.media.mediaText).matches) continue;
                    if (rule.selectorText && rule.style.getPropertyValue('unicode-bidi')) {
                        for (const selector of rule.selectorText.split(',')) {
                            if (el.matches(selector)) selectors.push(selector.trim());
                        }
                    }
                    if (rule.cssRules) walk(rule.cssRules);
                }
            };
            for (const sheet of document.styleSheets) {
                if (sheet.href && sheet.href.endsWith('django_rtl_admin/css/rtl-admin.css')) {
                    walk(sheet.cssRules);
                }
            }
            return [getComputedStyle(el).unicodeBidi, selectors];
        }"""
    )


@pytest.fixture
def isolation_pages(settings, open_admin, live_server_app):
    """Open a page per language and isolation case, running ``prepare`` on each."""

    def _open(path, prepare=None):
        pages = {}
        for lang in ("ar-eg", "en"):
            for css, cells in ISOLATION_CASES:
                live_server_app.wait_until_idle()
                settings.RTL_ADMIN = {"ENABLE_CSS": css, "ISOLATE_TABLE_CELLS": cells}
                page = open_admin(path, lang=lang, width=1280)
                if prepare is not None:
                    # The follow-up request has to see the same settings.
                    prepare(page)
                    live_server_app.wait_until_idle()
                assert page.locator("html").get_attribute("lang") == lang
                sheet = page.locator('link[href$="django_rtl_admin/css/rtl-admin.css"]')
                assert sheet.count() == int(css)
                if css:
                    assert sheet.evaluate("el => el.sheet !== null"), "package CSS did not load"
                body = page.locator("body").get_attribute("class").split()
                assert ("rtl-admin--isolate-cells" in body) is cells
                assert not page.js_errors, page.js_errors
                pages[lang, css, cells] = page
        return pages

    return _open


def test_issue_2_message_link_and_subtitle_are_isolated(isolation_pages, e2e_data):
    """The object name in the "changed" message link and in the change-form subtitle.

    A link is ``unicode-bidi: normal`` in stock, so both switches are real
    negative controls for it.  Chromium's own stylesheet already isolates
    headings, so the subtitle computes ``isolate`` everywhere; what the
    package adds is read from its stylesheet, whose subtitle selector has to
    follow the markup of the running Django.  The switch is not tied to the
    direction, so English differs from stock here by design.
    """
    book = e2e_data["book"]
    change_form = f"/admin/testapp/book/{book.pk}/change/"

    def save_and_continue(page):
        with page.expect_navigation():
            page.locator("input[name=_continue]").click()
        page.wait_for_load_state("load")
        assert page.url.endswith(change_form), "the change form did not validate"

    for (lang, css, cells), page in isolation_pages(change_form, save_and_continue).items():
        case = f"{lang=} ENABLE_CSS={css} ISOLATE_TABLE_CELLS={cells}"
        isolated = ISOLATION_CASES[css, cells]
        link = page.locator("ul.messagelist li.success").get_by_role(
            "link", name=book.title, exact=True
        )
        assert unicode_bidi(link) == (
            ["isolate", [MESSAGE_LINK_RULE]] if isolated else ["normal", []]
        ), case
        subtitle = page.get_by_role("heading", name=book.title, exact=True, level=2)
        assert unicode_bidi(subtitle) == ["isolate", [SUBTITLE_RULE] if isolated else []], case


def test_issue_2_delete_page_object_links_are_isolated(isolation_pages, e2e_data):
    """The links in the object lists of both delete confirmation pages."""
    book = e2e_data["book"]

    def delete_selected(page):
        page.locator("#result_list input.action-select").first.check()
        page.locator("select[name=action]").select_option("delete_selected")
        with page.expect_navigation():
            page.locator("button[name=index]").click()
        page.wait_for_load_state("load")

    for path, prepare, body_class in (
        (f"/admin/testapp/book/{book.pk}/delete/", None, "delete-confirmation"),
        (CHANGELIST, delete_selected, "delete-selected-confirmation"),
    ):
        for (lang, css, cells), page in isolation_pages(path, prepare).items():
            case = f"{body_class} {lang=} ENABLE_CSS={css} ISOLATE_TABLE_CELLS={cells}"
            assert body_class in page.locator("body").get_attribute("class").split(), case
            # Chapter now has a change link too; check the selected book itself.
            link = page.locator('#content li > a[href^="/admin/testapp/book/"]')
            expected = (
                ["isolate", [DELETE_LIST_LINK_RULE]]
                if ISOLATION_CASES[css, cells]
                else ["normal", []]
            )
            assert unicode_bidi(link) == expected, case


def assert_name_bidi(locator, case, value, *, stock="normal"):
    """Block elements such as td and li already compute `isolate` in Chromium."""
    _lang, css, cells = case
    enabled = ISOLATION_CASES[css, cells]
    computed_value, package_rules = unicode_bidi(locator)
    assert computed_value == (value if enabled else stock), case
    assert bool(package_rules) is enabled, case


def test_recent_actions_object_link_is_isolated(isolation_pages, book_log_entry):
    for case, page in isolation_pages("/admin/").items():
        link = page.locator("#recent-actions-module").get_by_role(
            "link", name=book_log_entry.object_repr, exact=True
        )
        assert_name_bidi(link, case, "isolate")


def test_history_table_values_are_isolated(isolation_pages, book_log_entry):
    path = f"/admin/testapp/book/{book_log_entry.object_id}/history/"
    for case, page in isolation_pages(path).items():
        row = page.locator("#change-history tbody tr", has_text=book_log_entry.change_message)
        for name in (book_log_entry.user.username, book_log_entry.change_message):
            cell = row.get_by_role("cell", name=name, exact=True)
            assert_name_bidi(cell, case, "plaintext", stock="isolate")


@pytest.mark.parametrize("registered", [True, False], ids=["linked", "unlinked"])
def test_raw_id_related_object_label_is_isolated(
    isolation_pages, mixed_name_book, settings, registered
):
    if not registered:
        # Without a Book admin Django omits both the lookup link and the link
        # inside <strong>. Render that stock variant, not hand-built HTML.
        site = admin.AdminSite()
        site.register(Chapter, ChapterAdmin)
        urlconf = ModuleType("chapter_only_urls")
        urlconf.urlpatterns = [url_path("admin/", site.urls)]
        settings.ROOT_URLCONF = urlconf
    chapter = mixed_name_book.chapter_set.create(number=1, title="Introduction")
    for case, page in isolation_pages(f"/admin/testapp/chapter/{chapter.pk}/change/").items():
        label = page.locator(".field-book strong", has_text=mixed_name_book.title)
        assert label.get_by_role("link").count() == int(registered)
        assert_name_bidi(label, case, "isolate")


def test_autocomplete_selection_and_result_are_isolated(isolation_pages, mixed_name_book):
    name = mixed_name_book.category.name

    def open_results(page):
        page.locator(".field-category .select2-selection").click()
        page.get_by_role("option", name=name, exact=True).wait_for()

    path = f"/admin/testapp/book/{mixed_name_book.pk}/change/"
    for case, page in isolation_pages(path, open_results).items():
        selection = page.locator(".field-category .select2-selection__rendered", has_text=name)
        assert_name_bidi(selection, case, "plaintext")
        option = page.get_by_role("option", name=name, exact=True)
        assert_name_bidi(option, case, "plaintext", stock="isolate")


def test_autocomplete_multiple_selection_is_isolated(isolation_pages, e2e_data, monkeypatch):
    # Use an existing M2M rather than add a model just to render a choice chip.
    user = e2e_data["user"]
    group = user.groups.create(name="محرر /v1.2")
    monkeypatch.setattr(admin.site._registry[type(user)], "autocomplete_fields", ("groups",))
    for case, page in isolation_pages(f"/admin/auth/user/{user.pk}/change/").items():
        choice = page.locator(".field-groups .select2-selection__choice", has_text=group.name)
        assert_name_bidi(choice, case, "plaintext", stock="isolate")
