"""
Shared visual-language helpers for every general-purpose chart in this
package (area, bar, butterfly, and whatever comes after them).

Extracted from `area.py` once a second chart type (`bar.py`) needed the
exact same font-detection, contrast-aware ink color, and paint-shading
logic -- rather than let each new chart module quietly re-implement (and
slowly drift out of sync with) its own copy, this is the one place that
defines "what does Du Bois-style ink/paint look like" for the whole
package. Chart-specific layout logic (how a *bar* is sized vs how an
*area band* is sized) stays in each chart's own module; only the shared
visual vocabulary lives here.
"""

import colorsys
import datetime
import functools
import inspect
import logging
import math
import re
import string
import warnings
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import List, Optional, Sequence, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.artist as martist
import matplotlib.font_manager as fm
from matplotlib.path import Path
from matplotlib.transforms import Affine2D, Bbox

COLOR_CREAM = '#ded7c9'
COLOR_INK = '#1a1a1a'


def literal_text(chart_function):
    """
    Decorator for every chart function: draw all text exactly as given.

    matplotlib treats text between two dollar signs as math markup, so a
    label like "$5-$10" came out as an italic "5-10" and the title
    "Spending: $5 to $10 per day" as "SPENDING: 5TO10 PER DAY". Currency
    is everywhere in real data, so every chart builds its figure with math
    parsing off -- and with LaTeX off, in case the user has
    `text.usetex` switched on globally, where "%" and "_" in ordinary
    labels would break. Both settings are fixed on each text object when
    it's created, so the figure keeps them after the chart returns.

    Text parameters (title, subtitle, side and colorbar labels) that
    aren't strings are written out as `category_labels` would write them,
    so a title of 2024 reads "2024".
    """
    signature = inspect.signature(chart_function)
    text_parameters = [p for p in _TEXT_PARAMETERS if p in signature.parameters]

    @functools.wraps(chart_function)
    def wrapper(*args, **kwargs):
        if text_parameters:
            try:
                bound = signature.bind(*args, **kwargs)
            except TypeError:
                bound = None          # the chart function raises its own error
            if bound is not None:
                for name in text_parameters:
                    value = bound.arguments.get(name)
                    if value is not None and not isinstance(value, str):
                        bound.arguments[name] = category_labels([value])[0]
                args, kwargs = bound.args, bound.kwargs
        # Just these two settings are changed, and just they are put back.
        # matplotlib's rc_context put back *every* setting -- including
        # `interactive`, which matplotlib switches on when it makes the
        # first figure of a Jupyter session. When that first figure was one
        # of these charts, rc_context switched it off again, and from then
        # on Jupyter showed no figure at all: only the first chart appeared.
        saved = {key: plt.rcParams[key] for key in _LITERAL_TEXT}
        plt.rcParams.update(_LITERAL_TEXT)
        try:
            return chart_function(*args, **kwargs)
        finally:
            plt.rcParams.update(saved)
    return wrapper


_LITERAL_TEXT = {'text.parse_math': False, 'text.usetex': False}


# Parameters drawn as text. Any value works, as it does in matplotlib: a
# title of 2024 (say, a DataFrame's column name) crashed every chart with
# "expected string or bytes-like object, got 'int'".
_TEXT_PARAMETERS = ('title', 'subtitle', 'left_label', 'right_label', 'colorbar_label')


# Fonts tried, in order, for any character the chart's own font doesn't
# have -- Chinese, Japanese and Korean, Arabic, Hebrew, Devanagari, Thai,
# symbols. Only fonts that are actually installed are used. (Needs
# matplotlib 3.6+, which looks glyphs up font by font; older versions just
# use the first font.)
FALLBACK_FONTS = (
    'DejaVu Sans',                                   # ships with matplotlib
    'Noto Sans CJK JP', 'Noto Sans CJK SC', 'Noto Sans CJK TC', 'Noto Sans CJK KR',
    'Source Han Sans', 'WenQuanYi Zen Hei', 'IPAGothic', 'Droid Sans Fallback',
    'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'PingFang SC', 'Apple SD Gothic Neo',
    'Microsoft YaHei', 'Malgun Gothic', 'Yu Gothic', 'Meiryo', 'SimHei',
    'Noto Sans Arabic', 'Noto Sans Hebrew', 'Noto Sans Devanagari', 'Noto Sans Thai',
    'Arial Unicode MS', 'Segoe UI', 'Tahoma',
    'Noto Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Symbola',
)


class _FallbackWeightFilter(logging.Filter):
    """
    matplotlib 3.11 warns, every time text is drawn, when a font in the
    family list lacks the weight asked for -- and most of FALLBACK_FONTS
    (the CJK fonts especially) come in regular only, so every chart's bold
    text logged "findfont: Failed to find font weight bold for WenQuanYi
    Zen Hei". Using the regular weight for a script the chart's own font
    can't draw is the point of the fallback; that message only is dropped,
    and only for these fonts.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not (str(record.msg).startswith('findfont: Failed to find font weight')
                    and len(record.args or ()) > 1 and record.args[1] in FALLBACK_FONTS)


logging.getLogger('matplotlib.font_manager').addFilter(_FallbackWeightFilter())


@functools.lru_cache(maxsize=1)
def _installed_fonts() -> frozenset:
    return frozenset(f.name for f in fm.fontManager.ttflist)


def as_items(mapping, context: str) -> List[Tuple[str, object]]:
    """
    (label, value) pairs from a dict, a pandas Series (index -> value), a
    pandas DataFrame (column -> column), or anything else with `.items()`,
    with every label turned into a string.

    pie_chart and snake_chart called `segments.values()`, which on a
    pandas Series is an array rather than a method, so passing one crashed
    with "'numpy.ndarray' object is not callable"; stacked_area_chart
    crashed on integer series names (years, codes) the first time it
    upper-cased one.
    """
    items = getattr(mapping, 'items', None)
    if not callable(items):
        raise TypeError(f"{context} must be a dict of label -> value, or a pandas Series; "
                        f"got {type(mapping).__name__}.")
    pairs = list(items())
    labels = named_labels([k for k, _ in pairs], context)
    return [(label, v) for label, (_, v) in zip(labels, pairs)]


def segment_items(segments, chart: str) -> List[Tuple[str, object]]:
    """
    A pie's or a snake's segments as (name, value) pairs: from a dict, or a
    pandas Series indexed by name. A table is an error, rather than its
    column names being read as the segments.
    """
    if hasattr(segments, 'columns'):
        raise TypeError(f"{chart}: `segments` is a table; pass one column of it, indexed by "
                        f"name: df['share'], say, or df.set_index('name')['share'].")
    return as_items(segments, "`segments`")


def is_missing(v) -> bool:
    """True for None, NaN, NaT and pandas' NA."""
    if v is None or type(v).__name__ in ('NAType', 'NaTType'):
        return True
    if isinstance(v, (float, np.floating)):
        return bool(np.isnan(v))
    if isinstance(v, np.datetime64):
        return bool(np.isnat(v))
    return False


# A date written the ISO way, as a CSV file has it until it's parsed:
# "2020-03-01", "2020-03", "2000-01-01T08:00:00.000Z", "2020-03-01 14:30".
_ISO_DATE = re.compile(r'(\d{4})-(\d{2})(?:-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?'
                       r'(Z|[+-]\d{2}(?::?\d{2})?)?)?)?')


