"""
General-purpose Du Bois-style pie (proportional-circle) chart.

Same relationship to plate51.py as the other general chart types (see
GENERAL_ENGINE_README.md). The layout problem here is different again:
a thin wedge simply has no internal space for its own label, no matter
how much the font shrinks or the text wraps -- unlike a bar (which can
always grow taller) or an area band (which can always claim more of the
chart's width), a pie slice's available internal area is capped by its
own angle, full stop. Real chart libraries solve this with EXTERNAL
labels connected by a leader line, stacked vertically to avoid
overlapping each other -- a technique nothing else in this package has
needed yet, since every other chart type could always fall back to
shrinking, wrapping, or a legend instead.
"""

from typing import Dict, Optional, Sequence, Tuple
import math
import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from dubois_charts import colors as dubois_colors
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import (
    COLOR_CREAM,
    get_font as _get_font,
    text_color_for as _text_color_for,
    add_patch_texture,
    validate_figsize,
    display_caps,
    format_nonzero,
    validate_colors,
    literal_text,
    font_stack,
    segment_items,
    as_numbers,
    check_value_format,
    title_top,
)


@literal_text
def pie_chart(
    segments: Dict[str, float],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    colors: Optional[Sequence[str]] = None,
    value_format: str = '{:.0f}%',
    show_value_labels: bool = True,
    start_angle: float = 90.0,
    clockwise: bool = True,
    donut: bool = False,
    texture: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled pie chart for arbitrary data.

    Parameters
    ----------
    segments : Dict[str, float]
        Category -> value pairs: a dict, or a pandas Series (index ->
        value). Names can be text, numbers or dates. Values, zero or
        more, are shares of their total -- they don't need to sum to 100
        or to anything in particular.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width. The title is in
        capitals, as on the plates, except words whose mixed case is
        deliberate; the subtitle is as written.
    colors : Sequence[str], optional
        One color per segment. Defaults to
        `dubois_charts.colors.get_categorical(...)`.
    value_format : str
        `str.format`-style template for each segment's share of the
        total, as a percentage -- not for its value: a segment of 45 out
        of 180 is labelled with `value_format.format(25.0)`, "25%" by
        default. (So `'${:,.0f}'` would print "$25"; for the values
        themselves, put them in the names.) A share too small for the
        format prints as "<1%" rather than "0%". Values that already add
        up to 100, give or take 2 -- percentages as published, rounded --
        are labelled as they are, not as shares of their total: 13.4 of
        100.5 reads "13.4%", not "13.3%".
    show_value_labels : bool
        If True, each name is followed by its share.
    start_angle : float
        Degrees, measured counterclockwise from the positive x-axis
        (matplotlib's convention) -- 90 (the default) starts at the top.
    clockwise : bool
        If True (the default, and the usual reading convention for a
        pie chart), segments proceed clockwise from `start_angle`.
    donut : bool
        If True, punch a hole in the middle (inner radius 45% of the
        outer one) for a ring-style chart instead of a solid disk.
    texture : bool
        Overlay a light hand-painted-style grain on each wedge.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        Defaults to 9 x 9 inches. Long outside labels wrap rather than
        growing the figure.
    dpi : int
        Dots per inch, for the figure and for `save_path`.
    font : str or sequence of str, optional
        The font for all the text; by default the typewriter face the
        package picks (see the README's "Fonts"). Characters it lacks
        come from an installed font that has them.
    save_path : str, optional
        If given, save the figure here.
    seed : int
        Random seed for texture, so output is reproducible.

    A label goes inside its wedge where it fits; otherwise outside, in a
    column beside the pie, with a line to its wedge. With more slices
    than the columns have room for, the smallest are left unlabelled,
    with a warning.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = pie_chart(
    ...     segments={'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5},
    ...     title='Conjugal Condition',
    ... )
    """
    pairs = segment_items(segments, "pie_chart")
    if len(pairs) == 0:
        raise ValueError("`segments` must contain at least one entry.")

    labels = [label for label, _ in pairs]
    values = as_numbers([v for _, v in pairs], "segment values", names=labels)
    negative = [f'{labels[i]!r} ({values[i]:g})' for i in np.where(values < 0)[0]]
    if negative:
        raise ValueError(
            f"Segment {', '.join(negative[:5])}{' and more' if len(negative) > 5 else ''} "
            f"{'is' if len(negative) == 1 else 'are'} negative. Each segment is a share of "
            f"the circle, so every value must be zero or more.")
    if values.sum() <= 0:
        raise ValueError("segment values must sum to a positive total.")

    check_value_format(value_format)
    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    if colors is None:
        colors = dubois_colors.get_categorical(len(labels))
    colors = validate_colors(colors, len(labels), 'slices', each_needs_own=False)

    fracs = values / values.sum()
    sign = -1.0 if clockwise else 1.0
    cum = np.concatenate([[0.0], np.cumsum(fracs)])
    raw_angles = start_angle + sign * cum * 360.0  # one more than len(labels)

    r_pie = 1.0
    inner_r = 0.45 if donut else 0.0

    # ------------------------------------------------------------------
    # Figure sizing: reuses spiral_chart's proven algebra for solving a
    # data-unit radius that leaves room for external labels once
    # converted through the eventual data-to-pixel scale -- the same
    # "how much margin does the widest label actually need" problem,
    # just around a plain circle instead of a spiral.
    # ------------------------------------------------------------------
    if figsize is None:
        figsize = (9.0, 9.0)
    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi
    fig_h_px = figsize[1] * dpi

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
                       + (16 if title_lines or subtitle_lines else 0))

    ext_label_fs = 10.5
    ext_gap_px = 10
    point_texts = []
    value_texts = []
    total = float(values.sum())
    # Values that already add up to 100, give or take 2, are percentages
    # rounded in their source, and each slice is labelled with its own:
    # labelled with its share of 100.5, a published 13.4% read "13.3%".
    pct_of_total = values.copy() if abs(total - 100) <= 2 else values / total * 100
    for i in range(len(labels)):
        if show_value_labels:
            # format_nonzero: a visible sliver reads "<1%", never "0%".
            value_texts.append(format_nonzero(value_format, pct_of_total[i]))
            point_texts.append(f"{labels[i]}  {value_texts[-1]}")
        else:
            value_texts.append('')
            point_texts.append(labels[i])

    def _value_apart(i, lines):
        """A name that ends in a number keeps two spaces before its value,
        wrapped or not: wrapping closed them up, and "Cities / Over / 10000
        9%" read as if the 10000 went with the 9%."""
        v = value_texts[i]
        name = labels[i].rstrip()
        if (not lines or not v or not name or not name[-1].isdigit()
                or not lines[-1].endswith(' ' + v)):
            return lines
        return lines[:-1] + [lines[-1][:-len(v)].rstrip() + '  ' + v]
    # Labels drawn outside the pie wrap at about a quarter of the figure's
    # width. Room used to be reserved for the widest label as one line,
    # and if that left the pie too small the whole figure was scaled up:
    # one 70-character label made a 9-inch pie 24 inches wide, every
    # other label shrinking to nothing when it was displayed.
    ext_max_w_px = 0.24 * fig_w_px

    def _wrap_outside(i, fs):
        # Only labels too wide for the column wrap (wrapping re-joins words
        # with single spaces, which would lose the "name  value" gap).
        text = point_texts[i]
        if tu.measure_text_px(fig, text, fs, font, 'bold')[0] <= ext_max_w_px:
            return text
        wrap = lambda width: _value_apart(i, tu.wrap_text_to_width(fig, text, width, fs, font, 'bold'))
        lines = wrap(ext_max_w_px)
        # Then as narrow as the same number of lines allows, without
        # breaking a word, so the lines come out even: "Trade and /
        # transportation 2%", not "Trade and transportation / 2%".
        lo, hi = 0.3 * ext_max_w_px, ext_max_w_px
        for _ in range(8):
            mid = (lo + hi) / 2
            trial = wrap(mid)
            if len(trial) <= len(lines) and ' '.join(trial).split() == text.split():
                hi, lines = mid, trial
            else:
                lo = mid
        return '\n'.join(lines)

    ext_texts = [_wrap_outside(i, ext_label_fs) for i in range(len(point_texts))]

    axes_top_frac = 1 - title_block_px / fig_h_px
    axes_bottom_frac = 14 / fig_h_px
    # The plot takes all the room below the title. The pie and its label
    # columns are laid out in it as one group, centred, so a pie whose
    # outside labels are all on one side moves over to make room for them
    # rather than leaving the same room empty on the other side.
    edge_px = 6
    avail_w_px = max(fig_w_px - 2 * edge_px, 1.0)
    avail_h_px = max((axes_top_frac - axes_bottom_frac) * fig_h_px, 1.0)
    breathing_px = 0.05 * min(avail_w_px, avail_h_px)  # room around a pie with every label inside

    # Which labels fit inside their wedge depends on how big the pie is,
    # and how big the pie can be depends on whether any labels have to go
    # outside it. So: decide with the pie as large as it can be; if some
    # labels have to go outside, reserve room beside the pie for exactly
    # those labels and decide again, until the set stops changing -- then
    # draw. (Always reserving room for the widest label shrank the pie
    # enough to push a long label out of a 327-degree slice; widening the
    # axes after drawing squeezed the lines of two-line labels inside the
    # wedges together.)
    mid_angles = [math.radians((raw_angles[i] + raw_angles[i + 1]) / 2) for i in range(len(labels))]

    # ------------------------------------------------------------------
    # Per-segment labels: try inside the wedge first; anything that
    # doesn't fit (too narrow an angle, or a label too long even at the
    # smallest readable size) goes on a list for external placement.
    # ------------------------------------------------------------------
    def _point_in_wedge(x: float, y: float, theta1_deg: float, theta2_deg: float) -> bool:
        """Exact containment check: is (x, y) within this wedge's radius
        band and angle range? Used to VALIDATE a candidate label's actual
        rendered corners rather than trust an approximate width formula --
        arc-length-at-mid-radius looked like a reasonable proxy for
        available width, but for a wide wedge whose label sits well off
        the wedge's own angular center line, it overestimates how much
        horizontal room there really is: the true boundary near the top
        of a big slice can be a near-vertical radial edge just past the
        text's left side, or the outer circle curving in well before the
        arc-length estimate assumed. That overestimate was confirmed by
        checking actual rendered pixels: a wedge's percentage label ran
        past the wedge's real edge, going from crisp white-on-fill to
        barely-visible white-on-background right where the two disagreed.

        theta1_deg/theta2_deg are the RAW cumulative angles (`raw_angles[i]`,
        `raw_angles[i+1]`), not first normalized into [0, 360) -- taking
        `% 360` of each endpoint independently, as an earlier version did,
        throws away which of the two possible arcs between two angles is
        actually the wedge. That's backwards most severely for any wedge
        spanning more than half the circle: found by testing a 95% wedge
        whose own label, sitting well inside its own huge slice, failed
        this exact containment check against its own boundaries and was
        wrongly pushed to an external leader-line label instead of simply
        being drawn where it obviously belonged. Anchoring the comparison
        to `min`/`max` of the RAW (pre-modulo) endpoints and adjusting the
        test point into that same unwrapped frame keeps the true arc
        width intact regardless of how far the cumulative angles have
        drifted from the conventional [0, 360) range.
        """
        r = math.hypot(x, y)
        if r > r_pie or r < inner_r:
            return False
        ang = math.degrees(math.atan2(y, x))
        lo, hi = min(theta1_deg, theta2_deg), max(theta1_deg, theta2_deg)
        ang_adjusted = lo + ((ang - lo) % 360)
        return lo <= ang_adjusted <= hi

    def _wedge_fits_at_size(i: int, fontsize: float, px_per_data: float):
        """Does labels[i]'s text fit entirely within wedge i's real
        shape at this EXACT fontsize (checked via corner-in-wedge
        containment)? Returns the wrapped lines and center point if so,
        else None.

        Tries progressively narrower wrap widths at this fixed fontsize
        before giving up, not just one -- the arc-length-based starting
        estimate can still be too generous for a wedge's actual cross-
        section away from its widest point (the same reason the internal
        vs. external decision needs the real corner check at all, not
        just an approximate box), and re-wrapping into narrower lines at
        the SAME font size is what let a large wedge's long label
        eventually find a fitting arrangement before the fontsize search
        was shared across wedges. Losing this nested retry when this
        function was first written (search happened only across font
        sizes, not also across wrap widths within a size) was found by
        checking an actual render: two originally-easy-to-fit wedges
        were pushed external, for no shape-related reason, once this
        retry was missing.
        """
        mid = mid_angles[i]
        mid_r = (r_pie + inner_r) / 2 if donut else r_pie * 0.55
        cx, cy = mid_r * math.cos(mid), mid_r * math.sin(mid)
        theta_a, theta_b = raw_angles[i], raw_angles[i + 1]
        natural_w_px, _ = tu.measure_text_px(fig, point_texts[i], fontsize, font, 'bold')

        # Candidate wrap widths, tried in order: the natural (unwrapped)
        # single-line width first, then widths that force something
        # close to an even 2-line split, narrowing further from there.
        # Deliberately NOT a fixed small shrink (like 0.8x) applied
        # repeatedly to an arc-length estimate -- checked directly with
        # debug instrumentation: since a single-line render's width
        # doesn't change at all until the wrap width drops BELOW it,
        # three successive 0.8x shrinks from a generous starting
        # estimate stayed above that threshold every time, wasting most
        # of the retry budget with zero visible effect before the loop
        # ran out, right as the first real 2-line wrap needed one more
        # attempt than was left to try it.
        candidate_widths = [natural_w_px * 1.05, natural_w_px * 0.55,
                             natural_w_px * 0.42, natural_w_px * 0.32]

        for wrap_width_px in candidate_widths:
            lines = _value_apart(i, tu.wrap_text_to_width(fig, point_texts[i], wrap_width_px, fontsize,
                                                           font, 'bold', max_lines=None))
            if len(lines) > 3:
                # Up to three lines: the corner check below still decides
                # whether they fit, and a big slice holds three easily --
                # with a limit of two, a long name in a 327-degree slice was
                # sent outside whenever the pie was a little smaller.
                #
                # Ask wrap_text_to_width for the wrap it actually needs,
                # uncapped -- passing max_lines=2 directly here would let
                # it silently truncate-with-ellipsis to comply, and a
                # corner check against that shorter, truncated text could
                # wrongly accept it as a clean fit. This is the exact
                # same anti-pattern already found and fixed once in
                # fit_label_in_box (see GENERAL_ENGINE_README.md).
                continue
            if ' '.join(lines).split() != point_texts[i].split():
                continue    # a word was broken in two ("Divor / ced"): never inside a wedge
            widest_line_px = max(tu.measure_text_px(fig, ln, fontsize, font, 'bold')[0]
                                 for ln in lines)
            _, line_h_px = tu.measure_text_px(fig, 'Xg', fontsize, font, 'bold')
            total_h_px = line_h_px * len(lines) * 1.2
            half_w_data = (widest_line_px / 2) / px_per_data
            half_h_data = (total_h_px / 2) / px_per_data
            corners = [(cx - half_w_data, cy - half_h_data), (cx + half_w_data, cy - half_h_data),
                       (cx - half_w_data, cy + half_h_data), (cx + half_w_data, cy + half_h_data)]
            if all(_point_in_wedge(x, y, theta_a, theta_b) for x, y in corners):
                return (lines, cx, cy)
            # Corners escaped the wedge at this wrap width -- try the
            # next, narrower candidate rather than giving up immediately.
        return None

    # A single SHARED fontsize for every INTERNAL wedge label, rather
    # than each wedge independently maximizing its own size against its
    # own slice -- checked with actual rendered text properties, not
    # assumed: on a 4-segment pie, three labels landed at a consistent
    # ~13pt while one ("Widowed", the smallest wedge attempted
    # internally) came out at 9.75pt, and bold text at that smaller size
    # renders with visibly thinner strokes than the same weight at the
    # larger size -- reading as a different, mismatched font on the same
    # chart even though neither the font family nor the weight had
    # actually changed. This is the exact same bug, and the exact same
    # fix, as county_map_chart's per-county label sizing (see
    # GENERAL_ENGINE_README.md) -- found independently here rather than
    # assumed to be fixed just because the other instance was.
    candidates = [i for i in range(len(labels))
                  if abs(raw_angles[i + 1] - raw_angles[i]) >= 8]

    inside_sizes = (13, 12, 11, 10, 9, 8, 7)
    comfortable_fs = 10

    def _inside_labels(px_per_data):
        """
        The shared inside size and the labels that fit inside at it: the
        largest size at which every candidate fits -- unless that's below
        10pt, where labels get hard to read. Then 10pt, provided most still
        fit, and the few that don't go outside, rather than one small
        slice's name dragging every label down to 7pt.
        """
        fits = {}

        def fitting_at(fs):
            if fs not in fits:
                fits[fs] = {i: r for i in candidates
                            if (r := _wedge_fits_at_size(i, fs, px_per_data)) is not None}
            return fits[fs]

        # Only labels that fit inside at the smallest size get a say: the
        # rest go outside whatever size is picked.
        can_fit = set(fitting_at(inside_sizes[-1]))
        if not can_fit:
            return inside_sizes[-1], {}
        count = lambda fs: len(can_fit & set(fitting_at(fs)))
        all_fit = next(fs for fs in inside_sizes if count(fs) == len(can_fit))
        most_fit = next(fs for fs in inside_sizes if count(fs) >= max(1, len(can_fit) * 0.6))
        chosen = all_fit if all_fit >= comfortable_fs else max(all_fit, min(most_fit, comfortable_fs))
        return chosen, fitting_at(chosen)

    # An outside label goes in a column on its wedge's side of the pie.
    # Its text starts 1.18 radii plus 0.03 from the centre, so a column
    # needs column_k radii beyond the pie's edge, plus the label's width
    # and a gap.
    side_of = ['right' if math.cos(m) >= 0 else 'left' for m in mid_angles]
    column_k = 0.18 + 0.03 / r_pie

    def _widest_by_side(outside):
        widest = {}
        for i in outside:
            w = tu.measure_text_px(fig, ext_texts[i], ext_label_fs, font, 'bold')[0]
            widest[side_of[i]] = max(widest.get(side_of[i], 0.0), w)
        return widest

    def _pie_radius_px(outside):
        # The largest pie that leaves room for the columns these labels
        # need, side by side across the width, within the height.
        widest = _widest_by_side(outside)
        fixed = sum(w + ext_gap_px for w in widest.values()) + breathing_px * (2 - len(widest))
        r_px = min((avail_w_px - fixed) / (2 + column_k * len(widest)),
                   avail_h_px / 2 - breathing_px)
        return max(r_px, 0.15 * min(avail_w_px, avail_h_px))

    # Labels that go outside only ever add to the room reserved, so this
    # settles; the inside labels are always decided at the final size.
    outside = set()
    for _ in range(len(labels) + 1):
        px_per_data = _pie_radius_px(outside) / r_pie
        shared_fs, internal_placements = _inside_labels(px_per_data)
        now_outside = set(range(len(labels))) - set(internal_placements)
        if now_outside <= outside:
            break
        outside |= now_outside
    outside = now_outside

    r_px = r_pie * px_per_data
    widest_final = _widest_by_side(outside)
    room = {s: (column_k * r_px + widest_final[s] + ext_gap_px) if s in widest_final else breathing_px
            for s in ('left', 'right')}
    group_w_px = room['left'] + 2 * r_px + room['right']
    ax_x0_px, ax_y0_px = edge_px, axes_bottom_frac * fig_h_px
    centre_x_px = ax_x0_px + (avail_w_px - group_w_px) / 2 + room['left'] + r_px
    ax = fig.add_axes([ax_x0_px / fig_w_px, ax_y0_px / fig_h_px,
                       avail_w_px / fig_w_px, avail_h_px / fig_h_px])
    ax.set_facecolor(background)
    ax.set_xlim((ax_x0_px - centre_x_px) / px_per_data,
                (ax_x0_px + avail_w_px - centre_x_px) / px_per_data)
    ax.set_ylim(-avail_h_px / 2 / px_per_data, avail_h_px / 2 / px_per_data)
    ax.set_aspect('equal')
    ax.axis('off')

    # ------------------------------------------------------------------
    # Draw wedges.
    # ------------------------------------------------------------------
    for i in range(len(labels)):
        a0, a1 = raw_angles[i], raw_angles[i + 1]
        theta1, theta2 = (a0, a1) if a0 <= a1 else (a1, a0)
        color = colors[i % len(colors)]
        wedge = mpatches.Wedge((0, 0), r_pie, theta1, theta2,
                                 width=(r_pie - inner_r) if donut else None,
                                 facecolor=color, edgecolor=ink_color,
                                 linewidth=1.0, zorder=2)
        # add_artist, not add_patch: the limits are set, and working out
        # each wedge's extent from its arcs was a sixth of a 200-slice pie.
        ax.add_artist(wedge)
        if texture:
            add_patch_texture(ax, mpatches.Wedge((0, 0), r_pie, theta1, theta2,
                                                    width=(r_pie - inner_r) if donut else None,
                                                    transform=ax.transData),
                               color, (-r_pie, r_pie, -r_pie, r_pie), seed=seed + i * 53)

    external = []  # dicts: idx, angle, natural_x, natural_y
    for i in range(len(labels)):
        if i in internal_placements:
            lines, cx, cy = internal_placements[i]
            txt_color = _text_color_for(colors[i % len(colors)])
            _, line_h_px = tu.measure_text_px(fig, 'Xg', shared_fs, font, 'bold')
            line_gap = (line_h_px / px_per_data) * 1.2
            start_y = cy + line_gap * (len(lines) - 1) / 2
            for k, ln in enumerate(lines):
                ax.text(cx, start_y - k * line_gap, ln, ha='center', va='center',
                         fontsize=shared_fs, fontweight='bold', fontfamily=font,
                         color=txt_color, zorder=6)
        else:
            mid = mid_angles[i]
            r_label = r_pie * 1.12
            external.append({
                'idx': i,
                'angle': mid,
                'x': r_label * math.cos(mid),
                'y': r_label * math.sin(mid),
                'text': ext_texts[i],
            })

    # ------------------------------------------------------------------
    # External labels: group by side, decluttered vertically within each
    # side so overlapping natural positions (common when several thin
    # wedges cluster together on one side of the circle) get spread out
    # rather than drawn on top of each other.
    # ------------------------------------------------------------------
    if external:
        # Outside labels go in a column on each side of the pie, never over
        # it: they used to sit at their wedge's own angle, so the labels of
        # a cluster of thin wedges near 12 o'clock stacked straight down
        # across the biggest slice. Within a column, overlapping neighbours
        # are pushed apart symmetrically, up as well as down, so each label
        # stays as close as it can to its own wedge, spaced by its real
        # (possibly wrapped) height.
        #
        # If a column's labels are too tall to fit beside the pie at all,
        # the outside-label size steps down (to 7pt at the smallest), since
        # the axes can't grow tall enough without shrinking the pie to a dot.
        column_x = r_pie * 1.18
        for e in external:
            e['natural_y'] = e['y']
            e['x'] = column_x if e['x'] >= 0 else -column_x
        right_side = sorted([e for e in external if e['x'] >= 0], key=lambda e: -e['natural_y'])
        left_side = sorted([e for e in external if e['x'] < 0], key=lambda e: -e['natural_y'])

        def _measure(fs):
            for e in external:
                e['text'] = _wrap_outside(e['idx'], fs)
                e['text_w_px'], e['h_px'] = tu.measure_text_px(fig, e['text'], fs, font, 'bold')
            return tu.measure_text_px(fig, 'Xg', fs, font, 'bold')[1]

        for candidate_fs in (ext_label_fs, 9.5, 8.5, 7.5, 7):
            ext_line_h_px = _measure(candidate_fs)
            tallest_column = max(sum(e['h_px'] + ext_line_h_px * 0.5 for e in side)
                                 for side in (right_side, left_side) if side)
            if tallest_column <= 0.92 * avail_h_px:
                break
        ext_label_fs = candidate_fs

        # Still too tall at 7pt -- a pie of 200 slices has more names than
        # fit beside it: the smallest slices go unlabelled, until each
        # column fits. They're still drawn. (Their labels used to run off
        # the top and bottom of the figure and over each other.)
        unlabelled = 0
        for side in (right_side, left_side):
            while side and sum(e['h_px'] + ext_line_h_px * 0.5 for e in side) > 0.92 * avail_h_px:
                smallest = min(side, key=lambda e: values[e['idx']])
                side.remove(smallest)
                external.remove(smallest)
                unlabelled += 1
        if unlabelled:
            warnings.warn(
                f"pie_chart: {unlabelled} of the {len(labels)} slices are too small to label beside "
                f"the pie without overlapping, so they're left unlabelled. Grouping the smallest "
                f"slices into 'Other' reads better.", UserWarning, stacklevel=3)

        # Last resort only -- the room reserved above normally holds every
        # column: if a label would still reach past the plot, zoom out
        # about the pie's centre. Zooming out by f makes a label's width
        # in data units f times larger too, so for text starting at
        # `start` it needs  start + f * width <= f * limit,  i.e.
        #   f >= start / (limit - width).
        x_lo, x_hi = ax.get_xlim()
        zoom = 1.0
        for e in external:
            start = abs(e['x']) + 0.03
            limit = x_hi if e['x'] >= 0 else -x_lo
            width = (e['text_w_px'] + 2) / px_per_data
            zoom = max(zoom, start / (limit - width) if limit - width > 0.1 * limit else 10.0)
        if zoom > 1.001:
            y_lo, y_hi = ax.get_ylim()
            ax.set_xlim(x_lo * zoom, x_hi * zoom)
            ax.set_ylim(y_lo * zoom, y_hi * zoom)
            px_per_data /= zoom

        pad_data = (ext_line_h_px * 0.5) / px_per_data
        for e in external:
            e['h_data'] = e['h_px'] / px_per_data
        top_limit = ax.get_ylim()[1] - 2 / px_per_data
        for group in (right_side, left_side):
            for _ in range(500):
                moved = False
                for k in range(1, len(group)):
                    need = (group[k - 1]['h_data'] + group[k]['h_data']) / 2 + pad_data
                    overlap = need - (group[k - 1]['y'] - group[k]['y'])
                    if overlap > 1e-9:
                        group[k - 1]['y'] += overlap / 2
                        group[k]['y'] -= overlap / 2
                        moved = True
                # Keep the column inside the axes: a stack pushed past the
                # top or bottom slides back as a whole.
                if group:
                    over_top = group[0]['y'] + group[0]['h_data'] / 2 - top_limit
                    under_bottom = -top_limit - (group[-1]['y'] - group[-1]['h_data'] / 2)
                    shift = -over_top if over_top > 1e-9 else (under_bottom if under_bottom > 1e-9 else 0.0)
                    if shift:
                        for e in group:
                            e['y'] += shift
                        moved = True
                if not moved:
                    break

        for e in external:
            i = e['idx']
            color = colors[i % len(colors)]
            anchor_x, anchor_y = r_pie * math.cos(e['angle']), r_pie * math.sin(e['angle'])
            elbow_x, elbow_y = r_pie * 1.06 * math.cos(e['angle']), r_pie * 1.06 * math.sin(e['angle'])
            ha = 'left' if e['x'] >= 0 else 'right'
            label_x = e['x'] + (0.03 if ha == 'left' else -0.03)
            # Out from the wedge first, then across to the label column.
            ax.plot([anchor_x, elbow_x, e['x']], [anchor_y, elbow_y, e['y']], color=ink_color,
                     linewidth=0.8, zorder=5)
            ax.plot([anchor_x], [anchor_y], marker='o', markersize=2.5,
                     color=ink_color, zorder=5)
            ax.text(label_x, e['y'], e['text'], ha=ha, va='center', multialignment=ha,
                     fontsize=ext_label_fs, fontweight='bold', fontfamily=font,
                     color=ink_color, zorder=6, clip_on=False)

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
