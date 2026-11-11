"""End-to-end checks of the admin in a real browser, in Arabic and English.

Every page is opened in both directions, in the light and the dark colour
scheme, on a 360px phone and a 1280px desktop.  Each visit asserts that

* the document direction matches the language,
* the colour scheme actually applied,
* no JavaScript error was raised,
* nothing sticks out of the viewport on either side,

and saves a full-page screenshot to ``test-artifacts/e2e/``.  On top of that
each test checks the widgets on the page, and the ``*_point_the_right_way``
tests compare the English and Arabic renderings pixel by pixel to prove that
every arrow, chevron and icon flipped with the text.  One test also opens a
language that Django's metadata does not mark as RTL, promoted only through
``LANGUAGES_BIDI``.
"""

from __future__ import annotations

import re

import pytest

from .conftest import PASSWORD, WIDTHS
from .layout import (
    assert_controls_inside_viewport,
    assert_mirrored,
    assert_no_horizontal_overflow,
    assert_precedes,
    assert_start_aligned,
    box,
    colours,
    contrast,
    end_side,
    ink,
    luminance,
    side_of,
    start_side,
    text_and_box,
    text_box,
)

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

LANGS = ("en", "ar")
SCHEMES = ("light", "dark")

CHANGELIST = "/admin/testapp/book/"
ADD_FORM = "/admin/testapp/book/add/"
INLINE_GROUPS = ("#chapter_set-group", "#review_set-group")
# BidiSafeAdminMixin wraps every changelist cell in FSI ... PDI.
ISOLATES = "\u2066\u2067\u2068\u2069"


def change_form(book):
    return f"/admin/testapp/book/{book.pk}/change/"


def check_page(page, lang, scheme, where):
    """The checks every page gets, whatever is on it."""
    where = f"{where} [{lang}, {scheme}, {page.viewport_size['width']}px]"
    expected = "rtl" if lang == "ar" else "ltr"

    assert page.locator("html").get_attribute("dir") == expected, f"{where}: <html dir>"
    body_class = page.locator("body").get_attribute("class") or ""
    assert f"rtl-admin--{expected}" in body_class.split(), f"{where}: body class {body_class!r}"
    assert page.locator("body").evaluate("el => getComputedStyle(el).direction") == expected

    _, background = colours(page.locator("#container"))
    if scheme == "dark":
        assert luminance(background) < 0.1, f"{where}: dark scheme not applied ({background})"
    else:
        assert luminance(background) > 0.7, f"{where}: light scheme not applied ({background})"

    assert not page.js_errors, f"{where}: JavaScript errors {page.js_errors}"
    assert_no_horizontal_overflow(page, where)


def visit(open_admin, path, lang, scheme, *, login=True):
    """Open ``path`` once per viewport width."""
    for width in WIDTHS:
        yield open_admin(path, lang=lang, scheme=scheme, width=width, login=login)


def is_wide(page):
    return page.viewport_size["width"] >= 1024


def gap_between(first, second):
    """Horizontal distance between two boxes, 0 when they overlap."""
    return max(0, first.left - second.right, second.left - first.right)


def assert_popup_placed(page, popup, button, what):
    """Desktop popups open beside their button; phones centre them on screen."""
    popup_box, button_box = box(popup), box(button)
    width = page.viewport_size["width"]
    if width <= 767:
        assert abs(popup_box.center_x - width / 2) <= 2, f"{what} is not centred: {popup_box}"
    else:
        assert gap_between(popup_box, button_box) <= 120, (
            f"{what} opened away from its button: {popup_box} vs {button_box}"
        )


parametrize_all = pytest.mark.parametrize(
    "lang, scheme", [(lang, scheme) for lang in LANGS for scheme in SCHEMES]
)


# -- login ------------------------------------------------------------------------


@parametrize_all
def test_login_page(open_admin, snapshot, lang, scheme):
    for page in visit(open_admin, "/admin/login/", lang, scheme, login=False):
        check_page(page, lang, scheme, "login page")

        form = box(page.locator("#login-form"))
        for field in ("username", "password"):
            label = page.locator(f"label[for=id_{field}]")
            assert_start_aligned(text_box(label), form, lang, f"login {field} label")
            assert_start_aligned(box(page.locator(f"#id_{field}")), form, lang, f"login {field}")

        # Credentials are machine text: they stay LTR inside an RTL page.
        for field in ("username", "password"):
            direction = page.locator(f"#id_{field}").evaluate(
                "el => getComputedStyle(el).direction"
            )
            assert direction == "ltr", f"login {field} input is {direction}"

        switcher = page.locator("#branding .rtl-admin-language-switcher__select")
        assert switcher.is_visible()
        fg, bg = colours(switcher)
        assert contrast(fg, bg) >= 4.5, f"language switcher contrast {contrast(fg, bg):.2f}"

        snapshot(page, "login")


