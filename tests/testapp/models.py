from django.db import models


class Thing(models.Model):
    name = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=60, blank=True)
    note = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    published_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "testapp"
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def slug(self):
        return self.name.lower().replace(" ", "-")


# -- Models for the browser tests in tests/e2e --------------------------------
#
# Between them they put every stock-admin widget on screen: a filters sidebar,
# an actions bar and pagination on the changelist; fieldsets, a collapsible
# section, help text and validation errors on the change form; tabular and
# stacked inlines; date, time and split date/time widgets; and an autocomplete.


class Category(models.Model):
    name = models.CharField(max_length=100)
    is_featured = models.BooleanField(default=False)

    class Meta:
        app_label = "testapp"
        ordering = ("name",)
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Book(models.Model):
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published")]

    title = models.CharField(max_length=200, help_text="The title as printed on the cover.")
    isbn = models.CharField(
        "ISBN", max_length=20, help_text="ISBN-13, for example 978-3-16-148410-0."
    )
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    published_on = models.DateField(null=True, blank=True)
    available_from = models.DateTimeField(null=True, blank=True)
    launch_time = models.TimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    summary = models.TextField(blank=True, help_text="Shown on the catalogue page.")

    class Meta:
        app_label = "testapp"
        ordering = ("title",)

    def __str__(self):
        return self.title


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)

    class Meta:
        app_label = "testapp"
        ordering = ("number",)

    def __str__(self):
        return self.title


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    reviewer = models.CharField(max_length=200)
    body = models.TextField(help_text="Plain text; no markup.")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.reviewer
