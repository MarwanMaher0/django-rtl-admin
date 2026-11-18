"""``BidiSafeAdminMixin`` applied to a real changelist."""

import re
from types import ModuleType

import django
import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.exceptions import ObjectDoesNotExist
from django.test import RequestFactory, override_settings
from django.urls import include, path
from django.utils import translation
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from django_rtl_admin import BidiSafeAdminMixin
from django_rtl_admin.bidi import FSI, ISOLATE_OPENERS, LRI, PDI, RLI, isolate

from .testapp.admin import BidiThingAdmin
from .testapp.models import Book, Category, Chapter, Review, Thing

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


def stock_delete_urlconf(stock_cls):
    """A URLconf whose admin site mirrors the default one, with a stock Thing admin.

    ``admin.site.urls`` is built once at import time, so swapping the registry
    alone would not change which admin serves the requests.
    """
    site = AdminSite()
    for model, model_admin in admin.site._registry.items():
        site.register(model, stock_cls if model is Thing else type(model_admin))
    urlconf = ModuleType("tests.urls_stock_delete")
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
    with override_settings(ROOT_URLCONF=stock_delete_urlconf(stock_cls)):
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
    with override_settings(ROOT_URLCONF=stock_delete_urlconf(stock_thing_admin_cls())):
        stock_html = admin_client.get(url, headers=AR_EG).content.decode()

    def breadcrumb(html):
        return re.search(rf'<a href="/admin/testapp/thing/{thing.pk}/change/">([^<]*)</a>', html)

    assert delete_question(bidi_html) == delete_question(stock_html)
    assert breadcrumb(bidi_html).group(1) == breadcrumb(stock_html).group(1)
    assert FSI not in delete_question(bidi_html)
    assert FSI not in breadcrumb(bidi_html).group(1)
