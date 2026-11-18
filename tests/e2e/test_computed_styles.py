"""Computed-style contracts for README defects 1–6, 8 and 10 (issue #3).

Use the existing live server and Chromium fixtures, not a second browser suite.
Each check reads the same stock markup with ENABLE_CSS on and off, in ar-eg and
en. Expectations are explicit, not inferred from the stylesheet under test.

The README predates some Django changes: chevrons already mirror through bidi,
and Django 6.1 removed the double help padding. Those are stock-parity checks,
not claimed negative controls. Existing LTR differences are pinned explicitly
rather than hiding them behind a blanket "English is unchanged".
"""

from __future__ import annotations

import django
import pytest
from django.contrib import admin

from tests.testapp.models import Book

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e

CHANGELIST = "/admin/testapp/book/"
ADD_FORM = "/admin/testapp/book/add/"
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
    ltr_changes=None,
    stock_parity_reason=None,
    pseudo=None,
):
    """Pin both baselines and the fix; require a real RTL negative control.

    LTR must match stock except for specifically named, documented differences.
    A stock-parity exception must be explicit (no skip, xfail, or caught assert).
    """
    ltr = {**stock_ltr, **(ltr_changes or {})}
    expected = {
        ("ar-eg", True): rtl,
        ("ar-eg", False): stock_rtl,
        ("en", True): ltr,
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
    unchanged = stock_ltr.keys() - (ltr_changes or {}).keys()
    for property in unchanged:
        assert measured["en", True][property] == measured["en", False][property]


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
    """5.2 floats left; 6.1 uses inline-block items with no first-item margin."""
    ltr = {"float": "left", "margin-left": "5px", "margin-right": "0px"}
    stock = {**ltr, "float": "none", "margin-left": "0px"} if DJANGO_61 else ltr
    assert_contract(
        style_pages(CHANGELIST),
        ".object-tools li",
        rtl={"float": "right", "margin-left": "0px", "margin-right": "5px"},
        stock_rtl=stock,
        stock_ltr=stock,
        # The package retains its float/5px layout even on Django 6.1.
        ltr_changes=ltr if DJANGO_61 else None,
    )


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
            rtl={"margin-left": "5px", "margin-right": "0px"},
            stock_rtl=stock,
            stock_ltr=stock,
            # Intentional package normalization in LTR as well as RTL.
            ltr_changes={"margin-left": "0px", "margin-right": "5px"},
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
        rtl = {"padding-left": "0px", "padding-right": "10px"}
        stock_rtl = {"padding-left": "10px", "padding-right": "10px"}
        stock_ltr = {"padding-left": "10px", "padding-right": "3px"}
    assert_contract(
        style_pages(ADD_FORM),
        ".field-title #id_title_helptext",
        rtl=rtl,
        stock_rtl=stock_rtl,
        stock_ltr=stock_ltr,
        ltr_changes=None if DJANGO_61 else {"padding-right": "0px"},
        stock_parity_reason="Django 6.1 stacked help text has no padding" if DJANGO_61 else None,
    )


def test_defect_8_inner_help_text_unicode_bidi(style_pages):
    """unicode-bidi is not inherited: reading only .help misses this regression."""
    assert_contract(
        style_pages(ADD_FORM),
        ".field-title #id_title_helptext > div",
        rtl={"unicode-bidi": "plaintext"},
        stock_rtl={"unicode-bidi": "isolate"},
        stock_ltr={"unicode-bidi": "isolate"},
        ltr_changes={"unicode-bidi": "plaintext"},
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
        assert values["ar-eg", True]["right"] == "3px"
        assert values["ar-eg", False]["left"] == "3px"
        # The opposite inset is a used pixel value, not 'auto', and depends on
        # the glyph/font width. Do not hardcode a font-dependent 4.29688px.
        assert values["ar-eg", False]["right"] != "3px"
        assert values["ar-eg", True]["left"] != "3px"
        assert values["ar-eg", True] != values["ar-eg", False]
        assert values["en", True] == values["en", False]
        assert values["en", False]["left"] == "3px"
