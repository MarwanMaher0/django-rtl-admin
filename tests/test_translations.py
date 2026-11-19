"""Translation integrity: extraction, catalog completeness and compilation.

The extractor, the `.po` parser and the catalog comparisons run on the
standard library alone so they also cover the no-Babel test cell. The
recompile-and-compare check prefers Babel and falls back to `msgfmt`, and
skips when neither is installed.
"""

import ast
import gettext as gettext_module
import pathlib
import re
import shutil
import subprocess

import pytest

import django_rtl_admin

ROOT = pathlib.Path(django_rtl_admin.__file__).parent
LOCALE_DIR = ROOT / "locale"

SHIPPED_LOCALES = ("ar", "ckb", "fa", "he", "ug", "ur")

# The complete inventory of messages the package marks for translation.
EXPECTED_MSGIDS = {
    "Language",
    "Go",
    "Django site admin",
    "Django administration",
    "Remove from sorting",
    "Sorting priority: %(priority_number)s",
    "Toggle sorting",
    "Select all objects on this page for an action",
    "Delete?",
    "Change",
    "View",
    "View on site",
    "Bilingual / RTL admin",
    "Select this object for an action - {}",
    "%(num)s second",
    "%(delta)s ago",
    "%(delta)s from now",
}

PLURAL_MSGIDS = {"%(num)s second": "%(num)s seconds"}
EXTRACTED_MSGIDS = EXPECTED_MSGIDS | set(PLURAL_MSGIDS.values())


# -- extraction ------------------------------------------------------------

TRANSLATE_TAG = re.compile(r"{%\s*trans(?:late)?\s+(?P<quote>[\"'])(?P<msg>.*?)(?P=quote)")
BLOCKTRANSLATE = re.compile(
    r"{%\s*blocktrans(?:late)?\b[^%]*%}(?P<body>.*?){%\s*endblocktrans(?:late)?\s*%}",
    re.DOTALL,
)
GETTEXT_CALL = re.compile(
    r"\b(?:gettext_lazy|gettext|_)\(\s*(?P<quote>[\"'])(?P<msg>.*?)(?P=quote)\s*\)"
)
GETTEXT_FUNC_NAMES = {"_", "gettext", "gettext_lazy", "ngettext"}


def _normalize_blocktranslate(body: str) -> str:
    text = " ".join(body.split())
    return re.sub(r"{{\s*(\w+)\s*}}", r"%(\1)s", text)


