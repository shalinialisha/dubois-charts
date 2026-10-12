"""
Colour palettes after W.E.B. Du Bois's data portraits for the 1900 Paris
Exposition: hand-painted plates whose bold, saturated colours -- crimson,
gold and black above all, with green, blue, purple and brown -- are few
and used sparingly.

Only DUBOIS_VERIFIED_PLATE51 is measured from a plate (a scan of Plate
51). The others are colours in the plates' spirit, not measurements:
see the note at DUBOIS_PRIMARY below.

References:
-----------
- W.E.B. Du Bois's Data Portraits: Visualizing Black America (2018)
- Library of Congress: African American Photographs Assembled for 1900 Paris Exposition
- #DuBoisChallenge style guides (2021, 2024)
"""

import colorsys
import warnings
from functools import lru_cache
from typing import Dict, List, Tuple

import matplotlib.colors as mcolors
import numpy as np

# Core Du Bois Colors
#
# IMPORTANT HONESTY NOTE: the DUBOIS_PRIMARY / DUBOIS_EXTENDED palettes
# below are stylistic approximations, not colors measured from an actual
# plate. They were originally written from general memory of "Du Bois
# looks bold/saturated/red-gold-black" rather than from pixel sampling,
# and that distinction matters -- e.g. the real green used in Plate 51 is
# a muted olive `#57845c`, not the vivid `#00A550` guessed below.
#
# Use DUBOIS_VERIFIED (further down) when you want colors that are
# actually traceable to a specific plate and measurement. Use
# DUBOIS_PRIMARY / DUBOIS_EXTENDED only as a general-purpose decorative
# palette "in the spirit of" Du Bois, not as a historical claim.

# Primary palette - general "in the spirit of Du Bois" decorative colors.
# NOT pixel-verified -- see DUBOIS_VERIFIED for measured colors.
DUBOIS_PRIMARY = {
    'crimson': '#DC143C',      # Vivid red/crimson - most dominant color
    'gold': '#D4AF37',         # Rich gold/yellow
    'black': '#000000',        # True black
    'tan': '#D2B48C',          # Light tan/beige
}

# Extended palette - additional decorative colors. NOT pixel-verified.
DUBOIS_EXTENDED = {
    'crimson': '#DC143C',
    'pink': '#FFC1CC',         # Soft pink
    'rose': '#E75480',         # Medium rose pink
    'gold': '#D4AF37',
    'yellow': '#FFD700',       # Brighter yellow
    'green': '#00A550',        # Vibrant green
    'navy': '#000080',         # Dark navy blue
    'blue': '#4682B4',         # Steel blue
    'purple': '#663399',       # Deep purple
    'brown': '#654321',        # Rich brown
    'tan': '#D2B48C',
    'cream': '#F5DEB3',        # Wheat/cream
    'black': '#000000',
    'gray': '#808080',         # Medium gray
}

# ---------------------------------------------------------------------------
# VERIFIED colors: pixel-sampled from actual scanned plates.
#
# Each entry here was produced by downloading the real Library of Congress
# scan, averaging pixel values over clean regions of each fill with
# PIL/numpy, and cross-checking the result against the plate's known data.
# See dubois_charts/charts/plate51.py and dubois_charts/charts/PLATE51_README.md for the
# full methodology on Plate 51. As more plates get this treatment, add
# their measured colors here rather than guessing.
# ---------------------------------------------------------------------------
DUBOIS_VERIFIED_PLATE51 = {
    'green': '#57845c',        # "FREE - LIBRE" fill, Plate 51
    'black': '#1d1d1d',        # "SLAVES / ESCLAVES" fill, Plate 51
    'cream': '#d9d2c6',        # paper background, Plate 51
}

# Sequential palettes, light to dark, for showing progression or intensity
# (the maps' colour classes).
#
# Each runs from a near-white tint, through the colour itself, to a dark
# shade, and its steps are evenly spaced in perceived lightness -- the one
# difference every reader sees, colour-blind or not -- so neighbouring
# classes on a map are equally easy to tell apart.
#
# The first versions were hand-picked lists whose steps weren't even, and
# get_sequential() took evenly spaced entries of them: two of a map's seven
# gold classes were 4.2 apart in CIEDE2000 (hard to tell apart for anyone),
# and two of the seven crimson ones 3.8 apart as a tritanope sees them, the
# list having swung from salmon to rose at much the same lightness. Each is
# now drawn from a few anchor colours (_SEQUENTIAL_ANCHORS) -- with a darker
# bronze for gold, whose old darkest shade left too little range for seven
# classes -- and _build_sequential() re-derives these lists from them.
_SEQUENTIAL_ANCHORS = {
    'crimson': ['#FFF0F0', '#DC143C', '#800020'],
    'gold': ['#FFF9E6', '#FFD700', '#D4AF37', '#5C4306'],
    'green': ['#E6F5E6', '#00A550', '#004020'],
}
CRIMSON_SEQUENTIAL = ['#FFF0F0', '#FFC0BD', '#F99593', '#F06C6E', '#E54350', '#D31239', '#AB082D', '#800020']
GOLD_SEQUENTIAL = ['#FFF9E6', '#FAD30F', '#D8B334', '#BB982D', '#A28222', '#8C6E19', '#755910', '#5C4306']
GREEN_SEQUENTIAL = ['#E6F5E6', '#A5D9AE', '#68BF7E', '#1BA855', '#008E45', '#00763A', '#005C2E', '#004020']

