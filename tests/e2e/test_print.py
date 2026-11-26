"""End-to-end checks of the print stylesheet in Arabic (RTL) and English (LTR)."""

from __future__ import annotations

import pytest

from .layout import assert_no_horizontal_overflow, assert_precedes, box

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

LANGS = ("en", "ar")
CHANGELIST = "/admin/testapp/book/"


def change_form(book):
    return f"/admin/testapp/book/{book.pk}/change/"


def assert_hidden_in_print(page, selectors, where):
    """Every matched element must be hidden with ``display: none`` in print media."""
    for selector in selectors:
        locator = page.locator(selector)
        assert locator.count() >= 1, f"{where}: selector {selector!r} matched no elements"
        for index in range(locator.count()):
            item = locator.nth(index)
            assert not item.is_visible(), f"{where}: {selector}[{index}] is still visible in print"
            display = item.evaluate("el => getComputedStyle(el).display")
            assert display == "none", (
                f"{where}: {selector}[{index}] has display={display!r}, expected 'none'"
            )


@pytest.mark.parametrize("lang", LANGS)
def test_changelist_print_media(open_admin, snapshot, lang):
    page = open_admin(CHANGELIST, lang=lang)
    sheet = page.locator(
        'link[rel="stylesheet"][media="print"][href$="django_rtl_admin/css/print.css"]'
    )
    assert sheet.count() == 1
    assert sheet.evaluate("el => el.sheet !== null"), "print.css did not load"

    page.emulate_media(media="print")

    where = f"print changelist [{lang}]"
    assert_hidden_in_print(
        page,
        [
            "#nav-sidebar",
            "#toggle-nav-sidebar",
            "#header",
            "#user-tools",
            ".rtl-admin-language-switcher",
            ".breadcrumbs",
            ".object-tools",
            "#changelist-form .actions",
            "#changelist-filter",
            "#toolbar",
            "#changelist-search",
            ".paginator",
            "#result_list .action-checkbox-column",
            "#result_list .action-checkbox",
        ],
        where,
    )

    assert page.locator("#content h1").is_visible()
    assert page.locator("#result_list").is_visible()
    rows = page.locator("#result_list tbody tr")
    assert rows.count() == 5
    assert rows.first.is_visible()

    thead_display = page.locator("#result_list thead").evaluate(
        "el => getComputedStyle(el).display"
    )
    assert thead_display == "table-header-group", f"{where}: thead display={thead_display!r}"

    row_break = rows.first.evaluate("el => getComputedStyle(el).breakInside")
    assert row_break == "avoid", f"{where}: row break-inside={row_break!r}"

    first_cell = page.locator("#result_list tbody td").first
    cell_styles = first_cell.evaluate(
        "el => ({unicodeBidi: getComputedStyle(el).unicodeBidi, "
        "whiteSpace: getComputedStyle(el).whiteSpace, "
        "overflowWrap: getComputedStyle(el).overflowWrap})"
    )
    assert cell_styles["unicodeBidi"] == "isolate", f"{where}: {cell_styles}"
    assert cell_styles["whiteSpace"] == "normal", f"{where}: {cell_styles}"
    assert cell_styles["overflowWrap"] in {"break-word", "anywhere"}, f"{where}: {cell_styles}"

    results_overflow = page.locator("#changelist .results").evaluate(
        "el => getComputedStyle(el).overflow"
    )
    assert results_overflow == "visible", f"{where}: .results overflow={results_overflow!r}"

    first_link_after = page.locator("#result_list tbody th a").first.evaluate(
        "el => getComputedStyle(el, '::after').content"
    )
    assert first_link_after == "none", f"{where}: link ::after content={first_link_after!r}"

    visible_headers = page.locator("#result_list thead th:visible")
    assert visible_headers.count() >= 2
    first_col = box(visible_headers.nth(0))
    second_col = box(visible_headers.nth(1))
    last_col = box(visible_headers.last)
    assert_precedes(first_col, second_col, lang, f"{where} column order")
    if lang == "ar":
        assert first_col.center_x > last_col.center_x, (
            f"{where}: first column is not on the right in RTL ({first_col} vs {last_col})"
        )
    else:
        assert first_col.center_x < last_col.center_x, (
            f"{where}: first column is not on the left in LTR ({first_col} vs {last_col})"
        )

    assert not page.js_errors, f"{where}: JavaScript errors {page.js_errors}"
    assert_no_horizontal_overflow(page, where)
    snapshot(page, f"print-changelist-{lang}")


