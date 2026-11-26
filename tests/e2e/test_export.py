"""CSV export from an Arabic changelist, end to end in a real browser."""

from __future__ import annotations

import csv
import io

import pytest

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

CHANGELIST = "/admin/testapp/book/"
ISOLATES = "\u2066\u2067\u2068\u2069\u200e\u200f\u061c"


def test_csv_export_downloads_the_selected_rows_in_arabic(open_admin, snapshot, tmp_path):
    page = open_admin(CHANGELIST, lang="ar")
    assert page.locator("html").get_attribute("dir") == "rtl"

    rows = page.locator("#result_list tbody tr")
    for title in ("Guns, Germs, and Steel", "Dune"):
        rows.filter(has_text=title).locator("input.action-select").check()
    counter = page.locator("#changelist-form .actions .action-counter")
    assert "٢" in counter.inner_text() or "2" in counter.inner_text()

    actions = page.locator("#changelist-form .actions")
    actions.locator("select[name=action]").select_option("export_as_csv")
    snapshot(page, "export-selected")
    with page.expect_download() as download_info:
        actions.locator("button[type=submit], input[type=submit]").first.click()
    download = download_info.value
    assert download.suggested_filename == "books.csv"

    path = tmp_path / "export.csv"
    download.save_as(str(path))
    data = path.read_bytes()
    # UTF-8 BOM so Excel detects the encoding.
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert not any(char in text for char in ISOLATES)

    table = list(csv.reader(io.StringIO(text)))
    assert table[0] == ["title", "ISBN", "category", "status", "published on", "price"]
    assert len(table) == 3  # header + the two selected rows only
    by_title = {row[0]: row for row in table[1:]}
    assert set(by_title) == {"Guns, Germs, and Steel", "Dune"}
    guns = by_title["Guns, Germs, and Steel"]
    assert guns[1] == "978-0-393-31755-8"
    assert guns[2] == "تاريخ"
    assert guns[3] == "Draft"
    assert guns[4] == "2025-08-10"
    assert guns[5] == "127.50"
    dune = by_title["Dune"]
    assert dune[2] == "Fiction"
    assert dune[4] == "2024-10-10"
    assert dune[5] == "129.50"
    assert not page.js_errors
