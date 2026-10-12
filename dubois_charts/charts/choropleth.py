"""
Du Bois-style choropleth maps: a U.S. state's counties (Georgia's by
default) or the whole country's (`county_map_chart`), and the country by
state (`state_map_chart`).

Same relationship to the general-purpose chart engine described in
GENERAL_ENGINE_README.md, but the shape of the problem is different
again from anything else in the package: every other chart type lays
out shapes it computes itself (rectangles, wedges, a parametric
spiral), so it always knows exactly what geometry it's dealing with.
A map's shapes come from the outside world -- 159 real county
boundaries, each an irregular, non-convex, differently-sized polygon
with no formula behind it -- and have to be projected onto a flat
Cartesian plane before anything about layout can even be asked.

This module bundles real boundary files rather than trying to compute
geography, the same way `plate51.py` bundles a real scanned image rather
than trying to compute history: `data/georgia_counties.geojson`, trimmed
from the U.S. Census county boundaries used in `plotly/datasets`, for
Georgia, and `data/us-counties-10m.json` -- us-atlas's TopoJSON of the
Census's 2017 cartographic county boundaries, licence alongside it --
for every other state and territory, and for the whole country -- its
states as well as its counties -- laid out as d3-geo's Albers USA
projection does, with Alaska and Hawaii inset.

Choropleths conventionally bin values into a handful of discrete color
classes rather than a smooth gradient (easier to read, easier to
reproduce in print) -- that convention is followed here, and happens to
suit the package's hand-tinted aesthetic well.
"""

import functools
import json
import os
import re
import unicodedata
import warnings
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as patheffects
from matplotlib.path import Path as MplPath

from dubois_charts import colors as dubois_colors
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import (
    COLOR_CREAM,
    get_font as _get_font,
    text_color_for as _text_color_for,
    validate_figsize,
    display_caps,
    literal_text,
    font_stack,
    category_labels,
    named_labels,
    as_numbers,
    is_missing,
    format_value,
    check_value_format,
    title_top,
)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# The fill for places with no value: a light, cool gray, at least 12.9
# apart in CIEDE2000 from every class of every palette's maps (two to eight
# classes) -- for readers with normal vision and with each kind of
# colour-blindness. The warm gray it replaced (#c9c2b4), about as light,
# was 1.1 apart from one of a seven-class crimson map's pinks as a
# deuteranope sees them: "no data" and a value looked the same.
MISSING_COLOR = '#C1BFD0'
# ... except on a diverging map for colour-blind readers, whose pale blues
# are as near the light gray as 4.7 for some readers: there, a dark cool
# gray, at least 14.8 apart from every class.
MISSING_COLOR_BESIDE_BLUE = '#5A5C60'
_DEFAULT_GEOJSON_PATH = os.path.join(_MODULE_DIR, 'data', 'georgia_counties.geojson')


def _normalize_name(name: str) -> str:
    """Loosely normalize a county name for matching against real-world
    input data, which can spell things a dozen slightly different ways
    ('DeKalb', 'De Kalb', 'Dekalb County', 'DEKALB', the Census's
    'DeKalb County, Georgia', 'Saint Louis' for 'St. Louis', 'Dona Ana'
    for 'Doña Ana')."""
    n = name.split(',')[0].strip().lower()
    n = ''.join(ch for ch in unicodedata.normalize('NFKD', n) if not unicodedata.combining(ch))
    n = re.sub(r'\bsainte\b', 'ste', re.sub(r'\bsaint\b', 'st', n))
    for suffix in (' city and borough', ' county', ' parish', ' borough', ' census area',
                   ' municipality', ' municipio', ' co.', ' co'):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    return ''.join(ch for ch in n if ch.isalnum())


_US_COUNTIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data',
                                 'us-counties-10m.json')

# FIPS code -> (postal code, name), for every state and territory in the
# bundled county boundaries.
STATES = {
    '01': ('AL', 'Alabama'), '02': ('AK', 'Alaska'), '04': ('AZ', 'Arizona'),
    '05': ('AR', 'Arkansas'), '06': ('CA', 'California'), '08': ('CO', 'Colorado'),
    '09': ('CT', 'Connecticut'), '10': ('DE', 'Delaware'), '11': ('DC', 'District of Columbia'),
    '12': ('FL', 'Florida'), '13': ('GA', 'Georgia'), '15': ('HI', 'Hawaii'),
    '16': ('ID', 'Idaho'), '17': ('IL', 'Illinois'), '18': ('IN', 'Indiana'),
    '19': ('IA', 'Iowa'), '20': ('KS', 'Kansas'), '21': ('KY', 'Kentucky'),
    '22': ('LA', 'Louisiana'), '23': ('ME', 'Maine'), '24': ('MD', 'Maryland'),
    '25': ('MA', 'Massachusetts'), '26': ('MI', 'Michigan'), '27': ('MN', 'Minnesota'),
    '28': ('MS', 'Mississippi'), '29': ('MO', 'Missouri'), '30': ('MT', 'Montana'),
    '31': ('NE', 'Nebraska'), '32': ('NV', 'Nevada'), '33': ('NH', 'New Hampshire'),
    '34': ('NJ', 'New Jersey'), '35': ('NM', 'New Mexico'), '36': ('NY', 'New York'),
    '37': ('NC', 'North Carolina'), '38': ('ND', 'North Dakota'), '39': ('OH', 'Ohio'),
    '40': ('OK', 'Oklahoma'), '41': ('OR', 'Oregon'), '42': ('PA', 'Pennsylvania'),
    '44': ('RI', 'Rhode Island'), '45': ('SC', 'South Carolina'), '46': ('SD', 'South Dakota'),
    '47': ('TN', 'Tennessee'), '48': ('TX', 'Texas'), '49': ('UT', 'Utah'),
    '50': ('VT', 'Vermont'), '51': ('VA', 'Virginia'), '53': ('WA', 'Washington'),
    '54': ('WV', 'West Virginia'), '55': ('WI', 'Wisconsin'), '56': ('WY', 'Wyoming'),
    '60': ('AS', 'American Samoa'), '66': ('GU', 'Guam'), '69': ('MP', 'Northern Mariana Islands'),
    '72': ('PR', 'Puerto Rico'), '78': ('VI', 'U.S. Virgin Islands'),
}
_STATE_ALIASES = {'washingtondc': '11', 'dc': '11', 'virginislands': '78',
                  'usvirginislands': '78', 'unitedstatesvirginislands': '78'}


def state_fips(state) -> str:
    """
    The two-digit FIPS code of a state or territory given by name
    ('Ohio'), postal code ('OH') or FIPS code (39 or '39').
    """
    key = str(category_labels([state])[0]).strip()
    if key.isdigit() and key.zfill(2) in STATES:
        return key.zfill(2)
    k = ''.join(ch for ch in key.lower() if ch.isalnum())
    for fips, (postal, name) in STATES.items():
        if k == postal.lower() or k == ''.join(ch for ch in name.lower() if ch.isalnum()):
            return fips
    if k in _STATE_ALIASES:
        return _STATE_ALIASES[k]
    raise ValueError(f"`state` {state!r} isn't a U.S. state or territory: give its name ('Ohio'), "
                     f"postal code ('OH') or FIPS code (39).")


@functools.lru_cache(maxsize=1)
def _us_json() -> dict:
    """The bundled TopoJSON, as read."""
    # UTF-8 said outright: Windows reads files in its own code page by
    # default, which turned "Doña Ana" into "DoÃ±a Ana".
    with open(_US_COUNTIES_PATH, encoding='utf-8') as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def _us_topology():
    """The bundled TopoJSON's arcs, decoded to longitude/latitude once,
    and its objects (counties, states, nation)."""
    topo = _us_json()
    (sx, sy), (tx, ty) = topo['transform']['scale'], topo['transform']['translate']
    arcs = []
    for arc in topo['arcs']:
        q = np.cumsum(np.asarray(arc, dtype=float), axis=0)
        arcs.append(np.column_stack([q[:, 0] * sx + tx, q[:, 1] * sy + ty]))
    return arcs, topo['objects']


def _us_arcs():
    """The decoded arcs, and the counties' geometries."""
    arcs, objects = _us_topology()
    return arcs, objects['counties']['geometries']


def _topo_polygons(geometry: dict, arcs) -> List[List[np.ndarray]]:
    """A TopoJSON Polygon or MultiPolygon as polygons, each a list of rings
    (outline first, then holes) of longitude/latitude points; [] for
    anything else. A negative arc index ~i means arc i reversed."""
    def ring(indices):
        parts = [arcs[i] if i >= 0 else arcs[~i][::-1] for i in indices]
        return np.concatenate([parts[0]] + [p[1:] for p in parts[1:]])

    if geometry['type'] == 'Polygon':
        return [[ring(r) for r in geometry['arcs']]]
    if geometry['type'] == 'MultiPolygon':
        return [[ring(r) for r in p] for p in geometry['arcs']]
    return []


def _load_state_counties(fips: str) -> List[dict]:
    """One state's counties (see `_state_counties`), fresh dicts each time:
    the drawing code adds its own keys to them."""
    return [dict(c, aliases=set(c['aliases'])) for c in _state_counties(fips)]


@functools.lru_cache(maxsize=None)
def _state_counties(fips: str) -> Tuple[dict, ...]:
    """
    One state's counties from the bundled Census boundaries (us-atlas's
    2017 cartographic counties), in the shape `_load_counties` gives.

    - Alaska's Aleutians cross 180 degrees: longitudes east of it are
      moved 360 degrees west, so the state isn't drawn across the globe.
    - The boundaries name counties without "County" or "city", so the
      four places where a county and an independent city share a name
      (Baltimore, St. Louis, and Virginia's Fairfax, Franklin, Richmond
      and Roanoke) become "Baltimore County" and "Baltimore City".
      Data can call the cities "... city", as the Census does.
    """
    arcs, geometries = _us_arcs()
    raw = []
    for g in geometries:
        if not str(g.get('id', '')).startswith(fips):
            continue
        polygons = _topo_polygons(g, arcs)
        if polygons:
            raw.append((str(g['id']), g.get('properties', {}).get('name', str(g['id'])), polygons))
    lons = np.concatenate([r[:, 0] for _, _, polys in raw for poly in polys for r in poly])
    shift = lons.max() - lons.min() > 180
    names = Counter(name for _, name, _ in raw)
    counties = []
    for geoid, name, polygons in raw:
        if shift:
            polygons = [[np.column_stack([np.where(r[:, 0] > 0, r[:, 0] - 360, r[:, 0]), r[:, 1]])
                         for r in poly] for poly in polygons]
        display, aliases = _county_names(geoid, name, names)
        counties.append({
            'name': display,
            'rings': [poly[0].tolist() for poly in polygons],
            'holes': [h.tolist() for poly in polygons for h in poly[1:]],
            'geoid': geoid,
            'countyfp': geoid[2:],
            'aliases': aliases,
        })
    return tuple(counties)


_CITY_STATES = ('24', '29', '32', '51')     # where independent cities are county equivalents


def _county_names(geoid: str, name: str, names_in_state: Counter):
    """A bundled county's name as drawn, and the names data can call it
    by: "Baltimore County" and "Baltimore City" where a county and an
    independent city share a name, and "Baltimore city" too, as the
    Census writes it."""
    is_city = geoid[:2] in _CITY_STATES and int(geoid[2:]) >= 500
    display = (f'{name} City' if is_city else f'{name} County') if names_in_state[name] > 1 else name
    aliases = {_normalize_name(display)}
    if is_city:
        aliases.add(_normalize_name(f'{name} city'))
    return display, aliases


@functools.lru_cache(maxsize=1)
def _county_name_states() -> Dict[str, frozenset]:
    """Every name a bundled county can be called by, as data are matched
    (`_normalize_name`), -> the states that have a county of that name.
    Read from the boundary file's names alone; no boundaries are decoded."""
    by_state: Dict[str, list] = {}
    for g in _us_json()['objects']['counties']['geometries']:
        geoid = str(g.get('id', ''))
        by_state.setdefault(geoid[:2], []).append((geoid, g.get('properties', {}).get('name', geoid)))
    found: Dict[str, set] = {}
    for fips, entries in by_state.items():
        names = Counter(name for _, name in entries)
        for geoid, name in entries:
            for alias in _county_names(geoid, name, names)[1]:
                found.setdefault(alias, set()).add(fips)
    return {alias: frozenset(states) for alias, states in found.items()}


def _states_with_counties(keys: Sequence[str]) -> Optional[set]:
    """The states that have a county by every one of these names -- or
    None when a key isn't a plain name (a FIPS code, or a name with its
    state), and there's nothing to work out."""
    if not keys or any(_county_code(k) or _split_state(k)[1] for k in keys):
        return None
    index = _county_name_states()
    states = None
    for key in keys:
        have = index.get(_normalize_name(key), frozenset())
        states = set(have) if states is None else states & have
    return states


# ---------------------------------------------------------------------------
# The whole country: every state, or every county, on one map.
# ---------------------------------------------------------------------------

def _conic_equal_area(parallels, rotate: float, center):
    """
    Albers' conic equal-area projection as d3-geo has it: standard
    parallels `parallels` (degrees), the globe turned `rotate` degrees of
    longitude first, and `center` (longitude and latitude in the turned
    globe) at the origin. Returns a function of longitude and latitude
    arrays, in degrees, to x and y in units of the earth's radius.
    """
    p0, p1 = math.radians(parallels[0]), math.radians(parallels[1])
    s0 = math.sin(p0)
    n = (s0 + math.sin(p1)) / 2
    c = 1 + s0 * (2 * n - s0)
    r0 = math.sqrt(c) / n

    def raw(lam, phi):
        r = np.sqrt(c - 2 * n * np.sin(phi)) / n
        return r * np.sin(lam * n), r0 - r * np.cos(lam * n)

    cx, cy = raw(math.radians(center[0]), math.radians(center[1]))

    def project(lon, lat):
        lam = np.radians((np.asarray(lon, dtype=float) + rotate + 180.0) % 360.0 - 180.0)
        x, y = raw(lam, np.radians(np.asarray(lat, dtype=float)))
        return x - cx, y - cy

    return project


