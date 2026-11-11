"""MkDocs hooks: per-page SEO metadata, JSON-LD and ``llms-full.txt``.

Every page gets absolute ``en``/``ar``/``x-default`` alternates derived from
``site_url``; the two landing pages (``index.md`` and ``index.ar.md``) get
SoftwareSourceCode, SoftwareApplication and FAQPage structured data in their
own language, and every other page gets a BreadcrumbList.
"""

import json
import re
from pathlib import Path

try:
    from mkdocs.plugins import event_priority
except ImportError:  # pragma: no cover - older MkDocs releases
    def event_priority(_priority):
        return lambda function: function

SITE_ROOT = "https://django-rtl-admin.readthedocs.io/"
REPOSITORY = "https://github.com/MarwanMaher0/django-rtl-admin"
LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"

FAQS = {
    "en": [
        (
            "Does this replace Django's admin?",
            "No. It extends the stock django.contrib.admin templates and styles. Your "
            "ModelAdmin classes, URLs, permissions, database schema, and stored values "
            "stay in Django.",
        ),
        (
            "Which Django and Python versions are supported?",
            "Python 3.10 or newer and Django 4.2 or newer are supported on compatible "
            "Python and Django combinations. The project test matrix covers Django 4.2 "
            "through 6.1 and Python 3.10 through 3.14.",
        ),
        (
            "Is Arabic text isolated automatically everywhere?",
            "No. The stylesheet provides CSS isolation and plaintext direction rules. "
            "Unicode isolation of changelist values is opt-in through BidiSafeAdminMixin; "
            "custom output can use the template filters or Python helpers.",
        ),
        (
            "Do I need Babel?",
            "Babel is optional. Install django-rtl-admin[babel] for CLDR number, currency, "
            "date, and time patterns. Without it, the helpers use Django formatting plus "
            "digit transliteration, with simpler currency and percentage output.",
        ),
        (
            "Will installation reformat every number and date?",
            "No. Locale-aware formatting is explicit: call the Python helpers or template "
            "filters where you need them. The demo's formatted price column is a custom "
            "display method, not universal automatic conversion.",
        ),
        (
            "Can I use it with a custom admin theme?",
            "The integration is designed for Django's stock admin markup. A project-level "
            "base_site.html can extend django_rtl_admin/base_site.html and preserve parent "
            "blocks. Compatibility with third-party themes is not guaranteed.",
        ),
        (
            "Which RTL languages can I use?",
            "Direction handling follows Django's LANGUAGES_BIDI setting and supports regional "
            "fallback and EXTRA_RTL_LANGUAGES. The package ships Arabic, Kurdish Sorani, "
            "Hebrew, Persian, Uyghur, and Urdu catalogs; your project's LANGUAGES setting "
            "controls the switcher.",
        ),
        (
            "Does it change identifiers in the database?",
            "No. Isolation and formatting are presentation-time operations. Apply Unicode "
            "controls while rendering, not when saving business identifiers, because "
            "directional controls can survive copying and serialization.",
        ),
    ],
    "ar": [
        (
            "هل تستبدل الحزمة لوحة إدارة Django؟",
            "لا. توسّع الحزمة قوالب django.contrib.admin وأنماطها الافتراضية. تبقى فئات "
            "ModelAdmin والمسارات والصلاحيات ومخطط قاعدة البيانات والقيم المخزنة ضمن Django.",
        ),
        (
            "ما إصدارات Django وPython المدعومة؟",
            "تدعم الحزمة Python 3.10 أو أحدث وDjango 4.2 أو أحدث ضمن التوليفات المتوافقة. "
            "تغطي مصفوفة الاختبارات Django من 4.2 إلى 6.1 وPython من 3.10 إلى 3.14.",
        ),
        (
            "هل يُعزل النص العربي تلقائيًا في كل مكان؟",
            "لا. توفر ورقة الأنماط عزل CSS وقواعد اتجاه للنص العادي. أما عزل Unicode لقيم "
            "قوائم السجلات فيتطلب BidiSafeAdminMixin صراحةً، ويمكن للمخرجات المخصصة استخدام "
            "مرشحات القوالب أو دوال Python.",
        ),
        (
            "هل أحتاج إلى Babel؟",
            "Babel اختيارية. ثبّت django-rtl-admin[babel] للحصول على أنماط CLDR للأرقام "
            "والعملات والتواريخ والأوقات. بدونها تستخدم الأدوات تنسيق Django مع تحويل "
            "الأرقام، بمخرجات أبسط للعملة والنسبة المئوية.",
        ),
        (
            "هل يعيد التثبيت تنسيق كل رقم وتاريخ؟",
            "لا. التنسيق وفق اللغة صريح: استدعِ دوال Python أو مرشحات القوالب حيث تحتاجه. "
            "عمود السعر المنسق في العرض التجريبي دالة عرض مخصصة، وليس تحويلًا تلقائيًا شاملًا.",
        ),
        (
            "هل تعمل الحزمة مع سمة إدارة مخصصة؟",
            "صُمم التكامل لوسوم لوحة Django الافتراضية. يمكن لقالب base_site.html في مشروعك "
            "أن يرث django_rtl_admin/base_site.html مع الحفاظ على كتل القالب الأصلية. "
            "لا يُضمن التوافق مع السمات الخارجية.",
        ),
        (
            "ما لغات RTL التي يمكنني استخدامها؟",
            "يتبع تحديد الاتجاه بيانات لغات Django مع دعم الرموز الإقليمية "
            "وEXTRA_RTL_LANGUAGES. ترفق الحزمة كتالوجات العربية والعبرية والفارسية "
            "والأردية، ويحدد إعداد LANGUAGES في مشروعك خيارات المبدّل.",
        ),
        (
            "هل تغيّر الحزمة المعرّفات في قاعدة البيانات؟",
            "لا. العزل والتنسيق عمليتا عرض فقط. طبّق محارف اتجاه Unicode أثناء العرض لا عند "
            "حفظ المعرّفات، لأن هذه المحارف قد تبقى عند النسخ والتسلسل.",
        ),
    ],
}


