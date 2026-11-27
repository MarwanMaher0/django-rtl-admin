---
title: واجهة Python البرمجية | django-rtl-admin
description: استخدم دوال Python لتحويل الأرقام عند الإدخال، وتوليد معرّفات الروابط من النص العربي، وعزل النص ثنائي الاتجاه، وتنسيق الأعداد والعملات والتواريخ بحسب اللغة.
---

# واجهة Python البرمجية { #python-api }

استخدم دوال العزل والتنسيق في طرائق العرض أو القوالب المخصصة. يمكن لهذه الدوال
الاستفادة من اللغة النشطة في Django ومن [الإعدادات](configuration.md). استخدم
`normalize_numeric_input` لمعالجة مدخلات النماذج، و`arabic_search_regex` لبناء
استعلامات `iregex` تراعي اختلاف صور الحروف العربية، و`arabic_slugify` لتوليد
معرّفات الروابط من نص مكتوب بالحرف العربي. تعيد هذه الدوال القيم دون حفظها.

## تحويل الأرقام عند الإدخال { #normalizing-numeric-input }

تُعيد الدالة `normalize_numeric_input(value, *, decimal_separator=".")` القيم غير
النصية كما هي. أما في النصوص فهي:

- تحوّل الأرقام العربية الهندية (`٠١٢٣٤٥٦٧٨٩`) والفارسية (`۰۱۲۳۴۵۶۷۸۹`) إلى الأرقام من `0` إلى `9`.
- تستبدل الفاصل العشري العربي `٫` (U+066B) بقيمة `decimal_separator`، وعلامة
  الطرح `−` (U+2212) بالعلامة `-` من ASCII.
- تحذف فاصل الآلاف العربي `٬` (U+066C). وتحذف داخل النص المسافة غير القابلة
  للكسر (U+00A0)، ونظيرتها الضيقة (U+202F)، والمسافة الرفيعة (U+2009) فقط إذا
  وقعت المسافة مباشرةً بين رقمين.
- تزيل محارف Unicode ذات الخاصية `Bidi_Control` والفراغات عند طرفَي النص.

```python
from django_rtl_admin import normalize_numeric_input

assert normalize_numeric_input("−١٬٢٣٤٫٥٠") == "-1234.50"
assert normalize_numeric_input("۱۲٫۵", decimal_separator=",") == "12,5"
assert normalize_numeric_input("١٢,٣ USD") == "12,3 USD"
```

