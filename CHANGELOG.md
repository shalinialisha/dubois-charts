# Changelog

What changed in each version of dubois-charts. Versions are numbered
the [Semantic Versioning](https://semver.org) way; before 1.0, a new
minor version (0.3, 0.4, ...) may change how charts look or what they
accept.

## 0.2.0 - Unreleased

The first version meant for other people to install. Since 0.1.0:

### Renamed

- The package is **dubois-charts**, imported as **`dubois_charts`**
  (`import dubois_charts as dc`). It was `dubois-visualization-package`,
  imported as `dubois` -- a name an unrelated project already uses on
  PyPI, whose package installs a `dubois` folder of its own.

### Added

- Charts for your own data, eight kinds: `bar_chart` (single, grouped,
  and positive and negative values), `stacked_area_chart`,
  `butterfly_chart`, `spiral_chart`, `snake_chart`, `pie_chart`,
  `county_map_chart` and `state_map_chart`. Every title, label and
  callout is sized from measurements of the actual text: long titles
  wrap, long labels shrink and then wrap, and labels that can't fit move
  to a legend or a callout rather than overlap.
- Maps: the counties of any U.S. state, the District of Columbia, Puerto
  Rico or an island territory, or of the whole country, and the country
  by state, with Alaska and Hawaii inset as in Albers USA and Puerto Rico
  off Florida. Counties can be keyed by name in any common spelling, with
  or without their state, by FIPS code or by Census GEO_ID; without
  `state=`, codes, names with their state, and names only one state's
  counties have say which state to draw. `geojson_path=` draws your own
  boundaries. A key that matches nothing is named in a warning, with the
  nearest spelling, or what became of a county the 2017 boundaries no
  longer have (Shannon County, South Dakota, renamed Oglala Lakota;
  Campbell and Milton, Georgia, merged into Fulton); data that match
  nothing, or two keys for one place, are an error. A missing value is
  no data for that place. Values with both signs are shaded on a
  diverging scale, green (or blue) below zero and crimson above, with a
  class boundary at zero; `palette='diverging'` asks for it.
- Colour-blind readers: `set_colorblind_safe()` switches every chart's
  default colours to a palette that stays distinct for readers with any
  common colour-blindness; `get_categorical(n, colorblind_safe=True)`,
  `get_diverging(n, colorblind_safe=True)` and
  `simulate_colorblindness()`. Map colour scales step evenly from light
  to dark, and areas with no data get a colour no reader confuses with
  the scale, and a "No data" swatch.
- Data as it comes: pandas Series and DataFrames, numpy arrays, dates,
  `Decimal`, numeric strings; a Series matched to the categories by its
  index; numbers and dates printed the way a person writes them; a clear
  error, naming the category, for a missing value, a negative one where
  it can't be drawn, or a word where a number belongs.
- A tutorial, `docs/tutorial.ipynb`.
- `tools/check_real_data.py`, which draws every chart from about thirty
  public data files and reports what each did.
- About 1,050 tests, among them nineteen image comparisons and runs of
  every example in the README and the docstrings, run by GitHub Actions:
  Python 3.10 to 3.15 on Linux, the oldest numpy, matplotlib and scipy
  supported, and Python 3.10 and 3.15 on macOS and Windows.

### Changed

- Needs Python 3.10 or newer (it claimed 3.8) and matplotlib 3.6 or
  newer (it claimed 3.5, which can't keep "$" in labels from being read
  as maths). scipy is now a declared dependency; it was always needed.
- Colours no longer repeat after eight categories: up to twenty are
  clearly distinct, and past that a warning says when some look alike.
- Mac and Windows letter the charts in Courier New, as Linux does in
  Liberation Mono; DejaVu Sans Mono was chosen first.
- Charts of hundreds of bars, slices or snake pieces draw about twice as
  fast: the hand-painted texture of a whole chart is one picture.
- A bar's outline shows on its right-hand edge, as on the other three.
- `get_diverging(n)` returns `n` colours for an even `n` (it printed a
  note and returned `n + 1`).
- Legends read across each row and then down, take as many columns as
  fit, break a name too long for a line, and get the room they need.
- A snake chart's scale marks go under its rows, on the background.
- Map data that match no place are an error rather than a blank map, as
  are two keys for one place.
- The charts don't print "Saved: ..." when they save; `show_palette()`
  returns its figure rather than calling `plt.show()`.
- A `font` that isn't installed gets one warning, and the usual face,
  instead of matplotlib's message twenty times over.
- `reset_theme()` puts back only the settings `set_theme()` changed.

### Fixed

- The installed package couldn't draw: scipy wasn't required, and the
  map boundaries and the Plate 51 scan weren't included.
- Names and values in the area chart sat partly in the next band when
  the bands sloped; on a tightly wound spiral, leader lines crossed loop
  after loop, each other, and other labels.
- Labels that overlapped each other, ran off the figure or out of their
  shapes, in every chart type, on long names, many categories, tied or
  tiny values, sparse or irregular dates, and other awkward data.
- County maps labelled the largest counties instead of those the data
  picks out; colour classes broke on tied values; callouts went missing
  when the state filled its frame.
- In a Jupyter notebook whose first figure was one of these charts, no
  figure after it showed: drawing a chart switched matplotlib's
  interactive mode back off. `reset_theme()`, `dubois_style()` and
  `DuBoisStyle` did the same, and `reset_theme()` also undid settings of
  the user's own made after `set_theme()`.
- A pandas Series of values was taken in order, whatever its index: a
  pivot table's rows, sorted '0-4', '10-14', '5-9', put the 10-14
  figures on the 5-9 bar.
- Grouped bars were a pixel or two thick from five series, and upside
  down from six; legends ran off the figure, sat on the chart and read
  out of order.
- A snake chart's scale couldn't be read on a dark segment; a spiral's
  label could sit past the next loop out, and read as that loop's.
- Numbers printed with more digits than the data have ("0.01200"), and a
  butterfly chart's two sides shared one format ("1,250,000.0000" to show
  0.012 on the other side).
