"""
General-purpose Du Bois-style butterfly (mirror) chart.

Same relationship to plate51.py as area.py and bar.py have (see
dubois_charts/charts/GENERAL_ENGINE_README.md for the full rationale): arbitrary
categories, arbitrary label length, and a title of whatever length the
caller has, sized from real measurements at render time rather than
hand-tuned for one demo dataset.

This is the one chart type in the package whose axis sits in the *middle*
of the figure rather than at an edge (categories run down the center,
with two mirrored bar sets growing left and right from it -- the style
Du Bois used for side-by-side comparisons, e.g. occupations by sex). That
changes what "reserve enough margin" means: bar.py only had to solve for
a left-hand label column, but a butterfly chart's center column has two
bar areas depending on it staying correctly sized on *both* sides at
once, so the margin math here solves for three regions (left plot, center
label gutter, right plot) simultaneously rather than one.
"""

import warnings
from typing import List, Optional, Sequence, Tuple
import numpy as np
import matplotlib.pyplot as plt

from dubois_charts import colors as dubois_colors
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import (
    COLOR_CREAM,
    get_font as _get_font,
    text_color_for as _text_color_for,
    add_rect_texture,
    validate_figsize,
    display_caps,
    literal_text,
    font_stack,
    as_numbers,
    named_labels,
    warn_repeated,
    default_value_format_for,
    check_value_format,
    fit_label_column,
    rows_to_label,
    largest_size_that_fits,
    title_top,
    aligned,
    number_text,
)