لا تفسّر الدالة النص باعتباره عددًا ولا تتحقق من صحته، وتترك الحروف وبقية علامات
الترقيم دون تغيير. فمثلًا، لا تخمّن ما إذا كانت فاصلة ASCII فاصلةً عشرية أم فاصل
آلاف. يستدعيها [مزيج لوحة الإدارة](admin-mixin.md#numeric-and-date-input) قبل أن
يقرأ Django الحقل، ويمرّر إليها الفاصل العشري النشط في Django للحقول العددية
التي تستخدم التنسيق المحلي.

## مطابقة الصور المكافئة في البحث العربي { #arabic-search-folding }

تحوّل `arabic_search_regex(term)` مفردة البحث إلى تعبير نمطي قابل للاستخدام
مع SQLite وPostgreSQL وMySQL 8، لمطابقة الصور المكافئة للحروف العربية والتشكيل
والتطويل والأرقام:

- تزيل من `term` التشكيل (U+064B–U+065F وU+0670)، والتطويل (`ـ`، U+0640)،
  ومحارف Unicode ذات الخاصية `Bidi_Control`.
- تجمع في فئات محارف بين أقواس مربعة صور الألف (`آ` و`أ` و`إ` و`ا` و`ٱ`)، والتاء
  المربوطة والهاء (`ة` و`ه`)، والألف المقصورة والياء والياء الفارسية والياء بهمزة
  (`ئ` و`ى` و`ي` و`ی`)، والكاف العربية والفارسية (`ك` و`ک`)، والواو والواو بهمزة
  (`ؤ` و`و`)، وصور كل رقم في ASCII (`0`–`9`) والأرقام العربية الهندية (`٠`–`٩`)
  والفارسية (`۰`–`۹`).
- تضع `[\u0640\u064b-\u065f\u0670]*` بعد كل حرف عربي كي لا يمنع التشكيل أو
  التطويل في النص المخزّن حدوث المطابقة.
- تضع كل علامة ترقيم أو رمز في فئة محارف منفردة بين قوسين مربعين. ولا يتضمن
  التعبير الناتج إلا المحارف الحرفية وفئات المحارف وعلامة `*`.

```python
import re

from django_rtl_admin import arabic_search_regex

pattern = arabic_search_regex("احمد ١٤٤٦")
assert re.fullmatch(pattern, "أَحْمَدُ 1446")
```

يستخدم [مزيج لوحة الإدارة](admin-mixin.md#arabic-search-folding) هذه الدالة في
`get_search_results()` لمفردات البحث التي تحتوي على حرف عربي أو رقم عربي هندي
أو فارسي.

## توليد معرّفات الروابط باستخدام `arabic_slugify` { #arabic-slugify }

تولّد `arabic_slugify(value, *, allow_unicode=False, max_length=None)` معرّف رابط
من نص مكتوب بالحرف العربي. في كلا الوضعين، تزيل الدالة التشكيل (U+064B–U+065F
وU+0670)، والتطويل (`ـ`، U+0640)، ومحارف Unicode ذات الخاصية `Bidi_Control`،
وتحوّل الأرقام العربية الهندية والفارسية إلى أرقام ASCII.

- عند ضبط `allow_unicode=True`، تعالج `slugify()` في Django النص المنظّف في وضع
  Unicode، ويمكنها الاحتفاظ بالحروف العربية.
- في وضع ASCII الافتراضي، يعالج التطبيع التوافقي الأشكال العرضية للحروف العربية.
  ثم تستبدل الدالة بالحروف المقابلات المبيّنة أدناه قبل تطبيق `slugify()` في Django
  في وضع ASCII. هذا تحويل ثابت لكل حرف، لا نقلٌ لنطق الكلمة. إذا احتوى المدخل
  على محارف عربية ولم ينتج عنه أي معرّف ASCII، تُستخدم القيمة البديلة `arabic`.

| الحروف | ASCII | الحروف | ASCII | الحروف | ASCII |
| --- | --- | --- | --- | --- | --- |
| `ا أ إ آ ٱ ء ع ى` | `a` | `ز` | `z` | `ق` | `q` |
| `ب` | `b` | `س ص` | `s` | `ك ک` | `k` |
| `ت ط` | `t` | `ش` | `sh` | `ل` | `l` |
| `ث` | `th` | `ظ` | `z` | `م` | `m` |
| `ج` | `j` | `غ` | `gh` | `ن` | `n` |
| `ح ه ة ہ ۀ ە` | `h` | `ف` | `f` | `و ؤ` | `w` |
| `خ` | `kh` | `پ` | `p` | `ي ی ئ` | `y` |
| `د ض` | `d` | `چ` | `ch` | `گ` | `g` |
| `ذ` | `dh` | `ژ` | `zh` | `ر` | `r` |

إذا تجاوز طول المعرّف `max_length`، يُقتطع عند آخر شرطة تقع ضمن الحد أو عنده،
مع حذف الشرطة نفسها. وإذا تجاوز المقطع الأول الحد، يُقتطع عند الحد مباشرةً.
تعني `None` عدم وضع حد، ويؤدي الصفر أو أي حد سالب إلى إرجاع سلسلة فارغة.

```python
from django_rtl_admin import arabic_slugify

assert arabic_slugify("مُقَدِّمَة ١٢") == "mqdmh-12"
assert arabic_slugify("مُقَدِّمَة ١٢", allow_unicode=True) == "مقدمة-12"
assert arabic_slugify("پژوهش ۱۴۰۳") == "pzhwhsh-1403"
assert arabic_slugify("مقدمة الكتاب", max_length=9) == "mqdmh"
assert arabic_slugify("مقدمة الكتاب", max_length=3) == "mqd"
```

لا تتحقق الدالة من تفرّد المعرّف. راجع [ملء معرّفات الروابط من النص العربي](admin-mixin.md#arabic-slug-prepopulation)
للتعرّف على التكامل مع لوحة الإدارة وقواعد التحقق.

::: django_rtl_admin.arabic_slugify
    options:
      heading_level: 3
      show_root_full_path: false

## مفاتيح الفرز العربية { #arabic-sort-keys }

استخدم `arabic_sort_key(value)` مفتاحًا (`key`) للدالة `sorted()` في بايثون. تعيد نصًا
بأحرف صغيرة، أو نصًا فارغًا (`""`) عند `None`. تحذف الحركات (U+064B–U+065F وU+0670)
والتطويل (`ـ`) ومحارف `Bidi_Control` في يونيكود، وتحوّل `آ` و`أ` و`إ` و`ٱ` إلى `ا`،
و`ة` إلى `ه`، و`ى` و`ئ` إلى `ي`، و`ؤ` إلى `و`، والأرقام العربية الهندية والفارسية إلى
أرقام ASCII. الناتج مفتاح نصي للمقارنة، لا قيمة عددية ولا بديل عن الكتابة الأصلية.

```python
from django_rtl_admin import arabic_sort_key

assert arabic_sort_key("مَكْتَبَة ١٢") == arabic_sort_key("مكتبه ۱۲") == "مكتبه 12"
assert arabic_sort_key(None) == ""
titles = ["آفاق العلم", "أبواب المدينة", "إدارة الوقت"]
assert sorted(titles, key=arabic_sort_key) == ["أبواب المدينة", "إدارة الوقت", "آفاق العلم"]
```

ولفرز `QuerySet`، تبني `arabic_sort_expression(field_name)` تعبيرًا في Django ORM يطبّق
الاستبدالات نفسها بـ`Replace` ثم يحوّل الناتج إلى أحرف صغيرة بـ`Lower`. مثلًا، لنموذج
`Book` فيه حقل نصي باسم `title_ar`:

```python
from django_rtl_admin import arabic_sort_expression

by_title = arabic_sort_expression("title_ar")
ascending = Book.objects.order_by(by_title.asc(), "pk")
descending = Book.objects.order_by(by_title.desc(), "pk")
```

يستخدم PostgreSQL وMySQL 8 استدعاءات `REPLACE` متداخلة ثم `LOWER`. أما SQLite فيستخدم
استعلامًا فرعيًا `WITH` لتفادي حد عمق المحلل في الإصدارات الأقدم: تمرّر سلاسل `REPLACE`
قصيرة نتائجها من مرحلة إلى التالية، ثم يطبّق `SELECT` الأخير `LOWER`.

لا تُثبَّت أي collation مخصّصة. يحسب الاستعلام المفتاح لكل صف، لذلك قد لا يسرّع فهرس
عادي على العنوان هذا الفرز، ويعطي `pk` الثانوي العناوين المتساوية ترتيبًا ثابتًا.
وتبقى قاعدة البيانات هي التي تحدد الـcollation وتحويل حالة الأحرف وموضع `NULL`: بخلاف
دالة بايثون، يترك التعبير `NULL` كما هي. لا تفترض ترتيبًا متطابقًا بين قواعد البيانات
المختلفة ولا فرزًا قاموسيًا كاملًا. ولا تحتاج أيٌّ من الدالتين
[مزيج الإدارة](admin-mixin.md#arabic-changelist-ordering) ولا تغيّر النص المخزّن.

## مرشّح قائمة السجلات بحسب الحرف الأول { #arabic-initial-list-filter }

تعيد `arabic_initial_filter(field_name, *, title=None, parameter_name=None, include_latin=True, include_digits=True)`
فئةً ترث `ArabicInitialListFilter` لاستخدامها في `ModelAdmin.list_filter`.
مرّر اسم حقل نصي أو مسارًا عبر علاقة مثل `publisher__name_ar`. يأخذ `title`
افتراضيًا قيمة `verbose_name` للحقل الأخير (أي تسمية `name_ar` في هذا المثال)،
أما القيمة الافتراضية لـ`parameter_name` فهي `field_name.replace("__", "_") + "__initial"`.
مثلًا، يصبح اسم المعامل `title__initial` للحقل `title`، و`publisher_name_ar__initial`
للمسار `publisher__name_ar`. يمنع استبدال فواصل المسار Django من تفسير المعامل
في الرابط على أنه استعلام عبر علاقة. حدّد `title` لتغيير عنوان المرشّح في الشريط
الجانبي، أو `parameter_name` لتغيير اسم معامل الاستعلام في الرابط.

يمكنك أيضًا تعريف فئة ترث `ArabicInitialListFilter` مباشرةً. اضبط `field_name`
في تعريف الفئة ومرّر الفئة نفسها إلى `list_filter`:

```python
from django.contrib import admin

from django_rtl_admin import ArabicInitialListFilter


class PublisherInitialFilter(ArabicInitialListFilter):
    field_name = "publisher__name_ar"
    include_digits = False


class BookAdmin(admin.ModelAdmin):
    list_filter = (PublisherInitialFilter,)
```

عند ضبط `include_digits=False`، تندرج الأسماء التي تبدأ برقم ضمن فئة **أخرى**.
وينطبق الأمر نفسه على الأسماء التي تبدأ بحرف لاتيني عند ضبط `include_latin=False`.
راجع [مثال قائمة السجلات](admin-mixin.md#filter-by-arabic-initial) لاستخدام الدالة
بدلًا من تعريف فئة، ولمعرفة مصدر الخيارات وترتيبها.

## اختيار دالة العزل { #choosing-an-isolation-helper }

- تزيل `isolate()` أي محارف Unicode موجودة من نوع `Bidi_Control` وتحيط القيمة
  النصية كاملةً بمحارف العزل. استخدم `direction="ltr"` لمعرّف ثابت مثل رقم ISBN.
- تزيل `isolate_runs()` محارف Unicode الموجودة من نوع `Bidi_Control` وتعزل
  المقاطع معاكسة الاتجاه داخل النص العادي.
- الدالتان `mark_isolated()` و`mark_isolated_runs()` تنتجان HTML. أبقِ
  `autoescape=True` للنص غير الموثوق. تزيل `mark_isolated()` محارف `Bidi_Control`
  الموجودة عند إحاطة القيمة، ولا تعيد تهريب HTML المعلّم مسبقًا بأنه آمن. أما
  `mark_isolated_runs()` فتترك HTML الآمن دون تغيير كي لا تتلف الوسوم.
- تزيل `strip_isolates()` محارف Unicode الاثني عشر من نوع `Bidi_Control`
  (`ALM` و`LRM` و`RLM` و`LRE` و`RLE` و`PDF` و`LRO` و`RLO` و`LRI` و`RLI` و`FSI`
  و`PDI`). ولا تزيل HTML ولا محارف التحكم غير المتعلقة بالاتجاه.

```python
from django.utils import translation

from django_rtl_admin.bidi import isolate, mark_isolated_runs
from django_rtl_admin.formatting import format_number

reference = isolate("978-0-13-468599-1", direction="ltr")
with translation.override("ar-eg"):
    description = mark_isolated_runs("الإصدار v1.2.3")
    amount = format_number(1234.5, decimal_pos=2)
```

يُدرج العزل محارف Unicode لا عناصر HTML. طبّقه عند العرض لا قبل حفظ المعرّفات،
فقد تبقى محارف التحكم عند النسخ واللصق.

::: django_rtl_admin.bidi
    options:
      heading_level: 2
      members:
        - rtl_languages
        - is_rtl_language
        - current_direction
        - text_direction
        - has_mixed_direction
        - isolate
        - is_isolated
        - strip_isolates
        - mark_isolated
        - isolate_runs
        - mark_isolated_runs

## التنسيق بحسب الإعدادات المحلية { #locale-aware-formatting }

ثبّت `django-rtl-admin[babel]` لاستخدام فواصل CLDR وأنماطها للعملات والتواريخ.
في غياب Babel أو عند ضبط `USE_BABEL=False`، يستخدم تنسيق الأعداد جدول CLDR
مضمّنًا لتحديد فاصل الآلاف والفاصل العشري وطريقة تجميع الأرقام وأشكالها بما يطابق
مخرجات Babel للإعدادات المحلية المدعومة. ولا يستخدم تنسيق Django مع تحويل الأرقام
إلا للإعدادات التي لا يغطيها الجدول. ويظل تنسيق التاريخ والوقت من اختصاص Django
في هذا المسار البديل. تُراعى قيمة `language` الصريحة في جميع الحالات.

استخدم `short` أو `medium` أو `long` أو `full` لتحديد نمط التاريخ أو التاريخ
والوقت على نحو يعمل مع Babel وDjango. في المسار البديل يبحث Django عن الأنماط
في وحدات التنسيق الخاصة باللغة المطلوبة. وتسبق وحدات المشروع المحددة في
`FORMAT_MODULE_PATH` وحدات Django المضمّنة. للتواريخ ولقيم التاريخ والوقت،
يختار `short` التنسيق المختصر، وتختار `medium` و`long` و`full` التنسيق المعتاد.
إذا لم تُعرّف الإعدادات المحلية `DATETIME_FORMAT`، يُجمع `DATE_FORMAT` مع
`TIME_FORMAT`. وإذا غاب `SHORT_DATETIME_FORMAT`، يُجمع `SHORT_DATE_FORMAT` مع
`TIME_FORMAT`. تسدّ أنماط CLDR المضمّنة الفجوات للأردية (`ur`) وللأويغورية (`ug`)
عندما لا يتضمن Django وحدة تنسيق للأويغورية (في 4.2). وإذا لم تغطِّ وحدات اللغة
ولا الجدول اللغة المطلوبة، تبقى قيم Django الافتراضية ساريةً.

في المسار البديل، تستخدم `format_time()` قيمة `TIME_FORMAT` للإعدادات المحلية
في الأنماط الأربعة المسماة. لطلب تنسيق معيّن، مرّر سلسلة تنسيق من Django إلى
`fmt`، مثل `H:i:s` للساعات والدقائق والثواني. تظل Babel تستخدم أنماطها المسماة
وأنماط CLDR للتواريخ والأوقات، ولا يختلف تحويل الأرقام بين المسارين.

عند ضبط `USE_TZ=True`، تحوّل `format_datetime()` و`format_time()` قيم `datetime`
التي تتضمّن معلومات المنطقة الزمنية إلى المنطقة الزمنية النشطة في Django باستخدام
`django.utils.timezone.localtime()` في مسار Babel ومسار Django البديل. ويضبط
مرشّحا القوالب `l10n_datetime` و`l10n_time` الخاصية `expects_localtime=True`،
فيحترمان `{% localtime off %}`. تبقى قيم `datetime` و`time` التي لا تتضمّن
معلومات المنطقة الزمنية، وقيم `date` المجرّدة، دون تغيير.

يتحكم `NUMERALS` في أشكال الأرقام، لا في جميع الفواصل. تحوّل
`transliterate_digits()` الأرقام بين `latn` و`arab` و`arabext` دون تغيير علامات
الترقيم. ويستدعي [مزيج الإدارة](admin-mixin.md#changelist-digit-localization)
`transliterate_digits(text, numbering_system())` على خلايا قائمة السجلات العددية
والزمنية المؤهلة عند تفعيل `LOCALIZE_CHANGELIST_DIGITS` أو `bidi_local_digits`،
مع الإبقاء على فواصل Django كما هي. تعيد دوال التنسيق نصًا؛ طبّق العزل عليه بشكل مستقل عند الحاجة.

تنسّق `format_timedelta()` مدةً من نوع `timedelta` أو عددًا من الثواني وفق أنماط
الوحدات في CLDR. وفي غياب Babel تستخدم نصوص `timesince` المترجمة في Django.
تطابق وسائطها `granularity` و`threshold` و`add_direction` و`format` وسائط
`babel.dates.format_timedelta`. وتنسّق `format_filesize()` عدد البايتات باستخدام
قوى 1000 افتراضيًا أو قوى 1024 عند ضبط `binary=True`. وتُستخدم أسماء الوحدات
المترجمة في Django في كلا المسارين.

::: django_rtl_admin.formatting
    options:
      heading_level: 2
      members:
        - arabic_search_regex
        - arabic_sort_key
        - arabic_sort_expression
        - numbering_system
        - normalize_numeric_input
        - transliterate_digits
        - format_number
        - format_currency
        - format_percent
        - format_timedelta
        - format_filesize
        - format_date
        - format_datetime
        - format_time
        - format_hijri_date

## التواريخ الهجرية { #hijri-dates }

تحتاج مواقع الإدارة في السعودية والخليج عادةً إلى تقويم أم القرى، وهو تقويم
لا توفّره Babel. تحوّل الدالتان `to_hijri()` و`from_hijri()` بين التاريخ
الميلادي والجدول الرسمي لتقويم أم القرى للسنوات 1343–1500 هـ
(1 أغسطس 1924 إلى 16 نوفمبر 2077 م) دون إضافة أي اعتماد وقت التشغيل. وترفع
التواريخ خارج هذا النطاق `ValueError`، وتقبل `to_hijri()` أيضًا قيمة
`datetime`، فتحوّل القيم الواعية بالمنطقة الزمنية إلى المنطقة النشطة عند
ضبط `USE_TZ=True`.

`HijriDate` فئة بيانات مجمّدة تضم `year` و`month` و`day` و`month_length`.
وتعرض `format_hijri_date()` أسماء الأشهر كاملة: بالعربية لـ`ar`، والفارسية
لـ`fa`، والأردية لـ`ur`، وبالنقحرة الإنجليزية لغيرها. يكتب النمط `long`
اليوم والشهر والسنة، ويضيف `medium` صفرًا بادئًا لليوم، ويكتب `short`
بالصيغة `dd/mm/yyyy`. وتتبع الأرقام `NUMERALS` ونظام ترقيم اللغة، وتُضاف
لاحقة العصر (`هـ` أو `هجری قمری` أو `ہجری` أو `AH`) ما لم تُضبط
`suffix=False`.

```python
from datetime import date

from django_rtl_admin import format_hijri_date, from_hijri, to_hijri

hijri = to_hijri(date(2024, 3, 11))
assert (hijri.year, hijri.month, hijri.day) == (1445, 9, 1)
assert from_hijri(1445, 9, 1) == date(2024, 3, 11)
assert format_hijri_date(date(2024, 3, 11), language="ar-eg") == "١ رمضان ١٤٤٥ هـ"
assert format_hijri_date(date(2024, 3, 11), language="en", suffix=False) == "1 Ramadan 1445"
```

استخدم في القوالب المرشّح `hijri_date` بعد `{% load rtl_admin %}`:

```html
{% load rtl_admin %}
{{ book.published_on|hijri_date }}
{{ book.published_on|hijri_date:"short" }}
```

::: django_rtl_admin.hijri
    options:
      heading_level: 3
      members:
        - HijriDate
        - to_hijri
        - from_hijri


## تصدير CSV { #csv-export }

`export_as_csv(modeladmin, request, queryset)` هو إجراء إدارة في Django يصدّر
الصفوف المحددة إلى دفق CSV بترميز UTF-8 آمن للجداول الإلكترونية. يعمل مع أي
`ModelAdmin`؛ ولا يتطلب `BidiSafeAdminMixin`. راجع
[دليل مزيج الإدارة](admin-mixin.md#csv-export) لمعرفة كيفية إضافته إلى
`actions` وقائمة السلوك الكاملة.

تعيد `make_csv_export_action(fields=None, *, filename=None, digits="latn",
header="verbose", bom=True, delimiter=",")` الإجراء نفسه بخيارات مخصصة.
وترفع قيم `digits` أو `header` أو `delimiter` غير الصالحة `ValueError`.

```python
from django_rtl_admin import export_as_csv, make_csv_export_action

native_digits = make_csv_export_action(digits="native", delimiter=";")
```

الإجراءان مزخرفان بـ`admin.action(permissions=["view"])` وبتسمية مترجمة،
ويتحققان من صلاحية عرض النموذج (`PermissionDenied` خلاف ذلك)، ويبثّان الصفوف
عبر `StreamingHttpResponse` و`QuerySet.iterator()`، ويزيلان محارف التحكم في
الاتجاهين في Unicode، ويحوّلان الأرقام العربية-الهندية والفارسية باستخدام
`transliterate_digits()` (مع إبقاء خلايا التاريخ/التاريخ مع الوقت/الوقت بصيغة
ISO 8601 بأرقام ASCII)، ويكتبان التواريخ والتواريخ مع الأوقات بصيغة ISO 8601 في
المنطقة الزمنية الحالية، ويحلّان عمليات البحث المرتبطة `field__subfield` في كل
إصدارات Django المدعومة، ويضيفان فاصلة عليا بادئة إلى الخلايا التي تبدأ بـ`=`
أو `+` أو `-` أو `@` أو محرف الجدولة أو إرجاع السطر، ويرسلان اسم ملف
`Content-Disposition` مرمّزًا وفق RFC 6266 مع بادئة UTF-8 BOM افتراضيًا. ويحصل
كل إجراء من المصنع على `__name__` مميز مشتق من خياراته، لذا يمكن لعدة إجراءات
أن تشترك في `ModelAdmin` واحد.

::: django_rtl_admin.actions
    options:
      heading_level: 3
      members:
        - export_as_csv
        - make_csv_export_action


## أرقام الهاتف { #phone-numbers }

تُطبّع الدالة `normalize_phone(value, *, default_region="SA")` أرقام الهاتف
الإقليمية إلى صيغة E.164 (مثل `"+966501234567"`)، وترفع الدالة
`validate_phone(value, *, regions=None, mobile_only=False)` الاستثناء
`django.core.exceptions.ValidationError` برسالة خطأ مترجمة عندما يكون الرقم
غير صالح، أو من منطقة غير مسموح بها، أو خطًا أرضيًا عند ضبط `mobile_only=True`.

تحوّل الدالتان الأرقام العربية الهندية (`٠١٢٣٤٥٦٧٨٩`) والفارسية (`۰۱۲۳۴۵۶۷۸۹`)
باستخدام `transliterate_digits()`، وتزيلان محارف `Bidi_Control` في Unicode
والمسافات والشرطات والنقاط والأقواس، وتقبلان البادئتين الدوليتين `+` و`00`
والصفر المحلي البادئ `0`، وترفضان الحروف.

ودون أي اعتماد إضافي وقت التشغيل، تغطي القواعد المضمّنة المملكة العربية
السعودية (`SA`، `+966`)، والإمارات العربية المتحدة (`AE`، `+971`)، والكويت
(`KW`، `+965`)، وقطر (`QA`، `+974`)، والبحرين (`BH`، `+973`)، وسلطنة عُمان
(`OM`، `+968`)، ومصر (`EG`، `+20`)، والأردن (`JO`، `+962`). وإذا كانت حزمة
`phonenumbers` الاختيارية مثبّتة (`pip install phonenumbers`)، تفوّض إليها
الدوال `normalize_phone()` و`validate_phone()` و`format_phone_display()`
التحليل والتحقق وتنسيق العرض الدولي بعد تطبيق تحويل الأرقام وإزالة محارف
التحكم في الاتجاه ورفض الحروف بالطريقة نفسها.

```python
from django_rtl_admin import (
    PhoneNumberField,
    format_phone_display,
    normalize_phone,
    validate_phone,
)

assert normalize_phone("٠٥٠ ١٢٣-٤٥٦٧") == "+966501234567"
assert normalize_phone("۰۰۹۷۱ ۵۰ ۱۲۳ ۴۵۶۷") == "+971501234567"
assert normalize_phone("010 1234 5678", default_region="EG") == "+201012345678"
validate_phone("+962 79 123 4567", regions=("JO", "SA"), mobile_only=True)
display = format_phone_display("+966501234567")
```

ولنماذج Django ونماذج التعديل في `ModelAdmin`، يُنظّف الحقل `PhoneNumberField`
(المشتق من `forms.CharField`) الأرقام الصالحة إلى صيغة E.164، ويقبل المعاملات
`default_region` و`regions` و`mobile_only`، ويعرض حقل الإدخال النصي بالسمات
`dir="ltr"` و`inputmode="tel"` و`autocomplete="tel"`:

```python
from django import forms

from django_rtl_admin import PhoneNumberField


class CustomerForm(forms.Form):
    phone = PhoneNumberField(default_region="SA", mobile_only=True)
```

وفي القوالب، استخدم المرشح `phone_display` بعد `{% load rtl_admin %}` لعرض
أرقام E.164 مجمّعةً بحسب الدولة ومحاطةً بعزل من اليسار إلى اليمين (LTR):

```django
{% load rtl_admin %}
{{ customer.phone|phone_display }}
```

::: django_rtl_admin.phones
    options:
      heading_level: 3
      members:
        - normalize_phone
        - validate_phone
        - format_phone_display
        - PhoneNumberField
