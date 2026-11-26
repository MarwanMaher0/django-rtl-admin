"""``BidiSafeAdminMixin`` applied to a real changelist."""

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace

import django
import pytest
from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.models import LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.utils import display_for_field
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, models
from django.test import RequestFactory, override_settings
from django.urls import include, path
from django.utils import formats, translation
from django.utils.html import format_html
from django.utils.safestring import SafeData, mark_safe
from django.utils.translation import gettext

from django_rtl_admin import BidiSafeAdminMixin, numbering_system, transliterate_digits
from django_rtl_admin.bidi import FSI, ISOLATE_OPENERS, LRI, PDI, RLI, isolate
from django_rtl_admin.mixins import _SUCCESS_MESSAGES, _localize_cell_digits

from .testapp.admin import BidiThingAdmin, BookAdmin, InputBookAdmin, LocalizedInputBookAdmin
from .testapp.models import Article, ArticleSection, Book, Category, Chapter, Review, Thing

pytestmark = pytest.mark.django_db

ARABIC = "التعلم"
CHANGELIST_URL = "/admin/testapp/thing/"
BOOK_CHANGELIST_URL = "/admin/testapp/book/"


def make_admin(**attrs):
    cls = type("TempAdmin", (BidiSafeAdminMixin, admin.ModelAdmin), attrs)
    return cls(Thing, AdminSite())


def request_for(user):
    request = RequestFactory().get(CHANGELIST_URL)
    request.user = user
    return request


# -- slug prepopulation ---------------------------------------------------


ARTICLE_ADD_URL = "/admin/testapp/article/add/"
SLUG_SCRIPT = "django_rtl_admin/js/slug.js"


def article_data(**overrides):
    return {
        "title": "مُقَـدِّمَة ١٢",
        "subtitle": "جديدة",
        "slug": "",
        "unicode_slug": "",
        "stock_slug": "",
        "articlesection_set-TOTAL_FORMS": "2",
        "articlesection_set-INITIAL_FORMS": "0",
        "articlesection_set-0-title": "پژوهش ۱۴۰۳",
        "articlesection_set-0-slug": "",
        "articlesection_set-1-title": "",
        "articlesection_set-1-slug": "",
        **overrides,
    }


def test_admin_add_fills_empty_slugs_before_validation(admin_client):
    form_page = admin_client.get(ARTICLE_ADD_URL)
    assert tuple(form_page.context["media"]._js).count(SLUG_SCRIPT) == 1
    form = form_page.context["adminform"].form
    assert 'data-rtl-slug="ascii"' in str(form["slug"])
    assert 'data-rtl-slug="unicode"' in str(form["unicode_slug"])
    assert "required" not in str(form["slug"])
    assert form.fields["slug"].required
    assert "data-rtl-slug" not in str(form["stock_slug"])
    assert SLUG_SCRIPT not in make_admin().media._js

    response = admin_client.post(ARTICLE_ADD_URL, article_data())
    assert response.status_code == 302
    article = Article.objects.get()
    assert article.title == "مُقَـدِّمَة ١٢"
    assert article.slug == "mqdmh-12-jdydh"
    assert article.unicode_slug == "مقدمة-12"
    assert article.stock_slug == ""
    assert list(ArticleSection.objects.values_list("article_id", "slug")) == [
        (article.pk, "پژوهش-1403")
    ]


def test_explicit_slug_is_preserved_and_existing_slugs_are_not_regenerated(admin_client):
    response = admin_client.post(ARTICLE_ADD_URL, article_data(slug="my-manual-slug"))
    assert response.status_code == 302
    article = Article.objects.get(slug="my-manual-slug")
    change_url = f"/admin/testapp/article/{article.pk}/change/"
    form = admin_client.get(change_url).context["adminform"].form
    assert 'data-rtl-slug="off"' in str(form["slug"])

    data = article_data(title="عنوان جديد", unicode_slug=article.unicode_slug)
    data.update({"articlesection_set-TOTAL_FORMS": "0"})
    response = admin_client.post(change_url, data)
    assert response.context["adminform"].form.errors.as_data()["slug"][0].code == "required"
    article.refresh_from_db()
    assert article.slug == "my-manual-slug"


def test_custom_admin_form_fields_are_preserved(admin_user):
    class CustomFormAdmin(admin.ModelAdmin):
        def get_form(self, request, obj=None, change=False, **kwargs):
            form = super().get_form(request, obj, change=change, **kwargs)
            form.base_fields["slug"].disabled = True
            return form

    class CustomArticleAdmin(BidiSafeAdminMixin, CustomFormAdmin):
        prepopulated_fields = {"slug": ("title",)}

    model_admin = CustomArticleAdmin(Article, AdminSite())
    form = model_admin.get_form(request_for(admin_user), fields=("title", "slug"))()
    assert form.fields["slug"].disabled
    assert 'data-rtl-slug="off"' in str(form["slug"])


def test_request_specific_prepopulated_fields_load_script(admin_client, monkeypatch):
    model_admin = admin.site._registry[Article]
    monkeypatch.setattr(model_admin, "prepopulated_fields", {})
    monkeypatch.setattr(model_admin, "get_prepopulated_fields", lambda *_: {"slug": ("title",)})
    monkeypatch.setattr(model_admin, "inlines", ())
    assert SLUG_SCRIPT not in model_admin.media._js
    page = admin_client.get(ARTICLE_ADD_URL)
    assert SLUG_SCRIPT in page.context["media"]._js
    assert 'data-rtl-slug="ascii"' in str(page.context["adminform"].form["slug"])


def test_generated_slug_goes_through_uniqueness_validation(admin_client):
    Article.objects.create(title="مقدمة", slug="mqdmh-12-jdydh")
    response = admin_client.post(ARTICLE_ADD_URL, article_data())
    assert response.context["adminform"].form.errors.as_data()["slug"][0].code == "unique"
    assert Article.objects.count() == 1
    assert not ArticleSection.objects.exists()


@pytest.mark.parametrize(
    ("global_setting", "override"), [(False, None), (True, False), (False, True)]
)
def test_admin_slug_setting_can_be_overridden(admin_client, monkeypatch, global_setting, override):
    model_admin = admin.site._registry[Article]
    monkeypatch.setattr(model_admin, "bidi_transliterate_slugs", override)
    with override_settings(RTL_ADMIN={"TRANSLITERATE_SLUGS": global_setting}):
        assert (SLUG_SCRIPT in model_admin.media._js) is (override is True)
        response = admin_client.post(
            ARTICLE_ADD_URL, article_data(**{"articlesection_set-TOTAL_FORMS": "0"})
        )
    if override is True:
        assert response.status_code == 302
        assert Article.objects.get().slug == "mqdmh-12-jdydh"
    else:
        form = response.context["adminform"].form
        assert form.errors.as_data()["slug"][0].code == "required"
        assert "data-rtl-slug" not in str(form["slug"])


# -- list_display rewriting ------------------------------------------------


