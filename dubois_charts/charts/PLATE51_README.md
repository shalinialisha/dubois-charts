# Plate 51 Recreation: Pixel-Verified Reference Implementation

## What changed since the first draft

The first version of this recreation was built from memory/secondary
descriptions and got the chart **backwards**: it inverted the y-axis and put
black (slaves) as a mountain at the *top* with green (free) as a sliver at
the bottom. That's wrong. This version was rebuilt after downloading the
actual scanned original and analyzing it pixel-by-pixel, and corrects that
completely.

## Source of truth

- **Original drawing**: Library of Congress, digital ID `ppmsca.33913`,
  reproduction number `LC-DIG-ppmsca-33913`, call number LOT 11931, no. 51
  (M) [P&P]. Ink and watercolor on board, 710 x 560 mm, ca. 1900.
- **Archive copy used for analysis**: `original-plate-51.jpg`, downloaded
  from `ajstarks/dubois-data-portraits` (a GitHub archive of the plates and
  their transcribed data), saved in this folder as
  `reference-original-plate-51.jpg` for anyone who wants to re-verify or
  re-run the comparison.
- **Data**: `plate51/data.csv` from the same archive, cross-checked against
  the percentage labels hand-written on the original drawing itself.

## How the analysis was actually done

Rather than eyeballing a downscaled thumbnail, the image was loaded with
PIL/numpy and measured directly:

1. **Colors** were sampled and averaged over clean regions of each fill
   (green, black, cream paper background), away from text and edges.
2. **The chart's bounding box** was found by scanning rows/columns for the
   green-or-black fill boundary against the cream background.
3. **The data boundary curve** (the wavy line separating "free" from
   "slave") was traced column-by-column: for each year's x-position, scan
   from the bottom of the image upward and record the first green pixel.
   Converting that pixel row to a percentage and comparing against
   `data.csv` confirmed the mapping was correct to within ~1-2 points
   (consistent with hand-drawn imprecision).
4. **The "cliff"** between 1860 and 1870 was traced the same way and turned
   out to be a straight diagonal line from the 1860 boundary point down to
   the bottom-right corner -- i.e. exactly what you get from linearly
   interpolating the real data (free% jumps from 11 to 100 in one decade).
   No special-casing was needed once the orientation was fixed.

## The key correction

**The chart is not inverted.** It's an entirely ordinary, non-inverted
stacked-area chart:

| Layer | Position | Meaning | Typical size |
|---|---|---|---|
| Black | Bottom | SLAVES / ESCLAVES | 86-92% (huge) |
| Green | Top | FREE - LIBRE | 8-14% (thin ribbon) |

Because slaves were the overwhelming majority for 76 of the 80 years shown,
black dominates the chart as a heavy, oppressive mass, with only a thin
green strip of freedom above it -- until 1870, when the strip suddenly
becomes the whole chart. Du Bois didn't need an inverted axis or any other
trick to make this land; the history does the work when you just plot it
straight.

Other corrections from the first draft:

- **Years run along the top** of the chart, not the bottom.
- **There is no y-axis.** Du Bois hand-labeled the free-percentage directly
  on the boundary curve instead (`8%`, `11%`, `13.5%`, ... `100%`).
- **Colors are muted and hand-painted**, not vibrant/saturated digital
  tones -- see exact values below.

## Verified data

From `data.csv` (Atlanta University / U.S. Census), confirmed against the
pixel-traced boundary curve:

| Year | Slave % | Free % |
|---|---|---|
| 1790 | 92.0 | 8.0 |
| 1800 | 88.0 | 11.0 |
| 1810 | 86.5 | 13.5 |
| 1820 | 87.0 | 13.0 |
| 1830 | 86.0 | 14.0 |
| 1840 | 87.0 | 13.0 |
| 1850 | 88.0 | 12.0 |
| 1860 | 89.0 | 11.0 |
| 1870 | 0.0 | 100.0 |

