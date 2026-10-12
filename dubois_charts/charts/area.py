"""
General-purpose Du Bois-style stacked area chart.

RELATIONSHIP TO plate51.py
---------------------------
`dubois_charts/charts/plate51.py` is a pixel-verified recreation of one specific
historical drawing: fixed data, fixed bilingual title, fixed two category
names ("SLAVES" / "FREE - LIBRE"), fixed at nine years. It exists to prove
the package can reproduce the source material accurately, and it's a good
reference for the visual style, but it is *not* what someone reaches for to
chart their own data -- nothing about it takes parameters.

This module is that other thing: a `stacked_area_chart()` function that
takes arbitrary categories, an arbitrary number of series, arbitrary label
lengths, and a title of whatever length the caller actually has, and still
produces a readable, non-overlapping, Du Bois-styled chart. It shares the
same visual language (colors, monospace caps, cream background, optional
hand-painted texture) but every size and position is computed from the
actual input at render time via `dubois_charts.text_utils`, instead of hand-tuned
for one specific dataset.

See dubois_charts/text_utils.py for why this matters and how the fitting works.
"""

import functools
import warnings
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.path import Path
from matplotlib.transforms import offset_copy

from dubois_charts import colors as dubois_colors
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import (
    COLOR_CREAM,
    get_font as _get_font,
    text_color_for as _text_color_for,
    shade as _shade,
    validate_figsize,
    display_caps,
    validate_colors,
    literal_text,
    font_stack,
    as_items,
    as_numbers,
    as_datetimes,
    category_labels,
    date_labels,
    streak_field,
    GrainLayer,
    is_missing,
    default_value_format_for,
    check_value_format,
    title_top,
    aligned,
    add_legend,
    number_text,
    shared_size_fallback,
    _is_real_number,
    _midnights,
)


def _x_positions(x) -> Tuple[np.ndarray, List[str], bool]:
    """
    Plotting positions and labels for the x values, and whether the x
    values have an order of their own (numbers or dates) rather than being
    labels to space evenly.

    Dates -- datetime.date/datetime, pandas Timestamps, numpy datetime64 --
    are placed by time, so irregular dates are spaced truthfully, and
    labelled as compactly as they allow: just the year when every date is
    1 January, year and month when every date is the 1st, the date when
    there's no time of day. (They used to be spaced evenly, and pandas
    dates printed as "2020-01-01 00:00:00".) Numbers are placed by value
    and written as a person would: a pandas column of years that became
    floats reads "2018", not "2018.0".

    A missing x (None, NaN, NaT) or an infinite one is an error: there's
    nowhere to put it. A None used to turn the whole axis into evenly
    spaced text with "None" printed on it; a NaN or NaT crashed with
    matplotlib's "Axis limits cannot be NaN or Inf" or "'float' object
    cannot be interpreted as an integer".
    """
    values = list(x)
    bad = [i for i, v in enumerate(values)
           if is_missing(v) or (isinstance(v, (float, np.floating)) and not np.isfinite(v))]
    if bad:
        shown = ', '.join(f'position {i} ({values[i]})' for i in bad[:5])
        raise ValueError(f"x has a missing or infinite value at {shown}: every x needs a "
                         f"real value. Drop those points, or fill them in, first.")
    if values and all(isinstance(v, (int, float, np.integer, np.floating))
                      and not isinstance(v, (bool, np.bool_)) for v in values):
        return np.array(values, dtype=float), category_labels(values), True
    dates = as_datetimes(values)
    if dates and all(d is not None for d in dates):
        return np.array(mdates.date2num(dates), dtype=float), date_labels(dates), True
    return np.arange(len(values), dtype=float), category_labels(values), False


# The round steps x labels are thinned to: for whole numbers, 1, 2, 5, 10,
# 20, 25, 50, 100...; for months, 1, 2, 3, 4 and 6 months, then whole years.
_NUMBER_STEPS = sorted({m * 10 ** k for k in range(10) for m in (1, 2, 5)}
                       | {25 * 10 ** k for k in range(9)})
_MONTH_STEPS = [1, 2, 3, 4, 6] + [12 * y for y in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000)]


def _calendar_keys(x):
    """
    For x that are whole numbers, or dates: each as a whole number -- the
    number itself, or the month it falls in, counted from year 0 -- and the
    round steps to label them at. None for anything else.

    Dates through a month -- daily or weekly figures -- share their month's
    number, and are labelled at the first of them in a round month. They
    used to be labelled every so many points from the first, and four
    years of daily figures read "2020-01-25, 2020-09-19, 2021-05-15".
    """
    values = list(x)
    if all(_is_real_number(v) for v in values):
        arr = np.asarray(values, dtype=float)
        if not np.all(np.abs(arr - np.round(arr)) < 1e-9) or np.abs(arr).max() > 1e15:
            return None
        return np.round(arr).astype(np.int64), _NUMBER_STEPS
    dates = as_datetimes(values)
    if all(d is not None for d in dates):
        days = _midnights(dates)
        return np.array([d.year * 12 + d.month - 1 for d in days], dtype=np.int64), _MONTH_STEPS
    return None


def _round_tick_candidates(calendar, step: int):
    """
    Which points to label when only every `step`-th has room: the first,
    and those at round values -- every 5th or 10th year, each January --
    rather than every `step`-th from wherever the data start. Monthly
    figures labelled every 40th month read "Jan 2000, May 2003, Sep 2006",
    and years from 1874 every 3rd "1874, 1877, 1880, 1883". None when the
    x values aren't whole numbers or months, or no round step fits.
    """
    if calendar is None or step <= 1:
        return None
    keys, steps = calendar
    gaps = np.diff(np.sort(keys))
    gaps = gaps[gaps > 0]
    if not len(gaps):
        return None
    if len(np.unique(keys)) < len(keys):
        # Several points a month (keys are in order here): the first point
        # of each round month, at a step of months as wide as `step` points.
        per_point = (keys.max() - keys.min()) / (len(keys) - 1)
        for nice in steps:
            if nice >= step * per_point:
                picked = [i for i, k in enumerate(keys)
                          if k % nice == 0 and (i == 0 or keys[i - 1] != k)]
                return sorted({0, *picked}) if len(picked) >= 2 else None
        return None
    spacing = int(gaps.min())
    for nice in steps:
        if nice >= step * spacing and nice % spacing == 0:
            picked = [i for i, k in enumerate(keys) if k % nice == 0]
            return sorted({0, *picked}) if len(picked) >= 2 else None
    return None