def _iso_datetime(text: str) -> Optional[datetime.datetime]:
    """The date an ISO 8601 string writes, or None if it isn't one."""
    m = _ISO_DATE.fullmatch(text.strip())
    if not m:
        return None
    year, month, day, hour, minute, second, fraction, zone = m.groups()
    try:
        moment = datetime.datetime(int(year), int(month), int(day or 1), int(hour or 0),
                                   int(minute or 0), int(second or 0),
                                   int((fraction or '0')[:6].ljust(6, '0')))
    except ValueError:              # "2020-13-45": not a date
        return None
    if zone:
        minutes = 0
        if zone != 'Z':
            digits = zone[1:].replace(':', '')
            minutes = (int(digits[:2]) * 60 + int(digits[2:] or 0)) * (-1 if zone[0] == '-' else 1)
        moment = moment.replace(tzinfo=datetime.timezone(datetime.timedelta(minutes=minutes)))
    return moment


def as_datetime(v) -> Optional[datetime.datetime]:
    """
    `v` as a datetime.datetime if it's a date or time stamp of any kind --
    datetime.date or datetime.datetime, a pandas Timestamp, a numpy
    datetime64, or a date written the ISO way ("2020-03-01", "2020-03",
    "2000-01-01T08:00:00Z") -- or None if it isn't one (or is missing: NaT).

    A CSV file's dates are text until they're parsed, so a column read
    with pd.read_csv as it is was drawn as text: the area chart printed
    "2000-01-01T08:00:00.000Z" over its first point and spaced the dates
    evenly, whatever the gaps between them.
    """
    if isinstance(v, str):
        return _iso_datetime(v)
    if is_missing(v):
        return None
    if type(v).__name__ == 'Period':
        # A pandas Period -- a month, a quarter, a year -- by its start, so
        # a PeriodIndex reads "Jan 2012" like the dates it stands for (it
        # used to print as "2012-01").
        v = v.start_time
    if isinstance(v, np.datetime64):
        v = v.astype('datetime64[us]').astype(datetime.datetime)
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, datetime.date):
        return datetime.datetime(v.year, v.month, v.day)
    return None


def date_labels(dates: Sequence[datetime.datetime]) -> List[str]:
    """
    Labels for a set of dates, as compact as they allow while still
    telling every date apart: just the year when every date is 1 January,
    month and year when every date is the 1st, the date alone when there's
    no time of day, and the time to the minute (or second) otherwise. The
    first two need at least two dates -- one date on 1 January could be
    that particular day.
    """
    dates = _midnights(dates)
    midnight = all(d.time() == datetime.time() for d in dates)
    several = len(dates) >= 2
    if several and midnight and all(d.month == 1 and d.day == 1 for d in dates):
        return [f'{d.year}' for d in dates]
    if several and midnight and all(d.day == 1 for d in dates):
        return [d.strftime('%b %Y') for d in dates]
    if midnight:
        return [d.strftime('%Y-%m-%d') for d in dates]
    if all(d.second == 0 and d.microsecond == 0 for d in dates):
        return [d.strftime('%Y-%m-%d %H:%M') for d in dates]
    return [d.strftime('%Y-%m-%d %H:%M:%S') for d in dates]


def _midnights(dates: Sequence[datetime.datetime]) -> List[datetime.datetime]:
    """
    `dates` as days, when their times of day only say where in the world
    each day began: every date at about the same time -- within two hours
    of each other, for daylight saving -- and none on the same day as
    another. Monthly figures stored as midnight in California are
    "2000-01-01T08:00:00Z", or 07:00 in summer, and were labelled
    "2000-01-01 08:00"; a time after midday is the next day's midnight
    somewhere east ("2011-12-31 15:00" is 1 January in Tokyo). Other dates
    are returned as they are.
    """
    dates = [d.replace(tzinfo=None) for d in dates]
    if len(dates) < 2:
        return dates
    hours = np.array([d.hour + d.minute / 60 + d.second / 3600 for d in dates])
    if not hours.any():
        return dates
    # The spread of the times round the clock (23:00 and 01:00 are two hours apart).
    shifted = (hours - hours[0] + 12) % 24
    if shifted.max() - shifted.min() > 2:
        return dates
    gaps = np.diff(sorted(d.timestamp() for d in dates))
    if gaps.min() < 22 * 3600:
        return dates
    return [datetime.datetime(d.year, d.month, d.day) + datetime.timedelta(days=int(d.hour >= 12))
            for d in dates]


def _is_real_number(v) -> bool:
    return (isinstance(v, (int, float, np.integer, np.floating))
            and not isinstance(v, (bool, np.bool_)))


def _number_text(v) -> str:
    """
    One number written the way a person would: whole numbers without a
    decimal point, and without the floating-point noise of arithmetic
    (0.1 + 0.2 is "0.3", not "0.30000000000000004"). numpy's float32 and
    float16 print with the digits their own precision holds.
    """
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, np.floating) and np.dtype(type(v)).itemsize < 8:
        text = str(v)
        return text[:-2] if text.endswith('.0') else text
    return f'{float(v):.15g}'


def _number_labels(values) -> List[str]:
    """
    Labels for a set of numbers used as categories or positions. Integers
    print as they are. A set of floats shares one number of decimal places
    -- the fewest that show every value, up to six -- so 2018.0 reads
    "2018" and [0.5, 1.0, 1.5] reads "0.5, 1.0, 1.5". Anything else (ints
    mixed with floats, values needing more decimals, magnitudes from 1e15
    up) prints value by value.
    """
    texts = [_number_text(v) for v in values]
    if all(isinstance(v, (float, np.floating)) for v in values):
        finite = [(v, t) for v, t in zip(values, texts) if np.isfinite(v)]
        if finite and max(abs(float(v)) for v, _ in finite) < 1e15 and not any('e' in t for _, t in finite):
            decimals = max(len(t.split('.')[1]) if '.' in t else 0 for _, t in finite)
            if decimals <= 6:
                return [f'{float(v):.{decimals}f}' if np.isfinite(v) else t
                        for v, t in zip(values, texts)]
    return texts


def category_labels(values) -> List[str]:
    """
    Text for each category, series name or segment name, however it was
    given. Strings are unchanged. Numbers and dates are written the way a
    person would write them, not the way Python prints them: pandas often
    turns a column of years into floats, and dates into Timestamps, so
    labels used to read "2018.0", "2018-01-01 00:00:00" or
    "2018-01-01T00:00:00.000000000". Now they read "2018".

    Tidying never makes two different categories look the same; if it
    would, every label is left exactly as Python prints it.
    """
    values = list(values)
    plain = [str(v) for v in values]
    if not values:
        return plain
    if all(isinstance(v, tuple) and v for v in values) and len({len(v) for v in values}) == 1:
        # A pandas MultiIndex -- df.groupby(['year', 'month']) -- names each
        # row with a tuple, which printed "(2000, 1)" and "('Germany', '15-40')".
        # Each part is written as its own column would be, joined with commas.
        parts = [category_labels(column) for column in zip(*values)]
        labels = [', '.join(row) for row in zip(*parts)]
        return plain if len(set(labels)) < len(set(plain)) else labels
    dates = [as_datetime(v) for v in values]
    if all(d is not None for d in dates):
        labels = date_labels(dates)
    elif all(_is_real_number(v) for v in values):
        labels = _number_labels(values)
    else:
        labels = [date_labels([d])[0] if d is not None
                  else _number_text(v) if _is_real_number(v) and not is_missing(v)
                  else str(v)
                  for v, d in zip(values, dates)]
    if len(set(labels)) < len(set(plain)):
        return plain
    return labels