def _site_root(config):
    root = str(config.site_url or SITE_ROOT)
    return root if root.endswith("/") else root + "/"


def _route(page, language):
    """Site-relative route of a page without any language prefix.

    MkDocs reports the homepage as ``"."``/``"./"``; everything else is a
    directory URL such as ``"installation/"``. mkdocs-static-i18n prefixes
    translated builds with the locale (``"ar/installation/"``), which is
    stripped so the same route can be re-prefixed for every alternate.
    """
    route = page.file.url.removeprefix("./")
    if language != DEFAULT_LANGUAGE:
        route = route.removeprefix(f"{language}/")
    if route in {"", ".", "./", "index.html"}:
        return ""
    return route


def _absolute(root, language, route):
    prefix = "" if language == DEFAULT_LANGUAGE else f"{language}/"
    return f"{root}{prefix}{route}"


def _root_relative(language, route):
    prefix = "" if language == DEFAULT_LANGUAGE else f"{language}/"
    return f"/{prefix}{route}"


def _is_landing(page):
    name = page.file.src_path.replace("\\", "/").rsplit("/", 1)[-1]
    return page.is_homepage or name in {"index.md", "index.ar.md"}


def _is_fallback(page, language):
    """True when a localized build reuses the default-language source.

    mkdocs-static-i18n copies untranslated pages into every locale. Those
    pages contain English text, so they must not inherit the RTL direction
    of the surrounding Arabic chrome.
    """
    if language == DEFAULT_LANGUAGE:
        return False
    return not page.file.src_path.replace("\\", "/").endswith(f".{language}.md")


def _has_translation(page, language):
    """True when a real ``.<language>.md`` translation exists for the page."""
    if language == DEFAULT_LANGUAGE:
        return True
    alternate = getattr(page.file, "alternates", {}).get(language)
    return bool(alternate and getattr(alternate, "locale", None) == language)


def _landing_json_ld(canonical, description, language):
    software = {
        "@type": "SoftwareSourceCode",
        "@id": f"{canonical}#source",
        "name": "django-rtl-admin",
        "description": description,
        "url": canonical,
        "codeRepository": REPOSITORY,
        "license": "https://opensource.org/licenses/MIT",
        "version": "0.1.0",
        "programmingLanguage": "Python",
        "runtimePlatform": ["Python 3.10+", "Django 4.2+"],
        "inLanguage": language,
    }
    application = {
        "@type": "SoftwareApplication",
        "@id": f"{canonical}#application",
        "name": "django-rtl-admin",
        "description": description,
        "url": canonical,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "OS independent",
        "isAccessibleForFree": True,
        "license": "https://opensource.org/licenses/MIT",
        "inLanguage": language,
    }
    faq = {
        "@type": "FAQPage",
        "@id": f"{canonical}#faq",
        "url": canonical,
        "inLanguage": language,
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in FAQS[language]
        ],
    }
    return {"@context": "https://schema.org", "@graph": [software, application, faq]}