- One sliver of a snake, or thin bands in an area chart, took every name
  down to 7 or 8pt, though they never held their own.
- County names a county shares with an independent city ("Richmond",
  Virginia) were taken to be the county without a word; another state's
  county names, without `state=`, drew Georgia's counties of the same
  names; Connecticut's planning regions matched nothing, unexplained.
- `$` signs turned text into maths; forced capitals turned "iOS" into
  "IOS"; Chinese, Japanese and Korean labels were empty boxes; a sliver
  of a pie read "0%"; on Windows, "Doña Ana" came out garbled.
- Found by charting real public data -- Du Bois's own data for the
  plates, census, employment, election, COVID-19, energy and climate
  files: a row with no name (a total) was drawn as a bar called "nan",
  and a row given twice as two bars without a word; dates stored as
  midnight somewhere else read "2000-01-01 08:00"; x labels fell every
  40th month, "Jan 2000, May 2003", or ran together; halves rounded to
  even, so 4.5% read "4%" on a pie and "4.5%" on a bar; a pie of
  published percentages adding up to 100.5 relabelled them as shares of
  100.5; a snake chart named a segment without its number, listed the
  rest in its legend without any, and marked rows of 3.4 as "3" and "7";
  four years of months made 6.9 turns of a spiral, and labels ran into
  each other; a map with a missing value was an error; signed data shared
  a class across zero; callouts side by side read as one name; and a
  grouped bar's name sat level with its second bar. A second pass, with
  files read by `pd.read_csv` and nothing else: dates left as text were
  drawn as text; four years of days were labelled every 238th day, with
  a wobble at every point; sixty-six years were labelled tilted, every
  other year; three-decimal data printed "11,072.753", and a snake's
  marks "20.000%"; spirals of monthly CO2 and births tangled without a
  word; a NaN map key stopped the chart, and codes that matched nothing
  weren't explained; MultiIndex rows read "(2000, 1)"; and "7.47%" was
  only "not a number".

## 0.1.0

The first version, never published: Du Bois colour palettes,
matplotlib themes, the Plate 51 recreation, and the first chart
functions for your own data.