def _python_msgids(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    msgids: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in GETTEXT_FUNC_NAMES:
            continue
        for argument in node.args[: 2 if name == "ngettext" else 1]:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                msgids.add(argument.value)
    return msgids


def extract_msgids() -> set[str]:
    msgids: set[str] = set()
    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        msgids.update(match.group("msg") for match in TRANSLATE_TAG.finditer(text))
        msgids.update(match.group("msg") for match in GETTEXT_CALL.finditer(text))
        msgids.update(
            _normalize_blocktranslate(match.group("body"))
            for match in BLOCKTRANSLATE.finditer(text)
        )
    for path in sorted(ROOT.rglob("*.py")):
        if "locale" in path.parts:
            continue
        msgids.update(_python_msgids(path))
    return msgids


def test_extraction_finds_exactly_the_marked_messages():
    assert extract_msgids() == EXTRACTED_MSGIDS


# -- the .po parser ---------------------------------------------------------


def _unquote(lines: list[str]) -> str:
    return "".join(ast.literal_eval(line) for line in lines)


def parse_po(path: pathlib.Path) -> list[dict]:
    """Parse a `.po` file into `{msgid, msgstr, fuzzy}` dicts, header included."""
    entries: list[dict] = []
    field: str | tuple[str, int] | None = None
    fuzzy = False
    msgid: list[str] = []
    msgid_plural: list[str] = []
    msgstr: list[str] = []
    msgstr_plural: dict[int, list[str]] = {}
    plural_msgstr = re.compile(r"^msgstr\[(\d+)\]\s+(.*)$")

    def flush() -> None:
        nonlocal field, fuzzy, msgid, msgid_plural, msgstr, msgstr_plural
        if msgid or msgstr or msgid_plural or msgstr_plural:
            entry = {"msgid": _unquote(msgid), "msgstr": _unquote(msgstr), "fuzzy": fuzzy}
            if msgid_plural or msgstr_plural:
                entry["msgid_plural"] = _unquote(msgid_plural)
                entry["msgstr_plural"] = {
                    index: _unquote(lines) for index, lines in sorted(msgstr_plural.items())
                }
                if not entry["msgstr"] and 0 in entry["msgstr_plural"]:
                    entry["msgstr"] = entry["msgstr_plural"][0]
            entries.append(entry)
        field, fuzzy, msgid, msgid_plural, msgstr, msgstr_plural = (
            None,
            False,
            [],
            [],
            [],
            {},
        )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            if line.startswith("#,") and "fuzzy" in line:
                fuzzy = True
        elif not line:
            continue
        elif line.startswith("msgid "):
            flush()
            field = "msgid"
            msgid.append(line[len("msgid ") :])
        elif line.startswith("msgid_plural "):
            field = "msgid_plural"
            msgid_plural.append(line[len("msgid_plural ") :])
        elif (plural := plural_msgstr.match(line)) is not None:
            index = int(plural[1])
            field = ("plural", index)
            msgstr_plural[index] = [plural[2]]
        elif line.startswith("msgstr "):
            field = "msgstr"
            msgstr.append(line[len("msgstr ") :])
        elif line.startswith('"'):
            if field == "msgid":
                msgid.append(line)
            elif field == "msgid_plural":
                msgid_plural.append(line)
            elif field == "msgstr":
                msgstr.append(line)
            elif isinstance(field, tuple):
                msgstr_plural[field[1]].append(line)
        else:
            field = None
    flush()
    return entries


def po_path(code: str) -> pathlib.Path:
    return LOCALE_DIR / code / "LC_MESSAGES" / "django.po"


def mo_path(code: str) -> pathlib.Path:
    return LOCALE_DIR / code / "LC_MESSAGES" / "django.mo"


def non_header_po_entries(code: str) -> dict[str, str]:
    return {
        entry["msgid"]: entry["msgstr"]
        for entry in parse_po(po_path(code))
        if entry["msgid"] and not entry["fuzzy"]
    }


def mo_entries(path: pathlib.Path) -> dict[str, str]:
    with open(path, "rb") as handle:
        # GNUTranslations exposes the compiled catalog dict here; the tests
        # compare entries rather than bytes because msgfmt and Babel lay out
        # the binary differently.
        catalog = gettext_module.GNUTranslations(handle)._catalog
    entries: dict[str, str] = {}
    for key, msgstr in catalog.items():
        if not key:
            continue
        if isinstance(key, tuple):
            # Plural entries are keyed as (msgid, plural_index); form 0 is the
            # entry the .po comparison pairs with ``msgstr``.
            msgid, index = key
            if index == 0:
                entries[msgid] = msgstr
        else:
            entries[key] = msgstr
    return entries


# -- shipped catalogs -------------------------------------------------------


def test_the_shipped_locales_are_the_documented_six():
    directories = sorted(path.name for path in LOCALE_DIR.iterdir() if path.is_dir())
    assert directories == sorted(SHIPPED_LOCALES)


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_each_locale_ships_both_a_po_and_a_mo(code):
    assert po_path(code).is_file()
    assert mo_path(code).is_file()


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_every_message_is_translated_without_fuzzy_flags(code):
    entries = {entry["msgid"]: entry for entry in parse_po(po_path(code)) if entry["msgid"]}
    missing = EXPECTED_MSGIDS - entries.keys()
    assert not missing, f"{code}: untranslated or missing: {sorted(missing)}"
    for msgid in sorted(EXPECTED_MSGIDS):
        entry = entries[msgid]
        assert not entry["fuzzy"], f"{code}: {msgid!r} is flagged fuzzy"
        assert entry["msgstr"].strip(), f"{code}: {msgid!r} has an empty translation"
        assert entry["msgstr"] != msgid, f"{code}: {msgid!r} was left untranslated"


def _placeholders(text: str) -> tuple[list[str], int]:
    return sorted(re.findall(r"%\((\w+)\)s", text)), text.count("{}")


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_translations_preserve_interpolation_placeholders(code):
    for msgid, msgstr in non_header_po_entries(code).items():
        assert _placeholders(msgstr) == _placeholders(msgid), f"{code}: {msgid!r}"


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_the_po_header_declares_its_locale(code):
    header = next(entry for entry in parse_po(po_path(code)) if not entry["msgid"])
    language = re.search(r"^Language:\s*(\S+)\s*$", header["msgstr"], re.MULTILINE)
    assert language, f"{code}: the catalog header has no Language field"
    assert language.group(1) == code


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_the_shipped_mo_matches_the_po(code):
    compiled = mo_entries(mo_path(code))
    source = non_header_po_entries(code)
    assert compiled == source, f"{code}: django.mo is stale relative to django.po"


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_the_shipped_mo_translates_every_message(code):
    with open(mo_path(code), "rb") as handle:
        translations = gettext_module.GNUTranslations(handle)
    for msgid in sorted(EXPECTED_MSGIDS):
        if msgid in PLURAL_MSGIDS:
            translated = translations.ngettext(msgid, PLURAL_MSGIDS[msgid], 2)
        else:
            translated = translations.gettext(msgid)
        assert translated != msgid, f"{code}: {msgid!r} missing from django.mo"
        assert translated.strip(), f"{code}: {msgid!r} compiles to an empty string"


# -- recompilation ----------------------------------------------------------


def _compile_po(po: pathlib.Path, target: pathlib.Path) -> None:
    try:
        from babel.messages.mofile import write_mo
        from babel.messages.pofile import read_po
    except ImportError:
        msgfmt = shutil.which("msgfmt")
        if msgfmt is None:
            pytest.skip("neither Babel nor msgfmt is available")
        subprocess.run([msgfmt, str(po), "-o", str(target)], check=True, capture_output=True)
        return
    with open(po, "rb") as handle:
        catalog = read_po(handle)
    with open(target, "wb") as handle:
        write_mo(handle, catalog)


@pytest.mark.parametrize("code", SHIPPED_LOCALES)
def test_recompiling_the_po_reproduces_the_shipped_mo(code, tmp_path):
    target = tmp_path / "django.mo"
    _compile_po(po_path(code), target)
    assert mo_entries(target) == mo_entries(mo_path(code)), (
        f"{code}: the committed django.mo was not compiled from django.po"
    )
