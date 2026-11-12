---
title: فحوصات النظام | django-rtl-admin
description: شخّص rtl_admin.E001 وW001 إلى W006 لخيارات الإعدادات وأنواعها غير الصالحة، وترتيب التطبيقات، والمفاتيح غير المعروفة، وغياب نقطة نهاية set_language، وإعداد LocaleMiddleware، ولغات RTL الغائبة عن LANGUAGES_BIDI.
---

# فحوصات النظام { #system-checks }

يسجّل التطبيق ست دوال فحص في Django يمكنها إصدار معرّف خطأ واحد وستة معرّفات
تحذير. شغّلها ضمن الفحوصات المعتادة لمشروعك:

```sh
python manage.py check
```

يمثّل E001 كائن `Error` في Django؛ وتمثّل W001 إلى W006 كائنات `Warning` في Django.
بادئتها الدقيقة هي `rtl_admin`، لا `django_rtl_admin`. يحدث التسجيل عندما تستورد
`django_rtl_admin.apps.RTLAdminConfig.ready()` وحدة الفحوصات.

تقرأ الفحوصات التي تفحص الإعدادات قيمها الخام بدلًا من دالة الوصول إلى الإعدادات
أثناء التشغيل، لذا تُبلَّغ الإعدادات غير الصالحة دون أن تثير هذه الفحوصات
`ImproperlyConfigured`. يظل التحقق أثناء التشغيل قائمًا.

| المعرّف | الشرط | الإصلاح الأساسي |
| --- | --- | --- |
| `rtl_admin.E001` | قيمة غير مدعومة لإعداد ذي خيارات محددة. | استخدم أحد الخيارات المقبولة للإعداد الذي أُبلغ عنه. |
| `rtl_admin.W001` | تطبيق لوحة إدارة RTL مُدرج بعد تطبيق الإدارة المرفق مع Django. | ضع `django_rtl_admin` قبل `django.contrib.admin`. |
| `rtl_admin.W002` | يحتوي `RTL_ADMIN` على مفاتيح غير مدعومة. | صحّح المفاتيح التي أُبلغ عنها أو احذفها. |
| `rtl_admin.W003` | المبدّل مفعّل ولا يمكن توليد عنوان `set_language`. | أضف مسار نقطة نهاية اللغة في Django أو عطّل المبدّل. |
| `rtl_admin.W004` | المبدّل مفعّل والمسار الدقيق لـ`LocaleMiddleware` غير موجود. | أضف البرمجية الوسيطة أو عطّل المبدّل. |
| `rtl_admin.W005` | ليس `RTL_ADMIN` كائن ربط ولا `None`، أو نوع أحد الخيارات المفحوصة غير صالح. | استخدم كائن ربط أو `None` وأنواع الخيارات الموثَّقة. |
| `rtl_admin.W006` | أحد الرموز في `EXTRA_RTL_LANGUAGES` غير موجود في `settings.LANGUAGES_BIDI`. | أضف الرمز إلى `LANGUAGES_BIDI` أو احذفه من `EXTRA_RTL_LANGUAGES`. |

## `rtl_admin.E001`: خيارات إعدادات غير صالحة { #rtl_admine001-invalid-setting-choices }

يصدر `check_settings_values` خطأ E001 مستقلًا لكل خيار غير صالح في هذا الجدول:

| الإعداد | القيم المقبولة |
| --- | --- |
| `ISOLATION_DIRECTION` | `"auto"`, `"ltr"`, `"rtl"` |
| `NUMERALS` | `"auto"`, `"latn"`, `"arab"`, `"arabext"` |
| `LANGUAGE_SWITCHER_LABELS` | `"native"`, `"translated"`, `"both"` |

صحّح القيمة التي أُبلغ عنها أو احذف الخيار لاستخدام قيمته الافتراضية. يُبلّغ
الفحص الخيارات غير الصالحة قبل الوصول إليها أثناء التشغيل؛ ويظل الوصول إلى خيار
غير صالح أثناء التشغيل يثير `ImproperlyConfigured`.

## `rtl_admin.W001`: ترتيب التطبيقات { #rtl_adminw001-app-order }

يستخدم الفحص `django.apps.apps.get_app_configs()` ويقرأ `name` لكل إعداد تطبيق
بحسب ترتيب السجل. إذا وُجد كل من `django_rtl_admin` و`django.contrib.admin`،
فيجب أن يظهر الأول قبله. إذا غاب أحدهما، فلا يصدر هذا الفحص شيئًا.

أدرج التطبيق قبل تطبيق الإدارة المرفق مع Django في قائمة تطبيقاتك الحالية،
مع الاحتفاظ بتطبيقات المشروع الأخرى واعتمادياته. يوضح هذا المقطع الترتيب:

```python
INSTALLED_APPS = [
    "django_rtl_admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
```

