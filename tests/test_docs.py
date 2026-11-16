import json
import re
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

import django_rtl_admin

DOCS = Path(__file__).resolve().parents[1] / "docs"
SEO = runpy.run_path(str(DOCS / "hooks" / "seo.py"))
TRANSLATED = (
    "installation",
    "deployment",
    "configuration",
    "template-tags",
    "admin-mixin",
    "system-checks",
    "translations",
    "rtl-defects",
)


def test_arabic_documentation_matches_english_structure():
    for name in TRANSLATED:
        assert (DOCS / f"{name}.ar.md").is_file()
    SEO["_check_translations"](DOCS)


@pytest.mark.parametrize(
    ("translated", "error"),
    [
        ("# عنوان\n\n```python\nx = 2\n```\n", "Code blocks differ"),
        ("# عنوان\n\n## إضافي\n\n```python\nx = 1\n```\n", "Heading count or levels differ"),
        ("## عنوان\n\n```python\nx = 1\n```\n", "Heading count or levels differ"),
        ("# عنوان { #wrong }\n\n```python\nx = 1\n```\n", "Heading anchors differ"),
        ("# عنوان\n\n```python\nx = 1\n```\n", "Heading anchors differ"),
    ],
)
def test_docs_build_rejects_translation_drift(tmp_path, translated, error):
    (tmp_path / "topic.md").write_text("# Title\n\n```python\nx = 1\n```\n", encoding="utf-8")
    (tmp_path / "topic.ar.md").write_text(translated, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))


def test_docs_build_checks_nested_translations(tmp_path):
    nested = tmp_path / "guide"
    nested.mkdir()
    (nested / "topic.md").write_text("# Title\n", encoding="utf-8")
    (nested / "topic.ar.md").write_text("# عنوان\n## إضافي\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Heading count or levels differ"):
        SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))


@pytest.mark.parametrize("name", ["index", "quick-start", *TRANSLATED, "guide/topic"])
def test_docs_build_requires_arabic_translations(tmp_path, name):
    english = tmp_path / f"{name}.md"
    english.parent.mkdir(parents=True, exist_ok=True)
    english.write_text("# Title\n", encoding="utf-8")
    translated = english.with_suffix(".ar.md")
    translated.write_text("# عنوان { #title }\n", encoding="utf-8")
    SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))
    translated.unlink()
    with pytest.raises(ValueError, match="Missing Arabic translation"):
        SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))


def test_docs_build_allows_only_the_english_reference_fallbacks(tmp_path):
    for name in ("api", "changelog"):
        (tmp_path / f"{name}.md").write_text("# Title\n", encoding="utf-8")
    SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))
    nested = tmp_path / "guide"
    nested.mkdir()
    (nested / "api.md").write_text("# Title\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing Arabic translation"):
        SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))


