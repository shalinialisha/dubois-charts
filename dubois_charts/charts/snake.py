"""
General-purpose Du Bois-style snake (wrapped bar) chart.

Same relationship to plate51.py as the other general chart types have
(see GENERAL_ENGINE_README.md): arbitrary segments, arbitrary label
length, a title of whatever length the caller has, sized from real
measurements at render time.

The layout problem here is different again from anything else in the
package. `area.py`, `bar.py`, and `butterfly.py` place labels along a
straight edge; `spiral.py` places them around a curve. A snake chart
takes ONE long scale -- a single 100%-style breakdown -- and folds it
into several rows to fit a compact aspect ratio, alternating each row's
reading direction (left-to-right, then right-to-left, boustrophedon-
style) so the eye can follow the scale continuously from one row into
the next rather than jumping back to a left margin. That means:

  - A segment can straddle a row boundary and has to be drawn as two (or
    more, for a segment wider than a full row) separate rectangle
    pieces that are visually broken but represent one logical category.
  - "Left" and "right" swap meaning every other row, so a label glued to
    "the start of the segment" needs a different actual on-screen anchor
    depending on which row it's in.
  - Segments can be split into pieces far too narrow to hold their own
    label even when the *whole* segment easily could -- so label
    placement has to consider the widest single piece a segment was cut
    into, not the segment's total width.
"""

import re
import warnings
from typing import Dict, Optional, Sequence, Tuple
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
    validate_colors,
    literal_text,
    font_stack,
    segment_items,
    as_numbers,
    default_value_format_for,
    check_value_format,
    title_top,
    add_legend,
    number_text,
    shared_size_fallback,
)


_FIXED_FIELD = re.compile(r'(\{[^{}:]*:[^{}]*?\.)(\d+)([fF%]\})')


def _scale_mark_format(value_format: str, row_width: float, n_rows: int) -> str:
    """
    The format for the marks at the rows' ends: `value_format`, with the
    fewest decimals that put every mark within a twentieth of a row of the
    value it marks. Seventeen papers over five rows are 3.4 a row, and
    with whole numbers the marks read "0 ... 3", "7 ... 3", "7 ... 10": a
    segment of 3 stopped well short of the "3". And the marks are round
    numbers more often than the values are: shares of the world's
    electricity, published to three decimals, put "20.000%" and "40.000%"
    at the rows' ends, where "20%" and "40%" say the same.
    """
    fields = _FIXED_FIELD.findall(value_format)
    if len(fields) != 1:
        return value_format
    shift = 2 if fields[0][2].startswith('%') else 0    # '{:.0%}' writes 0.25 as "25%"
    marks = [row * row_width for row in range(n_rows + 1)]
    for decimals in range(int(fields[0][1]) + 4):
        if max(abs(m - round(m, decimals + shift)) for m in marks) <= 0.05 * row_width + 1e-12:
            break
    return _FIXED_FIELD.sub(lambda m: f'{m.group(1)}{decimals}{m.group(3)}', value_format)