يتبع البحث عن قوالب التطبيقات هذا الترتيب، لتتمكن الحزمة من تقديم قالب يحلّ محل
`admin/base_site.html`. يُتعرَّف على كل من المسارات المعتادة مثل
`django_rtl_admin.apps.RTLAdminConfig` والفئات الفرعية المخصصة مثل
`myproject.apps.MyAdminConfig` من خلال `name` المسجَّل لها
(مثل `django.contrib.admin`)، لا من خلال مسار استيرادها.

لا تثبت نتيجة W001 الخالية من التحذيرات أن القالب المستخدم فعليًا يأتي من الحزمة:
قد تظل قوالب مستوى المشروع ومحمّلات القوالب المخصصة ذات أولوية. إذا كنت تحتفظ بقالب
بديل، فليَرث `django_rtl_admin/base_site.html` كما هو موضح في
[التثبيت](installation.md).

## `rtl_admin.W002`: إعدادات غير معروفة { #rtl_adminw002-unknown-settings }

يقارن الفحص مفاتيح `RTL_ADMIN` بالقيم الافتراضية المدعومة. يسرد تحذير واحد جميع
المفاتيح غير المعروفة بترتيب مفروز، ويسرد تلميحه المفاتيح المدعومة.
تُتجاهل المفاتيح غير المعروفة، لذا لا يعطّل الخطأ الإملائي ميزةً ولا يضبط إعداداتها.

على سبيل المثال، استخدم `ENABLE_CSS`، لا `ENABEL_CSS`:

```python
RTL_ADMIN = {
    "ENABLE_CSS": False,
}
```

راجع [الإعدادات](configuration.md) للاطلاع على الإعدادات المدعومة الثلاثة عشر
جميعها. يفحص W002 أسماء المفاتيح فقط؛ ويُبلّغ E001 الخيارات غير الصالحة،
ويُبلّغ W005 مشكلات الأنواع المذكورة أدناه.

## `rtl_admin.W003`: غياب نقطة نهاية اللغة { #rtl_adminw003-missing-language-endpoint }

عندما تكون `LANGUAGE_SWITCHER` ذات قيمة تُقيَّم منطقيًا إلى صحيح، يستدعي الفحص
`reverse("set_language")`. ينتج W003 عن أي استثناء عادي من ذلك الاستدعاء،
بما في ذلك غياب مسار أو وجود خطأ آخر في URLconf. يجب أن يكون الاسم متاحًا دون نطاق أسماء.

أضف نقطة نهاية اللغة في Django إلى URLconf الرئيسي إلى جانب مساراتك الأخرى:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
```

إذا كان المسار موجودًا بالفعل، فابحث عن خطأ URLconf أو توليد العنوان الكامن وراءه.
إذا لم تكن تتيح تبديل اللغة، فاضبط `RTL_ADMIN["LANGUAGE_SWITCHER"] = False`.

يخفي وسم تضمين المبدّل النموذج عند `NoReverseMatch` فقط. يلتقط الفحص استثناءات
أكثر، لذا لا يُخفى أثناء العرض كل خطأ في URLconf يسبب W003.
لا يثبت مجرد توفير مسار باسم معيّن أن دالة العرض البديلة المخصصة تنفّذ سلوك
ملف تعريف الارتباط الخاص باللغة في Django.

## `rtl_admin.W004`: غياب البرمجية الوسيطة للإعدادات المحلية { #rtl_adminw004-missing-locale-middleware }

عندما تكون `LANGUAGE_SWITCHER` ذات قيمة تُقيَّم منطقيًا إلى صحيح، يجب أن تكون
السلسلة النصية الدقيقة `django.middleware.locale.LocaleMiddleware` موجودةً في
`MIDDLEWARE`. وإلا يحذّر الفحص من أن اللغة المختارة لن تبقى ساريةً.

أضفها بعد `SessionMiddleware` وقبل `CommonMiddleware`، مع الاحتفاظ ببقية
البرمجيات الوسيطة لديك. هذا ترتيب قياسي:

```python
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

يتحقق الفحص من الوجود، لا من الترتيب. لا يُتعرَّف على فئة فرعية مخصصة متوافقة
تحت مسار استيراد مختلف. لا يخفي غياب البرمجية الوسيطة نموذج المبدّل؛ فهي متطلب
مستقل أثناء التشغيل. اتبع [البدء السريع](quick-start.md) لإعداد اختيار اللغة كاملًا.

## `rtl_admin.W005`: أنواع إعدادات غير صالحة { #rtl_adminw005-invalid-setting-types }

يصدر `check_settings_types` تحذير W005 مستقلًا لكل نوع غير صالح يكتشفه:

| الإعداد | متطلب النوع |
| --- | --- |
| `RTL_ADMIN` | كائن من نوع `collections.abc.Mapping` (مثل `dict` أو `types.MappingProxyType`)، أو `None` لاستخدام القيم الافتراضية. |
| `EXTRA_RTL_LANGUAGES` | يجب ألا يكون سلسلة نصية مفردة؛ استخدم مجموعةً من رموز اللغات بدلًا منها. |
| `FONT_STACK` | `None`، أو سلسلة نصية، أو تسلسل من السلاسل النصية مثل قائمة أو صف. |
| `ENABLE_CSS`, `ISOLATE_CHANGELIST`, `ISOLATE_TABLE_CELLS`, `PLAINTEXT_FORM_FIELDS`, `USE_BABEL`, `LANGUAGE_SWITCHER` | قيمة `bool` حقيقية (`True` أو `False`)، لا بديلًا يُقيَّم منطقيًا إلى صحيح أو خطأ. |

