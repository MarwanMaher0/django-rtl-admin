from django import forms
from django.contrib import admin, messages

from django_rtl_admin import BidiSafeAdminMixin, PhoneNumberField, export_as_csv

from .models import Article, ArticleSection, Book, Category, Chapter, Contact, Review, Thing


class BidiThingAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("name", "name_ar", "reference", "quantity", "is_active", "upper_name")
    list_filter = ("is_active",)
    search_fields = ("name", "reference")
    readonly_fields = ("note",)

    @admin.display(description="Upper", ordering="name")
    def upper_name(self, obj):
        return obj.name.upper()


class PlainThingAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "is_active")


admin.site.register(Thing, BidiThingAdmin)


# -- Admins for the browser tests in tests/e2e --------------------------------


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    raw_id_fields = ("book",)


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1


class ReviewInline(admin.StackedInline):
    model = Review
    extra = 1


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    bidi_arabic_ordering = ("title",)
    list_display = ("title", "isbn", "category", "status", "published_on", "price")
    list_filter = ("status", "category", "published_on")
    search_fields = ("title", "isbn")
    date_hierarchy = "published_on"
    list_per_page = 5
    autocomplete_fields = ("category",)
    actions = ("mark_published", export_as_csv)
    inlines = (ChapterInline, ReviewInline)
    readonly_fields = ("archive_note",)
    fieldsets = (
        (
            None,
            {
                "fields": ("title", "isbn", "category", "status", "archive_note"),
                "description": "Bibliographic details, exactly as on the title page.",
            },
        ),
        ("Publication", {"fields": (("published_on", "launch_time"), "available_from", "price")}),
        (
            "Notes",
            {
                "classes": ("collapse",),
                "fields": ("summary",),
                "description": "Optional catalogue copy.",
            },
        ),
    )

    @admin.action(description="Mark selected books as published")
    def mark_published(self, request, queryset):
        updated = queryset.update(status="published")
        self.message_user(request, f"Marked {updated} book(s) as published.", messages.SUCCESS)


class InputChapterInline(BidiSafeAdminMixin, ChapterInline):
    pass


class InputBookAdmin(BookAdmin):
    """Used in the input POST tests' URLconf, not the browser suite's admin site."""

    inlines = (InputChapterInline, ReviewInline)
    list_editable = ("price",)


class LocalizedPriceForm(forms.ModelForm):
    class Meta:
        localized_fields = ("price",)


class LocalizedInputBookAdmin(InputBookAdmin):
    form = LocalizedPriceForm


class ArticleSectionInline(BidiSafeAdminMixin, admin.TabularInline):
    model = ArticleSection
    prepopulated_fields = {"slug": ("title",)}
    extra = 1


@admin.register(Article)
class ArticleAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    prepopulated_fields = {
        "slug": ("title", "subtitle"),
        "unicode_slug": ("title",),
        "stock_slug": ("title",),
    }
    inlines = (ArticleSectionInline,)


class ContactAdminForm(forms.ModelForm):
    phone = PhoneNumberField()

    class Meta:
        model = Contact
        fields = ("name", "phone")


@admin.register(Contact)
class ContactAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    form = ContactAdminForm
    list_display = ("name", "phone")