# How the country is laid out, as d3-geo's geoAlbersUsa does it: the lower
# 48 states in Albers' projection, Alaska (at 35% scale, or it would be
# a third of the map) and Hawaii inset below California and Arizona, and
# Puerto Rico -- placed as d3-composite-projections does -- off Florida.
# (projection, scale, offset), in units of the lower 48's scale.
_LOWER_48 = (_conic_equal_area((29.5, 45.5), 96, (-0.6, 38.7)), 1.0, (0.0, 0.0))
_INSETS = {
    '02': (_conic_equal_area((55, 65), 154, (-2, 58.5)), 0.35, (-0.307, -0.201)),
    '15': (_conic_equal_area((8, 18), 157, (-3, 19.9)), 1.0, (-0.205, -0.212)),
    '72': (_conic_equal_area((8, 18), 66, (0, 18)), 1.0, (0.350, -0.224)),
}
_ISLAND_TERRITORIES = ('60', '66', '69', '78')      # not on the map of the country
_COUNTRY_NAMES = {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}
_STATE_GEO_ID = re.compile(r'^\d{7}US(\d{2})$')


def _state_code(key) -> Optional[str]:
    """The FIPS code of the state or territory `key` names -- by name,
    postal code, FIPS code or Census GEO_ID ('0400000US13') -- or None."""
    k = str(key).strip()
    m = _STATE_GEO_ID.match(k)
    if m:
        return m.group(1) if m.group(1) in STATES else None
    try:
        return state_fips(k)
    except ValueError:
        return None


def _is_country(state) -> bool:
    """Whether `state` asks for the whole country ('US', 'USA', 'United States')."""
    return ''.join(ch for ch in str(state).lower() if ch.isalnum()) in _COUNTRY_NAMES


def _split_state(key: str) -> Tuple[str, Optional[str]]:
    """A county key as (normalized county name, state FIPS code): 'Cook
    County, Illinois' -> ('cook', '17'). Without a state after its last
    comma, the state is None."""
    if ',' in key:
        head, tail = key.rsplit(',', 1)
        state = _state_code(tail)
        if state is not None:
            return _normalize_name(head), state
    return _normalize_name(key), None


def _key_state(key: str) -> Optional[str]:
    """The state a county key says it's in -- a FIPS code's first two
    digits, or the state named after its last comma -- or None."""
    code = _county_code(key)
    if code:
        return code[1][:2] if code[0] == 'geoid' else None
    return _split_state(key)[1]


def _country_states(present) -> List[str]:
    """The states drawn on a map of the country: the 50 and DC, and Puerto
    Rico when it's among `present`."""
    return [f for f in STATES if f not in _ISLAND_TERRITORIES and (f != '72' or '72' in present)]


def _load_us_states(fips_codes: Sequence[str]) -> List[dict]:
    """The states (and territories) with these FIPS codes, as regions."""
    arcs, objects = _us_topology()
    regions = []
    for g in objects['states']['geometries']:
        fips = str(g.get('id'))
        if fips not in fips_codes:
            continue
        polygons = _topo_polygons(g, arcs)
        regions.append({
            'name': STATES[fips][1],
            'rings': [poly[0] for poly in polygons],
            'holes': [h for poly in polygons for h in poly[1:]],
            'geoid': fips,
            'state': fips,
            'countyfp': None,
            'aliases': set(),
        })
    return regions


def _load_us_counties(fips_codes: Sequence[str]) -> List[dict]:
    """Every county of these states, named 'Cook, IL' (county names repeat
    from state to state), matched by name only together with the state."""
    regions = []
    for fips in fips_codes:
        postal = STATES[fips][0]
        for c in _load_state_counties(fips):
            regions.append(dict(c, name=f"{c['name']}, {postal}", state=fips,
                                aliases={(fips, alias) for alias in c['aliases']}))
    return regions


def _project_country(regions: List[dict]) -> None:
    """Project every region onto the map of the country -- the lower 48,
    or its state's inset -- as `_project_state` does for one state."""
    for c in regions:
        project, k, (ox, oy) = _INSETS.get(c['state'], _LOWER_48)

        def xy(ring, project=project, k=k, ox=ox, oy=oy):
            a = np.asarray(ring, dtype=float)
            x, y = project(a[:, 0], a[:, 1])
            return np.column_stack([k * x + ox, k * y + oy])

        c['xy_rings'] = [xy(r) for r in c['rings']]
        c['xy_holes'] = [xy(r) for r in c['holes']]
        c['area'] = (sum(_polygon_area(r) for r in c['xy_rings'])
                     - sum(_polygon_area(r) for r in c['xy_holes']))


_GEO_ID = re.compile(r'^\d{7}US(\d{5})$')


def _county_code(key: str) -> Optional[Tuple[str, str]]:
    """
    ('geoid', '13121') or ('countyfp', '121') when `key` is a FIPS code,
    otherwise None: five digits for state and county (four when an
    integer lost the leading zero -- 1001 is Alabama's 01001), up to
    three for the county alone, or a Census GEO_ID like
    '0500000US13121'. US data very often identifies counties this way
    rather than by name; they used to match nothing.
    """
    k = key.strip()
    m = _GEO_ID.match(k)
    if m:
        return 'geoid', m.group(1)
    if k.isdigit():
        if len(k) <= 3:
            return 'countyfp', k.zfill(3)
        if len(k) <= 5:
            return 'geoid', k.zfill(5)
    return None


# Where a boundary file keeps each county's name, in order of preference:
# the Census's own files use NAME; others use these.
_NAME_PROPERTIES = ('NAME', 'name', 'Name', 'NAMELSAD', 'NAME_2', 'county', 'County',
                    'COUNTY', 'county_name', 'COUNTY_NAME', 'CountyName')


def _feature_codes(props: dict) -> Tuple[Optional[str], Optional[str]]:
    """(5-digit GEOID, 3-digit county FIPS) from a feature's properties."""
    geoid = None
    for key in ('GEOID', 'GEOID20', 'GEOID10', 'FIPS', 'fips', 'GEO_ID', 'geo_id'):
        value = props.get(key)
        if value is None or str(value).strip() == '':
            continue
        code = _county_code(str(value))
        if code and code[0] == 'geoid':
            geoid = code[1]
            break
    if geoid is None and props.get('STATEFP') is not None and props.get('COUNTYFP') is not None:
        geoid = str(props['STATEFP']).zfill(2) + str(props['COUNTYFP']).zfill(3)
    countyfp = props.get('COUNTYFP')
    countyfp = str(countyfp).zfill(3) if countyfp is not None else (geoid[-3:] if geoid else None)
    return geoid, countyfp


def _oriented(ring, counterclockwise: bool):
    """The ring wound the given way: matplotlib fills by winding number,
    so a hole only shows as a hole when it winds against its outline."""
    xy = np.asarray(ring, dtype=float)
    x, y = xy[:, 0], xy[:, 1]
    is_ccw = (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) > 0
    return xy if is_ccw == counterclockwise else xy[::-1]


def _load_counties(geojson_path: str) -> List[dict]:
    """
    Every county in a GeoJSON file: its name, its outline(s), any holes,
    and its FIPS codes when the file has them. A county in several pieces
    (a MultiPolygon: islands, say) keeps every piece -- only the first
    used to be drawn -- and a hole (a city that's a county of its own,
    inside another) is left unfilled. The bundled Georgia file is all
    single pieces without holes.
    """
    with open(geojson_path, encoding='utf-8') as f:      # GeoJSON is UTF-8 by definition
        gj = json.load(f)
    counties = []
    property_keys = set()
    for feat in gj.get('features', []):
        props = feat.get('properties') or {}
        property_keys.update(props)
        geom = feat.get('geometry') or {}
        if geom.get('type') == 'Polygon':
            polygons = [geom['coordinates']]
        elif geom.get('type') == 'MultiPolygon':
            polygons = geom['coordinates']
        else:
            continue                          # no area to colour
        name = next((props[k] for k in _NAME_PROPERTIES if props.get(k) not in (None, '')), None)
        if name is None:
            raise ValueError(
                f"County boundaries in {os.path.basename(geojson_path)!r} have no name property "
                f"(looked for {', '.join(_NAME_PROPERTIES[:4])}, ...); their properties are "
                f"{sorted(property_keys)}.")
        geoid, countyfp = _feature_codes(props)
        counties.append({
            'name': str(name),
            'rings': [p[0] for p in polygons if p],
            'holes': [h for p in polygons for h in p[1:]],
            'geoid': geoid,
            'countyfp': countyfp,
            'aliases': {_normalize_name(str(name))},
        })
    return counties


def _project(lon: float, lat: float, lon0: float, cos_lat0: float) -> Tuple[float, float]:
    """Simple aspect-corrected equirectangular projection: fine for a
    single U.S. state's extent, where the distortion a proper map
    projection exists to fix is negligible. Scaling x by cos(mean
    latitude) keeps a degree of longitude and a degree of latitude
    visually comparable in length, which plain (lon, lat) as (x, y)
    does not -- without it, Georgia renders visibly squashed
    horizontally, since a degree of longitude is physically shorter than
    a degree of latitude this far from the equator."""
    return (lon - lon0) * cos_lat0, lat