def test_list_display_entries_become_isolating_wrappers(admin_user):
    model_admin = make_admin(list_display=("name", "reference"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert all(callable(entry) for entry in display)
    assert [entry.__name__ for entry in display] == ["name", "reference"]


def test_wrappers_keep_the_column_labels(admin_user):
    model_admin = make_admin(list_display=("name", "reference"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert [str(entry.short_description) for entry in display] == ["name", "reference"]


def test_wrappers_keep_the_sort_field(admin_user):
    model_admin = make_admin(list_display=("name",))
    (wrapper,) = model_admin.get_list_display(request_for(admin_user))
    assert wrapper.admin_order_field == "name"


def test_wrappers_are_cached_so_identity_is_stable(admin_user):
    model_admin = make_admin(list_display=("name",))
    request = request_for(admin_user)
    assert model_admin.get_list_display(request) == model_admin.get_list_display(request)


def test_list_display_links_are_translated_to_the_same_wrappers(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), list_display_links=("reference",))
    request = request_for(admin_user)
    display = model_admin.get_list_display(request)
    links = model_admin.get_list_display_links(request, display)
    assert links[0] is display[1]


def test_sortable_by_is_translated_too(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), sortable_by=("name",))
    request = request_for(admin_user)
    display = model_admin.get_list_display(request)
    assert model_admin.get_sortable_by(request)[0] is display[0]


def test_boolean_columns_are_left_alone(admin_user):
    model_admin = make_admin(list_display=("name", "is_active"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "is_active"


def test_list_editable_columns_are_left_alone(admin_user):
    model_admin = make_admin(
        list_display=("name", "reference"),
        list_display_links=("name",),
        list_editable=("reference",),
    )
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "reference"


def test_excluded_columns_are_left_alone(admin_user):
    model_admin = make_admin(
        list_display=("name", "reference"), bidi_isolate_exclude=("reference",)
    )
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "reference"


def test_bidi_isolate_fields_restricts_the_set(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), bidi_isolate_fields=("reference",))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[0] == "name"
    assert callable(display[1])


def test_the_mixin_can_be_switched_off_per_admin(admin_user):
    model_admin = make_admin(list_display=("name",), bidi_isolate_changelist=False)
    assert model_admin.get_list_display(request_for(admin_user)) == ("name",)


@override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False})
def test_the_mixin_can_be_switched_off_globally(admin_user):
    model_admin = make_admin(list_display=("name",))
    assert model_admin.get_list_display(request_for(admin_user)) == ("name",)


def test_callables_already_in_list_display_are_passed_through(admin_user):
    def custom(obj):
        return obj.name

    model_admin = make_admin(list_display=(custom,))
    assert model_admin.get_list_display(request_for(admin_user)) == (custom,)


# -- rendered output -------------------------------------------------------


def test_changelist_cells_are_isolated(admin_client, thing):
    response = admin_client.get(CHANGELIST_URL)
    assert response.status_code == 200
    html = response.content.decode()
    assert FSI + "978-0-262-03561-3" + PDI in html
    assert FSI + thing.name_ar + PDI in html


def test_changelist_keeps_the_admin_column_css_classes(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert 'class="field-reference"' in html
    assert "column-reference" in html


def test_changelist_keeps_the_sort_links(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "sortable column-name" in html


def test_changelist_keeps_the_link_to_the_change_form(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert f'href="/admin/testapp/thing/{thing.pk}/change/"' in html


def test_changelist_still_renders_the_boolean_icon(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "icon-yes" in html


def test_html_in_a_value_stays_escaped_in_the_changelist(admin_client):
    Thing.objects.create(name="<script>alert(1)</script>", reference="x")
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_an_empty_value_is_not_isolated(admin_client):
    Thing.objects.create(name="Empty", reference="")
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert FSI + PDI not in html


def test_embedded_bidi_controls_are_stripped_in_the_changelist(admin_client):
    Thing.objects.create(name="Spoofed", reference="REF-\u202e42\u2069-OK")
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "\u202e" not in html
    assert FSI + "REF-42-OK" + PDI in html


def test_a_custom_display_method_is_isolated_too(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert FSI + "DEEP LEARNING" + PDI in html


def test_sorting_by_an_isolated_column_still_works(admin_client, thing):
    Thing.objects.create(name="Alpha", reference="a")
    response = admin_client.get(CHANGELIST_URL, {"o": "1"})
    assert response.status_code == 200
    names = [obj.name for obj in response.context["cl"].result_list]
    assert names == sorted(names)


def test_searching_still_works(admin_client, thing):
    response = admin_client.get(CHANGELIST_URL, {"q": "978-0-262"})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 1


# -- related lookups ---------------------------------------------------------

related_lookups = pytest.mark.skipif(
    django.VERSION < (5, 1), reason="list_display accepts related lookups on Django 5.1+"
)


def make_book_admin(**attrs):
    attrs.setdefault("actions", None)
    cls = type("TempBookAdmin", (BidiSafeAdminMixin, admin.ModelAdmin), attrs)
    return cls(Book, admin.site)


def render_book_changelist(model_admin, user, **params):
    request = RequestFactory().get(BOOK_CHANGELIST_URL, params)
    request.user = user
    response = model_admin.changelist_view(request)
    response.render()
    return response


@pytest.fixture
def books(db):
    zeta = Category.objects.create(name="Zeta", is_featured=True)
    alpha = Category.objects.create(name="Alpha")
    middle = Category.objects.create(name=ARABIC)
    Book.objects.create(title="A first", isbn="1", category=zeta)
    Book.objects.create(title="B second", isbn="2", category=alpha)
    Book.objects.create(title="C third", isbn="3", category=middle)
    Book.objects.create(title="D fourth", isbn="4", category=None)


@related_lookups
def test_a_related_lookup_keeps_its_sort_field(admin_user):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1].__name__ == "category__name"
    assert display[1].admin_order_field == "category__name"


@related_lookups
def test_a_related_lookup_column_has_a_sort_link(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    html = render_book_changelist(model_admin, admin_user).content.decode()
    assert "sortable column-category__name" in html
    assert 'class="field-category__name"' in html


@related_lookups
@pytest.mark.parametrize(("order", "reverse"), [("1", False), ("-1", True)])
def test_sorting_by_a_related_lookup_orders_the_rows(admin_user, books, order, reverse):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    response = render_book_changelist(model_admin, admin_user, o=order)
    assert response.status_code == 200
    names = [
        book.category.name
        for book in response.context_data["cl"].result_list
        if book.category is not None
    ]
    assert names == sorted(names, reverse=reverse)
    assert len(names) == 3


@related_lookups
def test_a_related_lookup_value_is_isolated(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    html = render_book_changelist(model_admin, admin_user).content.decode()
    assert FSI + "Alpha" + PDI in html
    assert FSI + ARABIC + PDI in html
    assert FSI + PDI not in html


@related_lookups
def test_a_boolean_field_at_the_end_of_a_lookup_is_left_alone(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__is_featured"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "category__is_featured"
    response = render_book_changelist(model_admin, admin_user)
    assert response.status_code == 200


@pytest.mark.skipif(django.VERSION >= (5, 1), reason="behaviour before Django 5.1")
def test_a_related_lookup_is_not_resolved_before_django_5_1(admin_user):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    assert model_admin._bidi_model_field("category__name") is None
    assert model_admin._bidi_order_field("category__name", None, None) is None
    with pytest.raises(AttributeError, match="Unable to lookup 'category__name'"):
        model_admin.get_list_display(request_for(admin_user))


# -- readonly_fields on the change form --------------------------------------


def render_change(model_admin, obj, user, *, lang="en"):
    request = RequestFactory().get(f"/admin/testapp/{obj._meta.model_name}/{obj.pk}/change/")
    request.user = user
    with translation.override(lang):
        response = model_admin.changeform_view(request, str(obj.pk))
        response.render()
    return response


@pytest.mark.parametrize("lang", ["ar-eg", "en"])
def test_readonly_field_with_arabic_and_embedded_path_isolates_the_path(admin_user, lang):
    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="نُقل الملف إلى /srv/archive/2024-03-05",
    )
    model_admin = make_book_admin(
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    html = render_change(model_admin, book, admin_user, lang=lang).content.decode()
    assert f"نُقل الملف إلى {LRI}/srv/archive/2024-03-05{PDI}" in html


def test_readonly_field_with_english_and_embedded_arabic_isolates_arabic(admin_user):
    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="Archived under قسم المخطوطات today",
    )
    model_admin = make_book_admin(
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    html = render_change(model_admin, book, admin_user, lang="en").content.decode()
    assert f"Archived under {RLI}قسم المخطوطات{PDI} today" in html


def test_readonly_multiline_text_isolates_each_paragraph_and_renders_br(admin_user):
    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        summary="نُقل إلى /srv/archive/2024-03-05\r\nFiled under قسم المخطوطات\n2024-03-05",
    )
    model_admin = make_book_admin(
        readonly_fields=("summary",),
        fields=("title", "summary"),
    )
    html = render_change(model_admin, book, admin_user, lang="ar-eg").content.decode()
    expected = (
        f"نُقل إلى {LRI}/srv/archive/2024-03-05{PDI}"
        f"<br>Filed under {RLI}قسم المخطوطات{PDI}"
        f"<br>{LRI}2024-03-05{PDI}"
    )
    assert expected in html


def test_readonly_label_help_text_and_css_classes_match_stock_admin(admin_user):
    import re

    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="Plain ASCII note",
    )
    stock_cls = type(
        "StockBookAdmin",
        (admin.ModelAdmin,),
        {
            "readonly_fields": ("isbn", "archive_note"),
            "fieldsets": ((None, {"fields": (("title", "isbn"), "archive_note")}),),
        },
    )
    stock_admin = stock_cls(Book, admin.site)
    bidi_admin = make_book_admin(
        readonly_fields=("isbn", "archive_note"),
        fieldsets=((None, {"fields": (("title", "isbn"), "archive_note")}),),
    )

    def scrub_csrf(s: str) -> str:
        return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"', s)

    stock_html = scrub_csrf(
        render_change(stock_admin, book, admin_user, lang="en").content.decode()
    )
    bidi_html = scrub_csrf(render_change(bidi_admin, book, admin_user, lang="en").content.decode())
    assert bidi_html == stock_html
    assert "field-archive_note" in bidi_html
    assert "Provenance note with archive path and date." in bidi_html
    request = RequestFactory().get(f"/admin/testapp/book/{book.pk}/change/")
    request.user = admin_user
    resp = bidi_admin.changeform_view(request, str(book.pk))
    assert repr(resp.context_data["adminform"]).startswith("<AdminForm:")
    assert resp.context_data["adminform"].errors == {}


def test_html_in_a_readonly_value_stays_escaped(admin_user):
    book = Book.objects.create(
        title="XSS",
        isbn="978-0-691-16628-5",
        archive_note='نُقل <script>alert("xss")</script> إلى /srv/archive',
    )
    model_admin = make_book_admin(
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    html = render_change(model_admin, book, admin_user, lang="ar-eg").content.decode()
    assert '<script>alert("xss")</script>' not in html
    assert f"{LRI}&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;{PDI}" in html
    assert f"{LRI}/srv/archive{PDI}" in html


def test_embedded_bidi_controls_are_stripped_in_readonly_values(admin_user):
    book = Book.objects.create(
        title="Spoofed",
        isbn="978-0-691-16628-5",
        archive_note="نُقل إلى /srv/\u202earchive\u2069/file.pdf",
    )
    model_admin = make_book_admin(
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    html = render_change(model_admin, book, admin_user, lang="ar-eg").content.decode()
    assert "\u202e" not in html
    assert f"{LRI}/srv/archive/file.pdf{PDI}" in html


def test_readonly_boolean_safestring_empty_and_callable_values(admin_user):
    category = Category.objects.create(name="تاريخ / History", is_featured=True)
    thing = Thing.objects.create(name="Widget", reference="", is_active=True)

    def callable_note(obj):
        return "مرجع /ref/2024-03-05"

    @admin.display(boolean=True, description="Flag")
    def callable_flag(self, obj):
        return True

    @admin.display(description="Safe link")
    def safe_badge(self, obj):
        return format_html('<span class="badge">{}</span>', "v1.2.3")

    @admin.display(description="Safe plain")
    def safe_plain(self, obj):
        return mark_safe("نُقل /srv/safe/2024-03-05")

    @admin.display(description="Nothing")
    def none_value(self, obj):
        return None

    @admin.display(description="Blank")
    def blank_value(self, obj):
        return ""

    class HtmlObj:
        def __html__(self):
            return mark_safe("<em>custom-html</em>")

    @admin.display(description="Dunder HTML")
    def dunder_html(self, obj):
        return HtmlObj()

    def missing_attr_lookup(obj):
        raise ObjectDoesNotExist

    model_admin = make_admin(
        readonly_fields=(
            "is_active",
            "reference",
            "published_on",
            callable_note,
            "callable_flag",
            "safe_badge",
            "safe_plain",
            "none_value",
            "blank_value",
            "dunder_html",
            missing_attr_lookup,
        ),
        fields=(
            "name",
            "is_active",
            "reference",
            "published_on",
            callable_note,
            "callable_flag",
            "safe_badge",
            "safe_plain",
            "none_value",
            "blank_value",
            "dunder_html",
            missing_attr_lookup,
        ),
        callable_flag=callable_flag,
        safe_badge=safe_badge,
        safe_plain=safe_plain,
        none_value=none_value,
        blank_value=blank_value,
        dunder_html=dunder_html,
    )
    html = render_change(model_admin, thing, admin_user, lang="ar-eg").content.decode()
    assert "icon-yes" in html
    assert f"مرجع {LRI}/ref/2024-03-05{PDI}" in html
    assert '<span class="badge">v1.2.3</span>' in html
    assert "نُقل /srv/safe/2024-03-05" in html
    assert f"{LRI}/srv/safe/2024-03-05{PDI}" not in html
    assert "<em>custom-html</em>" in html
    assert LRI + "-" + PDI not in html

    # ForeignKey readonly field renders an admin change link (SafeString) untouched.
    book = Book.objects.create(title="History Book", isbn="123", category=category)
    book_admin = make_book_admin(
        readonly_fields=("category",),
        fields=("title", "category"),
    )
    book_html = render_change(book_admin, book, admin_user, lang="ar-eg").content.decode()
    assert f'href="/admin/testapp/category/{category.pk}/change/"' in book_html


def test_readonly_m2m_and_password_hash_are_handled(admin_user):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.forms import UserChangeForm
    from django.contrib.auth.models import Group

    User = get_user_model()
    group = Group.objects.create(name="مجموعة /ops/2024-03-05")
    admin_user.groups.add(group)

    user_admin_cls = type(
        "TempUserAdmin",
        (BidiSafeAdminMixin, admin.ModelAdmin),
        {
            "form": UserChangeForm,
            "readonly_fields": ("groups", "password"),
            "fields": ("username", "groups", "password"),
        },
    )
    user_admin = user_admin_cls(User, admin.site)
    request = RequestFactory().get(f"/admin/auth/user/{admin_user.pk}/change/")
    request.user = admin_user
    with translation.override("ar-eg"):
        response = user_admin.changeform_view(request, str(admin_user.pk))
        response.render()
    html = response.content.decode()
    assert f"مجموعة {LRI}/ops/2024-03-05{PDI}" in html
    assert "<strong>" in html


def test_readonly_isolation_opt_outs_and_exclusions(admin_user):
    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="نُقل الملف إلى /srv/archive/2024-03-05",
        summary="ملاحظة /tmp/2024-03-05",
    )

    def custom_note(obj):
        return "ملاحظة دالة /var/log/2024-03-05"

    # Opt-out via per-admin attribute.
    off_admin = make_book_admin(
        bidi_isolate_readonly=False,
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    off_html = render_change(off_admin, book, admin_user, lang="ar-eg").content.decode()
    assert LRI not in off_html

    # Opt-out via global RTL_ADMIN["ISOLATE_READONLY_FIELDS"] = False.
    default_admin = make_book_admin(
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    with override_settings(RTL_ADMIN={"ISOLATE_READONLY_FIELDS": False}):
        global_off_html = render_change(
            default_admin, book, admin_user, lang="ar-eg"
        ).content.decode()
    assert LRI not in global_off_html

    # Explicit per-admin True overrides global False.
    forced_on_admin = make_book_admin(
        bidi_isolate_readonly=True,
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    with override_settings(RTL_ADMIN={"ISOLATE_READONLY_FIELDS": False}):
        forced_on_html = render_change(
            forced_on_admin, book, admin_user, lang="ar-eg"
        ).content.decode()
    assert f"نُقل الملف إلى {LRI}/srv/archive/2024-03-05{PDI}" in forced_on_html

    # bidi_isolate_exclude honours both field names and callable names;
    # bidi_isolate_fields restricts list_display only, not readonly_fields.
    excluded_admin = make_book_admin(
        bidi_isolate_fields=("isbn",),
        bidi_isolate_exclude=("archive_note", "custom_note"),
        readonly_fields=("archive_note", "summary", custom_note),
        fields=("title", "archive_note", "summary", custom_note),
    )
    excluded_html = render_change(excluded_admin, book, admin_user, lang="ar-eg").content.decode()
    assert f"{LRI}/srv/archive/2024-03-05{PDI}" not in excluded_html
    assert f"{LRI}/var/log/2024-03-05{PDI}" not in excluded_html
    assert f"ملاحظة {LRI}/tmp/2024-03-05{PDI}" in excluded_html


def test_view_only_user_gets_isolated_readonly_fields_and_inlines(django_user_model):
    from django.contrib.auth.models import Permission

    viewer = django_user_model.objects.create_user(username="viewer", password="pw", is_staff=True)
    perms = Permission.objects.filter(
        content_type__app_label="testapp",
        codename__in=["view_book", "view_chapter", "view_review"],
    )
    viewer.user_permissions.set(perms)

    book = Book.objects.create(
        title="مقدمة /vol-1/2024-03-05",
        isbn="978-0-691-16628-5",
        archive_note="نُقل الملف إلى /srv/archive/2024-03-05",
    )
    Chapter.objects.create(book=book, number=1, title="فصل /ch-1/2024-03-05")
    Review.objects.create(book=book, reviewer="Layla", body="مراجعة /rev/2024-03-05")

    class BidiChapterInline(BidiSafeAdminMixin, admin.TabularInline):
        model = Chapter
        extra = 0

    class BidiReviewInline(BidiSafeAdminMixin, admin.StackedInline):
        model = Review
        extra = 0

    model_admin = make_book_admin(
        inlines=(BidiChapterInline, BidiReviewInline),
        readonly_fields=("archive_note",),
        fields=("title", "archive_note"),
    )
    html = render_change(model_admin, book, viewer, lang="ar-eg").content.decode()
    assert f"مقدمة {LRI}/vol-1/2024-03-05{PDI}" in html
    assert f"نُقل الملف إلى {LRI}/srv/archive/2024-03-05{PDI}" in html
    assert f"فصل {LRI}/ch-1/2024-03-05{PDI}" in html
    assert f"مراجعة {LRI}/rev/2024-03-05{PDI}" in html


def test_readonly_custom_adminform_and_readonly_subclass_keep_working(admin_user):
    from django.contrib.admin import helpers

    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="plain",
    )

    class CustomReadonlyField(helpers.AdminReadonlyField):
        def contents(self):
            return mark_safe("مخصص /srv/custom/2024-03-05")

    def failing_lookup(_obj):
        raise RuntimeError("custom contents() does not use lookup_field")

    class CustomFieldline(helpers.Fieldline):
        def __iter__(self):
            yield CustomReadonlyField(
                self.form, failing_lookup, is_first=True, model_admin=self.model_admin
            )
            yield from super().__iter__()

    class CustomFieldset(helpers.Fieldset):
        def __iter__(self):
            for field in self.fields:
                yield CustomFieldline(
                    self.form, field, self.readonly_fields, model_admin=self.model_admin
                )

    class CustomAdminForm(helpers.AdminForm):
        def __iter__(self):
            for name, options in self.fieldsets:
                yield CustomFieldset(
                    self.form,
                    name,
                    readonly_fields=self.readonly_fields,
                    model_admin=self.model_admin,
                    **options,
                )

    class CustomBookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
        readonly_fields = ("archive_note",)
        fields = ("title", "archive_note")

        def render_change_form(
            self, request, context, add=False, change=False, form_url="", obj=None
        ):
            af = context["adminform"]
            context["adminform"] = CustomAdminForm(
                af.form, af.fieldsets, {}, af.readonly_fields, af.model_admin
            )
            return super().render_change_form(
                request, context, add=add, change=change, form_url=form_url, obj=obj
            )

    custom_admin = CustomBookAdmin(Book, admin.site)
    html = render_change(custom_admin, book, admin_user, lang="ar-eg").content.decode()
    assert f"مخصص {LRI}/srv/custom/2024-03-05{PDI}" in html


def test_readonly_counting_callable_is_called_once_per_change_form_render(admin_user):
    book = Book.objects.create(
        title="Muqaddimah",
        isbn="978-0-691-16628-5",
        archive_note="نُقل الملف إلى /srv/archive/2024-03-05",
    )
    counts = {"plain": 0, "safe": 0, "boolean": 0, "method": 0}

    def plain_callable(_obj):
        counts["plain"] += 1
        return "مرجع /ref/2024-03-05"

    def safe_callable(_obj):
        counts["safe"] += 1
        return mark_safe("نُقل /srv/safe/2024-03-05")

    @admin.display(boolean=True, description="Flag")
    def boolean_callable(_obj):
        counts["boolean"] += 1
        return True

    @admin.display(description="Method note")
    def method_note(self, _obj):
        counts["method"] += 1
        return "ملاحظة /var/log/2024-03-05"

    model_admin = make_book_admin(
        readonly_fields=(plain_callable, safe_callable, boolean_callable, "method_note"),
        fields=("title", plain_callable, safe_callable, boolean_callable, "method_note"),
        method_note=method_note,
    )
    html = render_change(model_admin, book, admin_user, lang="ar-eg").content.decode()
    assert counts == {"plain": 1, "safe": 1, "boolean": 1, "method": 1}
    assert f"مرجع {LRI}/ref/2024-03-05{PDI}" in html
    assert "نُقل /srv/safe/2024-03-05" in html
    assert f"{LRI}/srv/safe/2024-03-05{PDI}" not in html
    assert "icon-yes" in html
    assert f"ملاحظة {LRI}/var/log/2024-03-05{PDI}" in html


# -- delete confirmation page and delete message -----------------------------

AR_EG = {"accept-language": "ar-eg"}
MIXED_NAME = "مقدمة 978-0-262-03561-3"


def delete_url(obj):
    return f"/admin/testapp/{obj._meta.model_name}/{obj.pk}/delete/"


def delete_question(html):
    """The "Are you sure" paragraph -- the first ``<p>`` on the delete page.

    Everything before the content block (header, breadcrumbs, messages,
    title) uses other tags, so this is the paragraph that quotes the name.
    """
    match = re.search(r"<p>(.*?)</p>", html, re.S)
    assert match is not None
    return match.group(1)


def assert_balanced_isolates(text):
    depth = 0
    for char in text:
        if char in ISOLATE_OPENERS:
            depth += 1
        elif char == PDI:
            depth -= 1
            assert depth >= 0, f"stray closing PDI in {text!r}"
    assert depth == 0, f"unclosed isolate in {text!r}"


def test_delete_question_contains_the_isolated_str(admin_client):
    thing = Thing.objects.create(name=MIXED_NAME)
    response = admin_client.get(delete_url(thing), headers=AR_EG)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'dir="rtl"' in html
    # The question paragraph itself, not just the breadcrumb.
    assert FSI + MIXED_NAME + PDI in delete_question(html)
    proxy = response.context["object"]
    assert str(proxy) == isolate(str(thing))
    assert proxy.pk == thing.pk


def test_delete_message_contains_the_isolated_str(admin_client):
    thing = Thing.objects.create(name=MIXED_NAME)
    response = admin_client.post(delete_url(thing), {"post": "yes"}, headers=AR_EG, follow=True)
    assert response.status_code == 200
    assert not Thing.objects.filter(pk=thing.pk).exists()
    (message,) = [str(m) for m in response.context["messages"]]
    assert FSI + MIXED_NAME + PDI in message
    assert FSI + MIXED_NAME + PDI in response.content.decode()


def test_html_in_str_stays_escaped_on_the_delete_page(admin_client):
    thing = Thing.objects.create(name="<b>x</b> كتاب")
    html = admin_client.get(delete_url(thing), headers=AR_EG).content.decode()
    question = delete_question(html)
    assert FSI + "<b>x</b>" not in question
    assert FSI + "&lt;b&gt;x&lt;/b&gt; كتاب" + PDI in question


def test_html_in_str_stays_escaped_in_the_delete_message(admin_client):
    thing = Thing.objects.create(name="<b>x</b> كتاب")
    response = admin_client.post(delete_url(thing), {"post": "yes"}, headers=AR_EG, follow=True)
    html = response.content.decode()
    assert FSI + "<b>x</b>" not in html
    assert FSI + "&lt;b&gt;x&lt;/b&gt; كتاب" + PDI in html


def test_delete_breadcrumb_still_links_to_the_change_page(admin_client):
    thing = Thing.objects.create(name=MIXED_NAME)
    html = admin_client.get(delete_url(thing), headers=AR_EG).content.decode()
    assert f'href="/admin/testapp/thing/{thing.pk}/change/"' in html


def test_long_str_keeps_the_breadcrumb_isolate_balanced(admin_client):
    name = " ".join(f"word{i:02d}" for i in range(30))
    thing = Thing.objects.create(name=name)
    html = admin_client.get(delete_url(thing), headers=AR_EG).content.decode()
    link = re.search(rf'<a href="/admin/testapp/thing/{thing.pk}/change/">([^<]*)</a>', html)
    assert link is not None
    breadcrumb = link.group(1)
    assert breadcrumb.endswith("…")
    assert "word29" not in breadcrumb
    assert breadcrumb.startswith(FSI)
    assert_balanced_isolates(breadcrumb)
    # The question itself still shows the whole name, in balanced isolates.
    assert "word29" in html
    assert_balanced_isolates(delete_question(html))

    # Exactly 18 words: no truncation, so the breadcrumb is one plain isolate.
    short_name = " ".join(f"word{i:02d}" for i in range(18))
    other = Thing.objects.create(name=short_name)
    html = admin_client.get(delete_url(other), headers=AR_EG).content.decode()
    assert f">{FSI}{short_name}{PDI}</a>" in html


def test_render_delete_form_wraps_object_only_when_enabled(admin_user, thing):
    request = RequestFactory().get(delete_url(thing))
    request.user = admin_user

    context = {"object": thing}
    make_admin().render_delete_form(request, context)
    proxy = context["object"]
    assert proxy is not thing
    assert str(proxy) == isolate(str(thing))
    assert proxy.pk == thing.pk

    context = {"object": thing}
    make_admin(bidi_isolate_changelist=False).render_delete_form(request, context)
    assert context["object"] is thing

    empty = Thing.objects.create(name="")
    context = {"object": empty}
    make_admin().render_delete_form(request, context)
    assert str(context["object"]) == ""

    blank = Thing.objects.create(name="   ")
    context = {"object": blank}
    make_admin().render_delete_form(request, context)
    assert str(context["object"]) == "   "


def test_long_str_proxy_reuses_the_original_whitespace(admin_user):
    name = " ".join(f"word{i:02d}" for i in range(30))
    thing = Thing.objects.create(name=name)
    request = RequestFactory().get(delete_url(thing))
    request.user = admin_user
    context = {"object": thing}
    make_admin().render_delete_form(request, context)
    text = str(context["object"])
    # PDI glued to word 18, the original space, then the reopening isolate
    # glued to word 19 -- no extra space is introduced.
    assert f"word17{PDI} {FSI}word18" in text
    assert f"{PDI}  " not in text
    assert_balanced_isolates(text)


def test_response_delete_message_follows_the_switch(admin_user, thing):
    def message_for(model_admin):
        request = RequestFactory().post(delete_url(thing), {"post": "yes"})
        request.user = admin_user
        request._messages = CookieStorage(request)
        model_admin.response_delete(request, str(thing), thing.pk)
        return [str(m) for m in request._messages]

    stock = admin.ModelAdmin(Thing, AdminSite())
    stock_messages = message_for(stock)
    assert message_for(make_admin(bidi_isolate_changelist=False)) == stock_messages
    with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
        assert message_for(make_admin()) == stock_messages
    (on_message,) = message_for(make_admin())
    assert isolate(str(thing)) in on_message


def stock_thing_admin_cls():
    """A stock ModelAdmin with the same configuration as the registered one."""
    return type(
        "StockThingAdmin",
        (admin.ModelAdmin,),
        {
            name: getattr(BidiThingAdmin, name)
            for name in (
                "list_display",
                "list_filter",
                "search_fields",
                "readonly_fields",
                "upper_name",
            )
        },
    )


def thing_urlconf(thing_admin_cls):
    """A URLconf whose admin site mirrors the default one, with another Thing admin.

    ``admin.site.urls`` is built once at import time, so swapping the registry
    alone would not change which admin serves the requests.
    """
    site = AdminSite()
    for model, model_admin in admin.site._registry.items():
        site.register(model, thing_admin_cls if model is Thing else type(model_admin))
    urlconf = ModuleType("tests.urls_thing_admin")
    urlconf.urlpatterns = [
        path("admin/", site.urls),
        path("i18n/", include("django.conf.urls.i18n")),
    ]
    return urlconf


def test_switch_off_delete_page_and_message_match_stock(admin_client):
    stock_cls = stock_thing_admin_cls()

    def scrub_csrf(s):
        return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"', s)

    def delete_round_trip(pk=None):
        thing = Thing.objects.create(pk=pk, name=MIXED_NAME)
        url = delete_url(thing)
        page = admin_client.get(url, headers=AR_EG).content.decode()
        response = admin_client.post(url, {"post": "yes"}, headers=AR_EG, follow=True)
        messages = [str(m) for m in response.context["messages"]]
        return thing.pk, scrub_csrf(page), messages, scrub_csrf(response.content.decode())

    with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
        pk, off_page, off_messages, off_final = delete_round_trip()
    with override_settings(ROOT_URLCONF=thing_urlconf(stock_cls)):
        _, stock_page, stock_messages, stock_final = delete_round_trip(pk=pk)

    assert off_page == stock_page
    assert off_messages == stock_messages
    assert off_final == stock_final
    assert FSI + MIXED_NAME not in off_page
    assert not any(FSI in message for message in off_messages)


def test_whitespace_only_str_matches_stock_on_the_delete_page(admin_client):
    thing = Thing.objects.create(name="   ")
    url = delete_url(thing)
    bidi_html = admin_client.get(url, headers=AR_EG).content.decode()
    with override_settings(ROOT_URLCONF=thing_urlconf(stock_thing_admin_cls())):
        stock_html = admin_client.get(url, headers=AR_EG).content.decode()

    def breadcrumb(html):
        return re.search(rf'<a href="/admin/testapp/thing/{thing.pk}/change/">([^<]*)</a>', html)

    assert delete_question(bidi_html) == delete_question(stock_html)
    assert breadcrumb(bidi_html).group(1) == breadcrumb(stock_html).group(1)
    assert FSI not in delete_question(bidi_html)
    assert FSI not in breadcrumb(bidi_html).group(1)


def stock_book_admin_cls():
    """A stock ModelAdmin with the same configuration as the registered BookAdmin."""
    # Skip dunders and ``media``: Django < 5.0's MediaDefiningClass adds a ``media``
    # property bound to BookAdmin via ``super(cls, self)``; the new class makes its own.
    own = {
        name: value
        for name, value in vars(BookAdmin).items()
        if not name.startswith("__") and name != "media"
    }
    return type("StockBookAdmin", (admin.ModelAdmin,), own)


def book_urlconf(book_admin_cls):
    """A URLconf whose admin site mirrors the default one, with another Book admin."""
    site = AdminSite()
    for model, model_admin in admin.site._registry.items():
        site.register(model, book_admin_cls if model is Book else type(model_admin))
    urlconf = ModuleType("tests.urls_book_admin")
    urlconf.urlpatterns = [
        path("admin/", site.urls),
        path("i18n/", include("django.conf.urls.i18n")),
    ]
    return urlconf


def fetch_book_delete_page(client, book, page):
    if page == "delete":
        return client.get(delete_url(book), headers=AR_EG)
    return client.post(
        BOOK_CHANGELIST_URL,
        {"action": "delete_selected", ACTION_CHECKBOX_NAME: [str(book.pk)]},
        headers=AR_EG,
    )


@pytest.mark.parametrize("page", ["delete", "delete_selected"])
def test_delete_lists_isolate_plain_review_and_keep_book_link(admin_client, page):
    assert Review not in admin.site._registry
    book = Book.objects.create(title=MIXED_NAME, isbn="978-0-262-03561-3")
    Review.objects.create(book=book, reviewer="مراجعة v1.2.3", body="plain")
    Review.objects.create(book=book, reviewer="ملاحظة: /srv/archive/v1.2.3", body="colon")

    response = fetch_book_delete_page(admin_client, book, page)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'dir="rtl"' in html

    expected_book_link = f'Book: <a href="/admin/testapp/book/{book.pk}/change/">{MIXED_NAME}</a>'
    assert expected_book_link in html
    assert f"Review: {FSI}مراجعة v1.2.3{PDI}" in html
    assert f"Review: {FSI}ملاحظة: /srv/archive/v1.2.3{PDI}" in html
    assert FSI + FSI not in html

    entries = (
        response.context["deleted_objects"]
        if page == "delete"
        else response.context["deletable_objects"][0]
    )
    book_entry, related_entries = entries
    assert isinstance(book_entry, SafeData)
    assert str(book_entry) == expected_book_link
    assert FSI not in book_entry
    assert all(not isinstance(item, SafeData) for item in related_entries)
    assert set(related_entries) == {
        f"Review: {FSI}مراجعة v1.2.3{PDI}",
        f"Review: {FSI}ملاحظة: /srv/archive/v1.2.3{PDI}",
    }


@pytest.mark.parametrize("page", ["delete", "delete_selected"])
def test_html_in_related_review_stays_escaped_on_delete_pages(admin_client, page):
    book = Book.objects.create(title=MIXED_NAME, isbn="978-0-262-03561-3")
    Review.objects.create(book=book, reviewer="<b>مراجعة</b> /srv/v1.2.3", body="xss")

    response = fetch_book_delete_page(admin_client, book, page)
    assert response.status_code == 200
    html = response.content.decode()
    assert "<b>مراجعة</b>" not in html
    assert f"Review: {FSI}&lt;b&gt;مراجعة&lt;/b&gt; /srv/v1.2.3{PDI}" in html

    entries = (
        response.context["deleted_objects"]
        if page == "delete"
        else response.context["deletable_objects"][0]
    )
    (review_entry,) = entries[1]
    assert not isinstance(review_entry, SafeData)
    assert review_entry == f"Review: {FSI}<b>مراجعة</b> /srv/v1.2.3{PDI}"


@pytest.mark.parametrize("switch", ["setting", "attribute"])
@pytest.mark.parametrize("page", ["delete", "delete_selected"])
def test_switch_off_delete_lists_match_stock(admin_client, switch, page):
    book = Book.objects.create(title=MIXED_NAME, isbn="978-0-262-03561-3")
    Review.objects.create(book=book, reviewer="مراجعة v1.2.3", body="plain")

    def scrub_csrf(s):
        return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"', s)

    with override_settings(ROOT_URLCONF=book_urlconf(stock_book_admin_cls())):
        stock_html = scrub_csrf(fetch_book_delete_page(admin_client, book, page).content.decode())

    if switch == "setting":
        with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
            off_html = scrub_csrf(fetch_book_delete_page(admin_client, book, page).content.decode())
    else:
        off_cls = variant(BookAdmin, bidi_isolate_changelist=False)
        with override_settings(ROOT_URLCONF=book_urlconf(off_cls)):
            off_html = scrub_csrf(fetch_book_delete_page(admin_client, book, page).content.decode())

    assert off_html == stock_html
    assert "Review: مراجعة v1.2.3" in off_html
    assert FSI not in off_html


def test_get_deleted_objects_unit_with_protected_and_nested_lists(admin_user):
    book_link = format_html(
        '{}: <a href="{}">{}</a>', "Book", "/admin/testapp/book/1/change/", "مقدمة v1.2.3"
    )
    chapter_link = format_html(
        '{}: <a href="{}">{}</a>', "Chapter", "/admin/testapp/chapter/2/change/", "فصل v2.0"
    )
    protected_link = format_html(
        '{}: <a href="{}">{}</a>', "Category", "/admin/testapp/category/3/change/", "تصنيف v3.0"
    )

    stub_deleted = [
        book_link,
        [
            "Review: مراجعة v1.2.3",
            "Review: ملاحظة: /srv/v1.2.3",
            "Review: <b>x</b> كتاب",
            f"Review: {FSI}مراجعة v1.2.3{PDI}",
            "Review: REF-\u202e42\u2069-OK",
            "Review: ",
            "Review:    ",
            "Review: \u202e\u2069",
            "bare entry",
            chapter_link,
            ["Note: حاشية /a/b", ["Tag: وسم 1.0"]],
        ],
    ]
    stub_counts = {"books": 1, "reviews": 8, "notes": 1, "tags": 1}
    stub_perms = {"secret"}
    stub_protected = [
        protected_link,
        "Audit: سجل /var/log/2024-03-05",
        "Audit: تنبيه: <b>err</b>",
        f"Audit: {FSI}سجل v1{PDI}",
    ]

    class StubParentAdmin(admin.ModelAdmin):
        def get_deleted_objects(self, objs, request):
            return stub_deleted, stub_counts, stub_perms, stub_protected

    bidi_cls = type("BidiStubAdmin", (BidiSafeAdminMixin, StubParentAdmin), {})
    model_admin = bidi_cls(Book, AdminSite())
    request = request_for(admin_user)

    deleted, counts, perms, protected = model_admin.get_deleted_objects([], request)

    assert deleted == [
        book_link,
        [
            f"Review: {FSI}مراجعة v1.2.3{PDI}",
            f"Review: {FSI}ملاحظة: /srv/v1.2.3{PDI}",
            f"Review: {FSI}<b>x</b> كتاب{PDI}",
            f"Review: {FSI}مراجعة v1.2.3{PDI}",
            f"Review: {FSI}REF-42-OK{PDI}",
            "Review: ",
            "Review:    ",
            "Review: \u202e\u2069",
            "bare entry",
            chapter_link,
            [f"Note: {FSI}حاشية /a/b{PDI}", [f"Tag: {FSI}وسم 1.0{PDI}"]],
        ],
    ]
    assert deleted[0] is book_link
    assert deleted[1][9] is chapter_link
    assert not isinstance(deleted[1][2], SafeData)
    assert counts is stub_counts
    assert perms is stub_perms
    assert protected == [
        protected_link,
        f"Audit: {FSI}سجل /var/log/2024-03-05{PDI}",
        f"Audit: {FSI}تنبيه: <b>err</b>{PDI}",
        f"Audit: {FSI}سجل v1{PDI}",
    ]
    assert protected[0] is protected_link
    assert all(not isinstance(item, SafeData) for item in protected[1:])

    # No double isolation if the mixin runs again over an already-isolated result.
    class AlreadyIsolatedParent(admin.ModelAdmin):
        def get_deleted_objects(self, objs, request):
            return deleted, counts, perms, protected

    second_cls = type("SecondBidiStubAdmin", (BidiSafeAdminMixin, AlreadyIsolatedParent), {})
    assert second_cls(Book, AdminSite()).get_deleted_objects([], request) == (
        deleted,
        counts,
        perms,
        protected,
    )

    # Direction follows RTL_ADMIN["ISOLATION_DIRECTION"], not bidi_isolation_direction.
    ltr_cls = type(
        "LtrBidiStubAdmin",
        (BidiSafeAdminMixin, StubParentAdmin),
        {"bidi_isolation_direction": "rtl"},
    )
    with override_settings(RTL_ADMIN={"ISOLATION_DIRECTION": "ltr"}):
        ltr_deleted, _, _, ltr_protected = ltr_cls(Book, AdminSite()).get_deleted_objects(
            [], request
        )
    assert ltr_deleted[1][0] == f"Review: {LRI}مراجعة v1.2.3{PDI}"
    assert ltr_protected[1] == f"Audit: {LRI}سجل /var/log/2024-03-05{PDI}"

    # Disabled via attribute or setting returns the parent result untouched.
    off_cls = type(
        "OffBidiStubAdmin",
        (BidiSafeAdminMixin, StubParentAdmin),
        {"bidi_isolate_changelist": False},
    )
    assert off_cls(Book, AdminSite()).get_deleted_objects([], request) == (
        stub_deleted,
        stub_counts,
        stub_perms,
        stub_protected,
    )
    with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
        assert model_admin.get_deleted_objects([], request) == (
            stub_deleted,
            stub_counts,
            stub_perms,
            stub_protected,
        )


# -- add and change success messages -----------------------------------------

ADD_URL = "/admin/testapp/thing/add/"
SAVE_BUTTONS = pytest.mark.parametrize("button", [None, "_continue", "_addanother"])


def change_url(obj):
    return f"/admin/testapp/thing/{obj.pk}/change/"


def thing_form(name, button=None, **fields):
    data = {"name": name, "quantity": "0", "price": "0", "is_active": "on", **fields}
    if button:
        data[button] = "1"
    return data


def variant(base, **attrs):
    """``base`` with ``attrs`` overridden, to be served through ``thing_urlconf``."""
    return type(f"{base.__name__}Variant", (base,), attrs)


@staticmethod
def no_change_permission(request, obj=None):
    return False


@staticmethod
def change_permission_while_active(request, obj=None):
    """An object-level rule: an inactive thing can no longer be changed."""
    return obj is None or obj.is_active


def save_outcome(client, thing_admin_cls, data, obj=None):
    """Save the add form, or ``obj``'s change form, in ar-eg and follow the redirect.

    ``thing_admin_cls`` is the admin class that serves the request; ``None``
    keeps the registered ``BidiThingAdmin``.  The saved object's primary key
    is scrubbed from the result, so that two saves which create different rows
    can be compared with ``==``.
    """
    url = ADD_URL if obj is None else change_url(obj)
    urlconf = "tests.urls" if thing_admin_cls is None else thing_urlconf(thing_admin_cls)
    with override_settings(ROOT_URLCONF=urlconf):
        response = client.post(url, data, headers=AR_EG, follow=True)
    assert response.status_code == 200
    assert response.redirect_chain, "the form did not validate"
    pk = Thing.objects.latest("pk").pk if obj is None else obj.pk

    def scrub(text):
        return text.replace(f"/thing/{pk}/", "/thing/PK/")

    html = response.content.decode()
    assert 'dir="rtl"' in html
    message_list = re.search(r'<ul class="messagelist">.*?</ul>', html, re.S)
    return SimpleNamespace(
        redirects=[(scrub(target), status) for target, status in response.redirect_chain],
        messages=[scrub(str(message)) for message in response.context["messages"]],
        message_list=scrub(message_list.group(0)),
    )


@SAVE_BUTTONS
def test_add_message_isolates_the_plain_name_without_change_permission(admin_client, button):
    form = thing_form(MIXED_NAME, button)
    bidi = save_outcome(
        admin_client, variant(BidiThingAdmin, has_change_permission=no_change_permission), form
    )
    stock = save_outcome(
        admin_client,
        variant(stock_thing_admin_cls(), has_change_permission=no_change_permission),
        form,
    )
    (stock_message,) = stock.messages
    # Django prints the name once, as plain text, because the user cannot
    # follow a link to the change form.
    assert "<a" not in stock_message
    assert stock_message.count(MIXED_NAME) == 1
    assert bidi.messages == [stock_message.replace(MIXED_NAME, FSI + MIXED_NAME + PDI)]
    assert bidi.message_list == stock.message_list.replace(MIXED_NAME, FSI + MIXED_NAME + PDI)
    # Only the message differs: the redirect and the log entry are Django's.
    assert bidi.redirects == stock.redirects
    assert [entry.object_repr for entry in LogEntry.objects.all()] == [MIXED_NAME, MIXED_NAME]


@SAVE_BUTTONS
def test_add_message_with_change_permission_matches_stock(admin_client, button):
    form = thing_form(MIXED_NAME, button)
    bidi = save_outcome(admin_client, None, form)
    stock = save_outcome(admin_client, stock_thing_admin_cls(), form)
    (message,) = bidi.messages
    assert f'<a href="/admin/testapp/thing/PK/change/">{MIXED_NAME}</a>' in message
    assert FSI not in message
    assert bidi.messages == stock.messages
    assert bidi.message_list == stock.message_list
    assert bidi.redirects == stock.redirects
    assert [entry.object_repr for entry in LogEntry.objects.all()] == [MIXED_NAME, MIXED_NAME]


@SAVE_BUTTONS
def test_change_message_with_change_permission_matches_stock(admin_client, button):
    thing = Thing.objects.create(name=MIXED_NAME)
    form = thing_form(MIXED_NAME, button, reference="v1.2.3")
    bidi = save_outcome(admin_client, None, form, thing)
    stock = save_outcome(admin_client, stock_thing_admin_cls(), form, thing)
    (message,) = bidi.messages
    assert f'<a href="/admin/testapp/thing/PK/change/">{MIXED_NAME}</a>' in message
    assert FSI not in message
    assert bidi.messages == stock.messages
    assert bidi.message_list == stock.message_list
    assert bidi.redirects == stock.redirects
    assert [entry.object_repr for entry in LogEntry.objects.all()] == [MIXED_NAME, MIXED_NAME]


def test_change_without_change_permission_is_refused_like_stock(admin_client):
    """Without change permission the change view never reaches ``response_change``."""
    thing = Thing.objects.create(name=MIXED_NAME)
    form = thing_form("renamed 1.2.3")
    for base in (BidiThingAdmin, stock_thing_admin_cls()):
        urlconf = thing_urlconf(variant(base, has_change_permission=no_change_permission))
        with override_settings(ROOT_URLCONF=urlconf):
            response = admin_client.post(change_url(thing), form, headers=AR_EG)
            page = admin_client.get(CHANGELIST_URL, headers=AR_EG)
        assert response.status_code == 403
        assert not list(page.context["messages"])
    thing.refresh_from_db()
    assert thing.name == MIXED_NAME
    assert not LogEntry.objects.exists()


def test_change_message_stays_linked_when_the_save_costs_the_change_permission(admin_client):
    """``response_change`` links the name whatever the permission; that is left alone."""
    thing = Thing.objects.create(name=MIXED_NAME)
    form = thing_form(MIXED_NAME)
    del form["is_active"]
    bidi = save_outcome(
        admin_client,
        variant(BidiThingAdmin, has_change_permission=change_permission_while_active),
        form,
        thing,
    )
    thing.refresh_from_db()
    assert not thing.is_active
    Thing.objects.filter(pk=thing.pk).update(is_active=True)
    stock = save_outcome(
        admin_client,
        variant(stock_thing_admin_cls(), has_change_permission=change_permission_while_active),
        form,
        thing,
    )
    (message,) = bidi.messages
    assert f'<a href="/admin/testapp/thing/PK/change/">{MIXED_NAME}</a>' in message
    assert FSI not in message
    assert bidi.messages == stock.messages
    assert bidi.message_list == stock.message_list
    assert bidi.redirects == stock.redirects


class PlainChangeMessageAdmin(admin.ModelAdmin):
    """Prints the name instead of a dead link once the user cannot change the object."""

    has_change_permission = change_permission_while_active

    def response_change(self, request, obj):
        if self.has_change_permission(request, obj):
            return super().response_change(request, obj)
        message = format_html(
            gettext("The {name} “{obj}” was changed successfully."),
            name=self.opts.verbose_name,
            obj=str(obj),
        )
        self.message_user(request, message, messages.SUCCESS)
        return self.response_post_save_change(request, obj)


def test_plain_change_message_from_a_base_class_is_isolated(admin_client):
    thing = Thing.objects.create(name=MIXED_NAME)
    form = thing_form(MIXED_NAME)
    del form["is_active"]
    bidi_cls = type("BidiPlainChangeAdmin", (BidiSafeAdminMixin, PlainChangeMessageAdmin), {})
    bidi = save_outcome(admin_client, bidi_cls, form, thing)
    Thing.objects.filter(pk=thing.pk).update(is_active=True)
    stock = save_outcome(admin_client, PlainChangeMessageAdmin, form, thing)
    (stock_message,) = stock.messages
    assert "<a" not in stock_message
    assert bidi.messages == [stock_message.replace(MIXED_NAME, FSI + MIXED_NAME + PDI)]
    assert bidi.redirects == stock.redirects


def _django_admin_msgids():
    """Every msgid in Django's English admin catalogue, continuation lines joined."""
    po = Path(admin.__file__).parent / "locale" / "en" / "LC_MESSAGES" / "django.po"
    entries = re.findall(r'^msgid ((?:"(?:[^"\\]|\\.)*"\n)+)', po.read_text("utf-8"), re.M)
    return {"".join(re.findall(r'"((?:[^"\\]|\\.)*)"', entry)) for entry in entries}


def test_recognised_success_messages_are_still_djangos_msgids():
    # The plain-name rewrite matches Django's success messages verbatim; if
    # Django rewords one, isolation would silently stop for that message.
    msgids = _django_admin_msgids()
    assert "The {name} “{obj}” was added successfully." in msgids
    assert [msgid for msgid in _SUCCESS_MESSAGES if msgid not in msgids] == []


def test_html_in_str_stays_escaped_in_the_add_message(admin_client):
    form = thing_form("<b>x</b>")
    plain = save_outcome(
        admin_client, variant(BidiThingAdmin, has_change_permission=no_change_permission), form
    )
    assert FSI + "&lt;b&gt;x&lt;/b&gt;" + PDI in plain.message_list
    assert "<b>" not in plain.message_list
    linked = save_outcome(admin_client, None, form)
    assert (
        '<a href="/admin/testapp/thing/PK/change/">&lt;b&gt;x&lt;/b&gt;</a>' in linked.message_list
    )
    assert "<b>" not in linked.message_list
    assert FSI not in linked.message_list


def test_html_in_str_stays_escaped_in_the_change_message(admin_client):
    thing = Thing.objects.create(name="<b>x</b>")
    linked = save_outcome(admin_client, None, thing_form("<b>x</b>"), thing)
    assert (
        '<a href="/admin/testapp/thing/PK/change/">&lt;b&gt;x&lt;/b&gt;</a>' in linked.message_list
    )
    assert "<b>" not in linked.message_list
    assert FSI not in linked.message_list


def test_popup_add_response_is_stock_without_change_permission(admin_client):
    form = thing_form(MIXED_NAME, "_popup")
    popups = []
    for base in (BidiThingAdmin, stock_thing_admin_cls()):
        urlconf = thing_urlconf(variant(base, has_change_permission=no_change_permission))
        with override_settings(ROOT_URLCONF=urlconf):
            response = admin_client.post(ADD_URL, form, headers=AR_EG)
            page = admin_client.get(CHANGELIST_URL, headers=AR_EG)
        assert response.status_code == 200
        # The popup hands the name to the opener's <select>; it shows no message.
        assert not list(page.context["messages"])
        pk = str(Thing.objects.latest("pk").pk)
        data = json.loads(response.context["popup_response_data"])
        assert data == {"value": pk, "obj": MIXED_NAME}
        popups.append(response.content.decode().replace(f"&quot;{pk}&quot;", "&quot;PK&quot;"))
    bidi_popup, stock_popup = popups
    assert bidi_popup == stock_popup
    assert FSI not in bidi_popup
    assert [entry.object_repr for entry in LogEntry.objects.all()] == [MIXED_NAME, MIXED_NAME]


@pytest.mark.parametrize("switch", ["setting", "attribute"])
@SAVE_BUTTONS
def test_switch_off_add_message_matches_stock(admin_client, switch, button):
    form = thing_form(MIXED_NAME, button)
    stock = save_outcome(
        admin_client,
        variant(stock_thing_admin_cls(), has_change_permission=no_change_permission),
        form,
    )
    if switch == "setting":
        off_cls = variant(BidiThingAdmin, has_change_permission=no_change_permission)
        with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
            off = save_outcome(admin_client, off_cls, form)
    else:
        off_cls = variant(
            BidiThingAdmin,
            has_change_permission=no_change_permission,
            bidi_isolate_changelist=False,
        )
        off = save_outcome(admin_client, off_cls, form)
    assert off.messages == stock.messages
    assert off.message_list == stock.message_list
    assert off.redirects == stock.redirects
    assert MIXED_NAME in off.message_list
    assert FSI not in off.message_list


@pytest.mark.parametrize("switch", ["setting", "attribute"])
@SAVE_BUTTONS
def test_switch_off_change_message_matches_stock(admin_client, switch, button):
    thing = Thing.objects.create(name=MIXED_NAME)
    form = thing_form(MIXED_NAME, button)
    stock = save_outcome(admin_client, stock_thing_admin_cls(), form, thing)
    if switch == "setting":
        with override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}):
            off = save_outcome(admin_client, None, form, thing)
    else:
        off = save_outcome(
            admin_client, variant(BidiThingAdmin, bidi_isolate_changelist=False), form, thing
        )
    assert off.messages == stock.messages
    assert off.message_list == stock.message_list
    assert off.redirects == stock.redirects
    assert MIXED_NAME in off.message_list
    assert FSI not in off.message_list


def add_messages(model_admin, user, name):
    """Call ``response_add`` directly, in English, and return the messages it queued."""
    obj = Thing.objects.create(name=name)
    request = RequestFactory().post(ADD_URL)
    request.user = user
    request._messages = CookieStorage(request)
    with translation.override("en"):
        response = model_admin.response_add(request, obj)
    # The name handed to message_user() does not outlive the call.
    assert not hasattr(request, "_bidi_plain_object_name")
    return [str(message) for message in request._messages], response


def test_only_the_quoted_name_is_isolated_in_the_add_message(admin_user):
    class RemindingAdmin(admin.ModelAdmin):
        has_change_permission = no_change_permission

        def response_post_save_add(self, request, obj):
            self.message_user(request, "Thanks, a note was saved.")
            return super().response_post_save_add(request, obj)

    bidi = type("BidiRemindingAdmin", (BidiSafeAdminMixin, RemindingAdmin), {})
    # The name "a" is also a substring of the sentence around it and of the
    # project's own message; neither of those is touched.
    bidi_messages, bidi_response = add_messages(bidi(Thing, AdminSite()), admin_user, "a")
    stock_messages, stock_response = add_messages(
        RemindingAdmin(Thing, AdminSite()), admin_user, "a"
    )
    assert stock_messages == ["The thing “a” was added successfully.", "Thanks, a note was saved."]
    assert bidi_messages == [
        f"The thing “{FSI}a{PDI}” was added successfully.",
        "Thanks, a note was saved.",
    ]
    assert bidi_response.status_code == stock_response.status_code == 302
    assert bidi_response.url == stock_response.url


@pytest.mark.parametrize("name", ["", "   ", "\u202e\u2069"])
def test_names_with_nothing_to_isolate_keep_the_stock_add_message(admin_user, name):
    bidi_messages, _ = add_messages(
        make_admin(has_change_permission=no_change_permission), admin_user, name
    )
    stock = variant(admin.ModelAdmin, has_change_permission=no_change_permission)
    stock_messages, _ = add_messages(stock(Thing, AdminSite()), admin_user, name)
    assert bidi_messages == stock_messages
    assert FSI not in bidi_messages[0]


def test_padded_and_bidi_control_names_are_isolated_as_django_prints_them(admin_user):
    stock = variant(admin.ModelAdmin, has_change_permission=no_change_permission)
    name = "  v1.2.3 \u202eكتاب  "
    # Django 6.1 strips the name it prints; earlier versions print it as is.
    printed = name.strip() if django.VERSION >= (6, 1) else name
    bidi_messages, _ = add_messages(
        make_admin(has_change_permission=no_change_permission), admin_user, name
    )
    stock_messages, _ = add_messages(stock(Thing, AdminSite()), admin_user, name)
    assert stock_messages == [f"The thing “{printed}” was added successfully."]
    # isolate() drops the embedded override, so it cannot reach past the quotes.
    isolated = FSI + printed.replace("\u202e", "") + PDI
    assert bidi_messages == [f"The thing “{isolated}” was added successfully."]


# -- localized input in admin-generated fields -------------------------------

INPUT_LANGUAGES = ("ar", "fa", "he", "en")
BOOK_ADD_URL = f"{BOOK_CHANGELIST_URL}add/"


@pytest.fixture
def post_book(admin_client, settings):
    # Without fa in LANGUAGES, LocaleMiddleware silently falls back to English.
    settings.LANGUAGES = [*settings.LANGUAGES, ("fa", "Persian"), ("de", "German")]
    settings.ROOT_URLCONF = book_urlconf(InputBookAdmin)

    def post(url, data, language):
        with translation.override(language):
            response = admin_client.post(url, data, headers={"accept-language": language})
        assert response.wsgi_request.LANGUAGE_CODE == language
        return response

    return post


def book_input_data(**overrides):
    return {
        "title": "Manuscript",
        "isbn": "ISBN-\u206712−۳٫٤\u2069",
        "status": "draft",
        "published_on": "\u200f٢٠٢٤-٠٣-٠٥",
        "launch_time": "۱۴:۳۰:۰۹\u200e",
        "available_from_0": "\u2066۲۰۲۴-۰۶-۱۹\u2069",
        "available_from_1": "\u061c١٧:٢٨:٣٩",
        "price": "١٬٢٣٤٫٥٠",
        "chapter_set-TOTAL_FORMS": "0",
        "chapter_set-INITIAL_FORMS": "0",
        "review_set-TOTAL_FORMS": "0",
        "review_set-INITIAL_FORMS": "0",
        **overrides,
    }


@pytest.mark.parametrize("language", INPUT_LANGUAGES)
@pytest.mark.parametrize("view", ["add", "change"])
def test_book_input_saves_numbers_dates_and_inline_but_preserves_text(post_book, language, view):
    if view == "change":
        book = Book.objects.create(title="Old", isbn="old")
        url = f"{BOOK_CHANGELIST_URL}{book.pk}/change/"
    else:
        url = BOOK_ADD_URL
    data = book_input_data()
    data.update(
        {
            "chapter_set-TOTAL_FORMS": "1",
            "chapter_set-0-number": "\u2066۱٬۰۲۴\u2069",
            "chapter_set-0-title": "Chapter ۴۲",
        }
    )
    response = post_book(url, data, language)
    assert response.status_code == 302, response.context["errors"]
    if view == "change":
        book.refresh_from_db()
    else:
        book = Book.objects.get()
    assert book.isbn == data["isbn"]  # CharField, despite its digits and punctuation.
    assert book.price == Decimal("1234.50")
    assert book.published_on == date(2024, 3, 5)
    assert book.launch_time == time(14, 30, 9)
    assert book.available_from == datetime(2024, 6, 19, 17, 28, 39, tzinfo=timezone.utc)
    chapter = book.chapter_set.get()
    assert (chapter.number, chapter.title) == (1024, "Chapter ۴۲")


def test_plain_inline_does_not_inherit_book_input_normalization(post_book):
    data = book_input_data()
    data.update(
        {
            "review_set-TOTAL_FORMS": "1",
            "review_set-0-reviewer": "Layla",
            "review_set-0-body": "Manuscript review",
            "review_set-0-reviewed_at_0": data["available_from_0"],
            "review_set-0-reviewed_at_1": data["available_from_1"],
        }
    )
    response = post_book(BOOK_ADD_URL, data, "fa")
    assert response.status_code == 200
    assert not response.context["adminform"].form.errors
    review_formset = next(
        inline.formset
        for inline in response.context["inline_admin_formsets"]
        if inline.formset.model is Review
    )
    assert set(review_formset.forms[0].errors) == {"reviewed_at"}
    assert not Book.objects.exists()


@pytest.mark.parametrize("language", INPUT_LANGUAGES)
def test_list_editable_price_accepts_localized_input(post_book, language):
    book = Book.objects.create(title="Draft", isbn="123", price="1.00")
    response = post_book(
        BOOK_CHANGELIST_URL,
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-id": str(book.pk),
            "form-0-price": "−۳\u202f۴۵۶٫۷۵",
            "_save": "1",
        },
        language,
    )
    assert response.status_code == 302, response.context["cl"].formset.errors
    book.refresh_from_db()
    assert book.price == Decimal("-3456.75")


@pytest.mark.parametrize("language", [*INPUT_LANGUAGES, "de"])
@pytest.mark.parametrize("use_thousands", [True, False])
def test_localized_price_uses_django_decimal_separator(
    post_book, settings, language, use_thousands
):
    settings.USE_THOUSAND_SEPARATOR = use_thousands
    settings.ROOT_URLCONF = book_urlconf(LocalizedInputBookAdmin)
    # Django handles its own group separator when enabled; the Arabic group
    # mark is unambiguous and accepted even with grouping disabled.
    with translation.override(language):
        group = formats.get_format("THOUSAND_SEPARATOR") if use_thousands else "٬"
    response = post_book(BOOK_ADD_URL, book_input_data(price=f"۱{group}۲۳۴٫۵۰"), language)
    assert response.status_code == 302, response.context["errors"]
    assert Book.objects.get().price == Decimal("1234.50")


@pytest.mark.parametrize(
    ("invalid_field", "raw"), [("price", "\u200f۳٫۴٫۵"), ("title", "\u200f۳٬۴۵۶٫۷۵")]
)
def test_invalid_book_input_redisplays_the_original_values(post_book, invalid_field, raw):
    data = book_input_data(price=raw)
    if invalid_field == "title":
        data["title"] = ""
    response = post_book(BOOK_ADD_URL, data, "fa")
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert set(form.errors) == {invalid_field}
    if invalid_field == "price":
        assert form.errors.as_data()["price"][0].code == "invalid"
    else:
        assert form.cleaned_data["price"] == Decimal("3456.75")
    assert not Book.objects.exists()
    # A number input sanitizes even a correctly rendered localized value to
    # empty in the browser. The actual bound control must be able to display it.
    assert form["price"].field.widget.input_type != "number"
    assert 'inputmode="decimal"' in str(form["price"])
    assert form["price"].value() == raw
    html = response.content.decode()
    for name in ("price", "published_on", "launch_time", "available_from_0", "available_from_1"):
        assert f'value="{data[name]}"' in html


@pytest.mark.parametrize(
    ("admin_cls", "global_enabled", "accepts_input"),
    [
        pytest.param(admin.ModelAdmin, True, False, id="plain-admin"),
        pytest.param(InputBookAdmin, False, False, id="global-off"),
        pytest.param(
            variant(InputBookAdmin, bidi_normalize_input=False), True, False, id="admin-off"
        ),
        pytest.param(
            variant(InputBookAdmin, bidi_normalize_input=True), False, True, id="admin-on"
        ),
    ],
)
def test_book_input_respects_admin_opt_in_and_switch_precedence(
    post_book, settings, admin_cls, global_enabled, accepts_input
):
    settings.ROOT_URLCONF = book_urlconf(admin_cls)
    settings.RTL_ADMIN = {"NORMALIZE_INPUT_DIGITS": global_enabled}
    data = book_input_data(
        published_on="", launch_time="", available_from_0="", available_from_1=""
    )
    response = post_book(BOOK_ADD_URL, data, "ar")
    if accepts_input:
        assert response.status_code == 302, response.context["errors"]
        assert Book.objects.get().price == Decimal("1234.50")
    else:
        assert response.status_code == 200
        form = response.context["adminform"].form
        assert set(form.errors) == {"price"}
        assert form["price"].field.widget.input_type == "number"
        assert not Book.objects.exists()


@pytest.mark.parametrize(
    ("db_field", "raw", "expected"),
    [
        (models.IntegerField(), "−۴۲", -42),
        (models.FloatField(), "−١٢٫٧٥", -12.75),
        (
            models.DateTimeField(),
            "\u200f۲۰۲۴-۰۳-۰۵ ۱۴:۳۰:۰۹",
            datetime(2024, 3, 5, 14, 30, 9, tzinfo=timezone.utc),
        ),
    ],
    ids=["signed-integer", "float", "non-split-datetime"],
)
def test_generated_fields_normalize_input_before_validation(admin_user, db_field, raw, expected):
    # No schema changes needed for types absent from the fixture models.
    db_field.set_attributes_from_name("sample")
    kwargs = {}
    if isinstance(db_field, models.DateTimeField):
        kwargs = {"form_class": forms.DateTimeField, "widget": forms.DateTimeInput}
    with translation.override("he"):
        field = make_book_admin().formfield_for_dbfield(db_field, request_for(admin_user), **kwargs)
        assert field.clean(raw) == expected
        if isinstance(db_field, models.IntegerField):
            assert field.widget.input_type == "text"
            assert field.widget.attrs["inputmode"] == "numeric"


def test_normalization_uses_the_form_instances_field_configuration(admin_user):
    # A wrapper bound to the form class's base_fields would use the wrong
    # input_formats for one (or both) instances of the same ModelForm.
    form_class = make_book_admin(fields=("published_on",)).get_form(request_for(admin_user))
    first = form_class(data={"published_on": "٠٥/٠٣/٢٠٢٤"})
    second = form_class(data=first.data)
    first.fields["published_on"].input_formats = ["%d/%m/%Y"]
    second.fields["published_on"].input_formats = ["%m/%d/%Y"]
    assert first.is_valid() and second.is_valid()
    assert first.cleaned_data["published_on"] == date(2024, 3, 5)
    assert second.cleaned_data["published_on"] == date(2024, 5, 3)


@override_settings(USE_THOUSAND_SEPARATOR=True)
def test_localized_three_decimal_places_are_not_mistaken_for_a_group(admin_user):
    # In German the hard-coded dot in "1.250" would be silently removed as
    # grouping, storing 1250 instead of 1.25, not even raising a form error.
    db_field = models.DecimalField(max_digits=7, decimal_places=3)
    db_field.set_attributes_from_name("amount")
    with translation.override("de"):
        field = make_book_admin().formfield_for_dbfield(
            db_field, request_for(admin_user), localize=True
        )
        assert field.clean("١٫٢٥٠") == Decimal("1.250")


# -- Arabic search folding ---------------------------------------------------

SEARCH_LANGUAGES = ("ar", "fa", "en")


@pytest.fixture
def get_changelist_results(admin_client, settings):
    settings.LANGUAGES = [*settings.LANGUAGES, ("fa", "Persian")]

    def fetch(url, q, language="ar"):
        with translation.override(language):
            response = admin_client.get(url, {"q": q}, headers={"accept-language": language})
        assert response.status_code == 200
        assert response.wsgi_request.LANGUAGE_CODE == language
        return list(response.context["cl"].result_list)

    return fetch


@pytest.mark.parametrize("language", SEARCH_LANGUAGES)
@pytest.mark.parametrize(
    ("stored", "query"),
    [
        ("أحمد", "احمد"),
        ("احمد", "أحمد"),
        ("إبراهيم", "ابراهيم"),
        ("آدم", "ادم"),
        ("ٱبن خلدون", "ابن"),
        ("مُحَمَّدٌ", "محمد"),
        ("محمد", "مُحَمَّدٌ"),
        ("مدرسة", "مدرسه"),
        ("مدرسه", "مدرسة"),
        ("على", "علي"),
        ("علي", "على"),
        ("علی", "علي"),
        ("بئر", "بير"),
        ("کتاب", "كتاب"),
        ("مؤمن", "مومن"),
        ("مـحـمـد", "محمد"),
        ("محمد", "مـحـمـد"),
    ],
)
def test_book_and_thing_changelists_fold_arabic_forms(
    get_changelist_results, language, stored, query
):
    matched_book = Book.objects.create(title=stored, isbn="111")
    Book.objects.create(title="عنوان مختلف", isbn="222")
    matched_thing = Thing.objects.create(name=stored, reference="111")
    Thing.objects.create(name="عنصر مختلف", reference="222")

    assert get_changelist_results(BOOK_CHANGELIST_URL, query, language) == [matched_book]
    assert get_changelist_results(CHANGELIST_URL, query, language) == [matched_thing]


@pytest.mark.parametrize("language", SEARCH_LANGUAGES)
@pytest.mark.parametrize("query", ["٢٦٢", "۲۶۲"])
def test_book_and_thing_changelists_fold_localized_digits(
    get_changelist_results, thing, language, query
):
    Thing.objects.create(name="Other", reference="999-0-000-00000-0")
    matched_book = Book.objects.create(title="Deep Learning", isbn="978-0-262-03561-3")
    Book.objects.create(title="Other", isbn="999-0-000-00000-0")

    assert get_changelist_results(CHANGELIST_URL, query, language) == [thing]
    assert get_changelist_results(BOOK_CHANGELIST_URL, query, language) == [matched_book]


def test_search_honours_startswith_and_exact_prefixes(admin_user):
    exact = Book.objects.create(title="أحمد", isbn="1")
    prefix = Book.objects.create(title="أحمد شوقي", isbn="2")
    Book.objects.create(title="ديوان أحمد شوقي", isbn="3")
    request = request_for(admin_user)

    starts_admin = make_book_admin(search_fields=("^title",))
    starts_qs, _ = starts_admin.get_search_results(request, Book.objects.all(), "احمد")
    assert set(starts_qs) == {exact, prefix}

    exact_admin = make_book_admin(search_fields=("=title",))
    exact_qs, _ = exact_admin.get_search_results(request, Book.objects.all(), "احمد")
    assert list(exact_qs) == [exact]

    ends_admin = make_book_admin(search_fields=("title__iendswith",))
    ends_qs, _ = ends_admin.get_search_results(request, Book.objects.distinct(), "احمد")
    assert list(ends_qs) == [exact]


def test_search_skips_at_prefix_and_non_text_fields(admin_user):
    class ExactTextSearch(models.lookups.Exact):
        lookup_name = "search"

        def get_rhs_op(self, connection, rhs):
            return connection.operators["exact"] % rhs

    matched = Book.objects.create(title="أحمد", summary="مُحَمَّدٌ", isbn="1", price="10.00")
    summary_only = Book.objects.create(title="آخر", summary="مُحَمَّدٌ", isbn="2", price="20.00")
    request = request_for(admin_user)

    models.TextField.register_lookup(ExactTextSearch)
    try:
        at_admin = make_book_admin(search_fields=("title", "@summary"))
        # "@summary" is kept in super() (matching exact "مُحَمَّدٌ") but skipped for iregex.
        folded_title, _ = at_admin.get_search_results(request, Book.objects.all(), "احمد")
        assert list(folded_title) == [matched]
        unfolded_at, _ = at_admin.get_search_results(request, Book.objects.all(), "محمد")
        assert list(unfolded_at) == []
        exact_at, _ = at_admin.get_search_results(request, Book.objects.all(), "مُحَمَّدٌ")
        assert set(exact_at) == {matched, summary_only}
        both_at, _ = at_admin.get_search_results(request, Book.objects.all(), "احمد مُحَمَّدٌ")
        assert list(both_at) == [matched]
    finally:
        models.TextField._unregister_lookup(ExactTextSearch)

    t1 = Thing.objects.create(
        name="أحمد", reference="ref-42", quantity=42, price="15.00", is_active=True
    )
    t2 = Thing.objects.create(
        name="أحمد", reference="ref-7", quantity=7, price="99.00", is_active=False
    )

    empty_fields_admin = make_admin(search_fields=())
    no_fields_qs, _ = empty_fields_admin.get_search_results(request, Thing.objects.all(), "احمد")
    assert set(no_fields_qs) == {t1, t2}

    non_text_only = make_admin(search_fields=("quantity", "price", "published_on", "is_active"))
    only_non_text_qs, _ = non_text_only.get_search_results(request, Thing.objects.all(), "احمد")
    assert list(only_non_text_qs) == []

    id_only_admin = make_admin(search_fields=("reference", "id__exact"))
    num_qs, _ = id_only_admin.get_search_results(request, Thing.objects.all(), f"٤٢ {t1.pk}")
    assert list(num_qs) == [t1]

    mixed_fields = ["name", "quantity", "price", "published_on", "is_active", "=quantity"]
    if django.VERSION >= (5, 2):
        mixed_fields.extend(["id__exact", "is_active__exact"])
    mixed_admin = make_admin(search_fields=tuple(mixed_fields))
    single_qs, _ = mixed_admin.get_search_results(request, Thing.objects.all(), "احمد")
    assert set(single_qs) == {t1, t2}
    if django.VERSION >= (5, 2):
        two_term_qs, _ = mixed_admin.get_search_results(
            request, Thing.objects.all(), f"احمد {t1.pk}"
        )
        assert list(two_term_qs) == [t1]
        bool_true_qs, _ = mixed_admin.get_search_results(request, Thing.objects.all(), "احمد True")
        assert list(bool_true_qs) == [t1]
        bool_false_qs, _ = mixed_admin.get_search_results(
            request, Thing.objects.all(), "احمد False"
        )
        assert list(bool_false_qs) == [t2]


@pytest.mark.parametrize("language", SEARCH_LANGUAGES)
@pytest.mark.parametrize("stored_digits", ["٩٧٨", "۹۷۸"])
def test_arabic_word_plus_ascii_digits_matches_localized_digits_in_title(
    get_changelist_results, language, stored_digits
):
    matched = Book.objects.create(title=f"كتاب {stored_digits}", isbn="000")
    Book.objects.create(title="كتاب ١٢٣", isbn="111")
    Book.objects.create(title=f"مرجع {stored_digits}", isbn="222")

    assert get_changelist_results(BOOK_CHANGELIST_URL, "كتاب 978", language) == [matched]


def test_multi_term_search_ands_terms_and_unescapes_quotes(get_changelist_results, settings):
    target = Book.objects.create(title="أحمد بن خلدون", isbn="978-1", summary="Dune edition")
    Book.objects.create(title="أحمد شوقي بن سينا", isbn="978-2", summary="Other")
    Book.objects.create(title="عبد الرحمن بن خلدون", isbn="978-3", summary="Dune edition")

    assert get_changelist_results(BOOK_CHANGELIST_URL, "احمد خلدون") == [target]
    assert get_changelist_results(BOOK_CHANGELIST_URL, '"احمد بن" خلدون') == [target]

    summary_admin_cls = type(
        "SummaryBookAdmin", (BookAdmin,), {"search_fields": ("title", "summary")}
    )
    settings.ROOT_URLCONF = book_urlconf(summary_admin_cls)
    assert get_changelist_results(BOOK_CHANGELIST_URL, "احمد Dune") == [target]


def test_related_lookups_track_duplicates_and_deduplicate_changelist(
    admin_user, get_changelist_results, settings
):
    history = Category.objects.create(name="الإسلام والتاريخ")
    matched = Book.objects.create(title="كتاب", isbn="1", category=history)
    other = Book.objects.create(title="آخر", isbn="2", category=None)
    Chapter.objects.create(book=matched, number=1, title="الفصل الأول")
    Chapter.objects.create(book=matched, number=2, title="المبحث الأول")
    Chapter.objects.create(book=other, number=1, title="الفصل الثاني")
    request = request_for(admin_user)

    fk_admin = make_book_admin(search_fields=("^category__name",))
    fk_qs, fk_dup = fk_admin.get_search_results(request, Book.objects.all(), "الاسلام")
    assert not fk_dup
    assert list(fk_qs) == [matched]

    rev_cls = type("ChapterSearchBookAdmin", (BookAdmin,), {"search_fields": ("chapter__title",)})
    rev_admin = rev_cls(Book, admin.site)
    _, rev_dup = rev_admin.get_search_results(request, Book.objects.all(), "الاول")
    assert rev_dup

    settings.ROOT_URLCONF = book_urlconf(rev_cls)
    assert get_changelist_results(BOOK_CHANGELIST_URL, "الاول") == [matched]


def test_autocomplete_folds_on_mixin_admin_but_not_plain_admin(admin_client):
    book = Book.objects.create(title="أحمد شوقي", isbn="111")
    Book.objects.create(title="طٰه حسين", isbn="222")
    Category.objects.create(name="تاريخ الإسلام")

    mixin_resp = admin_client.get(
        "/admin/autocomplete/",
        {"app_label": "testapp", "model_name": "chapter", "field_name": "book", "term": "احمد"},
    )
    assert mixin_resp.status_code == 200
    assert mixin_resp.json()["results"] == [{"id": str(book.pk), "text": "أحمد شوقي"}]

    plain_resp = admin_client.get(
        "/admin/autocomplete/",
        {"app_label": "testapp", "model_name": "book", "field_name": "category", "term": "الاسلام"},
    )
    assert plain_resp.status_code == 200
    assert plain_resp.json()["results"] == []


@pytest.mark.parametrize(
    ("admin_factory", "global_enabled", "folds"),
    [
        pytest.param(stock_book_admin_cls, True, False, id="plain-modeladmin"),
        pytest.param(lambda: BookAdmin, False, False, id="global-off"),
        pytest.param(
            lambda: variant(BookAdmin, bidi_fold_search=False), True, False, id="admin-off"
        ),
        pytest.param(lambda: variant(BookAdmin, bidi_fold_search=True), False, True, id="admin-on"),
    ],
)
def test_search_folding_opt_out_and_plain_admin_precedence(
    get_changelist_results, settings, admin_factory, global_enabled, folds
):
    book = Book.objects.create(title="أحمد", isbn="111")
    settings.ROOT_URLCONF = book_urlconf(admin_factory())
    settings.RTL_ADMIN = {"FOLD_ARABIC_SEARCH": global_enabled}

    results = get_changelist_results(BOOK_CHANGELIST_URL, "احمد")
    assert results == ([book] if folds else [])
    assert get_changelist_results(BOOK_CHANGELIST_URL, "أحمد") == [book]


@pytest.mark.parametrize("empty_after_fold", ["\u0640", "\u064e\u0651", "\u200f", '""'])
def test_terms_folding_to_empty_do_not_match_every_row(admin_user, empty_after_fold):
    Book.objects.create(title="أحمد", isbn="111")
    request = request_for(admin_user)
    bidi_admin = BookAdmin(Book, admin.site)
    stock_admin = stock_book_admin_cls()(Book, admin.site)

    bidi_qs, _ = bidi_admin.get_search_results(request, Book.objects.all(), empty_after_fold)
    stock_qs, _ = stock_admin.get_search_results(request, Book.objects.all(), empty_after_fold)
    assert list(bidi_qs) == list(stock_qs)


def test_regex_metacharacters_in_arabic_queries_match_literally(admin_user):
    literal = Book.objects.create(title="أحمد (ج١) [نسخة] a+b*c?.^$|\\:10:30", isbn="1")
    Book.objects.create(title="أحمد ج1 نسخة axbyczX:10:30", isbn="2")
    request = request_for(admin_user)
    bidi_admin = BookAdmin(Book, admin.site)

    qs, _ = bidi_admin.get_search_results(
        request, Book.objects.all(), "احمد (ج1) [نسخه] a+b*c?.^$|\\:10:30"
    )
    assert list(qs) == [literal]


@pytest.mark.parametrize(
    "query",
    ["", "978", "Deep Learning", "978-0-262-03561-3", "a+b*c?", "שלום עולם"],
)
def test_ascii_and_hebrew_queries_produce_identical_sql_to_stock_modeladmin(admin_user, query):
    request = request_for(admin_user)
    base_qs = Book.objects.all()
    bidi_admin = BookAdmin(Book, admin.site)
    stock_admin = stock_book_admin_cls()(Book, admin.site)

    bidi_qs, bidi_dup = bidi_admin.get_search_results(request, base_qs, query)
    stock_qs, stock_dup = stock_admin.get_search_results(request, base_qs, query)
    assert bidi_dup == stock_dup
    assert bidi_qs.query.sql_with_params() == stock_qs.query.sql_with_params()


# -- Arabic changelist ordering ----------------------------------------------


@pytest.fixture
def arabic_titles(db):
    # Expected dictionary order after folding alef variants and vowel marks.
    # Raw code-point order puts آفاق first, not after أُصول.
    titles = ("أبواب المدينة", "إدارة الوقت", "أُصول اللغة", "آفاق العلم", "بَحر الشعر", "بلاد النيل")
    for i, title in enumerate(titles[::2] + titles[1::2]):
        Book.objects.create(title=title, isbn=str(i))
    return titles


@pytest.mark.parametrize("language", ["ar", "en"])
@pytest.mark.parametrize("order", ["1", "-1"])
def test_arabic_ordering_title_sort_link(admin_client, arabic_titles, language, order):
    response = admin_client.get(
        BOOK_CHANGELIST_URL, {"o": order}, headers={"accept-language": language}
    )
    assert response.status_code == 200
    assert response.wsgi_request.LANGUAGE_CODE == language
    direction = "ascending" if order == "1" else "descending"
    assert f"column-title sorted {direction}" in response.content.decode()
    cl = response.context["cl"]
    expected = list(arabic_titles if order == "1" else reversed(arabic_titles))
    # Check the database order as well as the first rendered page: sorting
    # only the rows already fetched by the paginator gives the wrong page.
    assert list(cl.queryset.values_list("title", flat=True)) == expected
    assert [book.title for book in cl.result_list] == expected[: BookAdmin.list_per_page]


@pytest.mark.parametrize("order", ["1", "-1"])
def test_arabic_ordering_equivalent_titles_use_descending_pk(admin_user, order):
    # Each pair differs by just one letter: hamzated alef, ta marbuta,
    # or alef maqsura. Both the pairs and their members are in raw SQL order.
    pairs = [
        ("أيام العرب", "ايام العرب"),
        ("رحلة الشتاء", "رحله الشتاء"),
        ("صدى الجبال", "صدي الجبال"),
    ]
    if order == "-1":
        pairs = [pair[::-1] for pair in reversed(pairs)]

    raw_pks = []
    folded_pks = []
    for titles in pairs:
        # Insert in the requested raw order, so *every* pair must swap places
        # when its keys tie and Django's -pk tiebreaker takes over.
        pks = [Book.objects.create(title=title, isbn="1").pk for title in titles]
        raw_pks.extend(pks)
        folded_pks.extend(reversed(pks))

    def changelist_pks(admin_class):
        response = render_book_changelist(admin_class(Book, admin.site), admin_user, o=order)
        return list(response.context_data["cl"].queryset.values_list("pk", flat=True))

    assert changelist_pks(stock_book_admin_cls()) == raw_pks
    assert changelist_pks(BookAdmin) == folded_pks


def test_arabic_ordering_textfield_with_isolation_off(admin_user):
    first = Book.objects.create(title="Z", isbn="2", summary="أبواب المدينة")
    second = Book.objects.create(title="A", isbn="1", summary="آفاق العلم")
    model_admin = make_book_admin(
        list_display=("isbn", "summary"),
        bidi_arabic_ordering=("summary",),
        bidi_isolate_changelist=False,
    )
    response = render_book_changelist(model_admin, admin_user, o="1")
    assert list(response.context_data["cl"].result_list) == [first, second]


def test_arabic_ordering_honours_modeladmin_ordering(admin_user, arabic_titles):
    model_admin = make_book_admin(
        list_display=("title", "isbn"), bidi_arabic_ordering=("title",), ordering=("-title", "isbn")
    )
    # A later pk would win Django's default tiebreaker, but must not win
    # ahead of the explicitly configured secondary ordering field.
    tied_title = arabic_titles[-1]
    Book.objects.create(title=tied_title, isbn="999")
    response = render_book_changelist(model_admin, admin_user)
    rows = list(response.context_data["cl"].result_list)
    assert [book.title for book in rows] == [tied_title, *reversed(arabic_titles)]
    assert rows[0].isbn < rows[1].isbn


@pytest.mark.parametrize(
    ("fields", "order", "global_enabled"),
    [
        pytest.param(("title",), "2", True, id="unlisted-isbn"),
        pytest.param((), "1", True, id="no-fields"),
        pytest.param(("title",), "1", False, id="global-off"),
    ],
)
def test_arabic_ordering_inactive_sort_matches_stock_sql(
    admin_user, arabic_titles, fields, order, global_enabled
):
    class PlainBookAdmin(admin.ModelAdmin):
        list_display = ("title", "isbn")

    class BidiBookAdmin(BidiSafeAdminMixin, PlainBookAdmin):
        bidi_arabic_ordering = fields

    def queryset(admin_class):
        response = render_book_changelist(admin_class(Book, admin.site), admin_user, o=order)
        return response.context_data["cl"].queryset

    with (
        override_settings(RTL_ADMIN={"ARABIC_ORDERING": global_enabled}),
        translation.override("ar"),
    ):
        stock = queryset(PlainBookAdmin)
        bidi = queryset(BidiBookAdmin)
        assert bidi.query.sql_with_params() == stock.query.sql_with_params()
        assert list(bidi) == list(stock)
        if order == "1":
            raw_titles = list(Book.objects.order_by("title").values_list("title", flat=True))
            assert raw_titles != list(arabic_titles)
            assert [book.title for book in bidi] == raw_titles


def test_arabic_ordering_preserves_custom_changelist_and_orderby(admin_user, arabic_titles):
    from django.contrib.admin.views.main import ChangeList

    title_desc = models.F("title").desc(nulls_last=True)

    class CustomChangeList(ChangeList):
        def get_ordering(self, request, queryset):
            return [title_desc]

    class CustomAdmin(admin.ModelAdmin):
        def get_changelist(self, request, **kwargs):
            return CustomChangeList

    class OrderedAdmin(BidiSafeAdminMixin, CustomAdmin):
        bidi_arabic_ordering = ("title",)

    response = render_book_changelist(OrderedAdmin(Book, admin.site), admin_user)
    cl = response.context_data["cl"]
    assert isinstance(cl, CustomChangeList)
    assert [book.title for book in cl.result_list] == list(reversed(arabic_titles))
    folded, tiebreaker = cl.queryset.query.order_by
    assert folded.descending and folded.nulls_last
    assert tiebreaker == "-pk"
    assert title_desc.expression == models.F("title")  # The custom ordering wasn't mutated.


def test_plain_modeladmin_ignores_arabic_ordering(admin_user, arabic_titles):
    # This plain admin copies BookAdmin's opt-in attribute, but not the mixin.
    plain = stock_book_admin_cls()(Book, admin.site)
    with translation.override("ar"):
        response = render_book_changelist(plain, admin_user, o="1")
    qs = response.context_data["cl"].queryset
    raw_titles = list(Book.objects.order_by("title").values_list("title", flat=True))
    assert list(qs.values_list("title", flat=True)) == raw_titles


# -- changelist digit localization -------------------------------------------


class TemporalBookAdmin(BookAdmin):
    list_display = (
        "title",
        "isbn",
        "category",
        "status",
        "published_on",
        "available_from",
        "launch_time",
        "price",
        "code_badge",
    )

    @admin.display(description="Badge", ordering="title")
    def code_badge(self, obj):
        return f"B-{obj.pk}"


def _strip_csrf(html: str) -> str:
    return re.sub(
        r'name="csrfmiddlewaretoken" value="[^"]+"',
        'name="csrfmiddlewaretoken" value="TOKEN"',
        html,
    )


def _extract_cell(html: str, field: str) -> str:
    match = re.search(
        rf'<(?:td|th) class="field-{re.escape(field)}(?:\s+[^"]*)?">(.*?)</(?:td|th)>',
        html,
        re.S,
    )
    assert match is not None, f"missing field-{field} cell"
    return match.group(1)


def _create_sample_book() -> Book:
    category = Category.objects.create(name="Shelf 7")
    return Book.objects.create(
        title="Edition 2026",
        isbn="978-0-262-03561-3",
        category=category,
        status="draft",
        published_on=date(2026, 3, 5),
        available_from=datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc),
        launch_time=time(9, 15),
        price=Decimal("1234.50"),
    )


@pytest.mark.parametrize(
    ("language", "expected_system"),
    [
        ("ar-eg", "arab"),
        ("fa", "arabext"),
        ("ar", "latn"),
        ("en", "latn"),
        ("he", "latn"),
    ],
)
def test_book_changelist_localizes_digits_only_in_non_latin_locales(
    admin_client, settings, language, expected_system
):
    settings.LANGUAGES = [*settings.LANGUAGES, ("fa", "Persian")]
    settings.ROOT_URLCONF = book_urlconf(TemporalBookAdmin)
    book = _create_sample_book()

    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": False}),
        translation.override(language),
    ):
        off_resp = admin_client.get(BOOK_CHANGELIST_URL, headers={"accept-language": language})
    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": True}),
        translation.override(language),
    ):
        on_resp = admin_client.get(BOOK_CHANGELIST_URL, headers={"accept-language": language})

    assert off_resp.status_code == on_resp.status_code == 200
    assert on_resp.wsgi_request.LANGUAGE_CODE == language
    off_html = off_resp.content.decode()
    on_html = on_resp.content.decode()

    if expected_system == "latn":
        assert _strip_csrf(on_html) == _strip_csrf(off_html)
        return

    with translation.override(language):
        assert numbering_system() == expected_system
        for field_name in ("published_on", "available_from", "launch_time", "price"):
            db_field = Book._meta.get_field(field_name)
            django_rendered = display_for_field(getattr(book, field_name), db_field, "-")
            expected = FSI + transliterate_digits(django_rendered, expected_system) + PDI
            cell = _extract_cell(on_html, field_name)
            assert cell == expected
            assert not re.search(r"[0-9]", cell)

    if language == "ar-eg":
        assert "١٢٣٤,٥٠" in _extract_cell(on_html, "price")
        assert "٢٠٢٦" in _extract_cell(on_html, "published_on")
    elif language == "fa":
        assert "۱۲۳۴.۵۰" in _extract_cell(on_html, "price")
        assert "۲۰۲۶" in _extract_cell(on_html, "published_on")

    # CharField, ForeignKey, choices, and callable columns stay untouched.
    assert _extract_cell(on_html, "title") == _extract_cell(off_html, "title")
    assert f"{FSI}Edition 2026{PDI}" in _extract_cell(on_html, "title")
    assert _extract_cell(on_html, "isbn") == f"{FSI}978-0-262-03561-3{PDI}"
    assert _extract_cell(on_html, "category") == f"{FSI}Shelf 7{PDI}"
    assert _extract_cell(on_html, "status") == _extract_cell(off_html, "status")
    assert _extract_cell(on_html, "code_badge") == f"{FSI}B-{book.pk}{PDI}"


@pytest.mark.parametrize(
    ("admin_factory", "global_enabled", "localizes"),
    [
        pytest.param(lambda: TemporalBookAdmin, False, False, id="default-off"),
        pytest.param(lambda: TemporalBookAdmin, True, True, id="global-on"),
        pytest.param(
            lambda: variant(TemporalBookAdmin, bidi_local_digits=False),
            True,
            False,
            id="admin-override-off",
        ),
        pytest.param(
            lambda: variant(TemporalBookAdmin, bidi_local_digits=True),
            False,
            True,
            id="admin-override-on",
        ),
        pytest.param(
            lambda: variant(
                stock_book_admin_cls(),
                list_display=("title", "isbn", "published_on", "available_from", "price"),
            ),
            True,
            False,
            id="plain-modeladmin",
        ),
    ],
)
def test_changelist_digit_localization_switches_and_plain_modeladmin(
    admin_client, settings, admin_factory, global_enabled, localizes
):
    settings.ROOT_URLCONF = book_urlconf(admin_factory())
    _create_sample_book()

    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": global_enabled}),
        translation.override("ar-eg"),
    ):
        resp = admin_client.get(BOOK_CHANGELIST_URL, headers=AR_EG)
    assert resp.status_code == 200
    price_cell = _extract_cell(resp.content.decode(), "price")
    if localizes:
        assert price_cell == f"{FSI}١٢٣٤,٥٠{PDI}"
    else:
        assert "1234,50" in price_cell
        assert "١٢٣٤" not in price_cell


@pytest.mark.parametrize(
    ("language", "numerals", "expected_price"),
    [
        ("en", "arab", f"{FSI}١٢٣٤.٥٠{PDI}"),
        ("ar", "arab", f"{FSI}١٢٣٤,٥٠{PDI}"),
        ("en", "arabext", f"{FSI}۱۲۳۴.۵۰{PDI}"),
        ("ar-eg", "latn", f"{FSI}1234,50{PDI}"),
        ("fa", "latn", f"{FSI}1234.50{PDI}"),
    ],
)
def test_changelist_digit_localization_honours_numerals_override(
    admin_client, settings, language, numerals, expected_price
):
    settings.LANGUAGES = [*settings.LANGUAGES, ("fa", "Persian")]
    settings.ROOT_URLCONF = book_urlconf(TemporalBookAdmin)
    _create_sample_book()

    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": True, "NUMERALS": numerals}),
        translation.override(language),
    ):
        resp = admin_client.get(BOOK_CHANGELIST_URL, headers={"accept-language": language})
    assert resp.status_code == 200
    assert _extract_cell(resp.content.decode(), "price") == expected_price


@pytest.mark.parametrize("via_attribute", [False, True])
def test_changelist_digit_localization_works_when_isolation_is_disabled_and_keeps_sorting(
    admin_client, settings, via_attribute
):
    admin_cls = variant(
        TemporalBookAdmin,
        list_display=("price", "title", "isbn", "published_on"),
        list_display_links=("price",),
        sortable_by=("price", "published_on"),
        **({"bidi_isolate_changelist": False, "bidi_local_digits": True} if via_attribute else {}),
    )
    settings.ROOT_URLCONF = book_urlconf(admin_cls)
    cheap = Book.objects.create(
        title="Book 1",
        isbn="978-1",
        published_on=date(2025, 1, 2),
        price=Decimal("10.00"),
    )
    expensive = Book.objects.create(
        title="Book 2",
        isbn="978-2",
        published_on=date(2026, 3, 5),
        price=Decimal("99.50"),
    )
    rtl_cfg = (
        {} if via_attribute else {"ISOLATE_CHANGELIST": False, "LOCALIZE_CHANGELIST_DIGITS": True}
    )

    with override_settings(RTL_ADMIN=rtl_cfg), translation.override("ar-eg"):
        resp = admin_client.get(BOOK_CHANGELIST_URL, {"o": "-1"}, headers=AR_EG)
    assert resp.status_code == 200
    assert list(resp.context["cl"].result_list) == [expensive, cheap]
    html = resp.content.decode()
    assert not any(ch in html for ch in (*ISOLATE_OPENERS, PDI))
    assert "sortable column-price" in html
    assert (
        f'<a href="/admin/testapp/book/{expensive.pk}/change/?_changelist_filters=o%3D-1">٩٩,٥٠</a>'
    ) in html
    assert _extract_cell(html, "isbn") in ("978-2", "978-1")
    assert _extract_cell(html, "title") in ("Book 2", "Book 1")

    # In Latin-digit locales, disabling isolation + enabling local digits stays stock-identical.
    with (
        override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False}),
        translation.override("en"),
    ):
        stock_en = admin_client.get(BOOK_CHANGELIST_URL).content.decode()
    with (
        override_settings(
            RTL_ADMIN={"ISOLATE_CHANGELIST": False, "LOCALIZE_CHANGELIST_DIGITS": True}
        ),
        translation.override("en"),
    ):
        digits_en = admin_client.get(BOOK_CHANGELIST_URL).content.decode()
    assert _strip_csrf(digits_en) == _strip_csrf(stock_en)