# Categorical palettes for discrete categories
# These are designed to be maximally distinguishable

# Classic Du Bois palette (3-4 colors)
DUBOIS_CLASSIC_3 = ['#DC143C', '#D4AF37', '#000000']
DUBOIS_CLASSIC_4 = ['#DC143C', '#D4AF37', '#00A550', '#000000']

# Extended categorical palette (up to 8 colors)
DUBOIS_CATEGORICAL_8 = [
    '#DC143C',  # Crimson
    '#D4AF37',  # Gold
    '#00A550',  # Green
    '#4682B4',  # Blue
    '#E75480',  # Rose
    '#663399',  # Purple
    '#654321',  # Brown
    '#000000',  # Black
]

# ---------------------------------------------------------------------------
# More than eight categories
#
# get_categorical() used to start the eight colours above over again for a
# ninth category, so category 9 came out in the same crimson as category 1
# and a bar chart of ten countries gave two pairs of them the same colour.
#
# DUBOIS_CATEGORICAL_20 keeps those eight exactly as they were and adds
# twelve more, chosen so that no two of the twenty -- and none of them
# against the cream paper -- look more alike than the closest pair of the
# original eight (crimson and rose). "Look alike" is measured with
# CIEDE2000, the CIE's standard formula for how different two colours
# appear: about 1 is a just-noticeable difference, crimson and rose are
# 15.4 apart, and every pair here is at least 15.
#
# The additions were picked most-distinct first: first the package's other
# Du Bois colours that clear that bar (pink, gray, navy -- tan, the brighter
# yellow and the Plate 51 olive don't: they're too close to the paper, the
# gold and the green), then lighter and darker tones of the palette, the
# lighter ones muted as they go so nothing turns neon.
#
# _build_categorical_20() re-derives this list, and tests/test_colors.py
# checks that the two agree and that every pair really is 15 or more apart.
# ---------------------------------------------------------------------------
DUBOIS_CATEGORICAL_20 = DUBOIS_CATEGORICAL_8 + [
    '#FFC1CC',  # Pink            (DUBOIS_EXTENDED)
    '#808080',  # Gray            (DUBOIS_EXTENDED)
    '#000080',  # Navy            (DUBOIS_EXTENDED)
    '#005228',  # Dark green      (darkened green)
    '#6B0F2B',  # Wine            (darkened rose)
    '#997AB8',  # Lavender        (lightened purple)
    '#95C6AD',  # Sage            (lightened green)
    '#BDBDDB',  # Pale periwinkle (lightened navy)
    '#474747',  # Charcoal        (lightened black)
    '#866D1D',  # Ochre           (darkened gold)
    '#2E5576',  # Slate blue      (darkened blue)
    '#A38566',  # Fawn            (lightened brown)
]

_PAPER = '#ded7c9'          # the cream every chart is drawn on (charts._common.COLOR_CREAM)
_CLEARLY_DISTINCT = 15.0    # CIEDE2000; the closest pair of the original eight is 15.4
_DARKEST_TONE = 22.0        # CIE L*; darker tones are hard to tell from black

_SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                         [0.2126729, 0.7151522, 0.0721750],
                         [0.0193339, 0.1191920, 0.9503041]])
_D65_WHITE = np.array([0.95047, 1.00000, 1.08883])


def _to_lab(colors) -> np.ndarray:
    """CIE L*a*b* (D65) of each colour (hex, or anything matplotlib accepts), as an (N, 3) array."""
    rgb = np.array([mcolors.to_rgb(c) for c in colors], dtype=float)
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _SRGB_TO_XYZ.T / _D65_WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.column_stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])])


