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

## تصفية عناوين الكتب بحسب الحرف الأول

استورد `arabic_initial_filter` من `django_rtl_admin` واضبط
`list_filter = (arabic_initial_filter("title_ar"),)` في فئة `ModelAdmin`.
عند اختيار `ا` تظهر معًا العناوين التي تبدأ بـ`أ` أو `إ` أو `آ`، ولا يحتاج
المرشّح إلى مزيج. راجع [التصفية بحسب الحرف الأول](https://marwanmaher0.github.io/django-rtl-admin/ar/admin-mixin/#filter-by-arabic-initial)
لمعرفة خيارات الشريط الجانبي، و[مرجع `ArabicInitialListFilter`](https://marwanmaher0.github.io/django-rtl-admin/ar/api/#arabic-initial-list-filter)
لتعريف فئة فرعية وضبط خياراتها.

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

## الإعدادات

تُضبط الحزمة عبر القاموس `RTL_ADMIN` في إعدادات Django، ويمكن تعطيل كل ميزة على حدة. راجع [مرجع الإعدادات الكامل](https://marwanmaher0.github.io/django-rtl-admin/ar/configuration/) لجميع الخيارات.

| المفتاح | القيمة الافتراضية | التأثير |
| --- | --- | --- |
| `ENABLE_CSS` | `True` | ربط ورقة الأنماط الداعمة للاتجاهين داخل وسم `<head>` في لوحة الإدارة. |
| `PRINT_STYLES` | `True` | ربط ورقة أنماط الطباعة (`django_rtl_admin/css/print.css`) بالسمة `media="print"` بعد ورقة الأنماط الرئيسة لطباعة نظيفة بالاتجاهين RTL وLTR. يجب أن تكون القيمة منطقية. |
| `TRANSLITERATE_SLUGS` | `True` | ملء معرّفات الروابط الفارغة تلقائيًا من النص العربي أو الفارسي في نماذج الإضافة والصفوف المضمّنة الجديدة. يجب أن تكون القيمة منطقية. |
| `LANGUAGE_SWITCHER` | `True` | عرض مبدّل اللغة في ترويسة لوحة الإدارة وصفحة تسجيل الدخول. |

## تصدير قائمة السجلات إلى CSV يفتحه Excel بشكل صحيح

`export_as_csv` إجراء إدارة يعمل مع أي `ModelAdmin`، ولا يتطلب المزيج. يصدّر
الصفوف المحددة بترتيب `list_display` إلى ملف UTF-8 مع بادئة BOM، ويزيل محارف
التحكم في الاتجاهين، ويحوّل الأرقام العربية-الهندية والفارسية إلى ASCII،
ويكتب التواريخ بصيغة ISO 8601 في المنطقة الزمنية الحالية، ويُضيف فاصلة عليا
بادئة إلى الخلايا التي تبدأ كصيغ جدولية، ويبث الصفوف فلا تُحمَّل التصديرات
الكبيرة إلى الذاكرة دفعة واحدة:

```python
from django.contrib import admin

from django_rtl_admin import export_as_csv, make_csv_export_action


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title_ar", "isbn", "price")
    actions = (export_as_csv,)
```

استخدم `make_csv_export_action(fields=None, *, filename=None, digits="latn",
header="verbose", bom=True, delimiter=",")` لتخصيص الأعمدة أو اسم الملف
(تُرمَّز الأسماء العربية وفق RFC 6266) أو الأرقام المحلية أو رؤوس الأعمدة
أو الفاصل. صلاحية العرض مطلوبة. انظر
[تصدير CSV](https://marwanmaher0.github.io/django-rtl-admin/ar/admin-mixin/#csv-export).

## تطبيع أرقام الهاتف والتحقق منها

يدخل مستخدمو لوحة الإدارة في دول الخليج ومصر والأردن أرقام الهاتف بأرقام
عربية هندية أو فارسية مع مسافات وشرطات ونقاط وأقواس وبادئات `00` أو `+`
وأصفار محلية ومحارف تحكم ثنائية الاتجاه. تتضمن الحزمة قواعد مضمّنة للسعودية
(`SA`) والإمارات (`AE`) والكويت (`KW`) وقطر (`QA`) والبحرين (`BH`) وعُمان
(`OM`) ومصر (`EG`) والأردن (`JO`) دون أي اعتماد إضافي وقت التشغيل، وتستخدم
حزمة `phonenumbers` الاختيارية تلقائيًا عند تثبيتها:

```python
from django import forms

from django_rtl_admin import (
    PhoneNumberField,
    format_phone_display,
    normalize_phone,
    validate_phone,
)

assert normalize_phone("٠٥٠ ١٢٣-٤٥٦٧") == "+966501234567"
assert normalize_phone("00971 50 123 4567") == "+971501234567"
validate_phone("+20 10 1234 5678", regions=("EG", "SA"), mobile_only=True)


class CustomerForm(forms.Form):
    phone = PhoneNumberField(default_region="SA")
```

ينظّف الحقل `PhoneNumberField` المدخلات الصالحة إلى صيغة E.164، ويعرض حقل
الإدخال بالسمات `dir="ltr"` و`inputmode="tel"` و`autocomplete="tel"`. وفي
القوالب، يجمّع المرشح `{{ customer.phone|phone_display }}` أرقام E.164 بحسب
الدولة ويحيطها بعزل LTR لتظهر صحيحةً داخل النص العربي. راجع
[أرقام الهاتف](https://marwanmaher0.github.io/django-rtl-admin/ar/api/#phone-numbers).

## الأعداد الترتيبية العربية

لا توفّر Python ولا Django ألفاظًا للأعداد الترتيبية العربية، فتظهر أرقام
الفواتير والمراتب والخطوات والطوابق أرقامًا مجرّدة أو بالصيغة `1st`. تكتب
`ordinal_words()` العدد الترتيبي بالعربية الفصحى مطابقًا للاسم الذي يصفه في
التذكير والتأنيث والتعريف والتنكير، وتكتب `ordinal_short()` الصيغة المختصرة
التي ترافق الأرقام في كل لغة:

```python
from django.contrib import admin

from django_rtl_admin import ordinal_display, ordinal_short, ordinal_words

assert ordinal_words(3) == "الثالث"
assert ordinal_words(3, gender="feminine") == "الثالثة"
assert ordinal_words(2, definite=False) == "ثانٍ"
assert ordinal_words(11, gender="f") == "الحادية عشرة"
assert ordinal_words(21) == "الحادي والعشرون"
assert ordinal_words(125) == "المئة والخامس والعشرون"

assert ordinal_short(3, language="en") == "3rd"
assert ordinal_short(25, language="ar") == "الـ25"


class FloorAdmin(admin.ModelAdmin):
    list_display = ("building", ordinal_display("number", gender="masculine"))
```

الأعداد من 1 إلى 99 هي الأعداد الترتيبية نفسها، ومنها الصيغتان الخاصتان
بالعددين 1 و2 والأعداد المركبة من 11 إلى 19 وألفاظ العقود. وليس للمئة والألف
صيغة ترتيبية في العربية، فيُكتب ما زاد على 100 بالعدد الأصلي لمئاته وما فوقها
ثم الواو والعدد الترتيبي لخانتيه الأخيرتين، حتى 999,999,999,999. تُكتب الألفاظ
في حالة الرفع. والعلامة المختصرة في العربية هي أداة التعريف متبوعةً بتطويل،
أي `الـ`، قبل الأرقام. وتلتزم الأرقام بالإعداد الموجود
`LOCALIZE_CHANGELIST_DIGITS`: تبقى لاتينية ما دام معطّلًا، وتتبع أرقام اللغة
والإعداد `NUMERALS` عند تفعيله (`الـ٢٥` في `ar-eg`). ويرفع الصفر والأعداد
السالبة والقيم من نوع `bool` أو `float` والسلاسل النصية التي لا تمثل عددًا
صحيحًا `ValueError`. تعيد `ordinal_display()` دالة تصلح لـ`list_display` وتُبقي
العمود قابلًا للفرز عبر `admin_order_field`. وفي القوالب، استخدم
`{{ floor.number|ordinal_ar }}` و`{{ invoice.sequence|ordinal_ar:"f,indef" }}`
و`{{ ranking.position|ordinal_short }}`. راجع
[الأعداد الترتيبية العربية](https://marwanmaher0.github.io/django-rtl-admin/ar/api/#arabic-ordinals).
