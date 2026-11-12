---
title: العرض التجريبي المباشر والنشر | django-rtl-admin
description: شغّل المشروع التجريبي ثنائي اللغة بالعربية والإنجليزية محليًا أو في Docker، وانشره على Fly.io أو Render بإعدادات تعتمد على البيئة، وأعد ضبط بيانات العرض التجريبي المخصص للقراءة فقط وفق جدول زمني.
---

# العرض التجريبي المباشر والنشر { #live-demo-and-deployment }

يتضمن المستودع مشروعًا تجريبيًا كاملًا ثنائي اللغة ضمن `example/`، مع حقول
بالعربية والإنجليزية (`Publisher` و`Book` و`Chapter`)، وضبط `BidiSafeAdminMixin`
على قوائم السجلات، وتنسيق العملات حسب الإعدادات المحلية (`EGP`)، وتفعيل
مبدّل اللغة في الترويسة وصفحة تسجيل الدخول للإنجليزية (`en`) والعربية (`ar`)
والعربية — مصر (`ar-eg`) والعبرية (`he`).

---

## تشغيل العرض التجريبي محليًا { #running-the-demo-locally }

من جذر المستودع (لا يلزم ضبط متغيرات البيئة للتطوير المحلي):

```sh
python -m pip install -e ".[babel,demo]"
cd example
python manage.py reset_demo
python manage.py runserver
```

افتح `http://127.0.0.1:8000/admin/` وسجّل الدخول باستخدام:

- **اسم المستخدم:** `demo`
- **كلمة المرور:** `demo12345`

### مستخدم العرض التجريبي { #the-demo-user }

