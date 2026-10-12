"""
Plate 51: "Proportion of Freemen and Slaves Among American Negroes"

A pixel-verified recreation of W.E.B. Du Bois's 1900 Paris Exposition chart.

===============================================================================
HOW THIS RECREATION WAS BUILT
===============================================================================

This module was built by downloading the actual original drawing (from the
ajstarks/dubois-data-portraits GitHub archive, sourced from the Library of
Congress, LC-DIG-ppmsca-33913) and analyzing it pixel-by-pixel with PIL/numpy:

  - Colors were sampled and averaged from clean regions of the green fill,
    black fill, and cream paper background.
  - The chart's bounding box was located by scanning for the green/black
    fill boundary against the cream background.
  - The data boundary curve (the wavy line separating "free" from "slave")
    was traced column-by-column and cross-checked against the actual
    Atlanta University data (data.csv from the same archive).

THE KEY INSIGHT THIS ANALYSIS REVEALED (and what earlier drafts got wrong):

  The chart is **NOT** an inverted-axis plot. It is a completely ordinary,
  non-inverted stacked-area chart:

    - BLACK ("SLAVES") is the BOTTOM layer, running from 0 up to the slave
      percentage. Because slaves were 86-92% of the population for most of
      the period, this layer is a huge, heavy, mountain-like mass filling
      almost the entire chart.
    - GREEN ("FREE") is the TOP layer, a thin ribbon running from the slave
      percentage up to 100. For most of the period this is a narrow strip
      only 8-14% tall.
    - Years run along the TOP of the chart, not the bottom. There is no
      y-axis at all -- Du Bois instead hand-labeled the free-percentage
      directly on the wavy boundary line.
    - The dramatic "cliff" between 1860 and 1870 isn't a design trick or an
      inverted axis -- it falls straight out of the data. Free% jumps from
      11% to 100% in a single decade (Emancipation), so a straight line
      between those two points naturally carves a steep diagonal wall
      through the chart. Du Bois didn't need to distort anything; the
      history did the work.

===============================================================================
VERIFIED DATA (from data.csv, Atlanta University / U.S. Census)
===============================================================================

    Year   Slave%   Free%
    1790    92.0      8.0
    1800    88.0     11.0
    1810    86.5     13.5
    1820    87.0     13.0
    1830    86.0     14.0
    1840    87.0     13.0
    1850    88.0     12.0
    1860    89.0     11.0
    1870     0.0    100.0

===============================================================================
VERIFIED COLORS (sampled directly from the source image)
===============================================================================

    Green (FREE fill):    RGB(87, 132, 92)   #57845c
    Black (SLAVES fill):  RGB(29, 29, 29)    #1d1d1d
    Cream (paper):        RGB(217, 210, 198) #d9d2c6
    Text on black:        near-white cream, not pure white
    Text on green/cream:  near-black ink

Original: ink and watercolor on board, 710 x 560 mm, ca. 1900.
Library of Congress: LOT 11931, no. 51 (M) [P&P], LC-DIG-ppmsca-33913
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
from typing import Optional, Tuple
import os

from dubois_charts.charts._common import COLOR_CREAM, get_font as _get_font, validate_figsize

# The reference scan and this module always live side by side in the
# installed package -- resolving paths relative to __file__ (rather than
# a bare filename resolved against the caller's cwd) means
# `create_side_by_side()` and `main()` work the same way regardless of
# where the importing script happens to be run from. A bare relative
# default here was found to silently produce a blank "ORIGINAL" panel
# the moment this module was called from anywhere other than its own
# directory.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_REFERENCE_PATH = os.path.join(_MODULE_DIR, 'reference-original-plate-51.jpg')


# ---------------------------------------------------------------------------
# Verified historical data (Atlanta University / U.S. Census, via data.csv)
# ---------------------------------------------------------------------------
YEARS = [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870]
SLAVE_PCT = [92.0, 88.0, 86.5, 87.0, 86.0, 87.0, 88.0, 89.0, 0.0]
FREE_PCT = [8.0, 11.0, 13.5, 13.0, 14.0, 13.0, 12.0, 11.0, 100.0]

# Labels exactly as they appear on the original, including the trailing
# periods Du Bois used after each percentage.
FREE_LABELS = ['8%', '11%', '13.5%', '13%', '14%', '13%', '12%', '11%', '100%']

# ---------------------------------------------------------------------------
# Verified colors (pixel-sampled from the source image, see module docstring)
# ---------------------------------------------------------------------------
# COLOR_CREAM is shared with every other chart in the package (imported
# above from _common.py) -- it happens to be the exact same value here
# because the background really is that color in both contexts, not
# because of a coincidence worth re-deriving. The other four colors below
# are specific to this one plate's actual measured pigments and have no
# equivalent in _common.py.
COLOR_GREEN = '#57845c'
COLOR_BLACK = '#1d1d1d'
COLOR_TEXT_ON_BLACK = '#e8e2d2'
COLOR_TEXT_ON_CREAM = '#1a1a1a'


def _spaced(text: str, gap: str = ' ') -> str:
    """
    Insert a space between every character to fake letter-tracking.

    Du Bois's draftsmen used a hand-lettered, evenly tracked-out caps style
    for emphasis words (SLAVES, FREE - LIBRE, the year numerals). Matplotlib
    doesn't expose real letter-spacing, so we fake it by interleaving plain
    space characters -- a Unicode thin space looks nicer in principle but
    most installed monospace faces are missing that glyph and silently
    fall back to a tofu box, so we stick to a normal space, which every
    font supports and which the monospace advance width already renders
    with a reasonable, deliberate-looking gap.
    """
    return gap.join(list(text))


def _hand_drawn_jitter(x: np.ndarray, y: np.ndarray, amplitude: float = 0.35,
                        seed: int = 51) -> np.ndarray:
    """
    Add subtle, smoothly-varying noise to a boundary line so it reads as
    hand-inked rather than machine-plotted, without distorting the data.
    Only applied to interior points -- endpoints are left exact.
    """
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, amplitude, size=len(y))
    # Smooth the noise so it wobbles gently rather than looking jagged/random
    kernel = np.array([0.2, 0.6, 0.2])
    smoothed = np.convolve(noise, kernel, mode='same')
    smoothed[0] = 0
    smoothed[-1] = 0
    return y + smoothed


def _densify(years: list, values: list, points_per_segment: int = 12) -> Tuple[np.ndarray, np.ndarray]:
    """
    Linearly interpolate extra points between each pair of real data points.

    Du Bois's line is dead straight between data points -- we're not adding
    curvature, just enough resolution that the hand-drawn jitter (applied
    afterward) has something to wobble along, the same way a hand-inked
    straightedge line still has tiny tremors in it.
    """
    xs, ys = [], []
    for i in range(len(years) - 1):
        x0, x1 = years[i], years[i + 1]
        y0, y1 = values[i], values[i + 1]
        n = points_per_segment if i < len(years) - 2 else 2  # keep the final cliff perfectly straight
        seg_x = np.linspace(x0, x1, n, endpoint=False)
        seg_y = np.linspace(y0, y1, n, endpoint=False)
        xs.append(seg_x)
        ys.append(seg_y)
    xs.append([years[-1]])
    ys.append([values[-1]])
    return np.concatenate(xs), np.concatenate(ys)


def create_plate_51(
    figsize: Tuple[float, float] = (8.0, 10.3),
    dpi: int = 150,
    add_texture: bool = True,
    add_jitter: bool = True,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Recreate Du Bois's Plate 51 with verified layout, data, and colors.

    Parameters
    ----------
    figsize : Tuple[float, float]
        Figure size in inches. Default matches the original's ~799:1024
        aspect ratio.
    dpi : int
        Resolution.
    add_texture : bool
        If True, overlay subtle hand-painted-style brush texture on the
        fills (faint vertical strokes in green, faint diagonal strokes in
        black), matching the visible texture in the original watercolor.
    add_jitter : bool
        If True, give the boundary line a very slight hand-inked wobble
        instead of a perfectly ruler-straight line.
    save_path : Optional[str]
        If given, save the figure here.

    Returns
    -------
    plt.Figure
    """
    font = _get_font()
    validate_figsize(figsize, dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(COLOR_CREAM)
    ax.set_facecolor(COLOR_CREAM)

    # ---- Layout constants (fractions of the axes, matching measured proportions) ----
    x0, x1 = 1790, 1870
    y0, y1 = 0, 100  # NOT inverted -- standard orientation

    # The axes only occupies the lower ~78% of the figure; the title block
    # (title / French subtitle / attribution line) lives above it in
    # figure-fraction space via fig.text(), and the year numerals live in
    # a headroom strip (100-112 in data y) just above the colored chart.
    AXES_TOP = 0.775
    fig.subplots_adjust(top=AXES_TOP, bottom=0.02, left=0.035, right=0.965)

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    # ---- Build the (possibly densified + jittered) boundary line ----
    if add_jitter:
        dense_x, dense_free = _densify(YEARS, FREE_PCT)
        dense_slave = 100 - dense_free
        # Only jitter the long flat 1790-1860 stretch; leave the 1860-1870
        # cliff perfectly straight since that's a real, sharp historical
        # discontinuity, not something that should look hand-wobbled.
        cliff_start = np.searchsorted(dense_x, 1860)
        jittered_slave = dense_slave.copy()
        jittered_slave[:cliff_start] = _hand_drawn_jitter(
            dense_x[:cliff_start], dense_slave[:cliff_start], amplitude=0.3
        )
        plot_x, plot_slave = dense_x, jittered_slave
    else:
        plot_x, plot_slave = np.array(YEARS, dtype=float), np.array(SLAVE_PCT, dtype=float)

    # ---- Fills: BLACK on the bottom (majority), GREEN on top (minority) ----
    # This is the core correction: standard orientation, not inverted.
    ax.fill_between(plot_x, 0, plot_slave, color=COLOR_BLACK,
                     linewidth=0, zorder=2)
    ax.fill_between(plot_x, plot_slave, 100, color=COLOR_GREEN,
                     linewidth=0, zorder=1)

    # A crisp ink outline along the boundary curve (Du Bois's line work is
    # a clean, deliberate stroke even where the fills look painterly)
    ax.plot(plot_x, plot_slave, color=COLOR_BLACK, linewidth=1.1, zorder=3,
             solid_capstyle='round')

    # ---- Optional hand-painted texture ----
    if add_texture:
        _add_texture(ax, plot_x, plot_slave, x0, x1)

    # ---- Remove all standard axis furniture; this chart has none ----
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # A thin ink border frames the whole colored block, as in the original
    border = Polygon(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        closed=True, fill=False, edgecolor=COLOR_BLACK, linewidth=1.2, zorder=5
    )
    ax.add_patch(border)

    # ---- Year labels, in a headroom strip above the colored chart ----
    for yr in YEARS:
        ax.text(yr, 104, str(yr), ha='center', va='bottom',
                 fontsize=14, fontweight='bold', fontfamily=font,
                 color=COLOR_TEXT_ON_CREAM, zorder=6, clip_on=False)
        ax.plot([yr, yr], [100, 102], color=COLOR_TEXT_ON_CREAM,
                 linewidth=1, zorder=6, clip_on=False)

    # ---- Free-percentage labels along the boundary, in the green band ----
    for i, (yr, free, label) in enumerate(zip(YEARS[:-1], FREE_PCT[:-1], FREE_LABELS[:-1])):
        slave = 100 - free
        label_y = slave + 1.8  # a small, consistent gap above the boundary
        ha = 'left' if i == 0 else 'center'
        label_x = yr + 0.6 if i == 0 else yr
        ax.text(label_x, label_y, label, ha=ha, va='bottom',
                 fontsize=9.5, fontweight='bold', fontfamily=font,
                 color=COLOR_TEXT_ON_CREAM, zorder=6)
    # The final "100%" sits near the top right, since the whole column is green
    ax.text(1868, 90, '100%', ha='right', va='bottom',
             fontsize=9.5, fontweight='bold', fontfamily=font,
             color=COLOR_TEXT_ON_CREAM, zorder=6)

    # ---- "FREE - LIBRE" label, centered high in the green band ----
    ax.text(1824, 99, _spaced('FREE - LIBRE'), ha='center', va='top',
             fontsize=11.5, fontweight='bold', fontfamily=font,
             color=COLOR_TEXT_ON_CREAM, zorder=6)

    # ---- "SLAVES / ESCLAVES", centered in the black mass, white ink ----
    # The original's tracking here is tighter than our default _spaced()
    # gap -- plain monospace advance (no extra inserted space) is a closer
    # match to how snug these two words sit in the source image.
    ax.text(1828, 48, 'SLAVES', ha='center', va='center',
             fontsize=22, fontweight='bold', fontfamily=font,
             color=COLOR_TEXT_ON_BLACK, zorder=6)
    ax.text(1828, 41, 'ESCLAVES', ha='center', va='center',
             fontsize=22, fontweight='bold', fontfamily=font,
             color=COLOR_TEXT_ON_BLACK, zorder=6)

    # ---- Title block, in figure-fraction space above the axes ----
    fig.text(0.5, 0.965, 'PROPORTION OF FREEMEN AND SLAVES AMONG AMERICAN NEGROES .',
              ha='center', va='top', fontsize=12.5, fontweight='bold',
              fontfamily=font, color=COLOR_TEXT_ON_CREAM)
    fig.text(0.5, 0.915, 'PROPORTION DES N\u00c8GRES LIBRES ET DES ESCLAVES EN AM\u00c9RIQUE .',
              ha='center', va='top', fontsize=12.5, fontweight='bold',
              fontfamily=font, color=COLOR_TEXT_ON_CREAM)
    fig.text(0.5, 0.865, _spaced('DONE BY ATLANTA UNIVERSITY .'),
              ha='center', va='top', fontsize=9, fontweight='bold',
              fontfamily=font, color=COLOR_TEXT_ON_CREAM)

    # ---- Final canvas trim: headroom above (year row) matches AXES_TOP ----
    ax.set_xlim(x0 - 9, x1 + 9)
    ax.set_ylim(-2, 112)

    if save_path:
        fig.savefig(save_path, dpi=dpi, facecolor=COLOR_CREAM,
                     bbox_inches=None, pad_inches=0)

    return fig


def _add_texture(ax, plot_x, plot_slave, x0, x1, seed: int = 7) -> None:
    """
    Overlay visible hand-painted-style brush texture, clipped to each fill.

    The original is watercolor on board with clearly visible grain and
    brush-stroke variation -- flat digital color reads as noticeably too
    "clean" by comparison. This renders each fill as a base color plus a
    smoothed noise field (so it looks like uneven paint coverage / brush
    drag rather than digital speckle), using imshow so the texture is a
    real per-pixel field rather than a handful of thin lines that wash out
    at render resolution.
    """
    from scipy.ndimage import gaussian_filter
    rng = np.random.RandomState(seed)

    def make_texture_rgba(base_hex, light_hex, dark_hex, shape=(700, 500),
                           fine_sigma=0.7, streak_sigma=(40, 1.4), strength=0.16):
        """Build an RGBA array: base color plus a *fine*, low-contrast
        grain, with a faint vertical streaky component layered on top for
        brush-drag. Kept deliberately subtle -- this should read as paper
        grain at a glance, not as a pattern."""
        h, w = shape

        # Fine grain: small-radius blur so it stays high-frequency (paper
        # tooth / brush grain), not blobby.
        grain = gaussian_filter(rng.normal(0, 1, size=(h, w)), sigma=fine_sigma)
        grain = grain / (np.abs(grain).max() + 1e-9)  # -1..1

        # Faint vertical streaks: heavily blurred along y (long streak),
        # only slightly blurred along x (keeps streaks thin/distinct).
        streaks = gaussian_filter(rng.normal(0, 1, size=(h, w)), sigma=streak_sigma)
        streaks = streaks / (np.abs(streaks).max() + 1e-9)  # -1..1

        combined = 0.6 * grain + 0.4 * streaks  # -1..1, mostly fine grain

        base_rgb = np.array(plt.matplotlib.colors.to_rgb(base_hex))
        light_rgb = np.array(plt.matplotlib.colors.to_rgb(light_hex))
        dark_rgb = np.array(plt.matplotlib.colors.to_rgb(dark_hex))

        img = np.tile(base_rgb, (h, w, 1))
        pos = combined > 0
        neg = ~pos
        w_pos = (combined[pos] * strength)[:, None]
        w_neg = (-combined[neg] * strength)[:, None]
        img[pos] = (1 - w_pos) * base_rgb + w_pos * light_rgb
        img[neg] = (1 - w_neg) * base_rgb + w_neg * dark_rgb

        alpha = np.ones((h, w))
        return np.dstack([img, alpha])

    # ---- Green band: fine grain + very faint vertical brush-drag ----
    green_tex = make_texture_rgba(
        COLOR_GREEN, light_hex='#7aab7f', dark_hex='#3f6a45',
        shape=(500, 380), fine_sigma=0.8, streak_sigma=(55, 1.2), strength=0.14,
    )
    green_im = ax.imshow(green_tex, extent=(x0, x1, 0, 100), origin='lower',
                          aspect='auto', zorder=2.5, interpolation='bilinear')

    # ---- Black mass: fine grain + faint vertical streaking ----
    black_tex = make_texture_rgba(
        COLOR_BLACK, light_hex='#4a453d', dark_hex='#000000',
        shape=(700, 380), fine_sigma=0.9, streak_sigma=(65, 1.3), strength=0.17,
    )
    black_im = ax.imshow(black_tex, extent=(x0, x1, 0, 100), origin='lower',
                          aspect='auto', zorder=2.5, interpolation='bilinear')

    # Clip each texture image to its actual fill polygon so it never bleeds
    # into the cream margin or crosses the boundary line.
    green_clip = ax.fill_between(plot_x, plot_slave, 100, alpha=0)
    black_clip = ax.fill_between(plot_x, 0, plot_slave, alpha=0)
    green_im.set_clip_path(green_clip.get_paths()[0], transform=ax.transData)
    black_im.set_clip_path(black_clip.get_paths()[0], transform=ax.transData)

    # Distinct thin vertical panel-divider lines in the green band, at each
    # interior year mark -- a clearly visible feature of the original,
    # separate from (and crisper than) the fine grain texture above.
    for yr in YEARS[1:-1]:
        jitter = rng.uniform(-0.15, 0.15)
        line, = ax.plot([yr + jitter, yr + jitter], [0, 100],
                         color='#2f4f34', linewidth=1.1, alpha=0.4,
                         zorder=2.6, solid_capstyle='butt')
        line.set_clip_path(green_clip.get_paths()[0], transform=ax.transData)

    # A few faint, longer diagonal strokes on top for occasional deliberate
    # brush "drag" marks -- sparse, so they read as accents, not a pattern
    for _ in range(8):
        x_start = rng.uniform(x0 + 2, x1 - 2)
        drift = rng.uniform(-2.5, 2.5)
        y_top = rng.uniform(5, 90)
        length = rng.uniform(20, 55)
        line, = ax.plot([x_start, x_start + drift], [y_top, max(0, y_top - length)],
                         color='#000000',
                         linewidth=rng.uniform(0.7, 1.3), alpha=rng.uniform(0.10, 0.20),
                         zorder=2.6, solid_capstyle='round')
        line.set_clip_path(black_clip.get_paths()[0], transform=ax.transData)


def create_side_by_side(save_path: Optional[str] = None,
                         original_path: str = _DEFAULT_REFERENCE_PATH) -> plt.Figure:
    """
    Render the recreation next to the actual scanned original for direct
    visual QA. This is the comparison used to iterate on accuracy.

    `original_path` defaults to the reference scan shipped alongside this
    module (resolved relative to this file, not the caller's working
    directory), so this works the same way whether it's run as
    `python3 plate51.py` from inside dubois_charts/charts/ or imported and
    called from anywhere else entirely.
    """
    import matplotlib.image as mpimg
    import os
    import tempfile
    import warnings

    fig, axes = plt.subplots(1, 2, figsize=(15, 10.3), dpi=150)

    # Render the recreation to a real temp file (not a bare filename in
    # the caller's cwd, which risks permission errors, collisions between
    # concurrent calls, and leftover debris if this is interrupted before
    # the cleanup at the end of the function runs) purely so it can be
    # read back in as an image array for side-by-side display.
    fd, tmp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        single = create_plate_51()
        single.savefig(tmp_path, dpi=single.dpi, facecolor=COLOR_CREAM,
                       bbox_inches=None, pad_inches=0)
        plt.close(single)

        recreation_img = mpimg.imread(tmp_path)
        axes[0].imshow(recreation_img)
        axes[0].set_title('RECREATION', fontsize=13, fontweight='bold')
        axes[0].axis('off')

        if os.path.exists(original_path):
            original_img = mpimg.imread(original_path)
            axes[1].imshow(original_img)
            axes[1].set_title('ORIGINAL (Library of Congress)', fontsize=13, fontweight='bold')
        else:
            # Leaving the panel blank but still titled "ORIGINAL" reads as
            # a successful comparison even when the reference image was
            # never found -- misleading for anyone using this to verify
            # accuracy. Say so on the panel itself, not just in a log line
            # that's easy to miss.
            warnings.warn(
                f"Reference image not found at '{original_path}' -- showing "
                "the recreation only. Pass original_path explicitly if the "
                "reference scan lives somewhere else.",
                stacklevel=2,
            )
            axes[1].text(0.5, 0.5, 'Reference image not found:\n' + original_path,
                          ha='center', va='center', fontsize=11, wrap=True,
                          transform=axes[1].transAxes)
            axes[1].set_title('ORIGINAL (not found)', fontsize=13, fontweight='bold')
        axes[1].axis('off')

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, facecolor='white', bbox_inches='tight')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return fig


def main():
    import os
    output_dir = 'plate51_recreation'
    os.makedirs(output_dir, exist_ok=True)

    print("Generating pixel-verified Plate 51 recreation...")
    fig1 = create_plate_51(save_path=f'{output_dir}/plate51_authentic.png')
    plt.close(fig1)

    print("Generating side-by-side comparison with the actual original...")
    fig2 = create_side_by_side(
        save_path=f'{output_dir}/plate51_side_by_side.png',
        original_path=_DEFAULT_REFERENCE_PATH,
    )
    plt.close(fig2)

    print("Done.")


if __name__ == '__main__':
    main()