def named_labels(values, context: str) -> List[str]:
    """
    `category_labels(values)`, after making sure none is missing. A row
    with no name -- a "Total" row whose name cell is empty, read by pandas
    as NaN -- used to be drawn as a bar, slice or band called "nan".
    """
    values = list(values)
    missing = [i for i, v in enumerate(values) if is_missing(v)]
    if missing:
        where = ', '.join(f'position {i}' + (f' (after {values[i - 1]!r})' if i and not is_missing(values[i - 1]) else '')
                          for i in missing[:5])
        raise ValueError(
            f"{context} has {'a name' if len(missing) == 1 else f'{len(missing)} names'} missing "
            f"(None or NaN) at {where}{' and more' if len(missing) > 5 else ''}. Every item needs "
            f"a name: drop {'that row' if len(missing) == 1 else 'those rows'} (a total, say) or "
            f"name {'it' if len(missing) == 1 else 'them'} first.")
    return category_labels(values)


def warn_repeated(labels: Sequence[str], chart: str, what: str = '`categories`') -> None:
    """
    Warn when a name appears more than once: each is drawn as an item of
    its own, side by side, which is right for a ranking of people who
    share a name but usually means a table has a row twice.
    """
    seen, repeated = set(), []
    for label in labels:
        if label in seen and label not in repeated:
            repeated.append(label)
        seen.add(label)
    if repeated:
        shown = ', '.join(map(repr, repeated[:5])) + (' and more' if len(repeated) > 5 else '')
        warnings.warn(
            f"{chart}: {shown} {'appears' if len(repeated) == 1 else 'appear'} more than once "
            f"in {what}; each is drawn on its own. If they're the same thing, combine them "
            f"first (in pandas, df.groupby(...).sum()), or drop the repeat.",
            UserWarning, stacklevel=3)


_GENERIC_FAMILIES = {'serif', 'sans-serif', 'sans serif', 'sans', 'cursive', 'fantasy',
                     'monospace', 'mono'}


def font_stack(font) -> Tuple[str, ...]:
    """
    `font` (a family name, or a sequence of them) followed by whichever
    FALLBACK_FONTS are installed, so text in any script finds a font that
    can draw it instead of rendering as empty boxes. The chart's own font
    still draws every character it has.

    A font that isn't installed is left out, with one warning that says
    so -- matplotlib's own message, "findfont: Font family ... not found",
    came about twenty times a chart -- and if none of `font` is, the
    chart's usual font is used.
    """
    primary = [font] if isinstance(font, str) else list(font)
    installed = _installed_fonts()
    missing = [f for f in primary if f not in installed and str(f).lower() not in _GENERIC_FAMILIES]
    if missing:
        primary = [f for f in primary if f not in missing] or [get_font()]
        warnings.warn(
            f"{', '.join(map(repr, missing))} {'is' if len(missing) == 1 else 'are'} not an "
            f"installed font, so the chart uses {primary[0]!r}. "
            f"matplotlib.font_manager.get_font_names() lists the installed fonts.",
            UserWarning, stacklevel=4)
    return tuple(primary + [f for f in FALLBACK_FONTS if f in installed and f not in primary])


def validate_finite(values, context: str, names: Optional[Sequence[str]] = None) -> None:
    """
    Raise a clear ValueError if `values` contains any NaN or infinite
    entries, naming exactly which ones (by label, if `names` is given)
    rather than which raw array position.

    This exists because a NaN or inf sneaking into any chart's values
    doesn't fail loudly and immediately -- every chart in this package
    computes axis limits, box sizes, or angles directly from these
    numbers, and a single non-finite entry corrupts that math instead of
    raising. Checked directly, not assumed: a NaN value in bar_chart
    rendered as a completely invisible, unlabeled bar with no error at
    all, and in one case appeared to have thrown off the axis scale
    for the *other*, perfectly valid bars in the same chart -- exactly
    the "confidently wrong, silently" failure mode this whole package
    otherwise goes out of its way to avoid.

    Parameters
    ----------
    values : array-like
        The values to check (any shape; flattened for the check).
    context : str
        A short phrase naming what these values are, used in the error
        message -- e.g. "`values`" or "segment values".
    names : Sequence[str], optional
        Parallel labels (categories, segment names, ...) for the
        flattened values, used to name exactly which entries are bad
        instead of only reporting a raw index.
    """
    as_numbers(values, context, names)


def _number_text_hint(v) -> str:
    """How to make a number of text written for people -- "12.5%",
    "1,234", "$5" -- into one, when that's what `v` is."""
    if not isinstance(v, str):
        return ''
    text = v.strip()
    bare = text.rstrip('%').strip()
    if text.endswith('%') and _is_number_text(bare):
        return (" It's a percentage written as text: take the % sign off first -- in pandas, "
                "s.str.rstrip('%').astype(float).")
    if ',' in text and _is_number_text(text.replace(',', '')):
        return (" It's a number written with thousands separators: read the file with "
                "pd.read_csv(..., thousands=','), or take the commas out first.")
    if text[:1] and text[:1] in '$€£¥' and _is_number_text(text[1:].replace(',', '')):
        return (" It's an amount written with its currency sign: take the sign (and any "
                "commas) off first, and pass value_format='${:,.0f}' to put it back in the labels.")
    return ''