يوفّر مشروع `example/` أمرَي إدارة لتعبئة البيانات وضبط [مستخدم العرض التجريبي](#the-demo-user):

- يشغّل `python manage.py reset_demo` (الاسم البديل: `resetdemo`) الترحيلات، ويفرّغ
  قاعدة البيانات، ويعيد تحميل بيانات الناشرين والكتب والفصول النموذجية ثنائية اللغة،
  ويضبط `demo` بوصفه **حساب موظف للقراءة فقط** (`is_staff=True`،
  `is_superuser=False`) ضمن مجموعة `Demo Read-Only` التي لا تتضمن سوى
  صلاحيات `view_*` لنماذج العرض التجريبي (`library.Publisher` و`library.Book`
  و`library.Chapter`). لا يستطيع المستخدم `demo` عرض مستخدمي `auth` أو مجموعاته،
  ولا إضافة السجلات أو تعديلها أو حذفها. كما يُخفى رابط **تغيير كلمة المرور**
  عنه في ترويسة لوحة الإدارة، ويُمنع من الوصول إلى `/admin/password_change/` (`403 Forbidden`)
  كي لا يتمكن الزوار من تغيير بيانات الدخول المشتركة للعرض التجريبي (يرى الموظفون الآخرون
  الرابط، ويظل بإمكانهم تغيير كلمات المرور الخاصة بهم).
- ينشئ `python manage.py demodata` حساب `demo` أو يحدّثه بوصفه مستخدمًا ذا صلاحيات كاملة
  (مرّر `--read-only` لإنشاء حساب الموظف المخصص للعرض فقط بدلًا من ذلك)، ويُدرج
  السجلات النموذجية أو يحدّثها دون تفريغ الجداول القائمة.

---

## متغيرات البيئة { #environment-variables }

يقرأ `example/config/settings.py` إعداداته من متغيرات البيئة.
تكون القيمة الافتراضية لـ `DEBUG` هي `False` ما لم يُفعّل صراحةً، ولا يفعّل
`LOCAL_DEV` من تلقاء نفسه مطلقًا. تكون القيمة الافتراضية لـ `DJANGO_ENV` هي `production` بغضّ النظر عن
`DEBUG`؛ ويضبط `example/manage.py` القيمة `DJANGO_ENV=development` افتراضيًا، فتكون
`LOCAL_DEV=True` للأوامر المحلية (`python manage.py runserver`) عندما لا توجد متغيرات
بيئة خاصة بالنشر، مما يتيح التشغيل المحلي دون أي متغيرات بيئة
وتقديم الملفات الثابتة للوحة الإدارة تلقائيًا. خارج التطوير
المحلي (`LOCAL_DEV=False` — بما في ذلك عندما تكون `DJANGO_ENV=production`، أو عند ضبط أي
متغير بيئة خاص بالنشر مثل `RENDER` أو `FLY_APP_NAME` أو `PORT`
أو `DATABASE_URL` أو `ALLOWED_HOSTS` أو `CSRF_TRUSTED_ORIGINS`، أو كلما
حمّل أي خادم WSGI/ASGI أو `get_wsgi_application()` / `get_asgi_application()`
الوحدة `config.settings` دون `manage.py`)، يتطلب `example/config/settings.py`
ضبط `SECRET_KEY` على قيمة سرية قوية وغير افتراضية (وألّا تكون
`django-insecure-*` مطلقًا)، وإلا يرفع `ImproperlyConfigured` عند بدء التشغيل؛ كما أن
`example/config/urls.py` لا يربط مطلقًا دالة العرض الاحتياطية غير الآمنة في Django
لتقديم الملفات الثابتة:

| المتغير | القيمة الافتراضية | الوصف |
| --- | --- | --- |
| `SECRET_KEY` | قيمة احتياطية للتطوير المحلي *(فقط عندما تكون `LOCAL_DEV=True`)* | مفتاح التوقيع التشفيري في Django. مطلوب كلما كانت `LOCAL_DEV=False` (في الإنتاج وجميع خوادم WSGI/ASGI، بغضّ النظر عن `DEBUG`)؛ يؤدي غياب المفتاح أو استخدام مفتاح افتراضي أو من النمط `django-insecure-*` إلى رفع `ImproperlyConfigured` في `config/settings.py` عند بدء التشغيل. |
| `DJANGO_ENV` | `production` (`development` عبر `manage.py`) | وضع البيئة الصريح (`development` أو `dev` أو `local` أو `production`). تكون `LOCAL_DEV` بقيمة `True` فقط عندما تكون `DJANGO_ENV` إحدى القيم `development`/`dev`/`local` ولا تكون أي متغيرات بيئة خاصة بالنشر مضبوطة. |
| `DEBUG` | `False` | معطّل ما لم يُضبط على `1` أو `true` أو `yes` أو `on`. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1],.localhost` | أسماء المضيفين المسموح لهم بتقديم العرض التجريبي، مفصولة بفواصل. |
| `CSRF_TRUSTED_ORIGINS` | *(فارغة)* | أصول `https://` موثوقة لطلبات POST المحمية من CSRF، مفصولة بفواصل (بما في ذلك `/i18n/setlang/` و`/admin/login/`). |
| `DATABASE_URL` | `sqlite:///<BASE_DIR>/db.sqlite3` | عنوان اتصال قاعدة البيانات (`sqlite:////data/db.sqlite3` أو `postgres://user:pass@host:5432/dbname`؛ وتتضمن `example/requirements.txt` الحزمة `psycopg[binary]`). |
| `PORT` | `8000` | منفذ الاستماع الذي يستخدمه Gunicorn داخل الحاوية. |
| `WEB_CONCURRENCY` | `2` | عدد عمليات Gunicorn العاملة. |
| `RESET_DEMO_ON_STARTUP` | `0` (`1` في `fly.toml`) | اضبطه على `1` لفرض تفريغ كامل باستخدام `reset_demo` عند كل إقلاع للحاوية. |
| `RESET_DEMO_INTERVAL_SECONDS` | `0` (`3600` في `fly.toml`) | الفاصل الزمني بالثواني الذي يشغّل عنده `entrypoint.sh` الأمر `python manage.py reset_demo` في الخلفية على قاعدة البيانات المحددة في `DATABASE_URL` النشط لخدمة الويب. |