def _ciede2000(lab1, lab2) -> np.ndarray:
    """
    CIEDE2000 colour difference between L*a*b* colours, row by row; either
    argument may be a single colour.

    Follows Sharma, Wu & Dalal (2005), "The CIEDE2000 color-difference
    formula: implementation notes, supplementary test data, and
    mathematical observations"; tests/test_colors.py checks it against
    their published test pairs.
    """
    L1, a1, b1 = np.atleast_2d(np.asarray(lab1, dtype=float)).T
    L2, a2, b2 = np.atleast_2d(np.asarray(lab2, dtype=float)).T

    c_mean7 = ((np.hypot(a1, b1) + np.hypot(a2, b2)) / 2) ** 7
    g = 0.5 * (1 - np.sqrt(c_mean7 / (c_mean7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.where(c1p == 0, 0.0, np.degrees(np.arctan2(b1, a1p)) % 360)
    h2p = np.where(c2p == 0, 0.0, np.degrees(np.arctan2(b2, a2p)) % 360)
    achromatic = (c1p * c2p) == 0

    d_lp, d_cp = L2 - L1, c2p - c1p
    d_hp = h2p - h1p
    d_hp = np.where(d_hp > 180, d_hp - 360, np.where(d_hp < -180, d_hp + 360, d_hp))
    d_hp = np.where(achromatic, 0.0, d_hp)
    d_big_hp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(d_hp / 2))

    lp_mean, cp_mean = (L1 + L2) / 2, (c1p + c2p) / 2
    h_sum = h1p + h2p
    hp_mean = np.where(np.abs(h1p - h2p) <= 180, h_sum / 2,
                       np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2))
    hp_mean = np.where(achromatic, h_sum, hp_mean)

    t = (1 - 0.17 * np.cos(np.radians(hp_mean - 30)) + 0.24 * np.cos(np.radians(2 * hp_mean))
         + 0.32 * np.cos(np.radians(3 * hp_mean + 6)) - 0.20 * np.cos(np.radians(4 * hp_mean - 63)))
    d_theta = 30 * np.exp(-(((hp_mean - 275) / 25) ** 2))
    cp_mean7 = cp_mean ** 7
    r_c = 2 * np.sqrt(cp_mean7 / (cp_mean7 + 25.0 ** 7))
    s_l = 1 + 0.015 * (lp_mean - 50) ** 2 / np.sqrt(20 + (lp_mean - 50) ** 2)
    s_c = 1 + 0.045 * cp_mean
    s_h = 1 + 0.015 * cp_mean * t
    r_t = -np.sin(np.radians(2 * d_theta)) * r_c
    return np.sqrt((d_lp / s_l) ** 2 + (d_cp / s_c) ** 2 + (d_big_hp / s_h) ** 2
                   + r_t * (d_cp / s_c) * (d_big_hp / s_h))


def _tones(color) -> List[str]:
    """
    Lighter and darker versions of `color`: the same hue at HLS lightness
    0.16, 0.20, ... 0.84. Versions lighter than the colour itself lose
    saturation as they go, so a lightened crimson becomes a dusty rose
    rather than a neon pink.
    """
    hue, lightness, saturation = colorsys.rgb_to_hls(*mcolors.to_rgb(color))
    tones = []
    for step in range(18):
        tone_lightness = 0.16 + 0.04 * step
        lightened_by = max(0.0, tone_lightness - lightness)
        tone_saturation = saturation * max(0.3, 1 - 2.0 * lightened_by)
        tones.append(mcolors.to_hex(colorsys.hls_to_rgb(hue, tone_lightness, tone_saturation)))
    return tones


def _tone_candidates(colors) -> List[str]:
    """Tones of every colour in `colors`, minus any dark enough to pass for black."""
    tones = [t for c in colors for t in _tones(c)]
    lightness = _to_lab(tones)[:, 0]
    return [t for t, L in zip(tones, lightness) if L >= _DARKEST_TONE]


def _most_distinct_first(chosen, candidates, stop_below=None) -> List[str]:
    """
    Order `candidates` most distinct first: repeatedly take the one whose
    closest match among the colours chosen so far (and the paper) is
    farthest away. Stops when the best one left would be closer than
    `stop_below` to something already chosen, or when none are left.
    """
    chosen = [c.lower() for c in chosen]
    pool = [c for c in dict.fromkeys(c.lower() for c in candidates) if c not in chosen]
    if not pool:
        return []
    pool_lab = _to_lab(pool)
    closest = np.full(len(pool), np.inf)
    for ref in _to_lab(chosen + [_PAPER]):
        closest = np.minimum(closest, _ciede2000(ref, pool_lab))
    picked = []
    available = np.ones(len(pool), dtype=bool)
    while available.any():
        best = int(np.argmax(np.where(available, closest, -np.inf)))
        if stop_below is not None and closest[best] < stop_below:
            break
        picked.append(pool[best])
        available[best] = False
        closest = np.minimum(closest, _ciede2000(pool_lab[best], pool_lab))
    return picked


def _build_categorical_20() -> List[str]:
    """Re-derive DUBOIS_CATEGORICAL_20 (see the comment above it), in lowercase hex."""
    palette = [c.lower() for c in DUBOIS_CATEGORICAL_8]
    named = [DUBOIS_EXTENDED[k] for k in ('pink', 'gray', 'navy', 'tan', 'yellow')]
    named.append(DUBOIS_VERIFIED_PLATE51['green'])
    palette += _most_distinct_first(palette, named, stop_below=_CLEARLY_DISTINCT)
    palette += _most_distinct_first(palette, _tone_candidates(palette), stop_below=_CLEARLY_DISTINCT)
    return palette


@lru_cache(maxsize=1)
def _colors_after_20() -> Tuple[str, ...]:
    """Every remaining tone of the twenty, most distinct first, with no minimum difference."""
    remaining = _most_distinct_first(DUBOIS_CATEGORICAL_20, _tone_candidates(DUBOIS_CATEGORICAL_20))
    return tuple(c.upper() for c in remaining)


def _lab_to_hex(lab) -> str:
    """The sRGB hex colour nearest a CIE L*a*b* (D65) colour."""
    L, a, b = (float(v) for v in lab)
    fy = (L + 16) / 116
    f = np.array([fy + a / 500, fy, fy - b / 200])
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * _D65_WHITE
    linear = np.linalg.solve(_SRGB_TO_XYZ, xyz)
    rgb = np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * np.abs(linear) ** (1 / 2.4) - 0.055)
    return mcolors.to_hex(np.clip(rgb, 0, 1))