@literal_text
def stacked_area_chart(
    x: Sequence[Union[str, int, float]],
    series: Dict[str, Sequence[float]],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    colors: Optional[Sequence[str]] = None,
    show_value_labels: bool = True,
    value_format: Optional[str] = None,
    show_band_labels: bool = True,
    ticks_on_top: bool = True,
    texture: bool = True,
    hand_drawn: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled stacked area chart for arbitrary data.

    Unlike a fixed recreation, every piece of text here is measured and
    fit at render time (see dubois_charts.text_utils), so this works whether you
    pass 2 categories or 12, a 6-character title or a 90-character one,
    and short or long series names.

    Parameters
    ----------
    x : Sequence
        Positions along the axis -- years, quarters, region names,
        whatever. Numbers and dates (`datetime`, pandas Timestamps and
        Periods, numpy `datetime64`, or ISO text such as "2020-03-01",
        as pd.read_csv leaves a column of dates) are placed by value and
        sorted, so irregular dates are spaced truthfully; anything else is
        spaced evenly in the order given. A missing or repeated x is an
        error.
    series : Dict[str, Sequence[float]] or DataFrame
        Ordered mapping of series name -> values, one value per entry in
        `x`, zero or more -- a dict, or a pandas DataFrame with a column
        per series. One column on its own, df['Price'], is one series,
        named for the column. A series that is a pandas Series whose
        index names the x values is matched to them by its index, whatever
        order its rows are in. Stacking order follows the mapping's order, first at the
        bottom -- the Du Bois convention of putting the base quantity at
        the bottom of the stack. Values don't need to sum to 100; the
        chart scales to the actual cumulative total, so this works for
        percentages, counts, or any other stacked quantity.
    title, subtitle : str, optional
        Chart title / subtitle. Wrapped and auto-sized to fit the figure
        width -- long titles simply take more lines rather than
        overflowing or getting clipped. The title is in capitals, as on
        the plates, except words whose mixed case is deliberate ("iOS");
        the subtitle is as written.
    colors : Sequence[str], optional
        One color per series, bottom to top. Defaults to
        `dubois_charts.colors.get_categorical(len(series))`.
    show_value_labels : bool
        If True, print each series' value inside its band, at each x
        whose label is shown, wherever the band is thick enough to hold
        it.
    value_format : str, optional
        A `str.format`-style template applied to each value for those
        labels, e.g. `'{:.0f}%'` or `'${:,.0f}'`. By default, plain
        numbers at the data's own precision -- with a percent sign when
        every column adds up to 100, since each value is then a
        percentage of its column.
    show_band_labels : bool
        If True, draw each series' name, in capitals, inside its band
        (like the original's "FREE - LIBRE" / "SLAVES"). A name that
        doesn't fit its band goes in a legend under the chart instead.
        Names share one size: the largest at which most of them fit.
    ticks_on_top : bool
        Put the category axis above the chart (the original plate's
        layout) instead of below.
    texture : bool
        Overlay a light hand-painted-style grain on each fill.
    hand_drawn : bool
        Give each boundary line a slight hand-inked wobble instead of a
        perfectly straight ruled line.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        Figure size in inches. If not given: 7 inches wide for up to
        eight x positions, half an inch wider for each one more, up to 11
        inches, and a twentieth taller than wide.
    dpi : int
        Dots per inch, for the figure and for `save_path`.
    font : str or sequence of str, optional
        The font for all the text; by default the typewriter face the
        package picks (see the README's "Fonts"). Characters it lacks
        come from an installed font that has them.
    save_path : str, optional
        If given, save the figure here.
    seed : int
        Random seed for texture/jitter, so output is reproducible.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = stacked_area_chart(
    ...     x=[2018, 2019, 2020, 2021, 2022],
    ...     series={
    ...         'On-site': [62, 58, 22, 30, 45],
    ...         'Hybrid': [10, 14, 18, 35, 40],
    ...         'Remote': [28, 28, 60, 35, 15],
    ...     },
    ...     title='Where knowledge workers did their jobs',
    ...     subtitle='Self-reported primary work location, surveyed companies',
    ... )
    """
    # A legend for the names that don't fit their bands goes under the
    # chart. Which names those are isn't known until the bands are laid
    # out, so the chart is drawn with room for one row of legend -- all
    # most charts need -- and drawn again with more when the legend turns
    # out longer. (With a fixed row's room, a second row sat on the chart.)
    x = list(x)
    options = dict(title=title, subtitle=subtitle, colors=colors,
                   show_value_labels=show_value_labels, value_format=value_format,
                   show_band_labels=show_band_labels, ticks_on_top=ticks_on_top,
                   texture=texture, hand_drawn=hand_drawn, background=background,
                   figsize=figsize, dpi=dpi, font=font, seed=seed)
    reserve_px = _LEGEND_ROOM_PX
    fig, legend_top_px, room_px = _draw_stacked_area(x, series, reserve_px, **options)
    for _ in range(2):
        if legend_top_px <= room_px or room_px < reserve_px:     # it fits, or can't have more
            break
        plt.close(fig)
        reserve_px = legend_top_px + 2
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')          # any were given the first time
            fig, legend_top_px, room_px = _draw_stacked_area(x, series, reserve_px, **options)
    if legend_top_px > room_px + 0.5:
        warnings.warn(
            "stacked_area_chart: the legend of the names that don't fit their bands needs more "
            "room than the figure has, and overlaps the chart. A bigger figsize, or shorter "
            "series names, make room.", UserWarning, stacklevel=3)

    if save_path:
        fig.savefig(save_path, dpi=dpi, facecolor=background)

    return fig


_LEGEND_ROOM_PX = 46


def _draw_stacked_area(x, series, legend_reserve_px, *, title, subtitle, colors,
                       show_value_labels, value_format, show_band_labels, ticks_on_top,
                       texture, hand_drawn, background, figsize, dpi, font, seed):
    """
    stacked_area_chart's figure, with `legend_reserve_px` of room at the
    bottom for the legend -- but no more than 40% of the figure -- and how
    far above the bottom the legend's text reaches (0 when there's no
    legend), which may be more than that room; and the room it had.
    """
    # One column of a table -- df['Price'] -- is one series, named for its
    # column. It was read as a mapping like any other: its row numbers
    # became the series' names and each value a series of its own, which
    # stopped with "object of type 'float' has no len()".
    if getattr(series, 'ndim', None) == 1 and hasattr(series, 'index') and hasattr(series, 'iloc'):
        series = {'' if series.name is None else series.name: series}
    series_items = as_items(series, "`series`")
    if len(series_items) == 0:
        raise ValueError("`series` must contain at least one series.")
    x = list(x)
    n = len(x)
    if n < 2:
        raise ValueError(
            "`stacked_area_chart` needs at least 2 x-position(s) to draw "
            "an area -- a single point has no span to fill, and rendered "
            "as a nearly blank chart with no fill, no band labels, and no "
            "value labels rather than raising, which is worse than "
            "raising clearly. For a single-point comparison, `bar_chart` "
            "is probably what you want instead."
        )
    for name, vals in series_items:
        if len(vals) != n:
            raise ValueError(
                f"Series '{name}' has {len(vals)} values but x has {n} entries; "
                "every series must have exactly one value per x position."
            )

    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    labels = [name for name, _ in series_items]
    # Plotting positions: numbers by value, dates by time, anything else
    # (text like "Q1", "Northeast") evenly spaced in the order given.
    x_pos, x_labels, x_is_ordered = _x_positions(x)
    calendar = _calendar_keys(x)
    values = np.array([as_numbers(aligned(vals, x_labels, f"series '{name}'"),
                                  f"series '{name}'", names=x_labels)
                       for name, vals in series_items])  # shape (n_series, n_x)
    negative = [f"'{labels[s]}' at {x_labels[j]} ({values[s, j]:g})"
                for s, j in zip(*np.where(values < 0))]
    if negative:
        raise ValueError(
            f"Series {', '.join(negative[:5])}{' and more' if len(negative) > 5 else ''} "
            f"{'is' if len(negative) == 1 else 'are'} negative. The areas stack one on "
            f"another, so every value must be zero or more. For values with a sign -- a "
            f"change, a gain or loss -- bar_chart draws bars both ways from zero.")

    if value_format is None:
        value_format = default_value_format_for(values, values.sum(axis=0))
    check_value_format(value_format)

    if colors is None:
        colors = dubois_colors.get_categorical(len(labels))
    colors = validate_colors(colors, len(labels), 'series', each_needs_own=True)[:len(labels)]

    if x_is_ordered:
        # A series plotted against numbers or dates is the same data in any
        # order, but drawn in the order given, unsorted x zig-zagged the
        # areas back over themselves. Sort by x; a repeated x is ambiguous.
        order = np.argsort(x_pos, kind='stable')
        x_pos, values = x_pos[order], values[:, order]
        x_labels = [x_labels[i] for i in order]
        if calendar is not None:
            calendar = (calendar[0][order], calendar[1])
        repeated = sorted({x_labels[i] for i in range(1, n) if x_pos[i] == x_pos[i - 1]})
        if repeated:
            raise ValueError(f"x has repeated values ({', '.join(repeated)}): each x position "
                             f"needs exactly one value per series. Combine the repeats first.")

    cumulative = np.vstack([np.zeros(n), np.cumsum(values, axis=0)])  # shape (n_series+1, n_x)
    y_max = cumulative[-1].max()
    y_max_padded = y_max * 1.0  # chart top == actual stack total, no padding (matches source style)

    # ------------------------------------------------------------------
    # Figure sizing: start from a reasonable default, then grow the width
    # if there are many categories (so ticks don't inevitably collide)
    # and reserve height for the title based on how many lines it will
    # actually need -- computed below once we can measure real text.
    # ------------------------------------------------------------------
    if figsize is None:
        # A little wider for more points, but not without limit: with 30 or
        # more points this used to reach 16 x 16.8 inches, and the x labels
        # are thinned to fit whatever the width anyway.
        width = min(max(7.0, 0.5 * n + 3.0), 11.0)
        height = width * 1.05
        figsize = (width, height)

    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi

    # ------------------------------------------------------------------
    # Title: wrap/fit to the figure width *before* laying out the axes,
    # so we know how many lines it needs and can reserve exactly that
    # much vertical space instead of guessing a fixed fraction.
    # ------------------------------------------------------------------
    margin_px = 0.05 * fig_w_px
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
                       + (20 if title_lines or subtitle_lines else 0))

    # ------------------------------------------------------------------
    # Category (x-axis) label style is decided *before* we finalize the
    # axes position, not after -- rotated labels take up meaningfully
    # more vertical room than horizontal ones, and if we don't account
    # for that before reserving header space, rotated labels end up
    # colliding with the title block above them (found by testing this
    # with long region names that don't fit un-rotated).
    axes_w_px_estimate = (0.94 - 0.06) * fig_w_px
    tick_fs = 13
    tick_style = tu.choose_tick_label_style(fig, x_labels, axes_w_px_estimate, n,
                                             tick_fs, font, 'bold')
    if x_is_ordered and tick_style['rotation']:
        # Numbers and dates go along the axis in order, so fewer of them,
        # level, at round values -- every fifth year -- say as much as every
        # one tilted. Sixty-six years were labelled every other year at 45
        # degrees, with a column of numbers under each label.
        widest_w, widest_h = max((tu.measure_text_px(fig, lbl, tick_fs, font, 'bold')
                                  for lbl in x_labels), key=lambda wh: wh[0])
        tick_style = {'fontsize': tick_fs, 'rotation': 0,
                      'step': max(2, int(np.ceil((widest_w + widest_h) * n / axes_w_px_estimate)))}
    widest_tick_w, widest_tick_h = (
        max((tu.measure_text_px(fig, lbl, tick_style['fontsize'], font, 'bold') for lbl in x_labels),
            key=lambda wh: wh[0])
        if x_labels else (0, 0)
    )
    if tick_style['rotation']:
        import math
        theta = math.radians(tick_style['rotation'])
        tick_header_px = widest_tick_w * math.sin(theta) + widest_tick_h * math.cos(theta)
        # A rotated label is anchored at its own bottom-left corner (see the
        # drawing loop below) and grows up-and-*rightward* from that point.
        # For every label except the last one, that rightward growth lands
        # harmlessly in the gap before the next tick. For the very last
        # (rightmost) tick, there is no next tick to grow into -- it can
        # run straight off the edge of the *figure* (not just the axes),
        # which is exactly the "Mountain Region" clipping bug this block
        # exists to prevent. clip_on=False (used below) only disables
        # clipping at the *axes* boundary; it does nothing to stop the
        # figure canvas itself from cropping the image at save time.
        tick_right_protrusion_px = widest_tick_w * math.cos(theta) + widest_tick_h * math.sin(theta)
    else:
        tick_header_px = widest_tick_h
        tick_right_protrusion_px = 0.0
    tick_header_px += 14  # small gap between chart top and tick text

    fig_h_px = figsize[1] * dpi
    legend_reserve_px = min(legend_reserve_px, 0.4 * fig_h_px)
    if ticks_on_top:
        axes_top_frac = 1 - (title_block_px + tick_header_px) / fig_h_px
        axes_bottom_frac = legend_reserve_px / fig_h_px
    else:
        axes_top_frac = 1 - (title_block_px + 14) / fig_h_px
        axes_bottom_frac = (legend_reserve_px + tick_header_px) / fig_h_px

    # Base margins, in pixels, before accounting for tick-label protrusion.
    left_margin_px = 0.06 * fig_w_px
    base_right_margin_px = 0.06 * fig_w_px
    axes_w_px_target = fig_w_px - left_margin_px - base_right_margin_px

    # If the last tick's rotated label needs more room than the base right
    # margin provides, GROW the figure (rather than shrink the plot area)
    # so the label has somewhere to go without either clipping off-canvas
    # or squeezing the chart itself narrower than intended. A small buffer
    # is added since our width estimate is for the *widest* label overall,
    # used here as a safe upper bound for whichever label ends up last.
    needed_right_margin_px = max(base_right_margin_px, tick_right_protrusion_px + 10)
    if needed_right_margin_px > base_right_margin_px:
        fig_w_px = left_margin_px + axes_w_px_target + needed_right_margin_px
        fig.set_size_inches(fig_w_px / dpi, figsize[1], forward=True)

    left_frac = left_margin_px / fig_w_px
    right_frac = 1 - needed_right_margin_px / fig_w_px

    fig.subplots_adjust(top=axes_top_frac, bottom=axes_bottom_frac,
                          left=left_frac, right=right_frac)
    ax = fig.add_subplot(111)
    ax.set_facecolor(background)

    x_span = x_pos.max() - x_pos.min() if n > 1 else 1.0
    pad = x_span * 0.012 if x_span > 0 else 0.5
    ax.set_xlim(x_pos.min() - pad, x_pos.max() + pad)
    ax.set_ylim(0, y_max_padded if y_max_padded > 0 else 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    axes_w_px = (right_frac - left_frac) * fig_w_px
    axes_h_px = (axes_top_frac - axes_bottom_frac) * fig_h_px

    # ------------------------------------------------------------------
    # Draw each stacked band, bottom to top, with optional hand-drawn
    # jitter on the interior boundaries (never on the outer 0/top edges).
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Draw each stacked band, bottom to top. If hand_drawn jitter is on,
    # it's computed once per interior boundary and reused for BOTH the
    # fill edges and the stroke line -- computing it separately for each
    # would leave a visible sliver where a wobbled stroke doesn't quite
    # trace the (still-exact) fill edge underneath it.
    # ------------------------------------------------------------------
    plot_x = x_pos
    jittered_cumulative = cumulative.copy()
    if hand_drawn and n > 2:
        # One wobble every dozen pixels or so. A wobble at every point was
        # a scribble once points came closer than that: a thousand days of
        # figures drew every boundary as a seismograph.
        n_wobbles = max(3, int(axes_w_px / 12))
        for i in range(1, len(labels)):  # interior boundaries only; 0 and the grand total stay exact
            rng_local = np.random.RandomState(seed + i)
            noise = rng_local.normal(0, (y_max_padded * 0.004 + 1e-9), size=min(n, n_wobbles))
            kernel = np.array([0.2, 0.6, 0.2])
            noise = np.convolve(noise, kernel, mode='same')
            noise[0] = 0
            noise[-1] = 0
            if n > n_wobbles:
                noise = np.interp(plot_x, np.linspace(plot_x.min(), plot_x.max(), n_wobbles), noise)
            jittered_cumulative[i] = cumulative[i] + noise

    for i, label in enumerate(labels):
        lower = jittered_cumulative[i]
        upper = jittered_cumulative[i + 1]
        ax.fill_between(plot_x, lower, upper, color=colors[i], linewidth=0, zorder=2)

    # Crisp boundary strokes between adjacent bands, tracing the exact
    # same (possibly jittered) line used for the fill edges above.
    for i in range(1, len(labels)):
        ax.plot(plot_x, jittered_cumulative[i], color=ink_color, linewidth=1.0,
                 zorder=3, solid_capstyle='round')

    if texture:
        _add_area_texture(ax, plot_x, jittered_cumulative, colors, x_pos.min(), x_pos.max(),
                           y_max_padded, seed=seed)

    # Outer border, matching the source material's framed-card look. The
    # top edge traces the *actual* per-column stack total rather than a
    # flat rectangle at the global max -- real-world stacked data often
    # doesn't sum to an exact constant at every point (rounding in survey
    # data, missing categories at some x, etc; even the original Du Bois
    # numbers this package recreates sum to 99 rather than 100 in one
    # column). A flat-topped border would leave a visible, misleading gap
    # above the fill wherever a column's true total falls short; tracing
    # the real total instead means the border and the fill always meet
    # exactly, and any such gaps in the underlying data are visible as a
    # slight (honest) dip rather than looking like a rendering bug.
    top_line = jittered_cumulative[-1]
    border_x = np.concatenate([[x_pos.min()], plot_x, [x_pos.max()], [x_pos.max()], [x_pos.min()], [x_pos.min()]])
    border_y = np.concatenate([[0], top_line, [top_line[-1]], [0], [0], [0]])
    ax.plot(border_x, border_y, color=ink_color, linewidth=1.2, zorder=5, solid_capstyle='round')

    # ------------------------------------------------------------------
    # Category (x-axis) labels, using the rotation/size/thinning decision
    # made earlier (before the axes were sized) so the reserved header
    # space and the actual rendered labels agree with each other.
    # ------------------------------------------------------------------
    # Tick labels sit a fixed 6px from the edge of the plot: x in data
    # units, y in axes units plus a pixel offset. They used to sit at 2% of
    # the data's height above the top -- about 18px on a typical chart --
    # while only the label's height plus 14px was reserved, so on a chart
    # without a title the year labels ran off the top of the image.
    tick_gap_px = 6
    tick_transform = offset_copy(ax.get_xaxis_transform(), fig=fig, x=0,
                                 y=tick_gap_px if ticks_on_top else -tick_gap_px, units='dots')
    tick_y = 1.0 if ticks_on_top else 0.0
    va = 'bottom' if ticks_on_top else 'top'

    # choose_tick_label_style sized and thinned the labels assuming evenly
    # spaced points (axes width / n per label). Numeric x values needn't
    # be even: 2000, 2020, 2021, 2022, 2023 leaves 2020-2023 crammed into
    # a sliver at the right, and their labels printed on top of each
    # other. So thin again using each label's real position and measured
    # width: keep a label only if it clears the previous kept one, and
    # always keep the final point -- in a time series the latest value is
    # usually the one that matters -- dropping its neighbour instead.
    import math as _math
    x_lim_lo, x_lim_hi = ax.get_xlim()

    def _tick_px(xv):
        return (xv - x_lim_lo) / (x_lim_hi - x_lim_lo) * axes_w_px

    tick_theta = _math.radians(tick_style['rotation']) if tick_style['rotation'] else 0.0

    def _ticks_clear(a, b, gap_px=6.0):
        (a_px, a_w, a_h), (b_px, b_w, b_h) = a, b
        if tick_theta:
            # Parallel rotated labels: what matters is the perpendicular
            # distance between their baselines, not their horizontal extent.
            return (b_px - a_px) * _math.sin(tick_theta) >= max(a_h, b_h) + 2
        return (b_px - b_w / 2) - (a_px + a_w / 2) >= gap_px

    tick_geom = {}
    tick_shift_px = {}
    tick_text: Dict[int, str] = {}      # a label other than the point's own, by index
    axes_left_px = left_frac * fig_w_px

    def _geometry(i):
        if i not in tick_geom:
            w, h = tu.measure_text_px(fig, tick_text.get(i, x_labels[i]), tick_style['fontsize'],
                                      font, 'bold')
            centre = _tick_px(plot_x[i])
            shift = 0.0
            if not tick_theta:
                # A centred label at either end can be wider than the margin
                # beside it (a date like "2024-03-30" is): nudge it inward so
                # it stays on the figure, and thin using where it will be drawn.
                left_edge = axes_left_px + centre - w / 2
                right_edge = axes_left_px + centre + w / 2
                shift = max(0.0, 4 - left_edge) - max(0.0, right_edge - (fig_w_px - 4))
            tick_shift_px[i] = shift
            tick_geom[i] = (centre + shift, w, h)
        return tick_geom[i]

    def _thin(candidates):
        # A run of evenly spaced labels is kept a line's height apart: six
        # pixels apart, "Jan 2000 Jan 2001 Jan 2002" read as one long string.
        # (Two or three labels at uneven places keep the six pixels.) The
        # first and last points may fall anywhere, so a run is judged by the
        # labels between them when there are enough: daily figures from 25
        # January, labelled every fourth month, read "Sep 2020 Jan 2021 May
        # 2021" six pixels apart, since 25 January to 1 September broke the run.
        between = candidates[1:-1] if len(candidates) >= 5 else candidates[:-1]
        steps = np.diff([plot_x[i] for i in between])
        run = len(steps) >= 2 and np.allclose(steps, steps[0], rtol=0.15)
        gap = max([6.0] + [_geometry(i)[2] for i in candidates]) if run else 6.0
        kept: List[int] = []
        for i in candidates:
            if not kept or _ticks_clear(_geometry(kept[-1]), _geometry(i), gap):
                kept.append(i)
            elif i == n - 1:
                # The final point lost to its neighbour: keep the final point,
                # dropping neighbours until it fits (never the first label).
                while len(kept) > 1 and not _ticks_clear(_geometry(kept[-1]), _geometry(i), gap):
                    kept.pop()
                if _ticks_clear(_geometry(kept[-1]), _geometry(i), gap):
                    kept.append(i)
        return kept

    # Daily or weekly dates are labelled at the first of them in a round
    # month, and that label names the month -- "Jul 2021", or "2021" when
    # every one is a January -- rather than the day it happens to be.
    sub_month = (calendar is not None and calendar[1] is _MONTH_STEPS
                 and len(np.unique(calendar[0])) < n)
    if sub_month:
        x_days = sorted(_midnights(as_datetimes(x)))

    def _candidates(step):
        picked = (_round_tick_candidates(calendar, step)
                  or [i for i in range(n) if i % step == 0])
        if picked[-1] != n - 1:
            # Thinning to every k-th point could skip the last one; in a time
            # series the latest point is usually the one that matters.
            picked.append(n - 1)
        return picked

    step = tick_style['step']
    tick_candidates = _candidates(step)
    while True:
        if sub_month:
            inner = [i for i in tick_candidates if i not in (0, n - 1)]
            yearly = all(x_days[i].month == 1 for i in inner)
            tick_text.clear()
            tick_text.update({i: str(x_days[i].year) if yearly else x_days[i].strftime('%b %Y')
                              for i in inner})
            tick_geom.clear()
            tick_shift_px.clear()
        kept_ticks = _thin(tick_candidates)
        # Round values thinned again lose their rhythm -- every other one of
        # 1875, 1880, 1885 is 1875, 1885 -- so for years and months the next
        # step up is tried instead, until all it picks have room (but for
        # the neighbours of the first and last points, which give way to them).
        dropped = set(tick_candidates) - set(kept_ticks)
        if (calendar is None or step >= n
                or dropped <= {tick_candidates[1], tick_candidates[-2]} - {0, n - 1}):
            break
        # The next step that picks other points: with a thousand days, one
        # step at a time took a thousand tries to reach the next round month.
        previous = tick_candidates
        while step < n and tick_candidates == previous:
            step += 1
            tick_candidates = _candidates(step)
    # Value labels (below) are drawn only in these columns: a column whose
    # x label was thinned or crowded out gets no numbers either, or the
    # chart would show numbers under years it doesn't name.
    kept_tick_set = set(kept_ticks)

    for i, (xv, lbl) in enumerate(zip(plot_x, x_labels)):
        if i not in kept_tick_set:
            continue
        lbl = tick_text.get(i, lbl)
        if tick_style['rotation']:
            # Anchor at the label's start (its own corner, not its center)
            # so rotated text extends up-and-away from its tick mark
            # instead of straddling it and crowding into its neighbors.
            ax.text(xv, tick_y, lbl, ha='left', va=va, fontsize=tick_style['fontsize'],
                     fontweight='bold', fontfamily=font, color=ink_color, zorder=6,
                     rotation=tick_style['rotation'], clip_on=False, rotation_mode='anchor',
                     transform=tick_transform)
        else:
            label_transform = (offset_copy(tick_transform, fig=fig, x=tick_shift_px[i], y=0, units='dots')
                               if tick_shift_px.get(i) else tick_transform)
            ax.text(xv, tick_y, lbl, ha='center', va=va, fontsize=tick_style['fontsize'],
                     fontweight='bold', fontfamily=font, color=ink_color, zorder=6,
                     clip_on=False, transform=label_transform)

    # ------------------------------------------------------------------
    # Band labels: try to fit each series' name inside its own band.
    # Anything that doesn't fit gets collected for a legend instead of
    # being forced in illegibly or overflowing into a neighboring band.
    #
    # Every position along the band is tried. At each, the room is the
    # band's height across the label's whole width -- from the highest
    # point of its lower edge to the lowest point of its upper edge -- and
    # the name is centred in that room. Among the positions with close to
    # the most room, the one nearest the middle of the chart wins, so a
    # name doesn't land at the very edge when the band is about as thick
    # in the middle.
    #
    # A name used to be centred on the band's middle at its thickest data
    # point, checked only against the band's thinnest *thickness* under it.
    # A sloping band can be thick enough all along a label and still leave
    # it: on data that changes much from point to point, names and values
    # sat half in the next band (38 of 40 random datasets had text outside
    # its own band). A name that fits nowhere on one line is tried on two.
    # ------------------------------------------------------------------
    legend_needed: List[Tuple[str, str]] = []
    # Pixel-space bounding boxes of every drawn band-name label, so value
    # labels (drawn next, for every series) can be checked against ALL of
    # them -- not just the same series' own label -- since thin, closely
    # stacked bands can easily put one series' name label directly beside
    # a neighboring series' value label.
    occupied_boxes_px: List[Tuple[float, float, float, float]] = []  # (x0, x1, y0, y1)
    # x in pixels from the plot's left edge. (This used to count from the
    # first data point, ignoring the small padding the plot has at each
    # end, so labels "clamped to the edge" stopped about 20px short of it
    # -- far enough that the first column's numbers sat nearer the second
    # year label than their own.)
    px_per_data = axes_w_px / (x_lim_hi - x_lim_lo)
    px_per_y = axes_h_px / (y_max_padded if y_max_padded else 1)
    # Labels near either end are clamped inside the drawn area, which runs
    # from the first x to the last, not inside the plot, which has a little
    # padding beyond it. Clamped to the plot's edge, they hung over the
    # area's border into that padding, where white text on the cream
    # background all but disappears ("1,900" read ",900").
    area_left_px = (x_pos.min() - x_lim_lo) * px_per_data
    area_right_px = (x_pos.max() - x_lim_lo) * px_per_data

    def _clamp_inside_area(desired_px, half_w):
        return min(max(desired_px, area_left_px + half_w), area_right_px - half_w)

    def _band_room(i, xa, xb):
        """For each span from xa to xb (data units): the highest point of band
        i's lower edge within it, and the lowest point of its upper edge.
        The edges are straight between data points, so both are at an end
        of the span or at a data point inside it."""
        lo, hi = jittered_cumulative[i], jittered_cumulative[i + 1]
        xa, xb = np.atleast_1d(np.asarray(xa, float)), np.atleast_1d(np.asarray(xb, float))
        floor = np.maximum(np.interp(xa, plot_x, lo), np.interp(xb, plot_x, lo))
        ceil = np.minimum(np.interp(xa, plot_x, hi), np.interp(xb, plot_x, hi))
        inside = (plot_x[None, :] > xa[:, None]) & (plot_x[None, :] < xb[:, None])
        if inside.any():
            floor = np.maximum(floor, np.where(inside, lo[None, :], -np.inf).max(axis=1))
            ceil = np.minimum(ceil, np.where(inside, hi[None, :], np.inf).min(axis=1))
        return floor, ceil

    if show_band_labels:
        band_w_px = axes_w_px * 0.55
        middle_px = (area_left_px + area_right_px) / 2

        def _name_layouts(label: str, fontsize: float):
            """The band's name on one line and, if it has more than one word,
            on two, broken where the longer line is shortest: (lines, width,
            height) in pixels, for the layouts no wider than band_w_px."""
            caps = display_caps(label)
            _, line_h = tu.measure_text_px(fig, 'Xg', fontsize, font, 'bold')

            def width(s):
                return tu.measure_text_px(fig, s, fontsize, font, 'bold')[0]

            layouts = [([caps], width(caps), line_h)]
            words = caps.split()
            if len(words) > 1:
                splits = [(' '.join(words[:k]), ' '.join(words[k:])) for k in range(1, len(words))]
                widths = [max(width(a), width(b)) for a, b in splits]
                k = int(np.argmin(widths))
                # Two lines, 1.25 line heights apart (as drawn below).
                layouts.append((list(splits[k]), widths[k], line_h * 2.25))
            return [layout for layout in layouts if layout[1] <= band_w_px]

        def _try_place_band(i: int, label: str, fontsize: float, occupied_boxes):
            """Band i's name at exactly this font size, where the band has
            room for it with a fifth of the room to spare above and below,
            clear of every box in `occupied_boxes`. Returns (lines, x, y,
            fontsize, box) -- x and y in data units, the box in pixels --
            or None if it fits nowhere."""
            if (jittered_cumulative[i + 1] - jittered_cumulative[i]).max() <= 0:
                return None
            for lines, label_w_px, label_h_px in _name_layouts(label, fontsize):
                half_w = label_w_px / 2 + 6
                first, last = area_left_px + half_w, area_right_px - half_w
                if first > last:
                    continue
                centres_px = np.linspace(first, last, int((last - first) // 4) + 2)
                centres = x_lim_lo + centres_px / px_per_data
                half_span = (label_w_px / 2 + 3) / px_per_data
                floor, ceil = _band_room(i, centres - half_span, centres + half_span)
                room_px = (ceil - floor) * px_per_y
                fits = np.where(room_px * 0.6 >= label_h_px)[0]
                if not len(fits):
                    continue
                roomy = room_px >= room_px[fits].max() * 0.85
                order = sorted(fits, key=lambda k: (not roomy[k], abs(centres_px[k] - middle_px)
                                                    if roomy[k] else -room_px[k]))
                for k in order:
                    y = (floor[k] + ceil[k]) / 2
                    box = (centres_px[k] - label_w_px / 2 - 8, centres_px[k] + label_w_px / 2 + 8,
                           y * px_per_y - label_h_px / 2 - 4, y * px_per_y + label_h_px / 2 + 4)
                    bx0, bx1, by0, by1 = box
                    if any(bx0 < ox1 and bx1 > ox0 and by0 < oy1 and by1 > oy0
                           for (ox0, ox1, oy0, oy1) in occupied_boxes):
                        continue
                    return (lines, centres[k], y, fontsize, box)
            return None

        # A single SHARED fontsize for every band label, rather than
        # each band independently maximizing its own size against its
        # own widest point -- checked with actual rendered text
        # properties, not assumed: on a 3-series chart with varying band
        # thickness, band labels came out at 16pt, 13.17pt, and 10.17pt
        # respectively, a 36% spread, and bold text at the smaller sizes
        # renders with visibly thinner strokes than the same weight at
        # the larger size, reading as a mismatched font on the same
        # chart even though neither the font family nor the weight had
        # changed. The same bug, and the same fix, as county_map_chart's,
        # pie_chart's, and snake_chart's per-item label sizing (see
        # GENERAL_ENGINE_README.md) -- checked for here once those three
        # made it a known category rather than a one-off.
        #
        # Tried largest-to-smallest, simulating the SAME sequential
        # collision-avoidance the original per-band logic already used
        # (a label placed at index i still has to avoid every label
        # placed at indices before it, at this same candidate size), and
        # committing to the winning size in a second pass so the actual
        # collision bookkeeping (`occupied_boxes_px`) only gets its real
        # entries once, from the fontsize actually used.
        candidate_indices = [i for i in range(len(labels))
                             if (jittered_cumulative[i + 1] - jittered_cumulative[i]).max() > 0]
        winning_results = None
        trials = []
        for candidate_fs in (16, 15, 14, 13, 12, 11, 10, 9, 8):
            trial_occupied: List[Tuple[float, float, float, float]] = []
            trial_results = {}
            for i in candidate_indices:
                result = _try_place_band(i, labels[i], candidate_fs, trial_occupied)
                if result is not None:
                    trial_results[i] = result
                    trial_occupied.append(result[4])
            trials.append((candidate_fs, trial_results))
            if len(trial_results) >= max(1, len(candidate_indices) * 0.6):
                winning_results = trial_results
                break
        if winning_results is None:
            winning_results = shared_size_fallback(trials)

        for i, label in enumerate(labels):
            if i not in winning_results:
                legend_needed.append((label, colors[i]))
                continue
            lines, label_x, mid_y, fs, candidate_box = winning_results[i]
            txt_color = _text_color_for(colors[i])
            _, line_h_px = tu.measure_text_px(fig, 'Xg', fs, font, 'bold')
            line_gap = line_h_px * 1.25 / px_per_y
            start_y = mid_y + line_gap * (len(lines) - 1) / 2
            for k, ln in enumerate(lines):
                ax.text(label_x, start_y - k * line_gap, ln, ha='center', va='center',
                         fontsize=fs, fontweight='bold', fontfamily=font,
                         color=txt_color, zorder=6)
            occupied_boxes_px.append(candidate_box)
    else:
        legend_needed = list(zip(labels, colors))

    # ------------------------------------------------------------------
    # Per-x value labels: one per series, placed at the vertical center
    # of that series' own band (not at a shared boundary edge, where two
    # adjacent series' labels would crowd into the same few pixels), and
    # skipped wherever the band is too thin at that point to hold a
    # label without spilling into its neighbor -- the same "don't label
    # a sliver" rule a pie chart applies to its smallest slices.
    #
    # If the band's middle is already taken -- by a band-name label, or
    # by another value label -- the label tries positions progressively
    # further above and below the middle, staying inside its own band,
    # before giving up. It used to give up immediately, which on sparse
    # time series threw away most of the chart's numbers: band names can
    # only anchor on a real data point, so with x = [2001, 2022, 2024]
    # three of the four names landed on the 2022 column, and every value
    # they touched was dropped -- 7 of 12, including the current-year
    # figures, the ones a reader most wants. Value labels are also now
    # checked against each other, not only against band names: with
    # irregularly spaced x values (2020, 2021, 2022 after a 2000 start)
    # neighbouring values in the same band used to print on top of each
    # other.
    # ------------------------------------------------------------------
    if show_value_labels:
        value_fs = 9
        # Values go in exactly the columns whose x label is shown. They used
        # to be thinned on their own schedule (every n // 14 points), which
        # with 100 points put numbers under years that had no label.
        value_columns = sorted(kept_tick_set)
        _, val_h_px = tu.measure_text_px(fig, '0%', value_fs, font, 'bold')
        min_band_px = val_h_px * 1.6
        placed_value_boxes_px: List[Tuple[float, float, float, float]] = []

        def _box_is_free(box):
            bx0, bx1, by0, by1 = box
            return not any(bx0 < ox1 and bx1 > ox0 and by0 < oy1 and by1 > oy0
                           for (ox0, ox1, oy0, oy1) in occupied_boxes_px + placed_value_boxes_px)

        for i in range(len(labels)):
            band_thickness = values[i]
            lower = jittered_cumulative[i]
            upper = jittered_cumulative[i + 1]
            mid = (lower + upper) / 2
            for j in value_columns:
                val = band_thickness[j]
                if val <= 0:
                    continue
                band_px = (val / y_max_padded) * axes_h_px if y_max_padded else 0
                if band_px < min_band_px:
                    continue  # too thin here to hold a label -- skip rather than overlap
                txt = number_text(value_format, val)
                txt_w_px, txt_h_px = tu.measure_text_px(fig, txt, value_fs, font, 'bold')
                # Clamp near the left/right edges so the label text itself
                # stays inside the drawn area, clear of its border, same
                # idea as the band name clamping above.
                desired_px = (plot_x[j] - x_lim_lo) * px_per_data
                half_w = txt_w_px / 2 + 5
                clamped_px = _clamp_inside_area(desired_px, half_w)
                label_x = x_lim_lo + clamped_px / px_per_data
                vx0, vx1 = clamped_px - txt_w_px / 2 - 3, clamped_px + txt_w_px / 2 + 3
                half_h = txt_h_px / 2 + 3

                # Where the label's centre may go: inside its own band
                # across the label's whole width, not just at its centre --
                # a sloped boundary can be many pixels higher at one edge
                # of the label than at the other. The band's middle comes
                # first, moved just far enough to be inside, then positions
                # above and below it. (The middle itself went unchecked, so
                # on a steep slope a value printed half over the next band.)
                floor, ceil = _band_room(i, x_lim_lo + vx0 / px_per_data,
                                         x_lim_lo + vx1 / px_per_data)
                lowest_px = floor[0] * px_per_y + half_h + 1
                highest_px = ceil[0] * px_per_y - half_h - 1
                if lowest_px > highest_px:
                    continue  # too thin across the label to hold it

                centre_px = min(max(mid[j] * px_per_y, lowest_px), highest_px)
                candidates = [centre_px]
                step_px = txt_h_px + 4
                k = 1
                while True:
                    added = False
                    for c in (centre_px + k * step_px, centre_px - k * step_px):
                        if lowest_px <= c <= highest_px:
                            candidates.append(c)
                            added = True
                    if not added:
                        break
                    k += 1

                for y_px in candidates:
                    box = (vx0, vx1, y_px - half_h, y_px + half_h)
                    if not _box_is_free(box):
                        continue
                    txt_color = _text_color_for(colors[i])
                    ax.text(label_x, y_px / px_per_y, txt, ha='center', va='center',
                             fontsize=value_fs, fontweight='bold', fontfamily=font,
                             color=txt_color, zorder=6)
                    placed_value_boxes_px.append(box)
                    break

    # ------------------------------------------------------------------
    # Legend for any band label(s) that didn't fit -- this is the
    # graceful fallback rather than clipping or overlapping text.
    # ------------------------------------------------------------------
    legend_top_px = 0.0
    if legend_needed:
        _, legend_top_px = add_legend(fig, legend_needed, ink_color, font, 0.96 * fig_w_px,
                                      max_height_px=legend_reserve_px)

    # ------------------------------------------------------------------
    # Title block, placed in figure-fraction space above the axes using
    # the line counts computed earlier -- so 1-line and 3-line titles
    # both end up with correctly sized, non-overlapping space.
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

    return fig, legend_top_px, legend_reserve_px


def _add_area_texture(ax, plot_x, cumulative, colors, x0, x1, y_max, seed=0):
    """
    Light, generalized version of the hand-painted grain used in
    plate51.py -- generated from each series' own color (lightened /
    darkened automatically) rather than hand-picked shades, so it works
    for whatever palette the caller passes in, not just green-and-black.
    Each band's grain is stretched over the whole plot and clipped to the
    band; the axes' GrainLayer draws them all as one image.
    """
    from scipy.ndimage import gaussian_filter
    rng = np.random.RandomState(seed + 1000)
    layer = GrainLayer.of(ax)

    for i, base_color in enumerate(colors):
        lower = cumulative[i]
        upper = cumulative[i + 1]
        if np.allclose(upper - lower, 0):
            continue
        light = _shade(base_color, 0.12)
        dark = _shade(base_color, -0.12)

        h, w = 300, 260
        grain = gaussian_filter(rng.normal(0, 1, size=(h, w)), sigma=0.8)
        grain = grain / (np.abs(grain).max() + 1e-9)
        streaks = streak_field(rng.normal(0, 1, size=(h, w)))
        streaks = streaks / (np.abs(streaks).max() + 1e-9)
        combined = 0.6 * grain + 0.4 * streaks

        base_rgb = np.array(plt.matplotlib.colors.to_rgb(base_color))
        light_rgb = np.array(plt.matplotlib.colors.to_rgb(light))
        dark_rgb = np.array(plt.matplotlib.colors.to_rgb(dark))
        band = Path(np.concatenate([np.column_stack([plot_x, lower]),
                                    np.column_stack([plot_x[::-1], upper[::-1]]),
                                    [[plot_x[0], lower[0]]]]), closed=True)
        layer.add(band, (x0, x1, 0, y_max), functools.partial(np.asarray, combined),
                  (0.14, base_rgb, light_rgb, dark_rgb))
