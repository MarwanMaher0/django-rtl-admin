"""Geometry and pixel helpers for the browser tests.

Everything here measures what Chromium actually rendered rather than what the
stylesheet says, so a rule that is overridden, shadowed or mirrored a second
time by the browser's own bidi handling still gets caught.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

# -- horizontal overflow ------------------------------------------------------

_OVERFLOW_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const problems = [];
  const root = document.scrollingElement || document.documentElement;
  if (root.scrollWidth > vw + 1) {
    problems.push(`page scrolls sideways: scrollWidth ${root.scrollWidth}px > ${vw}px`);
  }
  const describe = (el) => {
    let name = el.tagName.toLowerCase();
    if (el.id) name += '#' + el.id;
    const cls = (typeof el.className === 'string' ? el.className : '').trim();
    if (cls) name += '.' + cls.split(/\\s+/).join('.');
    const parent = el.parentElement;
    if (parent && parent !== document.body) {
      let p = parent.tagName.toLowerCase();
      if (parent.id) p += '#' + parent.id;
      else if (typeof parent.className === 'string' && parent.className.trim()) {
        p += '.' + parent.className.trim().split(/\\s+/)[0];
      }
      name = p + ' > ' + name;
    }
    return name;
  };
  // A scroll container (overflow-x: auto) is the right answer for wide
  // tables on a phone; only the container itself has to fit.
  const clipsX = (el) => getComputedStyle(el).overflowX !== 'visible';
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility !== 'visible' || cs.display === 'contents') continue;
    if (el.closest('[hidden], .hidden, template, script, style')) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    // Visually hidden helpers (skip links, select2's accessible select).
    if (cs.clip !== 'auto' || cs.clipPath !== 'none') continue;
    if (r.bottom < -500 || r.top < -500) continue;
    let ancestor = el.parentElement;
    let clipped = false;
    while (ancestor && ancestor !== document.body && ancestor !== document.documentElement) {
      if (clipsX(ancestor)) { clipped = true; break; }
      ancestor = ancestor.parentElement;
    }
    if (clipped) continue;
    if (r.left < -1 || r.right > vw + 1) {
      problems.push(
        `${describe(el)} spans ${Math.round(r.left)}..${Math.round(r.right)}px of a ${vw}px viewport`
      );
    }
  }
  return problems;
}
"""


def horizontal_overflow(page) -> list[str]:
    """Every rendered box that sticks out of the viewport, left or right.

    ``scrollWidth`` alone only catches overflow on the *end* side: content
    pushed past the start edge (the right edge in RTL) is unreachable rather
    than scrollable, so it has to be found box by box.
    """
    return page.evaluate(_OVERFLOW_JS)


def assert_no_horizontal_overflow(page, where: str) -> None:
    problems = horizontal_overflow(page)
    assert not problems, f"{where}: horizontal overflow\n  " + "\n  ".join(problems[:15])


_CONTROLS_OUTSIDE_JS = """
(containers) => {
  const vw = document.documentElement.clientWidth;
  const problems = [];
  for (const selector of containers) {
    const container = document.querySelector(selector);
    if (!container) {
      problems.push(`${selector} is not on the page`);
      continue;
    }
    for (const el of container.querySelectorAll('label, input, textarea, select')) {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (cs.visibility !== 'visible' || r.width === 0 || r.height === 0) continue;
      if (r.left < -0.5 || r.right > vw + 0.5) {
        const name = el.name || el.htmlFor || el.id || el.textContent.trim().slice(0, 30);
        problems.push(
          `${selector} ${el.tagName.toLowerCase()} ${name} spans`
          + ` ${Math.round(r.left)}..${Math.round(r.right)}px of a ${vw}px viewport`
        );
      }
    }
  }
  return problems;
}
"""


def assert_controls_inside_viewport(page, containers, where: str) -> None:
    """Every visible label and form control lies within the viewport.

    The page-wide overflow check skips anything inside a clipping or scrolling
    ancestor, because such boxes never make the page scroll.  A label or input
    cut off by one is still unusable, so form controls are checked box by box.
    """
    problems = page.evaluate(_CONTROLS_OUTSIDE_JS, list(containers))
    assert not problems, f"{where}: controls outside the viewport\n  " + "\n  ".join(problems[:15])


# -- boxes ----------------------------------------------------------------------


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2