# ---------------------------------------------------------------------------
# Colour-blind readers
#
# About one man in twelve and one woman in two hundred see colour
# differently: most often red and green look alike (deuteranopia and
# protanopia), more rarely blue and yellow (tritanopia). The classic
# palette fails them from four categories on: as a deuteranope sees them,
# its crimson and green are 6.4 apart in CIEDE2000 -- barely different --
# and as a protanope sees them its gold and green are 10.0 apart.
#
# simulate_colorblindness() shows colours as each of those readers sees
# them (Machado, Oliveira & Fernandes, 2009, at full severity -- the
# simulation most colour-vision tools use). DUBOIS_COLORBLIND_8 keeps the
# classic crimson, gold and black and adds the five Du Bois colours, or
# tones of them, that stay most distinct from those and from each other
# as seen with normal vision and with each of the three conditions,
# preferring the palette's own colours (steel blue, gray) to a tone of
# one when they're nearly as distinct: every pair is at least 16 apart
# for every reader. No ninth colour keeps that up -- past eight the
# closest pair falls to 12 -- so past eight a warning suggests labelling
# the categories or grouping the smallest.
#
# _build_colorblind_8() re-derives it, and tests/test_colors.py checks.
# ---------------------------------------------------------------------------
_MACHADO_2009 = {
    'protanopia': np.array([[0.152286, 1.052583, -0.204868],
                            [0.114503, 0.786281, 0.099216],
                            [-0.003882, -0.048116, 1.051998]]),
    'deuteranopia': np.array([[0.367322, 0.860646, -0.227968],
                              [0.280085, 0.672501, 0.047413],
                              [-0.011820, 0.042940, 0.968881]]),
    'tritanopia': np.array([[1.255528, -0.076749, -0.178779],
                            [-0.078411, 0.930809, 0.147602],
                            [0.004733, 0.691367, 0.303900]]),
}
COLORBLINDNESS = tuple(_MACHADO_2009)


def simulate_colorblindness(colors, kind: str = 'deuteranopia') -> List[str]:
    """
    How `colors` look to a reader with colour-blindness of the given
    `kind`: 'protanopia', 'deuteranopia' (red and green alike; together
    about 8% of men) or 'tritanopia' (blue and yellow alike; rare).

    Parameters
    ----------
    colors : list of colours (hex strings, or anything matplotlib accepts)
    kind : str

    Returns
    -------
    List[str]
        The colours as hex strings, as that reader would see them.

    Examples
    --------
    >>> simulate_colorblindness(['#DC143C', '#00A550'], 'deuteranopia')   # crimson, green
    ['#8b7e35', '#968b56']
    """
    if kind not in _MACHADO_2009:
        raise ValueError(f"`kind` must be one of {', '.join(map(repr, COLORBLINDNESS))}; got {kind!r}.")
    rgb = np.array([mcolors.to_rgb(c) for c in colors], dtype=float)
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    seen = np.clip(linear @ _MACHADO_2009[kind].T, 0, 1)
    srgb = np.where(seen <= 0.0031308, 12.92 * seen, 1.055 * seen ** (1 / 2.4) - 0.055)
    return [mcolors.to_hex(c) for c in srgb]


def _views(colors) -> List[np.ndarray]:
    """L*a*b* of `colors` as seen with normal vision and with each kind of colour-blindness."""
    return [_to_lab(colors)] + [_to_lab(simulate_colorblindness(colors, k)) for k in COLORBLINDNESS]


def closest_pair_for_every_reader(colors) -> float:
    """
    The smallest CIEDE2000 difference between any two of `colors` (and
    between any of them and the cream paper the charts are drawn on), as
    seen with normal vision or any kind of colour-blindness. About 1 is
    just noticeable; 15 or more is clearly different.
    """
    colors = list(colors) + [_PAPER]
    closest = np.inf
    for lab in _views(colors):
        for i in range(len(colors) - 1):
            closest = min(closest, float(_ciede2000(lab[i], lab[i + 1:]).min()))
    return closest


