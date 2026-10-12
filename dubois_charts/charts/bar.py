"""
General-purpose Du Bois-style horizontal bar chart.

Same relationship to plate51.py as area.py has (see area.py's module
docstring and dubois_charts/charts/GENERAL_ENGINE_README.md for the full
rationale): this takes arbitrary categories, arbitrary category-label
length, an arbitrary number of series, and a title of whatever length the
caller has, and produces a readable, non-overlapping result by measuring
real text at render time via `dubois_charts.text_utils` instead of hand-tuning
positions for one demo dataset.

Horizontal orientation (bars growing rightward from a left-hand category
axis) matches the source material's own bar charts -- e.g. "Occupations
of Georgia Negroes" -- and, as a practical matter, is also the orientation
that handles long category labels gracefully: a long label reads
naturally to the left of its bar, whereas a vertical bar chart would need
to rotate long labels or run out of horizontal room per bar.
"""

import warnings
from collections.abc import Mapping
from typing import Dict, Optional, Sequence, Tuple, Union
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
    default_value_format,
    validate_colors,
    literal_text,
    font_stack,
    as_items,
    as_numbers,
    named_labels,
    warn_repeated,
    check_value_format,
    fit_label_column,
    rows_to_label,
    largest_size_that_fits,
    title_top,
    aligned,
    add_legend,
    number_text,
)