def box(locator) -> Box:
    rect = locator.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return {left: r.left, top: r.top, width: r.width, height: r.height}; }"
    )
    return Box(**rect)


def text_box(locator) -> Box:
    """The box of the element's rendered text, not of the element."""
    rect = locator.evaluate(
        """el => {
          const range = document.createRange();
          range.selectNodeContents(el);
          const r = range.getBoundingClientRect();
          return {left: r.left, top: r.top, width: r.width, height: r.height};
        }"""
    )
    return Box(**rect)


def text_and_box(locator) -> tuple[Box, Box]:
    """``(text_box(locator), box(locator))``, measured in a single evaluation.

    Widgets that re-render their nodes - select2 replaces result options while
    the dropdown settles - can detach the element between two separate calls,
    and the later measurement then sees a zero rect.
    """
    rects = locator.evaluate(
        """el => {
          const range = document.createRange();
          range.selectNodeContents(el);
          const pick = r => ({left: r.left, top: r.top, width: r.width, height: r.height});
          return [pick(range.getBoundingClientRect()), pick(el.getBoundingClientRect())];
        }"""
    )
    return Box(**rects[0]), Box(**rects[1])


def precedes(first: Box, second: Box, lang: str, *, tolerance: float = 1) -> bool:
    """True when ``first`` comes before ``second`` in the reading direction."""
    if lang == "ar":
        return first.right > second.right + tolerance and first.center_x > second.center_x
    return first.left + tolerance < second.left and first.center_x < second.center_x


def assert_precedes(first: Box, second: Box, lang: str, what: str) -> None:
    assert precedes(first, second, lang), (
        f"{what}: expected the first box before the second in {lang} reading order, "
        f"got {first} and {second}"
    )


def assert_start_aligned(inner: Box, outer: Box, lang: str, what: str, *, tolerance=4) -> None:
    """``inner`` hugs the start edge of ``outer`` (left in LTR, right in RTL)."""
    if lang == "ar":
        gap_start, gap_end = outer.right - inner.right, inner.left - outer.left
    else:
        gap_start, gap_end = inner.left - outer.left, outer.right - inner.right
    assert gap_start <= tolerance or gap_start < gap_end, (
        f"{what}: not aligned to the {lang} start edge "
        f"(start gap {gap_start:.0f}px, end gap {gap_end:.0f}px)"
    )


def side_of(inner: Box, outer: Box) -> str:
    """Which physical half of ``outer`` the centre of ``inner`` falls in."""
    return "left" if inner.center_x < outer.center_x else "right"


def start_side(lang: str) -> str:
    return "right" if lang == "ar" else "left"


def end_side(lang: str) -> str:
    return "left" if lang == "ar" else "right"


# -- pixels ---------------------------------------------------------------------

_HIDE_TEXT_CSS = """
[data-e2e-ink]:not([data-e2e-ink="children"]), [data-e2e-ink] * {
  -webkit-text-fill-color: transparent !important;
  text-shadow: none !important;
  caret-color: transparent !important;
}
[data-e2e-ink]::before, [data-e2e-ink]::after, [data-e2e-ink]::marker {
  -webkit-text-fill-color: currentcolor !important;
}
[data-e2e-ink] {
  border-color: transparent !important;
  box-shadow: none !important;
  outline: none !important;
}
"""

_DECODE_JS = """
async (b64) => {
  const img = new Image();
  img.src = 'data:image/png;base64,' + b64;
  await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const data = ctx.getImageData(0, 0, img.width, img.height).data;
  const counts = new Map();
  const at = (x, y) => (y * img.width + x) * 4;
  const vote = (x, y) => {
    const i = at(x, y);
    const key = `${data[i] >> 3},${data[i + 1] >> 3},${data[i + 2] >> 3}`;
    const entry = counts.get(key) || {n: 0, i};
    entry.n += 1;
    counts.set(key, entry);
  };
  for (let x = 0; x < img.width; x++) { vote(x, 0); vote(x, img.height - 1); }
  for (let y = 0; y < img.height; y++) { vote(0, y); vote(img.width - 1, y); }
  let best = null;
  for (const entry of counts.values()) if (!best || entry.n > best.n) best = entry;
  const bg = [data[best.i], data[best.i + 1], data[best.i + 2]];
  const rows = [];
  for (let y = 0; y < img.height; y++) {
    let row = '';
    for (let x = 0; x < img.width; x++) {
      const i = at(x, y);
      const d = Math.abs(data[i] - bg[0]) + Math.abs(data[i + 1] - bg[1]) + Math.abs(data[i + 2] - bg[2]);
      row += d > 90 ? '1' : '0';
    }
    rows.push(row);
  }
  // A screenshot at a fractional offset picks up a sliver of the neighbouring
  // box along its edges; blank fully painted edge rows and columns.
  const full = '1'.repeat(img.width);
  const blank = '0'.repeat(img.width);
  for (let y = 0; y < rows.length && rows[y] === full; y++) rows[y] = blank;
  for (let y = rows.length - 1; y >= 0 && rows[y] === full; y--) rows[y] = blank;
  const column = (x) => rows.every((row) => row[x] === '1');
  const clear = (x) => rows.forEach((row, y) => { rows[y] = row.slice(0, x) + '0' + row.slice(x + 1); });
  for (let x = 0; x < img.width && column(x); x++) clear(x);
  for (let x = img.width - 1; x >= 0 && column(x); x--) clear(x);
  return rows;
}
"""