def test_per_field_isolation_exclusions_still_localize_digits(admin_user):
    book = _create_sample_book()
    model_admin = make_book_admin(
        list_display=("title", "isbn", "price"),
        bidi_isolate_fields=("isbn",),
        bidi_local_digits=True,
    )
    with translation.override("ar-eg"):
        display = model_admin.get_list_display(request_for(admin_user))
        assert display[2].admin_order_field == "price"
        html = render_book_changelist(model_admin, admin_user).content.decode()
    assert re.search(r'<th[^>]*class="sortable column-price"[^>]*>.*?href="\?o=[^"]+"', html, re.S)
    assert _extract_cell(html, "isbn") == f"{FSI}{book.isbn}{PDI}"
    assert _extract_cell(html, "price") == "١٢٣٤,٥٠"


@pytest.mark.django_db(transaction=True)
def test_integer_float_duration_choices_and_callables_on_changelist(admin_user, settings):
    class MetricSample(models.Model):
        label = models.CharField(max_length=50)
        count = models.IntegerField()
        ratio = models.FloatField()
        elapsed = models.DurationField()
        tier = models.IntegerField(choices=[(1, "Tier 1"), (2, "Tier 2")], default=1)
        active = models.BooleanField(default=True)

        class Meta:
            app_label = "testapp"

        def __str__(self):
            return self.label

    with connection.schema_editor() as editor:
        editor.create_model(MetricSample)
    try:
        sample = MetricSample.objects.create(
            label="Run 42",
            count=-42,
            ratio=12.5,
            elapsed=timedelta(days=2, hours=3, minutes=4, seconds=5),
            tier=1,
            active=True,
        )

        def raw_callable(obj):
            return f"C-{obj.count}"

        site = AdminSite()
        admin_cls = type(
            "MetricSampleAdmin",
            (BidiSafeAdminMixin, admin.ModelAdmin),
            {
                "list_display": (
                    "id",
                    "label",
                    "count",
                    "ratio",
                    "elapsed",
                    "tier",
                    "active",
                    raw_callable,
                ),
                "bidi_local_digits": True,
            },
        )
        site.register(MetricSample, admin_cls)
        urlconf = ModuleType("tests.urls_metrics")
        urlconf.urlpatterns = [path("admin/", site.urls)]
        settings.ROOT_URLCONF = urlconf

        model_admin = site._registry[MetricSample]
        request = RequestFactory().get("/admin/testapp/metricsample/")
        request.user = admin_user
        with translation.override("ar-eg"):
            resp = model_admin.changelist_view(request)
            resp.render()
            html = resp.content.decode()

        assert _extract_cell(html, "id") == (
            f'<a href="/admin/testapp/metricsample/{sample.pk}/change/">'
            f"{FSI}{transliterate_digits(str(sample.pk), 'arab')}{PDI}</a>"
        )
        assert _extract_cell(html, "label") == f"{FSI}Run 42{PDI}"
        assert _extract_cell(html, "count") == f"{FSI}-٤٢{PDI}"
        assert _extract_cell(html, "ratio") == f"{FSI}١٢,٥{PDI}"
        assert _extract_cell(html, "elapsed") == f"{FSI}٢ days, ٣:٠٤:٠٥{PDI}"
        assert _extract_cell(html, "tier") == f"{FSI}Tier 1{PDI}"
        assert 'src="/static/admin/img/icon-yes.svg"' in _extract_cell(html, "active")
        assert f"C-{sample.count}" in html
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(MetricSample)
        apps.all_models["testapp"].pop("metricsample", None)
        apps.clear_cache()