def _is_number_text(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return bool(text)


def as_numbers(values, context: str, names: Optional[Sequence[str]] = None) -> np.ndarray:
    """
    `values` as a float array, raising a clear ValueError that names the
    entry if any is missing (None, NaN), infinite, or not a number at all.

    Numbers of any kind convert: ints, floats, numpy scalars, Decimal,
    Fraction, numeric strings like "12" and booleans. Before this, a string
    like "n/a" failed with numpy's "could not convert string to float",
    and a missing value was reported as "NaN or infinity".
    """
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        flat_in = list(np.asarray(values, dtype=object).reshape(-1))
        for i, v in enumerate(flat_in):
            try:
                float(v)
            except (TypeError, ValueError):
                where = str(names[i]) if names is not None and len(names) == len(flat_in) else f"index {i}"
                raise ValueError(
                    f"{context} has a value that isn't a number for {where}: {v!r}. "
                    f"Every value must be a real, finite number.{_number_text_hint(v)}") from None
        raise
    flat = arr.reshape(-1)
    bad = ~np.isfinite(flat)
    if not bad.any():
        return arr
    bad_idx = np.where(bad)[0]
    if names is not None and len(names) == len(flat):
        bad_desc = [str(names[i]) for i in bad_idx]
    else:
        bad_desc = [f"index {i}" for i in bad_idx]
    raise ValueError(
        f"{context} contains a missing or non-finite value (None, NaN or infinity) for: "
        f"{bad_desc}. Every value must be a real, finite number: leave those out (in pandas, "
        f".dropna()), or fill them in."
    )


def aligned(values, categories: Sequence[str], context: str) -> list:
    """
    `values` as a list in the order of `categories` (their labels, as
    `category_labels` writes them).

    A pandas Series whose index names the categories -- every one, each
    once -- is matched to them by its index, as pandas would, whatever
    order its rows are in. A pivot table's rows come sorted ('0-4',
    '10-14', '5-9'), so matching them to the categories by position put
    the 10-14 figures on the 5-9 bar, with nothing to show for it.

    pandas' default index, 0, 1, 2..., and an index that names none of
    the categories -- the row numbers left by filtering a table, say --
    leave the values in the order given. An index that names some of the
    categories but not all is an error, since there's no telling which
    value belongs to which. Anything that isn't a pandas Series is taken
    in the order given.
    """
    index = getattr(values, 'index', None)
    if index is None or callable(index) or not hasattr(values, 'iloc'):
        return list(values)
    # (pandas 3 makes a RangeIndex of any evenly spaced whole numbers, so
    # 1990, 2000, 2010 is one too: only 0, 1, 2... is the default.)
    if type(index).__name__ == 'RangeIndex' and index.start == 0 and index.step == 1:
        return list(values)
    keys = category_labels(list(index))
    cats = list(categories)
    if keys == cats:
        return list(values)
    key_set, cat_set = set(keys), set(cats)
    if not key_set & cat_set:
        return list(values)
    if key_set == cat_set and len(key_set) == len(keys) == len(cats):
        position = {key: i for i, key in enumerate(keys)}
        listed = list(values)
        return [listed[position[c]] for c in cats]
    missing = [c for c in cats if c not in key_set]
    extra = [k for k in keys if k not in cat_set]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    problems = []
    if missing:
        problems.append(f"no value for {', '.join(map(repr, missing[:5]))}"
                        + (f" and {len(missing) - 5} more" if len(missing) > 5 else ''))
    if extra:
        problems.append(f"values for {', '.join(map(repr, extra[:5]))}"
                        + (f" and {len(extra) - 5} more" if len(extra) > 5 else '')
                        + ", which aren't categories")
    if repeated:
        problems.append(f"more than one value for {', '.join(map(repr, repeated[:5]))}")
    raise ValueError(
        f"{context} is a pandas Series whose index names some of the categories but not "
        f"exactly them: {'; '.join(problems)}. Its values are matched to the categories by "
        f"its index, as pandas would match them. Use .reindex(categories) to choose a value "
        f"for each, or .to_numpy() to take them in the order given.")


def get_font() -> str:
    """
    Pick the closest available monospace/typewriter font.

    Probes what's actually installed rather than hard-coding a name that
    might not resolve on a given system -- the original plates use a
    bold, hand-lettered caps style; Liberation Mono (metric-compatible
    with Courier) is the closest common stand-in when available, then
    Courier New itself, which Mac and Windows have. DejaVu Sans Mono,
    which ships with matplotlib, comes last: it was second, so on a Mac
    or a Windows machine -- no Liberation fonts -- it was picked over the
    Courier New they have.
    """
    available = {f.name for f in fm.fontManager.ttflist}
    for candidate in ['Liberation Mono', 'Courier New', 'Nimbus Mono PS', 'Courier',
                      'DejaVu Sans Mono']:
        if candidate in available:
            return candidate
    return 'monospace'


def text_color_for(bg_hex: str) -> str:
    """
    Pick black or near-white ink depending on a fill's brightness, so a
    label drawn on top of it stays legible regardless of which color the
    caller's palette happens to assign to that fill -- a user passing
    their own bright-yellow color shouldn't get invisible yellow-on-white
    text just because the default happened to be a dark color.
    """
    r, g, b = plt.matplotlib.colors.to_rgb(bg_hex)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return '#1a1a1a' if luminance > 0.5 else '#f2ede0'


def shade(hex_color: str, amount: float) -> str:
    """
    Lighten (amount > 0) or darken (amount < 0) a hex color for texture,
    working in HSV so the result stays a plausible paint variant of the
    same hue rather than drifting toward grey the way naive RGB
    lightening does.
    """
    r, g, b = plt.matplotlib.colors.to_rgb(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    v = min(1.0, max(0.0, v + amount))
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return plt.matplotlib.colors.to_hex((r2, g2, b2))


@functools.lru_cache(maxsize=8)
def _row_blur_matrix(n: int, sigma: float) -> np.ndarray:
    """
    scipy's gaussian_filter1d down the rows of an n-row array, as an n x n
    matrix: M @ x gives the same result to the last bit or two of a
    float (it's built by filtering the identity matrix, edges and all).
    The texture's long vertical streaks use a 361-tap filter, which
    scipy runs as a loop; as a matrix product it takes a tenth of the
    time, and the matrix is reused for every rectangle of that size.
    """
    from scipy.ndimage import gaussian_filter1d
    matrix = gaussian_filter1d(np.eye(n), sigma, axis=0)
    matrix.setflags(write=False)
    return matrix


def streak_field(noise: np.ndarray, sigma_rows: float = 45.0, sigma_cols: float = 1.2) -> np.ndarray:
    """gaussian_filter(noise, sigma=(sigma_rows, sigma_cols)), faster (see above)."""
    from scipy.ndimage import gaussian_filter1d
    return gaussian_filter1d(_row_blur_matrix(noise.shape[0], sigma_rows) @ noise, sigma_cols, axis=1)


def paint_grain(combined: np.ndarray, strength: float, base_rgb, light_rgb, dark_rgb) -> np.ndarray:
    """
    The RGBA texture: each pixel moves from the base colour toward the
    light shade where the noise is positive and the dark shade where it's
    negative, in proportion to the noise. Done a channel at a time into
    one array, which gives exactly the same numbers as the whole-array
    version it replaced, in about half the time.
    """
    h, w = combined.shape
    out = np.empty((h, w, 4))
    out[..., 3] = 1.0
    amount = combined * strength
    lighter = np.where(combined > 0, amount, 0.0)   # one of these two is exactly 0 at each pixel
    darker = amount - lighter
    for ch in range(3):
        channel = base_rgb[ch] + (light_rgb[ch] - base_rgb[ch]) * lighter
        channel += (base_rgb[ch] - dark_rgb[ch]) * darker
        np.clip(channel, 0, 1, out=channel)
        out[..., ch] = channel
    return out


def _grain_rgba(base_color: str, seed: int, shape: Tuple[int, int] = (220, 220),
                 strength: float = 0.65) -> np.ndarray:
    """
    Build an RGBA grain texture array from a smoothed noise field, blended
    toward lightened/darkened variants of `base_color`. Shared core used
    by both the polygon-clipped area texture and the rectangle-clipped
    bar texture below -- the only difference between those two is *what
    shape gets clipped to*, not how the paint grain itself is generated.

    The default `strength` was originally 0.14. Checked directly (not
    assumed): at that value, the actual rendered pixel variance across a
    real bar was so small (a handful of colors within a range of about
    3 RGB units out of 255) that it read as a flat, textureless fill --
    defeating the entire point of a "hand-painted" effect. Comparing
    strength values side by side, in real chart contexts rather than
    isolated color swatches, found a second, more specific problem
    hiding behind the first: the same nominal strength that reads as
    tasteful, visible grain on a saturated mid-tone color (crimson, gold)
    reads as distracting noise on a near-black fill, because human
    perception is more sensitive to a given absolute luminance change
    near the dark end of the range than in the middle -- confirmed by
    comparing an actual large black band's texture against equally-large
    red and gold bands at the same strength, not just small isolated
    swatches of each color, which didn't show the difference clearly
    since the effect compounds specifically with a large, low-luminance
    fill area.
    """
    return paint_grain(_grain_noise(seed, shape), *_grain_colours(base_color, strength))


def _grain_noise(seed: int, shape: Tuple[int, int] = (220, 220)) -> np.ndarray:
    """The smoothed noise behind _grain_rgba: fine grain and long
    vertical streaks, each scaled to -1..1, mixed 60:40."""
    from scipy.ndimage import gaussian_filter
    rng = np.random.RandomState(seed)
    h, w = shape
    grain = gaussian_filter(rng.normal(0, 1, size=(h, w)), sigma=0.8)
    grain = grain / (np.abs(grain).max() + 1e-9)
    streaks = streak_field(rng.normal(0, 1, size=(h, w)))
    streaks = streaks / (np.abs(streaks).max() + 1e-9)
    return 0.6 * grain + 0.4 * streaks


def _grain_colours(base_color: str, strength: float = 0.65):
    """paint_grain's (strength, base, light, dark) for _grain_rgba."""
    # Dampen the effective strength for dark base colors specifically --
    # full strength once lightness reaches about a quarter of the way up
    # from black, tapering down (never below 40% of the nominal
    # strength) as lightness approaches zero.
    _, base_l, _ = colorsys.rgb_to_hls(*plt.matplotlib.colors.to_rgb(base_color))
    lightness_factor = min(1.0, 0.4 + base_l * 2.4)
    strength = strength * lightness_factor
    base_rgb = np.array(plt.matplotlib.colors.to_rgb(base_color))
    light_rgb = np.array(plt.matplotlib.colors.to_rgb(shade(base_color, 0.12)))
    dark_rgb = np.array(plt.matplotlib.colors.to_rgb(shade(base_color, -0.12)))
    return strength, base_rgb, light_rgb, dark_rgb


class GrainShape:
    """
    One textured shape in a GrainLayer: its outline (a Path in data
    units), the box its grain is stretched over (x0, x1, y0, y1 in data
    units; x1 < x0 mirrors it), where its noise comes from, and how it's
    coloured.
    """

    def __init__(self, path, extent, noise, colours, rectangle=False):
        self.path, self.extent, self.colours = path, extent, colours
        self.rectangle = rectangle      # the path is an axis-aligned rectangle
        self._noise, self._noise_value = noise, None

    def noise(self) -> np.ndarray:
        if self._noise_value is None:
            self._noise_value = self._noise()
        return self._noise_value

    def get_array(self) -> np.ndarray:
        """The shape's whole grain, as an RGBA image (rows from the bottom)."""
        return paint_grain(self.noise(), *self.colours)


class GrainLayer(martist.Artist):
    """
    The grain of every textured shape in one axes, drawn as one image.

    Each shape's grain is what it was when every shape had an image of its
    own: a field of smoothed noise from its own seed, painted in its own
    colour, stretched over the shape's box and clipped to the shape's
    outline. But the shapes are sampled into a single picture when the
    chart is drawn -- at the resolution it's drawn at -- and drawn once.
    An image apiece cost several milliseconds a shape to make and draw:
    with a few hundred bars, slices or snake pieces, that was most of a
    four- or five-second chart. Past the first REUSE shapes, a shape
    borrows the noise of an earlier one (each still in its own colour):
    making the noise was most of what was left, and no one can tell one
    patch of noise from another.

    The outlines' edges are antialiased exactly as clipping each image to
    its shape antialiased them -- each shape's coverage of a pixel comes
    from matplotlib's own renderer -- and the shapes are laid over each
    other in the order they were added, as the images were.
    """

    REUSE = 24
    zorder = 2.4

    def __init__(self, ax):
        super().__init__()
        self.axes = ax
        self.set_figure(ax.figure)
        self.set_clip_box(ax.bbox)
        self.shapes: List[GrainShape] = []
        self._drawn = None          # (key, image, left, bottom) of the last draw

    @classmethod
    def of(cls, ax) -> 'GrainLayer':
        """The axes' grain layer, made and added the first time."""
        layer = getattr(ax, '_dubois_grain', None)
        if layer is None:
            layer = cls(ax)
            ax._dubois_grain = layer
            ax.add_artist(layer)
        return layer

    def add(self, path, extent, noise, colours, rectangle=False) -> GrainShape:
        shape = GrainShape(path, extent, noise, colours, rectangle)
        self.shapes.append(shape)
        self._drawn = None
        self.stale = True
        return shape

    def get_window_extent(self, renderer=None):
        return Bbox.null()

    def __getstate__(self):
        state = super().__getstate__()
        state['_drawn'] = None      # a picture of the last draw; made again when needed
        return state

    @martist.allow_rasterization
    def draw(self, renderer):
        if not self.get_visible() or not self.shapes:
            self.stale = False
            return
        magnification = renderer.get_image_magnification()
        to_pixels = self.axes.transData + Affine2D().scale(magnification)
        clip = self.axes.bbox
        key = (magnification, tuple(clip.bounds), tuple(to_pixels.transform([(0, 0), (1, 1)]).ravel()),
               len(self.shapes))
        if self._drawn is None or self._drawn[0] != key:
            self._drawn = (key,) + self._composite(to_pixels, clip, magnification)
        _, image, left, bottom = self._drawn
        if image is not None:
            gc = renderer.new_gc()
            self._set_gc_clip(gc)
            gc.set_alpha(self.get_alpha())
            renderer.draw_image(gc, left, bottom, image)
            gc.restore()
        self.stale = False

    def _composite(self, to_pixels, clip, magnification):
        from matplotlib.backends.backend_agg import RendererAgg
        cx0, cx1 = math.floor(clip.x0 * magnification), math.ceil(clip.x1 * magnification)
        cy0, cy1 = math.floor(clip.y0 * magnification), math.ceil(clip.y1 * magnification)
        # Each shape's box in whole pixels, inside the axes; the picture
        # covers them all.
        windows = []
        for shape in self.shapes:
            bounds = shape.path.get_extents(to_pixels)
            ix0, ix1 = max(math.floor(bounds.x0), cx0), min(math.ceil(bounds.x1), cx1)
            iy0, iy1 = max(math.floor(bounds.y0), cy0), min(math.ceil(bounds.y1), cy1)
            if ix1 > ix0 and iy1 > iy0:
                windows.append((shape, ix0, ix1, iy0, iy1))
        if not windows:
            return None, 0, 0
        x0, x1 = min(w[1] for w in windows), max(w[2] for w in windows)
        y0, y1 = min(w[3] for w in windows), max(w[4] for w in windows)
        colour = np.zeros((y1 - y0, x1 - x0, 3), dtype=np.float32)  # premultiplied; rows from the bottom
        alpha = np.zeros((y1 - y0, x1 - x0), dtype=np.float32)
        to_data = to_pixels.inverted()
        for shape, ix0, ix1, iy0, iy1 in windows:
            w, h = ix1 - ix0, iy1 - iy0
            # How much of each pixel the shape covers, as matplotlib's
            # renderer would clip to it. A rectangle is snapped to whole
            # pixels -- each edge to the nearest pixel boundary, as the
            # renderer snaps it -- and covers them completely; anything
            # else, the renderer itself works out.
            if shape.rectangle:
                (px0, py0), (px1, py1) = np.sort(to_pixels.transform(shape.path.vertices[[0, 2]]), axis=0)
                ix0, ix1 = max(math.floor(px0 + 0.5), ix0), min(math.floor(px1 + 0.5), ix1)
                iy0, iy1 = max(math.ceil(py0 - 0.5), iy0), min(math.ceil(py1 - 0.5), iy1)
                if ix1 <= ix0 or iy1 <= iy0:
                    continue
                w, h = ix1 - ix0, iy1 - iy0
                jj = ii = cover = None
            else:
                canvas = RendererAgg(w, h, 72)
                gc = canvas.new_gc()
                gc.set_linewidth(0)
                canvas.draw_path(gc, shape.path, to_pixels + Affine2D().translate(-ix0, -iy0),
                                 (1.0, 1.0, 1.0, 1.0))
                gc.restore()
                cover = np.asarray(canvas.buffer_rgba())[::-1, :, 3]
                jj, ii = np.nonzero(cover)
                if not len(jj):
                    continue
                cover = (cover[jj, ii] / np.float32(255))[:, None]
            # The grain at the centre of each pixel the shape covers,
            # sampled bilinearly from the shape's own field as an image
            # stretched over its box would be.
            ex0, ex1, ey0, ey1 = shape.extent
            noise = shape.noise()
            fh, fw = noise.shape
            xs = to_data.transform(np.column_stack([np.arange(ix0, ix1) + 0.5, np.full(w, iy0 + 0.5)]))[:, 0]
            ys = to_data.transform(np.column_stack([np.full(h, ix0 + 0.5), np.arange(iy0, iy1) + 0.5]))[:, 1]
            cols, col_w = _bilinear_index((xs - ex0) / (ex1 - ex0) * fw - 0.5, fw)
            rows, row_w = _bilinear_index((ys - ey0) / (ey1 - ey0) * fh - 0.5, fh)
            # Paint only the rows and columns the samples use.
            used_r, rows = np.unique(rows, return_inverse=True)
            used_c, cols = np.unique(cols, return_inverse=True)
            rows, cols = rows.reshape(-1, 2), cols.reshape(-1, 2)
            painted = paint_grain(noise[np.ix_(used_r, used_c)], *shape.colours)[..., :3]
            if cover is None:
                # The whole block: between rows, then between columns.
                between = (row_w[:, 0, None, None] * painted[rows[:, 0]]
                           + row_w[:, 1, None, None] * painted[rows[:, 1]])
                block = (slice(iy0 - y0, iy1 - y0), slice(ix0 - x0, ix1 - x0))
                colour[block] = (col_w[None, :, 0, None] * between[:, cols[:, 0]]
                                 + col_w[None, :, 1, None] * between[:, cols[:, 1]])
                alpha[block] = 1.0
                continue
            rows, cols, row_w, col_w = rows[jj], cols[ii], row_w[jj], col_w[ii]
            grain = sum(row_w[:, a, None] * col_w[:, b, None] * painted[rows[:, a], cols[:, b]]
                        for a in (0, 1) for b in (0, 1))
            at = (jj + (iy0 - y0), ii + (ix0 - x0))
            colour[at] = grain * cover + colour[at] * (1 - cover)
            alpha[at] = cover[:, 0] + alpha[at] * (1 - cover[:, 0])
        image = np.empty(alpha.shape + (4,), dtype=np.uint8)
        np.divide(colour, alpha[..., None], out=colour, where=alpha[..., None] > 0)
        np.clip(colour, 0, 1, out=colour)
        colour *= 255
        image[..., :3] = np.rint(colour)
        image[..., 3] = np.rint(alpha * 255)
        return image, x0 / magnification, y0 / magnification


def _bilinear_index(position: np.ndarray, size: int):
    """For sample positions along one axis of a field `size` long (0 is
    the first value's centre): the two neighbouring indices of each, and
    their weights, with positions past either end taking the end value."""
    lower = np.floor(position)
    weight = position - lower
    lower = lower.astype(int)
    index = np.column_stack([np.clip(lower, 0, size - 1), np.clip(lower + 1, 0, size - 1)])
    return index.ravel(), np.column_stack([1 - weight, weight])


def _texture_noise(layer: 'GrainLayer', seed: int):
    """Where a new shape's noise comes from: its own seed for the first
    GrainLayer.REUSE shapes of the layer, then an earlier shape's."""
    n = len(layer.shapes)
    if n < GrainLayer.REUSE:
        return functools.partial(_grain_noise, seed)   # (not a lambda: a figure has to pickle)
    donor = layer.shapes[n % GrainLayer.REUSE]
    return donor.noise


def add_rect_texture(ax, x0: float, y0: float, width: float, height: float,
                      base_color: str, seed: int = 0):
    """
    Paint a light hand-painted-style grain texture into a single
    rectangular region (a bar, a butterfly-chart bar, ...), clipped so it
    never bleeds past the rectangle's own edges. The axes' GrainLayer
    draws it (with every other textured shape in the axes); returns its
    GrainShape.

    Silently does nothing for a zero-size rectangle (a bar with value 0),
    since there's no visible area to paint.
    """
    if width == 0 or height == 0:
        return None
    # A rectangle under 6px across or tall gets none: the grain can't show
    # at that size, and painting it on 500 narrow snake pieces or a
    # thousand bars took half a minute.
    corners = ax.transData.transform([(x0, y0), (x0 + width, y0 + height)])
    if min(abs(corners[1] - corners[0])) < 6:
        return None
    layer = GrainLayer.of(ax)
    path = Path.unit_rectangle().transformed(Affine2D().scale(width, height).translate(x0, y0))
    return layer.add(path, (x0, x0 + width, y0, y0 + height), _texture_noise(layer, seed),
                     _grain_colours(base_color), rectangle=True)


def add_patch_texture(ax, patch, base_color: str,
                       extent: Tuple[float, float, float, float], seed: int = 0):
    """
    Paint the same grain texture into an arbitrary patch shape -- a pie
    wedge, in particular -- clipped exactly to that patch's outline, with
    the grain stretched over `extent` (x0, x1, y0, y1, in data units).
    `patch` should be in the axes' data coordinates. Returns its
    GrainShape; silently does nothing for a degenerate (zero-area) extent.
    """
    x0, x1, y0, y1 = extent
    if x1 <= x0 or y1 <= y0:
        return None
    layer = GrainLayer.of(ax)
    path = patch.get_patch_transform().transform_path(patch.get_path())
    return layer.add(path, extent, _texture_noise(layer, seed), _grain_colours(base_color))


def validate_figsize(figsize, dpi: float) -> None:
    """
    Raise a clear ValueError if `figsize` isn't a (positive, positive)
    pair of finite numbers, or `dpi` isn't positive and finite.

    Every chart in this package computes its whole layout in pixels
    (`fig_w_px = figsize[0] * dpi`, and so on) before ever calling
    `plt.figure()`, and divides by those pixel values repeatedly while
    solving margins and font sizes. matplotlib itself validates `dpi`
    (a non-positive dpi raises a clean error there), but happily accepts
    a degenerate `figsize` like `(0, 0)` -- which doesn't fail until
    *this* package's own layout math divides by the resulting zero
    pixel dimension, several calls deep, as a raw, unhelpful
    `ZeroDivisionError` rather than a message that names the actual
    problem. Checked directly (not assumed): `bar_chart(figsize=(0, 0))`
    crashed exactly this way before this check existed.
    """
    if (not isinstance(figsize, (tuple, list)) or len(figsize) != 2
            or not all(isinstance(v, (int, float)) for v in figsize)):
        raise ValueError(f"`figsize` must be a (width, height) pair of numbers, got {figsize!r}.")
    w, h = figsize
    if not (np.isfinite(w) and np.isfinite(h)) or w <= 0 or h <= 0:
        raise ValueError(
            f"`figsize` must be a pair of positive, finite numbers (inches); "
            f"got {figsize!r}."
        )
    if not np.isfinite(dpi) or dpi <= 0:
        raise ValueError(f"`dpi` must be a positive, finite number; got {dpi!r}.")


def validate_colors(colors, needed: int, what: str, each_needs_own: bool) -> list:
    """
    Check a `colors` argument the caller passed and return it as a list.

    A single colour string means that one colour (not its characters).
    An empty list is an error. When each item needs its own colour --
    series that only a legend's colour tells apart -- a list shorter than
    `needed` is an error too; otherwise a short list repeats, which is a
    legitimate choice (one colour for every bar, or two alternating).

    Without this, `stacked_area_chart` and multi-series `bar_chart` given
    too few colours stopped halfway through drawing with a bare
    IndexError, and an empty list crashed the other charts with a
    ZeroDivisionError.
    """
    if isinstance(colors, str):
        colors = [colors]
    colors = list(colors)
    if not colors:
        raise ValueError("`colors` is empty: pass at least one colour, or leave it out "
                         "to use the Du Bois palette.")
    if each_needs_own and len(colors) < needed:
        raise ValueError(
            f"`colors` has {len(colors)} colour{'' if len(colors) == 1 else 's'} for {needed} "
            f"{what}; each needs its own, because colour is what tells them apart. Pass at "
            f"least {needed}, or leave `colors` out to use the Du Bois palette."
        )
    return colors


def default_value_format(values) -> str:
    """
    A `str.format` template for labelling `values` when the caller didn't
    choose one: plain numbers with thousands separators, using the fewest
    decimal places (0, 1 or 2) that show every value exactly. Every label
    uses the same precision, so labels line up ("12.60" beside "6.48",
    not "12.6"). Data that needs more than two decimals gets the fewest
    that show every value exactly -- "0.012", "0.0018" -- but no more than
    show about three significant figures of the smallest nonzero value
    (long fractions such as 33.333333 read "33.33"), nor more than four of
    a typical one, the median: energy use in terawatt-hours, published to
    three decimals, reads "11,073" rather than "11,072.753" -- the tiniest
    values, solar power's first years, had been setting the precision for
    all of them.
    Values below 0.0001 or from 1e15 up switch to scientific notation
    ("4.10e-07"): in plain decimals they printed as "0.000000", every one
    of them.

    "Exactly" allows for float32 and similar rounding noise, so
    np.float32(0.1) still counts as one decimal place.
    """
    arr = np.asarray(values, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return '{:,.0f}'
    magnitude = np.abs(arr)
    nonzero = magnitude[magnitude > 0]
    if nonzero.size and (nonzero.max() >= 1e15 or nonzero.min() < 1e-4):
        return '{:.2e}'
    tolerance = 1e-6 * magnitude

    def exact(decimals):
        return bool(np.all(np.abs(arr - np.round(arr, decimals)) <= tolerance))

    for decimals in (0, 1, 2):
        if exact(decimals):
            return '{:,.%df}' % decimals
    # Enough for about three significant figures of the smallest value,
    # and fewer if fewer show every value exactly. (It used to be three
    # significant figures regardless: 0.012 printed as "0.01200".)
    smallest = float(nonzero.min()) if nonzero.size else 1.0
    decimals = int(min(6, max(2, 2 - np.floor(np.log10(smallest)))))
    decimals = next((d for d in range(3, decimals) if exact(d)), decimals)
    typical = float(np.median(nonzero)) if nonzero.size else 1.0
    decimals = min(decimals, int(max(0, 3 - np.floor(np.log10(typical)))))
    return '{:,.%df}' % decimals


def default_value_format_for(values, totals) -> str:
    """
    The default label format for a chart whose values are parts of some
    total (each column of a stacked area chart, each side of a butterfly
    chart, a snake chart's whole scale): `default_value_format(values)`,
    plus a percent sign when every one of those totals is 100 -- give or
    take 2, for rounding -- because then each value really is a
    percentage of its total, whatever the data are.
    """
    fmt = default_value_format(values)
    totals = np.atleast_1d(np.asarray(totals, dtype=float))
    if totals.size and np.all(np.abs(totals - 100) <= 2) and 'e' not in fmt:
        return fmt + '%'
    return fmt


def check_value_format(value_format) -> str:
    """
    Raise a clear error if `value_format` can't format a number, or has
    no placeholder (so every label would read the same), before any
    drawing starts. Returns it unchanged.

    Without this, '{:.0d}' failed deep inside a chart with Python's own
    "Unknown format code 'd' for object of type 'float'", and 'units'
    silently labelled every bar "units".
    """
    if not isinstance(value_format, str):
        raise TypeError(f"`value_format` must be a str.format template such as '{{:,.0f}}' "
                        f"or '{{:.1f}}%'; got {value_format!r}.")
    try:
        first, second = value_format.format(1234.5), value_format.format(-0.25)
    except (ValueError, IndexError, KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"`value_format` {value_format!r} can't format a number ({e}). "
                         f"Use a template such as '{{:,.0f}}', '{{:.1f}}%' or '${{:,.2f}}'.") from None
    if first == second:
        raise ValueError(f"`value_format` {value_format!r} has no {{}} placeholder for the "
                         f"number, so every label would read {first!r}.")
    return value_format


def fit_label_column(fig, labels, max_width_px: float, row_height_px: float, font,
                     sizes=(12.5, 11.5, 10.5, 9.5, 8.5, 8.0)):
    """
    One shared font size, and the line breaks, for a column of category
    labels (bar_chart's, butterfly_chart's middle column): the largest size
    at which every label fits `max_width_px` on as many lines as its row
    has room for, without breaking a word.

    The old order was shrink first, wrap only below 8pt, so one long name
    took every label on the chart down to 8pt; now that one name wraps and
    the rest stay full size. Only when nothing fits even at the smallest
    size does a label break mid-word, or -- if its row is too short for
    the lines it needs -- end in an ellipsis.

    Returns (fontsize, {label: [lines]}).
    """
    from dubois_charts import text_utils as tu
    unique = list(dict.fromkeys(labels))

    def lines_that_fit(fs):
        line_h = tu.measure_text_px(fig, 'Xg', fs, font, 'bold')[1]
        if not line_h:
            return 1
        # A size whose single line is taller than the row doesn't fit at
        # all. (This used to allow one line regardless, so 200 bars in
        # 16px rows got 12.5pt labels, 26px tall, printed over each other.)
        if line_h > 0.95 * row_height_px:
            return 0
        # block of k lines: one line's height plus 1.2 line-heights per extra line
        return int((0.95 * row_height_px / line_h - 1) / 1.2) + 1

    for fs in sizes:
        allowed = lines_that_fit(fs)
        wrapped = {}
        for lbl in unique:
            lines = tu.wrap_text_to_width(fig, lbl, max_width_px, fs, font, 'bold')
            if len(lines) > allowed or ' '.join(lines).split() != lbl.split():
                break
            wrapped[lbl] = lines
        else:
            return fs, wrapped
    fs = sizes[-1]
    allowed = max(1, lines_that_fit(fs))
    return fs, {lbl: tu.wrap_text_to_width(fig, lbl, max_width_px, fs, font, 'bold', max_lines=allowed)
                for lbl in unique}


def title_top(fig) -> float:
    """
    Where a chart's title starts, as a figure fraction: 1% of the height
    below the top edge, but never more than 0.09 inches. Titles used to
    start at a flat 0.99, which on a tall figure -- a 200-bar chart is 31
    inches -- put the title 47px down, past the room reserved for it and
    over the top of the chart.
    """
    height_px = fig.get_figheight() * fig.dpi
    return 1 - min(0.01 * height_px, 0.09 * fig.dpi) / height_px if height_px else 0.99


def rows_to_label(n: int, row_px: float, line_px: float) -> List[int]:
    """
    Which of `n` stacked rows, each `row_px` tall, get a label `line_px`
    tall: all of them when a label fits its row, otherwise every k-th row
    -- the fewest skipped that keeps labels from overlapping -- always
    including the first and the last (the top and bottom of a ranking).
    The value labels beside the bars follow the same rows.
    """
    if n <= 0:
        return []
    if row_px <= 0:
        return [0]
    if line_px <= 0.95 * row_px:
        return list(range(n))
    k = math.ceil(line_px / (0.95 * row_px))
    kept = list(range(0, n, k))
    if kept[-1] != n - 1:
        if len(kept) > 1 and (n - 1) - kept[-1] < k:
            kept.pop()
        kept.append(n - 1)
    return kept


def largest_size_that_fits(fig, font, height_px: float, sizes=(11, 10, 9, 8)) -> Optional[float]:
    """The largest of `sizes` whose line of text fits `height_px`, or None."""
    from dubois_charts import text_utils as tu
    for fs in sizes:
        if tu.measure_text_px(fig, 'Xg', fs, font, 'bold')[1] <= 0.95 * height_px:
            return fs
    return None


def shared_size_fallback(trials, comfortable: float = 10.0):
    """
    The labels to draw when no font size fits most of a chart's shape
    names inside their shapes (area bands, snake segments). `trials` is
    [(fontsize, {index: placement})], largest size first, one for every
    size tried.

    The size that fits the most names, of those from `comfortable` up --
    the largest such size, if several tie. The names that only fit
    smaller go to the legend. Only when no name fits at a comfortable
    size does a smaller one get used.

    (These charts used to take the smallest size whenever most names
    didn't fit: two slivers of a snake, or the thin bands of an area chart,
    took every name down to 7 or 8pt, though most of them never fit at any
    size -- and a band filling most of the chart was named in tiny type.)
    """
    pool = [r for fs, r in trials if fs >= comfortable]
    if not pool or not max(len(r) for r in pool):
        pool = [r for _, r in trials]
    most = max(len(r) for r in pool)
    return next(r for r in pool if len(r) == most)


LEGEND_SIZES = (10.0, 9.5, 9.0, 8.5, 8.0)


def legend_columns(fig, names: Sequence[str], max_width_px: float, fontsize: float, font):
    """
    How a legend of these names fits `max_width_px` at this font size:
    (columns, names), the most columns that fit with the entries read
    across each row and then down, and each name too long for a line of
    its own broken onto more lines.
    """
    from dubois_charts import text_utils as tu
    em = fontsize * fig.dpi / 72
    handle = (2.0 + 0.8) * em           # matplotlib's handlelength and handletextpad
    spacing, pad = 2.0 * em, 0.8 * em   # its columnspacing; borderpad on both sides
    room = max(max_width_px - handle - pad, em)
    names = ['\n'.join(tu.wrap_text_to_width(fig, name, room, fontsize, font, 'bold'))
             if tu.measure_text_px(fig, name, fontsize, font, 'bold')[0] > room else name
             for name in names]
    widths = [handle + max(tu.measure_text_px(fig, line, fontsize, font, 'bold')[0]
                           for line in name.split('\n'))
              for name in names]
    for ncol in range(len(names), 1, -1):
        if sum(max(widths[c::ncol]) for c in range(ncol)) + spacing * (ncol - 1) + pad <= max_width_px:
            return ncol, names
    return 1, names


def add_legend(fig, entries, ink_color: str, font, max_width_px: float,
               max_height_px: float = math.inf, sizes=LEGEND_SIZES):
    """
    A legend at the bottom of the figure: a swatch and a name for each of
    `entries`, (name, colour) pairs, read across each row and then down in
    the order given. It takes as many columns as `max_width_px` has room
    for, and the largest of `sizes` at which it's no taller than
    `max_height_px` (or the smallest). A name too long for a line of its
    own is broken onto more lines. An entry whose colour is None has no
    swatch ("+ 12 more").

    Returns the legend, and how far above the bottom of the figure its
    text reaches, in pixels (the top of the legend's box, less the
    padding inside it).

    (matplotlib fills a legend's columns one at a time, so with six entries
    in four columns they read 1, 3, 5, 6 / 2, 4. Legends also used to have
    a fixed four columns and a fixed row's room, so long names ran off
    both sides of the figure and a second row sat on top of the chart.)
    """
    import matplotlib.patches as mpatches
    from dubois_charts import text_utils as tu
    renderer = tu.get_renderer(fig)
    legend = top = None
    for fs in sizes:
        if legend is not None:
            legend.remove()
        ncol, names = legend_columns(fig, [name for name, _ in entries], max_width_px, fs, font)
        rows = -(-len(entries) // ncol)
        order = [r * ncol + c for c in range(ncol) for r in range(rows) if r * ncol + c < len(entries)]
        handles = [mpatches.Patch(facecolor=entries[i][1] or 'none', linewidth=0.8,
                                  edgecolor=ink_color if entries[i][1] is not None else 'none',
                                  label=names[i]) for i in order]
        legend = fig.legend(handles=handles, loc='lower center', ncol=ncol, frameon=False,
                            prop={'family': font, 'weight': 'bold', 'size': fs},
                            labelcolor=ink_color, bbox_to_anchor=(0.5, 0.0))
        top = legend.get_window_extent(renderer).y1 - legend.borderpad * fs * fig.dpi / 72
        if top <= max_height_px:
            break
    return legend, top


_FORMATTER = string.Formatter()


@functools.lru_cache(maxsize=256)
def _rounds_like_people(value_format: str) -> bool:
    """Whether every field of `value_format` is a fixed-point or percent
    one ('f', 'F', '%') -- where Python's round-half-to-even shows."""
    try:
        specs = [spec for _, name, spec, conv in _FORMATTER.parse(value_format)
                 if name is not None]
    except ValueError:
        return False
    return bool(specs) and all(spec and spec[-1] in 'fF%' and '{' not in spec for spec in specs)


def format_value(value_format: str, value: float) -> str:
    """
    `value_format.format(value)`, but with halves rounded up, as people
    round them: 4.5 to the nearest whole number is "5", 1,102,866.5 is
    "1,102,867". Python rounds to the nearest even digit -- "4",
    "1,102,866" -- so a pie's 4.5% read "4%" beside a bar's "4.5%", and
    the shares on it added up to 99%. The number is taken as written
    (2.675 is 2.675, not the binary fraction just below it), and formats
    other than fixed-point and percent ('{:g}', '{:.2e}') are left to
    Python.
    """
    if _rounds_like_people(value_format) and not isinstance(value, (bool, np.bool_)):
        try:
            number = Decimal(repr(float(value)))
        except (TypeError, ValueError, InvalidOperation, OverflowError):
            number = None
        if number is not None and number.is_finite():
            with localcontext() as context:
                context.rounding = ROUND_HALF_UP
                context.prec = 60
                try:
                    return value_format.format(number)
                except (ValueError, TypeError):
                    pass
    return value_format.format(value)


def format_nonzero(value_format: str, value: float) -> str:
    """
    Format `value` with `value_format`, except that a positive value never
    prints exactly like zero: if it would, show "<" followed by the
    smallest positive amount the format can display -- "<1%" for
    '{:.0f}%', "<0.1%" for '{:.1f}%'. A true zero still prints as zero.

    Found on real data: global mobile OS share (Android 72.77%, iOS
    26.82%, Other 0.41%) drew a visible "Other" wedge labelled
    "Other 0%", which reads as a contradiction.
    """
    text = format_value(value_format, value)
    zero_text = format_value(value_format, 0.0)
    if not value > 0 or text != zero_text:
        return text
    smallest, unit = None, 1.0
    for _ in range(12):
        if format_value(value_format, unit) == zero_text:
            break
        smallest, unit = unit, unit / 10
    return text if smallest is None else '<' + format_value(value_format, smallest)


def number_text(value_format: str, value: float) -> str:
    """
    A value as its label prints it: `format_nonzero`, with no-break spaces,
    so that where a label wraps, a number never loses its unit to the next
    line ("152" / "€").
    """
    return format_nonzero(value_format, value).replace(' ', '\u00a0')


_CAPS_TOKEN = re.compile(r"[^\s\-/]+")


def display_caps(text: str) -> str:
    """
    Capitalise text for the poster lettering used in titles, butterfly
    headers and area band names -- except words whose mixed case is
    deliberate, which are left exactly as written: "iOS", "eBay",
    "McDonald's", "DeKalb", "kWh". A word counts as deliberately mixed
    if it has a lowercase letter and also a capital somewhere after its
    first letter. Ordinary words ("Male", "android", "Natural Gas",
    "Kraków") are capitalised as before. Words are split on spaces,
    hyphens and slashes, so "Coca-Cola" still becomes "COCA-COLA".

    Found on real data: butterfly_chart's headers turned "iOS" into
    "IOS", while pie_chart, which doesn't force capitals, kept "iOS" --
    the same name spelled two ways depending on the chart type.
    """
    def _caps(match):
        word = match.group(0)
        letters = [c for c in word if c.isalpha()]
        deliberate = (any(c.islower() for c in letters)
                      and any(c.isupper() for c in letters[1:]))
        return word if deliberate else word.upper()
    return _CAPS_TOKEN.sub(_caps, text)