@pytest.mark.parametrize("lang", LANGS)
def test_language_switcher_and_login(open_admin, lang):
    other = "en" if lang == "ar" else "ar"
    page = open_admin("/admin/login/", lang=lang, login=False)

    with page.expect_navigation():
        page.locator("#branding .rtl-admin-language-switcher__select").select_option(other)
    page.wait_for_load_state("load")
    assert page.locator("html").get_attribute("dir") == ("rtl" if other == "ar" else "ltr")
    assert page.locator("html").get_attribute("lang") == other

    page.fill("#id_username", "admin")
    page.fill("#id_password", PASSWORD)
    with page.expect_navigation():
        page.locator("#login-form [type=submit]").click()
    assert page.url.rstrip("/").endswith("/admin")
    assert page.locator("#user-tools").is_visible()
    check_page(page, other, "light", "index after login")


def test_language_known_only_through_languages_bidi(open_admin, snapshot):
    """A code promoted to RTL with LANGUAGES_BIDI stays RTL in the body too."""
    for page in visit(open_admin, "/admin/", "ps", "light"):
        where = f"custom RTL [{page.viewport_size['width']}px]"
        assert page.locator("html").get_attribute("dir") == "rtl", f"{where}: <html dir>"
        assert page.locator("html").get_attribute("lang") == "ps", f"{where}: <html lang>"

        stylesheets = page.locator('link[rel="stylesheet"]').evaluate_all(
            "links => links.map(link => link.getAttribute('href'))"
        )
        assert any(path.endswith("admin/css/rtl.css") for path in stylesheets), (
            f"{where}: contrib RTL stylesheet missing: {stylesheets}"
        )

        body_class = page.locator("body").get_attribute("class") or ""
        assert "rtl-admin--rtl" in body_class.split(), f"{where}: body class {body_class!r}"
        assert page.locator("body").evaluate("el => getComputedStyle(el).direction") == "rtl"
        assert not page.js_errors, f"{where}: JavaScript errors {page.js_errors}"
        assert_no_horizontal_overflow(page, where)
        snapshot(page, "custom-rtl")


# -- changelist -------------------------------------------------------------------


