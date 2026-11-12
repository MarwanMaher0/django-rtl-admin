---
title: BidiSafeAdminMixin | django-rtl-admin
description: أضف عزل Unicode اختياريًا إلى قيم قائمة السجلات في Django، مع قوائم الحقول المسموح بها والاستثناءات والتحكم في الاتجاه وإرشادات الفرز وسلوك العرض الآمن.
---

# BidiSafeAdminMixin { #bidisafeadminmixin }

يضيف `BidiSafeAdminMixin` محارف عزل Unicode حول قيم قائمة السجلات المؤهلة.
استخدمه للأسماء مختلطة الاتجاه والمعرّفات وعناوين البريد الإلكتروني والمسارات وغيرها
من البيانات التي ينبغي ألا تؤثر في النص المحيط بها. يؤثر في العرض، لا في قيم النماذج
المخزّنة، ويعمل في لوحات الإدارة ذات الاتجاه من اليسار إلى اليمين (LTR) ومن اليمين إلى اليسار (RTL).

## إضافته إلى ModelAdmin { #add-it-to-a-modeladmin }

استورده من جذر الحزمة وضع المزيج **قبل** `admin.ModelAdmin`:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
```

يفترض هذا المثال أن `Book` يحتوي على الحقول `title` و`isbn` و`published_on`.
يمكن أيضًا الاستيراد مباشرةً من وحدة التنفيذ:

```python
from django_rtl_admin.mixins import BidiSafeAdminMixin
```

لا يُضاف العزل تلقائيًا إلى `ModelAdmin` عادي. لإعداد الهيكل العام للوحة الإدارة
وCSS، اتبع [التثبيت](installation.md) و[البدء السريع](quick-start.md).

## إعدادات كل فئة إدارة { #per-admin-configuration }

هذه هي خصائص الإعداد الأربع المدعومة جميعها:

| الخاصية | القيمة الافتراضية | التأثير |
| --- | --- | --- |
| `bidi_isolate_changelist` | `None` | تتبع `RTL_ADMIN["ISOLATE_CHANGELIST"]`؛ وتتجاوزها `True` أو `False` لفئة الإدارة هذه. |
| `bidi_isolate_fields` | `None` | تنظر في جميع المدخلات النصية المؤهلة؛ وإلا تعزل فقط الأسماء الموجودة في هذا الكائن القابل للتكرار. لا يعزل الصف الفارغ أي مدخل. |
| `bidi_isolate_exclude` | `()` | تترك المدخلات ذات هذه الأسماء دون تغيير، حتى لو كانت في قائمة السماح. |
| `bidi_isolation_direction` | `None` | تتبع `RTL_ADMIN["ISOLATION_DIRECTION"]`؛ استخدم `"auto"` أو `"ltr"` أو `"rtl"` لتجاوزها. |

على سبيل المثال، اعزل قيم ISBN وحدها وافرض اتجاهها من اليسار إلى اليمين:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

استخدم هذا التسجيل بديلًا عن التسجيل الأول، لا تسجيلًا إضافيًا.
لا توجد آلية مضمّنة لتحديد اتجاه مستقل لكل حقل: تنطبق خاصية الاتجاه على كل قيمة
يحيطها المزيج بمحارف العزل. لتطبيق سياسات أخرى، استثنِ عمودًا واستدعِ
`mark_isolated(value, direction="ltr")` بنفسك في طريقة عرضه.

اضبط `bidi_isolate_changelist=False` لتعطيل المزيج لفئة إدارة واحدة. يمكن لقيمة
`True` محلية إعادة تفعيله حتى عندما يكون المفتاح العام معطّلًا. توضح
[الإعدادات](configuration.md) القيم الافتراضية العامة والحماية المستقلة بواسطة CSS.

## الحقول المسمّاة وطرائق العرض { #named-fields-and-display-methods }

المدخلات النصية وحدها في `list_display` مرشّحة للعزل. تُدعم أسماء حقول النماذج
المباشرة وطرائق العرض المسمّاة في النموذج أو فئة الإدارة، وكذلك
[عمليات البحث عبر العلاقات](#related-lookups-and-sorting) في Django 5.1 أو أحدث.
تمر الكائنات القابلة للاستدعاء الموضوعة مباشرةً في `list_display` دون تغيير؛
استخدم اسم الطريقة لتفعيل العزل:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "upper_title")

    @admin.display(description="Upper title", ordering="title")
    def upper_title(self, obj):
        return obj.title.upper()
```