@literal_text
def bar_chart(
    categories: Sequence[str],
    values: Union[Sequence[float], Dict[str, Sequence[float]]],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    colors: Optional[Sequence[str]] = None,
    value_format: Optional[str] = None,
    show_value_labels: bool = True,
    sort_descending: bool = False,
    texture: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled horizontal bar chart for arbitrary data.

    Parameters
    ----------
    categories : Sequence
        One label per bar (or per bar-group, if `values` is multi-series):
        text, numbers or dates, which are written the way a person would
        write them ("2018", not "2018.0"; "Jan 2024", not "2024-01-01
        00:00:00"). Any length: every label gets the largest font size at
        which all of them fit the lines their rows have room for without
        breaking a word, so a long label wraps rather than shrinking the
        rest. A missing one (None, NaN -- a total row with no name) is an
        error; one given twice is drawn twice, with a warning.
    values : Sequence[float], or Dict[str, Sequence[float]] or DataFrame
        Either one number per category (a single bar each), or a mapping
        of series name -> one number per category (grouped bars, several
        side by side per category), such as a pandas DataFrame with a
        column per series; the series are named in a legend under the
        chart. A pandas Series whose index names the categories is
        matched to them by its index, whatever order its rows are in.
        Values are plotted as-is -- they don't need to be percentages or
        sum to anything in particular. Negative values work: bars grow
        from a shared zero, rightward when positive and leftward when
        negative (a vertical line marks zero whenever the data have both
        signs), and each value's label goes on the outward side of its
        own bar, so a growth rate or a profit and loss reads correctly.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width; long titles take
        more lines rather than overflowing. The title is in capitals, as
        on the plates, except words whose mixed case is deliberate ("iOS",
        "McDonald's"); the subtitle is as written.
    colors : Sequence[str], optional
        One color per category (single-series) or per series
        (multi-series). Defaults to `dubois_charts.colors.get_categorical(...)`.
    value_format : str, optional
        `str.format`-style template for the number drawn past each bar's
        end, e.g. `'{:.0f}%'` for percentages or `'${:,.0f}B'` for money.
        If omitted, values print as plain numbers with thousands
        separators and as many decimal places as the data have (up to
        about three significant figures of the smallest). A value too
        small for the format to show prints as "<1" (or "<0.1", ...)
        rather than as zero.
    show_value_labels : bool
        If True, print each bar's formatted value just past its end.
    sort_descending : bool
        If True (and `values` is single-series), reorder bars from
        largest to smallest. Ignored for multi-series data, where a
        single sort order can't serve every series at once.
    texture : bool
        Overlay a light hand-painted-style grain on each bar.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        Figure size in inches. If not given: 9 inches wide, and as tall
        as the bars need -- about 0.42 inches a row up to 22 inches, then
        at least 0.15 inches a row (room for a label each) up to 32.
        With more rows than that, labels go on every few rows, with a
        warning.
    dpi : int
        Dots per inch, for the figure and for `save_path`.
    font : str or sequence of str, optional
        The font for all the text; by default the typewriter face the
        package picks (see the README's "Fonts"). Characters it lacks --
        Chinese, Arabic -- come from an installed font that has them.
    save_path : str, optional
        If given, save the figure here.
    seed : int
        Random seed for texture, so output is reproducible.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = bar_chart(
    ...     categories=['Agriculture', 'Domestic Service', 'Manufacturing',
    ...                 'Trade', 'Professions'],
    ...     values=[45, 25, 12, 10, 8],
    ...     title='Occupations of Negroes in Georgia',
    ...     value_format='{:.0f}%',
    ...     sort_descending=True,
    ... )
    """
    categories = list(categories)
    if len(categories) == 0:
        raise ValueError("`categories` must contain at least one entry.")
    cat_labels = named_labels(categories, "`categories`")
    warn_repeated(cat_labels, 'bar_chart')
    # Several series: a dict of name -> values, or a pandas DataFrame (one
    # column per series). A pandas Series is one series, not a mapping.
    is_multi = isinstance(values, Mapping) or (
        hasattr(values, 'columns') and callable(getattr(values, 'items', None)))
    if is_multi:
        series_items = [(name, vals if hasattr(vals, '__len__') or not hasattr(vals, '__iter__')
                         else list(vals))         # a generator, say
                        for name, vals in as_items(values, "`values`")]
        series_names = [name for name, _ in series_items]
        for name, vals in series_items:
            if isinstance(vals, (str, bytes)) or not hasattr(vals, '__len__'):
                raise TypeError(
                    f"`values` is a dict, which bar_chart reads as several series of bars -- "
                    f"series name -> one value per category -- but '{name}' is a single value, "
                    f"{vals!r}. For one bar per category, pass the numbers as a list in the "
                    f"categories' order: bar_chart(list(d), list(d.values())) for a dict d.")
            if len(vals) != len(categories):
                raise ValueError(
                    f"Series '{name}' has {len(vals)} values but there are "
                    f"{len(categories)} categories; every series needs one "
                    "value per category."
                )
        value_matrix = np.array([as_numbers(aligned(vals, cat_labels, f"series '{name}'"),
                                            f"series '{name}'", names=cat_labels)
                                 for name, vals in series_items])  # (n_series, n_cat)
    else:
        if not hasattr(values, '__len__'):
            values = list(values)       # a generator, say
        if len(values) != len(categories):
            raise ValueError(
                f"`values` has {len(values)} entries but there are "
                f"{len(categories)} categories."
            )
        series_names = None
        value_matrix = as_numbers(aligned(values, cat_labels, "`values`"), "`values`",
                                  names=cat_labels).reshape(1, -1)

    if value_format is None:
        value_format = default_value_format(value_matrix)
    check_value_format(value_format)

    # Negative values are supported: each bar grows from a shared x=0
    # origin, rightward for a positive value and leftward for a negative
    # one (see "Diverging (positive/negative) data" below for the full
    # axis, margin, and label-side logic this needs).

    n_cat = len(categories)
    n_series = value_matrix.shape[0]

    # Sorting only makes unambiguous sense for a single series -- with
    # several series there's no one order that's "descending" for all of
    # them at once, so multi-series input keeps the caller's own order.
    if sort_descending and not is_multi:
        order = np.argsort(-value_matrix[0])
        value_matrix = value_matrix[:, order]
        cat_labels = [cat_labels[i] for i in order]

    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)

    if colors is None:
        if is_multi:
            colors = dubois_colors.get_categorical(n_series)
        else:
            # Every bar is labelled with its category, so colours that look
            # alike past the twentieth can't be misread: skip that warning.
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                colors = dubois_colors.get_categorical(n_cat)
    colors = validate_colors(colors, n_series if is_multi else n_cat,
                             'series' if is_multi else 'bars', each_needs_own=is_multi)

    # ------------------------------------------------------------------
    # Figure sizing: height scales with how many bars actually need to be
    # stacked vertically (categories x series-per-category, plus a gap
    # between category groups), so a 30-category chart doesn't cram every
    # bar into the same fixed height a 3-category chart would use.
    # ------------------------------------------------------------------
    bars_per_cat = n_series
    row_h_in = 0.42 if bars_per_cat == 1 else 0.30 * bars_per_cat + 0.14
    if figsize is None:
        # Up to 22 inches at the usual row height. Past that, rows shrink,
        # but not below 0.15 inches -- room for an 8pt label -- until the
        # figure is 32 inches tall: at a flat 22 inches, a chart of 195
        # countries had 0.11-inch rows, too short to label every bar.
        height = max(min(max(3.0, row_h_in * n_cat + 1.6), 22.0),
                     min(0.15 * n_cat + 1.6, 32.0))
        figsize = (9.0, height)

    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi
    fig_h_px = figsize[1] * dpi

    # ------------------------------------------------------------------
    # Title block -- identical pattern to stacked_area_chart: fit before
    # laying out the axes so we reserve exactly the vertical space the
    # (possibly wrapped) title actually needs.
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
                       + (16 if title_lines or subtitle_lines else 0))

    # The legend naming the series, under the chart: there's no room in a
    # bar to name its series the way area.py names a band, so grouped bars
    # always get one rather than relying on colour alone. Made first, so
    # the bars are laid out above however many rows it takes.
    # It gets at most 40% of the room below the title, at a smaller size if
    # that's what fits; a legend still too big overlaps the bars, with a
    # warning, rather than leaving them no room at all.
    legend_reserve_px = 0
    if is_multi:
        legend_room_px = 0.4 * (fig_h_px - title_block_px)
        _, legend_top_px = add_legend(fig, list(zip(series_names, colors)), ink_color, font,
                                      0.96 * fig_w_px, max_height_px=legend_room_px)
        legend_reserve_px = min(max(40, legend_top_px - 4), legend_room_px)
        if legend_top_px > legend_room_px + 0.5:
            warnings.warn(
                f"bar_chart: the legend of {n_series} series needs more room than the figure has, "
                f"and overlaps the bars. A bigger figsize, or shorter series names, make room.",
                UserWarning, stacklevel=3)

    # ------------------------------------------------------------------
    # How tall each category's row will be, and which rows get labels:
    # all of them when a label fits its row, as it does at the usual row
    # height; otherwise one row in k, so labels never print over each
    # other. Value labels go on the same rows, at the largest size (up to
    # 11pt) that fits; with several series they sit beside each bar, so
    # bars too close together for an 8pt number get none.
    # ------------------------------------------------------------------
    cat_fs_min = 8.0
    cat_sizes = (12.5, 11.5, 10.5, 9.5, 8.5, cat_fs_min)
    plot_h_px = fig_h_px - title_block_px - legend_reserve_px - 10
    row_px = plot_h_px / max(n_cat, 1)
    min_line_px = tu.measure_text_px(fig, 'Xg', cat_fs_min, font, 'bold')[1]
    edge_pad_px = 0.0
    if min_line_px > 0.95 * row_px:
        # Rows shorter than a label: labels go one row in k, at 8pt, with
        # half a label's height of room above the first row and below the
        # last, so their labels stay on the figure.
        edge_pad_px = min_line_px / 2
        row_px = (plot_h_px - 2 * edge_pad_px) / max(n_cat, 1)
        cat_sizes = (cat_fs_min,)
    label_rows = rows_to_label(n_cat, row_px, min_line_px)
    label_row_set = set(label_rows)
    label_pitch_px = row_px * (min(b - a for a, b in zip(label_rows, label_rows[1:]))
                               if len(label_rows) > 1 else 1)
    if len(label_rows) < n_cat:
        warnings.warn(
            f"bar_chart: {n_cat} categories leave {row_px:.0f}px per row, too little for "
            f"a label each, so {len(label_rows)} are labelled: one row in "
            f"{label_rows[1] - label_rows[0] if len(label_rows) > 1 else n_cat}, and the last. "
            f"A taller figsize labels them all.",
            UserWarning, stacklevel=3)
    if is_multi:
        bar_pitch_px = row_px * (1 - 2 * 0.16) / n_series
        value_fs = largest_size_that_fits(fig, font, bar_pitch_px)
        if show_value_labels and value_fs is None:
            warnings.warn(
                f"bar_chart: the bars are {bar_pitch_px:.0f}px apart, too close for value labels, "
                f"so they're left off. A taller figsize, or fewer categories, brings them back.",
                UserWarning, stacklevel=3)
    else:
        value_fs = largest_size_that_fits(fig, font, label_pitch_px)
    draw_values = show_value_labels and value_fs is not None
    value_fs = value_fs or 8

    # ------------------------------------------------------------------
    # Right-hand headroom for positive-value labels, and (new, for
    # diverging data) left-hand headroom for negative-value labels --
    # measured separately, since a negative bar's label sits on the
    # *left* of its own bar, not the right, and needs its own margin
    # rather than sharing the positive side's. Computed before the
    # category-label column below, since that column's own left margin
    # needs to already know how much extra space negative-value labels
    # require.
    # ------------------------------------------------------------------
    right_margin_px = 14
    neg_value_label_px = 0
    if draw_values:
        pos_vals = value_matrix[value_matrix >= 0]
        neg_vals = value_matrix[value_matrix < 0]
        pos_labels = [number_text(value_format, v) for v in pos_vals]
        neg_labels = [number_text(value_format, v) for v in neg_vals]
        widest_pos_w = max((tu.measure_text_px(fig, s, value_fs, font, 'bold')[0]
                            for s in pos_labels), default=0)
        widest_neg_w = max((tu.measure_text_px(fig, s, value_fs, font, 'bold')[0]
                            for s in neg_labels), default=0)
        right_margin_px = widest_pos_w + 14
        neg_value_label_px = widest_neg_w + 14 if len(neg_labels) else 0

    # ------------------------------------------------------------------
    # Category-label column: measure the widest label, shrink to fit a
    # generous-but-bounded fraction of the figure width, and only wrap
    # onto a second line if shrinking alone would go under a readable
    # floor -- the same shrink-before-wrap order `fit_title` uses.
    # ------------------------------------------------------------------
    max_label_frac = 0.34  # a single very long label can't eat the whole figure
    max_label_w_px = fig_w_px * max_label_frac

    cat_fs, cat_lines_per_label = fit_label_column(
        fig, [cat_labels[i] for i in label_rows], max_label_w_px, label_pitch_px, font,
        sizes=cat_sizes)
    actual_widest_w = max(
        tu.measure_text_px(fig, ln, cat_fs, font, 'bold')[0]
        for lines in cat_lines_per_label.values() for ln in lines
    )
    # Negative-value labels sit further left still, past the
    # category-label column itself -- reserved here using the width
    # already computed above, so both fit without a second layout pass.
    left_margin_px = actual_widest_w + 26 + neg_value_label_px

    axes_top_frac = 1 - title_block_px / fig_h_px
    axes_bottom_frac = (legend_reserve_px + 10) / fig_h_px
    left_frac = left_margin_px / fig_w_px
    right_frac = 1 - right_margin_px / fig_w_px

    fig.subplots_adjust(top=axes_top_frac, bottom=axes_bottom_frac,
                          left=left_frac, right=right_frac)
    ax = fig.add_subplot(111)
    ax.set_facecolor(background)

    axes_h_px = (axes_top_frac - axes_bottom_frac) * fig_h_px
    axes_w_px = (right_frac - left_frac) * fig_w_px
    # A fixed *pixel* gap between the category-label text and the axis
    # line, expressed as an axes-fraction offset -- computed from the
    # axes' actual pixel width rather than a hardcoded fraction (a fixed
    # fraction like -0.02 translates to a different number of pixels
    # depending on how wide the plotted area ends up being, which can
    # silently eat into -- or fall short of -- the margin actually
    # reserved for it below).
    # The category-label column sits further left than the axes' own
    # left edge by this gap -- and, when negative values reserved extra
    # room for their own value labels (computed above, before this
    # margin was applied), the category column shifts further left
    # still, by that same reserved width. Without this shift, both the
    # category label and a negative bar's value label independently
    # anchor themselves close to the axes' left edge, and for a bar
    # whose value approaches the axis minimum, the two collide directly
    # -- found by rendering real GDP-growth data where the single most
    # negative country's name and value literally overlapped.
    label_gap_px = 8
    label_anchor_x = -(label_gap_px + neg_value_label_px) / axes_w_px if axes_w_px else 0.0

    # ------------------------------------------------------------------
    # Bar geometry. Category 0 at the top (reading order), each category
    # occupying a unit-height band; within that band, n_series bars are
    # stacked with a small gap, sized so the whole cluster fits the band.
    #
    # Diverging data (a mix of positive and negative values): the x-axis
    # extends on whichever side(s) the data actually needs -- xlim_lo
    # stays 0 unless some value is negative, xlim_hi stays 0 unless some
    # value is positive -- so an all-positive dataset gets exactly the
    # same axis it always did (xlim_lo == 0), and a mix gets a shared
    # zero origin with room on both sides.
    # ------------------------------------------------------------------
    max_val = value_matrix.max() if value_matrix.size else 0
    min_val = value_matrix.min() if value_matrix.size else 0
    if max_val <= 0 and min_val >= 0:
        # Every value is exactly zero -- fall back to a default span
        # rather than a degenerate zero-width axis.
        xlim_lo, xlim_hi = 0.0, 1.0
    else:
        xlim_hi = max_val * 1.02 if max_val > 0 else 0.0
        xlim_lo = min_val * 1.02 if min_val < 0 else 0.0
    ax.set_xlim(xlim_lo, xlim_hi)
    pad_rows = edge_pad_px / row_px if row_px else 0.0
    y_top, y_bottom = -pad_rows, n_cat + pad_rows
    ax.set_ylim(y_bottom, y_top)  # inverted: category 0 at the top

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    group_pad = 0.16
    bar_h = (1 - 2 * group_pad) / n_series
    # The gap between bars in a group: 0.12 of the row, but never more than
    # about a third of each bar's share of it. A flat 0.12 was most of each
    # share from four series on, and more than all of it from six: five
    # series of bars were a pixel or two thick, and six drew upside down.
    bar_gap = min(0.12, 0.36 * bar_h)
    px_per_row = axes_h_px / (y_bottom - y_top) if n_cat else 0.0
    value_line_px = tu.measure_text_px(fig, 'Xg', value_fs, font, 'bold')[1]

    for c_idx in range(n_cat):
        cat_top = c_idx + group_pad
        for s_idx in range(n_series):
            val = value_matrix[s_idx, c_idx]
            y0 = cat_top + s_idx * bar_h
            h = bar_h - (bar_gap if n_series > 1 else 0)
            color = colors[s_idx if is_multi else c_idx % len(colors)]

            # Rectangle (and imshow's extent, for the texture below) both
            # accept a negative width natively -- anchored at (0, y0), a
            # negative val draws leftward from the shared origin rather
            # than rightward, with no special-casing needed here. A
            # mirrored noise texture is visually indistinguishable from
            # an unmirrored one, so no change is needed there either.
            # A bar a few pixels tall gets a thinner outline, or none: at a
            # thousand bars, 1pt outlines left more ink than colour.
            bar_px = h * px_per_row
            outline = 1.0 if bar_px >= 8 else (0.5 if bar_px >= 4 else 0.0)
            ax.add_patch(plt.Rectangle((0, y0), val, h, facecolor=color,
                                         edgecolor=ink_color, linewidth=outline, zorder=2))
            if texture and val != 0:     # (add_rect_texture skips bars under 6px)
                add_rect_texture(ax, 0, y0, val, h, color, seed=seed + c_idx * 97 + s_idx)

            if draw_values and (is_multi or c_idx in label_row_set):
                label = number_text(value_format, val)
                # With labels one row in k, a label is taller than its own
                # bar: it goes past the longest bar beside it as well, or
                # it would print over that bar's end.
                reach = val
                if not is_multi and len(label_rows) < n_cat and px_per_row:
                    half_rows = value_line_px / 2 / px_per_row
                    lo = max(0, int(np.floor(c_idx + 0.5 - half_rows)))
                    hi = min(n_cat, int(np.ceil(c_idx + 0.5 + half_rows)))
                    span = value_matrix[0, lo:hi]
                    reach = span.max() if val >= 0 else span.min()
                    reach = max(reach, val) if val >= 0 else min(reach, val)
                if val >= 0:
                    txt_x = reach + xlim_hi * 0.012
                    ha = 'left'
                else:
                    txt_x = reach - abs(xlim_lo) * 0.012
                    ha = 'right'
                ax.text(txt_x, y0 + h / 2, label, ha=ha, va='center',
                         fontsize=value_fs, fontweight='bold', fontfamily=font,
                         color=ink_color, zorder=6, clip_on=False)

        # Category label, vertically centered on the whole cluster, drawn
        # outside the axes to the left (figure/axes fraction x < 0, data
        # y at the cluster's center) so it never competes with bar fill
        # or value-label space. This uses the axes' own fractional
        # coordinate space, not a data-x position, so it sits just left
        # of the axes' left edge whether that edge is at 0 (all-positive
        # data, as before) or at a negative xlim_lo (diverging data) --
        # no change needed here for the new negative-value case.
        if c_idx not in label_row_set:
            continue
        # (The last bar of a group stops a gap short of the next group, so
        # the group's middle is half a gap above the row's: centred on the
        # row, a name sat level with the top of the second of two bars.)
        cluster_center_y = c_idx + 0.5 - (bar_gap / 2 if n_series > 1 else 0.0)
        lines = cat_lines_per_label[cat_labels[c_idx]]
        _, line_h_px = tu.measure_text_px(fig, 'Xg', cat_fs, font, 'bold')
        line_gap_data = (line_h_px * 1.2) / px_per_row if px_per_row else 0
        start_y = cluster_center_y - line_gap_data * (len(lines) - 1) / 2
        for k, ln in enumerate(lines):
            ax.text(label_anchor_x, start_y + k * line_gap_data, ln, ha='right', va='center',
                     fontsize=cat_fs, fontweight='bold', fontfamily=font,
                     color=ink_color, zorder=6, clip_on=False,
                     transform=ax.get_yaxis_transform())

    # A thin ink border around the plotted bar field, matching the
    # source material's framed-card look used elsewhere in the package.
    #
    # The frame encloses the value labels as well as the bars. It used to
    # sit at the axis limits, while value labels are placed just past each
    # bar's end -- so the label of the longest bar (and of any bar close to
    # it) always straddled the frame, and the frame line cut through the
    # number: "1,4|17.73", "$71|5B", "-8.|7%". Every chart with value
    # labels had it. The layout already reserves room for the widest label
    # on each side (right_margin_px, neg_value_label_px), so the frame is
    # simply drawn out to the edge of that room, 6px short of it. The bars
    # keep their size; only the frame moves.
    frame_lo, frame_hi = xlim_lo, xlim_hi
    px_per_unit = axes_w_px / (xlim_hi - xlim_lo) if xlim_hi > xlim_lo else 0.0
    if draw_values and px_per_unit:
        if np.any(value_matrix >= 0):
            frame_hi = xlim_hi + (right_margin_px - 6) / px_per_unit
        if np.any(value_matrix < 0):
            frame_lo = xlim_lo - (neg_value_label_px - 6) / px_per_unit
    ax.add_patch(plt.Rectangle((frame_lo, y_top), frame_hi - frame_lo, y_bottom - y_top, fill=False,
                                 edgecolor=ink_color, linewidth=1.0, zorder=1, clip_on=False))

    # A vertical line marking the shared zero origin, only drawn when the
    # data actually diverges (otherwise x=0 already coincides with the
    # left border drawn above, and a second line on top of it would add
    # nothing). Drawn above the bars (zorder 3) so it stays visible
    # crossing through bar fills, gaps between category rows, and the
    # bar-group padding alike, rather than only where a bar edge happens
    # to already mark it.
    if xlim_lo < 0 and xlim_hi > 0:
        ax.plot([0, 0], [y_top, y_bottom], color=ink_color, linewidth=1.0, zorder=3, clip_on=False)

    # ------------------------------------------------------------------
    # Title block, placed in figure-fraction space above the axes.
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
