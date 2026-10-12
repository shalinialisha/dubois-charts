"""
dubois-charts: data visualization in the style of W.E.B. Du Bois
=================================================================

A Python package for charting your own data in the style of W.E.B. Du
Bois's groundbreaking data portraits for the 1900 Paris Exposition.

Quick Start
-----------
Every chart takes your data and returns a matplotlib Figure:

>>> import dubois_charts as dc
>>> fig = dc.bar_chart(
...     categories=['Agriculture', 'Trade', 'Professions'],
...     values=[45, 25, 8],
...     title='Occupations',
...     value_format='{:.0f}%',
... )
>>> fig.savefig('occupations.png')       # doctest: +SKIP

The colors, and a matplotlib theme for charts of your own:

>>> dc.colors.crimson
'#DC143C'
>>> palette = dc.get_categorical(4)
>>> dc.set_theme()
>>> dc.reset_theme()

Modules
-------
colors
    Color palettes and color utilities
themes
    Matplotlib style themes inspired by Du Bois
charts
    Eight general-purpose chart types that take your own data --
    bar_chart, stacked_area_chart, butterfly_chart, spiral_chart,
    snake_chart, pie_chart, county_map_chart and state_map_chart -- plus
    the pixel-verified Plate 51 historical recreation
    (dubois_charts.charts.plate51)
text_utils
    Shared text-measurement and layout-fitting utilities used by every
    chart type in `charts`, so titles, category labels, and value labels
    of any length get sized and wrapped correctly rather than hardcoded

Historical Context
------------------
W.E.B. Du Bois and his team at Atlanta University created 63 innovative
data visualizations for the "American Negro" exhibit at the 1900 Paris
Exposition. These hand-painted charts used bold colors, creative chart
types, and compelling narratives to challenge racist assumptions and
demonstrate Black American progress since emancipation.

More information:
- Library of Congress Collection: https://www.loc.gov/collections/african-american-photographs-1900-paris-exposition/
- #DuBoisChallenge: https://github.com/ajstarks/dubois-data-portraits
"""

__version__ = '0.2.0'
__author__ = 'shalinialisha'

# Import main modules
from dubois_charts import colors
from dubois_charts import themes
from dubois_charts import charts

# Import key functions for convenience
from dubois_charts.themes import set_theme, reset_theme, list_themes
from dubois_charts.colors import (
    get_palette,
    get_sequential,
    get_categorical,
    get_diverging,
    set_colorblind_safe,
    simulate_colorblindness,
)
from dubois_charts.charts import (stacked_area_chart, bar_chart, butterfly_chart, spiral_chart,
                                  snake_chart, pie_chart, county_map_chart, state_map_chart)

# Define what gets imported with "from dubois_charts import *"
__all__ = [
    # Version info
    '__version__',
    # Modules
    'colors',
    'themes',
    'charts',
    # Key functions
    'set_theme',
    'reset_theme',
    'list_themes',
    'get_palette',
    'get_sequential',
    'set_colorblind_safe',
    'simulate_colorblindness',
    'get_categorical',
    'get_diverging',
    # Chart types
    'stacked_area_chart',
    'bar_chart',
    'butterfly_chart',
    'spiral_chart',
    'snake_chart',
    'pie_chart',
    'county_map_chart',
    'state_map_chart',
]
