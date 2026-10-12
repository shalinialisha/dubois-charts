"""
Matplotlib Themes Inspired by W.E.B. Du Bois

This module provides matplotlib style configurations that replicate
the aesthetic of Du Bois's original data visualizations.

Design Principles:
------------------
- Bold, saturated colors from a limited palette
- Clean, minimal styling
- Hand-drawn aesthetic (slightly irregular lines)
- Emphasis on data over decoration
- Typography inspired by turn-of-century design
- Generous whitespace
"""

import matplotlib as mpl
from typing import Dict
from dubois_charts import colors as dubois_colors


# Du Bois theme parameters
#
# The cream background below is the same #ded7c9 used throughout
# dubois_charts.charts (see dubois_charts/charts/_common.py's COLOR_CREAM) -- pixel-
# sampled from the actual Plate 51 scan rather than guessed. This module
# predates that verification work and originally used a generic, unverified
# "#F5F5DC" CSS beige; kept as a literal here (rather than importing
# _common.COLOR_CREAM) to avoid adding a cross-package import between
# sibling top-level modules for a single shared constant.
DUBOIS_THEME = {
    # Figure
    'figure.facecolor': '#ded7c9',      # Beige/cream background
    'figure.edgecolor': 'none',
    'figure.dpi': 100,
    
    # Axes
    'axes.facecolor': '#ded7c9',        # Match figure background
    'axes.edgecolor': '#000000',        # Black borders
    'axes.linewidth': 1.5,              # Slightly heavier lines
    'axes.grid': False,                 # No grid by default
    'axes.axisbelow': True,             # Grid behind data
    'axes.labelsize': 11,
    'axes.labelweight': 'normal',
    'axes.labelcolor': '#000000',
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.titlepad': 15,
    'axes.spines.left': True,
    'axes.spines.bottom': True,
    'axes.spines.top': False,           # No top spine
    'axes.spines.right': False,         # No right spine
    
    # Color cycle - Du Bois categorical palette. The twenty-colour version
    # starts with the same eight, so the first eight lines of a plot are
    # coloured exactly as before; lines nine to twenty used to repeat them.
    'axes.prop_cycle': mpl.cycler(color=dubois_colors.DUBOIS_CATEGORICAL_20),
    
    # Grid
    'grid.color': '#CCCCCC',
    'grid.linestyle': '-',
    'grid.linewidth': 0.5,
    'grid.alpha': 0.5,
    
    # Ticks
    'xtick.major.size': 6,
    'xtick.minor.size': 3,
    'xtick.major.width': 1.0,
    'xtick.minor.width': 0.5,
    'xtick.direction': 'out',
    'xtick.color': '#000000',
    'xtick.labelsize': 10,
    
    'ytick.major.size': 6,
    'ytick.minor.size': 3,
    'ytick.major.width': 1.0,
    'ytick.minor.width': 0.5,
    'ytick.direction': 'out',
    'ytick.color': '#000000',
    'ytick.labelsize': 10,
    
    # Lines
    'lines.linewidth': 2.5,             # Thicker lines like hand-drawn
    'lines.markersize': 8,
    'lines.markeredgewidth': 0,
    'lines.solid_capstyle': 'round',    # Rounded line caps
    
    # Patches (bars, etc.)
    'patch.linewidth': 1.0,
    'patch.facecolor': dubois_colors.crimson,
    'patch.edgecolor': '#000000',
    'patch.force_edgecolor': True,
    
    # Font
    'font.family': 'serif',
    'font.serif': ['Georgia', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    
    # Legend
    'legend.frameon': True,
    'legend.framealpha': 1.0,
    'legend.facecolor': '#ded7c9',
    'legend.edgecolor': '#000000',
    'legend.fancybox': False,
    'legend.fontsize': 9,
    'legend.title_fontsize': 10,
    
    # Saving
    'savefig.dpi': 300,
    'savefig.facecolor': '#ded7c9',
    'savefig.edgecolor': 'none',
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
}

# Alternative theme with white background (more modern)
DUBOIS_MODERN = {
    **DUBOIS_THEME,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'legend.facecolor': 'white',
    'savefig.facecolor': 'white',
}

# Minimalist theme (even cleaner)
DUBOIS_MINIMAL = {
    **DUBOIS_THEME,
    'axes.spines.left': False,
    'axes.spines.bottom': False,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
}


_THEMES = {'classic': DUBOIS_THEME, 'modern': DUBOIS_MODERN, 'minimal': DUBOIS_MINIMAL}
_SCALES = {'notebook': 1.0, 'paper': 0.8, 'talk': 1.3, 'poster': 1.6}
_FONT_SIZES = ('font.size', 'axes.labelsize', 'axes.titlesize', 'xtick.labelsize',
               'ytick.labelsize', 'legend.fontsize', 'legend.title_fontsize')


def _theme_settings(theme: str, context: str) -> Dict:
    """The rcParams a theme sets in a context: its own, with the font
    sizes scaled by the context, and the line widths by its square root."""
    if theme not in _THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Choose from: {list(_THEMES)}")
    if context not in _SCALES:
        raise ValueError(f"Unknown context '{context}'. Choose from: {list(_SCALES)}")
    settings = dict(_THEMES[theme])
    scale = _SCALES[context]
    if scale != 1.0:
        for key in _FONT_SIZES:
            settings[key] = settings[key] * scale
        for key in ('lines.linewidth', 'axes.linewidth'):
            settings[key] = settings[key] * scale ** 0.5
    return settings


# What set_theme() changed, as it was before: {setting: value}. Only these
# go back on reset_theme(). (Every setting used to be saved and put back,
# which undid any setting of the user's own made in between, and switched
# off the interactive mode matplotlib turns on for a notebook's first
# figure, so a notebook showed no more figures.)
_original_params = None


def set_theme(theme: str = 'classic', context: str = 'notebook') -> None:
    """
    Apply a Du Bois-inspired theme to matplotlib.
    
    This function modifies matplotlib's global rcParams to match the
    aesthetic of W.E.B. Du Bois's data visualizations.
    
    Parameters
    ----------
    theme : str
        Theme variant to apply. Options:
        - 'classic': Cream background, traditional Du Bois aesthetic (default)
        - 'modern': White background, cleaner modern interpretation
        - 'minimal': Ultra-minimal, no spines or ticks
    context : str
        Context for scaling. Options:
        - 'notebook': For Jupyter notebooks (default)
        - 'paper': For publications
        - 'talk': For presentations
        - 'poster': For large posters
    
    Examples
    --------
    >>> import dubois_charts as dc
    >>> dc.set_theme()  # Apply classic Du Bois theme
    >>> dc.set_theme('modern', 'talk')  # Modern theme for presentations
    
    Notes
    -----
    This changes matplotlib's settings for every plot that follows, not
    only this package's charts. reset_theme() puts them back.
    """
    global _original_params
    settings = _theme_settings(theme, context)
    if _original_params is None:
        _original_params = {}
    for key in settings:
        _original_params.setdefault(key, mpl.rcParams[key])
    mpl.rcParams.update(settings)


def reset_theme() -> None:
    """
    Undo set_theme(): put back every setting it changed -- however many
    times it was called -- as it was before the first call. Settings it
    doesn't change are left alone, including any changed since. Does
    nothing if set_theme() hasn't been called.

    Examples
    --------
    >>> import dubois_charts as dc
    >>> dc.set_theme()
    >>> # ... make plots ...
    >>> dc.reset_theme()  # Restore the settings from before set_theme()
    """
    global _original_params

    if _original_params:
        mpl.rcParams.update(_original_params)
    _original_params = None


def list_themes() -> list:
    """
    List available Du Bois themes.
    
    Returns
    -------
    list
        List of available theme names
    
    Examples
    --------
    >>> import dubois_charts as dc
    >>> dc.list_themes()
    ['classic', 'modern', 'minimal']
    """
    return list(_THEMES)


def get_theme_params(theme: str = 'classic') -> Dict:
    """
    Get the rcParams dictionary for a theme without applying it.
    
    Useful for inspecting or modifying theme parameters before applying.
    
    Parameters
    ----------
    theme : str
        Theme name
    
    Returns
    -------
    Dict
        Dictionary of matplotlib rcParams
    
    Examples
    --------
    >>> import dubois_charts as dc
    >>> params = dc.themes.get_theme_params('classic')
    >>> params['figure.facecolor']
    '#ded7c9'
    """
    if theme not in _THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Choose from: {list(_THEMES)}")
    return dict(_THEMES[theme])


def dubois_style():
    """
    The classic theme for one block of code only: `with dubois_style():`.
    Same as `DuBoisStyle()`.

    Examples
    --------
    >>> import dubois_charts as dc
    >>> import matplotlib.pyplot as plt
    >>> with dc.themes.dubois_style():
    ...     lines = plt.plot([1, 2, 3], [1, 2, 3])
    """
    return DuBoisStyle()


class DuBoisStyle:
    """
    A theme for one block of code only: `with DuBoisStyle('modern', 'talk'):`.
    Takes the same arguments as set_theme(); on leaving the block, the
    settings it changed are put back as they were, and no others.

    Parameters
    ----------
    theme : str
        'classic', 'modern' or 'minimal'.
    context : str
        'notebook', 'paper', 'talk' or 'poster'.

    Examples
    --------
    >>> import dubois_charts as dc
    >>> import matplotlib.pyplot as plt
    >>> with dc.themes.DuBoisStyle('modern', 'talk'):
    ...     lines = plt.plot([1, 2, 3], [1, 2, 3])
    """

    def __init__(self, theme: str = 'classic', context: str = 'notebook'):
        self.theme = theme
        self.context = context
        self.original_params = None

    def __enter__(self):
        settings = _theme_settings(self.theme, self.context)
        self.original_params = {key: mpl.rcParams[key] for key in settings}
        mpl.rcParams.update(settings)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_params is not None:
            mpl.rcParams.update(self.original_params)
            self.original_params = None


__all__ = [
    # Theme dictionaries
    'DUBOIS_THEME',
    'DUBOIS_MODERN',
    'DUBOIS_MINIMAL',
    # Functions
    'set_theme',
    'reset_theme',
    'list_themes',
    'get_theme_params',
    'dubois_style',
    # Classes
    'DuBoisStyle',
]