@parametrize_all
def test_changelist(open_admin, snapshot, lang, scheme):
    for page in visit(open_admin, CHANGELIST, lang, scheme):
        check_page(page, lang, scheme, "changelist")
        content = box(page.locator("#content"))

        rows = page.locator("#result_list tbody tr")
        assert rows.count() == 5

        # Header columns run in the reading direction.
        headers = page.locator("#result_list thead th")
        assert_precedes(box(headers.nth(1)), box(headers.nth(2)), lang, "changelist columns")

        # Search: magnifier, then the box, then the button.
        search = page.locator("#changelist-search")
        icon = search.locator("label img")
        field = page.locator("#searchbar")
        button = search.locator("input[type=submit]")
        assert_precedes(box(icon), box(field), lang, "search icon before the search box")
        assert_precedes(box(field), box(button), lang, "search box before its button")
        assert_start_aligned(box(icon), box(search), lang, "search icon")

        # Filters sidebar sits on the end side on a desktop.
        filters = page.locator("#changelist-filter")
        assert filters.is_visible()
        if is_wide(page):
            assert side_of(box(filters), content) == end_side(lang), "filters sidebar side"
            sidebar = page.locator("#nav-sidebar")
            assert side_of(box(sidebar), box(page.locator("#main"))) == start_side(lang)
            assert side_of(
                box(page.locator("#user-tools")), box(page.locator("#header"))
            ) == end_side(lang)
            addlink = page.locator(".object-tools a.addlink")
            assert side_of(box(addlink), content) == end_side(lang), "add button side"

        # Actions bar: pick a draft, the counter follows.
        actions = page.locator("#changelist-form .actions")
        counter = actions.locator(".action-counter")
        before = counter.inner_text()
        target = rows.filter(has_text="Guns, Germs, and Steel")
        target.locator("input.action-select").check()
        assert counter.inner_text() != before
        assert re.search(r"1|١", counter.inner_text()), counter.inner_text()
        assert target.evaluate("el => el.classList.contains('selected')")
        select = actions.locator("select[name=action]")
        go = actions.locator("button[type=submit], input[type=submit]").first
        assert_precedes(box(select), box(go), lang, "action select before Go")

        # Pagination: three pages of five, page one first.
        paginator = page.locator(".paginator")
        assert paginator.is_visible()
        links = paginator.locator("a")
        assert links.count() >= 2
        current = paginator.locator("[aria-current=page], .this-page").first
        following = paginator.locator("a:not([aria-current]):not(.showall)").first
        assert_precedes(box(current), box(following), lang, "page 1 before page 2")
        assert_start_aligned(text_box(paginator), box(paginator), lang, "paginator")

        snapshot(page, "changelist")

        # Run the action: the admin redirects back with a success message.
        select.select_option("mark_published")
        with page.expect_navigation():
            go.click()
        check_page(page, lang, scheme, "changelist after an action")
        message = page.locator("ul.messagelist li.success")
        assert message.count() == 1, page.locator("ul.messagelist").all_inner_texts()
        assert message.inner_text().strip() == "Marked 1 book(s) as published."
        assert_start_aligned(text_box(message), box(message), lang, "action success message")
        assert side_of_ink(ink(message)) == start_side(lang), f"{lang}: success icon side"
        published = page.locator("#result_list tbody tr", has_text="Guns, Germs, and Steel")
        status = published.locator("td.field-status").inner_text()
        assert status.strip(ISOLATES + " \n") == "Published", repr(status)
        snapshot(page, "action")

        # Page two holds the next five titles.
        first_title = page.locator("#result_list tbody tr th a").first.inner_text()
        with page.expect_navigation():
            page.locator(".paginator a", has_text=re.compile(r"^(2|٢)$")).first.click()
        assert re.search(r"[?&]p=2\b", page.url), page.url
        check_page(page, lang, scheme, "changelist page 2")
        assert page.locator("#result_list tbody tr").count() == 5
        assert page.locator("#result_list tbody tr th a").first.inner_text() != first_title
        current = page.locator(".paginator [aria-current=page], .paginator .this-page").first
        assert re.fullmatch(r"2|٢", current.inner_text().strip()), current.inner_text()
        snapshot(page, "page-2")

        page.fill("#searchbar", "Dune")
        with page.expect_navigation():
            page.press("#searchbar", "Enter")
        assert page.locator("#result_list tbody tr").count() == 1
        check_page(page, lang, scheme, "changelist search")
        snapshot(page, "search")


@parametrize_all
def test_changelist_filters(open_admin, snapshot, lang, scheme):
    for page in visit(open_admin, CHANGELIST, lang, scheme):
        filters = page.locator("#changelist-filter")
        status = filters.locator("details[data-filter-title=status]")
        with page.expect_navigation():
            status.locator("a[href*='status__exact=published']").click()
        assert "status__exact=published" in page.url
        check_page(page, lang, scheme, "filtered changelist")

        selected = page.locator("#changelist-filter details[data-filter-title=status] li.selected")
        widths = selected.evaluate(
            "el => [parseFloat(getComputedStyle(el).borderLeftWidth),"
            " parseFloat(getComputedStyle(el).borderRightWidth)]"
        )
        start_border = widths[1] if lang == "ar" else widths[0]
        end_border = widths[0] if lang == "ar" else widths[1]
        assert start_border >= 4 and end_border == 0, f"selected filter marker borders {widths}"

        title = page.locator("#changelist-filter details[data-filter-title=status] summary")
        assert_start_aligned(text_box(title), box(filters), lang, "filter title")

        # Collapse a filter; the closed arrow has to point into the list.
        title.click()
        assert not page.locator("#changelist-filter details[data-filter-title=status]").evaluate(
            "el => el.open"
        )
        snapshot(page, "filters")

        # Date hierarchy drill-down.
        hierarchy = page.locator(".xfull")
        if hierarchy.count():
            assert_start_aligned(
                text_box(hierarchy.first), box(page.locator("#changelist")), lang, "dates"
            )