def _most_distinct_for_every_reader(chosen, named, tones, count, prefer_named=0.85) -> List[str]:
    """Add `count` colours to `chosen`, each time the one farthest from all
    chosen so far (and the paper) for the reader to whom it's closest --
    one of `named` when that's at least `prefer_named` as far as the best."""
    chosen = [c.lower() for c in chosen]
    named = [c.lower() for c in named]
    pool = [c for c in dict.fromkeys(named + [t.lower() for t in tones]) if c not in chosen]
    pool_views = _views(pool)
    closest = np.full(len(pool), np.inf)
    for view, ref in zip(pool_views, _views(chosen + [_PAPER])):
        for r in ref:
            closest = np.minimum(closest, _ciede2000(r, view))
    added = []
    available = np.ones(len(pool), dtype=bool)
    for _ in range(count):
        if not available.any():
            break
        score = np.where(available, closest, -np.inf)
        best = int(np.argmax(score))
        named_score = np.where(available & np.isin(pool, named), closest, -np.inf)
        if named_score.max() >= prefer_named * score[best]:
            best = int(np.argmax(named_score))
        added.append(pool[best])
        available[best] = False
        for view in pool_views:
            closest = np.minimum(closest, _ciede2000(view[best], view))
    return added


def _du_bois_colours() -> List[str]:
    return list(dict.fromkeys(c.lower() for c in
                              list(DUBOIS_EXTENDED.values()) + list(DUBOIS_VERIFIED_PLATE51.values())
                              + DUBOIS_CATEGORICAL_20))


def _build_colorblind_8() -> List[str]:
    """Re-derive DUBOIS_COLORBLIND_8 (see the comment above it), in lowercase hex."""
    start = [c.lower() for c in DUBOIS_CLASSIC_3]
    named = _du_bois_colours()
    return start + _most_distinct_for_every_reader(start, named, _tone_candidates(named), 5)


DUBOIS_COLORBLIND_8 = [
    '#DC143C',  # Crimson
    '#D4AF37',  # Gold
    '#000000',  # Black
    '#4682B4',  # Steel blue      (DUBOIS_EXTENDED)
    '#1E1EAE',  # Ultramarine     (a tone of navy)
    '#808080',  # Gray            (DUBOIS_EXTENDED)
    '#902747',  # Claret          (a tone of rose)
    '#97AFC4',  # Pale blue       (a tone of steel blue)
]


@lru_cache(maxsize=1)
def _colorblind_after_8() -> Tuple[str, ...]:
    """More colours for colour-blind readers past eight, most distinct first."""
    named = _du_bois_colours()
    more = _most_distinct_for_every_reader(DUBOIS_COLORBLIND_8, named, _tone_candidates(named), 40)
    return tuple(c.upper() for c in more)


_COLORBLIND_SAFE = [False]


def set_colorblind_safe(on: bool = True) -> None:
    """
    Make every chart's default colours ones colour-blind readers can tell
    apart: DUBOIS_COLORBLIND_8 instead of the classic palette (and, for
    get_diverging(), crimson to blue instead of crimson to green). Colours
    passed to a chart explicitly are left alone. `set_colorblind_safe(False)`
    goes back to the classic palette.

    Examples
    --------
    >>> import dubois_charts as dc
    >>> dc.set_colorblind_safe()
    >>> fig = dc.pie_chart({'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5})
    >>> dc.set_colorblind_safe(False)
    """
    _COLORBLIND_SAFE[0] = bool(on)


# Diverging palette (useful for showing deviation from center)
DUBOIS_DIVERGING = [
    '#DC143C',  # Crimson
    '#E75480',  # Rose
    '#FFC1CC',  # Pink
    '#F5DEB3',  # Cream (neutral)
    '#99D699',  # Light green
    '#66C266',  # Medium green
    '#00A550',  # Du Bois green
]

# The same, for colour-blind readers: crimson to blue rather than crimson
# to green, which deuteranopes and protanopes see as two shades of the
# same brownish yellow. Each colour matches the lightness of its mirror
# on the other side, and every pair of mirrors -- and of neighbours -- is
# at least 12 apart in CIEDE2000 for every reader.
DUBOIS_DIVERGING_COLORBLIND = [
    '#DC143C',  # Crimson
    '#E05A7A',  # Rose
    '#F2A7B6',  # Pink
    '#F5DEB3',  # Cream (neutral)
    '#A3C3E3',  # Pale blue
    '#5A8CC4',  # Blue
    '#1F4E8F',  # Dark blue
]

# Pan-African flag colors (used in 2024 Du Bois Challenge)
PAN_AFRICAN = {
    'red': '#DC143C',
    'black': '#000000',
    'green': '#00A550',
}


