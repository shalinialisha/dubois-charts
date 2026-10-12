"""
General-purpose Du Bois-style spiral chart.

Same relationship to plate51.py as the other general chart types have
(see GENERAL_ENGINE_README.md): arbitrary categories, arbitrary label
length, a title of whatever length the caller has, sized from real
measurements at render time.

This is the most structurally different chart type in the package so
far. `area.py`, `bar.py`, and `butterfly.py` all place labels along a
straight edge, where "does this collide with its neighbor" is a 1-D
question (do these two x-ranges, or two y-ranges, overlap). A spiral
chart's labels sit at whatever angle their point on the curve happens to
land at, all the way around a circle -- collision has to be checked as
actual 2-D bounding-box overlap between labels that can approach each
other from any direction, not just "the next one over on the same axis".
See `_collides` below for how that's handled, and
GENERAL_ENGINE_README.md for what testing against a deliberately crowded
input found.

Inspired by Du Bois's spirals -- in Plate 11, "City and Rural Population.
1890.", the bar for the 734,952 people living in the country and
villages is so much longer than the cities' that it coils up into a
spiral. Here the spiral is a line chart wound round a centre: each
point's place in the sequence sets its angle, and its value its distance
from the centre.
"""

import warnings
from typing import List, Optional, Sequence, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects

from dubois_charts import colors as dubois_colors
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import (
    COLOR_CREAM,
    get_font as _get_font,
    text_color_for as _text_color_for,
    validate_figsize,
    display_caps,
    literal_text,
    font_stack,
    as_numbers,
    named_labels,
    default_value_format,
    check_value_format,
    title_top,
    aligned,
    number_text,
    as_datetime,
    _midnights,
)


def _turn_per_year(categories) -> Optional[float]:
    """
    For more than a year of monthly or quarterly dates, the number of turns
    that makes each a year -- so every January is at the top and each loop
    is a year -- or None. At a turn for every seven points, four years of
    months made 6.9 turns, and January 2013 came at 9 o'clock.
    """
    dates = [as_datetime(c) for c in categories]
    if not dates or any(d is None for d in dates):
        return None
    days = _midnights(dates)
    if any(d.day != 1 or d.hour or d.minute for d in days):
        return None
    months = np.array([d.year * 12 + d.month - 1 for d in days])
    gaps = set(np.diff(months).tolist())
    if gaps == {1} and len(months) > 12:
        return (len(months) - 1) / 12
    if gaps == {3} and len(months) > 4:
        return (len(months) - 1) / 4
    return None


def _warn_if_loops_meet(radii, vals, revolutions: float, px_per_data: float,
                        line_px: float) -> None:
    """
    Warn when the spiral's loops run into each other at many of its
    points, so the line can't be followed from one turn to the next: the
    place one turn on from a point is no farther out than the line is wide.

    Found on real data. Monthly carbon dioxide at Mauna Loa since 1958
    (313 to 414 parts per million) drew 62 turns as one solid red ring;
    monthly births, 2000-2014, a tangle of fifteen loops; a city's
    average high by month, four years of the same loop drawn on itself.
    The chart was drawn without a word.
    """
    n = len(radii)
    per_turn = (n - 1) / revolutions
    idx = np.arange(n)
    later = idx + per_turn
    inside = later <= n - 1
    if revolutions <= 1 or inside.sum() < 6:     # a handful of points can't tangle much
        return
    gap_px = (np.interp(later[inside], idx, radii) - radii[inside]) * px_per_data
    share = float(np.mean(gap_px < 1.5 * line_px))
    if share < 0.25:
        return
    lo, hi = float(vals.min()), float(vals.max())
    hints = []
    if lo > 0.4 * hi:
        base = format(lo, ',.6g')
        hints.append(f"The values are far from zero next to how much they change ({lo:,.6g} to "
                     f"{hi:,.6g}): chart the change from a baseline instead -- the values minus "
                     f"{base}, say -- and say so in the subtitle.")
    if revolutions > 12:
        hints.append(f"{revolutions:.0f} turns leave each little room: fewer points -- a yearly "
                     f"total or average, say -- would give them more.")
    if not hints:
        hints.append("A spiral suits a series that grows from turn to turn; one that rises and "
                     "falls within each turn, the same every time -- a season's pattern -- reads "
                     "better as a bar or area chart.")
    warnings.warn(
        f"spiral_chart: the loops of the spiral run into each other at {share:.0%} of its "
        f"points, so the line is hard to follow from turn to turn. "
        + ' '.join(hints), UserWarning, stacklevel=4)