@parametrize_all
def test_filtered_changelist_table_geometry(open_admin, lang, scheme):
    """No border bleeds out of a filtered table, and its title cells keep the
    stock padding at the start - 8px, widened to 10px at or below 1024px by
    responsive.css - while the stock 1em moves to the end."""
    for page in visit(open_admin, CHANGELIST, lang, scheme):
        check_page(page, lang, scheme, "changelist")
        assert "filtered" in (page.locator("#changelist").get_attribute("class") or "").split()

        table = page.locator("#result_list")
        bleed = table.evaluate("el => el.getBoundingClientRect().width - el.clientWidth")
        assert bleed <= 1, f"table borders bleed {bleed}px"

        # Rendered geometry, not computed styles: a zero-height block probe
        # inside the cell spans exactly its content box, so the gaps between
        # probe and cell - minus the borders - are the paddings as painted.
        cell = table.evaluate(
            """el => {
              const th = el.querySelector("tbody th");
              const probe = document.createElement("span");
              probe.style.cssText =
                "display:block;width:100%;height:0;margin:0;padding:0;border:0";
              th.appendChild(probe);
              try {
                const cs = getComputedStyle(th);
                const t = th.getBoundingClientRect();
                const p = probe.getBoundingClientRect();
                return {
                  padLeft: p.left - t.left - parseFloat(cs.borderLeftWidth),
                  padRight: t.right - p.right - parseFloat(cs.borderRightWidth),
                  font: parseFloat(cs.fontSize),
                };
              } finally {
                probe.remove();
              }
            }"""
        )
        start_pad = cell["padRight"] if lang == "ar" else cell["padLeft"]
        end_pad = cell["padLeft"] if lang == "ar" else cell["padRight"]
        base = 10 if page.viewport_size["width"] <= 1024 else 8
        assert abs(start_pad - base) <= 1, f"title cell start padding {start_pad}, want {base}"
        assert abs(end_pad - cell["font"]) <= 1, (
            f"title cell end padding {end_pad} is not 1em ({cell['font']})"
        )


# -- change form ------------------------------------------------------------------