على سبيل المثال، استخدم `False`، لا `"false"` أو `0`، لمفتاح تفعيل.
يؤدي حذف `RTL_ADMIN` أو ضبطه على `None` إلى استخدام القيم الافتراضية.
تُفحص قيم كائن الربط كالمعتاد، بما في ذلك المفاتيح غير المعروفة والخيارات غير
الصالحة وإعداد مبدّل اللغة. يستهدف تشخيص `EXTRA_RTL_LANGUAGES` السلاسل النصية
المفردة، لا صحة رموز اللغات. لا تمثّل فحوصات الأنواع هذه تحققًا شاملًا من جميع
محتويات الإعدادات.

## `rtl_admin.W006`: لغة RTL إضافية غائبة عن `LANGUAGES_BIDI` { #rtl_adminw006-extra-rtl-language-missing-from-languages_bidi }

يصدر `check_extra_rtl_languages_bidi` تحذير W006 عندما يغيب رمز من
`RTL_ADMIN["EXTRA_RTL_LANGUAGES"]` عن `settings.LANGUAGES_BIDI` في Django.
يضبط Django قيمة `<html dir>` انطلاقًا من ذلك الإعداد، باستخدام الرمز الأساسي
للغة كما تفعل `get_language_bidi()`. دون المدخل المقابل، يعرض Django مستندًا
باتجاه LTR بينما تضيف الحزمة `rtl-admin--rtl` إلى عنصر body، فلا يُحمَّل
`admin/css/rtl.css` المرفق مع Django ويختلف الاتجاهان.

يقارن الفحص الرموز الأساسية بالطريقة نفسها: يكفي وجود `"ps"` في `LANGUAGES_BIDI`
لرمز إضافي هو `ps-AF`. يتجاوز الفحص القيمة التي تكون سلسلة نصية مفردة، إذ يُبلّغ
عنها W005 بالفعل، ولا يفعل شيئًا عند حذف `EXTRA_RTL_LANGUAGES` أو تركه فارغًا.
تقرأ دوال الاتجاه المساعدة في الحزمة أيضًا `LANGUAGES_BIDI` — وتتجاهل علامة
`bidi` الخاصة بكل لغة في `LANG_INFO` — لذا يظل الرمز المعلَّم بأنه ثنائي الاتجاه
هناك فقط بحاجة إلى هذا المدخل. وحّد الإعدادين عند اعتماد لغة جديدة:

```python
from django.conf.global_settings import LANGUAGES_BIDI

LANGUAGES = [..., ("ps", "Pashto")]
LANGUAGES_BIDI = [*LANGUAGES_BIDI, "ps"]
RTL_ADMIN = {"EXTRA_RTL_LANGUAGES": ("ps",)}
```

تكفي إضافة الرمز إلى `LANGUAGES_BIDI` وحده لدوال الاتجاه المساعدة في الحزمة.
يُستخدم `EXTRA_RTL_LANGUAGES` للإعدادات المحلية التي لا يعرفها Django بعد؛
أدرج كل رمز أيضًا في `LANGUAGES_BIDI` عندما ينبغي أن يكون اتجاه المستند RTL كذلك.
هذا الاقتران هو الحالة المعتادة، ويفرضه W006.

## تعطيل فحوصات المبدّل { #disabling-the-switcher-checks }

إذا لم تكن تريد المبدّل، فعطّل ميزته بدلًا من الاكتفاء بإخفاء التحذيرات:

```python
RTL_ADMIN = {
    "LANGUAGE_SWITCHER": False,
}
```

يتجاوز هذا كلًا من W003 وW004 ويمنع ظهور النموذج وسكربته. تظل E001 وW001 وW002
وW005 وW006 تعمل. يمكن أن يحدث W003 وW004 معًا، ويظلان يعملان حتى عند ضبط لغة
واحدة فقط، رغم أن النموذج يختفي في تلك الحالة.

## ما لا تضمنه نتيجة خالية من المشكلات { #what-a-clean-result-does-not-guarantee }

لا تتحقق الفحوصات من `USE_I18N`، أو سياق القالب الخاص بالطلب وCSRF، أو صحة قائمة
اللغات المخصصة، أو تقديم الملفات الثابتة، أو توفر Babel، أو خصائص المزيج، أو
وراثة القوالب الفعلية. كما لا تتحقق من ترتيب البرمجيات الوسيطة.
استخدم [وسوم القوالب ومرشحاتها](template-tags.md) لمعرفة متطلبات العرض،
و[مزيج لوحة الإدارة](admin-mixin.md) لمعرفة عزل الأعمدة وخيارات تعطيله.
