"""Live slug prepopulation using Django's admin scripts in Chromium."""

import pytest
from django.contrib import admin

from django_rtl_admin import arabic_slugify
from tests.testapp.models import Article

pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_slug_preview_matches_server_and_respects_manual_edits(open_admin, lang):
    page = open_admin("/admin/testapp/article/add/", lang=lang)
    title = "مُقَـدِّمَة ١٢"
    page.locator("#id_title").focus()
    page.keyboard.insert_text(title)
    slug = page.locator("#id_slug")
    assert slug.input_value() == "mqdmh-12"
    assert page.locator("#id_unicode_slug").input_value() == "مقدمة-12"
    assert page.locator("#id_stock_slug").input_value() == ""

    subtitle = "أبجد هوز حطي كلمن"
    page.locator("#id_subtitle").fill(subtitle)
    assert slug.input_value() == arabic_slugify(f"{title} {subtitle}", max_length=20)
    slug.fill("manual-slug")
    page.locator("#id_title").fill("عنوان جديد")
    assert slug.input_value() == "manual-slug"
    assert page.locator("#id_unicode_slug").input_value() == "عنوان-جديد"
    assert not page.js_errors


def test_slug_preview_on_new_inline_rows(open_admin, monkeypatch):
    # An inline works on the change page even if the parent opts out.
    monkeypatch.setattr(admin.site._registry[Article], "bidi_transliterate_slugs", False)
    article = Article.objects.create(title="كتاب", slug="ktab")
    page = open_admin(f"/admin/testapp/article/{article.pk}/change/", lang="ar")
    inline = page.locator("#articlesection_set-group")
    inline.locator("#id_articlesection_set-0-title").fill("كِـتاب ١٢")
    assert inline.locator("#id_articlesection_set-0-slug").input_value() == "كتاب-12"

    inline.locator(".add-row a").click()
    inline.locator("#id_articlesection_set-1-title").fill("پژوهش ۱۴۰۳")
    assert inline.locator("#id_articlesection_set-1-slug").input_value() == "پژوهش-1403"
    assert inline.locator("#id_articlesection_set-0-slug").input_value() == "كتاب-12"
    assert not page.js_errors


def test_blank_slug_of_existing_record_is_not_prepopulated(open_admin):
    article = Article.objects.create(title="كتاب", slug="ktab", unicode_slug="")
    page = open_admin(f"/admin/testapp/article/{article.pk}/change/", lang="ar")
    page.locator("#id_title").fill("كتاب جديد ١٢")
    page.locator("#id_subtitle").focus()
    assert page.locator("#id_unicode_slug").input_value() == ""
    assert not page.js_errors