@parametrize_all
def test_change_form(open_admin, e2e_data, snapshot, lang, scheme):
    for page in visit(open_admin, change_form(e2e_data["book"]), lang, scheme):
        check_page(page, lang, scheme, "change form")

        fieldset = page.locator("fieldset").first
        # The description is English: `unicode-bidi: plaintext` lays it out
        # LTR even in the Arabic admin, so it hugs the left edge in both.
        description = fieldset.locator(".description")
        assert_start_aligned(text_box(description), box(fieldset), "en", "fieldset description")

        title_row = page.locator(".form-row.field-title")
        label = title_row.locator("label")
        field = page.locator("#id_title")
        help_text = page.locator("#id_title_helptext")
        # Labels are form chrome: even an untranslated English one sits on the
        # page's start edge, at every width.
        assert_start_aligned(text_box(label), box(title_row), lang, "title label")
        label_box, field_box = box(label), box(field)
        if field_box.top < label_box.top + label_box.height - 2:
            # Side by side (Django < 6.1 on a desktop): label first.
            assert_precedes(label_box, field_box, lang, "label before its input")
        else:
            # Stacked (Django 6.1, phones): label above, same start edge.
            start = (lambda b: b.right) if lang == "ar" else (lambda b: b.left)
            assert abs(start(label_box) - start(field_box)) <= 12, (label_box, field_box)
        # The help text lines up with the field it describes.
        help_box = box(help_text)
        padding = help_text.evaluate(
            "el => parseFloat(getComputedStyle(el)[document.dir === 'rtl' ? 'paddingRight' : 'paddingLeft'])"
        )
        if lang == "ar":
            assert abs(help_box.right - padding - field_box.right) <= 12, (help_box, field_box)
        else:
            assert abs(help_box.left + padding - field_box.left) <= 12, (help_box, field_box)

        # Multi-widget fields are labelled by a <legend>; it resolves its own
        # direction like a label so the colon stays at the end of the text.
        for legend in page.locator("fieldset.aligned .form-row legend").all():
            assert legend.evaluate("el => getComputedStyle(el).unicodeBidi") == "plaintext"

        # Collapsible section opens in place.
        collapse = page.locator("fieldset.collapse")
        assert not page.locator("#id_summary").is_visible()
        if collapse.locator("summary").count():
            title = collapse.locator("summary h2")
            collapse.locator("summary").click()
        else:  # Django < 5.1: an <h2> with a "Show" link.
            title = collapse.locator("h2")
            collapse.locator("a.collapse-toggle").click()
        assert page.locator("#id_summary").is_visible()
        assert_start_aligned(text_box(title), box(collapse), lang, "collapse title")

        # Tabular inline: columns in reading order, add-row link at the start.
        tabular = page.locator("#chapter_set-group")
        headers = tabular.locator("thead th:visible")
        assert_precedes(box(headers.nth(0)), box(headers.nth(1)), lang, "tabular inline columns")
        # The saved object's name floats above its row, not over the inputs.
        saved = tabular.locator("tbody tr.has_original").first
        original = box(saved.locator("td.original p"))
        first_input = box(saved.locator("td:not(.original) input:visible").first)
        assert original.top + original.height <= first_input.top + 1, (original, first_input)
        add_row = tabular.locator(".add-row a")
        assert_start_aligned(
            box(add_row), box(tabular.locator(".add-row td")), lang, "tabular add row"
        )
        before = tabular.locator("tbody tr.form-row:not(.empty-form)").count()
        add_row.click()
        assert tabular.locator("tbody tr.form-row:not(.empty-form)").count() == before + 1

        # Stacked inline: heading text at the start, delete box at the end.
        stacked = page.locator("#review_set-group")
        heading = stacked.locator(".inline-related h3").first
        assert_start_aligned(
            text_box(heading.locator("b")), box(heading), lang, "stacked inline heading"
        )
        delete = heading.locator("span.delete")
        if delete.count() and is_wide(page):
            assert side_of(box(delete), box(heading)) == end_side(lang), (
                "inline delete checkbox side"
            )

        # On a phone every inline label and control fits on screen.  Inlines
        # clip or scroll their overflow, so the page-wide check cannot see it.
        if not is_wide(page):
            assert_controls_inside_viewport(
                page, INLINE_GROUPS, f"inlines [{lang}, {scheme}, {page.viewport_size['width']}px]"
            )

        submit_row = page.locator(".submit-row").last
        save = submit_row.locator("input[name=_save]")
        delete_link = submit_row.locator("a.deletelink")
        if is_wide(page):
            assert_precedes(box(save), box(delete_link), lang, "save before delete")
            assert side_of(box(delete_link), box(submit_row)) == end_side(lang)

        snapshot(page, "change-form")


@parametrize_all
def test_validation_errors(open_admin, snapshot, lang, scheme):
    for page in visit(open_admin, ADD_FORM, lang, scheme):
        page.fill("#id_isbn", "978")
        with page.expect_navigation():
            page.locator("input[name=_save]").click()
        check_page(page, lang, scheme, "change form with errors")

        note = page.locator(".errornote")
        assert note.is_visible()
        assert_start_aligned(text_box(note), box(note), lang, "error note")

        errors = page.locator(".field-title .errorlist")
        assert errors.is_visible()
        assert_start_aligned(
            text_box(errors.locator("li")), box(errors), lang, "field error", tolerance=12
        )
        field = box(page.locator("#id_title"))
        error = text_box(errors.locator("li"))
        if is_wide(page):
            if lang == "ar":
                assert abs(error.right - field.right) <= 30, (error, field)
            else:
                assert abs(error.left - field.left) <= 30, (error, field)
        assert page.locator("#id_isbn").input_value() == "978"
        snapshot(page, "errors")


# -- widgets ----------------------------------------------------------------------


