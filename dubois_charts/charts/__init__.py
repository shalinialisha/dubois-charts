"""
dubois_charts.charts: Du Bois-styled chart types.

General-purpose (take your own data):
    bar_chart            -- dubois_charts.charts.bar
    stacked_area_chart   -- dubois_charts.charts.area
    butterfly_chart      -- dubois_charts.charts.butterfly
    spiral_chart         -- dubois_charts.charts.spiral
    snake_chart          -- dubois_charts.charts.snake
    pie_chart            -- dubois_charts.charts.pie
    county_map_chart     -- dubois_charts.charts.choropleth
    state_map_chart      -- dubois_charts.charts.choropleth

Historical reference (fixed data, pixel-verified against the original):
    plate51.create_plate_51, plate51.create_side_by_side

See GENERAL_ENGINE_README.md in this directory for why the general-purpose
functions are built the way they are, and PLATE51_README.md for how the
historical recreation was verified.
"""

from dubois_charts.charts.area import stacked_area_chart
from dubois_charts.charts.bar import bar_chart
from dubois_charts.charts.butterfly import butterfly_chart
from dubois_charts.charts.spiral import spiral_chart
from dubois_charts.charts.snake import snake_chart
from dubois_charts.charts.pie import pie_chart
from dubois_charts.charts.choropleth import county_map_chart, state_map_chart
from dubois_charts.charts import plate51

__all__ = [
    'stacked_area_chart',
    'bar_chart',
    'butterfly_chart',
    'spiral_chart',
    'snake_chart',
    'pie_chart',
    'county_map_chart',
    'state_map_chart',
    'plate51',
]