def get_palette(name: str = 'primary') -> Dict[str, str]:
    """
    Get a Du Bois color palette by name.
    
    Parameters
    ----------
    name : str
        Name of the palette. Options:
        - 'primary': General decorative Du Bois-style colors (default).
          NOT pixel-verified -- see 'verified_plate51'.
        - 'extended': Full extended decorative palette. NOT pixel-verified.
        - 'pan_african': Pan-African flag colors
        - 'verified_plate51': Colors actually pixel-sampled from the
          Plate 51 scan (green/black/cream). Use this when accuracy to a
          specific original plate matters more than decorative variety.
    
    Returns
    -------
    Dict[str, str]
        Dictionary mapping color names to hex codes
    
    Examples
    --------
    >>> get_palette('primary')['crimson']
    '#DC143C'
    >>> get_palette('verified_plate51')['green']   # the green measured from Plate 51
    '#57845c'
    """
    palettes = {
        'primary': DUBOIS_PRIMARY,
        'extended': DUBOIS_EXTENDED,
        'pan_african': PAN_AFRICAN,
        'verified_plate51': DUBOIS_VERIFIED_PLATE51,
    }
    
    if name not in palettes:
        raise ValueError(f"Unknown palette '{name}'. Choose from: {list(palettes.keys())}")

    return dict(palettes[name])         # a copy: changing it doesn't change the palette


