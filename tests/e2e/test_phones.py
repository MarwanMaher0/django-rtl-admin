"""Browser e2e test for submitting an Arabic-Indic phone number in an admin form."""

import pytest

from tests.testapp.models import Contact

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e


def test_submit_arabic_indic_phone_in_admin_change_form(open_admin):
    contact = Contact.objects.create(name="أحمد المنصور", phone="+966501111111")
    page = open_admin(f"/admin/testapp/contact/{contact.pk}/change/", lang="ar")

    phone_input = page.locator("#id_phone")
    assert phone_input.get_attribute("dir") == "ltr"
    assert phone_input.get_attribute("inputmode") == "tel"
    assert phone_input.get_attribute("autocomplete") == "tel"

    phone_input.fill("٠٥٥ ١٢٣-٤٥٦٧")
    page.locator('input[name="_save"]').click()
    page.wait_for_url("**/admin/testapp/contact/")

    contact.refresh_from_db()
    assert contact.phone == "+966551234567"
    assert not page.js_errors