@related_lookups
def test_related_lookup_cells_localize_digits_and_keep_sorting(admin_user):
    category = Category.objects.create(name="Cat 9", is_featured=True)
    book_a = Book.objects.create(
        title="Alpha",
        isbn="978-1",
        category=category,
        published_on=date(2025, 2, 3),
        available_from=datetime(2025, 2, 3, 8, 5, tzinfo=timezone.utc),
        launch_time=time(7, 30),
        price=Decimal("20.00"),
    )
    book_b = Book.objects.create(
        title="Beta",
        isbn="978-2",
        category=None,
        published_on=date(2026, 4, 6),
        available_from=datetime(2026, 4, 6, 16, 45, tzinfo=timezone.utc),
        launch_time=time(19, 10),
        price=Decimal("5.50"),
    )
    ch_a = Chapter.objects.create(book=book_a, number=1, title="Ch 1")
    ch_b = Chapter.objects.create(book=book_b, number=2, title="Ch 2")

    chapter_admin = type(
        "BidiChapterAdmin",
        (BidiSafeAdminMixin, admin.ModelAdmin),
        {
            "list_display": (
                "title",
                "number",
                "book__price",
                "book__published_on",
                "book__available_from",
                "book__launch_time",
                "book__isbn",
                "book__category__id",
                "book__category__is_featured",
            ),
            "bidi_local_digits": True,
        },
    )(Chapter, admin.site)

    request = RequestFactory().get("/admin/testapp/chapter/", {"o": "3"})
    request.user = admin_user
    with translation.override("fa"):
        resp = chapter_admin.changelist_view(request)
        resp.render()
        html = resp.content.decode()

    assert chapter_admin.get_list_display(request)[-1] == "book__category__is_featured"
    assert list(resp.context_data["cl"].result_list) == [ch_b, ch_a]
    assert "sortable column-book__price" in html
    assert _extract_cell(html, "number") in (f"{FSI}۱{PDI}", f"{FSI}۲{PDI}")
    assert f"{FSI}۵.۵۰{PDI}" in html
    assert f"{FSI}۲۰.۰۰{PDI}" in html
    assert "۲۰۲۶" in _extract_cell(html, "book__published_on")
    assert "۲۰۲۶" in _extract_cell(html, "book__available_from")
    assert f"{FSI}۱۹:۱۰{PDI}" in html
    assert f"{FSI}978-1{PDI}" in html
    assert '<td class="field-book__category__id">-</td>' in html
    featured_cells = re.findall(
        r'<td class="field-book__category__is_featured">(.*?)</td>',
        html,
        re.S,
    )
    assert len(featured_cells) == 2
    assert featured_cells[0] in ("-", '<img src="/static/admin/img/icon-unknown.svg" alt="None">')
    assert "True" in featured_cells[1]
    assert not any(ch in cell for cell in featured_cells for ch in (*ISOLATE_OPENERS, PDI))


