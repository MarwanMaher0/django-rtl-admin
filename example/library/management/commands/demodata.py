"""Create the demo superuser and a handful of bilingual records."""

import datetime
import decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from library.models import Book, Chapter, Publisher

PUBLISHERS = [
    {
        "name_en": "Dar Al-Nahda",
        "name_ar": "دار النهضة",
        "city_en": "Cairo",
        "city_ar": "القاهرة",
        "website": "https://example.com/dar-al-nahda",
        "contact_email": "rights@example.com",
    },
    {
        "name_en": "Beirut House",
        "name_ar": "دار بيروت",
        "city_en": "Beirut",
        "city_ar": "بيروت",
        "website": "https://example.org/beirut-house",
        "contact_email": "contact@example.org",
    },
]

BOOKS = [
    {
        "title_ar": "مقدمة ابن خلدون",
        "title_en": "The Muqaddimah",
        "author_ar": "ابن خلدون",
        "author_en": "Ibn Khaldun",
        "isbn": "978-0-691-16628-5",
        "edition": "3.2.1",
        "catalogue_path": "/archive/ar/2024-03-05/muqaddimah.pdf",
        "page_count": 1104,
        "price": "349.90",
        "published_on": datetime.date(2024, 3, 5),
        "status": "published",
        "is_featured": True,
        "summary_ar": (
            "نسخة محققة رقم "
            "v3.2.1 من ملف ISBN 978-0-691-16628-5 "
            "بتاريخ 2024-03-05."
        ),
        "chapters": [
            ("العمران البشري", "Human civilisation", 1),
            ("العصبية", "Group feeling", 148),
            ("الدولة والملك", "Dynasty and kingship", 402),
        ],
    },
    {
        "title_ar": "ألف ليلة وليلة",
        "title_en": "One Thousand and One Nights",
        "author_ar": "مجهول",
        "author_en": "Anonymous",
        "isbn": "978-0-14-044289-8",
        "edition": "12.0",
        "catalogue_path": "/archive/ar/1998-11-30/nights-vol-1.epub",
        "page_count": 2880,
        "price": "512.00",
        "published_on": datetime.date(1998, 11, 30),
        "status": "published",
        "is_featured": True,
        "summary_ar": (
            "المجلد الأول "
            "متاح على "
            "https://example.com/nights?vol=1&fmt=epub"
        ),
        "chapters": [
            ("شهرزاد", "Shahrazad", 1),
            ("السندباد", "Sindbad", 621),
        ],
    },
    {
        "title_ar": "رسالة الغفران",
        "title_en": "The Epistle of Forgiveness",
        "author_ar": "أبو العلاء المعري",
        "author_en": "Al-Ma'arri",
        "isbn": "978-1-4798-0033-9",
        "edition": "2.0.0-rc.4",
        "catalogue_path": "/archive/ar/2013-07-19/ghufran.txt",
        "page_count": 448,
        "price": "199.50",
        "published_on": datetime.date(2013, 7, 19),
        "status": "review",
        "is_featured": False,
        "summary_ar": (
            "مراجعة داخلية "
            "من قبل editor@example.org "
            "قبل 2025-01-15."
        ),
        "chapters": [
            ("الجنة", "Paradise", 12),
            ("النار", "Hellfire", 210),
        ],
    },
    {
        "title_ar": "كليلة ودمنة",
        "title_en": "Kalila and Dimna",
        "author_ar": "ابن المقفع",
        "author_en": "Ibn al-Muqaffa",
        "isbn": "978-9-953-89012-3",
        "edition": "1.0.0",
        "catalogue_path": "/archive/ar/2007-02-28/kalila.pdf",
        "page_count": 336,
        "price": "129.00",
        "published_on": datetime.date(2007, 2, 28),
        "status": "draft",
        "is_featured": False,
        "summary_ar": (
            "مسودة رقم 1.0.0 "
            "بانتظار المراجعة."
        ),
        "chapters": [
            ("الأسد والثور", "The lion and the ox", 5),
        ],
    },
    {
        "title_ar": "طوق الحمامة",
        "title_en": "The Ring of the Dove",
        "author_ar": "ابن حزم",
        "author_en": "Ibn Hazm",
        "isbn": "978-0-86356-166-1",
        "edition": "4.1",
        "catalogue_path": "/archive/ar/2019-09-01/tawq.pdf",
        "page_count": 288,
        "price": "175.25",
        "published_on": datetime.date(2019, 9, 1),
        "status": "published",
        "is_featured": False,
        "summary_ar": (
            "طبعة 4.1 من النسخة "
            "الإنجليزية The Ring of the Dove."
        ),
        "chapters": [
            ("علامات الحب", "Signs of love", 22),
            ("الوصال", "Union", 140),
        ],
    },
]


class Command(BaseCommand):
    help = "Create the demo superuser and sample bilingual records."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="demo12345")
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument(
            "--read-only",
            "--readonly",
            dest="read_only",
            action="store_true",
            help="Create the demo user as a read-only staff account in a view-only group.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        if options.get("read_only"):
            from .reset_demo import configure_readonly_demo_user

            user, group = configure_readonly_demo_user(
                username=username,
                password=options["password"],
                email=options["email"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Configured read-only staff user {user.username!r} "
                    f"(password: {options['password']}, group: {group.name!r})"
                )
            )
        else:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": options["email"], "is_staff": True, "is_superuser": True},
            )
            user.is_staff = True
            user.is_superuser = True
            user.set_password(options["password"])
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} superuser {username!r} "
                    f"(password: {options['password']})"
                )
            )

        publishers = []
        for data in PUBLISHERS:
            publisher, _created = Publisher.objects.update_or_create(
                name_en=data["name_en"], defaults=data
            )
            publishers.append(publisher)

        for index, raw_data in enumerate(BOOKS):
            data = dict(raw_data)
            chapters = list(data.pop("chapters", []))
            data["price"] = decimal.Decimal(data["price"])
            book, _created = Book.objects.update_or_create(
                isbn=data["isbn"],
                defaults=dict(data, publisher=publishers[index % len(publishers)]),
            )
            book.chapters.all().delete()
            for number, (title_ar, title_en, page) in enumerate(chapters, start=1):
                Chapter.objects.create(
                    book=book,
                    number=number,
                    title_ar=title_ar,
                    title_en=title_en,
                    starts_on_page=page,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{Publisher.objects.count()} publishers, {Book.objects.count()} books, "
                f"{Chapter.objects.count()} chapters."
            )
        )
