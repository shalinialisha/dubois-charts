# The General-Purpose Chart Engine

## Why this exists

`plate51.py` is a pixel-verified recreation of one specific historical
drawing: fixed data, a fixed bilingual title, fixed category names
("SLAVES" / "FREE - LIBRE"), fixed at nine specific years. Every font size
and x/y position in it was hand-tuned to fit that exact text. That's the
right approach for a faithful historical recreation, but it is **not**
what someone reaches for to chart their own data — nothing about it takes
parameters, and none of its hardcoded positions would survive contact with
a title of different length or a category name longer than "FREE".

`dubois_charts/text_utils.py` and `dubois_charts/charts/_common.py` are the other
thing: shared, general infrastructure that any chart type in this package
uses to size and place text correctly for **whatever the caller's data
actually is**, not just a demo case. Eight chart types are built on it:

| Chart | Module | Layout shape |
|---|---|---|
| Stacked area | `area.py` | `stacked_area_chart()` |
| Horizontal bar (single or grouped) | `bar.py` | `bar_chart()` |
| Butterfly / mirror (two-sided) | `butterfly.py` | `butterfly_chart()` |
| Spiral | `spiral.py` | `spiral_chart()` |
| Snake (wrapped bar) | `snake.py` | `snake_chart()` |
| Pie / proportional circle | `pie.py` | `pie_chart()` |
| Choropleth (a state's, or the country's, counties) | `choropleth.py` | `county_map_chart()` |
| Choropleth (the country by state) | `choropleth.py` | `state_map_chart()` |

All eight take arbitrary categories, an arbitrary number of series, and a
title of whatever length the caller has, and still produce a readable,
non-overlapping result.

## Shared infrastructure, not duplicated per chart

`dubois_charts/charts/_common.py` holds the visual vocabulary every chart type
needs regardless of its own layout logic: font detection (`get_font`),
contrast-aware ink color for text drawn on an arbitrary fill
(`text_color_for`), paint-style color shading for texture
(`shade`), and two texture painters -- `add_rect_texture` for
axis-aligned rectangles (`bar.py`, `butterfly.py`, `snake.py`) and
`add_patch_texture` for arbitrary patch shapes (`pie.py`'s wedges, which
are neither a rectangle nor a `fill_between` polygon like `area.py`'s own
clip). This was factored out of `area.py` once `bar.py` needed the exact
same font/color logic; the alternative (each chart module quietly
re-implementing its own copy) is how packages end up with three subtly
different definitions of "what does our ink color look like" that drift
out of sync over time.

`dubois_charts/text_utils.py` is the actual measurement layer underneath all of
that — see its own section below for what it does and why.

Every mature plotting library solves "will this text fit?" the same way:
render it (or measure it without rendering), check the real pixel size,
and adjust — rather than guessing a font size and hoping. `text_utils.py`
follows that pattern throughout:

- `measure_text_px()` — draws text off-screen and asks the renderer for
  its real bounding box. This is the building block everything else uses.
  Routes through `get_renderer()`, which caches the renderer per-figure
  after the first draw rather than re-drawing the whole figure on every
  call — see "The renderer-caching bug" in the `snake.py` section below
  for why that distinction turned out to matter a great deal.
- `fit_fontsize_to_width()` / `fit_fontsize_to_height()` — binary search
  over rendered size to find the largest font that still fits.
- `wrap_text_to_width()` — word-wraps by measured width, not a character
  count (character count is meaningless once bold/italic or non-monospace
  text is involved — "W" and "i" are not the same width).
- `fit_title()` — the shrink-before-wrap policy real title-fitting uses:
  try a modest shrink first, wrap only if that's not enough.
- `fit_label_in_box()` — fits a label into a fixed-size box, shrinking
  then wrapping, and returns `None` if there's genuinely no room so the
  caller can fall back to something else instead of forcing an overflow.
- `choose_tick_label_style()` — the escalating strategy real chart
  libraries use for a crowded category axis: fit as-is → shrink → rotate
  → thin out, tried in that order, least disruptive first.

## `area.py`: what "accommodating long titles and long variable names" actually means

This was tested against a deliberately adversarial input — a 130-character
title, five multi-word series names, and six long region-name categories —
and the first pass found three real, distinct layout bugs:

1. **Category labels clipped at the canvas edge.** A rotated label is
   anchored at one corner and grows outward from it; for the last
   category, "outward" can run past the edge of the *figure*, not just
   the plot area, which no amount of `clip_on=False` prevents. Fixed by
   computing the actual rightward protrusion of the widest rotated label
   and growing the figure to accommodate it, rather than assuming a fixed
   margin is always enough.

2. **An in-band label overflowing its own band.** The label's fit was
   checked against the band's thickness at one anchor point (its widest
   point), but a wide, multi-character label centered there can still
   cover neighboring x-positions where the band is thinner — and it did,
   bleeding across the boundary line. Fixed with a converging check: fit,
   measure the true minimum thickness across the label's actual rendered
   footprint (not just the anchor), and re-fit against that if it's
   tighter than what was assumed.

3. **Two different bands' labels overlapping each other.** Each band
   independently picked its own best position with no knowledge of what
   any other band had already placed — fine until two adjacent thin bands
   both centered their labels at a similar height and the text collided.
   Fixed by tracking every placed label's bounding box and checking new
   candidates against it, falling back to a legend entry (exactly like
   the "doesn't fit at all" case) rather than drawing overlapping text.

The adversarial case -- long band names on thin bands -- is now among
the reference images the test suite compares against
(`tests/baseline/`), next to a short-label case the function was *not*
specifically tuned for. (Early renders of both, from before most of the
fixes in this file, used to sit in a `general_tests/` folder.)

## `bar.py`: what testing found

Stress-tested with a 130-character title, four two-line category
questions, and three grouped series (`bar_test2_stress.png`). One bug
turned up before the test even ran, caught while re-reading the geometry
math rather than by looking at a render: the category-label x-position
was computed as `-0.015 * xlim_max / (right_frac - left_frac) *
(right_frac - left_frac)` — the division and multiplication by the same
term cancel out, so the whole expression silently reduced to
`-0.015 * xlim_max`, a value in data units being used where an
axes-fraction offset was needed. It happened to be small enough not to
visibly break the first render, which is exactly the kind of bug that
looks fine on one dataset and clips on the next. Replaced with a small
pixel gap converted to an axes-fraction offset using the axes' *actual*
pixel width, computed after that width is known, rather than a hardcoded
fraction that means a different number of pixels depending on how wide
the plot area ends up being.

`bar_test1_basic.png` (five short categories, sorted descending) and a
16-category/zero-value edge case (not kept as a permanent test image, but
straightforward to reproduce — see `bar_chart`'s docstring example) both
render cleanly.

## `butterfly.py`: what testing found

This is the one chart in the package whose label axis sits in the
*middle* rather than at an edge, and that changed which bugs testing
surfaced:

1. **Value labels overlapping their own bars.** The left-hand side uses
   an inverted x-axis (0 at the center, growing outward to the left) so
   that bars visually grow away from the shared category column.
   `ha='left'` / `ha='right'` in matplotlib are always screen-space
   directions, not data-space ones — on a normal axis they happen to
   coincide, which is easy to miss until an inverted axis makes them
   diverge. With `ha='left'`, a label anchored just past a bar's outer
   edge grew back *into* the bar instead of away from it, because
   "screen-right" on an inverted axis is "decreasing data-x", i.e. toward
   the center. Fixed by using `ha='right'` specifically on the inverted
   side, so the label grows screen-left, which is outward on that axis.

2. **Long headers overflowing in both directions at once.** `left_label`
   / `right_label` (e.g. "MALE" / "FEMALE") only had shrink-to-fit, no
   wrap fallback. An 86-character header shrunk to the font floor and
   *still* didn't fit — it ran off the left edge of the figure on one
   side and the right edge on the other, with the two headers colliding
   in the middle. Fixed with the same shrink-then-wrap escalation used
   for titles and category labels elsewhere in the package: try a shared
   font size that fits both headers on one line first, and only wrap onto
   more lines if shrinking alone can't get there. Re-tested against the
   original (47-character) header case afterward to confirm the fix
   didn't regress it — it didn't; if anything two lines at a readable size
   reads better than one line shrunk small, which is what that case now
   gets.

`butterfly_test1_basic.png` (short "MALE"/"FEMALE" headers, four short
categories) and `butterfly_test2_stress.png` (long headers, five two-line
categories, asymmetric left/right values sharing one scale) both render
cleanly after these fixes.

## `spiral.py`: what testing found

The structurally hardest chart in the package. `area.py`, `bar.py`, and
`butterfly.py` all place labels along a straight edge, where "does this
collide" is a 1-D question -- do two ranges on the same axis overlap. A
spiral's labels sit at whatever angle their point lands at, anywhere
around a curve that may wind past the same angular direction more than
once, so collision is genuine 2-D bounding-box overlap against neighbors
that can approach from any direction, including neighbors on a
*different loop* of the same curve. Testing with 16 long labels
("Fourteenth Enumeration Period  105k"-length text) on a multi-revolution
spiral went through several real, escalating problems before landing
somewhere honest:

1. **Only ~1 revolution by default, for typical point counts.** The
   first revolution formula (`round(n/9)`) rounded down to a single,
   lopsided loop for 8 points -- radius grows from small to large across
   one loose sweep, so the curve only reaches its *outer* extent right
   near where it started, leaving most of the reserved circular region
   empty and not reading as a spiral at all. Fixed with a default of at
   least 2 full turns (`max(2.0, n/7)`), which both looks like the source
   material's dense coils and fills the reserved space far more evenly,
   since every angle then gets crossed by an inner loop *and* an outer
   one rather than a single pass at a middling radius.

2. **Labels overlapping the spiral curve itself.** The collision check
   only compared new labels against *previously placed labels* -- it
   never treated the curve as an obstacle, so labels routinely landed
   with the ink line running straight through the text once there was
   more than one loop for a label to land near. Fixed by also checking
   each candidate label's box against the densified curve-sample points
   already computed for drawing the line.

3. **Overcorrecting the fix above into "almost every label just
   vanishes."** The first curve-avoidance attempt used a buffer as wide
   as half the label's own height on every side, tried to place all 16
   labels at once, and only searched a few small radial pushes along
   each point's own angle. Combined, that meant nearly the entire
   crowded region read as "occupied" before most labels even got a
   candidate position, and pushing straight outward from an inner loop
   typically just ran into the *next* loop rather than finding open
   space -- fifteen of sixteen labels were silently dropped. Fixed with
   three changes together: a much smaller curve buffer (just enough to
   keep text off the ink line, not clear a wide halo around it);
   proactively capping how many labels are even *attempted* (spread
   evenly by index, so competing claims on space are lower to begin
   with, the same "thin out" escalation `bar.py` and `area.py` use for a
   crowded axis); and scaling the radial search step to the spiral's
   *actual* loop spacing rather than a tiny fixed pixel gap, since a
   push that's much smaller than the real distance between loops just
   relocates a label within the same crowded gap it started in.

After all three fixes, `spiral_test3_moderate.png` (12 points, short
year-and-value labels) places all of them cleanly with two clear turns.
`spiral_test2_stress.png` (16 points, long descriptive labels) is the
honest result of the adversarial case: several labels are skipped rather
than forced into an overlap, which is the intended behavior, not a
remaining bug -- there is a real amount of long text that a given
spiral's physical space cannot hold without collision, and the chart says
so by omission rather than by drawing garbled text. `spiral_test1_basic.png`
(8 points, bare years) is a plain sanity check that nothing regressed
along the way.

A fourth issue turned up later, not from a render but from the automated
test suite (see "Automated tests" below): a test asserting that the
8-point basic case places every one of its labels failed -- 7 placed out
of 8. This wasn't something a manual visual check had caught; the earlier
description of that same test case in this document claimed all 8
rendered, and that claim was simply wrong -- an easy mistake to make when
eyeballing a chart with several similar-looking small text labels, and
exactly the kind of mistake an automated check catches and a visual
skim doesn't. The actual cause: the radial search's largest push (`2.2x`
the base step) placed that label's candidate position close enough to
the spiral's *second* pass through the same angular direction (one
revolution later, at a larger radius) that every candidate in the search
grid collided. Fixed by tightening the radial multipliers (`1.8x` max
instead of `2.2x`), which keeps every candidate comfortably on the near
side of the halfway point between loops rather than approaching it.
Confirmed by the same test suite: all 8 labels place cleanly now, and the
previously-passing adversarial and moderate cases still show no overlaps
afterward.

## `snake.py`: what testing found

A snake chart folds one long scale into several rows with alternating
reading direction (left-to-right, then right-to-left, boustrophedon-
style), so a segment can straddle a row boundary and needs splitting into
several rectangle pieces that share one color and, ideally, one label.
Testing this surfaced three real bugs -- and unlike every other chart
section above, two of the three turned out to live in shared
infrastructure (`text_utils.py`), not in `snake.py` itself. That's worth
sitting with for a moment: a new, structurally different chart type kept
finding bugs in code four *other* chart types had already been stress-
tested against, simply because none of them happened to call things in
the specific order or shape that exposed the problem.

**1. `fit_label_in_box` silently returning truncated text.** Internally
it called `wrap_text_to_width(text, ..., max_lines=n_lines)` to see
whether wrapping into `n_lines` lines would work, then checked
`if len(lines) > n_lines: continue` to reject it if not. The bug:
`wrap_text_to_width` was already truncating-with-an-ellipsis to comply
with that exact `max_lines` argument (its own correct, documented,
separately-tested behavior for a caller that wants exactly N lines no
matter what) -- so the returned `lines` could never exceed `n_lines`,
and the guard could never fire. A label too long to actually fit came
back looking like a clean success with `…` silently baked into it,
directly contradicting `fit_label_in_box`'s own documented contract
("returns None if there's genuinely no room"). It showed up as
`Percentage Employed in Recognized Professional Occupations` rendering
as `Recognized Professional…` on a real chart. Fixed by asking
`wrap_text_to_width` for the *real*, uncapped wrap and checking its true
length against `n_lines` ourselves, rather than asking it to force-fit-
with-truncation and then trusting the result. All 148 tests that existed
before this fix still passed afterward without any changes -- this bug
had simply never been exercised by anything built so far, not confirmed
safe by anything that had already run.

**2. The legend clipping off the bottom of the figure.** `snake.py` had
a comment sketching the right idea -- reserve canvas space for a
potential legend -- but never actually implemented it; the legend was
placed with a negative `bbox_to_anchor` offset and no corresponding
space reserved for it, so it rendered partially or fully past the bottom
edge of the canvas. Caught the same way the plate51.py path bugs were:
by checking actual rendered pixel extent, not by trusting the layout
math. Fixed by copying `area.py`'s and `bar.py`'s already-proven pattern
-- reserve a fixed strip unconditionally, before any per-label fitting
happens, sized for the worst case where every segment needs the legend.

**3. The renderer-caching bug -- the most consequential find in this
whole project so far.** `get_renderer()` called `fig.canvas.draw()`, a
full redraw of *every artist already on the figure*, on every single
text measurement. That's cheap for a chart that measures its text before
drawing much (a title, fit once, up front). It's ruinous for a chart
that measures text *after* placing a lot of expensive content: 
`snake.py`'s per-segment label-fitting loop runs after that segment's
rectangle-and-texture pieces are already drawn, so fitting segment N's
label redrew every one of segments 0..N-1's pieces on every internal
measurement call inside `fit_label_in_box`. A chart with 30 segments
took **130 seconds**. Fixed by caching the renderer on the figure object
after its first draw and reusing it thereafter, rather than redrawing
every time -- text-extent computation only depends on font metrics
(fontsize, family, weight, DPI), not on the current pixel buffer
reflecting every artist added since, so nothing about redrawing was
ever actually necessary past the first call.

This one needed real verification, not just a plausible-sounding
argument, before trusting it: `bar_chart` grows its figure via
`fig.set_size_inches()` mid-render to make room for a rotated tick
label, and if that happens *after* something already cached a renderer,
a naive cache could return stale, wrong measurements for the new figure
size. Checked directly -- measured text before a resize, resized, then
compared the post-resize measurement (using the pre-resize cached
renderer) against a completely fresh figure created directly at the
post-resize size. They matched exactly. Only after that did the fix go
in. Result: the 30-segment case dropped from 130 seconds to about 1
second (roughly 122x), and re-running the *entire* pre-existing test
suite afterward -- unrelated to `snake.py` -- dropped its total runtime
from roughly 170 seconds to about 20. That same wasted-redraw cost had
been quietly taxing every other chart's tests too; it just never showed
up as severely as it did once one chart's shape of problem (measure
text repeatedly, late, after heavy drawing) made it impossible to miss.