def test_docs_build_requires_an_english_source(tmp_path):
    (tmp_path / "topic.ar.md").write_text("# عنوان\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"Missing English source for topic\.ar\.md"):
        SEO["_check_translations"](tmp_path)


def test_docs_build_rejects_unclosed_code_fences():
    with pytest.raises(ValueError, match="Unclosed code fence"):
        SEO["_translation_structure"]("# Title\n```python\nx = 1\n")


def test_heading_markers_inside_code_are_not_counted():
    blocks, headings, anchors = SEO["_translation_structure"](
        "---\ntitle: Example\n---\n# Title\n~~~text\n## Not a heading\n~~~\n"
    )
    assert blocks == ["~~~text\n## Not a heading\n~~~\n"]
    assert headings == [1]
    assert anchors == ["title"]


@pytest.mark.parametrize(
    ("source", "anchors"),
    [
        ("# Title\n## Title\n## Title\n", ["title", "title_1", "title_2"]),
        ("## `name` and [link](topic.md)\n", ["name-and-link"]),
        ("# Édit &amp; <em>format</em> ###\n", ["edit-format"]),
        ("# عنوان { #english-anchor }\n", ["english-anchor"]),
        ('<h2 id="custom">Title</h2>\n', ["custom"]),
    ],
)
def test_heading_anchor_extraction(source, anchors):
    assert SEO["_translation_structure"](source)[2] == anchors


def test_quick_start_uses_the_english_heading_anchors():
    expected = [
        "quick-start",
        "1-enable-request-language-selection",
        "language-endpoint",
        "3-check-the-interface",
        "4-protect-changelist-values",
        "5-format-custom-output",
    ]
    for name in ("quick-start.md", "quick-start.ar.md"):
        assert (
            SEO["_translation_structure"]((DOCS / name).read_text(encoding="utf-8"))[2] == expected
        )


def test_docs_build_preserves_explicit_and_duplicate_anchors(tmp_path):
    (tmp_path / "topic.md").write_text(
        "# Title { #custom }\n## Repeated\n## Repeated\n", encoding="utf-8"
    )
    translated = tmp_path / "topic.ar.md"
    translated.write_text(
        "# عنوان { #custom }\n## مكرر { #repeated }\n## مكرر { #repeated_1 }\n", encoding="utf-8"
    )
    SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))
    translated.write_text(
        "# عنوان { #custom }\n## مكرر { #repeated_1 }\n## مكرر { #repeated }\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Heading anchors differ"):
        SEO["on_pre_build"](SimpleNamespace(docs_dir=tmp_path))


@pytest.mark.parametrize("name", TRANSLATED)
@pytest.mark.parametrize("language", ["en", "ar"])
def test_translated_docs_have_localized_seo_and_hreflang(name, language):
    root = "https://marwanmaher0.github.io/django-rtl-admin/"
    page = SimpleNamespace(
        file=SimpleNamespace(
            src_path=f"{name}.ar.md" if language == "ar" else f"{name}.md",
            url=f"ar/{name}/" if language == "ar" else f"{name}/",
            alternates={"ar": SimpleNamespace(locale="ar")},
        ),
        is_homepage=False,
        title="عنوان" if language == "ar" else "Title",
        meta={"description": "وصف" if language == "ar" else "Description"},
    )
    SEO["on_page_context"]({}, page, SimpleNamespace(theme={"language": language}, site_url=root))
    assert not page.meta["seo_fallback"]
    assert page.meta["seo_has_ar"]
    assert page.meta["seo_language"] == language
    assert page.meta["seo_direction"] == ("rtl" if language == "ar" else "ltr")
    assert page.meta["seo_en_url"] == f"{root}{name}/"
    assert page.meta["seo_ar_url"] == f"{root}ar/{name}/"
    assert page.meta["seo_sitemap"] == f"{root}sitemap.xml"
    assert page.meta["seo_canonical"] == page.meta[f"seo_{language}_url"]
    assert "(English)" not in page.meta["seo_title"]


def test_landing_seo_uses_github_pages_root_and_package_version():
    assert SEO["SITE_ROOT"] == "https://marwanmaher0.github.io/django-rtl-admin/"
    page = SimpleNamespace(
        file=SimpleNamespace(
            src_path="index.md",
            url="",
            alternates={"ar": SimpleNamespace(locale="ar")},
        ),
        is_homepage=True,
        title="django-rtl-admin",
        meta={"description": "Description"},
    )
    SEO["on_page_context"]({}, page, SimpleNamespace(theme={"language": "en"}, site_url=None))
    structured = json.loads(page.meta["seo_json_ld"])
    assert structured["@graph"][0]["version"] == django_rtl_admin.__version__
    assert page.meta["seo_canonical"] == "https://marwanmaher0.github.io/django-rtl-admin/"
    assert page.meta["seo_sitemap"] == "https://marwanmaher0.github.io/django-rtl-admin/sitemap.xml"


@pytest.mark.parametrize("name", ["api", "changelog"])
def test_untranslated_reference_pages_keep_english_fallback(name):
    page = SimpleNamespace(file=SimpleNamespace(src_path=f"{name}.md"))
    assert SEO["_is_fallback"](page, "ar")
    assert not (DOCS / f"{name}.ar.md").exists()