هذا تعريف بديل آخر لفئة إدارة نموذج `Book` يحتوي على حقل `title`.
يظل Django يتولى حلّ كل مدخل مسمّى وإنتاج قيمة عرضه المعتادة.
يحتفظ الغلاف باسم العمود وتسميته. يُحفظ الفرز لحقول النموذج المباشرة وطرائق العرض
المسمّاة ذات البيانات الوصفية الصريحة للترتيب، وكذلك لعمليات البحث عبر العلاقات
في Django 5.1 أو أحدث. تُربط روابط قائمة السجلات ومدخلات `sortable_by` بكائنات الأغلفة
المخبّأة نفسها؛ ولا يجعل هذا الربط بحد ذاته عمودًا قابلًا للفرز.

تُترك المدخلات التالية دون تغيير:

- الأسماء الموجودة في `bidi_isolate_exclude` أو خارج قائمة سماح ليست `None`.
- الأسماء الموجودة في `list_editable`، حتى عند إدراجها صراحةً في قائمة السماح.
- أعمدة `BooleanField`/`NullBooleanField`، بما فيها عمليات البحث عبر العلاقات التي
  تنتهي بأحدهما، والخصائص المسمّاة المعلَّمة بـ`boolean=True`، للحفاظ على الأيقونات المنطقية.
- المدخلات غير النصية القابلة للاستدعاء.

لا تُتجاوز الحقول العددية عمومًا. تُعاد قيم العرض الفارغة، بما فيها العنصر النائب
للقيمة الفارغة في لوحة الإدارة، دون محارف عزل.
أبقِ قواعد Django المعتادة لـ`list_display` والفرز و`list_editable` ساريةً؛
فالمزيج لا يجعل إعدادات لوحة الإدارة غير الصالحة صالحةً.

### عمليات البحث عبر العلاقات والفرز { #related-lookups-and-sorting }

يقبل Django 5.1 عمليات البحث عبر العلاقات مثل `publisher__name_en` في
`list_display`. في Django 5.1 والإصدارات اللاحقة، يحلّ المزيج عملية البحث باستخدام
`get_fields_from_path()` في Django، ويضبط `admin_order_field` للغلاف على
عملية البحث نفسها ليحتفظ العمود برابط فرزه وترتيب `?o=`، ويعزل قيمة العرض للحقل النهائي:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher__name_en")
```

عند غياب الكائن المرتبط، يُعرض العنصر النائب للقيمة الفارغة دون محارف عزل.
تُترك عملية البحث التي تنتهي بـ`BooleanField` أو `NullBooleanField`، مثل
`publisher__is_active`، لـDjango دون تغيير. استثنِ عملية بحث باستخدام
`bidi_isolate_exclude` لتعطيل عزلها كأي عمود آخر.

لا يدعم Django 4.2 و5.0 عمليات البحث عبر العلاقات في `list_display` (ترفضها
لوحة الإدارة)، ولا يحلّها المزيج في هذين الإصدارين أيضًا. استخدم فيهما طريقة عرض
مسمّاة ذات ترتيب صريح، لتحافظ على العزل والفرز في جميع إصدارات Django المدعومة:

```python
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "publisher_name")

    @admin.display(description="Publisher", ordering="publisher__name_en")
    def publisher_name(self, obj):
        return obj.publisher.name_en if obj.publisher is not None else None