def _polygon_area(xy: np.ndarray) -> float:
    """Shoelace formula -- used only to rank counties by size (for
    label_by='area', and to break ties), so approximate projected area
    (not geographically exact area) is perfectly sufficient."""
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def _polygon_centroid(xy: np.ndarray) -> Tuple[float, float]:
    """Area centroid of a simple polygon (falls back to the vertex mean
    for a degenerate, zero-area one)."""
    x, y = xy[:, 0], xy[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    a = cross.sum() / 2
    if abs(a) < 1e-12:
        return float(x.mean()), float(y.mean())
    return float(((x + x1) * cross).sum() / (6 * a)), float(((y + y1) * cross).sum() / (6 * a))


def _classify(values: np.ndarray, n_classes: int) -> Tuple[np.ndarray, bool]:
    """
    Colour classes for the map, as (edges, discrete).

    Normally quantile classes -- equal numbers of counties per class, the
    standard choropleth default, so a few outliers can't squash everyone
    else into one colour. edges are the boundaries b0 < b1 < ... < bk
    (k classes, the last one closed). Each boundary is an actual county's
    value, so it prints exactly at the data's own precision and every
    class holds at least the county on its lower boundary. Boundaries that
    tied values make coincide are merged, so there can be fewer classes
    than `n_classes`.

    When the data have no more distinct values than `n_classes`, quantile
    boundaries would only split the gaps between them, so instead each
    value gets a class of its own (discrete=True, edges are the values).

    Data with negative and positive values have a boundary at zero, so no
    class holds both, and the classes are split evenly between the two
    sides -- the odd one to the side with more counties, and fewer to a
    side with fewer distinct values -- each side in quantiles of its own.
    (A map of election margins had narrow wins for each side in one class,
    "-6 to +17"; and shared in proportion to the counties, the fifth of
    them won by one side all got one class.)

    Before this, three distinct values drew a seven-class colorbar reading
    "1 1 1 2 2 3 3 3", a map where every county had the same value read
    "5 5 5 5 5 5 5 5", and two counties got five empty classes.
    """
    ordered = np.sort(np.asarray(values, dtype=float))
    distinct = np.unique(ordered)
    if len(distinct) <= n_classes:
        return distinct, True

    def quantile_edges(vals, k):
        positions = np.round(np.linspace(0, 1, k + 1) * (len(vals) - 1)).astype(int)
        return np.unique(vals[positions])

    if ordered[0] < 0 < ordered[-1] and n_classes >= 2:
        negative, rest = ordered[ordered < 0], ordered[ordered >= 0]
        half = n_classes // 2
        n_negative = half if len(negative) <= len(rest) else n_classes - half
        n_negative = max(1, min(n_negative, len(np.unique(negative))))
        n_rest = min(n_classes - n_negative, len(np.unique(rest)))
        n_negative = max(1, min(n_classes - n_rest, len(np.unique(negative))))
        below = quantile_edges(negative, n_negative)[:-1] if len(np.unique(negative)) > 1 else negative[:1]
        above = quantile_edges(rest, n_rest)[1:] if len(np.unique(rest)) > 1 else rest[-1:]
        return np.unique(np.concatenate([below, [0.0], above])), False
    return quantile_edges(ordered, n_classes), False


_PALETTES = ('crimson', 'gold', 'green', 'diverging')
# The negative side of a diverging map for colour-blind readers: blue, as
# in colors.get_diverging(colorblind_safe=True).
_BLUE_ANCHORS = ['#EEF3FA', '#5A8CC4', '#1F4E8F']


def _ramp(name: str, n: int) -> List[str]:
    """`n` colours of one hue, light to dark."""
    if name == 'blue':
        return (dubois_colors._evenly_lighter(_BLUE_ANCHORS, n) if n > 1
                else [dubois_colors._evenly_lighter(_BLUE_ANCHORS, 8)[4]])
    return dubois_colors.get_sequential(name, n=n)


def _has_blue_classes(palette: Optional[str], edges: np.ndarray, n_used: int) -> bool:
    """Whether `_class_colors` gives some classes the colour-blind blue."""
    diverging = palette == 'diverging' or (palette is None and bool(edges[0] < 0 < edges[-1]))
    return (diverging and dubois_colors._COLORBLIND_SAFE[0]
            and bool((np.asarray(edges[:n_used]) < 0).any()))


def _class_colors(palette: Optional[str], edges: np.ndarray, n_used: int) -> List[str]:
    """
    The colours of the classes, lowest first. A sequential palette, light
    to dark; or, by default for data with negative and positive values, a
    diverging one: green (blue, with colors.set_colorblind_safe()) for the
    negative classes, darker the further below zero, and crimson for the
    rest, darker the higher -- so the sign is seen at a glance, which one
    light-to-dark scale can't show.
    """
    signed = bool(edges[0] < 0 < edges[-1])
    if palette is None:
        palette = 'diverging' if signed else 'crimson'
    if palette != 'diverging':
        return dubois_colors.get_sequential(palette, n=n_used)
    n_negative = int((np.asarray(edges[:n_used]) < 0).sum())
    negative_hue = 'blue' if dubois_colors._COLORBLIND_SAFE[0] else 'green'

    def side(hue, k):
        # A side's lightest class is one step in from near-white, so the
        # two sides' classes nearest zero still differ.
        return _ramp(hue, k + 1)[1:] if k > 1 else (_ramp(hue, 1) if k == 1 else [])
    return side(negative_hue, n_negative)[::-1] + side('crimson', n_used - n_negative)


def _data_decimals(values: np.ndarray, most: int = 6) -> int:
    """How many decimals the data are given to: the fewest that show every
    value exactly (0.25 -> 2, 2.5 -> 1, 82 -> 0), at most `most`."""
    values = np.asarray(values, dtype=float)
    scale = max(1.0, float(np.abs(values).max()))
    for d in range(most + 1):
        if np.all(np.abs(values - np.round(values, d)) <= 1e-9 * scale):
            return d
    return most


def _boundary_format(edges: np.ndarray, values: np.ndarray, discrete: bool) -> str:
    """
    Default colorbar number format: the data's own precision (so a
    boundary never looks like a value it isn't), but no more than four
    significant digits for big numbers -- a colour scale for incomes
    doesn't need cents -- and more decimals only if two different
    boundaries would otherwise print the same, or a small negative one
    would print as "-0". Discrete classes, labelled with their values,
    follow the same rule: four computed values like 4.985380125 used to
    print in full ("4.985380"), too long to fit beside each other.
    """
    decimals = _data_decimals(values)
    biggest = float(np.abs(edges).max())
    if biggest > 0:
        decimals = min(decimals, max(0, 3 - int(math.floor(math.log10(biggest)))))
    distinct = len(np.unique(edges))
    for d in range(decimals, decimals + 7):
        fmt = '{:,.%df}' % d
        texts = [format_value(fmt, e) for e in edges]
        negative_zero = any(t.startswith('-') and not any(ch in '123456789' for ch in t) for t in texts)
        if len(set(texts)) >= distinct and not negative_zero:
            return fmt
    return fmt


def _fit_tick_labels(fig, texts: List[str], spacing_px: float, font: str,
                     gap_px: float = 6.0) -> Tuple[float, List[int]]:
    """
    Font size and which of the evenly spaced colorbar labels to draw so
    that no two touch. All of them at 8pt, else all at 7pt; if they can't
    all fit, every second (third, ...) label at 8pt, then 7pt, rather than
    shrinking further -- always keeping the first and last. Only as a last
    resort 6pt. Long numbers across many classes ("1,311,188" on a
    twelve-class scale) used to print on top of each other.
    """
    widths = {fs: [tu.measure_text_px(fig, t, fs, font, 'bold')[0] for t in texts] for fs in (8, 7, 6)}
    last = len(texts) - 1

    def clear(idx, fs):
        w = widths[fs]
        return all((w[a] + w[b]) / 2 + gap_px <= (b - a) * spacing_px for a, b in zip(idx, idx[1:]))

    def thinned(fs):
        for step in range(2, len(texts) + 1):
            shown = list(range(0, last, step))
            while len(shown) > 1 and not clear(shown + [last], fs):
                shown.pop()          # the label just before the last one crowds it
            if clear(shown + [last], fs):
                return shown + [last]
        return None

    everything = list(range(len(texts)))
    for fs, pick in ((8, 'all'), (7, 'all'), (8, 'thin'), (7, 'thin'), (6, 'all'), (6, 'thin')):
        shown = everything if pick == 'all' else thinned(fs)
        if shown is not None and clear(shown, fs):
            return fs, shown
    return 6, [0, last] if last > 0 else [0]


LABEL_ORDERS = ('extremes', 'highest', 'lowest', 'area')


def _label_order(counties: List[dict], values: Dict[str, float], label_by: str) -> List[dict]:
    """
    Counties with data, in the order they should be offered a label.

    'extremes' alternates highest and lowest (highest first), 'highest'
    and 'lowest' take one end only, and 'area' is simply largest first.
    Ties go to the larger county, then alphabetically, so the order never
    depends on the order `data` happened to be given in.
    """
    by_area = sorted(counties, key=lambda c: (-c['area'], c['name']))
    if label_by == 'area':
        return by_area
    highest = sorted(by_area, key=lambda c: -values[c['name']])   # stable: ties stay largest-first
    lowest = sorted(by_area, key=lambda c: values[c['name']])
    if label_by == 'highest':
        return highest
    if label_by == 'lowest':
        return lowest
    order, seen = [], set()
    for pair in zip(highest, lowest):
        for c in pair:
            if c['name'] not in seen:
                seen.add(c['name'])
                order.append(c)
    return order


def _box_outline(half_w: float, half_h: float, spacing: float) -> np.ndarray:
    """Points around the edge of a box centred on (0, 0), no more than
    `spacing` apart, so checking them all catches a county boundary that
    cuts into the box between its corners."""
    nx = max(2, int(math.ceil(2 * half_w / spacing)) + 1)
    ny = max(2, int(math.ceil(2 * half_h / spacing)) + 1)
    xs, ys = np.linspace(-half_w, half_w, nx), np.linspace(-half_h, half_h, ny)
    return np.concatenate([np.column_stack([xs, np.full(nx, -half_h)]),
                           np.column_stack([xs, np.full(nx, half_h)]),
                           np.column_stack([np.full(ny, -half_w), ys]),
                           np.column_stack([np.full(ny, half_w), ys])])


def _label_anchor(outline: np.ndarray, path: MplPath, half_w: float, half_h: float,
                  spacing: float, grid: int = 25) -> Optional[Tuple[float, float]]:
    """
    Where to centre a label box of this size so that it sits entirely
    inside the county outline -- or None if it fits nowhere.

    Candidate centres are a grid over the county; a box "fits" when every
    point around its edge is inside the outline. Among the centres that
    fit, prefer ones with room to spare around the label, then the one
    nearest the county's centroid, so labels sit in the roomiest,
    most central spot rather than hard against a boundary.

    This replaced centring every label on the average of the outline's
    vertices, which for irregular counties is often a cramped spot (or
    not inside the county at all): measured on the 159 Georgia counties
    at the default size, 50 names fit inside at 8pt that way and 105 fit
    this way (91 and 143 at 6pt).
    """
    x0, y0 = outline.min(axis=0)
    x1, y1 = outline.max(axis=0)
    if 2 * half_w > x1 - x0 or 2 * half_h > y1 - y0:
        return None
    gx, gy = np.meshgrid(np.linspace(x0 + half_w, x1 - half_w, grid),
                         np.linspace(y0 + half_h, y1 - half_h, grid))
    centres = np.column_stack([gx.ravel(), gy.ravel()])
    centres = centres[path.contains_points(centres)]
    if not len(centres):
        return None
    # Nearest the centroid first. A box that doesn't fit with no room to
    # spare doesn't fit with room, so those are ruled out first -- by
    # their corners, then their whole edge -- and the rest tried a few at
    # a time, nearest first, with room. (Checking every spot's whole edge
    # at every room took a map of the 50 states, labelled throughout, 11
    # seconds.)
    target = np.array(_polygon_centroid(outline))
    centres = centres[np.argsort(((centres - target) ** 2).sum(axis=1), kind='stable')]

    def fitting(spots, edge):
        inside = path.contains_points((spots[:, None, :] + edge[None, :, :]).reshape(-1, 2))
        return inside.reshape(len(spots), -1).all(axis=1)

    corners = np.array([[-half_w, -half_h], [half_w, -half_h], [-half_w, half_h], [half_w, half_h]])
    centres = centres[fitting(centres, corners)]
    if len(centres):
        centres = centres[fitting(centres, _box_outline(half_w, half_h, spacing))]
    if not len(centres):
        return None
    for room in (half_h, half_h / 2):
        edge = _box_outline(half_w + room, half_h + room, spacing)
        for start in range(0, len(centres), 32):
            fits = fitting(centres[start:start + 32], edge)
            if fits.any():
                best = centres[start + int(np.argmax(fits))]
                return float(best[0]), float(best[1])
    return float(centres[0][0]), float(centres[0][1])


def _interior_point(outline: np.ndarray, path: MplPath) -> Tuple[float, float]:
    """A point inside the county for a callout's leader line to start
    from: the centroid, or if that falls outside a concave county, the
    point inside nearest to it."""
    centroid = _polygon_centroid(outline)
    if path.contains_point(centroid):
        return centroid
    (x0, y0), (x1, y1) = outline.min(axis=0), outline.max(axis=0)
    gx, gy = np.meshgrid(np.linspace(x0, x1, 31), np.linspace(y0, y1, 31))
    points = np.column_stack([gx.ravel(), gy.ravel()])
    inside = points[path.contains_points(points)]
    if not len(inside):
        return float(outline[:, 0].mean()), float(outline[:, 1].mean())
    best = inside[np.argmin(((inside - np.array(centroid)) ** 2).sum(axis=1))]
    return float(best[0]), float(best[1])


def _segments_cross(p1, p2, q1, q2) -> bool:
    """Whether the segments p1-p2 and q1-q2 cross (not merely touch)."""
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return side(q1, q2, p1) * side(q1, q2, p2) < 0 and side(p1, p2, q1) * side(p1, p2, q2) < 0


def _leader_end(start, centre, half_w: float, half_h: float) -> Tuple[float, float]:
    """Where a leader line from `start` meets the box: its nearest point."""
    return (float(np.clip(start[0], centre[0] - half_w, centre[0] + half_w)),
            float(np.clip(start[1], centre[1] - half_h, centre[1] + half_h)))


def _uncross_callouts(placed: List[dict], space: '_FreeSpace', base, room=None,
                      cross_cost: float = 0.0) -> None:
    """
    Where two callouts' leader lines cross, swap their labels -- each
    takes the other's place -- if both fit there and the lines get
    shorter (for crossing lines they usually do); failing that, find one
    of them a new place, now that every other line is known. Crossed
    lines are hard to follow to the right county; on a map of the 50
    states labelled throughout, Michigan's crossed Wisconsin's and
    Indiana's. `base` is the free space before any callout; each entry
    of `placed` has the county's `start`, the box's `centre` and
    half-size, and the line's `end`; `room` and `cross_cost` are as for
    `_FreeSpace.best_spot`.
    """
    def length(start, end):
        return math.hypot(end[0] - start[0], end[1] - start[1])

    def mark(skip=()):
        space.restore(base)
        for k, p in enumerate(placed):
            if k not in skip:
                space.take_label(*p['centre'], p['half_w'], p['half_h'])
                space.take_leader(p['start'], p['end'])

    def moved(p, q):
        """Where p's box goes in q's place: on the same side of it the
        line meets -- labels to the right of a state keep their left edges
        lined up -- or centred on it."""
        x, y = q['centre']
        if p['start'][0] < x - q['half_w']:
            x += p['half_w'] - q['half_w']
        elif p['start'][0] > x + q['half_w']:
            x -= p['half_w'] - q['half_w']
        return x, y

    def reordered(a, b):
        """Two labels side by side in a row (above or below the state), or
        stacked in a column (beside it), put back in the order of their
        counties along that row or column -- each keeping its own size, so
        a long name and a short one can trade places in the space the two
        take up between them."""
        (ax_, ay_), (bx_, by_) = a['centre'], b['centre']
        if abs(ay_ - by_) < min(a['half_h'], b['half_h']):              # a row
            lo = min(ax_ - a['half_w'], bx_ - b['half_w'])
            hi = max(ax_ + a['half_w'], bx_ + b['half_w'])
            if a['start'][0] <= b['start'][0]:
                return (lo + a['half_w'], ay_), (hi - b['half_w'], by_)
            return (hi - a['half_w'], ay_), (lo + b['half_w'], by_)
        if abs(ax_ - bx_) < min(a['half_w'], b['half_w']):              # a column
            lo = min(ay_ - a['half_h'], by_ - b['half_h'])
            hi = max(ay_ + a['half_h'], by_ + b['half_h'])
            if a['start'][1] <= b['start'][1]:
                return (ax_, lo + a['half_h']), (bx_, hi - b['half_h'])
            return (ax_, hi - a['half_h']), (bx_, lo + b['half_h'])
        return None

    def overlap(c1, hw1, hh1, c2, hw2, hh2) -> bool:
        return abs(c1[0] - c2[0]) < hw1 + hw2 and abs(c1[1] - c2[1]) < hh1 + hh2

    def line_hits(p, q, centre, hw, hh) -> bool:
        """Whether the segment p-q passes through the box (by points no
        further apart than half a grid cell)."""
        n = int(math.ceil(length(p, q) / (space.cell / 2))) + 2
        t = np.linspace(0.0, 1.0, n)
        xs, ys = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
        return bool(np.any((np.abs(xs - centre[0]) < hw) & (np.abs(ys - centre[1]) < hh)))

    def try_swap(i, j, a_centre, b_centre) -> bool:
        """Move a's label to a_centre and b's to b_centre, if the lines get
        shorter and stop crossing, and both labels are clear of the map,
        the other labels and the other lines. The other callouts are
        checked exactly, not on the grid: there a line's one-cell halo can
        reach into the very box the label it passes beside came from."""
        a, b = placed[i], placed[j]
        a_end = _leader_end(a['start'], a_centre, a['half_w'], a['half_h'])
        b_end = _leader_end(b['start'], b_centre, b['half_w'], b['half_h'])
        if (length(a['start'], a_end) + length(b['start'], b_end)
                >= length(a['start'], a['end']) + length(b['start'], b['end'])):
            return False
        if _segments_cross(a['start'], a_end, b['start'], b_end):
            return False
        new = ((a, a_centre, a_end), (b, b_centre, b_end))
        if overlap(a_centre, a['half_w'], a['half_h'], b_centre, b['half_w'], b['half_h']):
            return False
        space.restore(base)             # the map and the labels inside it
        for p, centre, end in new:
            if not (space.box_free(*centre, p['half_w'], p['half_h'])
                    and space.line_clear(p['start'], end)):
                return False
        for k, q in enumerate(placed):
            if k in (i, j):
                continue
            for p, centre, end in new:
                if (overlap(centre, p['half_w'], p['half_h'], q['centre'], q['half_w'], q['half_h'])
                        or line_hits(q['start'], q['end'], centre, p['half_w'], p['half_h'])
                        or line_hits(p['start'], end, q['centre'], q['half_w'], q['half_h'])):
                    return False
        if (line_hits(a['start'], a_end, b_centre, b['half_w'], b['half_h'])
                or line_hits(b['start'], b_end, a_centre, a['half_w'], a['half_h'])):
            return False
        a['centre'], b['centre'], a['end'], b['end'] = a_centre, b_centre, a_end, b_end
        return True

    def swap_pass() -> bool:
        changed = False
        for _ in range(4 * len(placed)):    # every swap shortens the lines, so this ends
            swapped = False
            for i in range(len(placed)):
                for j in range(i + 1, len(placed)):
                    a, b = placed[i], placed[j]
                    if not _segments_cross(a['start'], a['end'], b['start'], b['end']):
                        continue
                    pair = reordered(a, b)
                    swapped |= (try_swap(i, j, moved(a, b), moved(b, a))
                                or try_swap(i, j, b['centre'], a['centre'])
                                or (pair is not None and try_swap(i, j, *pair)))
            changed |= swapped
            if not swapped:
                break
        return changed

    def crossings(k, end=None):
        p = placed[k]
        return sum(_segments_cross(p['start'], end or p['end'], q['start'], q['end'])
                   for m, q in enumerate(placed) if m != k)

    def replace_pass() -> bool:
        # A crossing is worth `cross_cost` of extra line: a new place for
        # a label is taken only if its line is no longer than that buys.
        changed = False
        for k in sorted(range(len(placed)), key=crossings, reverse=True):
            now = crossings(k)
            if not now:
                continue
            p = placed[k]
            mark(skip=(k,))
            others = [(q['start'], q['end']) for m, q in enumerate(placed) if m != k]
            spot = space.best_spot(p['start'], p['half_w'], p['half_h'], room=room,
                                   leaders=others, cross_cost=cross_cost)
            if spot is None:
                continue
            then = crossings(k, spot[1])
            if (then < now and length(p['start'], spot[1]) + cross_cost * then
                    < length(p['start'], p['end']) + cross_cost * now):
                p['centre'], p['end'] = spot
                changed = True
        return changed

    def regroup_pass() -> bool:
        """Callouts whose lines cross one another, taken as a group: placed
        again one by one -- north to south, south to north, west to east or
        east to west, whichever crosses least -- so a stack of three labels
        in the wrong order (Virginia's King George, Caroline and Hanover,
        drawn wider in DejaVu Sans Mono) is put in the order of their
        counties even when no two of them can trade places."""
        n = len(placed)
        links = {k: set() for k in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if _segments_cross(placed[i]['start'], placed[i]['end'],
                                   placed[j]['start'], placed[j]['end']):
                    links[i].add(j)
                    links[j].add(i)
        changed, seen = False, set()
        for k in range(n):
            if k in seen or not links[k]:
                continue
            group, todo = set(), [k]
            while todo:
                m = todo.pop()
                if m not in group:
                    group.add(m)
                    todo.extend(links[m] - group)
            seen |= group

            def cost():
                return sum(length(placed[m]['start'], placed[m]['end']) for m in group) + \
                    cross_cost * sum(crossings(m) for m in group)

            before = {m: (placed[m]['centre'], placed[m]['end']) for m in group}
            best_cost, best = cost(), None
            for key in (lambda m: -placed[m]['start'][1], lambda m: placed[m]['start'][1],
                        lambda m: placed[m]['start'][0], lambda m: -placed[m]['start'][0]):
                mark(skip=group)
                done, complete = set(), True
                for m in sorted(group, key=key):
                    p = placed[m]
                    others = [(q['start'], q['end']) for t, q in enumerate(placed)
                              if t not in group or t in done]
                    spot = space.best_spot(p['start'], p['half_w'], p['half_h'], room=room,
                                           leaders=others, cross_cost=cross_cost)
                    if spot is None:
                        complete = False
                        break
                    p['centre'], p['end'] = spot
                    space.take_label(*spot[0], p['half_w'], p['half_h'])
                    space.take_leader(p['start'], spot[1])
                    done.add(m)
                if complete and cost() < best_cost - 1e-12:
                    best_cost = cost()
                    best = {m: (placed[m]['centre'], placed[m]['end']) for m in group}
                for m, (centre, end) in before.items():
                    placed[m]['centre'], placed[m]['end'] = centre, end
            if best is not None:
                for m, (centre, end) in best.items():
                    placed[m]['centre'], placed[m]['end'] = centre, end
                changed = True
        return changed

    for _ in range(3):              # moving one label can open a swap for another
        if not (swap_pass() | replace_pass() | regroup_pass()):
            break
    mark()


CALLOUT_CANDIDATES = 5000              # nearest spots tried for each callout


class _FreeSpace:
    """
    Where a callout label can go. A grid over the map (cells `cell` data
    units square) marks what's already there: the state itself -- every
    county, grown by `grow_cells` so a callout never touches the border --
    plus labels and leader lines as they're placed. Label boxes are also
    kept separately, because a leader line may cross counties but must not
    run through another label.

    `extend` adds whole cells beyond the map's frame -- (left, right,
    bottom, top) -- where callouts may also go. Whole cells keep the grid
    inside the frame exactly where it would be without them.

    `label_gap` keeps labels side by side that far apart: a label takes
    that much more room to its left and right from labels level with it,
    but no more from the state or the leader lines. (Callouts side by side were
    8-10 pixels apart, and "McCone, MT Hand, SD" read as one name. Widening
    the label's own box instead kept it that much further from the state
    too, and on Tennessee's map Campbell County's name was pushed an inch
    from its county.)
    """

    def __init__(self, counties: List[dict], xlim, ylim, cell: float, grow_cells: int,
                 extend: Tuple[int, int, int, int] = (0, 0, 0, 0), label_gap: float = 0.0):
        left, right, bottom, top = (int(k) for k in extend)
        self.label_gap = float(label_gap)
        self.cell = float(cell)
        self.x0, self.y0 = float(xlim[0]) - left * self.cell, float(ylim[0]) - bottom * self.cell
        self.nx = int(math.ceil((xlim[1] - xlim[0]) / cell)) + left + right
        self.ny = int(math.ceil((ylim[1] - ylim[0]) / cell)) + bottom + top
        xs = self.x0 + (np.arange(self.nx) + 0.5) * cell
        ys = self.y0 + (np.arange(self.ny) + 0.5) * cell
        state = np.zeros((self.ny, self.nx), dtype=bool)
        for c in counties:
            for ring in c['xy_rings']:
                (bx0, by0), (bx1, by1) = ring.min(axis=0), ring.max(axis=0)
                i0, i1 = self._col(bx0), self._col(bx1) + 1
                j0, j1 = self._row(by0), self._row(by1) + 1
                gx, gy = np.meshgrid(xs[i0:i1], ys[j0:j1])
                inside = MplPath(ring).contains_points(np.column_stack([gx.ravel(), gy.ravel()]))
                state[j0:j1, i0:i1] |= inside.reshape(gx.shape)
        self.taken = self._grow(state, grow_cells)
        self.spaced = self.taken.copy()
        self.labels = np.zeros_like(state)

    def _col(self, x: float) -> int:
        return int(np.clip((x - self.x0) // self.cell, 0, self.nx - 1))

    def _row(self, y: float) -> int:
        return int(np.clip((y - self.y0) // self.cell, 0, self.ny - 1))

    @staticmethod
    def _grow(mask: np.ndarray, k: int) -> np.ndarray:
        if k <= 0:
            return mask.copy()
        padded = np.pad(mask, k)
        h, w = mask.shape
        grown = np.zeros_like(mask)
        for dy in range(2 * k + 1):
            for dx in range(2 * k + 1):
                grown |= padded[dy:dy + h, dx:dx + w]
        return grown

    def _cells_along(self, p, q) -> Tuple[np.ndarray, np.ndarray]:
        n = int(math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / (self.cell / 2))) + 2
        t = np.linspace(0.0, 1.0, n)
        xs, ys = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
        cols = np.clip(((xs - self.x0) // self.cell).astype(int), 0, self.nx - 1)
        rows = np.clip(((ys - self.y0) // self.cell).astype(int), 0, self.ny - 1)
        return rows, cols

    def take_label(self, cx: float, cy: float, half_w: float, half_h: float) -> None:
        rows = slice(self._row(cy - half_h), self._row(cy + half_h) + 1)
        cols = slice(self._col(cx - half_w), self._col(cx + half_w) + 1)
        self.labels[rows, cols] = True
        self.taken[rows, cols] = True
        # The gap, along the label's middle: another label is kept that far
        # away only if it's level with this one, more than half overlapping
        # it -- side by side, read on one line. It's marked in `spaced`, a
        # copy of `taken`; best_spot(spaced=False) looks past it.
        gap, row = self.label_gap, self._row(cy)
        self.spaced[rows, cols] = True
        self.spaced[row, self._col(cx - half_w - gap):self._col(cx + half_w + gap) + 1] = True

    def take_leader(self, p, q) -> None:
        rows, cols = self._cells_along(p, q)
        for dr in (-1, 0, 1):          # the line's background-coloured halo is ~1 cell wide
            for dc in (-1, 0, 1):
                cells = (np.clip(rows + dr, 0, self.ny - 1), np.clip(cols + dc, 0, self.nx - 1))
                self.taken[cells] = True
                self.spaced[cells] = True

    def snapshot(self):
        return self.taken.copy(), self.spaced.copy(), self.labels.copy()

    def restore(self, snapshot) -> None:
        self.taken, self.spaced, self.labels = (a.copy() for a in snapshot)

    def box_free(self, cx: float, cy: float, half_w: float, half_h: float) -> bool:
        """Whether a box here is on the grid and clear of everything marked."""
        if (cx - half_w < self.x0 or cy - half_h < self.y0
                or cx + half_w > self.x0 + self.nx * self.cell
                or cy + half_h > self.y0 + self.ny * self.cell):
            return False
        rows = slice(self._row(cy - half_h), self._row(cy + half_h) + 1)
        cols = slice(self._col(cx - half_w), self._col(cx + half_w) + 1)
        return not self.taken[rows, cols].any()

    def line_clear(self, p, q) -> bool:
        """Whether a leader line from p to q runs through no label."""
        rows, cols = self._cells_along(p, q)
        return not self.labels[rows, cols].any()

    def best_spot(self, anchor, half_w: float, half_h: float, room=None, cost=(2.0, 1.0),
                  leaders=(), cross_cost: float = 0.0):
        """
        The best spot a `label_gap` from labels level with this one -- or
        the best spot at all, if that one's line is three gaps or more
        shorter: Virginia's Caroline, kept an em from Hanover, went across
        the state.
        """
        args = (anchor, half_w, half_h, room, cost, leaders, cross_cost)
        spot = self._best_spot(*args, spaced=True)
        if not self.label_gap:
            return spot
        near = self._best_spot(*args, spaced=False)
        if near is not None and (spot is None or math.dist(anchor, spot[1])
                                 > math.dist(anchor, near[1]) + 3 * self.label_gap):
            return near
        return spot

    def _best_spot(self, anchor, half_w: float, half_h: float, room=None, cost=(2.0, 1.0),
                   leaders=(), cross_cost: float = 0.0, spaced: bool = True):
        """
        The free spot nearest `anchor` for a box of this half-size, and
        where its leader line meets the box: ((cx, cy), (ex, ey)), or None
        if there's nowhere left. "Nearest" is the leader line's length,
        plus a small penalty for vertical offset, so callouts prefer to
        sit level with their county.

        `room`, (x0, x1, y0, y1), is what the figure already has room for;
        a box reaching past it would make the figure bigger, which costs
        `cost` (horizontal, vertical) per unit of distance it reaches out.
        Wider costs double: the figure grows on both sides, to keep the
        map centred under the title.

        `leaders` are the lines already drawn, as (start, end) pairs: a
        line crossing one costs `cross_cost` more, so a spot a little
        further away whose line crosses nothing is taken instead.

        `spaced`: keep `label_gap` from labels level with this one.
        """
        w = int(math.ceil(2 * half_w / self.cell)) + 1
        h = int(math.ceil(2 * half_h / self.cell)) + 1
        if w > self.nx or h > self.ny:
            return None
        s = np.zeros((self.ny + 1, self.nx + 1), dtype=np.int64)
        s[1:, 1:] = (self.spaced if spaced else self.taken).cumsum(axis=0).cumsum(axis=1)
        window = s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]
        rows, cols = np.nonzero(window == 0)
        if not len(rows):
            return None
        cx = self.x0 + (cols + w / 2) * self.cell
        cy = self.y0 + (rows + h / 2) * self.cell
        ax_, ay_ = anchor
        gap = np.hypot(np.maximum(np.abs(cx - ax_) - half_w, 0), np.maximum(np.abs(cy - ay_) - half_h, 0))
        score = gap + 0.25 * np.abs(cy - ay_)
        if room is not None:
            rx0, rx1, ry0, ry1 = room
            score = score + cost[0] * (np.maximum(rx0 - (cx - half_w), 0) + np.maximum(cx + half_w - rx1, 0)) \
                          + cost[1] * (np.maximum(ry0 - (cy - half_h), 0) + np.maximum(cy + half_h - ry1, 0))
        # The nearest spot whose leader line runs through no label: the
        # same cells `_cells_along` would visit, checked for a batch of
        # spots at a time (one by one, a crowded map spent seconds on
        # spots with no clear line).
        order = np.argsort(score, kind='stable')[:CALLOUT_CANDIDATES]
        if len(leaders) and cross_cost > 0:
            ex = np.clip(ax_, cx[order] - half_w, cx[order] + half_w)
            ey = np.clip(ay_, cy[order] - half_h, cy[order] + half_h)
            crossings = np.zeros(len(order))
            for (s0, s1), (e0, e1) in leaders:
                d1 = (e0 - s0) * (ay_ - s1) - (e1 - s1) * (ax_ - s0)
                d2 = (e0 - s0) * (ey - s1) - (e1 - s1) * (ex - s0)
                d3 = (ex - ax_) * (s1 - ay_) - (ey - ay_) * (s0 - ax_)
                d4 = (ex - ax_) * (e1 - ay_) - (ey - ay_) * (e0 - ax_)
                crossings += (d1 * d2 < 0) & (d3 * d4 < 0)
            if crossings.any():
                order = order[np.argsort(score[order] + cross_cost * crossings, kind='stable')]
        start, batch = 0, 16
        while start < len(order):
            ks = order[start:start + batch]
            ex = np.clip(ax_, cx[ks] - half_w, cx[ks] + half_w)
            ey = np.clip(ay_, cy[ks] - half_h, cy[ks] + half_h)
            n = np.ceil(np.hypot(ex - ax_, ey - ay_) / (self.cell / 2)).astype(int) + 2
            j = np.arange(n.max())[None, :]
            t = np.where(j >= n[:, None] - 1, 1.0, j * (1.0 / (n[:, None] - 1)))
            cols = np.clip(((ax_ + t * (ex[:, None] - ax_) - self.x0) // self.cell).astype(int), 0, self.nx - 1)
            rows = np.clip(((ay_ + t * (ey[:, None] - ay_) - self.y0) // self.cell).astype(int), 0, self.ny - 1)
            clear = ~self.labels[rows, cols].any(axis=1)
            if clear.any():
                i = int(np.argmax(clear))
                return (float(cx[ks[i]]), float(cy[ks[i]])), (float(ex[i]), float(ey[i]))
            start, batch = start + batch, min(4 * batch, 1024)
        return None


def _map_items(data, chart: str, what: str) -> List[Tuple[str, object]]:
    """A map's data as (key, value) pairs: a dict, or a pandas Series
    indexed by place. A table is an error rather than its column names
    being read as places, and so is no data at all.

    A missing value (None, NaN) means no data for that place, which is
    drawn as such, as an empty cell in a table would be. It used to be an
    error, and with pandas, missing values are everywhere: a rate worked
    out from two tables is NaN wherever either one has no row -- and with
    them dropped, the error became "two values for Puerto Rico", one for
    'PR' and one for 'Puerto Rico', both NaN."""
    if hasattr(data, 'columns'):
        raise TypeError(f"{chart}: `data` is a table; pass one column of it, indexed by {what}: "
                        f"df['rate'], say, or df.set_index('{what}')['rate'].")
    pairs = getattr(data, 'items', None)
    if not callable(pairs):
        raise TypeError(f"`data` must be a dict of {what} -> value, or a pandas Series indexed "
                        f"by {what}; got {type(data).__name__}.")
    pairs = list(pairs())
    # A value with no place -- its key missing -- can't go on the map, as a
    # key that names no place can't: it's left out, with a warning. It used
    # to stop the chart. The New York Times' county data has no code for New
    # York City or "Unknown", so the obvious df.set_index('fips') failed on
    # every day's figures.
    unplaced = [value for key, value in pairs if is_missing(key)]
    if unplaced:
        pairs = [(key, value) for key, value in pairs if not is_missing(key)]
        warnings.warn(
            f"{chart}: {len(unplaced)} value{'s' if len(unplaced) != 1 else ''} in `data` "
            f"{'have' if len(unplaced) != 1 else 'has'} no {what} -- the key is missing (None "
            f"or NaN) -- and {'are' if len(unplaced) != 1 else 'is'} left out.",
            UserWarning, stacklevel=4)
    labels = named_labels([key for key, _ in pairs], "`data`")
    items = [(label, value) for label, (_, value) in zip(labels, pairs)]
    if not items:
        raise ValueError(f"{chart}: `data` is empty, so there's nothing to map.")
    present = [(key, value) for key, value in items if not is_missing(value)]
    if not present:
        raise ValueError(f"{chart}: every value in `data` is missing (None or NaN), so there's "
                         f"nothing to map.")
    return present


def _state_for_names(keys: Sequence[str]) -> str:
    """
    The state to draw when `state` isn't given and the keys don't say:
    Georgia, as on Du Bois's own maps -- unless the keys are names, and
    names of counties of some one other state ("Cuyahoga", "Franklin",
    "Hamilton" are Ohio's), which draw that state. Names that several
    states have, Georgia among them, draw Georgia with a warning saying
    so; names that several other states have are an error, since there's
    no telling which state they're in.
    """
    states = _states_with_counties(keys)
    if not states:          # some key is a code, or some name is no state's county
        return '13'
    listed = ', '.join(sorted(STATES[f][1] for f in states))
    if '13' in states:
        if len(states) > 1:
            warnings.warn(
                f"county_map_chart: no `state` given, and {'that name is a county' if len(keys) == 1 else 'those names are counties'} "
                f"in {len(states)} states: {listed}. This draws Georgia, the default; pass "
                f"state= to draw another.", UserWarning, stacklevel=4)
        return '13'
    if len(states) == 1:
        return next(iter(states))
    raise ValueError(
        f"county_map_chart: no `state` given, and those county names aren't all Georgia's, the "
        f"default, but they're all counties of {len(states)} states: {listed}. Pass state= to "
        f"say which.")


# Counties that the bundled (2017) boundaries no longer have, because they
# were renamed, merged or divided before then: (state, code, name as
# matched, what became of it). Data from before the change still use them.
_RETIRED_COUNTIES = [
    ('46', '46113', 'shannon', 'Shannon County, SD', 'was renamed Oglala Lakota County (46102) in 2015'),
    ('02', '02270', 'wadehampton', 'Wade Hampton Census Area, AK',
     'was renamed Kusilvak Census Area (02158) in 2015'),
    ('51', '51515', 'bedfordcity', 'Bedford city, VA', 'became part of Bedford County (51019) in 2013'),
    ('02', '02201', 'princeofwalesouterketchikan', 'Prince of Wales-Outer Ketchikan Census Area, AK',
     'was divided in 2008, mostly between Prince of Wales-Hyder (02198) and Ketchikan Gateway (02130)'),
    ('02', '02232', 'skagwayhoonahangoon', 'Skagway-Hoonah-Angoon Census Area, AK',
     'was divided in 2007 into Skagway (02230) and Hoonah-Angoon (02105)'),
    ('02', '02280', 'wrangellpetersburg', 'Wrangell-Petersburg Census Area, AK',
     'was divided in 2008, mostly into Wrangell (02275) and Petersburg (02195)'),
    ('12', '12025', 'dade', 'Dade County, FL', 'was renamed Miami-Dade County (12086) in 1997'),
    ('51', '51560', 'cliftonforgecity', 'Clifton Forge city, VA',
     'became part of Alleghany County (51005) in 2001'),
    ('51', '51780', 'southbostoncity', 'South Boston city, VA', 'became part of Halifax County (51083) in 1995'),
    ('30', '30113', 'yellowstonenationalpark', 'Yellowstone National Park, MT',
     'was divided between Gallatin (30031) and Park (30067) counties in 1997'),
    ('13', None, 'campbell', 'Campbell County, GA', 'was merged into Fulton County in 1932'),
    ('13', None, 'milton', 'Milton County, GA', 'was merged into Fulton County in 1932'),
]


def _retired_note(key: str, map_states) -> Optional[str]:
    """What became of the county `key` names, if it's one the boundaries
    no longer have: on a map of one state, by its name or code; on the
    map of the country, by its code or its name with its state."""
    code = _county_code(key)
    if code:
        if code[0] != 'geoid':
            return None
        return next((f"({full}) {fate}" for _, old, _, full, fate in _RETIRED_COUNTIES
                     if old == code[1]), None)
    name, state = _split_state(key)
    if state is None and map_states is not None and len(map_states) == 1:
        state = next(iter(map_states))
    return next((fate for st, _, old, _, fate in _RETIRED_COUNTIES if st == state and old == name), None)


def _retired_hint(keys: Sequence[str], map_states) -> Tuple[str, List[str]]:
    """The hint for unmatched keys that name counties the boundaries no
    longer have, and the keys it explains."""
    notes = [(key, _retired_note(key, map_states)) for key in keys]
    notes = [(key, what) for key, what in notes if what]
    if not notes:
        return '', []
    shown = '; '.join(f"{key!r} {what}" for key, what in notes[:5])
    more = f'; and {len(notes) - 5} more' if len(notes) > 5 else ''
    return (f" ({shown}{more}. The bundled boundaries are the Census's of 2017: use the names "
            f"or codes of then, or pass boundaries of your data's year as geojson_path=.)",
            [key for key, _ in notes])


def _newer_boundaries_hint(keys: Sequence[str]) -> str:
    """Why keys for counties newer than the bundled (2017) boundaries match
    nothing, if any of them are."""
    codes = {code[1] for code in map(_county_code, keys) if code and code[0] == 'geoid'}
    names = {_normalize_name(k) for k in keys}
    newer = []
    if (any(c[:2] == '09' and '110' <= c[2:] <= '190' for c in codes)
            or any('planningregion' in n for n in names)):
        newer.append("Connecticut's nine planning regions, which took the place of its eight "
                     "counties in Census data from 2022")
    if codes & {'02063', '02066'} or names & {'chugach', 'copperriver'}:
        newer.append("Alaska's Chugach and Copper River census areas, which replaced "
                     "Valdez-Cordova in 2019")
    if not newer:
        return ''
    return (f" (The bundled boundaries are the Census's of 2017, so they don't have "
            f"{', or '.join(newer)}. Use the codes or names of 2017, or pass boundaries that "
            f"have them as geojson_path=.)")


def _unknown_codes_hint(keys: Sequence[str], country: bool, map_states) -> str:
    """Whose codes five-digit FIPS codes that matched nothing are: an
    island territory's, which the map of the country doesn't have, or a
    state's whose 2017 counties include none with that code. The
    warning used to list them without a word -- 40 codes from '2901' to
    '2940', Alaska's election districts as county-level election results
    have them, read as int; and the New York Times' '69110' and '78010',
    the Northern Mariana Islands and the Virgin Islands."""
    by_state: Dict[str, List[str]] = {}
    for key in keys:
        code = _county_code(key)
        if not code or code[0] != 'geoid':
            continue
        c = code[1]
        if (c[:2] == '09' and '110' <= c[2:] <= '190') or c in ('02063', '02066'):
            continue        # newer than the boundaries: _newer_boundaries_hint says so
        if country or (map_states and c[:2] in map_states):
            by_state.setdefault(c[:2], []).append(c)
    def listed(codes):
        codes = sorted(set(codes))
        return (repr(codes[0]) if len(codes) == 1 else f"{codes[0]!r} to {codes[-1]!r}" if len(codes) > 3
                else ', '.join(map(repr, codes))), len(codes)

    notes = []
    islands = [f for f in sorted(by_state) if f in _ISLAND_TERRITORIES and country]
    if islands:
        shown = [listed(by_state[f]) for f in islands]
        count = sum(k for _, k in shown)
        notes.append(f"{', '.join(text for text, _ in shown)} {'is' if count == 1 else 'are'} "
                     f"{'the code of an island territory' if count == 1 else 'codes of island territories'} "
                     f"({', '.join(STATES[f][1] for f in islands)}), which aren't on the map of the "
                     f"country: state='{STATES[islands[0]][0]}' draws "
                     f"{STATES[islands[0]][1] if len(islands) == 1 else 'one of them'} by itself")
    for f in sorted(by_state):
        if f in islands:
            continue
        shown, count = listed(by_state[f])
        if f in STATES:
            notes.append(f"{shown} {'is' if count == 1 else 'are'} {STATES[f][1]}'s "
                         f"code{'s' if count > 1 else ''}, but no county of {STATES[f][1]} "
                         f"on the bundled boundaries of 2017 has {'it' if count == 1 else 'them'}")
        else:
            notes.append(f"{shown}: {f} is no state's code")
    return f" ({'; '.join(notes)})" if notes else ''


def _close_matches_hint(keys: Sequence[str], counties: List[dict], matched=(),
                        state_name: Optional[str] = None, state_is_clear: bool = False) -> str:
    """For names that matched nothing: the map's county each is closest to
    in spelling, or the states it is a county of.

    A county that already has a value isn't suggested -- "'Bedford city'
    -- Radford?" pointed to a city in the data already, and following it
    gave the error "two values for Radford" -- unless the name is that
    county's with something added ('BIBB02'), which is a second row for
    it. When most of the names are the state's counties, the state is
    right, and a name of other states' counties ('Campbell', in Georgia
    data of 1890) is one the state's map doesn't have, not a sign that
    `state` is wrong."""
    import difflib
    by_alias = {alias: c['name'] for c in counties for alias in c['aliases'] if isinstance(alias, str)}
    matched = set(matched)
    index = _county_name_states()
    notes, gone = [], []
    for key in keys:
        if _county_code(key) or _split_state(key)[1]:
            continue
        name = _normalize_name(key)
        close = difflib.get_close_matches(name, list(by_alias), n=1, cutoff=0.75)
        if close and by_alias[close[0]] in matched:
            if name.startswith(close[0]):
                notes.append(f"{key!r} -- a second row for {by_alias[close[0]]}?")
            elif state_is_clear:
                gone.append(key)
        elif close:
            notes.append(f"{key!r} -- {by_alias[close[0]]}?")
        elif index.get(name) and not state_is_clear:
            states = sorted(STATES[f][1] for f in index[name])
            notes.append(f"{key!r} is a county of {', '.join(states[:3])}"
                         f"{' and more' if len(states) > 3 else ''}: is `state` right?")
        elif state_is_clear:
            gone.append(key)
    if gone and state_name:
        listed = ', '.join(map(repr, gone[:5])) + (' and more' if len(gone) > 5 else '')
        notes.append(f"{listed} {'is' if len(gone) == 1 else 'are'}n't among {state_name}'s "
                     f"counties on the bundled boundaries of 2017; counties are sometimes "
                     f"merged, renamed or divided")
    return f" ({'; '.join(notes[:5])})" if notes else ''


def _warn_county_or_city(matched_keys: Dict[str, str], counties: List[dict]) -> None:
    """Warn when a plain name was taken to be the county that shares it
    with an independent city -- Virginia's "Richmond", Maryland's
    "Baltimore" -- since the city is as likely to be meant."""
    names = {c['name'] for c in counties}
    taken = []
    for display, key in matched_keys.items():
        if _county_code(key) or ' County' not in display or 'county' in key.lower():
            continue
        city = display.replace(' County', ' City', 1)
        if city in names:
            taken.append(f"{key!r} to be {display}, not {city}")
    if taken:
        warnings.warn(
            f"county_map_chart took {'; '.join(taken)}. A county and an independent city share "
            f"{'that name' if len(taken) == 1 else 'those names'}: write \"... County\" or "
            f"\"... city\" to say which.", UserWarning, stacklevel=4)


def _check_map_options(label_by: str, n_classes) -> None:
    if label_by not in LABEL_ORDERS:
        raise ValueError(f"`label_by` must be one of {', '.join(map(repr, LABEL_ORDERS))}; "
                         f"got {label_by!r}.")
    if isinstance(n_classes, bool) or not isinstance(n_classes, (int, np.integer)) or n_classes < 1:
        raise ValueError(f"`n_classes` must be a whole number, 1 or more; got {n_classes!r}.")


def _project_state(regions: List[dict]) -> None:
    """
    Project every ring of every county once, up front -- reused for
    drawing, area ranking, and label placement alike -- with `_project`,
    centred on the state.
    """
    all_lons = [pt[0] for c in regions for ring in c['rings'] for pt in ring]
    all_lats = [pt[1] for c in regions for ring in c['rings'] for pt in ring]
    lon0 = (min(all_lons) + max(all_lons)) / 2
    cos_lat0 = math.cos(math.radians(sum(all_lats) / len(all_lats)))

    for c in regions:
        c['xy_rings'] = [np.array([_project(lon, lat, lon0, cos_lat0) for lon, lat in ring])
                          for ring in c['rings']]
        c['xy_holes'] = [np.array([_project(lon, lat, lon0, cos_lat0) for lon, lat in ring])
                          for ring in c['holes']]
        c['area'] = (sum(_polygon_area(ring) for ring in c['xy_rings'])
                     - sum(_polygon_area(ring) for ring in c['xy_holes']))


def _draw_map(regions: List[dict], matched_values: Dict[str, float], *, wanted,
              title, subtitle, value_format, palette, n_classes, missing_color, show_colorbar,
              colorbar_label, label_top_n, label_by, background, figsize, dpi, font, save_path,
              edge_width: float = 0.6, borders=None, mark_tiny: bool = False,
              chart: str = 'county_map_chart') -> plt.Figure:
    """
    Draw a choropleth of `regions` -- counties or states, each with its
    projected outline(s) (`xy_rings`), holes (`xy_holes`), `area` and
    `name` -- coloured by `matched_values` (name -> value): the colour
    classes, the figure's size, the regions, their labels and callouts,
    the colorbar and the title. `wanted` is the set of names to label, or
    None to choose by `label_top_n` and `label_by`. `borders` are outlines
    drawn over the regions (states over a country's counties),
    `mark_tiny` puts a dot on regions too small to see, and `chart` names
    the chart in warnings.
    """
    if value_format is not None:
        check_value_format(value_format)
    if palette is not None and palette not in _PALETTES:
        raise ValueError(f"`palette` must be one of {', '.join(map(repr, _PALETTES))}, or None "
                         f"for the default; got {palette!r}.")
    font = font_stack(font or _get_font())
    ink_color = _text_color_for(background)
    counties = regions

    all_xy = np.concatenate([r for c in counties for r in c['xy_rings']])
    x_min, x_max = all_xy[:, 0].min(), all_xy[:, 0].max()
    y_min, y_max = all_xy[:, 1].min(), all_xy[:, 1].max()

    # ------------------------------------------------------------------
    # Color classes: bin matched values into n_classes using quantile
    # breaks (equal COUNT per class) rather than equal-width bins, so a
    # handful of outlier counties can't collapse everyone else into one
    # class -- the standard choropleth-cartography default.
    # ------------------------------------------------------------------
    if matched_values:
        all_values = np.array(list(matched_values.values()), dtype=float)
        edges, discrete = _classify(all_values, n_classes)
        n_used = len(edges) if discrete else len(edges) - 1
        seq_colors = _class_colors(palette, edges, n_used)
        if missing_color is None:
            missing_color = (MISSING_COLOR_BESIDE_BLUE if _has_blue_classes(palette, edges, n_used)
                             else MISSING_COLOR)
        if value_format is None:
            value_format = _boundary_format(edges, all_values, discrete)
    else:
        edges, discrete, n_used, seq_colors = None, False, 0, []
    missing_color = missing_color or MISSING_COLOR

    def _class_color(value: float) -> str:
        if edges is None:
            return missing_color
        if discrete:
            idx = int(np.searchsorted(edges, value))
        else:
            idx = int(np.searchsorted(edges, value, side='right')) - 1
        return seq_colors[max(0, min(idx, n_used - 1))]

    # ------------------------------------------------------------------
    # Figure sizing: solved exactly rather than guessed. A rough
    # "+1.6 inches for title and colorbar" fudge factor was tried first
    # and left a large blank gap between the map and the colorbar --
    # because the axes uses `set_aspect('equal')`, matplotlib shrinks
    # the actual rendered map to whatever fits the more constraining
    # dimension of its allocated box, and a guessed-at box whose aspect
    # ratio doesn't exactly match the map's left empty space rather than
    # a full-bleed map. Solved instead: fix the width, measure how much
    # vertical room the title actually needs at that width, then compute
    # the exact axes height an equal-aspect map of this shape requires
    # and size the figure to precisely that -- the same "solve the
    # geometry, don't guess it" approach already used in spiral.py and
    # pie.py.
    # ------------------------------------------------------------------
    lat_span = y_max - y_min
    lon_span = x_max - x_min
    base_w = 9.0
    map_w_in = None                     # the map's width, when narrower than 90% of the figure
    auto_size = figsize is None         # then callouts may also widen the figure
    if figsize is None:
        # 9 inches wide, unless that makes a tall state's map more than 10
        # inches tall: then narrower, down to 5 (Delaware, at 9 wide, would
        # be 21 inches tall). Past that the figure stays 5 inches wide, for
        # the title and colorbar, and the map narrows inside it.
        aspect = lat_span / lon_span if lon_span else 1.0
        if 0.9 * base_w * aspect > 10.0:
            base_w = max(5.0, 10.0 / aspect / 0.9)
            if 0.9 * base_w * aspect > 10.0:
                map_w_in = 10.0 / aspect
        figsize = (base_w, base_w)  # placeholder height; corrected below
    validate_figsize(figsize, dpi)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    fig_w_px = figsize[0] * dpi

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
                       + (20 if title_lines or subtitle_lines else 0))

    colorbar_reserve_px = 90 if show_colorbar else 20

    # The axes spans 90% of the figure's width (5% margin each side);
    # under equal aspect, its height in pixels is fixed by that width
    # and the map's true (padded) lon/lat aspect ratio -- not a free
    # choice, so solve for it rather than assume a height and hope.
    axes_w_px = map_w_in * dpi if map_w_in else 0.90 * fig_w_px
    pad_x, pad_y = lon_span * 0.03, lat_span * 0.03
    padded_lon = lon_span + 2 * pad_x
    padded_lat = lat_span + 2 * pad_y
    axes_h_px = axes_w_px * (padded_lat / padded_lon)

    fig_h_px = title_block_px + axes_h_px + colorbar_reserve_px
    figsize = (figsize[0], fig_h_px / dpi)
    fig.set_size_inches(figsize[0], figsize[1], forward=True)
    fig_h_px = figsize[1] * dpi  # recompute from the now-final inches, exact

    axes_top_frac = 1 - title_block_px / fig_h_px
    axes_bottom_frac = colorbar_reserve_px / fig_h_px
    axes_w_frac = axes_w_px / fig_w_px
    ax = fig.add_axes([(1 - axes_w_frac) / 2, axes_bottom_frac, axes_w_frac,
                       axes_top_frac - axes_bottom_frac])
    ax.set_facecolor(background)
    ax.set_xlim(x_min - pad_x, x_max + pad_x)
    ax.set_ylim(y_min - pad_y, y_max + pad_y)
    ax.set_aspect('equal')
    ax.axis('off')

    px_per_data = axes_w_px / padded_lon

    # Colorbar geometry, in fractions of the figure's height as designed
    # for Georgia, but capped at Georgia's sizes in inches: a 24-inch-tall
    # map of the Northern Mariana Islands got a bar 100px thick. Its label
    # sits partly inside the map's frame, so callouts are kept off it
    # (one of Michigan's was printed over it).
    cb_h_frac = min(0.028, 0.29 * dpi / fig_h_px)
    cb_gap_frac = min(0.022, 0.23 * dpi / fig_h_px)
    cb_tick_frac = min(0.008, 0.083 * dpi / fig_h_px)
    cb_y = axes_bottom_frac * 0.35
    cb_w_scale = 1.0                    # less, when callouts widen the figure
    cb_label_box = None
    if show_colorbar and colorbar_label and edges is not None:
        label_w_px, label_h_px = tu.measure_text_px(fig, colorbar_label, 9, font, 'bold')
        bottom_px = (cb_y + cb_h_frac + cb_gap_frac) * fig_h_px
        to_data = ax.transData.inverted()
        (bx0, by0), (bx1, by1) = to_data.transform([(fig_w_px / 2 - label_w_px / 2 - 4, bottom_px - 4),
                                                    (fig_w_px / 2 + label_w_px / 2 + 4, bottom_px + label_h_px + 4)])
        cb_label_box = ((bx0 + bx1) / 2, (by0 + by1) / 2, abs(bx1 - bx0) / 2, abs(by1 - by0) / 2)

    # ------------------------------------------------------------------
    # Draw every county.
    # ------------------------------------------------------------------
    # add_artist, not add_patch: the limits are already set, and working
    # out each shape's own took four of the five seconds a map of the
    # country's 3,200 counties needed.
    for c in counties:
        value = matched_values.get(c['name'])
        color = _class_color(value) if value is not None else missing_color
        if not c['xy_holes']:
            for ring_xy in c['xy_rings']:
                poly = mpatches.Polygon(ring_xy, closed=True, facecolor=color,
                                          edgecolor=ink_color, linewidth=edge_width, zorder=2)
                ax.add_artist(poly)
        else:
            # Outlines wound one way and holes the other, in one path, so
            # the holes stay empty for the counties inside them.
            rings = ([_oriented(r, True) for r in c['xy_rings']]
                     + [_oriented(r, False) for r in c['xy_holes']])
            path = MplPath.make_compound_path(*[MplPath(r, closed=True) for r in
                                                [np.vstack([r, r[:1]]) for r in rings]])
            ax.add_artist(mpatches.PathPatch(path, facecolor=color, edgecolor=ink_color,
                                             linewidth=edge_width, zorder=2))
        if mark_tiny and c['area'] * px_per_data ** 2 < 12.0:
            # Too small to see (the District of Columbia on a map of the
            # country): a dot in its colour, where it is.
            cx, cy = _polygon_centroid(max(c['xy_rings'], key=_polygon_area))
            ax.plot([cx], [cy], marker='o', markersize=4.5, markerfacecolor=color,
                    markeredgecolor=ink_color, markeredgewidth=0.6, zorder=4)
    for ring_xy in borders or ():
        ax.add_artist(mpatches.Polygon(ring_xy, closed=True, fill=False, edgecolor=ink_color,
                                       linewidth=0.6, zorder=3))

    # ------------------------------------------------------------------
    # County labels.
    #
    # Which counties: by default the highest and lowest values (see
    # `label_by`). This used to be the largest counties on the map,
    # whatever the data: on real unemployment data it labelled six big
    # rural counties with middling rates and none of the extremes.
    #
    # A name goes inside its county when it fits -- checked against the
    # polygon's real outline with matplotlib's own point-in-polygon test,
    # not a bounding-box guess (the lesson pie_chart's wedge-boundary bug
    # taught). When it doesn't, it becomes a callout: the name outside the
    # state, with a leader line to the county, like pie_chart's external
    # labels. Callouts matter here because the counties with the most
    # extreme rates are very often the smallest -- few residents, so a
    # handful of people moves the rate a lot -- and on that same
    # unemployment map the highest and lowest counties in the state were
    # both too small to hold their names.
    # ------------------------------------------------------------------
    if wanted is not None:
        chosen = [c for c in counties if c['name'] in wanted]
    elif label_top_n > 0:
        with_data = [c for c in counties if c['name'] in matched_values]
        chosen = _label_order(with_data, matched_values, label_by)[:label_top_n]
    else:
        chosen = []

    for c in chosen:
        c['_outline'] = max(c['xy_rings'], key=_polygon_area)  # the largest piece's outline
        c['_path'] = MplPath(c['_outline'])

    label_pad_px = 2.0      # keep labels just clear of the boundary line
    anchors: Dict[Tuple[str, int], Optional[Tuple[float, float]]] = {}

    def _label_box(c, fontsize, pad_px):
        w_px, h_px = tu.measure_text_px(fig, c['name'], fontsize, font, 'bold')
        return (w_px / 2 + pad_px) / px_per_data, (h_px / 2 + pad_px) / px_per_data

    def _anchor(c, fontsize):
        """Where c's name fits inside c at this size (cached), or None."""
        key = (c['name'], fontsize)
        if key not in anchors:
            half_w, half_h = _label_box(c, fontsize, label_pad_px)
            anchors[key] = _label_anchor(c['_outline'], c['_path'], half_w, half_h,
                                         spacing=4.0 / px_per_data)
        return anchors[key]

    # A single SHARED fontsize for every label on the map, rather than
    # each county's label independently maximizing its own size against
    # its own shape -- checked with actual rendered text properties, not
    # assumed: two adjacent counties sized purely to fill their own very
    # differently-shaped polygons came out at roughly 6.6pt and 10.2pt
    # respectively, and bold text at the smaller of those two sizes
    # renders with visibly thinner, spindlier strokes than the same
    # weight at the larger size -- reading as a mismatched font on the
    # same map even though both were, technically, the same font and
    # weight. Solved by trying one shared size at a time, largest first.
    #
    # The size is the largest at which every chosen county that can hold
    # its name at all fits inside -- unless that's below 8pt, where map
    # labels get hard to read. Then labels stay at 8pt and the counties
    # too small for that become callouts, rather than every label
    # shrinking to fit the smallest county -- unless so many would that
    # the map fills with leader lines (more than eight, and more than two
    # thirds of the labels): then the largest size at which most (60%)
    # of the names that fit at all fit.
    # Counties too small for any size don't get a say: they're callouts
    # whatever size is picked (and counting them pinned every label on the
    # unemployment map at the smallest size).
    #
    # The test for 8pt counts callouts: it was "8pt if 60% of the names
    # that fit at all still fit at 8pt", which flipped on a pixel -- with a
    # Courier whose 6pt text is one pixel shorter, two small Georgia
    # counties began to fit at 6pt, the share at 8pt fell below 60%, and
    # every label on the map went to 6pt.
    label_sizes = (11, 10, 9, 8, 7, 6)
    comfortable_fs = 8
    can_fit = [c for c in chosen if _anchor(c, label_sizes[-1]) is not None]

    def _largest_size_fitting(share):
        return next((fs for fs in label_sizes
                     if sum(_anchor(c, fs) is not None for c in can_fit) >= share * len(can_fit)),
                    label_sizes[-1])

    # When no name fits inside its region at any size -- every label is a
    # callout, as on a map of the country's counties -- nothing sets the
    # size, and the largest (11pt) crowded the map. Callouts alone are 9pt.
    shared_fs = _largest_size_fitting(1.0) if can_fit else 9
    if shared_fs < comfortable_fs:
        if sum(_anchor(c, comfortable_fs) is None for c in chosen) <= max(8, 2 * len(chosen) // 3):
            shared_fs = comfortable_fs
        else:
            shared_fs = max(shared_fs, min(_largest_size_fitting(0.6), comfortable_fs))
    inside = [c for c in chosen if _anchor(c, shared_fs) is not None]
    callouts = [c for c in chosen if _anchor(c, shared_fs) is None]

    for c in inside:
        cx, cy = _anchor(c, shared_fs)
        value = matched_values.get(c['name'])
        fill_color = _class_color(value) if value is not None else missing_color
        ax.text(cx, cy, c['name'], ha='center', va='center', fontsize=shared_fs,
                 fontweight='bold', fontfamily=font,
                 color=_text_color_for(fill_color), zorder=6)

    if callouts:
        # Callouts go in the free space around the state -- inside the
        # map's frame, in the figure's margins beside it, or further out,
        # above and below the map and (when the figure's size is ours to
        # choose) past its sides, which makes the figure bigger and so
        # costs a little. Within the frame alone, a state that fills it
        # (Colorado, Kansas) had nowhere for a callout and silently left
        # the county unlabelled, and on long narrow ones (Tennessee,
        # Pennsylvania) labels landed far from their counties, with
        # leader lines across the state.
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        cell = 3.0 / px_per_data
        edge_px = 6.0
        side_room = max(0.0, (fig_w_px - axes_w_px) / 2 - edge_px) / px_per_data
        reach_x = side_room + (2.0 * dpi / px_per_data if auto_size else 0.0)
        reach_y = 1.5 * dpi / px_per_data
        ext_x, ext_y = int(reach_x / cell), int(reach_y / cell)
        # The land is the same whether marked county by county or, faster,
        # by the states' outlines.
        # Names side by side an em apart (see _FreeSpace).
        em = shared_fs * dpi / 72 / px_per_data
        space = _FreeSpace([{'xy_rings': borders}] if borders else counties, xlim, ylim,
                           cell=cell, grow_cells=2, extend=(ext_x, ext_x, ext_y, ext_y),
                           label_gap=em)
        for c in inside:
            space.take_label(*_anchor(c, shared_fs), *_label_box(c, shared_fs, label_pad_px))
        if cb_label_box is not None and cb_label_box[1] + cb_label_box[3] > ylim[0]:
            space.take_label(*cb_label_box)
        # The frame as the grid covers it, and what the figure has room for.
        frame = (xlim[0], xlim[0] + math.ceil((xlim[1] - xlim[0]) / cell) * cell,
                 ylim[0], ylim[0] + math.ceil((ylim[1] - ylim[0]) / cell) * cell)
        mid_x = (xlim[0] + xlim[1]) / 2
        room = [frame[0] - side_room, frame[1] + side_room, frame[2], frame[3]]
        base = space.snapshot()
        placed, unplaced = [], []
        for c in callouts:              # in label order: the most important get the nearest spots
            half_w, half_h = _label_box(c, shared_fs, 3.0)
            start = _interior_point(c['_outline'], c['_path'])
            spot = space.best_spot(start, half_w, half_h, room=room,
                                   leaders=[(p['start'], p['end']) for p in placed],
                                   cross_cost=0.5 * dpi / px_per_data)
            if spot is None:
                unplaced.append(c['name'])
                continue
            (tx, ty), end = spot
            space.take_label(tx, ty, half_w, half_h)
            space.take_leader(start, end)
            placed.append({'name': c['name'], 'start': start, 'centre': (tx, ty), 'end': end,
                           'half_w': half_w, 'half_h': half_h})
            box = (tx - half_w, tx + half_w, ty - half_h, ty + half_h)
            half = max(mid_x - min(room[0], box[0]), max(room[1], box[1]) - mid_x)
            room = [mid_x - half, mid_x + half, min(room[2], box[2]), max(room[3], box[3])]
        _uncross_callouts(placed, space, base, room=room, cross_cost=0.5 * dpi / px_per_data)

        content = list(frame)
        halo = [patheffects.Stroke(linewidth=2.6, foreground=background), patheffects.Normal()]
        for p in placed:
            (sx, sy), (tx, ty), (ex, ey) = p['start'], p['centre'], p['end']
            ax.plot([sx, ex], [sy, ey], color=ink_color, linewidth=0.8,
                    solid_capstyle='round', zorder=5, path_effects=halo)
            ax.plot([sx], [sy], marker='o', markersize=2.5, color=ink_color,
                    zorder=5.5, path_effects=halo)
            ax.text(tx, ty, p['name'], ha='center', va='center', fontsize=shared_fs,
                    fontweight='bold', fontfamily=font, color=ink_color, zorder=6)
            content = [min(content[0], tx - p['half_w']), max(content[1], tx + p['half_w']),
                       min(content[2], ty - p['half_h']), max(content[3], ty + p['half_h'])]
        if unplaced:
            warnings.warn(
                f"{chart}: no room for {len(unplaced)} of the labels, left off: "
                f"{unplaced}. Fewer labels (`label_top_n`), or a bigger `figsize`, would "
                f"fit them.",
                stacklevel=4,
            )

        # Make room for callouts outside the frame: the map keeps its
        # scale and stays centred, and the figure grows around it.
        if content[0] < frame[0] or content[1] > frame[1] or content[2] < frame[2] or content[3] > frame[3]:
            half_x = max(mid_x - content[0], content[1] - mid_x, (xlim[1] - xlim[0]) / 2)
            new_x = (mid_x - half_x, mid_x + half_x)
            new_y = (ylim[0], max(ylim[1], content[3]))
            if content[2] < frame[2]:
                # Below the map: the colorbar's label rises a little into
                # the map's frame, so leave it that much room under them.
                rise = (max(0.0, cb_label_box[1] + cb_label_box[3] - ylim[0])
                        if cb_label_box is not None else 0.0)
                new_y = (content[2] - rise - 4.0 / px_per_data, new_y[1])
            old_w_px, old_h_px = fig_w_px, fig_h_px
            axes_w_px = (new_x[1] - new_x[0]) * px_per_data
            axes_h_px = (new_y[1] - new_y[0]) * px_per_data
            fig.set_size_inches(max(fig_w_px, axes_w_px + 2 * edge_px) / dpi,
                                (title_block_px + axes_h_px + colorbar_reserve_px) / dpi, forward=True)
            fig_w_px, fig_h_px = (float(v) * dpi for v in fig.get_size_inches())
            ax.set_position([(1 - axes_w_px / fig_w_px) / 2, colorbar_reserve_px / fig_h_px,
                             axes_w_px / fig_w_px, axes_h_px / fig_h_px])
            ax.set_xlim(*new_x)
            ax.set_ylim(*new_y)
            # The colorbar keeps its size in pixels.
            k = old_h_px / fig_h_px
            cb_y, cb_h_frac, cb_gap_frac, cb_tick_frac = (v * k for v in
                                                          (cb_y, cb_h_frac, cb_gap_frac, cb_tick_frac))
            cb_w_scale = old_w_px / fig_w_px

    # ------------------------------------------------------------------
    # Colorbar: a manually-built discrete legend rather than matplotlib's
    # own colorbar machinery, so it matches this package's font/ink
    # conventions instead of matplotlib's defaults.
    # ------------------------------------------------------------------
    if show_colorbar and edges is not None:
        # Swatches keep the default seven-class width when there are fewer
        # classes (a single class shouldn't be a 60%-wide slab), and the
        # bar stays centred.
        seg_w = 0.60 / max(n_used, 7) * cb_w_scale
        cb_x0 = 0.5 - seg_w * n_used / 2
        for i, color in enumerate(seq_colors):
            fig.patches.append(mpatches.Rectangle(
                (cb_x0 + i * seg_w, cb_y), seg_w, cb_h_frac,
                transform=fig.transFigure, facecolor=color,
                edgecolor=ink_color, linewidth=0.6,
            ))
        # Class boundaries go at swatch edges; discrete classes are
        # labelled with their value, centred under the swatch.
        tick_x = [cb_x0 + (i + 0.5) * seg_w for i in range(n_used)] if discrete else \
                 [cb_x0 + i * seg_w for i in range(n_used + 1)]
        tick_text = [format_value(value_format, e) for e in edges]
        tick_fs, shown = _fit_tick_labels(fig, tick_text, seg_w * fig_w_px, font)
        for i in shown:
            fig.text(tick_x[i], cb_y - cb_tick_frac, tick_text[i],
                      ha='center', va='top', fontsize=tick_fs, fontweight='bold',
                      fontfamily=font, color=ink_color)
        if colorbar_label:
            fig.text(0.5, cb_y + cb_h_frac + cb_gap_frac, colorbar_label, ha='center', va='bottom',
                      fontsize=9, fontweight='bold', fontfamily=font, color=ink_color)
        if any(c['name'] not in matched_values for c in counties):
            # Regions without a value get a swatch of their own beside the
            # bar, so the reader needn't guess what the extra colour means:
            # right of it, past its last label, or if there's no room
            # there, left of it.
            def reach(i):
                return tu.measure_text_px(fig, tick_text[i], tick_fs, font, 'bold')[0] / 2 / fig_w_px
            gap = 12.0 / fig_w_px
            need = max(seg_w, tu.measure_text_px(fig, 'No data', tick_fs, font, 'bold')[0] / fig_w_px)
            cb_x1 = cb_x0 + seg_w * n_used
            x = max([cb_x1] + [tick_x[i] + reach(i) for i in shown]) + gap
            if x + need > 1 - 6.0 / fig_w_px:
                x = min([cb_x0] + [tick_x[i] - reach(i) for i in shown]) - gap - need
            if x >= 6.0 / fig_w_px:
                sx = x + (need - seg_w) / 2
                fig.patches.append(mpatches.Rectangle(
                    (sx, cb_y), seg_w, cb_h_frac, transform=fig.transFigure,
                    facecolor=missing_color, edgecolor=ink_color, linewidth=0.6))
                fig.text(sx + seg_w / 2, cb_y - cb_tick_frac, 'No data', ha='center', va='top',
                         fontsize=tick_fs, fontweight='bold', fontfamily=font, color=ink_color)

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


@literal_text
def county_map_chart(
    data: Dict[str, float],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    value_format: Optional[str] = None,
    palette: Optional[str] = None,
    n_classes: int = 7,
    missing_color: Optional[str] = None,
    show_colorbar: bool = True,
    colorbar_label: Optional[str] = None,
    label_top_n: int = 6,
    label_by: str = 'extremes',
    label_counties: Optional[Sequence[str]] = None,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
    geojson_path: Optional[str] = None,
    state: Optional[str] = None,
) -> plt.Figure:
    """
    Render a Du Bois-styled choropleth map of a U.S. state's counties --
    Georgia's unless `state` says otherwise -- or of every county in the
    country.

    Parameters
    ----------
    data : Dict[str, float]
        County -> value: a dict, or a pandas Series indexed by county.
        Counties can be given by name, matched loosely (case-insensitive,
        ignoring a trailing "County" and punctuation/spacing), so
        "DeKalb", "dekalb county", "De Kalb" and the Census's "DeKalb
        County, Georgia" all match -- a name followed by another state
        ("Cook County, Illinois" on Georgia's map) is that state's county,
        not this one's. Or by FIPS code: 13089 or "13089" (state and
        county), "089" (county alone), or the Census GEO_ID
        "0500000US13089". A key that matches nothing is named in a
        warning, with the county it's closest to in spelling -- or, for
        a county the bundled 2017 boundaries no longer have (Shannon
        County, South Dakota, renamed Oglala Lakota in 2015), what became
        of it; if none match, or two keys name the same county, it's an
        error. A name a
        county shares with an independent city ("Richmond", Virginia) is
        taken to be the county, with a warning. Counties with no value,
        or a missing one (None, NaN), are drawn in `missing_color`; a
        value whose key is missing has no place, and is left out with a
        warning.
    value_format : str, optional
        `str.format`-style template used for the colorbar's tick labels.
        By default, plain numbers with as many decimals as the data use
        -- more if that's what it takes for no two class boundaries to
        print the same.
    palette : str, optional
        The colours of the classes: one of `dubois_charts.colors`'
        sequential palettes, light to dark -- `'crimson'`, `'gold'` or
        `'green'` -- or `'diverging'`: green below zero (blue after
        `set_colorblind_safe()`), darker the further below, and crimson
        from zero up. By default, crimson -- or diverging when the data
        have both negative and positive values, as changes, margins and
        differences do. Data with both signs always have a class
        boundary at zero, so no class holds both.
    n_classes : int
        How many discrete color classes to bin values into (the
        conventional choropleth approach -- easier to read and to
        reproduce than a smooth gradient). Classes hold equal numbers of
        counties. Fewer are used when tied values would leave a class
        empty, and when the data have no more distinct values than this,
        each value gets a class of its own, labelled with that value.
    missing_color : str, optional
        Fill color for counties with no data, which the colorbar shows as
        "No data". The default is distinct from every colour class for
        colour-blind readers too: a light cool gray, or on a diverging map
        for colour-blind readers, where it would be too like the pale
        blues, a dark one.
    label_top_n : int
        How many counties to label with their name, if `label_counties`
        isn't given. 0 turns automatic labels off.
    label_by : str
        Which counties get those labels:

        - ``'extremes'`` (default): the highest and lowest values,
          alternately -- highest, lowest, second highest, second
          lowest, and so on.
        - ``'highest'`` or ``'lowest'``: one end only.
        - ``'area'``: the largest counties on the map, whatever their
          values.

        Ties go to the larger county. A name goes inside its county when
        it fits; when it doesn't, it's placed just outside the state
        with a leader line to the county (a callout). That matters for
        rates: the most extreme values are often in the smallest
        counties. Callouts go in the nearest free space -- around the
        state, in the figure's margins, or past them, in which case the
        figure grows to fit (the map keeps its size; a `figsize` width
        is kept, and the figure grows only in height). A county with no
        room anywhere is left unlabelled, with a warning.
    label_counties : Sequence[str], optional
        Explicit list of counties to label, by name or FIPS code,
        overriding `label_top_n` and `label_by`. Counties too small for
        their name get callouts, as above.
    geojson_path : str, optional
        Your own county boundaries, as a GeoJSON file, instead of the
        bundled ones. Each feature needs its county's name under `NAME`
        (or `name`, `NAMELSAD`, `NAME_2`, `county`, ...), and FIPS codes
        match when it has `GEOID` (or `STATEFP` and `COUNTYFP`), as the
        Census's own files do. Counties in several pieces
        (MultiPolygons) and counties with holes in them are drawn
        whole. One state at a time: county names must be unique within
        the file.
    state : str or int, optional
        Which state's (or territory's) counties to draw, by name
        ('Ohio'), postal code ('OH') or FIPS code (39). Every state, DC,
        Puerto Rico and the island territories are bundled, from the
        Census's 2017 county boundaries. Where a county and an
        independent city share a name (Baltimore, St. Louis, Fairfax,
        Franklin, Richmond, Roanoke), they're labelled "... County" and
        "... City".

        ``'US'`` draws every county in the country: the lower 48 states,
        Alaska and Hawaii inset below them, and Puerto Rico off Florida
        when the data include it, with the states' borders drawn over
        the counties'. County names repeat from state to state, so there
        counties are keyed by FIPS code or by name with their state
        ("Cook County, Illinois", "Cook, IL"), and labelled "Cook, IL".

        If `state` isn't given, data whose keys all say their state --
        five-digit FIPS codes, or names like "Cook County, Illinois" --
        draw that state, or the whole country when they span several.
        Plain names that are the counties of one state only draw that
        state ("Cuyahoga", "Franklin", "Hamilton": Ohio). Otherwise the
        map is Georgia's, as Du Bois's own maps were -- with a warning
        when the names are counties of other states too, and an error
        when they're all counties of several other states but not of
        Georgia. For data by state rather than county, see
        `state_map_chart`.

        The boundaries are the Census's of 2017, so they don't have later
        changes: Connecticut's planning regions, which replaced its
        counties in Census data from 2022, or Alaska's Chugach and Copper
        River census areas (2019). For those, pass boundaries that have
        them as `geojson_path`.
    title, subtitle : str, optional
        Wrapped and auto-sized to fit the figure width. The title is in
        capitals, as on the plates, except words whose mixed case is
        deliberate; the subtitle is as written.
    show_colorbar : bool
        If True, the colour classes are shown in a bar under the map,
        with their boundaries, and a "No data" swatch when some counties
        have no value.
    colorbar_label : str, optional
        Text above the colour bar -- what the values are.
    background : str
        The figure's colour: the cream of the plates' paper by default.
    figsize : (float, float), optional
        If not given, 9 inches wide -- narrower, down to 5, for a tall
        state, so its map is at most 10 inches tall -- and as tall as the
        map, title and colour bar need.
    dpi : int
        Dots per inch, for the figure and for `save_path`.
    font : str or sequence of str, optional
        The font for all the text; by default the typewriter face the
        package picks (see the README's "Fonts").
    save_path : str, optional
        If given, save the figure here.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = county_map_chart(
    ...     data={'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61},
    ...     title="Percentage Reporting Literacy, By County",
    ... )
    >>> fig = county_map_chart({'Cuyahoga': 4.9, 'Franklin': 3.8, 'Hamilton': 4.1}, state='OH')
    >>> fig = county_map_chart({'17031': 5.1, '48201': 4.3, '06037': 4.8})   # three states: the country
    """
    _check_map_options(label_by, n_classes)

    items = _map_items(data, 'county_map_chart', 'county')
    if geojson_path is not None and state is not None:
        raise ValueError("Pass `state` or `geojson_path`, not both: `state` picks one of the "
                         "bundled states, `geojson_path` your own boundaries.")
    country = state is not None and _is_country(state)
    # The states the data name: by five-digit FIPS codes, or as the
    # Census writes names, "Cook County, Illinois". None when some keys
    # don't say.
    key_states = [_key_state(key) for key, _ in items]
    named = None if None in key_states else set(key_states)
    if geojson_path is None and state is None:
        # Data that say which state they're for draw that state: a
        # California data set keyed 06001, 06003, ... draws California.
        # Several states draw the whole country.
        if named and len(named) > 1:
            country = True
        elif named and next(iter(named)) in STATES:
            state = next(iter(named))
        else:
            state = _state_for_names([key for key, _ in items])
    if country:
        # Puerto Rico only when the data have it; the island territories
        # aren't on the map of the country.
        counties = _load_us_counties(_country_states(set(key_states)))
        source = 'the United States'
    elif geojson_path is None:
        fips = state_fips(state)
        # Georgia keeps its own bundled boundaries, drawn exactly as before.
        counties = _load_counties(_DEFAULT_GEOJSON_PATH) if fips == '13' else _load_state_counties(fips)
        source = STATES[fips][1]
    else:
        counties = _load_counties(geojson_path)
        source = os.path.basename(geojson_path)
    if not counties:
        raise ValueError(f"No counties loaded from {source!r}.")
    # Values are matched to counties by name, so a name that appears twice
    # (Washington County is in 30 states) would get one county's value
    # drawn in both. (On the map of the country, names go with their state.)
    name_counts = Counter(_normalize_name(c['name']) for c in counties)
    repeated = sorted({c['name'] for c in counties if name_counts[_normalize_name(c['name'])] > 1})
    if repeated and not country:
        raise ValueError(
            f"County names repeat in {source!r} ({', '.join(repeated[:5])}"
            f"{', ...' if len(repeated) > 5 else ''}): county_map_chart draws one state at a "
            f"time, so give it a boundary file for one state -- or state='US' for the bundled "
            f"map of the whole country.")

    lookup = {alias: c for c in counties for alias in c['aliases']}
    by_code = {}
    for c in counties:
        if c['geoid']:
            by_code[('geoid', c['geoid'])] = c
    # A county's three-digit code identifies it only within one state.
    if len({c['geoid'][:2] for c in counties if c['geoid']}) <= 1:
        for c in counties:
            if c['countyfp']:
                by_code[('countyfp', c['countyfp'])] = c

    # The states on the map, when the boundaries say: a county named with
    # another state ("Cook County, Illinois" on Georgia's map) is that
    # state's, not the map's county of the same name.
    map_states = {c['geoid'][:2] for c in counties if c['geoid']} or None

    def _find_county(key: str):
        code = _county_code(key)
        if code:
            return by_code.get(code)
        name, in_state = _split_state(key)
        if in_state is not None and map_states is not None and in_state not in map_states:
            return None
        if country:
            return lookup.get((in_state, name)) if in_state else None
        return lookup.get(name)

    matched_values: Dict[str, float] = {}
    matched_keys: Dict[str, str] = {}
    unmatched_inputs: List[str] = []
    for raw_name, value in items:
        county = _find_county(raw_name)
        if county is None:
            unmatched_inputs.append(raw_name)
        elif county['name'] in matched_values:
            raise ValueError(
                f"`data` has two values for {county['name']}: {matched_keys[county['name']]!r} "
                f"and {raw_name!r} both name it. Give each county one value.")
        else:
            matched_values[county['name']] = value
            matched_keys[county['name']] = raw_name

    if unmatched_inputs:
        hint = ''
        if not by_code and any(_county_code(k) for k in unmatched_inputs):
            hint = (" (Some look like FIPS codes, but the boundary file has no GEOID or "
                    "COUNTYFP property to match them against.)")
        elif all(_state_code(k) and not _county_code(k) for k in unmatched_inputs):
            hint = " (They look like states: for data by state, use state_map_chart.)"
        elif country and any(not _county_code(k) and _split_state(k)[1] is None
                             for k in unmatched_inputs):
            hint = (" (County names repeat from state to state, so on the map of the whole "
                    "country give the state too -- 'Cook County, Illinois' -- or the FIPS code.)")
        elif not country and {_key_state(k) for k in unmatched_inputs} - {None} - (map_states or set()):
            hint = " (Some are other states' counties: state='US' draws the whole country.)"
        hint += _newer_boundaries_hint(unmatched_inputs)
        retired, explained = (_retired_hint(unmatched_inputs, map_states)
                              if geojson_path is None else ('', []))
        rest = [k for k in unmatched_inputs if k not in explained]
        if rest and not hint and not country:
            # Most of the names matched: the state is the right one.
            clear = len(matched_values) >= 0.8 * (len(matched_values) + len(unmatched_inputs))
            only_state = next(iter(map_states)) if map_states and len(map_states) == 1 else None
            hint = _close_matches_hint(rest, counties, matched_values,
                                       STATES[only_state][1] if only_state in STATES else None, clear)
        for more in (retired, _unknown_codes_hint(rest, country, map_states)
                     if geojson_path is None else ''):
            if hint.endswith(')') and more:
                hint = f"{hint[:-1]}; {more[2:]}"     # one parenthesis for all
            else:
                hint += more
        if not matched_values:
            raise ValueError(
                f"county_map_chart: none of the keys in `data` matched a county in {source}: "
                f"{unmatched_inputs[:8]}{' ...' if len(unmatched_inputs) > 8 else ''}{hint}")
        shown = (f"{unmatched_inputs}" if len(unmatched_inputs) <= 12
                 else f"{unmatched_inputs[:12]} and {len(unmatched_inputs) - 12} more")
        warnings.warn(
            f"county_map_chart: {len(unmatched_inputs)} input name(s) did not "
            f"match any known county and will be ignored: {shown}{hint}",
            stacklevel=3,
        )
    if geojson_path is None:
        _warn_county_or_city(matched_keys, counties)

    if matched_values:
        numbers = as_numbers(list(matched_values.values()), "`data`",
                             names=list(matched_values.keys()))
        matched_values = {name: float(v) for name, v in zip(matched_values, numbers)}

    wanted = None
    if label_counties is not None:
        label_keys = category_labels(list(label_counties))
        found = [(_find_county(k), k) for k in label_keys]
        wanted = {c['name'] for c, _ in found if c is not None}
        unmatched_labels = [k for c, k in found if c is None]
        if unmatched_labels:
            warnings.warn(
                f"county_map_chart: {len(unmatched_labels)} name(s) in "
                f"`label_counties` did not match any known county and will "
                f"be silently skipped rather than labeled: {unmatched_labels}. "
                "This is the same name-matching `data` uses -- check for typos.",
                stacklevel=3,
            )

    borders = None
    if country:
        # Thin county lines, with the states' borders drawn over them.
        _project_country(counties)
        states = _load_us_states(sorted({c['state'] for c in counties}))
        _project_country(states)
        borders = [r for st in states for r in st['xy_rings']]
    else:
        _project_state(counties)
    return _draw_map(counties, matched_values, wanted=wanted, title=title, subtitle=subtitle,
                     value_format=value_format, palette=palette, n_classes=n_classes,
                     missing_color=missing_color, show_colorbar=show_colorbar,
                     colorbar_label=colorbar_label, label_top_n=label_top_n, label_by=label_by,
                     background=background, figsize=figsize, dpi=dpi, font=font,
                     save_path=save_path, edge_width=0.15 if country else 0.6, borders=borders)


@literal_text
def state_map_chart(
    data: Dict[str, float],
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    value_format: Optional[str] = None,
    palette: Optional[str] = None,
    n_classes: int = 7,
    missing_color: Optional[str] = None,
    show_colorbar: bool = True,
    colorbar_label: Optional[str] = None,
    label_top_n: int = 6,
    label_by: str = 'extremes',
    label_states: Optional[Sequence[str]] = None,
    background: str = COLOR_CREAM,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
    font: Optional[str] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Render a Du Bois-styled choropleth map of the United States by state:
    the lower 48 states, with Alaska and Hawaii inset below them, and
    Puerto Rico off Florida when the data include it -- the way Du Bois
    mapped the country for the 1900 Paris Exposition, shaded state by
    state.

    Parameters
    ----------
    data : Dict[str, float]
        State -> value: a dict, or a pandas Series indexed by state. A
        state can be given by name ('Georgia', 'georgia'), postal code
        ('GA'), FIPS code (13 or '13') or Census GEO_ID ('0400000US13');
        the District of Columbia as 'District of Columbia', 'DC' or
        'Washington, D.C.'. Keys that match no state are named in a
        warning; if none match, or two keys name the same state, it's an
        error. Guam, the U.S. Virgin Islands, American Samoa and the
        Northern Mariana Islands aren't on the map. States with no value,
        or a missing one (None, NaN), are drawn in `missing_color`; a
        value whose key is missing has no place, and is left out with a
        warning.
    label_top_n, label_by
        As in `county_map_chart`: by default the three highest and three
        lowest states are labelled with their names -- inside the state
        when the name fits, otherwise outside it with a leader line (a
        callout), as for the small states of the Northeast.
    label_states : Sequence[str], optional
        The states to label, in any of the forms `data` takes,
        overriding `label_top_n` and `label_by`.

    The other parameters are as for `county_map_chart`. The District of
    Columbia, too small to see at this scale, is marked with a dot in its
    colour.

    Returns
    -------
    plt.Figure

    Examples
    --------
    >>> fig = state_map_chart({'California': 39.0, 'Texas': 30.5, 'Florida': 22.6},
    ...                       title='Population by state, millions')
    """
    _check_map_options(label_by, n_classes)
    items = _map_items(data, 'state_map_chart', 'state')
    codes = [(_state_code(key), key, value) for key, value in items]
    regions = _load_us_states(_country_states({code for code, _, _ in codes}))
    by_code = {r['geoid']: r for r in regions}

    matched_values: Dict[str, float] = {}
    matched_keys: Dict[str, str] = {}
    unmatched: List[str] = []
    off_map: List[str] = []
    for code, key, value in codes:
        if code in by_code:
            name = by_code[code]['name']
            if name in matched_values:
                raise ValueError(
                    f"`data` has two values for {name}: {matched_keys[name]!r} and {key!r} both "
                    f"name it. Give each state one value.")
            matched_values[name] = value
            matched_keys[name] = key
        elif code is not None:
            off_map.append(key)
        else:
            unmatched.append(key)
    hint = ''
    if unmatched and all(_county_code(k) or _split_state(k)[1] for k in unmatched):
        hint = " (They look like counties: for data by county, use county_map_chart.)"
    if not matched_values:
        raise ValueError(
            f"state_map_chart: none of the keys in `data` is a state on the map: "
            f"{(unmatched + off_map)[:8]}{' ...' if len(unmatched) + len(off_map) > 8 else ''}"
            f"{hint or ' (The island territories are not drawn.)' * bool(off_map and not unmatched)}")
    if unmatched:
        warnings.warn(
            f"state_map_chart: {len(unmatched)} key(s) matched no state and will be "
            f"ignored: {unmatched}{hint}",
            stacklevel=3,
        )
    if off_map:
        warnings.warn(
            f"state_map_chart: {off_map} {'is' if len(off_map) == 1 else 'are'} not on the map "
            f"of the country (the island territories aren't drawn), and will be ignored.",
            stacklevel=3,
        )
    if matched_values:
        numbers = as_numbers(list(matched_values.values()), "`data`",
                             names=list(matched_values.keys()))
        matched_values = {name: float(v) for name, v in zip(matched_values, numbers)}

    wanted = None
    if label_states is not None:
        keys = category_labels(list(label_states))
        found = [(by_code.get(_state_code(k)), k) for k in keys]
        wanted = {r['name'] for r, _ in found if r is not None}
        missing = [k for r, k in found if r is None]
        if missing:
            warnings.warn(
                f"state_map_chart: {len(missing)} name(s) in `label_states` matched no state "
                f"on the map and won't be labelled: {missing}.",
                stacklevel=3,
            )

    _project_country(regions)
    return _draw_map(regions, matched_values, wanted=wanted, title=title, subtitle=subtitle,
                     value_format=value_format, palette=palette, n_classes=n_classes,
                     missing_color=missing_color, show_colorbar=show_colorbar,
                     colorbar_label=colorbar_label, label_top_n=label_top_n, label_by=label_by,
                     background=background, figsize=figsize, dpi=dpi, font=font,
                     save_path=save_path, mark_tiny=True, chart='state_map_chart')