def test_empty_values_html_tags_list_editable_and_chrome_stay_untouched(
    admin_client, admin_user, settings
):
    # Null / empty_value_display containing digits is never rewritten.
    Book.objects.create(
        title="AA Null dates",
        isbn="978-0",
        published_on=None,
        available_from=None,
        launch_time=None,
        price=Decimal("15.00"),
    )
    null_admin = make_book_admin(
        list_display=("title", "published_on", "available_from", "launch_time", "price"),
        empty_value_display="-0-",
        bidi_local_digits=True,
    )
    with translation.override("ar-eg"):
        null_html = render_book_changelist(null_admin, admin_user).content.decode()
    for field_name in ("published_on", "available_from", "launch_time"):
        assert _extract_cell(null_html, field_name) == "-0-"
    assert _extract_cell(null_html, "price") == f"{FSI}١٥,٠٠{PDI}"

    # SafeData HTML tags and numeric character references stay untouched inside markup.
    with translation.override("ar-eg"):
        tagged = mark_safe('<a href="/books/42/?p=2" data-v="9">Book 42&#45;7</a>')
        assert _localize_cell_digits(tagged) == (
            '<a href="/books/42/?p=2" data-v="9">Book ٤٢&#45;٧</a>'
        )
        assert isinstance(_localize_cell_digits(tagged), SafeData)
        icon = mark_safe('<img src="/static/v2/icon-yes.svg" alt="True">')
        assert _localize_cell_digits(icon) == icon

    # list_editable inputs stay ASCII even when changelist digit localization is on.
    settings.ROOT_URLCONF = book_urlconf(InputBookAdmin)
    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": True}),
        translation.override("ar-eg"),
    ):
        editable_html = admin_client.get(BOOK_CHANGELIST_URL, headers=AR_EG).content.decode()
    assert 'value="15.00"' in editable_html

    # Filters, paginator, date hierarchy, and action counter stay byte-identical.
    for index in range(6):
        Book.objects.create(
            title=f"Extra {index}",
            isbn=f"978-{index + 10}",
            published_on=date(2026, 3, index + 1),
            price=Decimal("20.00") + index,
        )
    settings.ROOT_URLCONF = book_urlconf(variant(BookAdmin, empty_value_display="-0-"))
    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": False}),
        translation.override("ar-eg"),
    ):
        chrome_off = admin_client.get(BOOK_CHANGELIST_URL, headers=AR_EG).content.decode()
    with (
        override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": True}),
        translation.override("ar-eg"),
    ):
        chrome_on = admin_client.get(BOOK_CHANGELIST_URL, headers=AR_EG).content.decode()

    assert '<td class="field-published_on">-0-</td>' in chrome_on
    assert f"{FSI}١٥,٠٠{PDI}" in chrome_on
    assert 'data-actions-icnt="5"' in chrome_on
    assert re.sub(r"<tbody>.*?</tbody>", "", _strip_csrf(chrome_on), flags=re.S) == re.sub(
        r"<tbody>.*?</tbody>", "", _strip_csrf(chrome_off), flags=re.S
    )
