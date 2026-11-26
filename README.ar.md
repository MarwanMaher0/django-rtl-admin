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
