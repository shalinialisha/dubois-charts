"""
Shared text-fitting utilities for the dubois_charts package.

WHY THIS MODULE EXISTS
-----------------------
dubois_charts/charts/plate51.py recreates one specific historical drawing with one
specific title, one specific pair of category labels ("SLAVES" / "FREE"),
and nine specific years. Every font size and x/y position in that module
was hand-tuned to fit that exact text. That's fine for a fixed historical
recreation, but it is exactly the wrong way to build a chart function other
people will call with their own data -- their titles will be longer or
shorter, they might have 3 categories or 30, and their labels might be
"Q1" or "Percentage of Households Below the Poverty Line". Hardcoded font
sizes and positions will silently overflow, overlap, or clip for almost
any input that isn't the original demo data.

The fix used throughout this package, and the standard fix used by every
mature plotting library, is to stop guessing and instead measure:

  - matplotlib itself does this internally for `tight_layout()` and
    legend placement: it draws the text once, asks the renderer for the
    real pixel bounding box via `Text.get_window_extent()`, and adjusts
    layout from that.
  - plotly's `automargin` and `uniformtext` do the same thing: measure
    rendered label size, then shrink font size or expand margins to fit.
  - ggplot2's `scales::label_wrap()` / `element_text(angle=...)` wrap or
    rotate axis text once labels are measured to be too long for the
    available space.

Every function below follows the same pattern: render off-screen, measure
the real pixel size, then either shrink the font, wrap the text onto more
lines, rotate it, or -- as a last resort -- fall back to a legend instead
of an in-place label that has nowhere left to go. Every chart type in this
package (area charts today, and any future spiral/butterfly/bar chart
modules) should use these instead of hardcoding sizes for the demo data.
"""

import re
from typing import List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.text import Text

# Where a line may break: any whitespace but a no-break space.
_WORD_BREAK = re.compile(r'[^\S\u00a0]+')


def get_renderer(fig):
    """
    Get a usable renderer for `fig`, drawing it once first if necessary,
    then reusing that same renderer for every subsequent call.

    `Text.get_window_extent()` returns a zero-size box until the figure
    has been drawn at least once, so every measurement function in this
    module routes through here first. The renderer is cached on the
    figure object after that first draw rather than re-drawn on every
    call: text-extent computation only depends on the renderer's font
    metrics (fontsize, family, weight, dpi), not on the current pixel
    buffer reflecting every artist added since, so a full
    `fig.canvas.draw()` -- which re-renders every already-placed patch,
    line, and texture image -- is pure waste on the second and every
    later call once a renderer already exists.

    That waste compounds badly for any chart that measures text
    *after* placing a lot of expensive-to-redraw content: found while
    building snake_chart, whose per-segment label-fitting loop runs
    after all of that segment's rectangle-and-texture pieces are already
    drawn, so segment N's label fit was redrawing everything from
    segments 0..N-1 on every single measurement call inside it. A
    30-segment chart took over two minutes before this fix and well
    under a second after it.
    """
    cached = getattr(fig, '_dubois_cached_renderer', None)
    if cached is not None:
        return cached
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    fig._dubois_cached_renderer = renderer
    return renderer


def measure_text_px(fig, text: str, fontsize: float, fontfamily: str = 'monospace',
                     fontweight: str = 'normal') -> Tuple[float, float]:
    """
    Render `text` off-screen (well outside the visible axes) and return its
    real (width_px, height_px) at the given font size.

    This is the building block every other function in this module uses.
    It's a little wasteful to draw-and-discard a throwaway text object for
    every measurement, but it's exactly what matplotlib does internally,
    and chart construction happens once per render, not in a hot loop, so
    the cost is negligible in practice.
    """
    # The same strings get measured at the same sizes many times over (a
    # pie with 60 slices re-checks every label at every size each time its
    # layout is revised -- about 15,000 measurements), so each figure keeps
    # what it has measured. A size in pixels depends only on the text, the
    # font and the figure's dpi, which doesn't change.
    family_key = fontfamily if isinstance(fontfamily, str) else tuple(fontfamily)
    key = (text, float(fontsize), family_key, fontweight)
    sizes = fig.__dict__.setdefault('_dubois_text_sizes', {})
    if key in sizes:
        return sizes[key]
    # One probe per figure, never added to it, given each text in turn:
    # making a text object for every measurement and removing it again
    # was a third of the cost of measuring (a 300-piece snake chart
    # measures about 3,000 different texts).
    probe = fig.__dict__.get('_dubois_text_probe')
    if probe is None:
        probe = Text(-10, -10, '')
        probe.set_figure(fig)
        probe.set_transform(fig.transFigure)
        fig._dubois_text_probe = probe
    probe.update({'text': text, 'fontsize': fontsize, 'fontfamily': fontfamily,
                  'fontweight': fontweight, 'parse_math': plt.rcParams['text.parse_math'],
                  'usetex': plt.rcParams['text.usetex']})
    bbox = probe.get_window_extent(renderer=get_renderer(fig))
    sizes[key] = (bbox.width, bbox.height)
    return sizes[key]