@literal_text
def spiral_chart(
    categories: Sequence[str],
    values: Sequence[float],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    color: Optional[str] = None,
    value_format: Optional[str] = None,
    show_value_labels: bool = True,
    revolutions: Optional[float] = None,
    hand_drawn: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled spiral chart for arbitrary ordered data: a
    line wound clockwise from the top, each point's angle set by its
    place in the sequence and its distance from the centre by its value.

    Parameters
    ----------
    categories : Sequence
        One label per point, in the order they come round the spiral
        (e.g. years, in chronological order): text, numbers or dates,
        written as a person would ("2018", "Jan 2024"). Long labels wrap.
    values : Sequence[float]
        One number, zero or more, per category: the larger, the farther
        from the centre, with the largest at the outer edge. Distance
        isn't strictly proportional to value -- a small circle in the
        middle is kept clear, so zero sits on it -- and equal values make
        a circle; values that grow make the spiral widen, as in Du Bois's
        plates. Values far from zero that change little (carbon dioxide
        in parts per million) make loops that run into each other: chart
        the change from a baseline instead, and say so in the subtitle.
        When the loops do run together, a warning says so. A
        pandas Series whose index names the categories is matched to them
        by its index.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width. The title is in
        capitals, as on the plates, except words whose mixed case is
        deliberate; the subtitle is as written.
    color : str, optional
        Spiral line color. Defaults to the first color of
        `dubois_charts.colors.get_categorical(1)`.
    value_format : str, optional
        `str.format`-style template for the number shown alongside each
        category's label, e.g. `'{:.0f}'` or `'{:,.0f}'`. By default,
        plain numbers at the data's own precision.
    show_value_labels : bool
        If True, each label has its point's value after its name.
    revolutions : float, optional
        How many full turns the spiral makes from first point to last. By
        default one for every seven points, and at least two -- but for
        monthly or quarterly dates over more than a year, one a year, so
        each January is at the top. Pass it to make several charts alike.
    hand_drawn : bool
        Give the spiral a slight hand-inked wobble instead of a
        perfectly smooth mathematical curve.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        If not given, about 7 inches wide (more for many points, up to
        13) and a little taller, for the title. Labels too wide for the
        room around the spiral make the figure bigger.
    dpi : int
        Dots per inch, for the figure and for `save_path`.
    font : str or sequence of str, optional
        The font for all the text; by default the typewriter face the
        package picks (see the README's "Fonts"). Characters it lacks
        come from an installed font that has them.
    save_path : str, optional
        If given, save the figure here.
    seed : int
        Random seed for the hand-drawn wobble, so output is reproducible.

    Not every point is labelled: the last, highest, first and lowest
    come first, then others spread round the spiral, up to nine, where
    there's room. A label sits beside its point, or outside the spiral
    with a line to it.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = spiral_chart(
    ...     categories=[1870, 1880, 1890, 1900],
    ...     values=[45, 62, 89, 140],
    ...     title='Population Growth',
    ... )
    """
    categories = list(categories)
    values = values if hasattr(values, '__len__') else list(values)
    n = len(categories)
    if n < 2:
        raise ValueError("`spiral_chart` needs at least 2 points to draw a curve.")
    if len(values) != n:
        raise ValueError(
            f"`values` has {len(values)} entries but there are {n} categories."
        )
    cat_labels = named_labels(categories, "`categories`")
    vals = as_numbers(aligned(values, cat_labels, "`values`"), "`values`", names=cat_labels)
    negative = [f'{cat_labels[i]!r} ({vals[i]:g})' for i in np.where(vals < 0)[0]]
    if negative:
        raise ValueError(
            f"`values` has a negative value for {', '.join(negative[:5])}"
            f"{' and more' if len(negative) > 5 else ''}. A value is a distance from the "
            f"centre, so every value must be zero or more. To chart values with a sign, add "
            f"the same amount to all of them first, and say so in the subtitle.")
    if value_format is None:
        value_format = default_value_format(vals)
    check_value_format(value_format)

    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    color = color or dubois_colors.get_categorical(1)[0]

    if revolutions is None:
        # At least 2 full turns by default: with only ~1 turn, the curve
        # only ever reaches its outer radius near the single point where
        # it starts and ends, leaving most of the reserved circular
        # region empty (found by testing with 8 points, which rounds to
        # a single, lopsided loop rather than anything visually reading
        # as a "spiral") -- more turns both look more like the source
        # material's dense coils and use the reserved space more evenly,
        # since every angle then gets crossed by an inner AND an outer
        # loop rather than just one pass at a middling radius.
        revolutions = _turn_per_year(categories) or max(2.0, n / 7.0)
    elif revolutions <= 0:
        raise ValueError(
            f"`revolutions` must be positive (it's how many full turns "
            f"the spiral makes); got {revolutions!r}. A spiral needs at "
            "least some angular sweep to read as a spiral rather than a "
            "straight line."
        )

    if figsize is None:
        side = min(max(7.0, 5.5 + n * 0.03), 13.0)
        figsize = (side, side * 1.08)  # a touch taller, to leave room for the title

    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi
    fig_h_px = figsize[1] * dpi

    # ------------------------------------------------------------------
    # Title block (identical pattern to every other chart in the package).
    # ------------------------------------------------------------------
    margin_px = 0.04 * fig_w_px
    title_max_width = fig_w_px - 2 * margin_px
    title_lines, title_fs = ([], 0)
    subtitle_lines, subtitle_fs = ([], 0)
    if title:
        title_lines, title_fs = tu.fit_title(fig, display_caps(title), title_max_width,
                                              start_fontsize=16, fontfamily=font,
                                              fontweight='bold', min_fontsize=10, max_lines=3)
    if subtitle:
        subtitle_lines, subtitle_fs = tu.fit_title(fig, subtitle, title_max_width,
                                                    start_fontsize=11, fontfamily=font,
                                                    fontweight='normal', min_fontsize=8, max_lines=2)
    _, title_line_h = (tu.measure_text_px(fig, 'Xg', title_fs, font, 'bold')
                        if title_lines else (0, 0))
    _, subtitle_line_h = (tu.measure_text_px(fig, 'Xg', subtitle_fs, font, 'normal')
                           if subtitle_lines else (0, 0))
    title_block_px = (len(title_lines) * title_line_h * 1.35
                       + len(subtitle_lines) * subtitle_line_h * 1.35
                       + (18 if title_lines or subtitle_lines else 0))

    # ------------------------------------------------------------------
    # Label content: figure out what text goes with each point BEFORE
    # solving the geometry, since the margin the spiral needs depends on
    # how wide the widest label is, which depends on font size, which
    # (per the usual shrink-before-wrap policy) depends on how much room
    # there roughly is -- resolved below with direct algebra rather than
    # guessing, using a representative starting font size first and
    # trusting the margin equation to size around whatever that produces.
    # ------------------------------------------------------------------
    label_fs = 10.5
    label_fs_min = 7.5
    point_texts = []
    for i in range(n):
        if show_value_labels:
            point_texts.append(f"{cat_labels[i]}  {number_text(value_format, vals[i])}")
        else:
            point_texts.append(cat_labels[i])
    widest_label_px = max(tu.measure_text_px(fig, t, label_fs, font, 'bold')[0]
                          for t in point_texts)
    # A single very long label (long category name + value) shouldn't be
    # allowed to blow the whole spiral's margin out to something absurd --
    # shrink it toward the floor first, the same escalation used for
    # category columns in bar.py and butterfly.py, before accepting
    # whatever width results.
    max_reasonable_label_px = fig_w_px * 0.22
    if widest_label_px > max_reasonable_label_px:
        label_fs = tu.fit_fontsize_to_width(
            fig, max(point_texts, key=len), max_reasonable_label_px, font, 'bold',
            max_fontsize=label_fs, min_fontsize=label_fs_min
        )
        # Anything still too wide at the smallest size wraps onto more
        # lines. It used to stay one line, and the figure was scaled up to
        # fit it: one long label turned a 7-inch spiral into 18 inches.
        # (Only those: wrapping closes up the two spaces between a name
        # and its number, and it was done to every label, so "Period 3
        # name 7.5" lost the gap that shows where the name ends.)
        point_texts = [t if tu.measure_text_px(fig, t, label_fs, font, 'bold')[0]
                       <= max_reasonable_label_px
                       else '\n'.join(tu.wrap_text_to_width(fig, t, max_reasonable_label_px,
                                                            label_fs, font, 'bold'))
                       for t in point_texts]
        widest_label_px = max(tu.measure_text_px(fig, t, label_fs, font, 'bold')[0]
                              for t in point_texts)

    # ------------------------------------------------------------------
    # Geometry: solve for the data-unit radius that, once the widest
    # label's pixel width is converted through the eventual data-to-pixel
    # scale, still leaves the whole spiral (labels included) inside a
    # square axes of known pixel size. Solved directly (see module
    # docstring's algebra in GENERAL_ENGINE_README.md) rather than by
    # guess-and-check, so it's exact on the first try regardless of how
    # many points or how long the labels are.
    # ------------------------------------------------------------------
    axes_top_frac = 1 - title_block_px / fig_h_px
    axes_bottom_frac = 14 / fig_h_px
    side_frac = min(axes_top_frac - axes_bottom_frac, 1.0)
    axes_side_px = side_frac * min(fig_w_px, fig_h_px)

    r_value_span = 1.0  # the values' own contribution to radius, in data units
    r_base = 0.12        # small nonzero starting radius, so early points aren't at a point
    r_max_value_only = r_base + r_value_span

    label_gap_px = 10
    # Room outside the outermost loop for the widest label plus a gap on
    # each side of it, so a label can also go out there with a leader line.
    needed_px = widest_label_px + label_gap_px * 2.5
    shrink_factor = 1 - 2 * needed_px / axes_side_px
    if shrink_factor <= 0.35:
        # Labels alone would eat most or all of the available square --
        # grow the figure instead of letting the spiral collapse toward
        # nothing, the same "grow the canvas, don't shrink the content
        # into uselessness" choice bar.py makes for a rotated tick label
        # that doesn't fit its margin.
        needed_total_side_px = 2 * needed_px / 0.55  # solve for shrink_factor == 0.55
        scale = needed_total_side_px / axes_side_px
        fig_w_px *= scale
        fig_h_px *= scale
        fig.set_size_inches(fig_w_px / dpi, fig_h_px / dpi, forward=True)
        axes_side_px = side_frac * min(fig_w_px, fig_h_px)
        shrink_factor = 1 - 2 * needed_px / axes_side_px

    R_total = r_max_value_only / shrink_factor
    px_per_data = axes_side_px / (2 * R_total)

    ax = fig.add_axes([
        (fig_w_px / 2 - axes_side_px / 2) / fig_w_px if fig_w_px else 0.0,
        axes_bottom_frac,
        axes_side_px / fig_w_px if fig_w_px else side_frac,
        axes_side_px / fig_h_px if fig_h_px else side_frac,
    ])
    ax.set_facecolor(background)
    ax.set_xlim(-R_total, R_total)
    ax.set_ylim(-R_total, R_total)
    ax.set_aspect('equal')
    ax.axis('off')

    # ------------------------------------------------------------------
    # Spiral geometry: clockwise from the top, radius scaled by value.
    # ------------------------------------------------------------------
    start_angle = np.pi / 2
    angle_step = (revolutions * 2 * np.pi) / (n - 1)
    thetas = start_angle - np.arange(n) * angle_step
    max_val = vals.max() if vals.max() > 0 else 1.0
    radii = r_base + (vals / max_val) * r_value_span
    _warn_if_loops_meet(radii, vals, revolutions, px_per_data, 2.6 * dpi / 72)

    # Densify with interpolated points between each pair of real data
    # points so the drawn curve is smooth rather than faceted -- same
    # idea as plate51's boundary-line densification, adapted to polar
    # coordinates (interpolate theta and r together, then convert to
    # Cartesian once per interpolated point).
    dense_theta, dense_r = [], []
    for i in range(n - 1):
        # Enough samples for the angle this segment sweeps: a fixed 14 per
        # segment drew a jagged star when a few points spanned many turns.
        pts_per_segment = max(14, int(np.ceil(abs(thetas[i + 1] - thetas[i]) / (2 * np.pi) * 120)))
        seg_t = np.linspace(thetas[i], thetas[i + 1], pts_per_segment, endpoint=False)
        seg_r = np.linspace(radii[i], radii[i + 1], pts_per_segment, endpoint=False)
        dense_theta.append(seg_t)
        dense_r.append(seg_r)
    dense_theta.append([thetas[-1]])
    dense_r.append([radii[-1]])
    dense_theta = np.concatenate(dense_theta)
    dense_r = np.concatenate(dense_r)

    if hand_drawn:
        rng = np.random.RandomState(seed)
        noise = rng.normal(0, r_value_span * 0.004, size=len(dense_r))
        kernel = np.array([0.2, 0.6, 0.2])
        noise = np.convolve(noise, kernel, mode='same')
        noise[0] = noise[-1] = 0
        dense_r = dense_r + noise

    dense_x = dense_r * np.cos(dense_theta)
    dense_y = dense_r * np.sin(dense_theta)

    ax.plot(dense_x, dense_y, color=color, linewidth=2.6, zorder=2,
             solid_capstyle='round', solid_joinstyle='round')

    # Point markers first, then labels. Label and curve checks are done in
    # data units: px_per_data is the same in both directions, so a pixel
    # size converts with one division.
    # (add_artist, not add_patch: the limits are already set, and working
    # out each circle's extent from its curves took a second at 500 points.)
    for i in range(n):
        x_pt, y_pt = radii[i] * np.cos(thetas[i]), radii[i] * np.sin(thetas[i])
        ax.add_artist(plt.Circle((x_pt, y_pt), r_value_span * 0.008,
                                   facecolor=ink_color, edgecolor='none', zorder=3))

    placed_boxes: List[Tuple[float, float, float, float]] = []  # (x0, x1, y0, y1)
    placed_leaders: List[Tuple[np.ndarray, np.ndarray]] = []
    labelled_points: List[np.ndarray] = []
    line_h_px = tu.measure_text_px(fig, 'Xg', label_fs, font, 'bold')[1]
    # A small fixed buffer, not scaled to the label's own height in every
    # direction -- an earlier version used a buffer as large as half the
    # label height, which (combined with a dense multi-revolution spiral
    # where loops sit close together) treated nearly the entire crowded
    # region as "occupied" and silently dropped all but one of sixteen
    # labels in testing. This buffer only needs to keep text off the ink
    # line itself, not clear a wide halo around it.
    curve_buffer_data = (line_h_px * 0.12) / px_per_data
    gap_data = label_gap_px / px_per_data
    # Labels must stay inside the square the spiral was sized into: at
    # revolutions=0.5 a label was pushed out past the edge of the figure.
    limit = R_total - 2 / px_per_data
    curve_a = np.column_stack([dense_x[:-1], dense_y[:-1]])
    curve_b = np.column_stack([dense_x[1:], dense_y[1:]])
    dot_r = r_value_span * 0.008

    def _segments_cross(p, q, a, b):
        """Does segment p-q cross each segment a[k]-b[k]? Also returns how
        far along p-q (0 to 1) each crossing is."""
        d, e = q - p, b - a
        denom = d[0] * e[:, 1] - d[1] * e[:, 0]
        w = a - p
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / denom
            u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / denom
        return (denom != 0) & (t > 0) & (t < 1) & (u >= 0) & (u <= 1), t

    def _loops_crossed(p, q) -> int:
        """How many times a leader from p (a point on the spiral) to q
        crosses the spiral -- not counting where it leaves the line at p."""
        hit, t = _segments_cross(p, q, curve_a, curve_b)
        return int((hit & (t * np.hypot(*(q - p)) > 6 / px_per_data)).sum())

    def _hits_box(p, q, box) -> bool:
        """Does the segment p-q pass through the box (with a pixel or two
        to spare)? Liang-Barsky clipping."""
        pad = 2 / px_per_data
        x0, x1, y0, y1 = box[0] - pad, box[1] + pad, box[2] - pad, box[3] + pad
        dx, dy = q[0] - p[0], q[1] - p[1]
        t0, t1 = 0.0, 1.0
        for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
            if pk == 0:
                if qk < 0:
                    return False
            elif pk < 0:
                t0 = max(t0, qk / pk)
            else:
                t1 = min(t1, qk / pk)
            if t0 > t1:
                return False
        return True

    # Room between labels: two that merely didn't overlap could touch end to
    # end and read as one ("Dec 339,726Jan 329,962").
    apart_x = (line_h_px * 0.6) / px_per_data
    apart_y = (line_h_px * 0.15) / px_per_data

    def _collides(box, leader=None) -> bool:
        bx0, bx1, by0, by1 = box
        if bx0 < -limit or bx1 > limit or by0 < -limit or by1 > limit:
            return True
        if any(bx0 < ox1 + apart_x and bx1 > ox0 - apart_x and by0 < oy1 + apart_y and by1 > oy0 - apart_y
               for (ox0, ox1, oy0, oy1) in placed_boxes):
            return True
        # Not over another label's leader line: placed beside its point
        # after the first point's line was drawn, a label on a tight spiral
        # could sit right across it.
        if any(_hits_box(a, b, box) for a, b in placed_leaders):
            return True
        if leader is not None:
            p, q = np.asarray(leader[0], float), np.asarray(leader[1], float)
            if any(_hits_box(p, q, other) for other in placed_boxes):
                return True
            # Nor across another leader, or through a labelled point.
            if placed_leaders and _segments_cross(
                    p, q, np.array([a for a, _ in placed_leaders]),
                    np.array([b for _, b in placed_leaders]))[0].any():
                return True
            pq = q - p
            for o in labelled_points:
                s = np.clip(np.dot(o - p, pq) / max(np.dot(pq, pq), 1e-12), 0.0, 1.0)
                if np.hypot(*(p + s * pq - o)) < dot_r + 3 / px_per_data:
                    return True
        # Also treat the spiral curve itself as an obstacle -- a label
        # sitting just past ITS OWN point is fine, but with more than one
        # revolution, "radially outward" from an inner-loop point often
        # lands right on top of an OUTER loop passing through the same
        # angular direction.
        in_box = ((dense_x >= bx0 - curve_buffer_data) & (dense_x <= bx1 + curve_buffer_data)
                  & (dense_y >= by0 - curve_buffer_data) & (dense_y <= by1 + curve_buffer_data))
        return bool(in_box.any())

    # Which points get a label, most important first: the last point
    # (usually the most significant in a series), the highest, the first
    # and the lowest; then points at an even step through the series; then,
    # while there's room for more, whichever point is farthest on the page
    # from every point labelled so far. At most nine in all, so each has
    # room. (With many points, trying every one let whichever came first
    # claim the space.)
    #
    # The step was n / 9 points, rounded up. With 60 points at about seven
    # a turn that was every 7th point -- almost exactly one turn apart, so
    # the labels all sat on one ray, queued outward one above another. The
    # step is now one that sends successive labels at least a fifth of a
    # turn round from each other.
    max_labels = 9
    key_points = list(dict.fromkeys([n - 1, int(np.argmax(vals)), 0, int(np.argmin(vals))]))
    if n <= max_labels:
        stepped = list(range(n))
    else:
        turns_per_point = revolutions / (n - 1)

        def _apart(k):
            f = (k * turns_per_point) % 1.0
            return min(f, 1.0 - f)    # in turns: 0 is the same ray, 0.5 opposite sides

        steps = range(max(1, n // 12), -(-n // 7) + 1)
        step = max(steps, key=lambda k: (min(_apart(k), 0.2), -abs(k - n / max_labels)))
        stepped = list(range(0, n, step))
    # On a tight spiral the loops are too close for a label beside most
    # points -- except at the top and bottom, where the loops run level
    # and a line of text fits between them. There, the point nearest the
    # top (and then the bottom) of each turn.
    per_turn = (n - 1) / revolutions
    level = [int(round(t * per_turn)) for t in np.arange(0.0, revolutions + 0.01, 0.5)]
    queue = list(dict.fromkeys(key_points + stepped + [i for i in level if i < n]))
    positions = np.column_stack([radii * np.cos(thetas), radii * np.sin(thetas)])

    loop_spacing_data = r_value_span / revolutions
    outer_r = r_base + r_value_span
    halo = [patheffects.Stroke(linewidth=2.6, foreground=background), patheffects.Normal()]
    tried = set()
    while len(labelled_points) < max_labels and len(tried) < 40:
        if queue:
            i = queue.pop(0)
        else:
            rest = [k for k in range(n) if k not in tried]
            if not rest or not labelled_points:
                break
            done = np.array(labelled_points)
            far = np.hypot(positions[rest, 0][:, None] - done[None, :, 0],
                           positions[rest, 1][:, None] - done[None, :, 1]).min(axis=1)
            i = rest[int(np.argmax(far))]
        if i in tried:
            continue
        tried.add(i)
        text = point_texts[i]
        w_px, h_px = tu.measure_text_px(fig, text, label_fs, font, 'bold')
        w_data, h_data = w_px / px_per_data, h_px / px_per_data
        # How far apart, in radius, consecutive loops sit -- a push of a
        # few pixels never clears the next loop when loops are far apart,
        # so the step scales with the loop spacing; but never more than a
        # few gaps, or at half a revolution labels were thrown off the page.
        radial_step = max(gap_data, min(loop_spacing_data * 0.3, 4 * gap_data))
        point = np.array([radii[i] * np.cos(thetas[i]), radii[i] * np.sin(thetas[i])])

        placed = None
        # 1. Beside its own point: a small grid of (radial push, angular
        #    slide) candidates, sliding along its own loop before giving up
        #    -- with no loop of the spiral between the point and its label.
        #    (A label pushed out from a point on an inner loop could land
        #    past the next loop out, clear of the line, and read as that
        #    loop's.)
        for rm in (1.0, 1.4, 1.8):
            for ao in (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2):
                r_label = radii[i] + radial_step * rm
                theta_label = thetas[i] + ao * gap_data / max(radii[i], gap_data)
                cx, cy = r_label * np.cos(theta_label), r_label * np.sin(theta_label)
                box = (cx - w_data / 2, cx + w_data / 2, cy - h_data / 2, cy + h_data / 2)
                if _collides(box):
                    continue
                nearest = np.array([np.clip(point[0], box[0], box[1]), np.clip(point[1], box[2], box[3])])
                if _loops_crossed(point, nearest) or _loops_crossed(point, np.array([cx, cy])):
                    continue
                placed = (cx, cy, box, None)
                break
            if placed:
                break
        # 2. Outside the spiral, with a leader line. On a tightly wound
        #    spiral there's often no room between loops; those labels used
        #    to be dropped -- 39 of 40 on a 40-point one. The leader goes
        #    the way that crosses the fewest loops, and only the first,
        #    last, highest and lowest points may have one that crosses
        #    more than one: a line from deep inside a tight spiral, across
        #    loop after loop, points at a tangle more than at a point.
        #    (Every label that didn't fit beside its point used to take
        #    such a line -- five loops crossed, on a 40-point spiral.)
        if placed is None:
            key = i in key_points
            turns = (0.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.45, -0.45, 0.6, -0.6)
            if key:
                turns += (0.8, -0.8, 1.0, -1.0, 1.2, -1.2)
            best = None
            for dth in turns:
                th = thetas[i] + dth
                ux, uy = np.cos(th), np.sin(th)
                along = abs(ux) * w_data / 2 + abs(uy) * h_data / 2
                r_centre = outer_r + 1.2 * gap_data + along
                cx, cy = r_centre * ux, r_centre * uy
                box = (cx - w_data / 2, cx + w_data / 2, cy - h_data / 2, cy + h_data / 2)
                end = np.array([np.clip(point[0], box[0], box[1]), np.clip(point[1], box[2], box[3])])
                if _collides(box, leader=(point, end)):
                    continue
                crossed = _loops_crossed(point, end)
                if best is None or crossed < best[0]:
                    best = (crossed, (cx, cy, box, end))
                if crossed == 0:
                    break
            if best is not None and (key or best[0] <= 1):
                placed = best[1]
        if placed is None:
            continue    # nowhere clear: skipped rather than drawn over the curve or a label
        cx, cy, box, end = placed
        if end is not None:
            ax.plot([point[0], end[0]], [point[1], end[1]], color=ink_color, linewidth=0.8,
                    zorder=3.5, solid_capstyle='round', path_effects=halo)
            placed_leaders.append((point, end))
        # Center alignment in both directions -- a spiral's points sit at
        # every angle, so there's no single "outward" screen direction to
        # left/right-align against.
        ax.text(cx, cy, text, ha='center', va='center', multialignment='center',
                 fontsize=label_fs, fontweight='bold', fontfamily=font, color=ink_color,
                 zorder=4, clip_on=False)
        placed_boxes.append(box)
        labelled_points.append(point)

    # ------------------------------------------------------------------
    # Title block.
    # ------------------------------------------------------------------
    y_cursor = title_top(fig)
    for ln in title_lines:
        fig.text(0.5, y_cursor, ln, ha='center', va='top', fontsize=title_fs,
                  fontweight='bold', fontfamily=font, color=ink_color)
        y_cursor -= (title_line_h * 1.35) / fig_h_px
    if title_lines and subtitle_lines:
        y_cursor -= 6 / fig_h_px
    for ln in subtitle_lines:
        fig.text(0.5, y_cursor, ln, ha='center', va='top', fontsize=subtitle_fs,
                  fontweight='normal', fontfamily=font, color=ink_color)
        y_cursor -= (subtitle_line_h * 1.35) / fig_h_px

    if save_path:
        fig.savefig(save_path, dpi=dpi, facecolor=background)

    return fig
