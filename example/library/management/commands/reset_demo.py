"""Flush the database, reload demo data, and make the 'demo' user read-only."""

from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

DEFAULT_GROUP_NAME = "Demo Read-Only"
DEFAULT_DEMO_MODEL_NAMES = (
    ("library", "Publisher"),
    ("library", "Book"),
    ("library", "Chapter"),
)


def configure_readonly_demo_user(
    *,
    username: str = "demo",
    password: str = "demo12345",
    email: str = "demo@example.com",
    group_name: str = DEFAULT_GROUP_NAME,
    models: tuple[type, ...] | None = None,
):
    """Ensure ``username`` is a staff, non-superuser belonging to a view-only group
    whose permissions are limited strictly to viewing the demo models.
    """
    if models is None:
        models = tuple(
            apps.get_model(app_label, model_name)
            for app_label, model_name in DEFAULT_DEMO_MODEL_NAMES
        )

    app_labels = {model._meta.app_label for model in models}
    for app_config in apps.get_app_configs():
        if app_config.label in app_labels:
            create_permissions(app_config, verbosity=0)

    content_types = list(ContentType.objects.get_for_models(*models).values())
    view_permissions = list(
        Permission.objects.filter(
            content_type__in=content_types,
            codename__startswith="view_",
        )
    )
    group, _ = Group.objects.get_or_create(name=group_name)
    group.permissions.set(view_permissions)

    User = get_user_model()
    user, _created = User.objects.get_or_create(
        username=username,
        defaults={"email": email},
    )
    user.email = email
    user.is_active = True
    user.is_staff = True
    user.is_superuser = False
    user.set_password(password)
    user.save()
    user.user_permissions.clear()
    user.groups.set([group])
    return user, group


class Command(BaseCommand):
    help = (
        "Flush the database, reload sample bilingual records, and configure "
        "the 'demo' account as a read-only staff user."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="demo12345")
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--group", default=DEFAULT_GROUP_NAME)
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Skip flushing the database before reloading demo records.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        group_name = options["group"]

        call_command("migrate", "--no-input", verbosity=0)
        if not options["no_flush"]:
            call_command("flush", "--no-input", verbosity=0)

        with transaction.atomic():
            call_command(
                "demodata",
                username=username,
                password=password,
                email=email,
                read_only=True,
                stdout=self.stdout,
            )
            user, group = configure_readonly_demo_user(
                username=username,
                password=password,
                email=email,
                group_name=group_name,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Configured read-only staff user {user.username!r} in group "
                f"{group.name!r} with {group.permissions.count()} view permissions."
            )
        )
