"""Arabic initial filters on a stock ModelAdmin and the SQLite test database."""

from urllib.parse import parse_qs, urlsplit

import django
import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.utils import translation

from django_rtl_admin import ArabicInitialListFilter, arabic_initial_filter, isolate

from .testapp.models import Book, Category, Thing

pytestmark = pytest.mark.django_db


def bind_filter(filter_class, model_admin=None, **query):
    """Bind a SimpleListFilter as ChangeList does on each Django series."""
    if model_admin is None:
        model_admin = admin.ModelAdmin(Book, AdminSite())
    request = RequestFactory().get("/", query)
    params = request.GET.dict() if django.VERSION < (5, 0) else dict(request.GET.lists())
    return filter_class(request, params, model_admin.model, model_admin), request


def create_books(titles):
    Book.objects.bulk_create([Book(title=title) for title in titles])


def filtered_titles(spec, request, queryset=None):
    if queryset is None:
        queryset = Book.objects.all()
    return set(spec.queryset(request, queryset).values_list("title", flat=True))


def test_lookup_values_and_labels_follow_arabic_and_persian_alphabet_order():
    letters = "ب پ ت ج چ ح ز ژ س ك ک گ ل ي ی".split()
    create_books([*reversed(letters), "Zoo", "apple", "Apricot", "۳", "!"])
    filter_class = arabic_initial_filter("title")
    with translation.override("ar"):
        spec, _ = bind_filter(filter_class)
        assert spec.lookup_choices == [
            *((letter, isolate(letter)) for letter in [*letters, "A", "Z", "0-9"]),
            ("other", isolate("أخرى")),
        ]

    # In particular, Arabic kaf/ya and their Persian forms are separate filters.
    for letter in letters:
        assert filtered_titles(*bind_filter(filter_class, title__initial=letter)) == {letter}


@pytest.fixture
def folded_titles():
    groups = {
        "ا": ["ابن", "آفاق", "إيمان", "أدب", "\u2067ـَٱلكتاب\u2069"],
        "ه": ["هواء", "ة"],
        "و": ["ورق", "ؤ"],
        "ي": ["يد", "ى", "ئ"],
        "M": ["Maps", "maps"],
        "0-9": ["2nd", "٠١٢", "۹۹", "४०"],
        "other": ["", "ـَ\u200f", "#index", "東京"],
    }
    create_books(title for titles in groups.values() for title in titles)
    return groups


@pytest.mark.parametrize("value", ["ا", "ه", "و", "ي", "M", "0-9", "other"])
def test_selected_bucket_matches_original_titles(folded_titles, value, django_assert_num_queries):
    spec, request = bind_filter(arabic_initial_filter("title"), title__initial=value)
    assert {key for key, _ in spec.lookup_choices} == set(folded_titles)
    with django_assert_num_queries(0):
        filtered = spec.queryset(request, Book.objects.all())
    with django_assert_num_queries(1):
        assert set(filtered.values_list("title", flat=True)) == set(folded_titles[value])


@pytest.mark.parametrize(
    "include_latin,include_digits", [(False, True), (True, False), (False, False)]
)
def test_disabled_categories_move_to_other(include_latin, include_digits):
    create_books(["كتاب", "Maps", "٤"])
    filter_class = arabic_initial_filter(
        "title", include_latin=include_latin, include_digits=include_digits
    )
    spec, request = bind_filter(filter_class, title__initial="other")
    expected_choices = ["ك"]
    expected_other = set()
    if include_latin:
        expected_choices.append("M")
    else:
        expected_other.add("Maps")
    if include_digits:
        expected_choices.append("0-9")
    else:
        expected_other.add("٤")
    assert [value for value, _ in spec.lookup_choices] == [*expected_choices, "other"]
    assert filtered_titles(spec, request) == expected_other


def test_factory_returns_configured_subclass_without_changing_defaults():
    custom = arabic_initial_filter("isbn", title="Identifier initial", parameter_name="prefix")
    assert issubclass(custom, ArabicInitialListFilter)
    assert issubclass(ArabicInitialListFilter, admin.SimpleListFilter)
    Book.objects.create(title="Sample", isbn="ISBN-1")
    Book.objects.create(title="Another", isbn="978-0")
    spec, request = bind_filter(custom, prefix="I")
    assert spec.title == "Identifier initial"
    assert spec.expected_parameters() == ["prefix"]
    assert filtered_titles(spec, request) == {"Sample"}
    default, _ = bind_filter(arabic_initial_filter("isbn"))
    assert default.title == "ISBN"  # Explicit field verbose_name, not the attribute name.
    assert default.expected_parameters() == ["isbn__initial"]