def get_sequential(color: str = 'crimson', n: int = None) -> List[str]:
    """
    Get a sequential color palette.
    
    Parameters
    ----------
    color : str
        Base color for the sequence. Options: 'crimson', 'gold', 'green'
    n : int, optional
        Number of colors to return. If None, returns full palette.
    
    Returns
    -------
    List[str]
        List of hex color codes from light to dark
    
    Examples
    --------
    >>> colors = get_sequential('crimson', n=5)
    >>> len(colors)
    5
    """
    sequences = {
        'crimson': CRIMSON_SEQUENTIAL,
        'gold': GOLD_SEQUENTIAL,
        'green': GREEN_SEQUENTIAL,
    }
    
    if color not in sequences:
        raise ValueError(f"Unknown sequence '{color}'. Choose from: {list(sequences.keys())}")
    
    seq = sequences[color]
    
    if n is None:
        return list(seq)
    elif n <= 0:
        raise ValueError("n must be positive")
    elif n == 1:
        # One colour: the middle of the range, neither the near-white
        # start nor the darkest end. (The spacing formula below divides
        # by n - 1, so this used to be a ZeroDivisionError.)
        return [seq[len(seq) // 2]]
    return _evenly_lighter(_SEQUENTIAL_ANCHORS[color], n)


def _lightness_weight(L):
    """CIEDE2000's lightness weighting: the same change of L* looks smaller
    towards white and black than in the middle."""
    return 1 + 0.015 * (L - 50) ** 2 / np.sqrt(20 + (L - 50) ** 2)


def _evenly_lighter(anchors: List[str], n: int) -> List[str]:
    """
    `n` colours along the path through `anchors` (light to dark, in
    L*a*b*), from the first to the last, at evenly spaced perceived
    lightness: L* steps weighted as CIEDE2000 weights them, so each step
    looks the same size.
    """
    lab = _to_lab(anchors)
    lightness = lab[:, 0]
    grid = np.linspace(lightness[-1], lightness[0], 2001)
    perceived = np.concatenate([[0.0], np.cumsum(np.diff(grid) / _lightness_weight((grid[1:] + grid[:-1]) / 2))])
    out = []
    for target in np.interp(np.linspace(perceived[-1], 0.0, n), perceived, grid):
        i = int(np.clip(np.searchsorted(-lightness, -target, side='right') - 1, 0, len(anchors) - 2))
        span = lightness[i] - lightness[i + 1]
        t = (lightness[i] - target) / span if span else 0.0
        out.append(_lab_to_hex(lab[i] + np.clip(t, 0.0, 1.0) * (lab[i + 1] - lab[i])))
    return [c.upper() for c in out]


def _build_sequential(name: str) -> List[str]:
    """Re-derive CRIMSON_SEQUENTIAL, GOLD_SEQUENTIAL or GREEN_SEQUENTIAL."""
    return _evenly_lighter(_SEQUENTIAL_ANCHORS[name], 8)


@lru_cache(maxsize=1)
def _closest_earlier_after_20() -> Tuple[float, ...]:
    """For each colour after the twentieth: how far it is from the closest colour before it."""
    sequence = DUBOIS_CATEGORICAL_20 + list(_colors_after_20())
    lab = _to_lab(sequence)
    return tuple(float(_ciede2000(lab[i], lab[:i]).min()) for i in range(20, len(sequence)))


def get_categorical(n: int = 4, colorblind_safe: bool = None) -> List[str]:
    """
    Get a categorical color palette with n distinct colors.

    Up to eight colours this is the classic Du Bois palette: crimson, gold
    and black for three or fewer; crimson, gold, green and black for four;
    and from five, crimson, gold, green, blue, rose, purple, brown and
    black, in that order. Up to twenty it continues with
    DUBOIS_CATEGORICAL_20, in which no two colours look more alike than
    crimson and rose do.

    Past twenty, each extra category gets the most distinct tone of the
    palette still available, so no colour is used twice. Some of those
    will look alike, though, and once two of the colours returned are
    closer than crimson and rose a warning says so. (After a few hundred
    the tones run out and colours repeat.) With that many categories,
    grouping the smallest into "Other" usually reads better.

    The first eight never change, so charts made before the palette was
    extended look exactly the same.

    With `colorblind_safe=True` (or after `set_colorblind_safe()`) the
    colours come from DUBOIS_COLORBLIND_8 instead: crimson, gold and black,
    then colours that stay clearly different for readers with any common
    colour-blindness -- the classic palette's crimson and green look alike
    to about one man in twelve. Past eight no colours manage that, and a
    warning says so.

    Parameters
    ----------
    n : int
        Number of colors needed.
    colorblind_safe : bool, optional
        Colours colour-blind readers can tell apart. By default, whatever
        `set_colorblind_safe()` last set (off unless called).

    Returns
    -------
    List[str]
        List of n hex color codes.

    Examples
    --------
    >>> colors = get_categorical(4)
    >>> len(colors)
    4
    >>> len(set(get_categorical(12)))   # no repeats past eight
    12
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if colorblind_safe is None:
        colorblind_safe = _COLORBLIND_SAFE[0]
    if colorblind_safe:
        if n <= len(DUBOIS_COLORBLIND_8):
            return DUBOIS_COLORBLIND_8[:n]
        sequence = DUBOIS_COLORBLIND_8 + list(_colorblind_after_8())
        warnings.warn(
            f"get_categorical({n}, colorblind_safe=True): past eight categories no colours "
            f"stay clearly different for colour-blind readers (the closest two of these are "
            f"{closest_pair_for_every_reader(sequence[:n]):.1f} apart in CIEDE2000 for some "
            f"reader). Labelling the categories directly, or grouping the smallest into "
            f"'Other', keeps the chart readable.",
            stacklevel=2,
        )
        return [sequence[i % len(sequence)] for i in range(n)]
    if n <= 3:
        return DUBOIS_CLASSIC_3[:n]
    elif n <= 4:
        return DUBOIS_CLASSIC_4[:n]
    elif n <= 8:
        return DUBOIS_CATEGORICAL_8[:n]
    elif n <= len(DUBOIS_CATEGORICAL_20):
        return DUBOIS_CATEGORICAL_20[:n]

    sequence = DUBOIS_CATEGORICAL_20 + list(_colors_after_20())
    if n > len(sequence):
        warnings.warn(
            f"get_categorical({n}): there are only {len(sequence)} different colours, so "
            f"colours repeat after that, and many look alike well before it. Consider "
            f"grouping the smallest categories into 'Other'.",
            stacklevel=2,
        )
        return [sequence[i % len(sequence)] for i in range(n)]

    closest = min(_closest_earlier_after_20()[:n - len(DUBOIS_CATEGORICAL_20)])
    if closest < _CLEARLY_DISTINCT:
        warnings.warn(
            f"get_categorical({n}): with this many categories some colours look alike "
            f"(the closest two are {closest:.1f} apart in CIEDE2000; no two of the first "
            f"20 are less than 15). Consider grouping the smallest categories into 'Other'.",
            stacklevel=2,
        )
    return sequence[:n]


def get_diverging(n: int = 7, colorblind_safe: bool = None) -> List[str]:
    """
    Get a diverging color palette.
    
    Useful for data that diverges from a central value (e.g., -100 to +100).
    
    Parameters
    ----------
    n : int
        Number of colors needed. An odd number has the neutral cream in
        the middle; an even one doesn't.
    colorblind_safe : bool, optional
        Crimson to blue instead of crimson to green, whose two ends look
        alike to red-green colour-blind readers. By default, whatever
        `set_colorblind_safe()` last set.
    
    Returns
    -------
    List[str]
        List of hex color codes from one extreme through neutral to opposite extreme
    
    Examples
    --------
    >>> colors = get_diverging(7)
    >>> len(colors)
    7
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if colorblind_safe is None:
        colorblind_safe = _COLORBLIND_SAFE[0]
    palette = DUBOIS_DIVERGING_COLORBLIND if colorblind_safe else DUBOIS_DIVERGING
    # (An even n used to be printed a warning and quietly given n + 1
    # colours, one more than asked for.)
    if n == 1:
        return [palette[len(palette) // 2]]
    if n <= len(palette) and (len(palette) - 1) % (n - 1) == 0:
        step = (len(palette) - 1) // (n - 1)
        return palette[::step]
    return [c.upper() for c in _interpolate_colors(palette, n)]


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert hex color to RGB tuple (0-1 range for matplotlib).
    
    Parameters
    ----------
    hex_color : str
        Hex color code (e.g., '#DC143C')
    
    Returns
    -------
    Tuple[float, float, float]
        RGB values in 0-1 range
    
    Examples
    --------
    >>> rgb = hex_to_rgb('#DC143C')
    >>> print(f"R: {rgb[0]:.3f}, G: {rgb[1]:.3f}, B: {rgb[2]:.3f}")
    R: 0.863, G: 0.078, B: 0.235
    """
    return mcolors.hex2color(hex_color)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """
    Convert RGB values (0-1 range) to hex color.
    
    Parameters
    ----------
    r, g, b : float
        RGB values in 0-1 range
    
    Returns
    -------
    str
        Hex color code
    
    Examples
    --------
    >>> rgb_to_hex(0.863, 0.078, 0.235)
    '#dc143c'
    """
    return mcolors.rgb2hex((r, g, b))


def _interpolate_colors(colors: List[str], n: int) -> List[str]:
    """
    Interpolate between colors to create a palette of n colors.
    
    Parameters
    ----------
    colors : List[str]
        List of hex color codes to interpolate between
    n : int
        Number of colors to generate
    
    Returns
    -------
    List[str]
        List of interpolated hex color codes
    """
    if n == 1:
        return [colors[len(colors) // 2]]
    
    # Convert to RGB for interpolation
    rgb_colors = [hex_to_rgb(c) for c in colors]
    
    # Create interpolated colors
    result = []
    for i in range(n):
        # Map i to position in original color list
        pos = i * (len(rgb_colors) - 1) / (n - 1)
        idx = int(pos)
        frac = pos - idx
        
        if idx >= len(rgb_colors) - 1:
            result.append(colors[-1])
        else:
            # Linear interpolation between two colors
            r1, g1, b1 = rgb_colors[idx]
            r2, g2, b2 = rgb_colors[idx + 1]
            
            r = r1 + (r2 - r1) * frac
            g = g1 + (g2 - g1) * frac
            b = b1 + (b2 - b1) * frac
            
            result.append(rgb_to_hex(r, g, b))
    
    return result


def show_palette(palette_name: str = 'primary', save_path: str = None):
    """
    Draw a palette as a row of swatches, each with its hex code.

    Parameters
    ----------
    palette_name : str
        'primary', 'extended', 'pan_african', 'categorical', 'crimson',
        'gold', 'green' (the sequential palettes) or 'diverging'.
    save_path : str, optional
        If given, save the figure here.

    Returns
    -------
    plt.Figure
        Like the charts: a notebook shows it, and in a script
        ``plt.show()`` does.

    Examples
    --------
    >>> fig = show_palette('primary')
    >>> fig = show_palette('extended', save_path='extended.png')
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    
    # Get the palette
    if palette_name in ['primary', 'extended', 'pan_african']:
        palette = get_palette(palette_name)
        colors = list(palette.values())
        names = list(palette.keys())
        title = f"Du Bois {palette_name.title()} Palette"
    elif palette_name == 'categorical':
        colors = get_categorical(len(DUBOIS_CATEGORICAL_20))
        names = [f'Color {i+1}' for i in range(len(colors))]
        title = "Du Bois Categorical Palette"
    elif palette_name in ['crimson', 'gold', 'green']:
        colors = get_sequential(palette_name)
        names = [f'{i+1}' for i in range(len(colors))]
        title = f"Du Bois {palette_name.title()} Sequential Palette"
    elif palette_name == 'diverging':
        colors = get_diverging(7)
        names = [f'{i+1}' for i in range(len(colors))]
        title = "Du Bois Diverging Palette"
    else:
        raise ValueError(f"Unknown palette: {palette_name}")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 2))
    ax.set_xlim(0, len(colors))
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    # Draw color swatches
    for i, (color, name) in enumerate(zip(colors, names)):
        rect = mpatches.Rectangle((i, 0), 1, 1, facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)
        
        # Add color name below
        ax.text(i + 0.5, -0.15, name, ha='center', va='top', fontsize=8, rotation=45)
        
        # Add hex code above
        ax.text(i + 0.5, 1.05, color.upper(), ha='center', va='bottom', fontsize=7, family='monospace')
    
    ax.set_title(title, fontsize=14, pad=30)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig


# Export main colors as module-level variables for easy access
crimson = DUBOIS_PRIMARY['crimson']
gold = DUBOIS_PRIMARY['gold']
black = DUBOIS_PRIMARY['black']
tan = DUBOIS_PRIMARY['tan']

__all__ = [
    # Dictionaries
    'DUBOIS_PRIMARY',
    'DUBOIS_EXTENDED',
    'DUBOIS_VERIFIED_PLATE51',
    'PAN_AFRICAN',
    # Lists
    'CRIMSON_SEQUENTIAL',
    'GOLD_SEQUENTIAL',
    'GREEN_SEQUENTIAL',
    'DUBOIS_CLASSIC_3',
    'DUBOIS_CLASSIC_4',
    'DUBOIS_CATEGORICAL_8',
    'DUBOIS_CATEGORICAL_20',
    'DUBOIS_DIVERGING',
    # Functions
    'get_palette',
    'get_sequential',
    'get_categorical',
    'get_diverging',
    'hex_to_rgb',
    'rgb_to_hex',
    'show_palette',
    # Quick access
    'crimson',
    'gold',
    'black',
    'tan',
]
