from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RTLAdminConfig(AppConfig):
    name = "django_rtl_admin"
    label = "rtl_admin"
    verbose_name = _("Bilingual / RTL admin")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from . import checks  # noqa: F401  (registers the system checks)