Note: 1800's row (Slave=88, Free=11) sums to 99, not 100 -- verified as
a genuine feature of the source rather than a transcription slip (see
"Tech-debt audit and fixes" below). Every other year sums to exactly 100.

## Verified colors

Sampled directly from the source image (averaged over clean regions):

| Element | RGB | Hex |
|---|---|---|
| Green fill | (87, 132, 92) | `#57845c` |
| Black fill | (29, 29, 29) | `#1d1d1d` |
| Cream paper | (217, 210, 198) | `#d9d2c6` (used as `#ded7c9` in the rendered background) |

## Layout, verified by pixel measurement

- Chart bounding box in the source scan: left x=46, right x=751, top y=252,
  bottom y=994 (pixels, in a 799x1024 image).
- Years are evenly spaced across the full chart width, left (1790) to right
  (1870) -- confirmed by locating the year-label text clusters and checking
  their spacing (~88px per decade, consistent with even spacing).
- "FREE - LIBRE" sits centered, high in the green band.
- "SLAVES" / "ESCLAVES" sit centered in the black mass, two lines, in a
  warm off-white (not pure white).
- Percentage labels sit just above the boundary curve, inside the green
  band, at each year from 1790-1860; "100%" sits near the top right since
  the whole column is green at 1870.

## What this module does

`plate51.py` reproduces all of the above:

- `create_plate_51()` -- renders the recreation with verified data, colors,
  and layout. Includes optional hand-drawn boundary jitter and hand-painted
  brush texture (both subtle, tuned to be visible without turning into
  noise).
- `create_side_by_side()` -- renders the recreation next to the actual
  scanned original (`reference-original-plate-51.jpg`) for direct visual
  QA. This is the comparison that was used to iterate on accuracy.
- `main()` -- generates both and writes them to `plate51_recreation/`.

```python
from dubois_charts.charts.plate51 import create_plate_51, create_side_by_side

fig = create_plate_51(save_path='my_plate51.png')

# Compare directly against the scanned original
fig2 = create_side_by_side(save_path='comparison.png')
```

## Texture notes

The original is ink and watercolor on board, so both fills have visible,
irregular grain rather than flat digital color. This is reproduced with a
smoothed noise field (fine grain + faint vertical streaking to suggest
brush drag), rendered as a real per-pixel image and clipped to each fill
region -- plus a handful of crisp, sparse diagonal accent strokes, and
distinct thin vertical panel-divider lines in the green band (a clearly
visible feature of the original, likely from a straightedge-guided brush
stroke at each year mark).

This went through several rounds of calibration: the first pass was
essentially invisible at render resolution, an intermediate pass overshot
into a blotchy tie-dye pattern, and the current version aims for "reads as
grain at a glance" rather than either extreme.

## Tech-debt audit and fixes

This module got a `/engineering:tech-debt`-style audit after the other
four chart types (`area.py`, `bar.py`, `butterfly.py`, `spiral.py`) had
already been through stress-testing, shared-infrastructure extraction,
and a pytest regression suite -- `plate51.py` had none of that. Findings,
scored on `(Impact + Risk) x (6 - Effort)`:

| Item | Type | Priority | Fixed |
|---|---|---|---|
| Zero automated tests | Test debt | 32 | Yes -- `tests/test_plate51.py`, 27 tests |
| cwd-dependent file paths | Code debt | 30 | Yes |
| Duplicate `_get_font()` / `COLOR_CREAM` vs `_common.py` | Code debt | 20 | Yes |
| Missing reference image fails silently, keeps "ORIGINAL" label | Code debt | 20 | Yes |
| Dead `import random` (stdlib, never called) | Code debt | 10 | Yes |

