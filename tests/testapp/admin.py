from django.contrib import admin, messages

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book, Category, Chapter, Review, Thing


class BidiThingAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("name", "name_ar", "reference", "quantity", "is_active", "upper_name")
    list_filter = ("is_active",)
    search_fields = ("name", "reference")

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


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1


class ReviewInline(admin.StackedInline):
    model = Review
    extra = 1


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "category", "status", "published_on", "price")
    list_filter = ("status", "category", "published_on")
    search_fields = ("title", "isbn")
    date_hierarchy = "published_on"
    list_per_page = 5
    autocomplete_fields = ("category",)
    actions = ("mark_published",)
    inlines = (ChapterInline, ReviewInline)
    fieldsets = (
        (
            None,
            {
                "fields": ("title", "isbn", "category", "status"),
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