`snake_test1_basic.png` (5 segments, 4 rows) and
`snake_test2_stress.png` (5 long-labeled segments including one spanning
4 rows, 6 rows total, deliberately sized so one segment's only available
space is too narrow for its label) both render cleanly after all three
fixes -- the stress case's unplaceable label correctly falls back to a
legend rather than truncating or overflowing.

## `pie.py`: what testing found

A pie slice has a hard ceiling on internal space that nothing else in
the package runs into: a bar can always grow taller, an area band can
always claim more of the chart's width, but a thin wedge's available
area is capped by its own angle, full stop, no matter how much the font
shrinks. Real chart libraries solve this with an EXTERNAL label
connected by a leader line -- a technique nothing else here had needed
yet, since every other chart could fall back to shrinking, wrapping, or
a legend instead. That's implemented as: try to fit inside the wedge
first; anything that can't (too narrow an angle, or a label too long
even at the smallest readable size) gets a label placed just outside the
circle instead, connected back to its wedge with a thin line, with all
the external labels on each side of the circle decluttered vertically so
labels from adjacent thin wedges don't land on top of each other.

**Estimating "does this fit inside the wedge" turned out to be the hard
part, and the first estimate was wrong.** The initial approach measured
available width as the arc length at a representative mid-radius --
`angular_span_in_radians x radius` -- which sounds like a reasonable
proxy and is *exactly* the wrong thing to check, because a label is
drawn as flat, horizontal text, while a wedge's actual boundary is two
straight radial edges and a curved outer arc. For a wide wedge whose
label doesn't sit near the wedge's own angular centerline, the true
available width at the label's specific height can be meaningfully
smaller than the arc-length estimate -- bounded on one side by a
near-vertical radial edge, on the other by the outer circle curving in
sooner than the estimate assumed. This wasn't caught by reasoning about
the formula; it was caught by looking at actual pixels: a 40%-of-circle
wedge's label, `Percentage Reporting Agricultural Occupation  40%`,
rendered with everything crisp and legible except the trailing `40%`,
which faded to barely visible right where the label crossed from the
wedge's fill onto the cream background behind it -- white text on red is
high contrast, white text on cream is not.

Fixed by replacing the trust-the-formula approach with an exact
geometric check: fit a candidate label, then verify all four corners of
its *actual rendered* bounding box genuinely fall within the wedge (right
radius band, right angle range) using real point-in-wedge containment,
not an approximation. If a corner escapes, shrink the box estimate and
retry -- bounded to a few attempts, since each retry strictly shrinks,
so it always terminates -- and fall back to an external label if nothing
fits. Re-run on the original failing case, the label now correctly
recognizes it can't fit safely and moves to an external position instead
of silently overflowing.

`pie_test1_basic.png` (4 segments, including one thin enough to need an
external label on the first try) and `pie_test2_stress.png` (11
segments, eight of them small and clustered together on one side,
including the exact wide-wedge configuration that originally failed)
both render cleanly after the fix -- reproduced and confirmed via the
same before/after pixel comparison used to find the bug in the first
place, not just re-run and assumed fixed.

## `choropleth.py`: what testing found

Every other chart in the package computes its own shapes -- a rectangle,
a wedge, a parametric spiral -- so it always knows exactly what geometry
it's placing text against. A map's shapes come from the outside world:
159 real Georgia county boundaries, each an irregular, often elongated or
diagonal polygon with no formula behind it, bundled as an actual GeoJSON
file (`data/georgia_counties.geojson`, trimmed from the county boundaries
`plotly/datasets` uses) the same way `plate51.py` bundles a real scanned
image rather than trying to compute history.

**The figure-height guess left a large gap between the map and its
colorbar.** The first version reserved title and colorbar space with a
guessed `+1.6 inches` added to a height computed from the map's lat/lon
aspect ratio. That guess doesn't account for `ax.set_aspect('equal')`:
matplotlib shrinks the *rendered* map to fit whichever dimension of its
allocated box is more constraining, so a box whose aspect ratio doesn't
land exactly right leaves the map smaller than its box with the leftover
space simply blank -- visible in the first render as a large gap between
the state outline and the colorbar sitting at its own fixed position
below it. Fixed the way `spiral.py` and `pie.py`'s own geometry was
solved rather than guessed: fix the figure width, measure how much
vertical room the title actually needs at that width, compute the exact
axes height an equal-aspect map of this shape requires, and size the
figure to precisely that sum -- no leftover space to begin with, rather
than hoping a guessed reservation happens to match.