@literal_text
def butterfly_chart(
    categories: Sequence[str],
    left_values: Sequence[float],
    right_values: Sequence[float],
    left_label: Optional[str] = None,
    right_label: Optional[str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    left_color: Optional[str] = None,
    right_color: Optional[str] = None,
    value_format: Optional[str] = None,
    show_value_labels: bool = True,
    texture: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled butterfly (mirrored two-sided) bar chart.

    Parameters
    ----------
    categories : Sequence
        One label per row, drawn centered between the two bar sets: text,
        numbers or dates (written as a person would: "2018", "Jan 2024").
        Any length: every label gets the largest font size at which all of
        them fit the lines their rows have room for without breaking a
        word, so a long label wraps rather than shrinking the rest. A
        missing one (None, NaN) is an error; one given twice is drawn
        twice, with a warning.
    left_values, right_values : Sequence[float]
        One number, zero or more, per category for each side. A pandas
        Series whose index names the categories is matched to them by its
        index, whatever order its rows are in. Both sides share one scale,
        set by the largest value on either, so the two stay directly
        comparable -- the point of a butterfly chart. (When one side's
        largest value is more than a hundred times the other's, a warning
        says the smaller side's bars are too short to see.)
    left_label, right_label : str, optional
        Header drawn above each side, e.g. "MALE" / "FEMALE", in capitals.
        Shrunk to fit its own half of the chart if it's wider than that.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width. The title is in
        capitals, as on the plates, except words whose mixed case is
        deliberate ("iOS"); the subtitle is as written.
    left_color, right_color : str, optional
        Defaults to the first two colors of
        `dubois_charts.colors.get_categorical(2)`.
    value_format : str, optional
        `str.format`-style template for the number drawn past each bar's
        outer end. By default, plain numbers at the data's own precision
        -- with a percent sign when each side adds up to 100, since each
        value is then a percentage of its side -- and, when the two
        sides' numbers are of very different sizes, each side at its own.
    show_value_labels : bool
        If True, print each bar's value past its outer end.
    texture : bool
        Overlay a light hand-painted-style grain on each bar.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        If not given: 10.5 inches wide, and as tall as the rows need --
        0.5 inches a row up to 20 inches, then at least 0.15 inches a row
        (room for a label each) up to 32. With more rows than that,
        labels go on every few rows, with a warning.
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

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = butterfly_chart(
    ...     categories=['Agriculture', 'Domestic Service', 'Trade', 'Professions'],
    ...     left_values=[52, 38, 6, 4],
    ...     right_values=[31, 55, 8, 6],
    ...     left_label='MALE', right_label='FEMALE',
    ...     title='Occupations by Sex',
    ... )
    """
    categories = list(categories)
    left_values = left_values if hasattr(left_values, '__len__') else list(left_values)
    right_values = right_values if hasattr(right_values, '__len__') else list(right_values)
    n_cat = len(categories)
    if n_cat == 0:
        raise ValueError("`categories` must contain at least one entry.")
    if len(left_values) != n_cat or len(right_values) != n_cat:
        raise ValueError(
            "`left_values` and `right_values` must each have exactly one "
            f"entry per category ({n_cat})."
        )

    cat_labels = named_labels(categories, "`categories`")
    warn_repeated(cat_labels, 'butterfly_chart')
    left_vals = as_numbers(aligned(left_values, cat_labels, "`left_values`"),
                           "`left_values`", names=cat_labels)
    right_vals = as_numbers(aligned(right_values, cat_labels, "`right_values`"),
                            "`right_values`", names=cat_labels)
    for side, vals in (('left_values', left_vals), ('right_values', right_vals)):
        negative = [f'{cat_labels[i]!r} ({vals[i]:g})' for i in np.where(vals < 0)[0]]
        if negative:
            raise ValueError(
                f"`{side}` has a negative value for {', '.join(negative[:5])}"
                f"{' and more' if len(negative) > 5 else ''}. Each side's bars grow out from "
                f"the middle, so every value must be zero or more. For values with a sign -- a "
                f"change, a profit or loss -- bar_chart draws bars both ways from zero.")
    biggest = left_vals.max(), right_vals.max()
    lopsided = min(biggest) > 0 and max(biggest) / min(biggest) > 100
    if lopsided:
        warnings.warn(
            f"butterfly_chart: the largest value on the {'left' if biggest[0] > biggest[1] else 'right'} "
            f"is {max(biggest) / min(biggest):,.0f} times the largest on the other side. Both sides "
            f"share one scale, so the bars on that side are too short to see. A butterfly chart "
            f"compares two measures of the same kind; for two different measures, draw two charts.",
            UserWarning, stacklevel=3)
    if value_format is not None:
        check_value_format(value_format)
        left_format = right_format = value_format
    elif lopsided:
        # Numbers of very different sizes, in different units most likely:
        # one format for both sides printed "1,250,000.000" to show 0.012
        # on the other side.
        left_format = default_value_format_for(left_vals, [left_vals.sum()])
        right_format = default_value_format_for(right_vals, [right_vals.sum()])
    else:
        left_format = right_format = default_value_format_for(
            np.concatenate([left_vals, right_vals]), [left_vals.sum(), right_vals.sum()])

    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    palette = dubois_colors.get_categorical(2)
    left_color = left_color or palette[0]
    right_color = right_color or palette[1]

    # ------------------------------------------------------------------
    # Figure sizing: height scales with category count, same policy as
    # bar.py; width defaults a bit wider since two bar areas share it.
    # ------------------------------------------------------------------
    if figsize is None:
        # As in bar_chart: past 20 inches rows shrink, but not below 0.15
        # inches -- room for an 8pt label -- until the figure is 32 tall.
        height = max(min(max(3.2, 0.5 * n_cat + 1.8), 20.0),
                     min(0.15 * n_cat + 1.8, 32.0))
        figsize = (10.5, height)

    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi
    fig_h_px = figsize[1] * dpi

    # ------------------------------------------------------------------
    # Title block (identical pattern to area.py / bar.py).
    # ------------------------------------------------------------------
    margin_px = 0.03 * fig_w_px
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

    # ------------------------------------------------------------------
    # Header row (left_label / right_label), reserved above the bars.
    # Sized from whichever header is taller once each is fit to its own
    # half-width -- computed properly once we know plot_half_width_px,
    # so this starts as a provisional estimate and is finalized below.
    # ------------------------------------------------------------------
    header_fs_max = 15
    header_block_px = (header_fs_max * 1.5 + 10) if (left_label or right_label) else 0

    # ------------------------------------------------------------------
    # Center label gutter: measure every category label, shrink to fit a
    # bounded fraction of the figure width, wrap onto a second line only
    # if shrinking alone isn't enough -- identical escalation to bar.py's
    # category column, just landing in the middle instead of on the left.
    # ------------------------------------------------------------------
    cat_fs_max = 12.5
    cat_fs_min = 8.0
    max_label_frac = 0.30
    max_label_w_px = fig_w_px * max_label_frac

    # Rows, and which get labels -- the same rules as bar_chart's: every
    # row when a label fits its row, otherwise one row in k at 8pt, with
    # half a label of room above the first row and below the last. Value
    # labels go on the same rows, at the largest size up to 11pt that fits.
    cat_sizes = (cat_fs_max, 11.5, 10.5, 9.5, 8.5, cat_fs_min)
    plot_h_px = fig_h_px - title_block_px - header_block_px - 14
    row_px = plot_h_px / max(n_cat, 1)
    min_line_px = tu.measure_text_px(fig, 'Xg', cat_fs_min, font, 'bold')[1]
    edge_pad_px = 0.0
    if min_line_px > 0.95 * row_px:
        edge_pad_px = min_line_px / 2
        row_px = (plot_h_px - 2 * edge_pad_px) / max(n_cat, 1)
        cat_sizes = (cat_fs_min,)
    label_rows = rows_to_label(n_cat, row_px, min_line_px)
    label_row_set = set(label_rows)
    label_pitch_px = row_px * (min(b - a for a, b in zip(label_rows, label_rows[1:]))
                               if len(label_rows) > 1 else 1)
    if len(label_rows) < n_cat:
        warnings.warn(
            f"butterfly_chart: {n_cat} rows leave {row_px:.0f}px each, too little for a label "
            f"each, so {len(label_rows)} are labelled: one row in "
            f"{label_rows[1] - label_rows[0]}, and the last. A taller figsize labels them all.",
            UserWarning, stacklevel=3)
    value_fs = largest_size_that_fits(fig, font, label_pitch_px) or cat_fs_min
    cat_fs, cat_lines_per_label = fit_label_column(
        fig, [cat_labels[i] for i in label_rows], max_label_w_px, label_pitch_px, font,
        sizes=cat_sizes)
    actual_widest_w = max(
        tu.measure_text_px(fig, ln, cat_fs, font, 'bold')[0]
        for lines in cat_lines_per_label.values() for ln in lines
    )
    center_gap_px = actual_widest_w + 2 * 14  # padding on both sides of the label

    # ------------------------------------------------------------------
    # Outer margins for value labels past each bar's far end -- measured
    # per side, since left/right formatted values can differ in width.
    # ------------------------------------------------------------------
    outer_left_px = 12
    outer_right_px = 12
    if show_value_labels:
        left_label_strs = [number_text(left_format, v) for v in left_vals]
        right_label_strs = [number_text(right_format, v) for v in right_vals]
        widest_left = max((tu.measure_text_px(fig, s, value_fs, font, 'bold')[0]
                           for s in left_label_strs), default=0)
        widest_right = max((tu.measure_text_px(fig, s, value_fs, font, 'bold')[0]
                            for s in right_label_strs), default=0)
        outer_left_px = widest_left + 14
        outer_right_px = widest_right + 14

    # ------------------------------------------------------------------
    # Solve the three horizontal regions simultaneously: whatever is left
    # after both outer margins and the center gutter splits evenly into
    # the two (necessarily equal-width, for a fair visual comparison)
    # bar areas.
    # ------------------------------------------------------------------
    remaining_px = fig_w_px - outer_left_px - outer_right_px - center_gap_px
    plot_half_width_px = max(remaining_px / 2, fig_w_px * 0.12)  # floor: keep bars usable
    # If labels+margins genuinely don't leave room even at the floor, the
    # center gutter is what gets trimmed back, rather than letting bar
    # areas collapse to nothing.
    if remaining_px < fig_w_px * 0.24:
        center_gap_px = max(fig_w_px - outer_left_px - outer_right_px - fig_w_px * 0.24, fig_w_px * 0.08)
        plot_half_width_px = fig_w_px * 0.12

    # Now finalize the header row height using the ACTUAL half-width.
    # Uses the same shrink-before-wrap escalation as `fit_title`: try a
    # shared font size (so both headers look visually consistent) that
    # fits both labels on one line first; only if a long header genuinely
    # can't be shrunk to a still-readable size does it wrap onto more
    # lines -- found to be necessary after testing with a header long
    # enough to run clean off both edges of the figure at the font-floor
    # size a shrink-only approach was left at.
    #
    # Headers are put into their display capitals here, *before* they're
    # measured and wrapped. They used to be measured in their original
    # case and upper-cased only when drawn: fine in the default monospace
    # font, where both cases are the same width, but with a proportional
    # font the capitals are wider than what was measured. display_caps
    # also keeps deliberate mixed case ("iOS" no longer becomes "IOS").
    if left_label:
        left_label = display_caps(left_label)
    if right_label:
        right_label = display_caps(right_label)
    left_lines: List[str] = [left_label] if left_label else []
    right_lines: List[str] = [right_label] if right_label else []
    if left_label or right_label:
        box_w = plot_half_width_px * 0.92
        labels_present = [l for l in (left_label, right_label) if l]

        shared_fs = header_fs_max
        for lbl in labels_present:
            fs = tu.fit_fontsize_to_width(fig, lbl, box_w, font, 'bold',
                                           max_fontsize=shared_fs,
                                           min_fontsize=header_fs_max * 0.65)
            shared_fs = min(shared_fs, fs)

        one_line_ok = all(
            tu.measure_text_px(fig, lbl, shared_fs, font, 'bold')[0] <= box_w
            for lbl in labels_present
        )
        if one_line_ok:
            header_fs = shared_fs
        else:
            header_fs = max(header_fs_max * 0.75, 9)
            if left_label:
                left_lines = tu.wrap_text_to_width(fig, left_label, box_w, header_fs,
                                                    font, 'bold', max_lines=3)
            if right_label:
                right_lines = tu.wrap_text_to_width(fig, right_label, box_w, header_fs,
                                                     font, 'bold', max_lines=3)

        n_header_lines = max(len(left_lines) or 1, len(right_lines) or 1)
        _, header_h_px = tu.measure_text_px(fig, 'Xg', header_fs, font, 'bold')
        header_block_px = header_h_px * 1.3 * n_header_lines + 10
    else:
        header_fs = header_fs_max

    legend_reserve_px = 0  # butterfly charts identify sides via the header row, not a legend
    axes_top_frac = 1 - (title_block_px + header_block_px) / fig_h_px
    axes_bottom_frac = (legend_reserve_px + 14) / fig_h_px
    axes_h_px = (axes_top_frac - axes_bottom_frac) * fig_h_px

    left_ax_x0 = outer_left_px / fig_w_px
    left_ax_w = plot_half_width_px / fig_w_px
    right_ax_x0 = (outer_left_px + plot_half_width_px + center_gap_px) / fig_w_px
    right_ax_w = plot_half_width_px / fig_w_px

    ax_l = fig.add_axes([left_ax_x0, axes_bottom_frac, left_ax_w, axes_top_frac - axes_bottom_frac])
    ax_r = fig.add_axes([right_ax_x0, axes_bottom_frac, right_ax_w, axes_top_frac - axes_bottom_frac])
    for ax in (ax_l, ax_r):
        ax.set_facecolor(background)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    max_val = max(left_vals.max() if left_vals.size else 0,
                   right_vals.max() if right_vals.size else 0)
    xlim_max = max_val * 1.02 if max_val > 0 else 1.0
    ax_l.set_xlim(xlim_max, 0)   # inverted: 0 at the center, growing outward to the left
    ax_r.set_xlim(0, xlim_max)
    pad_rows = edge_pad_px / row_px if row_px else 0.0
    y_top, y_bottom = -pad_rows, n_cat + pad_rows
    ax_l.set_ylim(y_bottom, y_top)
    ax_r.set_ylim(y_bottom, y_top)
    px_per_row = axes_h_px / (y_bottom - y_top) if n_cat else 0.0
    value_line_px = tu.measure_text_px(fig, 'Xg', value_fs, font, 'bold')[1]

    def _reach(vals, i):
        # With labels one row in k, a value label is taller than its own
        # bar, so it goes past the longest bar beside it too.
        if len(label_rows) == n_cat or not px_per_row:
            return vals[i]
        half_rows = value_line_px / 2 / px_per_row
        lo = max(0, int(np.floor(i + 0.5 - half_rows)))
        hi = min(n_cat, int(np.ceil(i + 0.5 + half_rows)))
        return max(vals[i], vals[lo:hi].max())

    # ------------------------------------------------------------------
    # Bars, value labels, and (in the space between the two axes)
    # category labels.
    # ------------------------------------------------------------------
    bar_pad = 0.18
    bar_h = 1 - 2 * bar_pad
    rng_seed = seed

    for i in range(n_cat):
        y0 = i + bar_pad
        lv, rv = left_vals[i], right_vals[i]

        # Thin bars get thin outlines, or none, and no texture (as in bar_chart).
        bar_px = bar_h * px_per_row
        outline = 1.0 if bar_px >= 8 else (0.5 if bar_px >= 4 else 0.0)
        ax_l.add_patch(plt.Rectangle((0, y0), lv, bar_h, facecolor=left_color,
                                       edgecolor=ink_color, linewidth=outline, zorder=2))
        ax_r.add_patch(plt.Rectangle((0, y0), rv, bar_h, facecolor=right_color,
                                       edgecolor=ink_color, linewidth=outline, zorder=2))
        if texture:                      # (add_rect_texture skips bars under 6px)
            if lv > 0:
                add_rect_texture(ax_l, 0, y0, lv, bar_h, left_color, seed=rng_seed + i * 53)
            if rv > 0:
                add_rect_texture(ax_r, 0, y0, rv, bar_h, right_color, seed=rng_seed + i * 53 + 31)

        if show_value_labels and i in label_row_set:
            # ax_l's x-axis is inverted (0 at center, growing outward to
            # the left) so a bar's "outer" edge is at INCREASING data x.
            # Text alignment (ha) is always screen-space, though, not
            # data-space -- on this inverted axis ha='left' would anchor
            # the text at its screen-left edge and grow it screen-
            # rightward, which corresponds to DECREASING data x, i.e.
            # back toward the bar and center. ha='right' is what actually
            # extends the label outward, away from the bar, on this side.
            ax_l.text(_reach(left_vals, i) + xlim_max * 0.015, y0 + bar_h / 2, number_text(left_format, lv),
                       ha='right', va='center', fontsize=value_fs, fontweight='bold',
                       fontfamily=font, color=ink_color, zorder=6, clip_on=False)
            ax_r.text(_reach(right_vals, i) + xlim_max * 0.015, y0 + bar_h / 2, number_text(right_format, rv),
                       ha='left', va='center', fontsize=value_fs, fontweight='bold',
                       fontfamily=font, color=ink_color, zorder=6, clip_on=False)

        # Category label: figure-fraction position computed from the
        # shared y-mapping between the two (identically-scaled) axes.
        if i not in label_row_set:
            continue
        cluster_center_y = i + 0.5
        frac_y = axes_top_frac - ((cluster_center_y - y_top) / (y_bottom - y_top)) * (axes_top_frac - axes_bottom_frac)
        lines = cat_lines_per_label[cat_labels[i]]
        _, line_h_px = tu.measure_text_px(fig, 'Xg', cat_fs, font, 'bold')
        line_gap_frac = (line_h_px * 1.2) / fig_h_px
        start_y = frac_y + line_gap_frac * (len(lines) - 1) / 2
        center_x_frac = (left_ax_x0 + left_ax_w + right_ax_x0) / 2
        for k, ln in enumerate(lines):
            fig.text(center_x_frac, start_y - k * line_gap_frac, ln, ha='center', va='center',
                      fontsize=cat_fs, fontweight='bold', fontfamily=font, color=ink_color)

    # Borders around each side, matching the framed-card look used
    # elsewhere in the package.
    #
    # Each frame encloses its side's value labels as well as its bars.
    # Frames used to sit at the axis limits while value labels sit just
    # past each bar's outer end, so the longest bar's label straddled the
    # frame and the line cut through it ("91%" on real Android/iOS share
    # data). The layout already reserves outer margins sized to the widest
    # label on each side, so each frame extends outward into that margin,
    # stopping 6px short of the figure edge. The inner edges, at the
    # centre gutter, don't move; the bars keep their size.
    ext_l_px = ext_r_px = 0.0
    if show_value_labels and xlim_max > 0:
        right_axes_end_px = outer_left_px + 2 * plot_half_width_px + center_gap_px
        ext_l_px = max(0.0, outer_left_px - 6)
        # Capped so the frame can't leave the figure even when very wide
        # labels have already squeezed the layout past its normal budget.
        ext_r_px = max(0.0, min(outer_right_px - 6, fig_w_px - 6 - right_axes_end_px))
    px_per_unit = plot_half_width_px / xlim_max if xlim_max > 0 else 1.0
    ax_l.add_patch(plt.Rectangle((0, y_top), xlim_max + ext_l_px / px_per_unit, y_bottom - y_top, fill=False,
                                   edgecolor=ink_color, linewidth=1.0, zorder=1, clip_on=False))
    ax_r.add_patch(plt.Rectangle((0, y_top), xlim_max + ext_r_px / px_per_unit, y_bottom - y_top, fill=False,
                                   edgecolor=ink_color, linewidth=1.0, zorder=1, clip_on=False))
    # Headers are centred on each frame, not on the bar area alone, so they
    # stay visually balanced now that the frames extend outward.
    header_center_l = 0.5 - (ext_l_px / plot_half_width_px) / 2 if plot_half_width_px else 0.5
    header_center_r = 0.5 + (ext_r_px / plot_half_width_px) / 2 if plot_half_width_px else 0.5

    # ------------------------------------------------------------------
    # Header labels, centered over each side, in the reserved row above
    # the bars. Multi-line headers stack upward from the bars so the
    # LAST line sits closest to the bar area, matching normal reading
    # order (first line on top).
    #
    # The topmost line's anchor is derived directly from header_block_px
    # (the same value used to reserve the space in the first place),
    # rather than an independent hardcoded starting offset -- an earlier
    # version used a fixed "1.03" axes-fraction start that had no actual
    # relationship to how much space header_block_px had reserved, and
    # for a long header wrapped to two lines, the two disagreed enough
    # that the topmost line's rendered top edge ran past the literal top
    # edge of the canvas. Confirmed by checking actual rendered pixel
    # extent (0px margin at the top), then by adding direct instrumentation
    # to compare the drawn position against the true figure-top ceiling
    # rather than guessing which formula was wrong.
    # ------------------------------------------------------------------
    _, header_line_h_px = tu.measure_text_px(fig, 'Xg', header_fs, font, 'bold')
    line_h_axes = header_line_h_px / axes_h_px if axes_h_px else 0
    header_line_gap_axes = line_h_axes * 1.25
    header_ceiling_axes = 1.0 + header_block_px / axes_h_px if axes_h_px else 1.0

    def _draw_header(ax_obj, lines, center_x):
        if not lines:
            return
        # Anchor the TOPMOST line's rendered top edge just inside the
        # actual reserved ceiling (with a small safety inset for normal
        # variance between the 'Xg' height probe and a given line's real
        # rendered extent), then stack the rest downward from there.
        y0 = header_ceiling_axes - line_h_axes * 1.08
        for k, ln in enumerate(lines):
            y = y0 - k * header_line_gap_axes
            ax_obj.text(center_x, y, ln, ha='center', va='bottom',  # already in display capitals
                         fontsize=header_fs, fontweight='bold', fontfamily=font,
                         color=ink_color, transform=ax_obj.transAxes, clip_on=False)

    _draw_header(ax_l, left_lines, header_center_l)
    _draw_header(ax_r, right_lines, header_center_r)

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
