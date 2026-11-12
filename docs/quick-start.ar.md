---
title: البدء السريع | django-rtl-admin
description: اضبط لوحة إدارة Django ثنائية اللغة بترتيب التطبيقات وLocaleMiddleware ومسار اللغة والعزل الاختياري للنصوص والتنسيق الصريح حسب اللغة.
---

# البدء السريع { #quick-start }

ابدأ بمشروع Django قائم تعمل فيه لوحة الإدارة الافتراضية، ثم اتبع
[دليل التثبيت](installation.md). تُعدّل المقاطع التالية إعدادات ذلك المشروع؛
احتفظ بإعدادات قاعدة البيانات والأمان والقوالب وسائر إعدادات التطبيق.

تبقى صفحة واجهة Python البرمجية وسجل التغييرات باللغة الإنجليزية.

## 1. تفعيل اختيار لغة الطلب { #1-enable-request-language-selection }

أبقِ `django_rtl_admin` قبل `django.contrib.admin` في `INSTALLED_APPS`. في
`settings.py`، فعّل دعم التدويل واختر اللغات التي تريد إتاحتها:

```python
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("ar", "Arabic"),
    ("ar-eg", "Arabic (Egypt)"),
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

ضع `LocaleMiddleware` بعد `SessionMiddleware` وقبل `CommonMiddleware`.
احتفظ بمعالجات سياق القوالب القياسية الخاصة بالطلب والمصادقة والرسائل، كما يوفّرها
قالب مشروع Django. يستخدم مبدّل اللغة الطلب للحفاظ على المسار الحالي في لوحة الإدارة
وسلسلة معاملات الاستعلام.

## 2. إضافة نقطة نهاية اللغة في Django { #language-endpoint }

في ملف `urls.py` الرئيسي لمشروعك:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
```

يرسل مبدّل اللغة طلب `POST` محميًا من CSRF إلى عنوان `set_language`. يضبط Django
ملف تعريف الارتباط الخاص باللغة، ويطبّق `LocaleMiddleware` هذا الاختيار على الطلبات
اللاحقة. إذا كنت تستخدم `i18n_patterns`، فأبقِ نقطة النهاية `i18n/` خارج مجموعة
المسارات التي تُضاف إليها بادئة اللغة.

## 3. التحقق من الواجهة { #3-check-the-interface }

```sh
python manage.py check
python manage.py runserver
```

افتح `/admin/`. اختر العربية من مبدّل اللغة في ترويسة الصفحة؛ ويتوفر مبدّل أيضًا
في صفحة تسجيل الدخول. يتبع اتجاه لوحة الإدارة والمسافات المبنية على الخصائص المنطقية
اللغة النشطة. اختر الإنجليزية مجددًا للتحقق من التخطيط من اليسار إلى اليمين (LTR).

لا يلزم تعريف قاموس `RTL_ADMIN`. على سبيل المثال، لعرض أسماء اللغات باللغتين
واستخدام الجنيه المصري عند عدم تحديد عملة:

```python
RTL_ADMIN = {
    "CURRENCY": "EGP",
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

## 4. حماية القيم في قائمة السجلات { #4-protect-changelist-values }

لا تعيد ورقة الأنماط كتابة قيم نماذجك. فعّل عزل الخلايا صراحةً في كل فئة إدارة
تعرض نصوصًا مختلطة الاتجاه:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

يفترض هذا المثال أن نموذج `Book` لديك يحتوي على الحقلين `title` و`isbn`. يجب أن
يسبق المزيج (mixin) الفئة `ModelAdmin` في قائمة الوراثة. يعزل المزيج هنا رقم ISBN
وحده ويفرض عرضه من اليسار إلى اليمين. احذف كلتا الخاصيتين لعزل جميع الأعمدة المؤهلة
باستخدام الاتجاه الافتراضي المحدد في الإعدادات. راجع
[BidiSafeAdminMixin](admin-mixin.md) لمعرفة الاستثناءات وخيارات تعطيل العزل.

## 5. تنسيق المخرجات المخصصة { #5-format-custom-output }

في قالب مخصص، حمّل `rtl_admin`:

```django
{% load rtl_admin %}
<p>{{ book.isbn|bidi_isolate:"ltr" }}</p>
<p>{{ book.title|bidi_runs }}</p>
<p>{{ amount|l10n_number:2 }}</p>
<p>{{ amount|l10n_currency:"EGP" }}</p>
```

يجب أن تكون قيمة `amount` عددية في أمثلة التنسيق هذه. يتطلب استخدام هذه المرشحات
تفعيلًا صريحًا؛ فتثبيت الحزمة لا يجعل كل حقل في لوحة الإدارة يتكيّف تلقائيًا مع
الإعدادات المحلية. يستخدم رمز اللغة `ar` وحده عادةً الأرقام اللاتينية، بينما يستخدم
`ar-eg` الأرقام العربية الهندية. راجع [الإعدادات](configuration.md) لفرض نظام
ترقيم، و[وسوم القوالب ومرشحاتها](template-tags.md) للاطلاع على المكتبة كاملةً.