def test_missing_field_name_is_reported():
    class NoFieldFilter(ArabicInitialListFilter):
        pass

    with pytest.raises(ImproperlyConfigured, match="field_name"):
        bind_filter(NoFieldFilter)


def test_empty_queryset_has_no_choices_or_matches():
    spec, request = bind_filter(arabic_initial_filter("title"), title__initial="other")
    assert spec.lookup_choices == []
    assert not spec.has_output()
    assert filtered_titles(spec, request) == set()


def test_reverse_related_filter_returns_each_category_once():
    category = Category.objects.create(name="Travel")
    for title in ["Atlas", "Almanac"]:
        Book.objects.create(title=title, category=category)
    Category.objects.create(name="No books")
    model_admin = admin.ModelAdmin(Category, AdminSite())
    spec, request = bind_filter(
        arabic_initial_filter("book__title"), model_admin, book_title__initial="A"
    )
    assert list(spec.queryset(request, Category.objects.all())) == [category]


def test_lookup_discovery_is_one_distinct_initial_query(django_assert_num_queries):
    # Thing orders by name, which must not leak into the DISTINCT projection.
    Thing.objects.bulk_create([Thing(name=str(i), note="كتاب") for i in range(10)])
    model_admin = admin.ModelAdmin(Thing, AdminSite())
    with django_assert_num_queries(1) as queries:
        spec, _ = bind_filter(arabic_initial_filter("note"), model_admin)
        assert spec.lookup_choices == [("ك", isolate("ك"))]
    sql = queries.captured_queries[0]["sql"].upper()
    assert "SELECT DISTINCT" in sql
    # Both supported backends slice before returning the value to Python.
    assert "SUBSTR(" in sql or "SUBSTRING(" in sql
    for field in Thing._meta.concrete_fields:
        if field.name != "note":
            assert f'"{field.column.upper()}"' not in sql


def test_lookups_respect_model_admin_and_filtering_preserves_supplied_queryset():
    class PublishedAdmin(admin.ModelAdmin):
        def get_queryset(self, request):
            return super().get_queryset(request).filter(status="published")

    Book.objects.create(title="أبواب", status="published", price=10)
    Book.objects.create(title="إبرة", status="published", price=20)
    Book.objects.create(title="آفاق", status="draft", price=20)
    Book.objects.create(title="سر", status="draft", price=20)
    model_admin = PublishedAdmin(Book, AdminSite())
    spec, request = bind_filter(arabic_initial_filter("title"), model_admin, title__initial="ا")
    assert spec.lookup_choices == [("ا", isolate("ا"))]
    qs = model_admin.get_queryset(request).filter(price=20)
    assert filtered_titles(spec, request, qs) == {"إبرة"}


@pytest.mark.parametrize(
    "value,expected",
    [
        ("ا", {"Atlas"}),
        ("other", {"Uncategorized", "Empty category"}),
        ("not-a-bucket", {"Atlas", "Uncategorized", "Empty category"}),
        (None, {"Atlas", "Uncategorized", "Empty category"}),
    ],
)
def test_related_filter_on_changelist(admin_user, rf, value, expected):
    class CategoryInitial(ArabicInitialListFilter):
        field_name = "category__name"

    class CatalogAdmin(admin.ModelAdmin):
        list_filter = (CategoryInitial,)

    Book.objects.create(title="Atlas", category=Category.objects.create(name="أطالس"))
    Book.objects.create(title="Uncategorized", category=None)
    Book.objects.create(title="Empty category", category=Category.objects.create(name=""))
    param = "category_name__initial"
    request = rf.get("/", {param: value} if value is not None else {})
    request.user = admin_user
    changelist = CatalogAdmin(Book, AdminSite()).get_changelist_instance(request)
    assert {book.title for book in changelist.result_list} == expected
    (spec,) = changelist.filter_specs
    assert spec.expected_parameters() == [param]
    assert spec.title == Category._meta.get_field("name").verbose_name
    # The links Django actually emits must round-trip without relation traversal.
    all_link, *links = spec.choices(changelist)
    assert param not in parse_qs(urlsplit(all_link["query_string"]).query)
    assert [parse_qs(urlsplit(link["query_string"]).query) for link in links] == [
        {param: ["ا"]},
        {param: ["other"]},
    ]