```

هذه تعريفات بديلة لنموذج `Book` ذي مفتاح أجنبي `publisher` يحتوي نموذجه المرتبط
على الحقلين `name_en` و`is_active`. سجّل التعريف المختار فقط. إذا كنت تستخدم
قائمة سماح للعزل، فأدرج عملية البحث أو `publisher_name` لإحاطتها بمحارف العزل.

## التهريب والتنسيق { #escaping-and-formatting }

تستدعي الأغلفة `display_for_field` أو `display_for_value` في Django، ثم
`mark_isolated`. يُهرَّب النص العادي الذي يشبه شيفرة HTML قبل عزله.
يُوثق بالقيم المعلَّمة مسبقًا بأنها آمنة، أو التي توفّر `__html__`، بدلًا من تنقيتها.
أنشئ شيفرة HTML المخصصة باستخدام `format_html` في Django، لا بتعليم نص غير موثوق بأنه آمن.

لا تعزل يدويًا نتيجة عرض سيعزلها المزيج مرةً أخرى: عزل القيمة كاملةً ليس عمليةً
تحافظ على النتيجة نفسها عند تكرارها. إما أن تدع المزيج يعالج القيمة، أو تستثني
ذلك العمود المسمّى، أو توفّر مباشرةً كائنًا قابلًا للاستدعاء يعالجها مسبقًا.
قد تبقى محارف التحكم في Unicode عند النسخ واللصق؛ طبّقها عند العرض بدلًا من
حفظها ضمن المعرّفات.

لا يستخدم المزيج تلقائيًا منسّقات Babel أو الأرقام في هذه الحزمة.
استدعِ `format_number` أو `format_currency` في طريقة عرض مسمّاة عند الحاجة،
ثم دع المزيج يعزل نتيجتها. راجع [واجهة Python البرمجية](api.md) أو
[مرشحات القوالب](template-tags.md) للتنسيق الصريح.

## النطاق والتخصيص { #scope-and-customization }

يعيد المزيج كتابة نقاط تخصيص العرض لقائمة السجلات فقط. ولا يعيد كتابة عناصر
التحرير، أو جميع الحقول المخصصة للقراءة فقط، أو المخرجات المصدَّرة. يظل العزل
بواسطة CSS مستقلًا، بما في ذلك في الأعمدة التي يتجاوزها المزيج.

أبقِ الخصائص ثابتةً بعد بدء فئة الإدارة في خدمة الطلبات: تُخبَّأ الأغلفة لكل مثيل
من فئة الإدارة، ويُحفظ الاتجاه الصريح الخاص بكل فئة إدارة عند إنشاء الأغلفة.
تُحدَّد التسميات والبيانات الوصفية للترتيب أيضًا في تلك المرحلة.
لا يوجد ضمان عام لنسخ جميع البيانات الوصفية المخصصة للكائنات القابلة للاستدعاء
أو الخصائص؛ تحقّق من الأعمدة المتخصصة مع إصدار Django لديك.

أعِد تعريف `bidi_isolation_enabled(request=None)` لتفعيل العزل بحسب الطلب؛
يتجاهل التنفيذ الافتراضي الطلب. حافظ على استدعاءات `super()` التعاونية
عند إعادة تعريف التهيئة أو نقاط تخصيص قائمة السجلات القياسية أدناه.
يسرد المرجع المولَّد تواقيعها دون تكرار النص الذي يشرح استخدام الفئة.
في هذه التواقيع، يمثّل `_ListDisplay` قائمةً أو صفًا من مدخلات `list_display`
(أسماء حقول أو كائنات قابلة للاستدعاء)، وهو الشكل نفسه الذي يمنحه django-stubs
لنقاط التخصيص في Django نفسه.

::: django_rtl_admin.mixins.BidiSafeAdminMixin
    options:
      heading_level: 3
      show_root_heading: true
      show_root_full_path: false
      show_bases: false
      show_source: false
      show_if_no_docstring: true
      show_docstring_description: false
      show_docstring_attributes: false
      show_docstring_examples: false
      members:
        - bidi_isolation_enabled
        - get_list_display
        - get_list_display_links
        - get_sortable_by
