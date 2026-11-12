---
title: التثبيت | django-rtl-admin
description: ثبّت django-rtl-admin على Python 3.10 أو أحدث وDjango 4.2 أو أحدث، وسجّل التطبيق قبل لوحة الإدارة المضمّنة، وانشر الملفات الثابتة، وحافظ على كتل القوالب المخصصة.
---

# التثبيت { #installation }

## المتطلبات { #requirements }

- Python 3.10 أو أحدث.
- Django 4.2 أو أحدث، مع استخدام إصدار Python يدعمه إصدار Django المذكور.
- لوحة الإدارة الافتراضية `django.contrib.admin` في Django، واعتمادياتها المعتادة، وتقديم الملفات
  الثابتة. توسّع هذه الحزمة لوحة الإدارة المضمّنة؛ وليست سمة بديلة للوحة الإدارة
  ولا ترحيلًا لقاعدة البيانات.

تغطي مصفوفة الاختبارات التوليفات المدعومة من Python 3.10–3.14 وDjango
4.2 و5.0 و5.1 و5.2 و6.0 و6.1. لا يدعم كل إصدار من Django جميع إصدارات
Python.

## تثبيت الحزمة { #install-the-package }

```sh
python -m pip install django-rtl-admin
```

لتنسيق الأعداد والعملات والتواريخ والأوقات بالاستناد إلى CLDR، ثبّت Babel أيضًا:

```sh
python -m pip install "django-rtl-admin[babel]"
```

Babel اختياري. عند غيابه، يعتمد التنسيق على صيغ الإعدادات المحلية في Django
مع تحويل أشكال الأرقام؛ وتكون مخرجات العملات والنسب المئوية أبسط. راجع
[واجهة Python البرمجية](api.md#locale-aware-formatting) لمعرفة اختلافات التنسيق البديل.

## تسجيل التطبيق قبل لوحة الإدارة { #register-the-app-before-the-admin }

في ملف `settings.py` لمشروعك، أدرج `django_rtl_admin` **قبل**
`django.contrib.admin` في قائمة `INSTALLED_APPS` الحالية. احتفظ بتطبيقاتك الأخرى:

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

استخدم محمّل قوالب التطبيقات في Django ‏(`APP_DIRS=True` في إعداد DjangoTemplates
القياسي). يتيح ترتيب التطبيقات لقالب الحزمة `admin/base_site.html` تجاوز
القالب الافتراضي. وهو يحمّل ورقة أنماط الحزمة وبرنامج مبدّل اللغة النصي؛
ولا توجد خطوة بناء لملفات CSS أو JavaScript.

## الملفات الثابتة والنشر { #static-files-and-deployment }

تتضمن حزمة wheel القوالب وCSS وJavaScript وكتالوجات الترجمة المجمّعة.
استخدم عملية النشر المعتادة لمشروعك:

```sh
python manage.py collectstatic --noinput
python manage.py check
```

قدّم الملفات الثابتة المجمّعة بالطريقة المعتادة للوحة إدارة Django. لا تحتوي
الحزمة نفسها على نماذج أو ترحيلات. أما مشروع Django المنشأ حديثًا، فلا يزال
يحتاج إلى ترحيلات Django نفسها وحساب موظف أو مستخدم ذي صلاحيات كاملة.

تابع إلى [البدء السريع](quick-start.md) لضبط لغات الطلبات
ونقطة نهاية المبدّل. راجع [فحوصات النظام](system-checks.md) إذا أصدر الإعداد
تحذيرًا من `rtl_admin.W001` إلى `rtl_admin.W004`.

## تجاوزات القوالب والسمات القائمة { #existing-template-overrides-and-themes }

يأخذ ملف `templates/admin/base_site.html` على مستوى المشروع الأولوية على قوالب
التطبيقات. إذا كنت تدير تجاوزًا مخصصًا، فمدّد القالب الأساسي الصريح للحزمة
واحتفظ بكتل القالب الأب:

```django
{% extends "django_rtl_admin/base_site.html" %}

{% block title %}Library admin | {{ block.super }}{% endblock %}
```

تضيف الحزمة فئات لعنصر body في `bodyclass`، وتحمّل الموارد في `responsive`،
وتضع مبدّلات اللغة في `userlinks` وفي `branding` للمستخدمين غير المسجّلين. احتفظ
بـ `{{ block.super }}` عند تجاوز هذه الكتل للحفاظ على تلك الميزات.

كما تتجاوز الحزمة `admin/change_list_results.html` و
`admin/edit_inline/tabular.html` و`admin/widgets/split_datetime.html` لتوفير
أسماء ميسّرة لمربعات تحديد الإجراءات، والحقول المضمّنة وعناصر التحكم في الحذف،
ومدخلات التاريخ والوقت. يأخذ تجاوز أحد هذه القوالب على مستوى المشروع الأولوية،
وتُفقد التسميات الميسّرة الخاصة بذلك القالب ما لم تُدمج شيفرة ترميز الحزمة
في نسخة المشروع. ولا تتأثر تجاوزات الحزمة الأخرى ولا أنماطها.

قد تستخدم سمات لوحة الإدارة التابعة لجهات خارجية شيفرة ترميز أو وراثة قوالب مختلفة؛
ولا تضمن ورقة أنماط لوحة الإدارة الافتراضية التوافق معها.