@parametrize_all
def test_calendar_and_clock(open_admin, e2e_data, snapshot, lang, scheme):
    for page in visit(open_admin, change_form(e2e_data["book"]), lang, scheme):
        date_input = page.locator("#id_published_on")
        shortcuts = page.locator(".field-published_on .datetimeshortcuts").first
        assert_precedes(box(date_input), box(shortcuts), lang, "date shortcuts after the input")

        page.locator("#calendarlink0").click()
        calendar = page.locator("#calendarbox0")
        assert calendar.is_visible()
        check_page(page, lang, scheme, "calendar popup")

        cal_box = box(calendar)
        assert_popup_placed(page, calendar, page.locator("#calendarlink0"), "calendar")
        previous = calendar.locator(".calendarnav-previous")
        following = calendar.locator(".calendarnav-next")
        assert side_of(box(previous), cal_box) == start_side(lang), "previous month side"
        assert side_of(box(following), cal_box) == end_side(lang), "next month side"

        days = calendar.locator("table tr").first.locator("th")
        assert days.count() == 7
        assert_precedes(box(days.nth(0)), box(days.nth(6)), lang, "first weekday first")

        caption = calendar.locator("caption")
        month = caption.inner_text()
        following.click()
        assert caption.inner_text() != month
        previous.click()
        assert caption.inner_text() == month
        snapshot(page, "calendar")

        calendar.locator("td a", has_text=re.compile(r"^(15|١٥)$")).first.click()
        assert not calendar.is_visible()
        assert date_input.input_value().endswith("15")

        page.locator("#clocklink0").click()
        clock = page.locator("#clockbox0")
        assert clock.is_visible()
        assert_popup_placed(page, clock, page.locator("#clocklink0"), "clock")
        check_page(page, lang, scheme, "clock popup")
        snapshot(page, "clock")
        clock.locator("ul.timelist a").nth(3).click()
        assert not clock.is_visible()
        assert page.locator("#id_launch_time").input_value() == "12:00:00"


@parametrize_all
def test_autocomplete(open_admin, e2e_data, snapshot, lang, scheme):
    for page in visit(open_admin, change_form(e2e_data["book"]), lang, scheme):
        selection = page.locator(".field-category .select2-selection")
        rendered = selection.locator(".select2-selection__rendered")
        arrow = selection.locator(".select2-selection__arrow")
        assert side_of(box(arrow), box(selection)) == end_side(lang), "autocomplete arrow side"
        assert_start_aligned(text_box(rendered), box(selection), lang, "autocomplete value")

        wrapper = page.locator(".field-category .related-widget-wrapper")
        links = wrapper.locator("a.related-widget-wrapper-link:visible")
        if is_wide(page):
            assert_precedes(
                box(selection), box(links.first), lang, "related links after the select"
            )

        selection.click()
        dropdown = page.locator(".select2-container--open .select2-dropdown")
        dropdown.wait_for()
        page.locator(".select2-search__field").fill("تا")
        option = page.locator(".select2-results__option", has_text="تاريخ")
        option.wait_for()
        assert_start_aligned(*text_and_box(option), lang=lang, what="autocomplete option")
        check_page(page, lang, scheme, "autocomplete dropdown")
        snapshot(page, "autocomplete")

        option.click()
        assert rendered.inner_text().strip().endswith("تاريخ")


@parametrize_all
def test_language_switcher_in_header(open_admin, lang, scheme):
    for page in visit(open_admin, "/admin/", lang, scheme):
        check_page(page, lang, scheme, "index")
        switcher = page.locator("#user-tools .rtl-admin-language-switcher")
        select = switcher.locator("select")
        assert select.is_visible()
        fg, bg = colours(select)
        assert contrast(fg, bg) >= 4.5, f"switcher select contrast {contrast(fg, bg):.2f}"
        label = switcher.locator("label")
        if label.is_visible():
            fg, bg = colours(label)
            assert contrast(fg, bg) >= 3, f"switcher label contrast {contrast(fg, bg):.2f}"
        dropdown_colours = select.locator("option").first.evaluate(
            "el => [getComputedStyle(el).color, getComputedStyle(el).backgroundColor]"
        )
        assert dropdown_colours[0] != dropdown_colours[1]


@parametrize_all
def test_dashboard_action_link_padding(open_admin, lang, scheme):
    """Action links reserve 16px of icon room at the start and keep the stock
    0.6em gap at the end - dropped below 1024px, like the stock sheets do.

    Measured on the rendered boxes: the inline link's border rect includes
    its padding, the text rect inside it does not, so the gap between the
    two is exactly the room the link reserves - and paints - on each side.
    """
    for page in visit(open_admin, "/admin/", lang, scheme):
        check_page(page, lang, scheme, "index")
        assert "dashboard" in (page.locator("body").get_attribute("class") or "").split()

        link = page.locator("#content-main .module table td a").first
        label, frame = text_and_box(link)
        font = link.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
        if lang == "ar":
            start_gap, end_gap = frame.right - label.right, label.left - frame.left
        else:
            start_gap, end_gap = label.left - frame.left, frame.right - label.right
        assert abs(start_gap - 16) <= 1, f"action link reserves {start_gap}px at the start"
        expected_end = 0.6 * font if is_wide(page) else 0
        assert abs(end_gap - expected_end) <= 1, (
            f"action link end gap {end_gap:.1f} is not {expected_end:.1f}"
        )