@dataclass(frozen=True)
class Ink:
    """The non-background pixels of an element, as rows of '0'/'1'."""

    rows: tuple[str, ...]

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    @property
    def columns(self) -> list[int]:
        return [x for x in range(self.width) if any(row[x] == "1" for row in self.rows)]

    def bbox(self) -> tuple[int, int, int, int]:
        cols = self.columns
        lines = [y for y, row in enumerate(self.rows) if "1" in row]
        assert cols and lines, "nothing was drawn"
        return cols[0], lines[0], cols[-1] + 1, lines[-1] + 1

    @property
    def center_fraction(self) -> float:
        """Horizontal centre of mass of the ink, 0 = left edge, 1 = right edge.

        A centre of mass rather than of the bounding box, so symmetric
        decoration (rounded corners of a pill button) cannot drown out the
        icon whose side is being asked about.
        """
        self.bbox()
        xs = [x for row in self.rows for x, pixel in enumerate(row) if pixel == "1"]
        return (sum(xs) / len(xs) + 0.5) / self.width

    def cropped(self) -> list[str]:
        x0, y0, x1, y1 = self.bbox()
        return [row[x0:x1] for row in self.rows[y0:y1]]


# Only the part of the element the user can see: a cell in a scrolled table is
# partly hidden by its scroll container, and that part has nothing to say.
_VISIBLE_RECT_JS = """
el => {
  let r = el.getBoundingClientRect();
  let left = r.left, top = r.top, right = r.right, bottom = r.bottom;
  for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) {
    if (getComputedStyle(node).overflowX === 'visible') continue;
    const c = node.getBoundingClientRect();
    left = Math.max(left, c.left);
    right = Math.min(right, c.right);
  }
  left = Math.max(left, 0);
  right = Math.min(right, document.documentElement.clientWidth);
  top = Math.max(top, 0);
  bottom = Math.min(bottom, window.innerHeight);
  return {x: left, y: top, width: Math.max(1, right - left), height: Math.max(1, bottom - top)};
}
"""


def ink(locator, *, children_only: bool = False) -> Ink:
    """Screenshot an element with its text hidden and keep only the ink.

    Background icons, pseudo-element glyphs and list markers stay visible, so
    what is left is exactly the decoration whose direction is under test.
    ``::marker`` inherits the text fill and ignores attempts to restore it, so
    for a ``<summary>`` pass ``children_only`` to hide only the text inside it.
    """
    page = locator.page
    page.evaluate(
        """css => {
          if (!document.getElementById('e2e-ink-style')) {
            const style = document.createElement('style');
            style.id = 'e2e-ink-style';
            style.textContent = css;
            document.head.appendChild(style);
          }
        }""",
        _HIDE_TEXT_CSS,
    )
    locator.scroll_into_view_if_needed()
    locator.evaluate(
        "(el, mode) => el.setAttribute('data-e2e-ink', mode)", "children" if children_only else ""
    )
    try:
        clip = locator.evaluate(_VISIBLE_RECT_JS)
        png = page.screenshot(clip=clip, animations="disabled", caret="hide")
    finally:
        locator.evaluate("el => el.removeAttribute('data-e2e-ink')")
    rows = page.evaluate(_DECODE_JS, base64.b64encode(png).decode("ascii"))
    return Ink(tuple(rows))