def fit_fontsize_to_width(fig, text: str, max_width_px: float, fontfamily: str = 'monospace',
                           fontweight: str = 'bold', max_fontsize: float = 24,
                           min_fontsize: float = 6) -> float:
    """
    Return the largest font size in [min_fontsize, max_fontsize] at which
    `text` renders no wider than `max_width_px`.

    Uses a binary search over measured widths (the same idea as plotly's
    `uniformtext` autosizing) rather than a character-count heuristic,
    which breaks down for anything but a fixed-width font and a fixed
    string of digits.

    If even `min_fontsize` doesn't fit, returns `min_fontsize` anyway --
    callers should combine this with `wrap_text_to_width` or truncate in
    that case rather than shrinking text into illegibility.
    """
    if not text:
        return max_fontsize

    lo, hi = min_fontsize, max_fontsize
    # A few iterations of bisection is plenty of precision for font sizes
    for _ in range(12):
        mid = (lo + hi) / 2
        w, _ = measure_text_px(fig, text, mid, fontfamily, fontweight)
        if w <= max_width_px:
            lo = mid
        else:
            hi = mid
    return lo


def wrap_text_to_width(fig, text: str, max_width_px: float, fontsize: float,
                        fontfamily: str = 'monospace', fontweight: str = 'bold',
                        max_lines: Optional[int] = None) -> List[str]:
    """
    Word-wrap `text` into lines that each render no wider than
    `max_width_px` at the given font size, measuring real rendered width
    rather than counting characters.

    If a single word is itself wider than `max_width_px` (a very long
    identifier with no spaces), it gets hard-broken to fit. If `max_lines`
    is given and the text still doesn't fit after wrapping, the last line
    is truncated with an ellipsis -- the same graceful-degradation pattern
    plotly and CSS `text-overflow: ellipsis` use, rather than silently
    overflowing or crashing.

    A no-break space (U+00A0) holds the words either side of it together,
    as it does in a word processor: the charts put one between a number
    and its unit, so "152 €" never ends a line at "152".
    """
    words = _WORD_BREAK.split(text.strip(' \t\r\n'))
    words = [w for w in words if w]
    if not words:
        return ['']

    lines: List[str] = []
    current = ''

    def width_of(s: str) -> float:
        w, _ = measure_text_px(fig, s, fontsize, fontfamily, fontweight)
        return w

    for word in words:
        candidate = f'{current} {word}'.strip()
        if width_of(candidate) <= max_width_px or not current:
            # Still fits, or it's the first word on the line and has no
            # choice but to go here -- handle an over-long single word.
            if not current and width_of(word) > max_width_px:
                lines.extend(_hard_break_word(fig, word, max_width_px, fontsize,
                                               fontfamily, fontweight))
                current = ''
            else:
                current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while width_of(last + '\u2026') > max_width_px and len(last) > 1:
            last = last[:-1]
        lines[-1] = last.rstrip() + '\u2026'

    return lines


def _hard_break_word(fig, word: str, max_width_px: float, fontsize: float,
                      fontfamily: str, fontweight: str) -> List[str]:
    """Break a single over-long word across multiple lines, character by
    character, for the rare case where wrapping alone can't help."""
    pieces, current = [], ''
    for ch in word:
        candidate = current + ch
        w, _ = measure_text_px(fig, candidate, fontsize, fontfamily, fontweight)
        if w <= max_width_px or not current:
            current = candidate
        else:
            pieces.append(current)
            current = ch
    if current:
        pieces.append(current)
    return pieces