# -- mirrored icons -----------------------------------------------------------------


def pair(open_admin, path, **kwargs):
    return {lang: open_admin(path, lang=lang, **kwargs) for lang in LANGS}


def test_changelist_icons_point_the_right_way(open_admin, snapshot):
    pages = pair(open_admin, CHANGELIST)

    # Navigation sidebar open: the chevron points towards the sidebar.
    toggles = {lang: ink(page.locator("#toggle-nav-sidebar")) for lang, page in pages.items()}
    assert_mirrored(toggles["en"], toggles["ar"], "open nav-sidebar toggle")

    for page in pages.values():
        page.locator("#toggle-nav-sidebar").click()
        page.wait_for_function("!document.getElementById('main').classList.contains('shifted')")
    toggles = {lang: ink(page.locator("#toggle-nav-sidebar")) for lang, page in pages.items()}
    assert_mirrored(toggles["en"], toggles["ar"], "closed nav-sidebar toggle")
    for page in pages.values():
        page.locator("#toggle-nav-sidebar").click()

    # A collapsed filter shows an arrow pointing along the reading direction.
    arrows = {}
    for lang, page in pages.items():
        summary = page.locator("#changelist-filter details[data-filter-title=status] > summary")
        summary.click()
        arrows[lang] = ink(summary)
        assert side_of_ink(arrows[lang]) == start_side(lang), f"{lang}: filter arrow side"
    assert_mirrored(arrows["en"], arrows["ar"], "collapsed filter arrow")

    # The "+" on the add button sits after the label.
    for lang, page in pages.items():
        icon = ink(page.locator(".object-tools a.addlink"))
        assert side_of_ink(icon) == end_side(lang), f"{lang}: add button icon side"

    for lang, page in pages.items():
        snapshot(page, f"icons-{lang}")


def test_change_form_icons_point_the_right_way(open_admin, e2e_data, snapshot):
    pages = pair(open_admin, change_form(e2e_data["book"]))

    # Django 5.1+ collapses fieldsets with <details>; its disclosure triangle
    # points along the reading direction.
    if pages["en"].locator("fieldset.collapse summary").count():
        collapsed = {
            lang: ink(page.locator("fieldset.collapse summary"), children_only=True)
            for lang, page in pages.items()
        }
        for lang, glyph in collapsed.items():
            assert side_of_ink(glyph) == start_side(lang), f"{lang}: collapse marker side"
        assert_mirrored(collapsed["en"], collapsed["ar"], "collapsed fieldset marker")

    for lang, page in pages.items():
        assert_add_row_icons(page, lang)

    for page in pages.values():
        page.locator("#calendarlink0").click()
        page.locator("#calendarbox0").wait_for()
    for nav in ("previous", "next"):
        glyphs = {
            lang: ink(page.locator(f"#calendarbox0 .calendarnav-{nav}"))
            for lang, page in pages.items()
        }
        assert_mirrored(glyphs["en"], glyphs["ar"], f"calendar {nav}-month arrow")

    for lang, page in pages.items():
        snapshot(page, f"icons-{lang}")


@pytest.mark.parametrize("lang", LANGS)
def test_add_row_icons_on_a_phone(open_admin, e2e_data, lang):
    page = open_admin(change_form(e2e_data["book"]), lang=lang, width=min(WIDTHS))
    assert_add_row_icons(page, lang)


def assert_add_row_icons(page, lang):
    """The "+" of every "Add another" link sits before its text."""
    for group in INLINE_GROUPS:
        link = page.locator(f"{group} .add-row a")
        assert side_of_ink(ink(link)) == start_side(lang), f"{lang}: {group} add-row icon side"
        text, icon_room = text_box(link), box(link)
        if lang == "ar":
            assert text.right <= icon_room.right - 14, f"{group}: add-row text over its icon"
        else:
            assert text.left >= icon_room.left + 14, f"{group}: add-row text over its icon"


def side_of_ink(glyph):
    return "left" if glyph.center_fraction < 0.5 else "right"