def _resample(rows: list[str], width: int, height: int) -> list[list[bool]]:
    h, w = len(rows), len(rows[0])
    return [
        [rows[min(h - 1, y * h // height)][min(w - 1, x * w // width)] == "1" for x in range(width)]
        for y in range(height)
    ]


def _iou(a: list[list[bool]], b: list[list[bool]]) -> float:
    inter = union = 0
    for row_a, row_b in zip(a, b, strict=True):
        for pa, pb in zip(row_a, row_b, strict=True):
            inter += pa and pb
            union += pa or pb
    return inter / union if union else 1.0


def _invert(rows: list[str]) -> list[str]:
    """The unpainted pixels enclosed by paint on the same row."""
    inverted = []
    for row in rows:
        first, last = row.find("1"), row.rfind("1")
        if first < 0:
            inverted.append("0" * len(row))
            continue
        inside = row[first : last + 1].translate(str.maketrans("01", "10"))
        inverted.append("0" * first + inside + "0" * (len(row) - last - 1))
    return inverted


def mirror_scores(reference: Ink, candidate: Ink, *, holes: bool = False) -> tuple[float, float]:
    """(overlap with the mirrored reference, overlap with the reference as is).

    With ``holes`` the comparison runs on the unpainted pixels inside the
    glyph's box instead: a white arrow cut out of a filled circle is all
    circle and no arrow as far as the painted pixels are concerned.
    """
    ref, cand = reference.cropped(), candidate.cropped()
    if holes:
        ref, cand = _invert(ref), _invert(cand)
    width = max(len(ref[0]), len(cand[0]), 8)
    height = max(len(ref), len(cand), 8)
    ref_px, cand_px = _resample(ref, width, height), _resample(cand, width, height)
    mirrored = [list(reversed(row)) for row in ref_px]
    return _iou(mirrored, cand_px), _iou(ref_px, cand_px)


def assert_mirrored(ltr: Ink, rtl: Ink, what: str) -> None:
    """The RTL rendering is the horizontal mirror image of the LTR one."""
    holes = False
    self_mirror, _ = mirror_scores(ltr, ltr)
    if self_mirror >= 0.85:
        holes = True
        self_mirror, _ = mirror_scores(ltr, ltr, holes=True)
    assert self_mirror < 0.85, f"{what}: the LTR glyph is symmetric, nothing to compare"
    as_mirror, as_is = mirror_scores(ltr, rtl, holes=holes)
    # A 9-10 px glyph loses a pixel or two to anti-aliasing between font
    # renderers (CI scored a correctly mirrored chevron 0.58), so the
    # absolute floor stays loose and the margin over "as is" decides.
    # The boundary is inclusive because a correctly mirrored small calendar arrow can score exactly 0.50.
    assert as_mirror >= 0.5 and as_mirror > as_is + 0.2, (
        f"{what}: the RTL glyph does not point the other way "
        f"(overlap with the mirrored LTR glyph {as_mirror:.2f}, unmirrored {as_is:.2f})\n"
        + "\n".join(ltr.cropped())
        + "\n--- rtl ---\n"
        + "\n".join(rtl.cropped())
    )


def assert_same_shape(ltr: Ink, rtl: Ink, what: str) -> None:
    """The RTL rendering is the same glyph, unmirrored (symmetric icons)."""
    _, as_is = mirror_scores(ltr, rtl)
    assert as_is > 0.6, f"{what}: the icon changed shape between directions ({as_is:.2f})"


# -- colour ---------------------------------------------------------------------


def _channel(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    light, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


_COLOURS_JS = """
el => {
  const parse = (value) => {
    const m = value.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const parts = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return {rgb: parts.slice(0, 3), alpha: parts.length > 3 ? parts[3] : 1};
  };
  let bg = null;
  for (let node = el; node; node = node.parentElement) {
    const c = parse(getComputedStyle(node).backgroundColor);
    if (c && c.alpha > 0.5) { bg = c.rgb; break; }
  }
  if (!bg) bg = [255, 255, 255];
  const fg = parse(getComputedStyle(el).color);
  return {fg: fg ? fg.rgb : [0, 0, 0], bg};
}
"""


def colours(locator) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(text colour, effective background colour) of an element."""
    result = locator.evaluate(_COLOURS_JS)
    return tuple(result["fg"]), tuple(result["bg"])