def test_every_seo_value_set_by_the_hook_is_read_by_a_template():
    hook = (DOCS / "hooks" / "seo.py").read_text(encoding="utf-8")
    templates = "".join(
        path.read_text(encoding="utf-8") for path in (DOCS / "overrides").rglob("*.html")
    )
    keys = set(re.findall(r'page\.meta\["(\w+)"\] = ', hook))
    assert "seo_sitemap" in keys
    unused = sorted(key for key in keys if not re.search(rf"page\.meta\.{key}\b", templates))
    assert not unused


def test_the_sitemap_is_linked_without_a_robots_file():
    assert not (DOCS / "robots.txt").exists()
    assert (DOCS / "overrides" / "sitemap.xml").is_file()
    partial = (DOCS / "overrides" / "partials" / "seo.html").read_text(encoding="utf-8")
    assert '<link rel="sitemap" type="application/xml"' in partial
    assert 'href="{{ page.meta.seo_sitemap }}"' in partial
    for template in ("main.html", "home.html"):
        assert '{% include "partials/seo.html" %}' in (DOCS / "overrides" / template).read_text(
            encoding="utf-8"
        )
    llms = (DOCS / "llms.txt").read_text(encoding="utf-8")
    assert f"{SEO['SITE_ROOT']}sitemap.xml" in llms


FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")


def _prose_paragraphs(text):
    paragraphs, lines, fence = [], [], None
    for line in [*text.splitlines(), ""]:
        marker = FENCE.match(line)
        if fence is not None:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        elif line.strip():
            lines.append(line)
            continue
        if lines:
            paragraphs.append("\n".join(lines))
            lines = []
    return paragraphs


def _collectstatic_paragraphs(text):
    return [paragraph for paragraph in _prose_paragraphs(text) if "collectstatic" in paragraph]


@pytest.mark.parametrize(
    "path",
    [DOCS.parent / "README.md", DOCS / "installation.md", DOCS / "installation.ar.md"],
    ids=lambda path: path.name,
)
def test_collectstatic_instructions_mention_static_root(path):
    paragraphs = _collectstatic_paragraphs(path.read_text(encoding="utf-8"))
    assert paragraphs, f"{path.name} does not explain collectstatic in prose"
    for paragraph in paragraphs:
        assert "STATIC_ROOT" in paragraph, f"{path.name}: {paragraph}"


def test_collectstatic_paragraphs_exclude_code_blocks_and_other_paragraphs():
    text = (
        "Set `STATIC_ROOT` first.\n\n"
        "```sh\npython manage.py collectstatic\n\necho STATIC_ROOT\n```\n"
        "Then run `collectstatic`\nwhen you deploy.\n\n"
        "`STATIC_ROOT` is where the files go.\n"
    )
    assert _collectstatic_paragraphs(text) == ["Then run `collectstatic`\nwhen you deploy."]
    assert _collectstatic_paragraphs("```sh\npython manage.py collectstatic\n```\n") == []


@pytest.mark.parametrize(
    "block",
    [
        "~~~sh\npython manage.py collectstatic\n~~~\n",
        "~~~sh\npython manage.py collectstatic\n\n```\nrun collectstatic\n~~~\n",
        "~~~~\n~~~\npython manage.py collectstatic\n~~~~\n",
        "````md\n```sh\npython manage.py collectstatic\n```\n\nrun collectstatic\n````\n",
        "```sh\n~~~\npython manage.py collectstatic\n```\n",
    ],
)
def test_collectstatic_paragraphs_treat_tilde_and_nested_fences_as_code(block):
    text = f"Before.\n\n{block}Run `collectstatic` with `STATIC_ROOT` set.\n"
    assert _collectstatic_paragraphs(text) == ["Run `collectstatic` with `STATIC_ROOT` set."]
