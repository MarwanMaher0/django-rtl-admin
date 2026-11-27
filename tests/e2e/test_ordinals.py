"""Browser e2e test for an Arabic ordinal column in a right-to-left changelist."""

import pytest

from tests.testapp.models import Chapter

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e

CHANGELIST = "/admin/testapp/chapter/"


def test_arabic_ordinals_are_shown_in_an_rtl_changelist_column(open_admin, e2e_data, snapshot):
    # The shared data already has chapters 1 and 2 of this book.
    for number in (11, 21, 100, 125):
        Chapter.objects.create(book=e2e_data["book"], number=number, title=f"الفصل {number}")
    ordinals = [
        "الأول",
        "الثاني",
        "الحادي عشر",
        "الحادي والعشرون",
        "المئة",
        "المئة والخامس والعشرون",
    ]

    page = open_admin(CHANGELIST, lang="ar")
    assert page.locator("html").get_attribute("dir") == "rtl"
    cells = page.locator("#result_list tbody td.field-number")
    assert cells.all_inner_texts() == ordinals
    snapshot(page, "ordinal-column")

    # The column is laid out right to left: it sits to the left of the title
    # column that precedes it, and its text is visible and right-aligned.
    cell = cells.first
    assert cell.is_visible()
    assert cell.evaluate("el => getComputedStyle(el).direction") == "rtl"
    assert cell.evaluate("el => getComputedStyle(el).textAlign") in {"right", "start"}
    title = page.locator("#result_list tbody th.field-title").first.bounding_box()
    box = cell.bounding_box()
    assert box["x"] + box["width"] <= title["x"] + 1

    # The header still sorts by the number behind the words.
    header = page.locator("#result_list thead th.column-number")
    assert "sortable" in header.get_attribute("class").split()
    with page.expect_navigation():
        header.locator(".text a").click()
    page.wait_for_load_state("load")
    assert "o=-2" in page.url
    assert page.locator("#result_list tbody td.field-number").all_inner_texts() == ordinals[::-1]
    assert not page.js_errors