@literal_text
def snake_chart(
    segments: Dict[str, float],
    n_rows: int = 5,
    total: Optional[float] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    colors: Optional[Sequence[str]] = None,
    value_format: Optional[str] = None,
    show_value_labels: bool = True,
    alternate_direction: bool = True,
    texture: bool = True,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    seed: int = 0,
) -> plt.Figure:
    """
    Render a Du Bois-styled snake chart: one long scale, folded into
    `n_rows` rows with alternating reading direction.

    Parameters
    ----------
    segments : Dict[str, float]
        Ordered category -> value pairs along the scale, each zero or
        more, e.g. a 100% breakdown: a dict, or a pandas Series (index ->
        value). Names can be text, numbers or dates. Order matters --
        this is a sequence being folded, not an unordered set.
    n_rows : int
        How many rows to fold the scale into: a whole number, 1 or more.
    total : float, optional
        The full scale the rows divide up (e.g. 100 for a percentage
        breakdown). Defaults to `sum(segments.values())`. Explicitly
        pass this if your segments don't fill the whole scale and you
        want the remainder left visibly blank rather than the scale
        shrinking to fit just what's given.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width. The title is in
        capitals, as on the plates, except words whose mixed case is
        deliberate; the subtitle is as written.
    colors : Sequence[str], optional
        One color per segment. Defaults to
        `dubois_charts.colors.get_categorical(...)`.
    value_format : str, optional
        `str.format`-style template for each segment's value, shown
        alongside its name where there's room, and for the scale marks
        under the ends of each row. By default, plain numbers at the
        data's own precision -- with a percent sign when the scale's total
        is 100, since every value is then a percentage of it.
    show_value_labels : bool
        If True, a segment's value follows its name, on the snake or in
        the legend.
    alternate_direction : bool
        If True (the namesake behavior), odd rows read right-to-left so
        the scale continues smoothly from the end of one row into the
        start of the next. If False, every row reads left-to-right (a
        plain wrap, not a snake) -- occasionally preferable if your
        audience finds the alternating direction more confusing than
        space-saving for a given dataset.
    texture : bool
        Overlay a light hand-painted-style grain on each segment piece.
    background : str
        The figure's colour: the cream of the plates' paper by default.
        Text is dark on a light background and light on a dark one.
    figsize : (float, float), optional
        If not given, 10 inches wide, and 0.9 inches a row plus room for
        the title (3.5 to 16 inches tall).
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

    A segment's name, and its value, go inside its widest piece where
    they fit, all names at one size; the rest are listed, with their
    values, in a legend under the snake. The marks at the rows' ends have
    as many decimals as it takes to show where each row ends: 17 over 5
    rows is 3.4 a row.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = snake_chart(
    ...     segments={
    ...         'Agriculture': 45, 'Domestic Service': 25, 'Manufacturing': 12,
    ...         'Trade': 10, 'Professions': 8,
    ...     },
    ...     n_rows=4,
    ...     title='Occupations, Folded to Fit',
    ... )
    """
    pairs = segment_items(segments, "snake_chart")
    if len(pairs) == 0:
        raise ValueError("`segments` must contain at least one entry.")
    if (isinstance(n_rows, (bool, np.bool_)) or not isinstance(n_rows, (int, float, np.integer, np.floating))
            or not float(n_rows).is_integer() or n_rows < 1):
        raise ValueError(f"`n_rows` must be a whole number of rows, 1 or more; got {n_rows!r}.")
    n_rows = int(n_rows)

    labels = [label for label, _ in pairs]
    values = as_numbers([v for _, v in pairs], "segment values", names=labels)
    negative = [f'{labels[i]!r} ({values[i]:g})' for i in np.where(values < 0)[0]]
    if negative:
        raise ValueError(
            f"Segment {', '.join(negative[:5])}{' and more' if len(negative) > 5 else ''} "
            f"{'is' if len(negative) == 1 else 'are'} negative. Each segment is a length along "
            f"the scale, so every value must be zero or more.")

    scale_total = total if total is not None else float(values.sum())
    if scale_total <= 0:
        raise ValueError("The scale total must be positive.")
    if values.sum() > scale_total + 1e-9:
        raise ValueError(
            f"segments sum to {values.sum():g}, which is more than "
            f"total={scale_total:g} -- either raise `total` or reduce "
            "the segment values so they fit within the stated scale."
        )

    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    if colors is None:
        colors = dubois_colors.get_categorical(len(labels))
    colors = validate_colors(colors, len(labels), 'segments', each_needs_own=False)

    row_width = scale_total / n_rows
    if value_format is None:
        # From the segment values alone: the scale marks at row ends take
        # the same format, so 100 split over 6 rows reads "17%", not every
        # label turning into "60.00%" to show 16.67 exactly.
        value_format = default_value_format_for(values, [scale_total])
    check_value_format(value_format)
    mark_format = _scale_mark_format(value_format, row_width, n_rows)

    # ------------------------------------------------------------------
    # Cut every segment into per-row pieces up front. A piece is
    # (segment_index, row, local_x0, local_x1) where local_x is measured
    # left-to-right WITHIN that row's own span (direction mirroring for
    # alternating rows is applied later, at draw time, not here -- doing
    # it here would make the "which pieces does segment i have" bookkeeping
    # direction-dependent for no benefit). A segment wider than a single
    # row correctly produces more than two pieces if it needs to.
    # ------------------------------------------------------------------
    cum = np.concatenate([[0.0], np.cumsum(values)])
    pieces = []  # list of dicts: seg_idx, row, local_x0, local_x1
    for i in range(len(labels)):
        seg_start, seg_end = cum[i], cum[i + 1]
        if seg_end <= seg_start:
            continue  # zero-value segment: nothing to draw
        row_start = int(seg_start // row_width)
        row_end = min(int(np.ceil(seg_end / row_width)) - 1, n_rows - 1)
        for row in range(row_start, row_end + 1):
            row_lo, row_hi = row * row_width, (row + 1) * row_width
            piece_lo = max(seg_start, row_lo)
            piece_hi = min(seg_end, row_hi)
            if piece_hi <= piece_lo:
                continue
            pieces.append({
                'seg_idx': i,
                'row': row,
                'local_x0': piece_lo - row_lo,
                'local_x1': piece_hi - row_lo,
            })

    # ------------------------------------------------------------------
    # Figure sizing and title block (same pattern as every other chart).
    # ------------------------------------------------------------------
    if figsize is None:
        height = min(max(3.5, 0.9 * n_rows + 1.8), 16.0)
        figsize = (10.0, height)

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

    scale_label_fs = 9
    _, scale_label_h_px = tu.measure_text_px(fig, 'Xg', scale_label_fs, font, 'bold')

    # ------------------------------------------------------------------
    # Room for the legend. Segments too narrow for their name are listed
    # in a legend under the snake; how many that is depends on how tall
    # the rows are, which depends on the room the legend takes. So the
    # names are fitted, the legend given the room it then needs, and the
    # names fitted again, until that settles. The legend gets at most 35%
    # of the figure; past that it lists the largest segments and says how
    # many more there are.
    #
    # (Room used to be reserved for every segment, four to a row, whether
    # they needed it or not: 100 segments squeezed the snake into a third
    # of the figure, and from about 170 the room was taller than the
    # figure and the chart crashed with matplotlib's "bottom cannot be >=
    # top". Before that, with no room reserved at all, the legend ran off
    # the bottom of the figure.)
    # ------------------------------------------------------------------
    legend_sizes = (10.0,)
    legend_width_px = 0.96 * fig_w_px
    axes_top_frac = 1 - title_block_px / fig_h_px
    axes_w_px = 0.91 * fig_w_px
    px_per_data_x = axes_w_px / row_width if row_width else 1.0

    row_pad = 0.14
    row_h = 1 - 2 * row_pad

    def _legend_top(entries):
        """How far above the bottom of the figure, in px, the top of a
        legend of these (name, colour) entries is."""
        if not entries:
            return 0.0
        legend, top = add_legend(fig, entries, ink_color, font, legend_width_px, sizes=legend_sizes)
        legend.remove()
        return top

    def _legend_entries(listed, unplaced):
        # With its value: a segment named only in the legend used to have
        # no number anywhere (17 of 22 occupations), and a segment of 0 --
        # listed, since it has no width for a name -- read as one missing.
        entries = [(f"{labels[i]}  {number_text(value_format, values[i])}" if show_value_labels
                    else labels[i], colors[i % len(colors)]) for i in listed]
        if len(listed) < len(unplaced):
            entries.append((f'+ {len(unplaced) - len(listed)} more', None))
        return entries

    def _display_x(row: int, local_x: float) -> float:
        """Map a row-local x (always left-to-right in the underlying
        data) to where it actually gets drawn, mirroring odd rows when
        alternate_direction is on -- the one piece of arithmetic the
        whole "snake" behavior actually boils down to."""
        if alternate_direction and (row % 2 == 1):
            return row_width - local_x
        return local_x

    # ------------------------------------------------------------------
    # Segment labels: pick each segment's WIDEST single piece (not its
    # total width, which may be spread across pieces far too narrow
    # individually to hold text even though the segment as a whole is
    # generous), and solve for a single SHARED fontsize across every
    # segment label -- not each one independently maximizing its own
    # size against its own widest piece. Checked with actual rendered
    # text properties, not assumed: on a 5-segment snake chart with
    # varying piece widths, "Agriculture" (a full-row-width piece) came
    # out at 13pt while "Trade" (a much narrower piece) came out around
    # 7.2pt, a 44% difference -- bold text at the smaller size renders
    # with visibly thinner strokes than the same weight at the larger
    # size, reading as a mismatched font on the same chart even though
    # neither the font family nor the weight had changed. This is the
    # same bug, and the same fix, as county_map_chart's and pie_chart's
    # per-item label sizing (see GENERAL_ENGINE_README.md) -- checked
    # for here once those two made it clear this was a category of bug,
    # not a one-off.
    # ------------------------------------------------------------------
    def _no_word_was_broken(original_text: str, lines) -> bool:
        """Did wrapping split a single word across two lines (e.g. "Other"
        into "Oth" / "er"), rather than only ever breaking at an existing
        space? `wrap_text_to_width`'s hard-break fallback (for a single
        word wider than the available space on its own) is correct and
        necessary in general, but a caller offering a shared fontsize
        across many differently-sized pieces can end up locking in that
        fallback for a short, ordinary word like "Other" simply because
        its own piece happens to be very narrow -- found by rendering a
        real 8-category electricity-source breakdown where "Other" (1.2%
        of the total, a genuinely common, short, real-world category
        name) rendered as "Oth" over "er". Comparing the reconstructed
        words against the original catches this precisely: a clean wrap
        only ever moves whole words between lines, so re-joining and
        re-splitting the result must reproduce the exact original word
        list."""
        return ' '.join(lines).split() == original_text.split()

    widest_piece = {}
    for piece in pieces:
        best = widest_piece.get(piece['seg_idx'])
        if best is None or piece['local_x1'] - piece['local_x0'] > best['local_x1'] - best['local_x0']:
            widest_piece[piece['seg_idx']] = piece

    def _segment_fits_at_size(i: int, label: str, fontsize: float, px_per_row_y: float):
        widest = widest_piece.get(i)
        if widest is None:
            return None
        piece_w_data = widest['local_x1'] - widest['local_x0']
        box_w_px = piece_w_data * px_per_data_x * 0.88
        box_h_px = row_h * px_per_row_y * 0.7

        text = f"{label}  {number_text(value_format, values[i])}" if show_value_labels else label
        # Quick no: words are never broken, so a piece narrower than the
        # longest word of the name, or lower than one line, can't hold it.
        # (Checking every one of 500 narrow pieces in full took 17 seconds.)
        if tu.measure_text_px(fig, 'Xg', fontsize, font, 'bold')[1] > box_h_px or max(
                tu.measure_text_px(fig, w, fontsize, font, 'bold')[0] for w in label.split() or ['']) > box_w_px:
            return None
        # Forcing min_fontsize == max_fontsize == this exact candidate
        # makes fit_label_in_box check only "does it fit AT this size,"
        # rather than searching for its own best size -- the search
        # across candidates now happens once, up front, across every
        # segment together, rather than once per segment independently.
        # On two lines, or three. A segment whose name fits but not with its
        # number goes to the legend, where it has both: it used to be named
        # here without one ("STEAM RAILWAY EMPLOYEES", and no 7,440).
        fitted = None
        for max_lines in (2, 3):
            fitted = tu.fit_label_in_box(fig, text, box_w_px, box_h_px, font, 'bold',
                                          max_fontsize=fontsize, min_fontsize=fontsize,
                                          max_lines=max_lines)
            if fitted is not None and _no_word_was_broken(text, fitted[0]):
                break
            fitted = None
        if fitted is None:
            return None
        lines, fs = fitted
        dx0, dx1 = sorted([_display_x(widest['row'], widest['local_x0']),
                            _display_x(widest['row'], widest['local_x1'])])
        cx = (dx0 + dx1) / 2
        cy = widest['row'] + 0.5
        return (lines, cx, cy)

    def _fit_labels(px_per_row_y):
        trials = []
        for candidate_fs in (13, 12, 11, 10, 9, 8, 7):
            fitting = {}
            for i, label in enumerate(labels):
                result = _segment_fits_at_size(i, label, candidate_fs, px_per_row_y)
                if result is not None:
                    fitting[i] = result
            if len(fitting) >= max(1, len(labels) * 0.6):
                return candidate_fs, fitting
            trials.append((candidate_fs, fitting))
        fitting = shared_size_fallback(trials)
        return next(fs for fs, f in trials if f is fitting), fitting

    base_bottom_px = 20
    max_legend_px = 0.35 * fig_h_px
    legend_px = 0.0
    for _ in range(8):
        axes_bottom_frac = (base_bottom_px + legend_px) / fig_h_px
        axes_h_px = (axes_top_frac - axes_bottom_frac) * fig_h_px
        px_per_row_y = axes_h_px / n_rows if n_rows else 1.0
        shared_fs, placements = _fit_labels(px_per_row_y)
        unplaced = [i for i in range(len(labels)) if i not in placements]
        legend_need = min(_legend_top(_legend_entries(unplaced, unplaced)), max_legend_px)
        if legend_need <= legend_px + 0.5:
            break
        legend_px = legend_need

    # Which segments the legend lists: all of those without a name on the
    # snake, unless they don't fit in its room -- then as many of the
    # largest of them as do, in their order along the scale, and a last
    # entry saying how many more there are.
    listed = unplaced
    if _legend_top(_legend_entries(unplaced, unplaced)) > legend_px + 0.5:
        by_size = sorted(unplaced, key=lambda i: -values[i])
        lo, hi = 0, len(unplaced) - 1        # the most that fit is in lo..hi
        while lo < hi:
            keep = (lo + hi + 1) // 2
            if _legend_top(_legend_entries(sorted(by_size[:keep]), unplaced)) <= legend_px + 0.5:
                lo = keep
            else:
                hi = keep - 1
        listed = sorted(by_size[:lo])
        warnings.warn(
            f"snake_chart: {len(unplaced)} of the {len(labels)} segments are too narrow for their "
            f"names, more than the legend has room for, so it lists the {len(listed)} largest. "
            f"Fewer segments, or more rows (n_rows), label more.", UserWarning, stacklevel=3)

    fig.subplots_adjust(top=axes_top_frac, bottom=axes_bottom_frac, left=0.045, right=0.955)
    ax = fig.add_subplot(111)
    ax.set_facecolor(background)

    ax.set_xlim(0, row_width)
    ax.set_ylim(n_rows, 0)  # row 0 at top
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # ------------------------------------------------------------------
    # Draw every piece. A given segment can own several pieces (split
    # across rows); all pieces from the same segment share its color.
    # ------------------------------------------------------------------
    for piece in pieces:
        i, row = piece['seg_idx'], piece['row']
        lo, hi = piece['local_x0'], piece['local_x1']
        color = colors[i % len(colors)]
        y0 = row + row_pad
        # A mirrored row's rectangle still needs x0 < x0+width; compute
        # the two display-space edges and sort them rather than assuming
        # which one ends up smaller.
        dx0, dx1 = sorted([_display_x(row, lo), _display_x(row, hi)])
        ax.add_patch(plt.Rectangle((dx0, y0), dx1 - dx0, row_h, facecolor=color,
                                     edgecolor=ink_color, linewidth=0.9, zorder=2))
        if texture:
            add_rect_texture(ax, dx0, y0, dx1 - dx0, row_h, color,
                              seed=seed + i * 41 + row * 7)

    # ------------------------------------------------------------------
    # Scale anchors: the actual global cumulative value at each row's
    # two screen edges, so the fold is still readable as ONE scale
    # rather than n_rows disconnected bars. Needed precisely because
    # alternating direction means "left edge" doesn't consistently mean
    # "smaller value" the way it would on a single ordinary axis.
    #
    # They go just under each row's ends, on the background. They used to
    # go inside the row, over whatever segment was there, in ink that
    # couldn't be read on a dark one: "3,500 €" on navy, "2,625 €" on
    # black. Where rows are too close together for a line of text between
    # them, they stay inside, on a patch of the background colour.
    # ------------------------------------------------------------------
    gap_px = 2 * row_pad * px_per_row_y
    outside = gap_px >= scale_label_h_px + 4
    nudge = 2 / px_per_row_y if px_per_row_y else 0.0
    for row in range(n_rows):
        row_lo_val, row_hi_val = row * row_width, (row + 1) * row_width
        left_val, right_val = ((row_hi_val, row_lo_val)
                                if (alternate_direction and row % 2 == 1)
                                else (row_lo_val, row_hi_val))
        y = row + 1 - row_pad
        placement = (dict(va='top') if outside else
                     dict(va='bottom', bbox=dict(boxstyle='square,pad=0.15', facecolor=background,
                                                 edgecolor='none')))
        for x, value, ha in ((0, left_val, 'left'), (row_width, right_val, 'right')):
            ax.text(x, y + nudge if outside else y - nudge, number_text(mark_format, value),
                    ha=ha, fontsize=scale_label_fs, fontweight='bold', fontfamily=font,
                    color=ink_color, zorder=6, **placement)

    for i, label in enumerate(labels):
        if i not in placements:
            continue
        lines, cx, cy = placements[i]
        txt_color = _text_color_for(colors[i % len(colors)])
        _, line_h_px = tu.measure_text_px(fig, 'Xg', shared_fs, font, 'bold')
        line_gap = (line_h_px / axes_h_px) * n_rows * 1.2 if axes_h_px else 0
        start_y = cy - line_gap * (len(lines) - 1) / 2
        for k, ln in enumerate(lines):
            ax.text(cx, start_y + k * line_gap, ln, ha='center', va='center',
                     fontsize=shared_fs, fontweight='bold', fontfamily=font,
                     color=txt_color, zorder=6)

    # A thin ink border around each row, matching the framed-card look
    # used elsewhere in the package.
    for row in range(n_rows):
        ax.add_patch(plt.Rectangle((0, row + row_pad), row_width, row_h, fill=False,
                                     edgecolor=ink_color, linewidth=0.9, zorder=1))

    if unplaced:
        add_legend(fig, _legend_entries(listed, unplaced), ink_color, font, legend_width_px,
                   sizes=legend_sizes)

    # ------------------------------------------------------------------
    # Title block, in figure-fraction space above the axes.
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