@pytest.mark.parametrize("lang", LANGS)
def test_change_form_print_media(open_admin, e2e_data, snapshot, lang):
    page = open_admin(change_form(e2e_data["book"]), lang=lang)
    page.emulate_media(media="print")

    where = f"print change form [{lang}]"
    assert_hidden_in_print(
        page,
        [
            "#nav-sidebar",
            "#toggle-nav-sidebar",
            "#header",
            "#user-tools",
            ".rtl-admin-language-switcher",
            ".breadcrumbs",
            ".object-tools",
            ".submit-row",
            "#chapter_set-group .add-row",
            "#review_set-group .add-row",
            "#chapter_set-group td.delete",
            "#chapter_set-group thead th:last-child",
            "#review_set-group .inline-related h3 span.delete",
            ".datetimeshortcuts",
        ],
        where,
    )

    assert page.locator("#content h1").is_visible()
    assert page.locator("#id_title").is_visible()
    assert page.locator("#id_isbn").is_visible()
    readonly = page.locator(".field-archive_note .readonly")
    assert readonly.is_visible()
    assert readonly.evaluate("el => getComputedStyle(el).unicodeBidi") == "plaintext"

    fieldset_break = page.locator("#book_form > div > fieldset").first.evaluate(
        "el => getComputedStyle(el).breakInside"
    )
    assert fieldset_break == "avoid", f"{where}: fieldset break-inside={fieldset_break!r}"

    tabular = page.locator("#chapter_set-group table")
    assert tabular.is_visible()
    inline_thead_display = tabular.locator("thead").evaluate("el => getComputedStyle(el).display")
    assert inline_thead_display == "table-header-group", (
        f"{where}: inline thead display={inline_thead_display!r}"
    )

    inline_row_break = tabular.locator("tbody tr.has_original").first.evaluate(
        "el => getComputedStyle(el).breakInside"
    )
    assert inline_row_break == "avoid", f"{where}: inline row break-inside={inline_row_break!r}"

    inline_cell_bidi = tabular.locator("tbody tr.has_original td.field-title").first.evaluate(
        "el => getComputedStyle(el).unicodeBidi"
    )
    assert inline_cell_bidi == "isolate", f"{where}: inline cell unicode-bidi={inline_cell_bidi!r}"

    inline_headers = tabular.locator("thead th:visible")
    assert inline_headers.count() >= 2
    first_inline_col = box(inline_headers.nth(0))
    second_inline_col = box(inline_headers.nth(1))
    assert_precedes(first_inline_col, second_inline_col, lang, f"{where} inline columns")

    stacked = page.locator("#review_set-group .inline-related.has_original").first
    assert stacked.is_visible()

    assert not page.js_errors, f"{where}: JavaScript errors {page.js_errors}"
    assert_no_horizontal_overflow(page, where)
    snapshot(page, f"print-change-form-{lang}")


def test_arabic_changelist_pdf_render_smoke(open_admin, artifacts_dir):
    page = open_admin(CHANGELIST, lang="ar")
    pdf_bytes = page.pdf(format="A4", print_background=False)
    assert pdf_bytes.startswith(b"%PDF-"), "page.pdf() did not return a PDF document"
    assert b"%%EOF" in pdf_bytes, "page.pdf() output is missing PDF EOF marker"
    assert len(pdf_bytes) > 1000, f"PDF output unexpectedly small ({len(pdf_bytes)} bytes)"
    (artifacts_dir / "arabic-changelist.pdf").write_bytes(pdf_bytes)
    assert not page.js_errors, f"JavaScript errors {page.js_errors}"
