import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        assert SEO["_translation_structure"]((DOCS / name).read_text(encoding="utf-8"))[2] == expected


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
    root = "https://django-rtl-admin.readthedocs.io/"
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
    assert page.meta["seo_canonical"] == page.meta[f"seo_{language}_url"]
    assert "(English)" not in page.meta["seo_title"]


@pytest.mark.parametrize("name", ["api", "changelog"])
def test_untranslated_reference_pages_keep_english_fallback(name):
    page = SimpleNamespace(file=SimpleNamespace(src_path=f"{name}.md"))
    assert SEO["_is_fallback"](page, "ar")
    assert not (DOCS / f"{name}.ar.md").exists()
