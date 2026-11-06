import library.admin  # noqa: F401
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as serve_static
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="root"),
    path("healthz/", healthz, name="healthz"),
    path("healthz", healthz),
    path(
        "admin/password_change/",
        admin.site.admin_view(admin.site.password_change),
    ),
    path(
        "admin/password_change/done/",
        admin.site.admin_view(admin.site.password_change_done),
    ),
    path("admin/", admin.site.urls),
    # The language switcher posts here.
    path("i18n/", include("django.conf.urls.i18n")),
]

if getattr(settings, "LOCAL_DEV", False):
    urlpatterns.append(
        re_path(
            r"^static/(?P<path>.*)$",
            serve_static,
            {"insecure": True},
        )
    )
