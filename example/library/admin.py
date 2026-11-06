from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

from django_rtl_admin import BidiSafeAdminMixin, format_currency, format_number

from .models import Book, Chapter, Publisher

_default_admin_password_change = admin.site.password_change
_default_admin_password_change_done = admin.site.password_change_done
_default_admin_each_context = admin.site.each_context


def is_demo_user(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    demo_username = getattr(settings, "DEMO_USERNAME", "demo")
    return getattr(user, "username", None) == demo_username


def _guarded_password_change(request, extra_context=None):
    if is_demo_user(request.user):
        raise PermissionDenied("Password change is disabled for the shared demo account.")
    return _default_admin_password_change(request, extra_context=extra_context)


def _guarded_password_change_done(request, extra_context=None):
    if is_demo_user(request.user):
        raise PermissionDenied("Password change is disabled for the shared demo account.")
    return _default_admin_password_change_done(request, extra_context=extra_context)


def _each_context(request):
    context = _default_admin_each_context(request)
    context["is_demo_user"] = is_demo_user(request.user)
    return context


admin.site.password_change = _guarded_password_change
admin.site.password_change_done = _guarded_password_change_done
admin.site.each_context = _each_context


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1
    fields = ("number", "title_en", "title_ar", "starts_on_page")


@admin.register(Publisher)
class PublisherAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "city_ar", "website", "contact_email")
    search_fields = ("name_en", "name_ar", "city_en", "city_ar")
    fieldsets = (
        (None, {"fields": (("name_en", "name_ar"), ("city_en", "city_ar"))}),
        (_("Contact"), {"fields": ("website", "contact_email")}),
    )


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    """A stock ModelAdmin plus one mixin.

    ``BidiSafeAdminMixin`` isolates every changelist cell, so the ISBN, the
    edition string, the catalogue path and the date stop being reordered when
    the admin is shown in Arabic.
    """

    list_display = (
        "title_ar",
        "author_ar",
        "isbn",
        "edition",
        "catalogue_path",
        "published_on",
        "localised_price",
        "is_featured",
    )
    list_display_links = ("title_ar",)
    list_filter = ("status", "is_featured", "publisher", "published_on")
    search_fields = ("title_en", "title_ar", "author_en", "author_ar", "isbn")
    date_hierarchy = "published_on"
    ordering = ("-published_on",)
    inlines = [ChapterInline]
    autocomplete_fields = ("publisher",)
    readonly_fields = ("added_at",)
    fieldsets = (
        (None, {"fields": (("title_en", "title_ar"), ("author_en", "author_ar"))}),
        (
            _("Catalogue"),
            {
                "fields": (
                    "publisher",
                    "isbn",
                    "edition",
                    "catalogue_path",
                    ("page_count", "price"),
                ),
                "description": _(
                    "Identifiers stay left-to-right no matter which language "
                    "the admin is displayed in."
                ),
            },
        ),
        (
            _("Publication"),
            {"fields": ("published_on", "status", "is_featured", "added_at")},
        ),
        (_("Summary"), {"fields": ("summary_ar",), "classes": ("collapse",)}),
    )

    @admin.display(description=_("price"), ordering="price")
    def localised_price(self, obj):
        return format_currency(obj.price)

    @admin.display(description=_("pages"), ordering="page_count")
    def localised_pages(self, obj):
        return format_number(obj.page_count)