Deliberately **not** flagged as debt: the hardcoded pixel positions
throughout the layout (`1828, 48` for SLAVES, `AXES_TOP = 0.775`, and so
on). Those look like debt at a glance -- magic numbers everywhere -- but
generalizing them would defeat the purpose of this specific module, which
exists to be the one bespoke, pixel-tuned recreation in the package (see
"What's still specific to plate51.py" in GENERAL_ENGINE_README.md).

**cwd-dependent paths**, in detail: `create_side_by_side()` defaulted
`original_path` to the bare filename `'reference-original-plate-51.jpg'`,
resolved against whatever directory the caller happened to be running
from. Called as `python3 plate51.py` from inside `dubois_charts/charts/`, that
works by accident. Imported and called from anywhere else -- which is
the normal way a package function gets used -- it silently produced a
blank "ORIGINAL" panel with no error. Fixed by resolving the default
against `os.path.dirname(__file__)` instead, so it works the same way
regardless of caller location; verified by actually calling it from an
unrelated `/tmp` directory rather than only reasoning about the fix.
The intermediate render (used only to reload the recreation as an image
array for side-by-side display) had the same class of problem one level
smaller -- a bare filename written to the cwd instead of a real temp
file -- fixed with `tempfile.mkstemp()` and a `try/finally` cleanup.

**Silent failure on a missing reference image**, in detail: even after
the path fix, `original_path` can still legitimately not exist (a typo,
a moved file). The old behavior left the right panel blank but still
titled "ORIGINAL (Library of Congress)" -- indistinguishable at a glance
from a successful comparison. Fixed to emit a `UserWarning` naming the
path that wasn't found, and to say so directly on the blank panel instead
of leaving it looking like a completed comparison.

**The 1800 data point**, found while writing a test that assumed every
row should sum to exactly 100: the archive's own `data.csv` has 1800 as
Slave=88 / Free=11, which is 99. Before treating that as a bug to fix,
it was checked against the actual pixel-traced boundary curve and the
literal "11%" hand-drawn on the original plate (both already documented
above) -- both confirm Free=11 is correct. The 1-point gap is a genuine
artifact of the original: Du Bois' team rounded slave% and free% as
independent columns from the underlying census fractions, and two
independently-rounded complementary percentages don't always land on a
clean 100. The test suite encodes this as a documented ~1-point tolerance
rather than either silently ignoring it or "correcting" the historical
data to satisfy a tidier invariant -- the latter would trade accuracy to
the source for a test that looks stricter than it should be.

**A missing `figsize`/`dpi` validation**, found later by deliberately
checking this module against a category of bug already fixed across all
seven general-purpose chart functions: `create_plate_51` exposes
`figsize` and `dpi` exactly like the others do, but had never been wired
up to the shared `validate_figsize` check those seven use. A degenerate
figsize like `(0, 0)` didn't fail where you'd expect -- calling the
function with no `save_path` succeeded outright, and the actual failure
only surfaced once a save was attempted, as a bare `SystemError: tile
cannot extend outside image` raised from inside PIL's PNG encoder,
naming neither `figsize` nor the real cause. Fixed by adding the same
`validate_figsize(figsize, dpi)` call the general engine already uses,
right before the figure is created.

## Remaining known gaps

- **Font**: the closest available monospace face (Liberation Mono / DejaVu
  Sans Mono, whichever resolves first) is a reasonable stand-in for the
  original's hand-lettered stencil-like caps, but isn't a precise match to
  the original letterforms.
- **Hand-drawn irregularity**: the boundary curve gets a light procedural
  jitter, but a real hand-drawn line has more character than smoothed
  noise can fully capture.

## Historical context

Du Bois and his students at Atlanta University created 63 of these
hand-painted charts for the "Exhibit of American Negroes" at the 1900 Paris
Exposition, using U.S. Census and Bureau of Labor data to make a visual,
data-driven case against racist pseudoscience -- only 35 years after
emancipation. This plate's stark, unadorned math (86-92% enslaved for
generation after generation, then a sudden vertical cliff to freedom) is
one of the most direct visual arguments in the entire series.
