"""A deliberately bilingual data model.

Every record carries an English and an Arabic title, plus the kinds of value
that the bidi algorithm loves to scramble inside Arabic prose: an ISBN, a
version-like edition string, an email address, a URL and a file path.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Publisher(models.Model):
    name_en = models.CharField(_("name (English)"), max_length=120)
    name_ar = models.CharField(_("name (Arabic)"), max_length=120)
    city_en = models.CharField(_("city (English)"), max_length=80, blank=True)
    city_ar = models.CharField(_("city (Arabic)"), max_length=80, blank=True)
    website = models.URLField(_("website"), blank=True)
    contact_email = models.EmailField(_("contact email"), blank=True)

    class Meta:
        verbose_name = _("publisher")
        verbose_name_plural = _("publishers")
        ordering = ("name_en",)

    def __str__(self):
        return self.name_en


class Book(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        REVIEW = "review", _("In review")
        PUBLISHED = "published", _("Published")

    title_en = models.CharField(_("title (English)"), max_length=200)
    title_ar = models.CharField(_("title (Arabic)"), max_length=200)
    author_en = models.CharField(_("author (English)"), max_length=120)
    author_ar = models.CharField(_("author (Arabic)"), max_length=120)
    summary_ar = models.TextField(_("summary (Arabic)"), blank=True)
    publisher = models.ForeignKey(
        Publisher,
        verbose_name=_("publisher"),
        on_delete=models.CASCADE,
        related_name="books",
    )
    isbn = models.CharField(_("ISBN"), max_length=20)
    edition = models.CharField(
        _("edition"),
        max_length=20,
        default="1.0.0",
        help_text=_("Semantic version of this printing, for example 2.0.0-rc.4."),
    )
    catalogue_path = models.CharField(
        _("catalogue path"),
        max_length=200,
        blank=True,
        help_text=_(
            "Absolute path inside the archive, for example /archive/ar/2024-03-05/file.pdf."
        ),
    )
    archive_note = models.CharField(
        _("archive note"),
        max_length=250,
        blank=True,
        help_text=_("Read-only provenance note mixing Arabic prose with an archive path and date."),
    )
    page_count = models.PositiveIntegerField(_("pages"), default=0)
    price = models.DecimalField(_("price"), max_digits=9, decimal_places=2, default=0)
    published_on = models.DateField(_("published on"))
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    is_featured = models.BooleanField(_("featured"), default=False)
    added_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("book")
        verbose_name_plural = _("books")
        ordering = ("-published_on",)

    def __str__(self):
        return self.title_en


class Chapter(models.Model):
    book = models.ForeignKey(
        Book, verbose_name=_("book"), on_delete=models.CASCADE, related_name="chapters"
    )
    number = models.PositiveIntegerField(_("number"))
    title_en = models.CharField(_("title (English)"), max_length=200)
    title_ar = models.CharField(_("title (Arabic)"), max_length=200)
    starts_on_page = models.PositiveIntegerField(_("starts on page"), default=1)

    class Meta:
        verbose_name = _("chapter")
        verbose_name_plural = _("chapters")
        ordering = ("number",)

    def __str__(self):
        return f"{self.number}. {self.title_en}"