def fit_title(fig, text: str, max_width_px: float, start_fontsize: float,
              fontfamily: str = 'monospace', fontweight: str = 'bold',
              min_fontsize: float = 9, max_lines: int = 3) -> Tuple[List[str], float]:
    """
    Fit a title into the available width, preferring to shrink font size a
    little before wrapping onto more lines, and wrapping before shrinking
    all the way down to illegibility.

    This mirrors how word processors and slide software auto-fit title
    text: try it at the requested size; if it overflows by a modest
    amount, shrink slightly; if it's too long to shrink into one line
    reasonably, wrap; only fall back to the minimum font size once
    wrapping alone has done what it can.

    Returns (lines, fontsize) -- callers use `len(lines)` to reserve the
    right amount of vertical space rather than assuming a title is always
    one line.
    """
    # Try shrinking (down to a "still readable" floor) to fit on one line first.
    one_line_fontsize = fit_fontsize_to_width(
        fig, text, max_width_px, fontfamily, fontweight,
        max_fontsize=start_fontsize, min_fontsize=max(min_fontsize, start_fontsize * 0.7)
    )
    w, _ = measure_text_px(fig, text, one_line_fontsize, fontfamily, fontweight)
    if w <= max_width_px:
        return [text], one_line_fontsize

    # Doesn't fit on one line even after a modest shrink -- wrap instead,
    # at a size a bit smaller than the original ask so wrapped lines don't
    # dominate the layout.
    wrap_fontsize = max(min_fontsize, start_fontsize * 0.85)
    lines = wrap_text_to_width(fig, text, max_width_px, wrap_fontsize,
                                fontfamily, fontweight, max_lines=max_lines)
    return lines, wrap_fontsize


def fit_fontsize_to_height(fig, max_height_px: float, fontfamily: str = 'monospace',
                            fontweight: str = 'bold', max_fontsize: float = 24,
                            min_fontsize: float = 6, sample_text: str = 'Xg') -> float:
    """
    Return the largest font size in [min_fontsize, max_fontsize] whose
    single-line rendered height fits within `max_height_px`.

    `sample_text` should contain both an ascender and a descender (the
    default 'Xg' does) so the measured height reflects a realistic line,
    not just flat digits.
    """
    lo, hi = min_fontsize, max_fontsize
    for _ in range(12):
        mid = (lo + hi) / 2
        _, h = measure_text_px(fig, sample_text, mid, fontfamily, fontweight)
        if h <= max_height_px:
            lo = mid
        else:
            hi = mid
    return lo


def fit_label_in_box(fig, text: str, max_width_px: float, max_height_px: float,
                      fontfamily: str = 'monospace', fontweight: str = 'bold',
                      max_fontsize: float = 20, min_fontsize: float = 7,
                      max_lines: int = 2) -> Optional[Tuple[List[str], float]]:
    """
    Try to fit `text` (e.g. an in-band series label like the original's
    "FREE - LIBRE") inside a box of the given size, shrinking and then
    wrapping as needed.

    Returns (lines, fontsize) if it fits within `max_lines` at
    `min_fontsize` or larger, or None if there's genuinely no room --
    callers should treat None as a signal to fall back to an external
    legend instead of forcing an illegible or overflowing label, the same
    way a pie chart moves a thin slice's label out to a callout instead of
    stuffing it inside a sliver too small to hold it.
    """
    # A font size that's fine for *width* can still be too tall for the
    # box on its own (one line can already exceed max_height_px) -- cap
    # the width search by the height constraint first so we don't pick a
    # fontsize that only "fits" by ignoring height, then try to fix it by
    # wrapping into MORE lines at that same too-large size (which only
    # makes total height worse, not better).
    height_ceiling = fit_fontsize_to_height(fig, max_height_px, fontfamily, fontweight,
                                             max_fontsize=max_fontsize, min_fontsize=min_fontsize)
    ceiling = max(min(max_fontsize, height_ceiling), min_fontsize)

    fontsize = fit_fontsize_to_width(fig, text, max_width_px, fontfamily, fontweight,
                                      max_fontsize=ceiling, min_fontsize=min_fontsize)
    w, h = measure_text_px(fig, text, fontsize, fontfamily, fontweight)
    if w <= max_width_px and h <= max_height_px:
        return [text], fontsize

    # One line doesn't fit even at the height-capped size -- try wrapping
    # into progressively more lines, each time solving for the fontsize
    # that lets that many stacked lines fit the height budget, then
    # checking whether wrapping at that size actually fits the width too.
    _, ref_h = measure_text_px(fig, 'Xg', 10.0, fontfamily, fontweight)
    line_spacing = 1.15
    for n_lines in range(2, max_lines + 1):
        max_fs_for_lines = (max_height_px / line_spacing / n_lines) * (10.0 / ref_h)
        candidate_fontsize = max(min(max_fs_for_lines, max_fontsize), min_fontsize)

        # Ask for the wrap this text actually needs, uncapped -- NOT
        # wrap_text_to_width's own max_lines parameter. That parameter
        # makes wrap_text_to_width truncate-with-ellipsis to comply
        # (its own documented, correct behavior for callers that want
        # exactly N lines no matter what), which meant the `len(lines) >
        # n_lines` check below could never fire: the truncated result
        # already satisfies it by construction. The result was
        # fit_label_in_box silently returning an ellipsis-truncated
        # label as if it were a clean fit -- exactly the "return None
        # instead of forcing something broken" contract this function
        # documents, quietly violated. Asking for the untruncated wrap
        # here and checking its real length against n_lines ourselves
        # is what actually enforces that contract.
        lines = wrap_text_to_width(fig, text, max_width_px, candidate_fontsize,
                                    fontfamily, fontweight, max_lines=None)
        if len(lines) > n_lines:
            continue

        max_line_w = max(measure_text_px(fig, ln, candidate_fontsize, fontfamily, fontweight)[0]
                          for ln in lines)
        _, single_h = measure_text_px(fig, 'Xg', candidate_fontsize, fontfamily, fontweight)
        total_h = single_h * len(lines) * line_spacing
        if max_line_w <= max_width_px and total_h <= max_height_px:
            return lines, candidate_fontsize

    return None