**County labels needed the same fix pie_chart's wedges already went
through, applied proactively this time.** The first version tried each
label exactly once, sized against the county's axis-aligned bounding
box. For a long, thin, or diagonally-oriented county -- common in
Georgia -- the bounding box can be considerably larger than the county's
actual area, so a single-shot estimate against it is frequently too
generous, and a strict corner-in-polygon validation (the same technique
that caught pie_chart's wedge-boundary bug, generalized here via
matplotlib's `Path.contains_point` for arbitrary polygons rather than a
wedge's simpler radius-and-angle check) rejected far more labels than
the shapes actually required: only 3 of 10 requested labels placed on
the stress-test map. Fixed by applying the same shrink-and-retry loop
`pie_chart` already uses -- tighten the estimate and re-validate up to a
few times before giving up -- which raised the yield to 6 of 10 on the
identical input. This is the one place in the project so far where a bug
was avoided by *applying an earlier lesson before it repeated itself*,
rather than being found by testing from scratch: the validate-real-
corners-not-an-approximation principle was already known going in, and
still needed the shrink-and-retry half of the fix added on top once
testing showed the strict version alone was too conservative.

A test bug, not a chart bug, showed up while writing the regression
coverage for the layout-gap fix: a check meant to measure the union
bounding box of every rendered county patch computed `min(top edges)`
and `max(bottom edges)` instead of `max(top edges)` and `min(bottom
edges)` -- backwards, collapsing toward the most restrictive single
patch instead of the true overall extent, and reporting content filling
only 80% of its allocated space when the actual figure (confirmed by
reproducing the exact same measurement directly, outside the test) was
already correctly filling 94.3%, matching the padding intentionally
built into the layout. Caught by checking the discrepancy directly
rather than assuming either the test or the fix was automatically
right, and logged here for the same reason every other mistake in this
document is: getting it wrong first and correcting it in view is more
useful to whoever reads this next than a record that only shows what
eventually worked.

`choropleth_test1_basic.png` (6 counties, testing the layout-gap fix) and
`choropleth_test2_stress.png` (all 159 counties filled, a long wrapped
title, a deliberate typo confirmed to raise a `UserWarning` naming it
rather than silently rendering that county as "no data", and the
shrink-and-retry label fix) both render cleanly.

## The second pass: combining conditions instead of testing one at a time

Every chart type above was stress-tested along one axis at a time -- a
long title, or many categories, or long labels, tried separately. After
all seven were built, a second pass went back through combining
conditions within a single call (many categories *and* long labels *and*
extreme values *and* custom colors *and* texture, all together) and
testing categories of input nothing had checked yet: NaN and infinite
values, negative values, degenerate figure sizes, unicode labels,
duplicate category names. This found six more real bugs, all in
already-shipped, already-tested code -- worth sitting with, since it
means "tested" was never the same claim as "correct in every
combination," and more likely means more remain in combinations not yet
tried than that this was the last pass needed.

**NaN and infinite values corrupted charts silently, in different ways
depending on the chart.** `bar_chart` and `butterfly_chart` rendered a
NaN value as a completely invisible, unlabeled bar with no error at all
-- and in one observed case, the bad value appeared to have thrown off
the axis scale for the *other*, perfectly valid bars in the same chart.
Other charts crashed instead, but with raw, low-level errors ("Axis
limits cannot be NaN or Inf", "cannot convert float NaN to integer")
that name a matplotlib internal, not the actual problem. Fixed with a
shared `validate_finite()` in `_common.py`, called by all seven chart
functions, that raises one consistent, actionable message naming exactly
which category or segment had the bad value.

**Negative values had the identical invisible-bar failure mode, for a
different reason.** `bar_chart`, `stacked_area_chart`, and
`butterfly_chart` had no non-negative check at all, unlike
`spiral_chart`, `snake_chart`, and `pie_chart`, which already rejected
negative values since their geometry (a radius, a segment width, a
wedge's slice) can't represent one. A bar's length is exactly the same
kind of magnitude, and every bar in this package grows from a fixed
zero-point with no visible axis range on the other side -- a negative
value rendered exactly like the NaN case, invisible, unlabeled, no
error. `stacked_area_chart`'s case was subtler: a negative component
didn't disappear, it made the cumulative running total dip, producing a
band boundary that visibly sagged at that point and silently dropped
just that one value label, discovered only by checking which labels
were actually drawn, not just how the chart looked at a glance. All
three now raise the same clear, consistent error the other three chart
types already had. (`bar_chart` has since gone further: rather than
rejecting negative values, it now draws them properly as diverging bars
-- see "`bar_chart` gains diverging (positive/negative) data support"
below. `stacked_area_chart` and `butterfly_chart` still reject them.)

**A degenerate figure size crashed every chart type with a raw
`ZeroDivisionError`.** matplotlib itself validates `dpi` (a
non-positive value raises a clean error there), but accepts a figsize
like `(0, 0)` without complaint -- every chart in this package computes
its entire layout in pixels before calling `plt.figure()`, and divides
by those pixel dimensions repeatedly while solving margins and font
sizes, so a zero or negative figsize doesn't fail until several function
calls deep, with an error that names neither the input nor the real
cause. Fixed with a shared `validate_figsize()`, called by all seven
chart functions right before figure creation, checking type, shape,
sign, and finiteness together. `spiral_chart(revolutions=0)` turned out
to be the same class of bug in a different spot (a lone,
un-validated division by a user-supplied number deep in the label
geometry) and got the same kind of direct, explicit fix rather than
being left as a special case.

**`county_map_chart`'s `label_counties` had a real, if smaller,
consistency gap:** `data` already warned when an input name matched no
county, but `label_counties` silently skipped an unmatched name with no
warning at all -- indistinguishable from "this county's shape was just
too small to hold a label," which is normal and doesn't need a warning.
Fixed to use the exact same name-matching warning `data` already had,
since a typo and a genuinely-too-small shape are different situations a
user would want to tell apart.

**`butterfly_chart`'s wrapped headers clipped at the very top of the
canvas** -- found the same way the layout-gap bug in `choropleth.py`
was: by checking actual rendered pixel extent, not trusting the layout
math. The reserved space (`header_block_px`) and the header's actual
drawing position were computed by two formulas with no relationship to
each other -- the drawing loop used a hardcoded `1.03` axes-fraction
starting offset that was never derived from how much space had actually
been reserved. For a short header the two happened to roughly agree; for
a long header wrapped to two lines, they didn't, by enough that the
topmost line's rendered top edge ran past the canvas edge. Direct
instrumentation (printing the actual axes-fraction ceiling versus the
drawing loop's computed position) found the exact mismatch rather than
guessing at it. Fixed by deriving the drawing position directly from
`header_block_px`, so the two formulas can't silently diverge again.

**`pie_chart`'s external labels clipped again, in a new configuration.**
Many similarly-wide labels clustered on one side of the circle (twelve
equal 3%-wide wedges, each with a long category name) clipped several
labels at the literal last pixel column of the canvas, even though the
figure's margin had, in principle, already been sized around "the widest
label." The problem: that sizing assumed *one* representative worst-case
label, but when many equally-wide labels cluster together, several of
them independently reach close to that same worst-case position at
once. The first fix attempt introduced a second, subtler bug on its own:
converting a label's pixel width into a data-unit width using the scale
*before* deciding how much the canvas needs to grow is circular, since a
larger final canvas has a smaller data-units-per-pixel ratio, meaning
the same pixel-width text needs *more* data-space than a conversion at
the smaller, pre-expansion scale suggests. Confirmed this really was an
undersized estimate (and not a broken mechanism) by manually forcing a
1.5x-larger expansion and watching the clipping disappear completely,
*before* working out the correct per-label algebra to replace the guess
with an exact solve.

**One of these fixes broke the package for one command, briefly, by
accident.** Midway through, an edit meant to be a harmless no-op (an
`old_str`/`new_str` pair that looked identical) actually stripped a
newline and merged a function signature onto the same line as its own
docstring, in the shared `_common.py` every chart imports from. The very
next command -- an ordinary import check -- failed immediately with a
clear `IndentationError` pointing at the exact line, so this was caught
before it could compound into something confusing to untangle later, but
it's worth recording plainly rather than smoothing over: "this edit
looks harmless" is not the same claim as "this edit is harmless," and
the fix was to actually diff the before/after, not to trust that
intuition next time.

None of this list should read as "and now every bug is found." It
should read as: testing one dimension at a time, however thoroughly,
systematically misses a category of bug that only shows up when
conditions combine -- which is a property of testing in general, not a
gap specific to this package, and reason enough to keep this kind of
pass as a standing practice rather than a one-time cleanup.

## The third find: reported directly, not caught by any test

Every bug up to this point was found by this project's own testing --
stress tests, combined-condition tests, pixel-extent checks. The next
one wasn't: it was reported directly against a rendered example, and it
passed every existing test in `test_choropleth.py`, including the ones
specifically checking label placement, because none of them checked the
right property.

**`county_map_chart`'s county-name labels didn't visually match each
other.** "Bibb" and "Cobb," labeled on the same map, looked like they
were set in different fonts -- one crisp and bold, one thin and
spindly. Checking the actual matplotlib `Text` properties directly
showed they weren't actually different fonts at all: both were
`fontweight='bold'`, both `'Liberation Mono'`. What differed was
fontsize -- Cobb at roughly 6.6pt, Bibb at roughly 10.2pt, a 35%
difference -- and bold text at a small size renders with visibly
thinner strokes than the same weight at a larger size, enough to read
as a mismatched font even though nothing about the font had changed.

The root cause was a real design gap, not a measurement error: each
county's label was fit *independently*, maximizing its own font size
against its own polygon's shape, with no step that considered any other
label being placed on the same map. Every other chart type in this
package already solves this correctly for its own category labels --
`bar_chart`, `butterfly_chart`, and `snake_chart` all compute one shared
fontsize across every category label up front, sized to whatever the
most space-constrained label needs, rather than letting each one
maximize independently. `county_map_chart`'s per-county labeling had
never been brought in line with that same principle.

Fixed by solving for one shared fontsize across every label being
placed on the map: try progressively smaller candidate sizes, and at
each one, check (via the same real corner-in-polygon containment used
elsewhere) which counties can actually hold their name at that exact
size. Accept the largest size where a clear majority of the requested
counties fit; counties that can't hold that shared size are left
unlabeled, the same "not every unit gets a label" behavior already used
throughout this package, rather than shown at a jarringly different
size of their own. On the reported case, this meant fewer labels
survived (3 of 6 requested, all at one consistent size, instead of 6 at
independently-chosen sizes) -- and turned out to reveal a second, smaller
finding along the way: `label_top_n`'s default of ranking candidate
counties by *geographic area* systematically favors exactly the wrong
counties for demographic or economic data, since Georgia's
data-richest counties (Fulton, DeKalb, Cobb -- the Atlanta metro area)
are also among its geographically smallest, and therefore hardest to
label cleanly. That's a real, separate design question -- what should
"the most important counties to label" default to when it isn't
geographic size -- left open rather than folded into this fix, since it
changes the feature's behavior rather than correcting a defect in it.
(Since settled: labels are now chosen by value, and counties too small
for their names get callouts instead of being left unlabeled. See
"Fixed in a second follow-up pass" below.)

This one is worth sitting with for a different reason than the others:
it slipped past every existing test, including tests that specifically
checked label placement, because those tests checked "does a label
render, does it stay inside its shape, do labels overlap" -- all true
here -- and never checked "do multiple labels on the same chart look
consistent with each other." A category of correctness that's obvious
to a human looking at the image and easy to miss when only individual
properties are asserted in isolation.

## The same bug, found a second time, in a different chart

Once a bug is understood as a *category* -- "items sized independently
against their own shape look inconsistent next to each other," not just
"this one county's label was too small" -- the obvious next question is
where else the same category exists. `pie_chart`'s internal wedge labels
were the next-most-likely candidate: exactly like counties, wedges vary
enormously in size on the same chart, and each one's label had been
fit the same independent way. Checked directly rather than assumed
either way: on the same 4-segment "Conjugal Condition" pie used
throughout this document, "Married" and "Single" rendered at roughly
13pt, "Widowed" at roughly 9.75pt -- the identical failure, just with
wedges standing in for counties. Fixed with the identical approach:
solve for one shared fontsize across every internally-placed label,
trying progressively smaller candidates and accepting the largest size
where a clear majority of labels can actually be placed at it.

That fix broke something else on the first attempt, in a way worth
recording precisely because it's a repeat of an *already-documented*
mistake. The shared-size search needs to check, at a given candidate
fontsize, whether a label wrapped to at most 2 lines fits its wedge --
and the first version called `wrap_text_to_width(..., max_lines=2)`
directly to get that wrap. But `wrap_text_to_width` truncates-with-
ellipsis to comply with a `max_lines` cap when the real content needs
more room, rather than reporting that it didn't fit -- the exact
`fit_label_in_box` anti-pattern already found and fixed once earlier in
this same project (see "the second pass," above), reintroduced here in
new code that happened to make the identical mistake independently. It
showed up immediately on render: a long label in a large wedge came out
as two garbled fragments, `"Divo"` and `"rce…"`, instead of "Divorced."
Fixed the same way as before -- ask for the wrap the text actually
needs, uncapped, and reject anything that genuinely needs more than 2
lines rather than accepting whatever the truncated version was mangled
into.

Fixing *that* surfaced a third, smaller issue in the same function: once
truncation was no longer silently masking the problem, a large
(144-degree) wedge with a long label started failing to fit at *any*
tested size, for no shape-related reason. Direct instrumentation traced
it to the retry schedule: each retry narrowed the candidate wrap width
by a fixed 20%, starting from a generous arc-length estimate -- but a
single line's rendered width doesn't change at all until the candidate
width drops *below* it, so three of four retry attempts had zero visible
effect before the budget ran out, one attempt short of the real 2-line
wrap that would have worked. Fixed by trying the natural single-line
width first, then widths chosen to force something close to an even
2-line split immediately, rather than inching toward one 20% at a time.

Three fixes to land one shared-fontsize change, each caught by actually
re-rendering and looking rather than assuming the previous fix was
sufficient -- which is the same practice this whole document keeps
returning to, just compounded three times in a row on the same feature.

## Checking the other two, on purpose

Two instances of the same bug, in two unrelated-looking charts, is
enough to stop treating it as coincidence. The other two chart types
with per-item internal labels -- `snake_chart`'s segment labels and
`area_chart`'s band labels -- were checked deliberately, not because a
fresh stress test happened to surface anything, but because the
category was now known and both used the identical suspect pattern
(`fit_label_in_box` called per-item, against that item's own box, with
no step considering any other label on the same chart).

Both had it. `snake_chart`, on a 5-segment chart with varying piece
widths, rendered "Agriculture" at 13pt against "Trade" at roughly
7.2pt -- a 44% spread, the worst of the four found. `area_chart`, on a
3-series chart with varying band thickness, spread from 16pt down to
10.17pt across its three band labels. Fixed identically both times:
solve for one shared fontsize by trying candidates from largest to
smallest, accept the largest one where enough items can actually be
placed at it, leave the rest to the legend.

`snake_chart`'s fix was mechanical, since its segments are plain
rectangles -- `fit_label_in_box` already does exactly the "does this
fit in this box" check needed; forcing `min_fontsize == max_fontsize`
at each candidate was enough to reuse it directly with no new geometry
code. `area_chart`'s fix needed more care: its band labels already had
their own sequential collision-avoidance from an earlier fix (a label
placed for band *i* has to avoid every label already placed for bands
before it), so finding the right *shared* size meant simulating that
same sequential placement once per candidate size -- trying all bands
in order, tracking which succeed against each other at that size,
before committing to the winning size and drawing for real in a second
pass. Getting this right meant preserving the existing per-band
convergence loop (which re-validates a label against the true minimum
thickness across its own footprint, not just its anchor point) inside
the new per-size search, rather than replacing it -- the two fixes are
solving different problems and both still apply together.

That's four for four, now, on every chart type that had this pattern.
Nothing about that guarantees a fifth won't turn up somewhere not yet
looked at closely enough -- only that "found it twice" was reason
enough to go look, rather than waiting for it to be reported a third
time.

## `background` was broken for every color except the default

After the label-consistency fixes above, a broader pass looked for other
categories of bug rather than more instances of the same one: input
compatibility with numpy and pandas objects (fine -- including a pandas
`Series` with a non-default post-sort index, a real pattern that could
plausibly have caused an ordering bug and didn't), seed reproducibility
for both static and jitter-based charts (fine), and state leakage across
repeated chart calls in a loop (fine, including confirming the renderer-
caching performance fix stays correctly scoped per-figure rather than
leaking measurements between unrelated charts).

Then a check of the `background` parameter -- documented and exposed on
every one of the seven chart functions -- found something serious.
Rendering any chart with a dark background instead of the default cream
made nearly every category label, value label, title, border, and
external label disappear. Not a subtle contrast issue -- category names
and percentage values were essentially unreadable, dark ink on a dark
page.

The cause was narrower than the symptom suggested: `_text_color_for()`,
the contrast-aware color picker already used throughout this package,
was only ever applied to text drawn *on top of a data fill* (a label
inside a colored bar, wedge, or band). Everything drawn directly on the
page background instead -- which turns out to be most of a chart's
text, plus every border -- used a hardcoded near-black `COLOR_INK`
constant that never once checked what `background` had actually been
set to. The default cream background happens to contrast fine against
near-black, which is exactly why this went unnoticed through every
stress test, every combined-condition test, and every regression test
in this document so far: none of them varied `background` away from its
default.

Fixed identically across all seven chart files: compute
`ink_color = text_color_for(background)` once, early in each function
-- treating the background itself as a fill that needs contrast-
appropriate ink, the exact same logic already proven correct for data
fills -- and use that computed value everywhere `COLOR_INK` used to be
hardcoded (titles, axis and category labels, borders, legends, external
labels). `butterfly.py` and `spiral.py` needed the `text_color_for`
import added, since neither had ever needed it before this fix, every
prior text-color decision in those two files having been about a data
fill.

Confirmed with an actual before/after check, not just re-running the
fixed version and assuming it was right: temporarily reverted `bar.py`
back to hardcoded `COLOR_INK`, confirmed the new regression test failed
against it with the exact expected value (`'#1a1a1a'`, unreadable
against a `'#1a1a2e'` background), then restored the real fix and
confirmed the same test passed again. The regression suite checks this
property directly and computationally -- an actual luminance calculation
against each rendered text artist's real color, on a dark background,
across all seven chart types, plus one test confirming the default
light background still gets dark ink rather than the fix having quietly
inverted that case.

This is the first bug in this whole project found by varying a
parameter that every single other test, all session, had left at its
default. Worth remembering the next time a chart type or feature seems
thoroughly tested: thoroughly tested along the axes someone thought to
vary is not the same claim as thoroughly tested.

## The texture was never actually visible

Every bug up to this point was a correctness problem: something crashed,
something rendered in the wrong place, something silently disappeared.
This one is different in kind -- nothing was wrong, in the sense that
every test passed and nothing behaved incorrectly. It just didn't
accomplish what it was built for.

`add_rect_texture` and `add_patch_texture` (the shared texture painters
`bar.py`, `butterfly.py`, `snake.py`, `area.py`, and `pie.py` all use)
were never broken. They correctly applied a subtle, seeded, noise-based
grain to every fill, exactly as designed. Checked directly: a horizontal
strip sampled straight through the middle of an actual rendered bar
showed only 4 distinct colors across its width, with the darkest and
lightest differing by 3 RGB units out of 255. Technically present,
completely invisible. The whole point of texture in this package is to
evoke Du Bois' actual hand-painted plates rather than look like a
generic flat-design chart -- and at that level, it wasn't accomplishing
that, even though every existing test (correctly) confirmed the texture
code ran without error and produced *some* variance.

The original 0.14 strength constant had likely been tuned, at some
point, by looking at a rendered chart and judging it "textured enough"
-- but a plausible explanation isn't the same as a re-derivation, and
revisiting it with a direct side-by-side comparison (multiple strength
values, rendered as actual chart fills rather than described) told a
different story: 0.14 read as flat, while values several times larger
read as genuine, visible, tasteful grain.

Raising the constant wasn't the whole fix, and finding that out required
testing the change in the specific context that would show a problem,
not the context that already looked fine. A strength that looked good on
saturated mid-tone colors (crimson, gold) looked distractingly noisy on
a large, near-black fill -- confirmed by comparing an actual chart's
black band against equally-sized red and gold bands at the identical
strength value, not by looking at small isolated color swatches of each,
which didn't show the difference clearly enough to notice. The reason is
a real, general property of human vision, not a quirk of this specific
noise algorithm: a given absolute change in luminance reads as more
prominent near the dark end of the range than in the middle. Fixed by
damping the effective strength for dark base colors specifically (full
strength once lightness rises to about a quarter of the way from black,
tapering down, never below 40% of the nominal value, as lightness
approaches zero), rather than searching for one compromise number that
would have undershot every mid-tone color to avoid overshooting black.

`plate51.py` was deliberately left untouched. It has its own, separately
calibrated, historically-verified texture implementation -- the whole
point of that separation (documented in `PLATE51_README.md`) is that its
calibration answers to the actual scanned original, not to a general
aesthetic judgment, and this fix was the latter.

## `bar_chart` gains diverging (positive/negative) data support

Real-world testing (pulling actual current data from the web rather than
constructed examples -- world population figures, EIA electricity
statistics, Georgia unemployment rates, and more) eventually reached a
textbook-common use case this package had no path for at all: GDP growth
rates, which are routinely negative (economic contractions), rejected
outright by `bar_chart`'s non-negative-value check.

That check, added earlier (see "the second pass," above), was itself the
correct fix for what it addressed -- a negative value used to render as
a completely invisible bar with no error, since every bar grew
rightward from a fixed x=0 start with no visible axis range on the other
side. But the fix's own suggested workaround ("pre-shift your values to
a non-negative range") turns out to be bad advice for genuinely signed
data like a growth rate: shifting the numbers would make the displayed
values wrong unless the caller does substantial extra work to relabel
everything correctly. The right fix wasn't a better error message -- it
was building the diverging support the chart never had.

The axis logic follows one rule: `xlim_lo` stays at 0 unless some value
is negative, and `xlim_hi` stays at 0 unless some value is positive.
This means an all-positive dataset gets the exact same `(0, max)` axis
it always has -- diverging support is additive, not a rewrite -- while
a mixed-sign dataset gets a shared zero origin with room on both sides,
and an all-negative dataset mirrors the original behavior around zero
instead of extending pointlessly into positive territory. A vertical
line marks the origin, but only when the data actually spans both
signs; when it doesn't, x=0 already coincides with one edge of the
plotted field, and a second line drawn on top of the existing border
would add nothing. Each value's label is drawn outward from its own
bar -- right of a positive bar, left of a negative one -- so the reader
never has to infer which side means what.

Landing this cleanly took two attempts, the second one caught by
rendering the real GDP data that motivated the feature in the first
place rather than trusting the design once it compiled. The first
version reserved extra left-margin space for negative-value labels (the
mirror image of the right-margin space already reserved for positive
ones) but didn't actually reposition anything to use it: negative-value
labels anchor near each bar's own end, which for the single most
negative value in a diverging dataset sits close to the axis minimum --
which is also exactly where the category-label column already sits, just
outside the axes' edge. The extra reserved width ended up as unused
space further out past both labels, while the two things that actually
needed separating stayed exactly as close together as before. Checked
directly against the real data, not assumed fixed by the reservation
existing: Qatar's country name and its own "-8.7%" figure overlapped by
about 60 pixels. Fixed by shifting the category-label column itself
further left by the reserved negative-label width, so the space ends up
*between* the two things competing for it rather than beyond both of
them.

## Testing with real data pulled from the web

Every test above used data constructed for the purpose. As a final check,
each chart type was run on real, current data pulled from public sources,
with names and numbers kept exactly as the source reported them: 2025
world population rankings, U.S. Energy Information Administration
electricity-generation shares, Android/iOS market share by region,
Georgia's census history, Fortune 500 revenue, IMF GDP growth
projections, EU city populations (including "Kraków"), and the complete
September 2026 BLS unemployment rate for all 159 Georgia counties.

**What held up.** The county map matched all 159 counties with zero
warnings, including the source's non-standard "Mcduffie County" and
"Mcintosh County" capitalization. Accented Latin characters ("Kraków")
render correctly in the default font. Unusual internal capitalization
("UnitedHealth Group") survives in `bar_chart` category labels. Every
earlier fix (shared label sizing, background contrast, texture) behaved
correctly throughout.

**Fixed as a result.**

- `snake_chart` split "Other", an ordinary five-letter category name, into
  "Oth" over "er" with no hyphen when its piece was narrow. The label
  fitter's hard-break fallback is correct for a single word wider than
  any available space, but the shared-fontsize search was accepting it
  silently. Any fitted result whose lines don't rebuild the original
  words exactly is now rejected, so a word that doesn't fit whole goes
  to the legend instead.
- `bar_chart` rejected negative values outright, which made real GDP
  growth data impossible to plot. It now supports diverging data; see
  the section above.

**Found, then fixed in a follow-up pass.** Four problems were first
recorded here as open, then fixed. Each fix was measured on the rendered
chart before and after, and its regression tests were confirmed to fail
against the old behaviour.

- **`stacked_area_chart` dropped value labels on sparse time series.** On
  x = [2001, 2022, 2024] (a distant baseline plus two recent years, a
  very common shape for real data), 7 of 12 value labels were missing,
  including the current-year figures for three of the four series. Band
  names can only anchor on a real data point. For fairly flat bands the
  tie-break toward the chart's centre put three of the four names on the
  2022 column, and every value label they touched was dropped instead of
  moved. Value labels now try the band's middle first, as before, then
  positions progressively further above and below it, staying inside
  their own band across their full width (a sloped boundary can sit
  several pixels higher at one edge of a label than the other). Measured
  across seven data shapes: the reported case went from 5 to 12 of 12
  labels, a two-point series from 2 to 4 of 4, and every other shape
  kept or gained labels, with zero overlapping text.

  The same probe found a related bug: with irregular spacing (2000,
  then 2020-2023) the x labels were spaced as if the points were even,
  so 2020-2023 printed on top of each other, and neighbouring value
  labels overlapped because value labels were never checked against each
  other. Year labels are now thinned by their real position and measured
  width, always keeping the final point, and value labels avoid each
  other as well as band names. The first version of that fix passed every
  objective check (no overlaps, nothing outside its band) and still
  wasn't readable: values stayed under the dropped years, stacked in a
  staircase with no way to tell which year each belonged to. Looking at
  the chart caught it. Columns whose year label is crowded out now get no
  values either, so every printed number sits under a named year.
- **`bar_chart`'s default `value_format` was `'{:.0f}%'`**, so raw
  counts got a percent sign: India's population in millions rendered as
  "1457%". The default is now a plain number with thousands separators
  and the fewest decimals (0-2) that show every value exactly, shared by
  all labels so they line up ("12.60" beside "6.48"); tiny values get
  enough decimals not to print as "0.00". Percentages are now asked for
  with `value_format='{:.0f}%'`, and the package's own percentage
  examples do so.
- **Forced capitals mangled names like "iOS".** `butterfly_chart`'s side
  headers turned "iOS" into "IOS" while `pie_chart` kept it. Every chart
  title and `stacked_area_chart`'s band names had the same problem. A
  shared `display_caps` now capitalises ordinary words but leaves
  deliberate mixed case alone ("iOS", "eBay", "DeKalb", "kWh"). Fixing
  the headers exposed a second bug: they were measured and wrapped in
  their original case but upper-cased only when drawn. In the default
  monospace font both cases are the same width, so it never showed; in
  a proportional font capitals are wider, and long headers ran up to
  114px past their half of the chart. Headers are now converted before
  measuring, and a test checks the rendered boxes in DejaVu Sans.
- **`pie_chart` labelled a visible sliver "0%"** when its share rounded
  to zero (0.41% became "Other 0%"). A share that rounds to zero but
  isn't zero now reads "<1%", or "<0.1%" and so on, matching the
  format's own precision; a true zero still reads "0%".
- **The frame line cut through value labels** in `bar_chart` and
  `butterfly_chart`. Noticed when re-rendering the real-data charts
  after the fixes above: "1,4|17.73" for China, "91%" in the Android
  panel. It was systematic. The frame sat at the axis limits while
  value labels sit just past each bar's end, so the longest bar's label,
  and any bar close to it, always straddled the frame. A probe measuring
  frame edges against rendered text boxes found it in every chart with
  value labels it tried: seven of seven, on both sides of diverging
  charts and in both butterfly panels. The layout already reserves room
  for the widest label on each side, so each frame now extends into that
  room, stopping 6px short of the figure edge; the bars keep their size.
  With value labels off, frames stay exactly where they were. Butterfly
  headers are centred on the wider frames so they stay balanced.

  One consequence was caught by re-running the old-behaviour checks
  rather than trusting the green suite: the wider frames made the
  header-overflow test from the capitals fix pass against the *old*,
  broken code. On its data, an oversized header happened to fit inside
  the widened frame. The test now checks the exact property that bug
  broke, that each header fits the width it was wrapped to, with value
  labels on and off, and fails on the old code in both cases.

**Fixed in a second follow-up pass.** The last two problems this
section listed as open, and four more found while fixing them.

- **Colours repeated after eight categories.** `get_categorical(n)`
  started the eight colours over for a ninth category, so the ten-country
  population chart drew India and Russia in the same crimson and China
  and DR Congo in the same gold. The first eight are unchanged, so no
  existing chart looks any different. Up to 20 categories the palette now
  continues with `DUBOIS_CATEGORICAL_20`: twelve more colours chosen so
  that no two of the twenty, and none of them against the cream paper,
  look more alike than crimson and rose, the closest pair of the
  original eight. "Look alike" is measured with CIEDE2000, the CIE's
  standard colour-difference formula (crimson and rose are 15.4 apart;
  every pair of the twenty is at least 15). The implementation matches
  all 31 of Sharma, Wu & Dalal's published test pairs, and agrees with
  scikit-image's to within 1e-13 on 2,500 random pairs.

  The additions were picked most distinct first. First come the
  package's other Du Bois colours that clear the bar: pink, gray and
  navy. Tan, the brighter yellow and the Plate 51 olive don't clear it,
  being too close to the paper, the gold and the green. Then come darker
  tones of the palette and lighter ones muted as they lighten, so
  nothing turns neon: dark green, wine, lavender, sage, pale periwinkle,
  charcoal, ochre, slate blue and fawn. Near-blacks are excluded because
  they read as black. `_build_categorical_20()` re-derives the list, and
  a test keeps the two in sync. Past 20, each category still gets a
  colour of its own, the most distinct tone left, and a warning says so
  once two of them are closer than crimson and rose (from 22 on).
  `bar_chart` doesn't warn for single-series bars, which are each
  labelled by name. The theme's colour cycle has the twenty too.

  Two related bugs turned up in the same code:
  - `stacked_area_chart` and grouped `bar_chart` crashed halfway through
    drawing with a bare `IndexError` when given fewer colours than
    series. Colour is the only thing telling their series apart, so that
    is now a clear `ValueError`.
  - An empty `colors` list crashed the other charts with
    `ZeroDivisionError`; it now gets a clear error too. A single colour
    string (`colors='#DC143C'`) now means that colour for every bar,
    not its characters.

- **County labels were chosen by size.** On real data, Georgia's county
  unemployment rates from the Bureau of Labor Statistics, the default
  asked for six labels on the largest counties. It drew three (Burke,
  Laurens, Washington, at 6pt), with rates of 5.4%, 3.5% and 3.3%. None
  was the highest in the state (Chattahoochee, 6.9%) or the lowest
  (Oconee, 2.5%). A new `label_by` parameter chooses the counties by
  value:
  - `'extremes'` (the default) alternates highest and lowest;
  - `'highest'` and `'lowest'` take one end;
  - `'area'` keeps the old behaviour.

  Ties go to the larger county, then alphabetically, so the labels don't
  depend on the order the data came in.

  Choosing by value exposed the real obstacle. The highest, third
  highest and lowest counties were all too small to hold their names.
  That's no coincidence: in a county of a few thousand people, a handful
  of jobs moves the rate a lot, so the extremes of a rate are often the
  smallest counties. Two changes followed:
  - **Placement.** A label was tried in one spot only, the average of
    the outline's vertices. For irregular counties that spot is often
    cramped, or not inside the county at all. Only the label's four
    corners were checked, so a boundary could cut through it between
    them. Labels now go in the roomiest, most central spot where every
    point along the label's edge is inside the county. At the default
    size, 105 of the 159 names now fit at 8pt, against 50 before (143
    against 91 at 6pt).
  - **Callouts.** A county too small for its name at any size gets a
    callout: the name just outside the state, with a leader line to a
    dot in the county, like `pie_chart`'s external labels. A thin
    paper-coloured halo keeps the leader from reading as a county
    boundary. Callouts go to the nearest free spot on a 3px grid that
    marks the state, placed labels and earlier leader lines. A leader
    may cross counties but not another label.

  The shared font size took three tries, each caught by looking at the
  render:
  1. First: the largest size at which 60% of the labels fit, with the
     rest handed to the next county in line. On the unemployment map
     that dropped the county with the lowest rate in the state to get
     9pt labels instead of 7pt.
  2. Then: every chosen county had to fit. The counties that fit
     nowhere were counted against the size, which pinned every label at
     6pt.
  3. Now: the largest size at which every county that can hold its name
     fits. If that's under a comfortable 8pt, labels stay at 8pt
     (provided most still fit) and the rest become callouts.

  The unemployment map now labels the three highest and three lowest
  counties at 8pt, three of them by callout.

  A probe measured the rendered text against the county outlines,
  every pixel along each label's edge, over 23 configurations: every
  `label_by`, 3 to 20 labels, small and large figures, random data, and
  an explicit list of eight small metro counties. Every label was either
  entirely inside its own county, or entirely outside the state with a
  leader line from its county. No labels overlapped, no leader line ran
  through another label, and nothing ran off the figure.

- **The colorbar printed the unemployment map's class boundaries as
  "2 3 3 3 3 4 4 7".** `county_map_chart`'s default `value_format` was
  `'{:.0f}'`, the same mistake `bar_chart` had. The default now follows
  the data's own precision (2.5, 2.8, 3.0 ... 6.9), with extra decimals
  only when two different boundaries would otherwise print the same.

**Still open.**

- **Many callouts get busy.** An interior county's leader line has to
  reach the edge of the state, so it can be long. Maps asking for 15-20
  labels on small counties work, but they get crowded.
- **Emoji need an emoji font matplotlib can draw.** Text falls back to
  any installed font that has a character (see below), but the common
  colour emoji fonts are bitmap fonts matplotlib can't load, so emoji
  render as boxes unless a monochrome emoji font (Noto Emoji, Symbola,
  Segoe UI Emoji) is installed. Nothing in the package can ship around
  that.
(Heavily tied data breaking the map's colour classes was listed here
too; it's fixed -- see the next section. So are spiral leader lines
crossing loop after loop on a tightly wound spiral -- see "Leader lines
on a tight spiral".)

## Any data: a stress test of the first seven charts

The real-data pass above tried one dataset per chart. This pass asked
the harder question: does every chart cope with whatever someone
brings? A harness ran all seven chart functions over about 370 input
variations, one change at a time from a plain baseline:

- containers: lists, tuples, numpy arrays, pandas Series, Index and
  DataFrame;
- number types: numpy int64 and float32, Decimal, Fraction, numeric
  strings, booleans;
- magnitudes: 1e-7 to 1e13, fractions, one value a million times the
  others, zeros, ties;
- counts: one category to a hundred;
- label text: long names, one 76-letter word, accents, Chinese, Japanese
  and Korean, emoji, dollar signs, newlines, blanks, duplicates,
  integers, dates, None;
- x values: dates of every kind, unsorted, repeated, one point, a
  hundred points.

Every render was checked for crashes, errors that don't say what's
wrong, text off the figure, text overlapping text, and "nan", "inf" or
misplaced percent signs, then contact sheets of the riskier cases were
looked at, since several problems don't show up in any measurement.

What it found, all fixed:

- **Dollar signs were read as math.** matplotlib treats text between two
  `$` as math markup: the label "$5-$10" rendered as "5-10" in italics,
  the title "Spending: $5 to $10 per day" as "SPENDING: 5TO10 PER DAY".
  Every chart function now builds its figure with math parsing off, and
  with LaTeX off, so a user's global `text.usetex = True` can't turn a
  "%" or "_" in an ordinary label into a LaTeX error. Both settings are
  fixed on each text object when it's created, so the returned figure
  keeps them.
- **Chinese, Japanese and Korean labels were empty boxes.** Charts drew
  in one monospace font. Text now falls back, glyph by glyph, to
  whichever installed font has the character (matplotlib 3.6+).
- **Percent signs on data that isn't a percentage.** `stacked_area_chart`,
  `butterfly_chart` and `snake_chart` defaulted to `'{:.0f}%'` whatever
  they were given: raw counts printed as "1900%", electricity in GWh as
  "4100000000%", fractions as "0%", and the snake's scale read "164%,
  328%". `spiral_chart`'s `'{:.0f}'` printed every value below 1 as "0".
  Defaults now show the data at its own precision, with a percent sign
  only when the values really are percentages of their total: every
  area column, each butterfly side, or the snake's scale adds up to
  100 (give or take 2, for rounding). That can never label something
  wrongly. Percentages that don't add up to 100 -- shares with minor
  categories left out, rates -- print as plain numbers, and
  `value_format='{:.0f}%'` adds the sign, as it already did for
  `bar_chart`.
- **Tiny values all printed as "0.000000".** Below 0.0001, and from 1e15
  up, default labels switch to scientific notation. float32 rounding
  noise no longer adds decimals (np.float32(0.1) is one decimal place).
- **pandas and number-type inputs.** `pie_chart` and `snake_chart` called
  `segments.values()`, which on a pandas Series is an array, not a
  method: passing one crashed with "'numpy.ndarray' object is not
  callable". A DataFrame of series gave `bar_chart` "The truth value of
  an array ... is ambiguous". `stacked_area_chart` crashed upper-casing
  an integer series name, and `county_map_chart` crashed sorting a
  value given as a string. All accept dicts, Series and DataFrames now,
  and any kind of number.
- **Errors that didn't say what was wrong.** A missing value was reported
  as "NaN or infinity"; a word where a number belonged failed with
  numpy's "could not convert string to float"; `value_format='{:.0d}'`
  failed deep inside a chart with Python's own message, and
  `value_format='units'` silently labelled every bar "units". Each now
  raises a ValueError that names the entry or the problem, before any
  drawing starts.
- **The area chart's year labels ran off the top of the image** on any
  chart without a title. They sat at 2% of the data's height above the
  plot, about 18px, while only their height plus 14px was reserved;
  a title above absorbed the difference. They now sit a fixed 6px above
  the plot.
- **Dates, order and many points in the area chart.**
  - Dates were spaced evenly however irregular, and pandas dates printed
    as "2020-01-01 00:00:00". They're now placed by time and labelled as
    compactly as they allow ("2020", "Jan 2024", "2024-03-30").
  - Unsorted x zig-zagged the areas back over themselves; the data are
    now sorted by x, and a repeated x is an error.
  - With 30 or more points the figure grew to 16 x 16.8 inches; it now
    stops at 11 inches wide.
  - With 100 points, thinning the year labels to every tenth skipped the
    last year. And value labels were thinned on a schedule of their own,
    so numbers sat under years with no label. The last point is now
    always a candidate, and values are drawn in exactly the columns
    whose year is shown.
  - Long date labels at either end are nudged back onto the figure.

  Writing the test for the last point turned up one more: labels
  "clamped to the edge" stopped about 20px short of it, because x was
  measured from the first data point, not the plot's padded edge. That
  put the first column's numbers nearer the second year label than
  their own. (The first fix for it went too far; see "edge labels hung
  over its border" below.)
- **Long labels ballooned the pie and spiral charts.** Both reserved room
  for their widest label on one line, and scaled the whole figure up if
  that left too little: one 70-character label made a 9-inch pie 24
  inches wide and a 7-inch spiral 18. Long outside labels now wrap.
- **Pie outside labels crossed the pie.** They sat at their wedge's own
  angle, so thin wedges clustered near 12 o'clock stacked their labels
  straight down over the biggest slice. Outside labels now go in a
  column on each side, pushed apart symmetrically, up and down, from
  their natural height, with elbow leader lines.

  Fixing that took three tries, each caught by a measurement:
  1. Widening the axes after the labels inside the wedges were drawn
     squeezed the lines of two-line labels into each other.
  2. Reserving column room up front, always, shrank the pie until a
     long name no longer fitted inside a 327-degree slice.
  3. Now: which labels fit inside is decided before anything is drawn,
     at the largest pie, and column room is reserved only for the labels
     that actually go outside. Then the decision is repeated until it
     stops changing, since a smaller pie can push more labels out.

  A pie whose labels all fit inside is now bigger than before, with a
  5% margin. Tracing that loop also showed that inside labels were
  limited to two lines, so a long name in a big slice was sent outside.
  Three are allowed now, but a wrap that breaks a word ("Divor / ced")
  is never used.
- **The inside-label size.** One small slice's label could drag every
  inside label down to 7pt. The inside size now follows the rule
  `county_map_chart`'s labels use: the largest size at which every label
  that fits at all fits. If that's under 10pt, labels stay at 10pt when
  most still fit, and the rest go outside.
- **Spiral labels.** The spiral tried labels only beside their point, and
  between tight loops nothing fits: a 40-point spiral drew 1 label of
  the 9 it tried.
  - Labels are now tried in order of importance (last point, highest,
    first, lowest). A label with no room beside its point goes just
    outside the spiral with a leader line.
  - At half a revolution a label was pushed off the page; labels are now
    kept inside the plot.
  - A few points over many revolutions drew a jagged star, because the
    curve had 14 samples between points however many turns that
    spanned. It's now sampled by angle.
- **One long name shrank every label** in `bar_chart` and
  `butterfly_chart` to 8pt. They shrank first and wrapped only below
  8pt. Now the largest size wins at which every label fits the lines
  its row has room for without breaking a word, so the long name wraps
  and the rest stay at 12.5pt.
- **Tied values broke the map's colour classes.** Quantile boundaries
  coincided when many counties shared a value, and:
  - three distinct values drew "1 1 1 2 2 3 3 3";
  - an all-equal map read "5 5 5 5 5 5 5 5";
  - two counties got five empty classes;
  - `n_classes=1` crashed, as did `get_sequential(n=1)`;
  - long numbers across many classes printed on top of each other.

  Now:
  - every boundary is an actual county's value, printed at the data's
    precision (at most four significant figures), never "-0";
  - every class holds a county;
  - a handful of distinct values get a class each, labelled with the
    value;
  - colorbar labels thin out rather than overprint, keeping the first
    and last.

More turned up afterwards: three from reading what the labels actually
say, rather than only checking whether they overlap or leave the figure
(the harness had tried integers and dates as labels, but only Python's
own `datetime.date`, which happens to print cleanly), one from the
harness's timings, and two from looking closely at before-and-after
renders.

- **Numbers and dates printed the way Python prints them.** pandas
  makes a column of years float whenever it has a gap, and turns dates
  into Timestamps, so category, series and segment names read
  "2018.0", "2018-01-01 00:00:00" or "2018-01-01T00:00:00.000000" (the
  spiral wrapped that last one mid-number, and the pie split
  "2021-01-01 / 00:00:00 15%" over two lines). Arithmetic left labels
  like "0.30000000000000004". Labels are now written the way a person
  would write them: "2018", "Jan 2024", "2024-03-01", "0.3".
  - Dates follow the area chart's rule: the year alone when every date
    is 1 January, month and year when every date is the 1st. Both need
    at least two dates, since one date on 1 January could mean that
    day.
  - A set of floats shares one number of decimals, the fewest that
    show every value ("0.5, 1.0, 1.5"). Integers mixed with floats
    print as written ("1, 2.5, 3").
  - Text is never changed, and if tidying would make two different
    categories read the same (0.3 and 0.1 + 0.2), every label is left
    exactly as Python prints it.
- **A number as a title crashed every chart** with "expected string or
  bytes-like object, got 'int'" -- a DataFrame's column name, say.
  Titles, subtitles, the butterfly's side labels and the map's colorbar
  label now take any value, as matplotlib's own text does.
- **A missing x in the area chart.** NaN crashed with matplotlib's "Axis
  limits cannot be NaN or Inf", NaT with "'float' object cannot be
  interpreted as an integer", and None silently turned the axis into
  evenly spaced text with "None" printed on it. Each is now an error
  that names the position.
- **Many slices were slow.** A 60-slice pie took about 10 seconds, for
  two reasons:
  - every wedge's texture image covered the whole pie;
  - each label was measured again at every size whenever the layout
    was revised, about 15,000 measurements of 900 different strings.

  Textures now cover only their own wedge (or band, in the area chart)
  at the same scale, and each figure keeps the sizes it has measured.
  The same pie takes about 3 seconds, and a 30-band area chart 3
  instead of 6. Renders are unchanged: no pixel moved by more than 3
  levels out of 255.
- **The area chart's edge labels hung over its border.** The fix above
  that measured x from the plot's padded edge clamped labels to that
  edge -- but the padding lies outside the drawn area, so numbers and
  band names at either end crossed the area's border line, and white
  numbers on the cream background lost a digit: "1,900" read ",900".
  Every measurement passed, because the text stayed inside the plot.
  Labels are now clamped inside the drawn area, 5px clear of its
  border for numbers and 6px for band names.
- **Pies with outside labels were small, and in a wide figure tiny.**
  The plot was a square, and room for a label column was taken from all
  four sides of it whichever side the labels were on. With every
  outside label on the left, a 9-inch pie came out 3.5 inches across
  beside an empty strip as wide as the labels; in a 12 x 6 figure the
  square was the figure's height, the columns didn't fit beside it, and
  the last-resort zoom shrank the pie to a dot half an inch across with
  its labels printed on top of each other.

  The plot now takes all the room below the title, and the pie and its
  columns are laid out across it as one group, centred, with a column
  only on a side that has labels. The same pies are 5.7 and 5 inches
  across. Pies with every label inside keep their size; in a tall
  figure they're now centred in the room below the title, where they
  used to sit at the bottom of it. Wrapped outside labels are also
  balanced now: "Trade and / transportation 2%", not "Trade and
  transportation / 2%".

Checked afterwards:
- The harness again: every variation either renders with no
  problems or raises a clear error for input that really is invalid
  (a missing value, a negative value where lengths or angles can't be
  negative, a repeated x). The only exception is emoji on a machine
  with no emoji font matplotlib can draw.
- Every chart under common user settings -- dark and ggplot styles,
  24pt default text, 300 dpi, a serif font, LaTeX text, tight saving --
  keeps its own look with no text problems.
- The area-label probe from the real-data pass reproduces its earlier
  results.
- 138 tests in `tests/test_any_data.py` cover all of this, and 98 of
  them fail against the code from before this pass, spread across
  every class.

## Large data: hundreds to thousands of points

The stress test above stopped at about a hundred points per chart. Real
data often has far more: ten years of daily values, a population pyramid
with a row for every year of age, every country in the world. So each
chart was run at a few hundred to a few thousand points -- 17 cases from
a 200-bar chart to a 3,650-day area chart -- and checked the same way:
overlapping or clipped text, figure size, time.

The area chart, spiral and map handled it. A 101-row population pyramid
was fine too. The rest:

- **Bar and butterfly labels printed over each other.** With 200 rows in
  a figure capped at 22 inches, each row was 16px, and the category
  labels came out at 12.5pt -- 26px tall -- on top of each other, the
  first half off the top of the figure. `fit_label_column` counted a
  size as fitting whenever its text fit the width, even if one line was
  taller than the row. Now a size fits only if its line fits the row,
  and:
  - figures grow past 22 inches (20 for butterfly charts) when needed,
    up to 32, so rows stay at least 0.15 inches, room for an 8pt label:
    200 countries get a label each;
  - beyond that, labels go one row in k at 8pt, always including the
    first and the last, with a warning that says so and how to label
    them all; value labels go on the same rows, past the longest bar
    beside them so they don't print over its end;
  - value labels take the largest size up to 11pt that fits their row,
    and grouped bars too close together for an 8pt number get none,
    with a warning;
  - bars under 8px tall get thinner outlines, and under 4px none: at a
    thousand bars, 1pt outlines left more ink than colour.
- **Titles on tall figures overlapped the chart.** Every chart started
  its title at 99% of the figure's height, which on a 31-inch figure is
  47px down -- past the room reserved for it. Titles now start 1% down
  but never more than 0.09 inches, which leaves every figure up to 9
  inches tall exactly as it was.
- **A 200-slice pie's labels ran off the figure.** Its outside-label
  columns were taller than the figure even at 7pt. The smallest slices
  now go unlabelled until the columns fit -- they're still drawn -- with
  a warning suggesting an "Other" group.
- **The snake chart crashed from about 170 segments.** It reserved
  legend room for every segment, four to a row, whether a segment needed
  the legend or not. At 100 segments that squeezed the snake into a third
  of the figure, and at 170 the room was taller than the figure:
  matplotlib's "bottom cannot be >= top". The legend now gets the room it
  needs, found by fitting the names, sizing the legend, and fitting
  again until that settles, with as many columns as the names allow and
  at most 35% of the figure. If its names don't fit there it lists the
  largest segments and ends "+ 434 more", with a warning. A snake whose
  names all fit no longer keeps an empty band for a legend it doesn't
  have.
- **Slow.** A thousand bars took 42 seconds, almost all of it painting
  a texture onto each bar; rectangles under 6px across now get none,
  since it can't show, and the same chart takes 3. A 500-segment snake
  checked every narrow piece in full for room for its name (17 seconds);
  a piece narrower than the name's longest word is now ruled out at
  once.

After the fixes, all 17 cases render with no overlapping or clipped
text. The slowest are a 500-segment snake (about 20 seconds) and a
200-row butterfly chart (about 15), nearly all of it texture:
`texture=False` brings them down to 3 seconds and under 2. (A faster
texture, below, has since brought them to 11 and 9.)

## A faster texture, and the county map with real county data

**The texture, about twice as fast, drawing exactly the same.** The
hand-painted grain was most of the time in any large chart: 27ms for
each bar, wedge or snake piece. Half of that was one blur, 45 rows deep,
that scipy runs as a loop over a 361-point filter. The same blur is a
matrix product -- the matrix built once, by blurring the identity
matrix, so it handles the edges exactly as scipy does -- and takes a
tenth of the time. The colour blend now runs a channel at a time instead
of on the whole array. A grain now takes 10ms. Every example image, and
pies, bars, butterfly and snake charts of up to 200 items, render
pixel-for-pixel the same as before; a 30-band area chart differs in 438
pixels by one level out of 255, rounding in a blend formula that was
written two ways. Tests compare both pieces against the original
computations. A 200-row butterfly chart now takes 9 seconds instead of
15, and a 500-piece snake 11 instead of 21.

**County keys and boundary files.** `county_map_chart` matched counties
by name only, and only names under the GeoJSON property `NAME`:
- FIPS codes -- how a great deal of US county data is keyed -- matched
  nothing. Every county drew as missing, with a warning that listed every
  key as an unknown name. Now 13121, "13121", 13121.0 (pandas), "121"
  and the Census GEO_ID "0500000US13121" all find Fulton. The bundled
  boundaries now carry each county's GEOID and COUNTYFP, taken from the
  Census county list and checked against a second list, all 159 the
  same.
- The Census's own names, "Fulton County, Georgia", didn't match
  either; anything after a comma is now ignored, along with "County",
  "Parish", "Borough" and similar.
- A boundary file of your own crashed with `KeyError: 'NAME'` unless
  its names were under exactly that property; `name`, `NAMELSAD`,
  `NAME_2`, `county` and others now work, and a file with none of them
  gets an error that lists the properties it does have.
- A county in several pieces kept only the first: islands disappeared.
  A county with a hole in it -- a city that's a county of its own,
  inside another -- was drawn with the hole filled in its own colour,
  covering the county inside whenever that one came first in the file.
  Both are now drawn whole, with the hole left open. (The bundled
  Georgia file has neither, and draws exactly as before.)
- A file covering several states would have matched one "Washington
  County" value to all of them; it's now refused with an error
  explaining that the chart draws one state at a time.

## Every state's counties

`county_map_chart` drew Georgia and nothing else: county data for any
other state couldn't be mapped without finding, converting and passing
a boundary file. It now takes `state=` -- a name, postal code or FIPS
code -- and draws any of the 50 states, DC, Puerto Rico and the island
territories, from the Census's 2017 cartographic county boundaries as
packaged by us-atlas (ISC licence, kept alongside; 842KB as TopoJSON,
decoded per state when asked for). Georgia stays the default and keeps
its own bundled file: its maps are pixel-for-pixel what they were. Data
keyed entirely by one state's five-digit FIPS codes draw that state
without being told.

Every state and territory was then drawn with random data, titled and
with a colorbar label, at the default 6 labels and again at 15, and
checked for text overlapping or leaving the figure. What that took:

- **Alaska crosses 180 degrees.** The western Aleutians have
  longitudes of +172 to +180; projected as they come, Alaska spans the
  globe. Longitudes east of 180 are moved 360 degrees west whenever a
  state's span exceeds 180.
- **Tall states made tall figures.** The map is 9 inches wide and as
  tall as its shape requires, which for Delaware would have been 21
  inches, and for the Northern Mariana Islands' line of islands 24. The
  figure now narrows to keep the map within 10 inches tall, down to 5
  inches wide -- the title and colorbar need that -- and past that the
  map narrows inside it.
- **The colorbar was sized in fractions of the figure's height.** On
  the 24-inch figure that made a bar 100px thick. Its sizes are now
  capped at what they are on Georgia's map (in inches), so Georgia's is
  unchanged.
- **A callout landed on the colorbar label.** The label sits partly
  inside the map's frame, below the state, which on Georgia had always
  been empty; one of Michigan's callouts was placed on it. Callouts now
  keep clear of it.
- **Discrete colour classes printed values in full.** With four
  counties and computed rates, the classes were labelled "4.985380",
  "9.323244" -- too long to sit side by side on a narrow figure, so two
  ran off it. They now follow the continuous classes' rule: at most four
  significant digits, more only if two values would print the same.
- **Names.** The boundaries name counties without "County", so the
  places where a county and an independent city share a name --
  Baltimore, St. Louis, and Virginia's Fairfax, Franklin, Richmond and
  Roanoke -- would have been refused as repeated names; they're
  "Fairfax County" and "Fairfax City", and data can say "Fairfax city",
  as the Census does. Name matching also learned "Parish", "Borough",
  "Census Area", "City and Borough", "Municipality" and "Municipio",
  "Saint" for "St.", and accents ("Dona Ana" finds Doña Ana, "Mayaguez"
  Mayagüez).

After that, all 56 draw with no text overlapping or off the figure, at
6 labels and at 15, each in under a second.

## Room for callouts

The every-state sweep checked that no text overlapped or left the
figure, and none did. Counting the labels and measuring the leader lines
found what that check couldn't see:

- **Labels went missing, silently.** A callout could only go inside the
  map's frame (the state's bounding box). A state that fills its frame
  -- Colorado, Kansas, North Dakota, rectangles more or less -- often
  had no room left in it, and the county was simply not labelled:
  Colorado drew 5, 6 or 7 of the 8 labels asked for in 8 of 12 random
  data sets, Kansas and North Dakota lost labels too, and nothing said
  so.
- **Labels landed far from their counties.** When the frame's only gap
  was elsewhere, the label went there: Kansas's Washington County, on
  the state's northern edge, was labelled 1.95 inches away in the
  frame's corner, its leader line running over the counties between;
  Puerto Rico's and Pennsylvania's callouts went 2 to 2.8 inches.

Callouts may now go outside the frame too: into the figure's margins,
which costs nothing, or past them -- above and below the map, and beside
it when the figure's size is the chart's to choose -- which makes the
figure bigger. The spot chosen is the one with the shortest leader line,
counting each inch the figure would grow as an inch of line (sideways
twice, since the figure widens on both sides to keep the map centred
under its title). The map keeps its scale and the colorbar its size; a
width given in `figsize` is kept, so then only the height grows. If a
county still has nowhere to go, a warning names it.

Measured on every callout of every state at 6 labels -- the leader
line's length less the distance from the county to the nearest edge of
the state's frame, i.e. how much further than the edge the label went --
the worst was 1.74 inches before and is 0.24 now. Every label asked for
is drawn, at 6 and at 15. Figures grew in 11 of the 56 states at 6
labels and 14 at 15, by at most 0.8 inches wide or 0.6 tall. A county in
the middle of a state with straight borders still has a long leader line
-- the state's edge is the nearest place outside it -- which is left as
a known limitation. Georgia's example map, which has room for its
callouts inside the frame, is pixel-for-pixel what it was.

With more room to search, a crowded map got slow: 60 labels on a 5-inch
Virginia took 5.6 seconds, nearly all of it trying spot after spot for
labels that had none. The check that a leader line runs through no
other label now takes a batch of spots at a time, visiting exactly the
cells it did one spot at a time -- every state's map, at 6 labels and at
15, is pixel-for-pixel the same -- and that map takes 1.9 seconds.

## The whole country

Data by state, or county data from more than one state, still drew
Georgia: an empty map, with every key named in a warning. Worse, a
county written with its state, as Census tables write them, matched
Georgia's county of the same name: "Cook County, Illinois" was drawn as
Georgia's Cook County and "Harris County, Texas" as Georgia's Harris,
without a word.

- **`state_map_chart`** draws the country by state -- keyed by name,
  postal code, FIPS code or GEO_ID -- laid out as d3-geo's Albers USA
  projection does: the lower 48 in Albers' equal-area conic projection
  (standard parallels 29.5 and 45.5 degrees), Alaska at 35% scale and
  Hawaii inset below California and Arizona, and Puerto Rico off Florida,
  as d3-composite-projections places it, when the data include it. A
  test checks the projection keeps areas: two one-degree cells, at 30
  and 45 degrees north, project in the ratio of their areas on the globe
  to one part in ten thousand. The District of Columbia, too small to
  see, is a dot in its colour.
- **`county_map_chart`** draws every county in the country when its
  data span states -- by FIPS code or by "County, State" names -- or
  when asked with `state='US'`: thin county lines, the states' borders
  over them, labels like "Cook, IL".
- **Names with a state are that state's.** On one state's map, a county
  named with another state is named in the warning, which suggests
  `state='US'`; data that all name one state draw that state. State
  names given to `county_map_chart` point to `state_map_chart`, and bare
  county names on the country's map are asked for their state.

What drawing them took:

- **Speed.** The first map of the country's 3,200 counties took 5
  seconds, four of them matplotlib working out each shape's data
  limits -- which this chart sets itself. Shapes are now added without
  that, and the free space for callouts is marked from the 51 states'
  outlines rather than 3,200 counties: 1 to 2 seconds. Labelling all 50
  states took 12 seconds, nearly all of it fitting names inside states;
  spots are now tried nearest the centre first, after ruling out those
  where the name doesn't fit at all, by its corners: 3 seconds. On the
  56 state maps and the examples, every label lands where it did before.
- **Callouts at 11pt.** On the country's counties no name fits inside
  its county, and the shared label size -- set by the names that fit --
  went to the largest, 11pt, crowding the map. When every label is a
  callout, they're now 9pt. (That changed two of the 56 state maps,
  whose six labels were all callouts.)
- **Crossing leader lines.** Callouts were placed one at a time, each at
  the spot nearest its county, so a later one's line could cross an
  earlier one's: with 15 labels, 9 of the 56 state maps had crossing
  lines, and 14 of 40 maps of five crowded states with other data. A
  spot whose line would cross another's now costs as much as half an
  inch more line; and once all are placed, lines that still cross get
  their labels swapped -- lined up on the side the lines meet -- or one
  of them moved, when that's worth the extra length. None of those 96
  maps has a crossing now. The 50 states labelled throughout, 25 of them
  callouts in the crowded Northeast, still have three.

Measured on state maps at 0, 6, 15 and 51 labels in three figure sizes,
and on the country's counties at 0, 6 and 15 labels in two: no text
overlapping or off the figure, and every callout clear of the map.
Georgia's example and the other examples are pixel-for-pixel what they
were.

## Getting it ready for other people

Everything above had only ever run on one machine: Linux, Python 3.11,
matplotlib 3.10, Liberation Mono. This round checked the rest of the
world, and found:

### A name of its own

`dubois` -- the name the package was imported by -- is taken on PyPI, by
an unrelated project in the same field (David White's Du Bois colour
palettes and matplotlib style, December 2025), which installs a
top-level `dubois` package too. Installing both would have let one
overwrite the other. Nothing had been published, so the package was
renamed while that was free: `pip install dubois-charts`,
`import dubois_charts` (`import dubois_charts as dc` in the docs).

### Other versions, other systems

The suite ran on Python 3.10, 3.12, 3.13 and 3.14 -- and, before the
release, on 3.15, out that month -- with the newest numpy, matplotlib,
scipy and pandas (2.5.3, 3.11.2, 1.18.1, 3.0.6), and on Python 3.10
with the oldest it now allows (1.21.6, 3.6.3, 1.7.3, 1.3.5). It had
claimed Python 3.8 to 3.11 and matplotlib 3.5 or newer:

- **matplotlib 3.5 can't be used.** It has no `text.parse_math` setting,
  which keeps "$5-$10" from being read as maths. The minimum is 3.6.
  Python 3.8 and 3.9 are past their end of life; the minimum is 3.10.
- **Python 3.10 has no `tomllib`**, which the packaging tests use to read
  `pyproject.toml`; they fall back to `tomli` there.
- **matplotlib 3.11 logged a warning for every bold word** -- "findfont:
  Failed to find font weight bold for WenQuanYi Zen Hei" -- when a
  fallback font that comes only in regular (most CJK fonts) was in the
  font list. That message is now dropped for the fallback fonts, and
  only for them.
- **matplotlib 3.11's text moved by a pixel**, with the FreeType it
  bundles (2.14, after years of 2.6). The Plate 51 test's colour probe
  landed on a letter, and now takes the row's median colour. On
  Virginia with 15 labels, two callouts' leader lines crossed, and the
  swap that should have uncrossed them was refused: its check used the
  free-space grid, whose margins around every label made the swapped
  boxes look blocked. Swaps and reorderings are now checked against the
  other labels' exact boxes.
- **Windows reads files as cp1252** unless told otherwise, and "Doña
  Ana" (New Mexico) came out garbled from the bundled boundaries. Every
  file is opened as UTF-8.

### Fonts on a Mac or a PC

The charts had only been drawn with Liberation Mono. A Mac or a Windows
machine has Courier New instead -- and it was never used: DejaVu Sans
Mono, which ships with matplotlib, came second in the list, so it always
won. Courier New now comes before it. Simulating those machines -- with
FreeMono, Courier's metrics, standing in as "Courier New" -- and a bare
one, with only matplotlib's DejaVu, found two more:

- **A pixel shrank every label on a map.** Labels share one size: the
  largest at which most names fit, "most" being 60% of the names that fit
  at any size. Courier's 6pt text is a pixel shorter than Liberation's,
  so two tiny Georgia counties started to fit at 6pt, the share at 8pt
  fell below 60%, and every label on the map went to 6pt. Labels are now
  8pt unless that would make more than max(8, 2n/3) of the n labels
  callouts.
- **Three callouts in reverse order.** In DejaVu, Virginia's King George,
  Caroline and Hanover were stacked so that every pair of their lines
  crossed, and no swap of two labels could fix it. A group of callouts
  whose lines cross is now placed again together, in each order that
  could work, keeping the shortest lines with no crossings.

Every chart lays out cleanly in all three font sets (tested in
`tests/test_fonts.py`, which hides every font but matplotlib's own).

### Colour-blind readers

No palette had been checked for colour-blind readers. Each was, now, as
it looks to readers with protanopia, deuteranopia and tritanopia
(Machado, Oliveira and Fernandes's 2009 simulation), measuring how
different two colours look as CIEDE2000 differences -- about 1 is just
noticeable, 15 or more clearly different:

- **The classic palette fails them.** Its crimson and green are under 7
  apart for a deuteranope -- two olives. `set_colorblind_safe()` switches
  every chart's default colours to `DUBOIS_COLORBLIND_8`: eight of Du
  Bois's own colours and tones of them (crimson, gold, black, steel blue,
  ultramarine, gray, claret, pale blue), chosen one at a time as the one
  most different from those already chosen, for every reader at once.
  No two are less than 16.6 apart for anyone. Past eight categories, a
  warning says some will look alike.
  `get_diverging(n, colorblind_safe=True)` runs crimson to blue rather
  than crimson to green, each colour as light as its mirror.
  (`get_diverging(6)` used to print a note and return seven colours; it
  returns six.)
- **Map classes, light to dark, for everyone.** The sequential palettes
  the maps use are now spaced evenly in perceived lightness, so
  neighbouring classes are at least 7 apart for every reader, at 3 to 7
  classes.
- **"No data" looked like data.** The colour of a county without a value
  was 1.1 from a crimson-pink class for deuteranopes -- indistinguishable.
  It's now a grey-lilac at least 12.9 from every class of every palette,
  for every reader, and a "No data" swatch beside the colour bar says
  what it means.

`simulate_colorblindness(colors, kind)` shows anyone's colours the same
way.

### Image comparison, in the test suite

Each round had ended with pixel-diffing the examples by hand. Nineteen
reference images now sit in `tests/baseline/` -- every chart type,
including the adversarial cases from the first fixes (`area.py`, above:
a 130-character title, five long series names, six long categories,
thin bands; and short labels the fixes weren't made for), a map of the
whole country, Virginia's crowded callouts, a 40-point spiral and Plate
51 -- and `tests/test_images.py` compares each chart with its reference.
A picture depends on the exact matplotlib, the FreeType it was built
with, numpy and scipy (the texture), so they're compared only where
those match `tests/baseline/environment.json`, and every font but
matplotlib's own is hidden while they're drawn. GitHub's "Image
comparison" job installs exactly those versions, and fails rather than
skips if they don't match. Three deliberate changes -- crimson ten
levels darker, value labels 8.5pt instead of 9, county lines 0.7pt
instead of 0.6 -- each failed it.

### Words outside their bands

Drawing the references found a bug in the area chart's first fix. A
band's name was placed at the band's middle at its thickest data point,
checked only against the band's thinnest *thickness* under the label --
not against where the band actually is. A sloping band can be thick
enough all along a label and still leave it: in the long-names case,
"TRADE AND TRANSPORTATION" dipped into the band below it, and "DOMESTIC
AND PERSONAL SERVICE" sat across two bands. On data that changes much
from point to point it was the rule, not the exception: 38 of 40 random
datasets had a name or a value partly outside its band. Value labels had
the same gap -- the band's middle, their first choice, went unchecked.

A name now goes where the band has room for it across the label's whole
width: every position along the band is tried, the room at each is the
gap between the highest point of the band's lower edge and the lowest
point of its upper edge, and the name is centred in that gap. Among the
positions with close to the most room, the one nearest the middle of
the chart wins. A name that fits nowhere on one line is tried on two,
broken where the longer line is shortest. Values are checked the same
way. None of the 40 random datasets has text outside its band now, and
the long-names chart has four of its five names inside, rather than
three (two of them misplaced).

### Leader lines on a tight spiral

On a tightly wound spiral there's rarely room for a label beside its
point, and every label that didn't fit went outside with a leader line
-- from deep inside, across loop after loop (five, on a 40-point
spiral), to end in a tangle no reader could follow. On a 60-point
spiral two leaders crossed each other; on a 30-point one, a label was
drawn over another's leader. And the labels were chosen every n/9
points, which on the 60-point spiral -- about seven points a turn -- put
all nine on one ray.

Now leaders cross no other leader, no label and no labelled point; each
goes the way across the fewest loops; and only the first, last, highest
and lowest points may have one that crosses more than one loop. The
other labels go to points where they fit: at a step through the series
that sends successive labels at least a fifth of a turn apart, at the
tops and bottoms of the turns, where the loops run level and a line of
text fits between them, and then wherever on the page is farthest from
the labels already placed. On the 40-point spiral the leaders cross 7
loops in all instead of 21 -- five of them the first point's, from the
very centre. Over 120 random spirals nothing breaks those
rules, and 117 get every label they could have (min(n, 9)), against 85
before.

### Only the first chart showed in Jupyter

Writing the tutorial notebook found this one: in a fresh Jupyter
session, the first chart showed and nothing after it did -- not another
chart, not any matplotlib figure. Every chart draws its text with
matplotlib's maths parsing off, and did it inside `rc_context`, which on
the way out puts back every setting as it was. matplotlib switches its
interactive mode on when it makes a session's first figure -- and when
that figure was a chart's, `rc_context` switched it straight back off,
and Jupyter only shows figures made in interactive mode. (Running
`%matplotlib inline` first hid it, which is why it went unnoticed.) The
charts now change the two text settings and put back only those. A test
checks that a setting changed while a chart is drawn is kept; it fails
on the old code.

### Hundreds of shapes, one picture

A chart of 300 bars took 4.2 seconds, a 200-row butterfly 4.9, nearly
all of it the hand-painted texture: every bar, slice, snake piece and
band had a picture of its own, made, clipped and drawn at several
milliseconds apiece. Now the texture of a whole axes is one picture
(`GrainLayer` in `_common.py`), made when the chart is drawn, at the
resolution it's drawn at: each shape's grain is sampled from its own
field of noise, stretched over its box exactly as its own picture was,
and clipped to it as the renderer clipped it -- a rectangle snapped to
whole pixels, anything else by the renderer's own coverage. Past 24
shapes, a shape borrows an earlier one's noise, in its own colour. A
test draws each kind of shape the old way, one clipped picture each,
and compares: the same to within a level here and there.

One difference shows: a bar's right-hand outline. The old pictures were
clipped to a rectangle as a box, which the renderer rounds out by a
pixel on the right, so the texture covered the right edge of every
bar's outline; now all four edges show alike.

Measuring text made a new text object for each of the ~3,000 different
labels a 300-piece snake chart tries; one reused object measures them
the same, a tenth faster. And a 500-point spiral spent a second
having matplotlib work out the extent of each point's dot from its
curves, for limits the chart sets itself; the dots, and pie wedges, are
added without that. Before and after, drawing and saving a PNG:

| chart | before | after |
| --- | --- | --- |
| 300 bars | 4.2 s | 2.0 s |
| 200-row butterfly | 4.9 s | 2.0 s |
| 300-piece snake | 3.7 s | 1.8 s |
| 200-slice pie | 3.0 s | 1.4 s |
| 500-point spiral | 1.6 s | 0.7 s |

What's left in those is mostly matplotlib drawing a few hundred labels
and writing a 1350 x 4800 PNG.

## What two first users found

Before the first release, two people who had never seen the package
used it from scratch, from the built wheel: one as a new user, with data
of their own and the mistakes people make, looking at every chart; one
checking every claim in the documentation against the code. The test
suite passed throughout -- these are things no test had asked about.
Each is now tested (`tests/test_first_users.py`, `tests/test_docs.py`):
every fix has tests that fail on the code before it, alongside a few
that check the cases that were already right stay so.

**Wrong numbers, without a word.** A pandas Series was taken in order,
whatever its index. A pivot table's rows come sorted -- '0-4', '10-14',
'5-9' -- so a population pyramid drawn from one put the 10-14 figures on
the 5-9 row. Now a Series whose index names the categories is matched to
them by index, as pandas would; an index that names none of them (the
default 0, 1, 2..., or a filtered table's row numbers) leaves the values
in order; one that names some but not all is an error saying which.
pandas 3 makes a `RangeIndex` of any evenly spaced whole numbers -- the
years 1990, 2000, 2010 -- so only 0, 1, 2... counts as the default.

**Grouped bars.** The gap between the bars of a group was a fixed 0.12
of the row: most of each bar's share from four series, all of it from
five (bars a pixel or two thick), more than all of it from six -- where
the height came out negative and the bars drew upside down. The gap is
now at most about a third of a bar's share.

**Legends.** A fixed four columns and a fixed row's room: long names ran
off both sides of the figure, a second row sat on the chart, and
matplotlib's column-by-column filling read 2019, 2021, 2023, 2024 /
2020, 2022. `add_legend` in `_common.py` lays every legend out (bar,
area and snake): as many columns as fit, entries ordered to read across
each row, a name too long for a line broken onto more, the size the
largest that fits. The bar chart makes its legend first and lays the
bars out above it; the area chart, which only knows which names need the
legend once it has fitted them to the bands, draws itself again with
room for more than one row when it needs it. (The legends asked for
9.5pt but got 10: given font properties without a size, matplotlib uses
its own legend size and ignores the one passed. Now the size is set.)

**Names shrunk for slivers.** An area chart's band names, and a snake's
segment names, share one size: the largest at which most of them fit.
When most never fit at any size -- thin bands, slivers of a snake -- that
rule fell through to the smallest size, so one band filling most of the
chart was named in 8pt type. Now the size is then the one that fits the
most names from 10pt up, the others going to the legend.

**The snake's scale.** The marks at each row's ends -- the chart's only
scale -- were drawn inside the row, over whatever segment was there, in
dark ink: "3,500 €" on navy couldn't be read. They go under the rows now,
on the background (inside, on a patch of background, only when rows are
too close together). And a value split from its unit at a line break
("152" / "€"): numbers are joined to their units with no-break spaces,
which `wrap_text_to_width` now honours.

**Spiral labels past the next loop.** A label beside its point was
checked for the curve inside its box, not between it and its point: on a
spiral whose loops sit close (carbon dioxide at Mauna Loa, 317 to 425
ppm), labels for points on the inner loop landed past the outer one,
clear of the line but reading as the outer loop's. Now a label without a
leader line has no part of the spiral between it and its point.

**Numbers.** Data needing more than two decimals got enough for three
significant figures of the smallest value, whatever the data had: 0.012
printed "0.01200". Now the fewest decimals that show every value, up to
that. A butterfly chart's sides shared one format, so 0.012 on one side
made the other print "1,250,000.0000"; sides of very different sizes --
different units, most likely -- now get a format each, and a warning
that the smaller side's bars are too short to see.

**Maps.** Data that matched no place drew a blank map with a warning;
it's an error now, as are two keys for one place ('NY' and 'New York').
A plain "Richmond" in Virginia was taken, silently, to be Richmond
County, not the city of Richmond; it still is, with a warning saying
how to choose. Florida's county names, given without `state=`, drew
Georgia's counties of the same names: names are now looked up in every
state's counties, and names only one state has draw that state, names
several have (Georgia among them) draw Georgia with a warning, and names
several other states have are an error. A key that matches nothing is
named with the county closest to it in spelling, or the states it is a
county of; Connecticut's planning-region codes, newer than the bundled
boundaries, are explained.

**Themes.** `reset_theme()` put back every setting as it was before the
first `set_theme()` -- undoing settings of the user's own made since,
and, like the theme blocks (`dubois_style()`, `DuBoisStyle`), switching
off the interactive mode matplotlib turns on at a notebook's first
figure: the same bug as the one in "Only the first chart showed in
Jupyter", above. They put back only what the theme changed now.

**Small things.** Every chart printed "Saved: ..." when it saved, and
`show_palette()` called `plt.show()`; a library shouldn't do either. A
`font` that isn't installed brought about twenty lines of matplotlib's
"findfont: Font family not found"; it's one warning now, and the usual
face. Errors for negative values name the value and its category; a
dict of single numbers given to `bar_chart`, a fractional `n_rows`, and
a DataFrame given to a map or a pie say what to pass instead.

**The documentation.** Nine of the README's nineteen examples didn't run
as written (a missing import, data never defined); several docstring
examples showed output their code doesn't give; no chart's docstring
described `background`, `dpi` or `font`, and some told the history of a
parameter rather than what it does; the palettes were called
"extracted from Du Bois's original visualizations", which only the
Plate 51 colours are; the CI was said to run "on every push" and "in
full" on macOS and Windows, which it doesn't. `tests/test_docs.py` now
runs every README example and docstring example, and checks every
chart's docstring describes every parameter.

## What real data found

Then every chart was drawn from real public data, read the way a user
would read it -- with pandas, reshaped as little as possible -- and
installed from the built wheel: the data for Du Bois's own plates (the
#DuBoisChallenge files, 50 charts from 46 plates); census population by
age and sex; unemployment by industry, by month, and by county; jobs by
sector; COVID-19 deaths by state; the 2020 presidential vote by county;
demographics of every county in the country; state agricultural
exports; carbon dioxide at Mauna Loa; global temperature by decade;
births by month and weekday; CO2 by country; America's electricity by
source. 85 charts, each looked at, and their numbers checked against
the files: every value drawn was right. The trouble was elsewhere, and
each kind is tested now in `tests/test_real_data.py`, with a few rows
shaped like the file that showed it. 83 of its tests fail on the code
before; the other 20 check what the fixes mustn't change.

**Rows that aren't data.** Plate 55's file ends in a total whose name
cell is empty, read by pandas as NaN: `bar_chart` drew a fourth bar,
labelled "nan", three times the others. A row with no name is an error
now, saying which row. Plate 22's file has the year 1880 twice: two
bars called 1880, in different colours, without a word -- a warning now.

**Missing values on a map.** A rate made from two tables is NaN wherever
either has no row (COVID-19 deaths per 100,000, from deaths by state and
a population table without the territories). A NaN on a map was an
error, and with the NaNs dropped by hand, "PR" from one table and
"Puerto Rico" from the other were "two values for Puerto Rico" -- both
NaN. On a map a missing value means no data now, drawn as such; only
the bar, butterfly, area, spiral, pie and snake charts, which have no
way to draw one, still refuse it, with a pointer to `.dropna()`.

**Counties that aren't on the map.** The bundled boundaries are 2017's.
Data from before then use counties since renamed, merged or divided:
Shannon County, South Dakota (Oglala Lakota since 2015), Wade Hampton
(Kusilvak), Bedford city (part of Bedford County since 2013), three
Alaska census areas divided in 2007 and 2008; Du Bois's 1890 Georgia has
Campbell and Milton, merged into Fulton in 1932. The warning listed
bare codes, or misled: "'Bedford city' -- Radford?" (another city,
already in the data, so following it gave "two values for Radford");
"'CAMPBELL' is a county of Kentucky...: is `state` right?", when 135 of
the 137 names were Georgia's. Now the warning says what became of those
counties; doesn't suggest a county that already has a value, unless the
name is that county's plus something ('BIBB02' -- "a second row for
Bibb?"); and when most names are the state's counties, says the others
aren't on the state's map rather than doubting the state.

**Signed data on a map.** The presidential margin by county runs from
-87 to +93, and on the one crimson scale, narrow wins for each side
shared a class, "-6 to +17". Classes now have a boundary at zero, split
evenly between the sides (in proportion to the counties, the fifth won
by one side all got one class), and by default a diverging scale: green
below zero, crimson above. For colour-blind readers the green is blue,
and the "No data" grey, as near the pale blues as 4.7 in CIEDE2000 for
some readers, is a dark grey there instead; every class of every split
is at least 12 from it, for every reader, as the tests check.

**Dates.** vega's unemployment file writes each month as midnight in
California, in UTC: "2000-01-01T08:00:00Z", and 07:00 in summer. The x
labels read "2000-01-01 08:00". Dates all at about one time of day, a
day or more apart, are read as days now -- a time after midday as the
next day, midnight east of Greenwich. pandas Periods read like the
dates they stand for ("Jan 2012", not "2012-01").

**X labels.** Thinned to every k-th point from the first, labels fell
every 40th month ("Jan 2000, May 2003, Sep 2006"), or every third year
from 1874. Numbers and months are labelled at round values now -- each
January, every 2nd, 5th or 10th year -- and a run of evenly spaced labels
is kept a line's height apart: six pixels apart, "Jan 2000 Jan 2001 Jan
2002" read as one long string.

**Rounding.** Python's formatting rounds halves to even: Plate 27's 4.5%
read "4%" on a pie and "4.5%" on a butterfly chart of the same data, and
Plate 19's 1,102,866.5 acres "1,102,866". Labels in fixed-point and
percent formats round halves up now (`format_value` in `_common.py`),
taking the number as written -- 2.675 is 2.675, not the binary fraction
just below it.

**Pies of published percentages.** Plate 60's percentages add up to
100.5, as rounded ones do; labelled with their shares of 100.5, the
published 13.4% read "13.3%", four labels of five disagreeing with the
source. Values adding up to 100, give or take 2, are labelled as given
now. And wrapping closed up the two spaces between a name and its
value: "Cities / Over / 10000 9%" read as if the 10000 went with the 9%.

**Snake charts.** Plate 26's "STEAM RAILWAY EMPLOYEES" was named on the
snake without its 7,440 -- the name fitted, the number didn't -- and the
17 occupations in the legend had no number anywhere; Plate 31's legend
listed only "Rent", which was 0. A name now goes on the snake only with
its number, on up to three lines, and the legend lists the rest with
theirs ("Rent  0%"). Seventeen newspapers over five rows are 3.4 a row,
but the marks at the rows' ends, in the data's whole numbers, read "0
... 3", "7 ... 3", "7 ... 10": the marks now get decimals when they need
them to be within a twentieth of a row of where the row ends.

**Spirals.** Four years of monthly temperatures made 6.9 turns at a turn
every seven points: January 2012 at the top, January 2013 at 9 o'clock,
the years a tangle. Monthly and quarterly dates over more than a year
make a turn a year now. Labels that didn't overlap could still touch
end to end, "Dec 339,726Jan 329,962"; they're kept apart now.

**Callouts and grouped bars.** Map callouts side by side were 8-10
pixels apart, and "McCone, MT Hand, SD" or "Emporia Greensville
Petersburg" read as one name: names level with each other are an em
apart now -- unless that would take one much further from its county
(three ems or more of leader line), when it goes where it would have.
The em is kept between names only: made part of each callout's box at
first, it kept names an em further from the state's border too, and on
the newest matplotlib Tennessee's Campbell County was labelled an inch
from its county. A grouped bar's name sat level with the top
of its second bar -- the group ends a gap short of the next -- and is
centred on its bars now.

Some things the reviewers noticed were left as they are: a bar chart's
bars each get a colour of their own, as on the plates (`colors=` takes
one colour for all); a spiral's labels and a pie's outside labels leave
room around them that a chart with few labels doesn't use; and a map
labels the extremes by name only. None of the data is in the
repository: it belongs to its publishers.

### A second pass

A second round drew 74 more charts -- `tools/check_real_data.py` draws
them again -- from the same kinds of files and some others -- the New York Times' daily COVID-19 figures by state and
by county, Our World in Data's energy and CO2, FiveThirtyEight's
college majors, hate crimes and drinks, the World Bank's population,
Census estimates by state -- read even more plainly: `pd.read_csv` and
nothing else. What it found is tested in the same file.

**Dates left as text.** `pd.read_csv` doesn't parse dates unless asked,
and the area chart printed "2000-01-01T08:00:00.000Z" over its first
point and spaced the dates evenly, whatever the gaps between them. Text
written the ISO way ("2020-03-01", "2020-03", with a time or a zone or
not) is a date now, everywhere a date is: placed by time, labelled
"Jan 2000", a spiral of it making a turn a year.

**Daily figures.** Four years of days were labelled every 238th day from
the first, "2020-01-25, 2020-09-19, 2021-05-15"; they're labelled at the
first day of a round month now, by the month or the year ("Jul 2021",
"2022"), with the first and last days as they are. And the hand-drawn
wobble, one at every point, drew each of a thousand-day chart's
boundaries as a seismograph: there's one every dozen pixels now,
whatever the number of points.

**Many years.** Sixty-six years of population were labelled every other
year, tilted 45 degrees, with a column of numbers under each label --
150 numbers on one chart. Numbers and dates stay level now, at a round
step (every fifth year): tilting is for text, which has no round step.

**Decimals.** Our World in Data publishes energy use to three decimals
of a terawatt-hour, and solar power's first years were a few
thousandths: the smallest value set the precision of every label,
"11,072.753". The precision is still the data's, but no more than about
four significant figures of a typical value (the median): "11,073". And
a snake's marks at the rows' ends, round numbers, used the values'
decimals: "20.000%" now reads "20%".

**Spirals that tangle.** Monthly CO2 at Mauna Loa (313 to 414 parts per
million) drew 62 turns as one red ring; monthly births, fifteen
crossing loops; a city's average high by month, the same loop four
times over. When a quarter or more of a spiral's points are no farther
from the next turn than the line is wide, a warning says so, and what
would read better: the change from a baseline, fewer points, or another
chart for a pattern that repeats every turn.

**Keys with no place.** The New York Times' county file has no FIPS code
for New York City or "Unknown", so `df.set_index('fips')` had NaN keys,
which stopped the chart -- and pandas had read the rest as floats,
1001.0. A value with no key is left out with a warning now, as a key
naming no place is, and 1001.0 is Alabama's 01001. Codes that match
nothing say whose they are: county election results give Alaska's 40
election districts, 02901 to 02940, as its counties, and the Times
includes the Northern Mariana Islands and the Virgin Islands, which
aren't on the map of the country. The warning listed the forty codes
without a word; it lists twelve now, and says what they are.

**Names and numbers written for people.** A pandas MultiIndex names its
rows with tuples, printed "(2000, 1)"; they read "2000, 1" now. plotly's
county file writes shares as "7.47%", and the error said only that it
isn't a number; it says how to make it one now, as for "1,234" and
"$5".

## The package didn't work when actually installed

Every test in this project, and every manual check, ran from the source
tree: `tests/conftest.py` puts the repository root on `sys.path` so
pytest works without installing anything, and every ad-hoc script did
the same with `sys.path.insert(0, '.')`. So nothing ever exercised the
package the way a user gets it, through `pip install`.

Doing that, in a fresh virtual environment with only the declared
dependencies, showed two real problems:

1. **`scipy` wasn't declared as a dependency.** The paint texture (on by
   default in `bar_chart`, `pie_chart`, `stacked_area_chart`,
   `butterfly_chart` and `snake_chart`) and `plate51.py` use
   `scipy.ndimage.gaussian_filter`. The import sits inside the functions
   that need it, so `import dubois_charts` succeeded and the failure only came
   on the first chart call: `ModuleNotFoundError: No module named
   'scipy'`. It never showed up in development because scipy happened to
   be installed already. The README's own `pip install -e .` route had
   the same problem.
2. **The package's data files weren't included.** With no package-data
   configuration, setuptools shipped only `.py` files, so
   `county_map_chart()` failed with `FileNotFoundError` on its bundled
   Georgia boundaries, and `plate51.create_side_by_side()` couldn't find
   its reference scan. Editable installs hid this because they point
   back at the source tree, where the files exist.

Both are fixed in `pyproject.toml`: `scipy>=1.7.0` is declared, and a
`[tool.setuptools.package-data]` table lists the two data files the code
opens at runtime. Checked the same way the problem was found: a fresh
virtual environment, a plain `pip install` of a copy of the package, then
every chart function called from outside the source tree. All work, and
`scipy` is pulled in automatically. The README's `pip install -e .`
route was checked the same way.

`tests/test_packaging.py` guards against this coming back without having
to build anything. It scans every import in `dubois_charts/`, including the
lazy ones inside functions, and checks each third-party module against
the declared dependencies. It also takes the data-file paths from the
modules' own constants and checks each is matched by the package-data
globs. It was confirmed to catch the original bug: with the old
`pyproject.toml` temporarily restored, all four tests failed with
messages naming `scipy` and each missing file.

## Automated tests

Everything documented above was found by generating an image and looking
at it -- effective, but slow, manual, and easy to get wrong (see the
spiral.py radial-search bug above, caught by a test *after* a visual
re-check of the same chart had already missed it and this document
briefly claimed something that wasn't true). `tests/` has a pytest suite
-- about 940 tests -- covering `text_utils.py`, `_common.py`, the colours
and themes, and all eight chart functions:

- **Structural tests** for every chart function: does it return a
  `Figure`, does it accept the documented parameter variations (grouped
  series, custom colors, texture/jitter toggles, ...), does it write a
  real file when given `save_path`.
- **Input validation tests**: mismatched lengths, empty input, and
  negative values (for every chart except `bar_chart`, which draws them
  as diverging bars, and `county_map_chart`, where a negative statistic
  is legitimate) all raise `ValueError` with a message that names the
  actual problem, not a generic failure.
- **Regression tests for the specific bugs documented above** -- not
  reworded versions of the structural tests, but checks that would have
  caught the exact failure mode: `butterfly_chart`'s inverted-axis labels
  are asserted to use `ha='right'` specifically on the left axis;
  `bar_chart`'s category-label positions are asserted to be sane
  axes-fraction offsets, not whatever a silently-canceled expression
  happens to produce; `spiral_chart`'s labels are rendered, measured with
  matplotlib's own `get_window_extent()`, and checked pairwise for zero
  overlap, on both the moderate and adversarial test cases; `snake_chart`
  is checked for split-segment piece counts, scale-anchor continuity
  between rows, and (via the same pixel-extent technique used elsewhere)
  that its legend never renders past the canvas edge; `fit_label_in_box`
  is checked never to return ellipsis-containing text; `get_renderer` is
  checked to actually cache (identity, not just equality, across calls
  on the same figure), to give numerically correct measurements even
  after a lot of intervening drawing or a figure resize, and a direct
  timing assertion guards against the redraw cost quietly coming back;
  `pie_chart`'s internal labels are checked, via each rendered text's
  actual transformed corners, to never escape the pie's radius, and its
  external labels are checked pairwise for zero overlap even under heavy
  clustering; `county_map_chart` is checked against the actual bundled
  data (159 counties present, every polygon non-empty), against
  real-world name spelling variance, for the layout-gap fix (the map's
  rendered content must fill the large majority of its allocated axes
  space, and no large blank vertical band may separate it from the
  colorbar), and for the label shrink-and-retry fix (a dense-data map
  must place a reasonable fraction of its requested county labels, not
  silently drop most of them to an overly strict single-shot estimate).
- **Cross-cutting regression tests from the combined-conditions pass**:
  every one of the seven chart functions is checked, through its actual
  public API rather than only the shared helper in isolation, to reject
  NaN and infinite values, non-positive or non-finite `figsize`, and
  non-positive `dpi` with a clear `ValueError` -- not a crash inside
  matplotlib, and not a silently-broken render. `stacked_area_chart` and
  `butterfly_chart` are each checked to reject negative values the same
  way `spiral_chart`/`snake_chart`/`pie_chart` already did (`bar_chart`
  was too, until it gained diverging support; its tests now check that
  negative values render correctly instead). `spiral_chart` is checked
  to reject
  `revolutions <= 0`. `butterfly_chart`'s wrapped headers are checked
  against actual rendered pixel extent to never clip at the canvas top.
- **`county_map_chart`'s label-consistency fix**: every rendered county
  label on a given map is checked to share exactly one fontsize and one
  font weight with every other rendered label on that same map -- the
  property the original bug report actually cared about, which no
  earlier test checked even though earlier tests already covered "does a
  label render," "does it stay inside its polygon," and "do labels
  overlap."
- **`pie_chart`'s matching internal-label-consistency fix**: every
  internally-placed wedge label on a given pie is checked to share one
  fontsize with every other internal label on that same pie, plus
  regression guards for the two mistakes made while landing that fix --
  no rendered label may contain an ellipsis (the reintroduced
  truncation bug), and a large wedge with a long label is checked to
  still place internally rather than being pushed external for no
  shape-related reason (the retry-schedule bug).
- **`snake_chart`'s and `stacked_area_chart`'s matching
  label-consistency fixes**: every placed segment label on a given
  snake chart, and every placed band label on a given area chart, are
  each checked to share one fontsize with every other label of the same
  kind on that same chart -- the same property checked for
  `county_map_chart` and `pie_chart`, verified here once the pattern was
  known to recur rather than assumed fixed by association.
- **The `background`-contrast fix, across all seven chart types**: each
  chart is rendered with a dark background and every text artist that
  sits directly on that background (not on a data fill) is checked,
  via an actual luminance calculation against its real rendered color,
  to be light -- category and value labels, axis labels, headers,
  external labels, and colorbar tick labels, one dedicated test per
  chart type. A companion test renders the default light background and
  confirms ink stays dark there, so the fix can't have quietly inverted
  that case. Confirmed to actually catch the original bug, not just
  pass by construction, by temporarily reverting `bar.py` to hardcoded
  `COLOR_INK` and watching the test fail with the exact unreadable
  value before restoring the fix.
- **The texture-strength recalibration**: checked as a measurable
  property, not a fixed magic number -- an actual rendered texture's
  pixel variance must exceed a threshold well above the old,
  effectively-invisible level; a near-black fill's variance must come
  out lower than a mid-tone color's at the same nominal strength
  (confirming the dark-color dampening is actually wired in, not just
  present as unused code); that dampening must be monotonic across a
  range of increasingly light base colors, not a single hardcoded
  pass/fail case; and `plate51.py` is checked to have no dependency on
  the shared `_grain_rgba` at all, confirming its own, separately
  calibrated texture was never touched.
- **`bar_chart`'s diverging-data support**: mixed-sign, all-negative,
  and grouped mixed-sign data are each checked to render without error;
  the axis is checked to still start exactly at 0 for all-positive data
  (the fix must be purely additive) and to end exactly at 0 for
  all-negative data; the origin line is checked to appear only when the
  data genuinely spans both signs; each value's label is checked to sit
  on the correct, outward side of its own bar; `sort_descending` is
  checked to still order correctly by signed value; and the exact
  collision this feature's own first implementation attempt introduced
  -- a category name overlapping its own bar's negative-value label --
  is checked directly against real rendered bounding boxes, not assumed
  fixed by the surrounding margin logic existing.
- **`snake_chart`'s word-break fix**: the real eight-source electricity
  breakdown that produced "Oth" / "er" is rendered, and every word in
  every drawn label is checked to be a whole word from the input.
- **Packaging** (`tests/test_packaging.py`): every third-party import in
  the package must be a declared dependency, and every data file the
  code opens at runtime must be covered by package-data. These read
  `pyproject.toml` directly, because the rest of the suite runs from the
  source tree and can't see what an installed copy is missing.
- **The real-data follow-up fixes**: `stacked_area_chart` on the sparse
  2001/2022/2024 series must keep all 12 value labels (including the
  2024 ones), a two-point series all 4, and moved labels must stay inside
  their own band; on sparse and irregularly spaced series no two texts
  may overlap, the first and final year labels must survive thinning, and
  no value may print under a year whose label was dropped (judged by
  rendered position, since values at the last column are nudged inward).
  `bar_chart`'s default must print raw counts without a percent sign,
  whole numbers without decimals, and every label at the same precision,
  while an explicit `value_format` still wins. `pie_chart` must label a
  0.41% sliver "<1%" and keep coarser or finer formats' own precision.
  Titles, band names and butterfly headers must keep "iOS" while
  capitalising ordinary words, and long butterfly headers in a
  proportional font must fit the width they were wrapped to and stay
  inside their frame. Each group was run against the old behaviour and
  failed there.
- **The frame fix**: across seven bar and butterfly configurations
  (raw counts, diverging, all-negative, grouped, currency, two butterfly
  datasets), no frame edge may pass through any rendered text, and every
  frame must stay inside the figure. With value labels off, `bar_chart`'s
  frame must stay exactly where it was. All seven crossing checks fail
  with the old frames.
- **The palette past eight**: `get_categorical` must be unchanged up to
  eight. Every count from 9 to 20 must have no repeats. Every pair of the
  twenty, and each against the paper, must be at least 15 CIEDE2000
  apart, with crimson and rose still the closest pair. The hardcoded list
  must match the procedure that chose it. Adding a category must never
  recolour the others, and the warning must come exactly when colours
  start to look alike. The CIEDE2000 code is checked against Sharma, Wu &
  Dalal's 31 published test pairs. The ten-country chart, a 12-series
  area chart and a 12-slice pie must each draw every category in its own
  colour, and too few or no colours must raise a clear error. Against the
  old cycling palette and colour handling, 27 of these fail.
- **County labels**, on the real unemployment data:
  - The default must label the three highest and three lowest counties.
  - `'highest'` and `'lowest'` must take exactly the top or bottom values.
  - `'area'` must take the largest counties.
  - Every requested label must be drawn.
  - Labels must not depend on the data's order.
  - The geometry check above must pass for five `label_by` settings, a
    small figure and an explicit metro list.
  - A constructed case must show a leader line routing around a label
    rather than through it.
  - The colorbar must print distinct boundaries.

  22 of these fail on the old map code. Each placement rule was also
  removed on its own (no fit check, callouts ignoring the map, leader
  lines allowed through labels), and each removal fails at least one
  test.
- **The map's colour classes for any data**: a few distinct values
  must get a class each, labelled with the values. An all-equal map and
  a single county must get one class. Heavily tied data must leave no
  class empty and repeat no label. Boundaries must be real county values
  and never print "-0". `n_classes=1` must work, invalid `n_classes`
  must raise, and colorbar labels must never overlap at 7, 12 or 20
  classes. `get_sequential(n=1)` must return one colour. 17 of these 18
  fail on the previous code.
- **Any data** (`tests/test_any_data.py`, 138 tests):
  - text: no chart text may be parsed as math or LaTeX, even with
    `text.usetex` on; currency labels must come out as written; CJK
    labels must render without missing glyphs where a CJK font is
    installed;
  - inputs: integer names, pandas Series and DataFrames, and every
    number type must work; a missing value or a word where a number
    belongs must be named in the error, and a bad `value_format` must
    be refused;
  - numbers: raw counts must never get a percent sign, shares of 100
    must keep theirs, and fractions and tiny values must not print as
    zero;
  - labels: years that pandas made float, Timestamps and numpy
    datetime64 values must print as "2018" or "Jan 2024" in every chart,
    float noise must not print, tidying must never merge two
    categories, and a title or side label may be a number;
  - area chart: no text may leave the figure, with or without a title;
    dates must be spaced by time and labelled compactly; unsorted x must
    draw the same chart as sorted; repeated x must raise, and so must a
    missing x (None, NaN, NaT) or an infinite one, naming it; numbers
    and band names must stay inside the drawn area, clear of its border;
    100 points must stay at 11 inches with the last year labelled and
    every number under a named year, or just inside the area's edge;
  - long labels must not resize pies or spirals or shrink the other
    labels of bar and butterfly charts;
  - pie outside labels must never cover the pie or each other in four
    crowded layouts, and no word may be broken inside a wedge; a pie
    with outside labels must use the room beside them in square, wide
    and tall figures, and wrapped labels must come out balanced;
  - a 40-point spiral must get its labels, half a revolution must keep
    them on the figure, and 12 revolutions must draw a smooth curve;
  - every chart must have no text problems under five common user
    settings.

  98 of the 138 fail against the code from before, spread across every
  class.
- **Fast texture** (`TestFastTextureMatchesTheOriginal` in
  `tests/test_common.py`, 4 tests): the matrix blur must match scipy's
  filter to 1e-12 at three shapes, including one shorter than the
  filter, and the channel-by-channel blend must equal the original
  whole-array formula exactly.
- **County keys and boundary files** (`TestRegressionCountyKeys` and
  `TestRegressionBoundaryFiles` in `tests/test_choropleth.py`, 12
  tests): GEOIDs as integers, text and pandas floats, county codes alone,
  GEO_IDs and Census-style names must each find the right counties with
  no warning; `label_counties` must take codes; another state's code
  must be named as unmatched; the bundled codes must be complete and
  right; a two-piece county must draw both pieces and a hole must show
  the county inside it; names under other properties must work, a file
  without one must say so, and repeated names must be refused. 11 of
  the 12 fail on the code from before.
- **Every state** (`TestRegressionEveryState` in `tests/test_choropleth.py`,
  20 tests): states by name, postal code and FIPS code; every state and
  territory loads with uniquely named counties, the right count for 14 of
  them, and nothing spanning 180 degrees; Alaska, Hawaii, Texas,
  Virginia, Tennessee, Michigan, Delaware, the Northern Mariana Islands
  and Puerto Rico draw at 12 labels with no text problems, 5 to 9 inches
  wide and at most 12 tall; Census-style names match in six states;
  codes alone pick the state; `state` with `geojson_path` is refused;
  and `state='GA'` draws exactly what the default does.
- **Callouts have room** (`TestRegressionCalloutsHaveRoom` in
  `tests/test_choropleth.py`, 13 tests): Colorado, Kansas and North
  Dakota must draw all 8 labels asked for, every callout clear of the
  map and led to by one line; on six states a callout must be no further
  from its county than the state's nearest edge plus 0.3 inches; adding
  callouts must leave the map and colorbar the same size in pixels while
  the figure grows; labels with no room must be named in a warning; and
  a `figsize` width must be kept. 12 of the 13 fail on the code from
  before (the last guards the new growth).
- **The whole country** (`tests/test_country_maps.py`, 29 tests): every
  form of state key must match with no warning, the District of Columbia
  by any name; keys that match no state must be named, with a pointer to
  `county_map_chart` when they look like counties, and the island
  territories must be named as off the map; Puerto Rico must appear only
  when the data have it; maps at 6, 15 and 51 labels must draw with no
  text problems and every callout clear of the map; the Northeast's
  small states must get callouts; DC must get a dot; Alaska and Hawaii
  must sit below and left of the lower 48; the projection must keep
  areas; county data from several states, by code or by name with state,
  must draw the country, and from one state that state; Illinois's Cook
  County must not be drawn as Georgia's; bare names on the country's map
  and state names given for counties must be told why they didn't match;
  every county must draw cleanly with 9pt callouts; and on six crowded
  state maps no two leader lines may cross. All 29 fail on the code from
  before.
- **Large data** (`TestRegressionLargeData` in `tests/test_any_data.py`,
  9 tests): 200 bars must each get a label with no text overlapping or
  off the figure, and the title must sit above the chart; 1,000 bars
  must label one row in k, including the first and last, with a
  warning; grouped bars too close for value labels must drop them with
  a warning; 200 butterfly rows must each get a label; a 200-slice pie's
  labels must stay on the figure and off the pie; snakes of 100 and 200
  segments must keep their legend on the figure and the snake at least
  55% of its height; and `fit_label_column` must never pick a size whose
  line is taller than the row. All 9 fail with this round's fixes taken
  out -- the 200-segment snake by crashing.
- **Versions, systems and fonts**: `tests/test_fonts.py` (11 tests)
  hides every font but matplotlib's own and draws every chart, checks
  Courier New is chosen over DejaVu Sans Mono, that the fallback fonts'
  missing-bold warning is dropped (and only theirs), and that a pixel's
  difference in a font no longer shrinks every map label;
  `tests/test_portability.py` reads the bundled boundaries with Windows's
  default encoding.
- **Colour-blind readers** (`TestColourBlindReaders` and
  `TestRegressionMapClassesForEveryReader` in `tests/test_colors.py`):
  the simulation must match known values and leave greys alone; the
  classic palette must fail (under 7) and the colour-blind one stay
  15 apart for every reader at 2 to 8 colours; the diverging palette's
  mirrored pairs must stay apart; map classes must be at least 7 apart
  for every reader at 3 to 7 classes and run light to dark; and the
  no-data colour must be at least 12 from every class of every palette.
- **Image comparison** (`tests/test_images.py`, 20 tests): nineteen
  charts against their references, and every reference still drawn.
- **Bands, spirals and speed**: `TestRegressionTextStaysInsideItsBand`
  in `tests/test_area.py` (15 tests: the long-names case, 12 random
  datasets, a name on two lines); `TestRegressionLeaderLinesOnTightSpirals`
  in `tests/test_spiral.py` (7 tests: leaders crossing loops, each other
  or labels on three tight spirals, labels on one ray);
  `TestRegressionGrainInOneImage` in `tests/test_common.py` (8 tests: one
  picture for 300 bars, noise made 24 times, each kind of shape the same
  as its own clipped picture, drawn at the resolution it's saved at, and
  a figure that still pickles). 14, 4 and 7 of them fail on the code from
  before; the rest guard against fixing it the wrong way.
- **Jupyter** (`TestRegressionChartsKeepShowingInJupyter` in
  `tests/test_common.py`): a setting changed while a chart is drawn --
  as matplotlib switches on interactive mode -- must be kept, and the two
  text settings put back even when the chart fails.

Run them from the package root with `pytest tests/`.

## Using it

```python
from dubois_charts.charts.area import stacked_area_chart

fig = stacked_area_chart(
    x=[2018, 2019, 2020, 2021, 2022],
    series={
        # bottom-to-top stacking order; values don't need to sum to 100
        'On-site': [62, 58, 22, 30, 45],
        'Hybrid': [10, 14, 18, 35, 40],
        'Remote': [28, 28, 60, 35, 15],
    },
    title='Where knowledge workers did their jobs',
    subtitle='Self-reported primary work location, surveyed companies',
    save_path='remote_work.png',
)
```

```python
from dubois_charts.charts.bar import bar_chart

fig = bar_chart(
    categories=['Agriculture', 'Domestic Service', 'Manufacturing', 'Trade'],
    values=[45, 25, 12, 10],            # or a dict of series for grouped bars
    title='Occupations of Negroes in Georgia',
    sort_descending=True,
)
```

```python
from dubois_charts.charts.butterfly import butterfly_chart

fig = butterfly_chart(
    categories=['Agriculture', 'Domestic Service', 'Trade', 'Professions'],
    left_values=[52, 38, 6, 4],
    right_values=[31, 55, 8, 6],
    left_label='Male', right_label='Female',
    title='Occupations by Sex',
)
```

```python
from dubois_charts.charts.spiral import spiral_chart

fig = spiral_chart(
    categories=[1870, 1880, 1890, 1900, 1910, 1920],
    values=[45, 62, 89, 140, 210, 305],
    title='Population Growth Over Time',
    subtitle='Estimated population, in thousands',
)
```

```python
from dubois_charts.charts.snake import snake_chart

fig = snake_chart(
    segments={
        'Agriculture': 45, 'Domestic Service': 25, 'Manufacturing': 12,
        'Trade': 10, 'Professions': 8,
    },
    n_rows=4,
    title='Occupations, Folded to Fit',
)
```

```python
from dubois_charts.charts.pie import pie_chart

fig = pie_chart(
    segments={'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5},
    title='Conjugal Condition',
)
```

```python
from dubois_charts.charts.choropleth import county_map_chart

fig = county_map_chart(
    data={'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61},
    title='Percentage Reporting Literacy, By County',
    colorbar_label='Percentage literate',
)
```

```python
from dubois_charts.charts.choropleth import state_map_chart

fig = state_map_chart(
    data={'California': 39.5, 'Texas': 29.1, 'Florida': 21.5, 'New York': 20.2},
    title='Population by State, 2020',
    colorbar_label='Millions of residents',
)
```

Long titles, many categories, long category or series names, and long
side-headers are all handled automatically — wrapped, shrunk, rotated, or
moved to a legend as needed, following the same escalation order real
chart libraries use, so you don't have to hand-tune font sizes for your
own dataset the way `plate51.py` does for its one.

See each function's docstring for its full parameter list (colors,
value-label formatting, texture toggle, hand-drawn jitter toggle where
applicable, and so on).

## What's still specific to `plate51.py`

The general engine deliberately does *not* try to reproduce every detail
of the Plate 51 recreation — that would mean re-imposing hardcoded
assumptions (a fixed 0-100 scale read as "the top IS 100%", the specific
"FREE - LIBRE" dash-separated wording, the exact hand-verified pixel
colors) that only make sense for that one historical plate. If you want
the historically faithful version, use `plate51.py`. If you want to chart
your own data in the same visual language, use `stacked_area_chart()`,
`bar_chart()`, `butterfly_chart()`, `spiral_chart()`, `snake_chart()`,
`pie_chart()`, `county_map_chart()` or `state_map_chart()`, depending on
which shape fits it.