def _breadcrumb_json_ld(canonical, home, title, language):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumbs",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "الرئيسية" if language == "ar" else "Home",
                "item": home,
            },
            {"@type": "ListItem", "position": 2, "name": title, "item": canonical},
        ],
    }


def on_page_context(context, page, config, **kwargs):
    language = config.theme["language"]
    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    title = str(page.meta.get("title") or page.title or "django-rtl-admin")
    description = str(page.meta.get("description") or "").strip()
    if not description:
        raise ValueError(f"Missing SEO description for {page.file.src_path}")

    root = _site_root(config)
    route = _route(page, language)
    landing = _is_landing(page)
    fallback = _is_fallback(page, language)
    has_ar = _has_translation(page, "ar")
    canonical = _absolute(root, language if not fallback else DEFAULT_LANGUAGE, route)
    page_language = DEFAULT_LANGUAGE if fallback else language
    title_only = title.split("|")[0].strip()
    seo_title = title if "django-rtl-admin" in title else f"{title} | django-rtl-admin"
    if fallback:
        seo_title = f"{title_only} (English) | django-rtl-admin"

    page.meta["seo_language"] = page_language
    page.meta["seo_direction"] = "rtl" if page_language == "ar" else "ltr"
    page.meta["seo_title"] = seo_title
    page.meta["seo_title_only"] = title_only
    page.meta["seo_canonical"] = canonical
    page.meta["seo_en_url"] = _absolute(root, "en", route)
    page.meta["seo_ar_url"] = _absolute(root, "ar", route)
    page.meta["seo_en_path"] = _root_relative("en", route)
    page.meta["seo_ar_path"] = _root_relative("ar", route)
    page.meta["seo_og_image"] = f"{root}assets/og-image.png"
    page.meta["seo_is_landing"] = landing
    page.meta["seo_fallback"] = fallback
    page.meta["seo_has_ar"] = has_ar
    page.meta["landing_faq"] = FAQS[page_language]

    if landing:
        structured = _landing_json_ld(canonical, description, page_language)
    else:
        home = _absolute(root, page_language, "")
        structured = _breadcrumb_json_ld(canonical, home, title_only, page_language)
    page.meta["seo_json_ld"] = json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c")
    return None


def _remove_sitemap_copies(config):
    """Remove stale per-directory sitemap copies from earlier builds.

    MkDocs writes a single ``sitemap.xml`` at the site root; the i18n plugin
    does not emit one per locale. Older builds of this project copied the
    sitemap next to every ``index.html``, so those stale copies are deleted
    here to keep only the root file. Note that MkDocs Material 9.7+ probes an
    absolute site-URL ``sitemap.xml`` for its language switcher and therefore
    logs CORS/network errors when the site is served from another host; the
    docs extra pins ``mkdocs-material<9.7`` to avoid that request entirely.
    """
    site_dir = Path(config.site_dir)
    for index in site_dir.rglob("index.html"):
        if index.parent != site_dir:
            stale = index.parent / "sitemap.xml"
            if stale.is_file():
                stale.unlink()


@event_priority(-100)
def on_post_build(config, **kwargs):
    _remove_sitemap_copies(config)
    docs_dir = Path(config.docs_dir)
    output = Path(config.site_dir) / "llms-full.txt"
    sections = [
        "# django-rtl-admin — full documentation",
        "",
        "django-rtl-admin extends Django's stock admin with logical-property RTL styling, "
        "opt-in Unicode bidi isolation, locale-aware formatting helpers, and a "
        "CSRF-protected language switcher. It supports Python 3.10+ and Django 4.2+ on "
        "compatible combinations. It does not replace the admin, change stored values, or "
        "automatically reformat every field.",
        "",
    ]
    for path in sorted(docs_dir.glob("*.md")):
        if path.name.endswith(".ar.md"):
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\A---\n.*?\n---\n+", "", text, flags=re.DOTALL)
        if path.name == "changelog.md":
            changelog = docs_dir.parent / "CHANGELOG.md"
            text = text.replace('--8<-- "CHANGELOG.md"', changelog.read_text(encoding="utf-8"))
        sections.extend([f"## Source: {path.name}", "", text.strip(), ""])
    output.write_text("\n".join(sections), encoding="utf-8")