تُجمّع الملفات الثابتة عند بناء الصورة في `STATIC_ROOT`، ويقدّمها
[WhiteNoise](https://whitenoise.readthedocs.io/) باستخدام
`CompressedStaticFilesStorage`.

---

## التشغيل باستخدام Docker { #running-with-docker }

ابنِ الحاوية وشغّلها من جذر المستودع:

```sh
docker build -t django-rtl-admin-demo .
docker run --rm -p 8000:8000 \
  -e SECRET_KEY="replace-with-a-random-secret" \
  -e ALLOWED_HOSTS="localhost,127.0.0.1" \
  django-rtl-admin-demo
```

يستخدم `Dockerfile` الصورة `python:3.12-slim`، ويعمل تحت حساب مستخدم غير جذري (`appuser`،
بمعرّف UID قيمته `10001`)، ويشغّل `collectstatic` و`reset_demo` أثناء بناء الصورة،
ويتيح `/healthz/` لفحوصات سلامة الحاوية، ويبدأ Gunicorn عبر
`entrypoint.sh`.

تحقّق من نقاط نهاية الحاوية من نافذة طرفية أخرى:

```sh
# Health check
curl -fsS http://127.0.0.1:8000/healthz/

# Admin login page
curl -fsSI http://127.0.0.1:8000/admin/login/
```

---

## النشر على Fly.io { #deploying-to-flyio }

يتوفر ملف `fly.toml` جاهز للاستخدام في جذر المستودع (مع نسخة مطابقة في
`example/fly.toml`):

```sh
# 1. Create the Fly app (do not deploy yet)
fly launch --copy-config --no-deploy

# 2. Create a persistent volume for the SQLite database
fly volumes create demo_data --region fra --size 1

# 3. Set a production secret key
fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"

# 4. Deploy
fly deploy
```

يربط `fly.toml` وحدة التخزين `demo_data` بالمسار `/data`، ويضبط
`DATABASE_URL="sqlite:////data/db.sqlite3"`، ويهيّئ فحص سلامة عبر HTTP
باستخدام `GET /healthz/`.

!!! note "الإيقاف التلقائي لآلات Fly وإعادة الضبط كل ساعة"
    نظرًا إلى أن `fly.toml` يفعّل `auto_stop_machines = "stop"` مع
    `min_machines_running = 0`، فإن المؤقّت الخلفي `RESET_DEMO_INTERVAL_SECONDS = "3600"`
    داخل الحاوية لا يتقدم إلا أثناء تشغيل آلة Fly، ويُفقد
    كلما توقفت الآلة تلقائيًا بسبب الخمول. لضمان حالة نظيفة
    بعد توقف بسبب الخمول، يضبط `fly.toml` أيضًا `RESET_DEMO_ON_STARTUP = "1"`، فيشغّل
    `entrypoint.sh` الأمر `python manage.py reset_demo` كلما بدأت الآلة
    تلقائيًا عند الطلب التالي. إذا كنت تحتاج إلى إعادة ضبط مستمرة كل ساعة
    وفق الوقت الفعلي حتى أثناء الخمول، فاضبط `auto_stop_machines = "off"` و
    `min_machines_running = 1` في `fly.toml`.

---

## النشر على Render { #deploying-to-render }

يتوفر مخطط `render.yaml` في جذر المستودع، ويعرّف قاعدة بيانات
PostgreSQL مشتركة (`django-rtl-admin-demo-db`، `plan: free`، تدعمها
`psycopg[binary]` في `example/requirements.txt`)، وخدمة ويب تعمل في Docker
(`django-rtl-admin-demo`، `plan: free`)، ومهمة cron واحدة تعمل كل ساعة
(`django-rtl-admin-demo-reset`، `schedule: "0 * * * *"`، `plan: starter`)،
تتصل بقاعدة البيانات المشتركة نفسها المحددة في `DATABASE_URL` وتشغّل `python manage.py reset_demo`.

!!! note "متطلب خطة مهام cron في Render"
    لا توفّر مهام cron في Render ‏(`type: cron`) خطة `free`؛ وتُعدّ `plan: starter`
    أدنى خطة صالحة لمهام cron في Render ضمن `render.yaml`. إذا أردت النشر على
    Render باستخدام موارد الفئة المجانية فقط، فاحذف خدمة cron المسماة `django-rtl-admin-demo-reset`
    من `render.yaml` وأضف `RESET_DEMO_ON_STARTUP="1"` و
    `RESET_DEMO_INTERVAL_SECONDS="3600"` إلى `envVars` الخاصة بخدمة الويب.

للنشر على Render:

1. ادفع المستودع إلى GitHub.
2. في لوحة تحكم Render، اختر **جديد → مخطط** وحدّد المستودع.
3. يقرأ Render ملف `render.yaml`، وينشئ `django-rtl-admin-demo-db`، ويربط
   `connectionString` الخاص بها بـ `DATABASE_URL` لكلٍّ من خدمة الويب ومهمة
   cron، ويولّد `SECRET_KEY`، ويضبط `/healthz/` بوصفه مسار فحص
   السلامة.

---

## جدولة عمليات إعادة ضبط العرض التجريبي الدورية { #scheduling-periodic-demo-resets }

على الرغم من أن [مستخدم العرض التجريبي](#the-demo-user) مقيّد بصلاحيات `view_*`
لنماذج `library` وممنوع من تغيير كلمة مروره، فإن تشغيل
`python manage.py reset_demo` **كل ساعة وفق جدول زمني** (`0 * * * *` / كل
`3600` ثانية) يضمن بقاء حالة قاعدة البيانات وبيانات دخول المستخدم
وصلاحياته على حالتها الأصلية النظيفة. ومن الضروري أن تستهدف مهمة إعادة الضبط
قاعدة البيانات نفسها (`DATABASE_URL`) التي تستخدمها خدمة الويب فعليًا:

### الخيار 1: مؤقّت الحاوية المضمّن (`RESET_DEMO_INTERVAL_SECONDS`) { #option-1-built-in-container-timer-reset_demo_interval_seconds }

عند ضبط `RESET_DEMO_INTERVAL_SECONDS` على عدد صحيح موجب (مضبوط على
`3600` — مرة كل ساعة — في `fly.toml`)، يُطلق `entrypoint.sh` حلقة
خلفية داخل حاوية الويب العاملة، تنفّذ
`python manage.py reset_demo` على قاعدة البيانات المحددة في `DATABASE_URL` النشط للحاوية
(مثل وحدة التخزين المربوطة `/data/db.sqlite3` على Fly.io). لاحظ أنه على Fly.io
عند استخدام `auto_stop_machines = "stop"`، يتوقف هذا المؤقّت داخل العملية عندما تتوقف الآلة
تلقائيًا؛ ويقرنه `fly.toml` بـ `RESET_DEMO_ON_STARTUP = "1"` لتُعاد
قاعدة البيانات إلى حالتها الأصلية عند استئناف تشغيل الآلة.

### الخيار 2: cron النظام أو مؤقّت مضيف الحاوية (كل ساعة: `0 * * * *`) { #option-2-system-cron-or-container-host-timer-hourly-0 }

شغّل `reset_demo` داخل حاوية الويب العاملة كي يعيد ضبط قاعدة بيانات
SQLite أو PostgreSQL النشطة في الحاوية:

```cron
0 * * * * docker exec django-rtl-admin-demo python manage.py reset_demo >/dev/null 2>&1
```

### الخيار 3: مهمة cron في Render مع قاعدة بيانات PostgreSQL مشتركة (`0 * * * *`) { #option-3-render-cron-job-with-shared-postgresql-database-0 }

ينشئ `render.yaml` قاعدة بيانات PostgreSQL مشتركة على Render
(`django-rtl-admin-demo-db`)، ويمرّر `connectionString` الخاص بها بوصفه `DATABASE_URL`
إلى كلٍّ من خدمة الويب `django-rtl-admin-demo` وخدمة cron الوحيدة
`django-rtl-admin-demo-reset` ‏(`schedule: "0 * * * *"`)، مما يضمن
تنفيذ إعادة ضبط واحدة بالضبط كل ساعة على قاعدة البيانات التي تستخدمها خدمة الويب.
