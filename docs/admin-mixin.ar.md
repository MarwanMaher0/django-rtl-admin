---
title: BidiSafeAdminMixin | django-rtl-admin
description: أضف عزل Unicode اختياريًا إلى خلايا قائمة السجلات وحقول القراءة فقط في نموذج التعديل في Django، مع قوائم السماح والاستثناءات والتحكم في الاتجاه وإرشادات الفرز وسلوك العرض الآمن.
---

# BidiSafeAdminMixin { #bidisafeadminmixin }

يضيف `BidiSafeAdminMixin` محارف عزل Unicode حول خلايا قائمة السجلات المؤهلة وحول
المقاطع معاكسة الاتجاه المضمّنة داخل حقول `readonly_fields` في نموذج التعديل، وحول
اسم الكائن في صفحة تأكيد الحذف وفي الرسائل التي تعرضه نصًا عاديًا.
استخدمه للأسماء مختلطة الاتجاه والمعرّفات وعناوين البريد الإلكتروني والمسارات وغيرها
من البيانات التي ينبغي ألا تؤثر في النص المحيط بها. يقتصر أثر العزل على العرض ولا
يمسّ القيم المخزّنة. ويتيح المزيج أيضًا [إدخال الأعداد والتواريخ](#numeric-and-date-input)
بالأرقام العربية الهندية أو الفارسية، و[توطين الأرقام في قائمة السجلات](#changelist-digit-localization)
اختياريًا للحقول العددية والزمنية، و[مطابقة الصور المكافئة في البحث العربي](#arabic-search-folding)
للأحرف والتشكيل والتطويل والأرقام، مهما كانت لغة الواجهة. ويملأ أيضًا
[معرّفات الروابط من عناوين مكتوبة بالحرف العربي](#arabic-slug-prepopulation).

## إضافته إلى ModelAdmin { #add-it-to-a-modeladmin }

استورده من جذر الحزمة وضع المزيج **قبل** `admin.ModelAdmin`:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    readonly_fields = ("archive_note",)
```

يفترض هذا المثال أن `Book` يحتوي على الحقول `title` و`isbn` و`published_on`
و`archive_note`.
يمكن أيضًا الاستيراد مباشرةً من وحدة التنفيذ:

```python
from django_rtl_admin.mixins import BidiSafeAdminMixin
```

لا يُضاف العزل تلقائيًا إلى `ModelAdmin` عادي. لإعداد الهيكل العام للوحة الإدارة
وCSS، اتبع [التثبيت](installation.md) و[البدء السريع](quick-start.md).

## إعدادات كل فئة إدارة { #per-admin-configuration }

| الخاصية | القيمة الافتراضية | التأثير |
| --- | --- | --- |
| `bidi_normalize_input` | `None` | تتبع `RTL_ADMIN["NORMALIZE_INPUT_DIGITS"]`؛ استخدم `True` أو `False` لتفعيل تحويل الأرقام عند الإدخال أو تعطيله في هذه الفئة. |
| `bidi_local_digits` | `None` | تتبع `RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"]`؛ استخدم `True` أو `False` لتفعيل [توطين الأرقام في قائمة السجلات](#changelist-digit-localization) أو تعطيله في هذه الفئة. |
| `bidi_fold_search` | `None` | تتبع `RTL_ADMIN["FOLD_ARABIC_SEARCH"]`؛ استخدم `True` أو `False` لتفعيل [مطابقة الصور المكافئة في البحث العربي](#arabic-search-folding) أو تعطيلها في هذه الفئة. |
| `bidi_transliterate_slugs` | `None` | تتبع `RTL_ADMIN["TRANSLITERATE_SLUGS"]`؛ استخدم `True` أو `False` لتفعيل [ملء معرّفات الروابط من النص العربي](#arabic-slug-prepopulation) أو تعطيله في فئة الإدارة العادية أو المضمّنة. |
| `bidi_isolate_changelist` | `None` | تتبع `RTL_ADMIN["ISOLATE_CHANGELIST"]`؛ وتتجاوزها `True` أو `False` لفئة الإدارة هذه. يشمل المفتاح نفسه [أسماء الكائنات](#object-names-in-messages-and-on-the-delete-page) في صفحة الحذف وفي الرسائل. |
| `bidi_isolate_readonly` | `None` | تتبع `RTL_ADMIN["ISOLATE_READONLY_FIELDS"]`؛ وتتجاوزها `True` أو `False` لفئة الإدارة هذه. |
| `bidi_isolate_fields` | `None` | تنظر في جميع مدخلات `list_display` النصية المؤهلة؛ وإلا تعزل فقط الأسماء الموجودة في هذا الكائن القابل للتكرار في قائمة السجلات. لا يعزل الصف الفارغ أي مدخل. |
| `bidi_isolate_exclude` | `()` | تترك مدخلات `list_display` أو `readonly_fields` هذه دون تغيير، حتى لو كانت في قائمة السماح لقائمة السجلات. |
| `bidi_isolation_direction` | `None` | تتبع `RTL_ADMIN["ISOLATION_DIRECTION"]` لخلايا قائمة السجلات؛ استخدم `"auto"` أو `"ltr"` أو `"rtl"` لتجاوزها. |

على سبيل المثال، اعزل قيم ISBN وحدها في قائمة السجلات وافرض اتجاهها من اليسار إلى اليمين:

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

استخدم هذا التسجيل بديلًا عن التسجيل الأول، لا تسجيلًا إضافيًا.
لا توجد آلية مضمّنة لتحديد اتجاه مستقل لكل حقل: تنطبق خاصية الاتجاه على كل قيمة
في قائمة السجلات يحيطها المزيج بمحارف العزل. لتطبيق سياسات أخرى، استثنِ عمودًا واستدعِ
`mark_isolated(value, direction="ltr")` بنفسك في طريقة عرضه.

لتعطيل أحد نوعي العزل في فئة إدارة واحدة، اضبط `bidi_isolate_changelist=False`
أو `bidi_isolate_readonly=False`. ويمكن لقيمة `True` محلية إعادة تفعيله حتى عندما يكون
المفتاح العام المقابل معطّلًا. توضح [الإعدادات](configuration.md) القيم الافتراضية
العامة والحماية المستقلة بواسطة CSS.

## إدخال الأعداد والتواريخ { #numeric-and-date-input }

إذا أُرسل سعر مكتوب على صورة `١٬٢٣٤٫٥٠`، يقرؤه الحقل على أنه `1234.50` حتى لو كانت
واجهة الإدارة بالإنجليزية. يستدعي المزيج الدالة [`normalize_numeric_input`](api.md#normalizing-numeric-input)
داخل `to_python()` في حقول النماذج التي تنشئها لوحة الإدارة من الأنواع `IntegerField`
و`DecimalField` و`FloatField` و`DateField` و`TimeField` و`DateTimeField`، بما فيها
جزآ التاريخ والوقت في `SplitDateTimeField`. يشمل ذلك نموذجَي الإضافة والتعديل
وأعمدة `list_editable`، ويشمل النماذج المضمّنة **إذا كانت فئة الإدارة المضمّنة نفسها
ترث المزيج**. لا يحوّل المزيج الأرقام في الحقول النصية مثل حقل الرقم الدولي للكتاب.

تُعيد الدالة `normalize_numeric_input(value, *, decimal_separator=".")` القيم غير النصية
كما هي. أما في النصوص فتحوّل الأرقام العربية الهندية والفارسية إلى الأرقام من `0` إلى `9`،
وتحوّل علامة الطرح `−` إلى `-` والفاصل `٫` إلى الفاصل العشري المطلوب. وتحذف فاصل الآلاف
`٬` ومحارف التحكم في اتجاه النص والفراغات عند طرفيه. ولا تحذف المسافة غير القابلة للكسر
(U+00A0) أو نظيرتها الضيقة (U+202F) أو المسافة الرفيعة (U+2009) داخل النص إلا إذا وقعت
بين رقمين مباشرةً. أما الحروف وعلامات الترقيم الأخرى فتبقى كما هي.

إذا كان الحقل العددي يستخدم التنسيق المحلي، يستبدل المزيج بالفاصل `٫` الفاصل العشري
المعتمد في إعدادات Django المحلية بدلًا من فرض النقطة. ثم يقرأ Django القيمة ويتحقق
من صحتها وفق قواعد الحقل المعتادة. لا يتغير إلا النص الذي يُمرَّر إلى الحقل لتحليله؛
فإذا تعذّر قبول النموذج، تبقى البيانات المرتبطة به كما أدخلها المستخدم.

يجب إدخال التاريخ بالتقويم الميلادي وبصيغة يقبلها الحقل. فمثلًا يتحول `۲۰۲۴-۰۳-۰۵`
إلى `2024-03-05`، لكن المزيج **لا يحوّل** التواريخ من التقويم الجلالي (الهجري الشمسي)
أو الهجري القمري إلى التقويم الميلادي.

## توطين الأرقام في قائمة السجلات { #changelist-digit-localization }

فعّل `RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"] = True` عمومًا أو `bidi_local_digits = True`
في فئة `ModelAdmin` واحدة لإعادة كتابة الأرقام في خلايا قائمة السجلات لحقول النماذج
العددية والزمنية المؤهلة وفق اللغة النشطة (وتعطّل `bidi_local_digits = False` الميزة في
فئة واحدة حين يكون الإعداد العام `True`؛ ولا تتأثر فئات `ModelAdmin` العادية):

```python
@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn", "published_on", "price")
    bidi_local_digits = True
```

عند التفعيل، يعيد المزيج كتابة خلايا قائمة السجلات لحقول النماذج من الأنواع
`IntegerField` (بما فيها فئات الأعداد الصحيحة وحقول الترقيم التلقائي الفرعية)
و`DecimalField` و`FloatField` و`DateField` و`DateTimeField` و`TimeField`
و`DurationField`—بما في ذلك مسارات العلاقات في Django 5.1 أو أحدث—عبر استدعاء
[`transliterate_digits(text, numbering_system())`](api.md#locale-aware-formatting)
قبل تطبيق عزل Unicode. تتغير محارف الأرقام وحدها بينما **تبقى الفواصل كما يعرضها
Django** (فعلى سبيل المثال تصبح `1234,50` في `ar-eg` على صورة `١٢٣٤,٥٠`، وتصبح
`1234.50` في `fa` على صورة `۱۲۳۴.۵۰`). وتظل الإعدادات المحلية التي تستخدم نظام
الترقيم `latn` (مثل `en` و`ar` و`he`) مطابقةً بايتًا ببايت دون أي تغيير، كما يفرض
`RTL_ADMIN["NUMERALS"]` (`"latn"` أو `"arab"` أو `"arabext"`) نظام الترقيم.

تُترك أعمدة `CharField` و`TextField` (مثل حقل ISBN أو العنوان)، وأعمدة `ForeignKey`،
والحقول المزوّدة بـ`choices`، والأيقونات المنطقية، والأعمدة المبنية على دوال أو خصائص
قابلة للاستدعاء دون مساس، وكذلك القيم `None` و`empty_value_display`، ولا تُعاد كتابة أي
محارف داخل وسوم HTML أبدًا. وتبقى روابط الفرز و`admin_order_field` وروابط صفحة التعديل
سليمةً، ويستمر توطين الأرقام في العمل حتى عند ضبط `ISOLATE_CHANGELIST = False` أو
`bidi_isolate_changelist = False`. ولا تشمل هذه الميزة حقول الإدخال في `list_editable`،
ولا المرشّحات الجانبية (`list_filter` و`date_hierarchy`)، ولا شريط ترقيم الصفحات
(paginator)، ولا عدّاد الإجراءات (action counter)، إذ تبقى جميعها دون تغيير.

## مطابقة الصور المكافئة في البحث العربي { #arabic-search-folding }

يقارن البحث القياسي في لوحة الإدارة محارف Unicode الخام، لذا لا يطابق البحث عن `احمد`
الكلمة `أحمد`، ولا يطابق `محمد` الشكل المشكول `مُحَمَّدٌ` أو الممدود بالتطويل `مـحمد`،
ولا يطابق `مدرسه` الكلمة `مدرسة`، ولا يطابق `علي` الصور `على` أو `علی`، ولا يطابق
`كتاب` الكلمة `کتاب`، كما لا يطابق `٢٦٢` أو `۲۶۲` الرقم `262`. في فئة الإدارة التي
تستخدم المزيج، يحتفظ `get_search_results()` بنتيجة `super().get_search_results()`،
ولكل مفردة ناتجة عن `smart_split()` تتضمن حرفًا عربيًا أو رقمًا عربيًا هنديًا أو فارسيًا
يضيف شرط `OR` عبر `field__iregex` المبني بالدالة
[`arabic_search_regex`](api.md#arabic-search-folding) على حقول `search_fields` النصية المؤهلة.

تشمل المطابقة حقول `CharField` و`TextField` (بما فيها الفئات الفرعية مثل `EmailField`
و`SlugField` و`URLField`، فضلًا عن مسارات العلاقات الأمامية والعكسية)، وتحترم البادئتين
`"^"` (مطابقة من بداية الحقل) و`"="` (مطابقة كاملة للحقل)، وتتخطى بادئة البحث النصي
الكامل `"@"` والحقول غير النصية، وتربط مفردات البحث المتعددة بعلاقة `AND`، وتحدّث
`may_have_duplicates` عندما يمرّ البحث عبر علاقة متعددة القيم. وبما أن عرض الإكمال
التلقائي `AutocompleteJsonView` في Django يفوّض البحث إلى `get_search_results()` في فئة
الإدارة المستهدفة، فإن حقول `autocomplete_fields` المرتبطة بفئة إدارة تستخدم المزيج
تكتسب المطابقة نفسها تلقائيًا.

أما عبارات البحث المقتصرة على محارف ASCII أو العبرية، أو المفردات التي تؤول بعد التجريد
إلى سلسلة فارغة (مثل حركات التشكيل أو التطويل أو محارف التحكم في الاتجاه وحدها)، فتُبقي
نتائج البحث واستعلام SQL القياسي دون أي تغيير. لتعطيل هذه الميزة عمومًا اضبط
`RTL_ADMIN["FOLD_ARABIC_SEARCH"] = False`، أو لفئة إدارة بعينها اضبط
`bidi_fold_search = False`؛ واضبط `bidi_fold_search = True` للإبقاء على المطابقة في فئة
واحدة حين يكون الإعداد العام `False`.

## ملء معرّفات الروابط من النص العربي { #arabic-slug-prepopulation }

استخدم `prepopulated_fields` في Django لتحديد حقل `SlugField` المراد ملؤه والحقول
التي يُشتقّ منها. يجب أن ترث فئة الإدارة المضمّنة `BidiSafeAdminMixin` بنفسها،
حتى لو ورثته فئة الإدارة الأم أيضًا:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book, Chapter


class ChapterInline(BidiSafeAdminMixin, admin.TabularInline):
    model = Chapter
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title", "subtitle")}
    inlines = [ChapterInline]
```

هذا التسجيل بديل عن التسجيل السابق. يفترض أن `Book` يحتوي على الحقول `title`
و`subtitle` و`slug`، وأن `Chapter` يحتوي على الحقلين `title` و`slug` ومفتاح
أجنبي يشير إلى `Book`. عند تحديد أكثر من حقل مصدر، تُجمع القيم بمسافات وفق
الترتيب المحدد قبل توليد المعرّف. فمثلًا، ينتج عن العنوان `مُقَدِّمَة` والعنوان
الفرعي `١٢` المعرّف `mqdmh-12` في حقل `SlugField` الذي لا يقبل إلا محارف ASCII،
أو `مقدمة-12` عند ضبط `allow_unicode=True`. ويراعي المعرّف الناتج حد طول الحقل؛
راجع [`arabic_slugify`](api.md#arabic-slugify) لمعرفة قواعد الاقتطاع.

تقتصر المعاينة في المتصفح والملء على الخادم على نماذج الإضافة والصفوف المضمّنة
الجديدة، بما فيها الصفوف الجديدة في نموذج تعديل السجل الأم. لهذه السجلات الجديدة،
يملأ الخادم المعرّف الفارغ قبل التحقق حتى دون JavaScript، ولا يستبدل معرّفًا غير
فارغ. عند تعديل سجل أو صف مضمّن موجود، لا يملأ المزيج المعرّف الذي أفرغته:
يظل Django يرفض القيمة الفارغة إذا كان الحقل مطلوبًا. تخضع المعرّفات الناتجة
لقواعد Django المعتادة للتحقق من الحقل والنموذج والتفرّد. أدخل معرّفًا مختلفًا
إذا أظهر التحقق وجود قيمة مكررة؛ لا يضيف المزيج لاحقة.

لترك ملء المعرّفات لـDjango، اضبط `RTL_ADMIN["TRANSLITERATE_SLUGS"] = False`
على مستوى المشروع، أو اضبط `bidi_transliterate_slugs = False` في فئة الإدارة
العادية أو المضمّنة المعنية. لتفعيل الميزة في فئة واحدة حتى عند تعطيلها عمومًا،
اضبط `bidi_transliterate_slugs = True` فيها.

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

لا تُحاط المدخلات التالية بمحارف العزل عند العرض:

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

## حقول القراءة فقط في نموذج التعديل { #read-only-fields-on-the-change-form }

في نموذج التعديل (وفي وضع العرض فقط والنماذج المضمّنة التي ترث `BidiSafeAdminMixin`
أيضًا)، يغلّف `render_change_form()` الكائن `context["adminform"]` بحيث تُعزل المقاطع
معاكسة الاتجاه المضمّنة في كل قيمة مؤهلة ضمن `readonly_fields` باستخدام
`mark_isolated_runs()` دون استبدال القالب `admin/includes/fieldset.html`. وتبقى
تسميات الحقول ونصوص المساعدة وفئات CSS من الشكل `field-<name>` مطابقةً للوحة الإدارة
الافتراضية.

ولأن `.rtl-admin div.readonly` يحمل القاعدة `unicode-bidi: plaintext`، يحدد المتصفح
الاتجاه الأساسي لكل سطر فقرة من أول محرف قوي فيه في كلٍّ من لوحتَي RTL وLTR. يستخدم
المزيج الاتجاه نفسه المستند إلى أول محرف قوي لكل سطر (مع الرجوع إلى اتجاه الواجهة
النشطة للأسطر المحايدة فقط) عند استدعاء `mark_isolated_runs()`، فيبقى المسار في ملاحظة
عربية مثل `نُقل الملف إلى /srv/archive/2024-03-05` معزولًا داخل `LRI...PDI` سواء أكانت
واجهة الإدارة `ar-eg` أم `en`.

تُدعم حقول النماذج وطرائق العرض المسمّاة في النموذج أو فئة الإدارة والكائنات القابلة
للاستدعاء في `readonly_fields`. وتُترك الحقول المنطقية وطرائق العرض المعلَّمة بـ`boolean=True`
والعناصر النائبة للقيم الفارغة وعناصر النماذج المخصصة للقراءة فقط والقيم التي هي أصلًا
`SafeString` (بما فيها روابط `ForeignKey` / `OneToOneField` في لوحة الإدارة) دون تغيير.
استثنِ اسم حقل أو كائنًا قابلًا للاستدعاء (بالكائن نفسه أو عبر `__name__`) باستخدام
`bidi_isolate_exclude`، أو عطّل الميزة لكل فئة إدارة عبر `bidi_isolate_readonly = False`،
أو عطّلها عمومًا عبر `RTL_ADMIN["ISOLATE_READONLY_FIELDS"] = False`.

## أسماء الكائنات في الرسائل وفي صفحة الحذف { #object-names-in-messages-and-on-the-delete-page }

تقتبس لوحة الإدارة أيضًا ناتج `__str__` للكائن داخل جمل وعناوين. في لوحة إدارة
RTL، يُعاد ترتيب معرّف مثل `978-0-262-03561-3` أو `v1.2.3` بين علامتَي الاقتباس
ما لم يُعزل. يتولى المزيج المواضع التي يعرض فيها Django الاسم نصًا عاديًا؛ وتتولى
ورقة أنماط الحزمة المواضع التي يكون فيها للاسم عنصر خاص به:

| موضع ظهور الاسم | وسيلة العزل | المفتاح |
| --- | --- | --- |
| سؤال تأكيد الحذف ومسار التنقل | المزيج، `render_delete_form()` | `ISOLATE_CHANGELIST` أو `bidi_isolate_changelist` |
| مدخلات الكائنات المرتبطة والمحمية النصية في صفحتَي تأكيد الحذف وتأكيد حذف العناصر المحددة | المزيج، `get_deleted_objects()` | `ISOLATE_CHANGELIST` أو `bidi_isolate_changelist` |
| رسالة نجاح الحذف | المزيج، `response_delete()` | `ISOLATE_CHANGELIST` أو `bidi_isolate_changelist` |
| رسالة «تمت الإضافة» دون صلاحية التعديل (نص عادي) | المزيج، `response_add()` | `ISOLATE_CHANGELIST` أو `bidi_isolate_changelist` |
| رسالتا «تمت الإضافة» و«تم التعديل» باسم على هيئة رابط | ورقة الأنماط | `ISOLATE_TABLE_CELLS` |
| العنوان الفرعي في نموذج التعديل | ورقة الأنماط | `ISOLATE_TABLE_CELLS` |
| روابط الكائنات في القوائم في صفحتَي تأكيد الحذف وتأكيد حذف العناصر المحددة | ورقة الأنماط | `ISOLATE_TABLE_CELLS` |

يحيط المزيج الاسم كله باستخدام `isolate()`، بالاتجاه الذي يحدده
`RTL_ADMIN["ISOLATION_DIRECTION"]`. لا تنطبق خصائص فئة الإدارة
`bidi_isolation_direction` و`bidi_isolate_fields` و`bidi_isolate_exclude` على أسماء
الكائنات. يهرّب Django الاسم بعد ذلك كعادته، فتبقى شيفرة HTML في `__str__`
مهرَّبةً، وتُزال من الاسم أولًا محارف `Bidi_Control` الموجودة فيه. في صفحة تأكيد
الحذف وفي رسالة «تمت الإضافة»، يُعرض الاسم الفارغ أو المكوَّن من مسافات فقط كما
في لوحة الإدارة الافتراضية تمامًا.

لا تُدرج قواعد ورقة الأنماط أي محارف. وهي تتطلب CSS الخاص بالحزمة
(`ENABLE_CSS`) وتتبع بنية HTML في لوحة الإدارة الافتراضية:

```css
.rtl-admin--isolate-cells ul.messagelist li a,
.rtl-admin--isolate-cells #content > h2,
.rtl-admin--isolate-cells #content > .titles-and-tools > .titles > h2,
.rtl-admin--isolate-cells.delete-confirmation #content ul li a {
  unicode-bidi: isolate;
}
```

### صفحة تأكيد الحذف ورسالته { #delete-confirmation-page-and-message }

يضع `render_delete_form()` في `context["object"]` وسيطًا خفيفًا بدلًا من الكائن، يعيد
`__str__` فيه الاسم معزولًا ويفوّض كل خاصية أخرى إلى الكائن الحقيقي، فيظل مسار
التنقل يشير إلى صفحة تعديل الكائن. ولا يمكن للمرشّح `truncatewords:"18"` في مسار
التنقل أن يقتطع محرف PDI الختامي: في الاسم الأطول يُغلق العزل بعد الكلمة الثامنة
عشرة ويُفتح من جديد لبقية الاسم. يعرض Django 6.1 السؤال من قيمة `escaped_object`
محسوبة مسبقًا، ويعزل المزيج تلك القيمة أيضًا.

يمرّر `response_delete()` الاسم المعزول إلى Django، الذي يبني منه رسالة «تم الحذف
بنجاح». ويحتفظ `LogEntry` بالاسم العادي.

تأتي قوائم الكائنات التي ستُحذف والكائنات المحمية في هذه الصفحة، وفي صفحة تأكيد
إجراء «حذف العناصر المحددة»، من الدالة `get_deleted_objects()` في Django. وتُترك
المدخلات المرتبطة بروابط (قيم `SafeString` التي تحتوي على رابط إدارة) مطابقةً
بايتًا ببايت لتعزلها ورقة الأنماط. أما المدخلات النصية العادية—مثل كائن مرتبط
ليست له صفحة إدارة خاصة به، والذي ينسّقه Django بالصيغة
`<Verbose name>: <str(obj)>`—فيُحاط الاسم فيها بعد أول `": "` باستخدام
`isolate()` بصفته نصًا عاديًا حتى يواصل Django تهريب أي شيفرة HTML فيه، مع
إبقاء تداخل القوائم و`model_count` و`perms_needed` دون تغيير.

### رسائل الإضافة والتعديل { #add-and-change-messages }

عندما يحق للمستخدم تعديل الكائن، يجعل Django اسمه رابطًا في رسالة النجاح. تعزل
ورقة الأنماط ذلك الرابط، ويترك المزيج الرسالة كما بناها Django تمامًا.

أما المستخدم الذي لا يملك صلاحية التعديل فتصله رسالة «تمت الإضافة» والاسم فيها نص
عادي لا يطاله أي محدِّد CSS، ولذلك يحيط المزيج الاسم باستخدام `isolate()`،
أيًّا كان زر الحفظ المستخدم.
لا تُعاد كتابة سوى الرسالة التي يبنيها Django نفسه. أما إعادة التوجيه، واستجابة
النافذة المنبثقة للكائن المرتبط، و`LogEntry`، وأي رسالة ترسلها شيفرتك عبر
`message_user()`، فتبقى كما هي تمامًا.

في Django من 4.2 إلى 6.1، يجعل `response_change()` الاسم رابطًا أيًّا كانت
صلاحيات المستخدم، فليس لرسالة «تم التعديل» صيغة نصية عادية ولا تُعاد كتابتها
أبدًا. ولا يتدخل `response_change()` في المزيج إلا عندما ترسل فئة أساسية رسالة
«تم التعديل» الخاصة بـDjango باسم عادي بدلًا من الرابط.

### العنوان الفرعي في نموذج التعديل { #change-form-subtitle }

يكرر نموذج التعديل، وكذلك في وضع العرض فقط، اسم الكائن في عنوان فرعي `<h2>` تحت
عنوان الصفحة. حتى Django 6.0 يكون هذا العنوان ابنًا مباشرًا للعنصر `#content`؛
ونقله Django 6.1 إلى داخل `.titles-and-tools > .titles`. وفي ورقة الأنماط قاعدة
لكل منهما. ليس لصفحة سجل التغييرات عنوان فرعي: الاسم فيها جزء من جملة العنوان
`<h1>`، التي لا تُعزل إلا كوحدة واحدة.

## التهريب والتنسيق { #escaping-and-formatting }

تستدعي أغلفة قائمة السجلات `display_for_field` أو `display_for_value` في Django، ثم
`mark_isolated`؛ وتعزل أغلفة حقول القراءة فقط المقاطع المضمّنة لكل سطر فقرة باستخدام
`mark_isolated_runs` وتصل الأسطر بـ`<br>` مطابقةً لـ`linebreaksbr` في Django. يُهرَّب
النص العادي الذي يشبه شيفرة HTML، وتزيل كلتا الدالتين أي محارف `Bidi_Control` موجودة في
Unicode قبل الإحاطة كي لا تفلت محارف `PDI` أو محارف فرض الاتجاه المضمّنة من نطاق العزل.
لا يُعاد تهريب القيم المعلَّمة مسبقًا بأنها آمنة، أو التي توفّر `__html__`، ولا تُنقَّى من
شيفرة HTML (وتترك `mark_isolated_runs` شيفرة HTML الآمنة مسبقًا دون تغيير). أنشئ شيفرة
HTML المخصصة باستخدام `format_html` في Django، لا بتعليم نص غير موثوق بأنه آمن.

نظرًا إلى أن `mark_isolated` تزيل محارف `Bidi_Control` الموجودة قبل الإحاطة، فإن
العمود الذي تستدعي طريقة عرضه `mark_isolated_runs` (أو تضبط اتجاه `mark_isolated`
صريحًا يختلف عن اتجاه فئة الإدارة الافتراضي) ستُستبدل محارف العزل الداخلية فيه ما لم
تستثنِ ذلك العمود المسمّى عبر `bidi_isolate_exclude` أو تضع الكائن القابل للاستدعاء
مباشرةً في `list_display`. قد تبقى محارف التحكم في Unicode عند النسخ واللصق؛ طبّقها
عند العرض بدلًا من حفظها ضمن المعرّفات.

حتى عند تفعيل [توطين الأرقام في قائمة السجلات](#changelist-digit-localization)، يكتفي
المزيج بتحويل محارف الأرقام في النص الذي ينسّقه Django للحقل، ولا يستدعي تلقائيًا منسّقات
Babel أو أنماط الفواصل والعملات الخاصة بـCLDR في هذه الحزمة. استدعِ `format_number` أو
`format_currency` في طريقة عرض مسمّاة عند الحاجة إلى فواصل الإعداد المحلي أو تنسيق
العملات، ثم دع المزيج يعزل نتيجتها. راجع [واجهة Python البرمجية](api.md) أو
[مرشحات القوالب](template-tags.md) للتنسيق الصريح.

## النطاق والتخصيص { #scope-and-customization }

يتدخل المزيج في طرائق عرض قائمة السجلات، وفي `get_search_results` للبحث في قائمة السجلات
وحقول الإكمال التلقائي، وفي `render_change_form` لحقول القراءة فقط،
وفي `get_deleted_objects` و`render_delete_form` و`response_delete` و`response_add`
و`response_change` و`message_user` لأسماء الكائنات. عند تفعيل تحويل الأرقام، تستخدم
عناصر الإدخال من النوع `number` مدخلًا نصيًا (`type="text"`) مع `inputmode="numeric"`
أو `inputmode="decimal"`. وبذلك يستطيع المتصفح اقتراح لوحة مفاتيح رقمية دون أن يمحو
القيمة المكتوبة بأرقام محلية عند إدخالها أو عند عرض النموذج مجددًا، كما قد يحدث مع
`type="number"`. ويظل Django مسؤولًا عن التحقق من القيمة على الخادم. تحتفظ بقية عناصر
الإدخال بإعداداتها، وتبقى المخرجات المصدَّرة كما هي. يظل العزل بواسطة CSS مستقلًا،
بما في ذلك في الأعمدة والحقول التي يتجاوزها المزيج.

أبقِ الخصائص ثابتةً بعد بدء فئة الإدارة في خدمة الطلبات: تُخبَّأ الأغلفة لكل مثيل
من فئة الإدارة، ويُحفظ الاتجاه الصريح الخاص بكل فئة إدارة عند إنشاء الأغلفة.
تُحدَّد التسميات والبيانات الوصفية للترتيب أيضًا في تلك المرحلة.
لا يوجد ضمان عام لنسخ جميع البيانات الوصفية المخصصة للكائنات القابلة للاستدعاء
أو الخصائص؛ تحقّق من الأعمدة المتخصصة مع إصدار Django لديك.

أعِد تعريف `bidi_isolation_enabled(request=None)` أو
`bidi_readonly_isolation_enabled(request=None)` لتفعيل العزل بحسب الطلب؛
يتجاهل التنفيذ الافتراضي لكليهما الطلب. حافظ على استدعاءات `super()` التعاونية
عند إعادة تعريف التهيئة أو نقاط تخصيص `ModelAdmin` القياسية أدناه.
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
        - bidi_readonly_isolation_enabled
        - formfield_for_dbfield
        - get_search_results
        - get_list_display
        - get_list_display_links
        - get_sortable_by
        - render_change_form
        - get_deleted_objects
        - render_delete_form
        - response_delete
        - response_add
        - response_change
        - message_user