def choose_tick_label_style(fig, labels: Sequence[str], available_width_px: float,
                             n_labels: int, fontsize: float, fontfamily: str = 'monospace',
                             fontweight: str = 'bold') -> dict:
    """
    Decide how to render a row of category tick labels (chart x-axis, or
    any similar row of repeated short labels) so they don't collide.

    This mirrors the escalating strategies seaborn/matplotlib and ggplot2
    use for crowded axis text, tried in order of "least disruptive first":

      1. As given, horizontal, at the requested font size.
      2. Shrunk to the largest size that lets every label fit its slot.
      3. Rotated 45 degrees at the requested size, if shrinking alone
         would go below a readable floor.
      4. Thinned out (show every Nth label) as a last resort for a large
         number of categories, the same way matplotlib's own tick locators
         drop labels rather than overlapping them.

    Returns a dict: {'fontsize': float, 'rotation': float, 'step': int}
    where `step` means "render every `step`-th label" (1 = all of them).
    """
    if n_labels == 0:
        return {'fontsize': fontsize, 'rotation': 0, 'step': 1}

    slot_width = available_width_px / n_labels
    widest = max((measure_text_px(fig, str(lbl), fontsize, fontfamily, fontweight)[0]
                  for lbl in labels), default=0)

    if widest <= slot_width * 0.92:
        return {'fontsize': fontsize, 'rotation': 0, 'step': 1}

    shrunk = fit_fontsize_to_width(fig, max(labels, key=len) if labels else '',
                                    slot_width * 0.92, fontfamily, fontweight,
                                    max_fontsize=fontsize, min_fontsize=fontsize * 0.55)
    if shrunk >= fontsize * 0.75:
        return {'fontsize': shrunk, 'rotation': 0, 'step': 1}

    # Rotating buys roughly a `slot_width / cos(45)` effective width for
    # the same footprint, without shrinking all the way to unreadable.
    rotated_w, _ = measure_text_px(fig, max(labels, key=len) if labels else '',
                                    fontsize, fontfamily, fontweight)
    if rotated_w * 0.71 <= slot_width * 2.2:  # cos(45) ~ 0.71, allow overlap into neighbours' vertical space
        return {'fontsize': fontsize, 'rotation': 45, 'step': 1}

    # Still too crowded (many long labels): thin them out.
    step = 1
    while slot_width * step < widest * 0.92 and step < n_labels:
        step += 1
    return {'fontsize': fontsize, 'rotation': 45 if step == 1 else 0, 'step': step}
