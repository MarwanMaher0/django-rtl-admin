"""WCAG checks of the stock admin views through axe-core and Playwright."""

from __future__ import annotations

import re

import pytest

from .conftest import WIDTHS

pytest.importorskip("playwright.sync_api")
axe_playwright = pytest.importorskip("axe_playwright_python.sync_playwright")

pytestmark = pytest.mark.e2e

AXE = axe_playwright.Axe()
AXE_OPTIONS = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
    },
    "resultTypes": ["violations"],
}


@pytest.mark.parametrize("view", ["changelist", "change-form", "delete-confirmation"])
@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_admin_accessibility(open_admin, e2e_data, artifacts_dir, request, view, lang, scheme):
    change_form = f"/admin/testapp/book/{e2e_data['book'].pk}/change/"
    paths = {
        "changelist": "/admin/testapp/book/",
        "change-form": change_form,
        "delete-confirmation": f"{change_form}delete/",
    }
    for width in WIDTHS:
        page = open_admin(paths[view], lang=lang, scheme=scheme, width=width)
        results = AXE.run(page, options=AXE_OPTIONS)
        where = f"{view} [{lang}, {scheme}, {width}px]"
        if results.violations_count:
            name = re.sub(r"[^\w.-]+", "_", request.node.name).strip("_")
            report = artifacts_dir / f"{name}-{width}px.json"
            results.save_to_file(report, violations_only=True)
        assert results.violations_count == 0, f"{where}\n{results.generate_report()}"
