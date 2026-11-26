# django-rtl-admin

[English README](README.md) · [التوثيق بالعربية](https://marwanmaher0.github.io/django-rtl-admin/ar/)

حزمة تجعل لوحة إدارة Django ثنائية اللغة: تخطيط من اليمين إلى اليسار، وعزل
النصوص المختلطة الاتجاه، وتنسيق الأرقام والتواريخ، ومبدّل للغة.

```sh
pip install django-rtl-admin
```

أضف `django_rtl_admin` قبل `django.contrib.admin` في `INSTALLED_APPS`، ثم اتبع
[دليل البدء السريع](https://marwanmaher0.github.io/django-rtl-admin/ar/quick-start/).

## توليد معرّف الرابط من عنوان عربي أو فارسي

لإصلاح معرّفات الروابط الفارغة في نموذج الإضافة، استخدم `BidiSafeAdminMixin`
قبل `admin.ModelAdmin` واضبط `prepopulated_fields = {"slug": ("title",)}`.
يولّد المزيج المعاينة عند الكتابة ويملأ `SlugField` الفارغ قبل التحقق من النموذج
حتى عند تعطيل JavaScript. يعمل أيضًا مع الصفوف الجديدة في النماذج المضمّنة
التي تستخدم المزيج. لا يغيّر معرّفًا غير فارغ ولا يضمن تفرّد المعرّفات.

```python
from django_rtl_admin import arabic_slugify

assert arabic_slugify("مُقَدِّمَة ١٢") == "mqdmh-12"
assert arabic_slugify("مُقَدِّمَة ١٢", allow_unicode=True) == "مقدمة-12"
assert arabic_slugify("پژوهش ۱۴۰۳") == "pzhwhsh-1403"
```

الميزة مفعّلة افتراضيًا. لتعطيلها على مستوى المشروع، استخدم
`RTL_ADMIN["TRANSLITERATE_SLUGS"] = False`، أو اضبط
`bidi_transliterate_slugs = False` في فئة إدارة أو نموذج مضمّن بعينه.
انظر [مرجع المزيج](https://marwanmaher0.github.io/django-rtl-admin/ar/admin-mixin/#arabic-slug-prepopulation)
و[جدول النقحرة وقواعد تحديد الطول](https://marwanmaher0.github.io/django-rtl-admin/ar/api/#arabic-slugify).

## التواريخ الهجرية بتقويم أم القرى

تحتاج مواقع الإدارة في السعودية والخليج إلى تقويم أم القرى، وهو تقويم لا توفّره
Babel. تتضمن الحزمة جدولًا مضمّنًا للسنوات 1343–1500 هـ (من 1924-08-01 إلى
2077-11-16 م)، لذلك لا يحتاج التحويل إلى أي اعتماد إضافي وقت التشغيل:

```python
from datetime import date

from django_rtl_admin import format_hijri_date, from_hijri, to_hijri

hijri = to_hijri(date(2024, 3, 11))
assert (hijri.year, hijri.month, hijri.day) == (1445, 9, 1)
assert from_hijri(1445, 9, 1) == date(2024, 3, 11)
assert format_hijri_date(date(2024, 3, 11), language="ar-eg") == "١ رمضان ١٤٤٥ هـ"
assert format_hijri_date(date(2024, 3, 11), language="en", suffix=False) == "1 Ramadan 1445"
```

تعيد `to_hijri()` فئة `HijriDate` المجمّدة (`year` و`month` و`day`
و`month_length`)، وتقبل التواريخ المجرّدة أو قيم `datetime`؛ وتُحوّل القيم
الواعية بالمنطقة الزمنية إلى المنطقة النشطة عند ضبط `USE_TZ=True`. وترفع
التواريخ خارج النطاق `ValueError`. وتعرض `format_hijri_date()` أسماء الأشهر
العربية الكاملة لـ`ar`، والفارسية لـ`fa`، والأردية لـ`ur`، وبالنقحرة
الإنجليزية لغيرها. وتقبل `long` أو `medium` أو `short`، وتتبع الأرقام
`NUMERALS` ونظام ترقيم اللغة، وتضيف لاحقة العصر الهجري ما لم تُضبط
`suffix=False`. واستخدم في القوالب `{{ book.published_on|hijri_date }}` أو
`{{ book.published_on|hijri_date:"short" }}`.
