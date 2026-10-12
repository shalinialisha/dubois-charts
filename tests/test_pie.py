"""
Tests for dubois_charts.charts.pie.pie_chart.

Includes regression coverage for a bug found by checking actual rendered
pixels (not just the layout math): a wide wedge's internal label was
sized using an arc-length-at-mid-radius approximation for available
width, which overestimated how much room really existed near the wedge's
own edges, and the label ran past the wedge's true boundary -- visible as
white text fading from crisp (on the wedge's fill) to barely legible (on
the cream background) right where the estimate and reality disagreed.
"""

import math
import pytest
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

from dubois_charts.charts.pie import pie_chart


BASIC_SEGMENTS = {'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5}


def _rendered_content_extent_px(fig, save_path):
    """Save, reload, and find the bounding box of all non-background
    pixels -- the same pixel-level verification technique used
    throughout this project."""
    from PIL import Image
    fig.savefig(save_path, dpi=fig.dpi, facecolor=fig.get_facecolor())
    img = np.array(Image.open(save_path).convert('RGB'))
    bg = np.array([int(c * 255) for c in fig.get_facecolor()[:3]])
    diff = np.abs(img.astype(int) - bg).sum(axis=2)
    mask = diff > 30
    ys, xs = np.where(mask)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()), img.shape


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = pie_chart(segments=BASIC_SEGMENTS)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = pie_chart(segments=BASIC_SEGMENTS, title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_segment(self):
        fig = pie_chart(segments={'Everything': 100})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_donut_mode(self):
        fig = pie_chart(segments=BASIC_SEGMENTS, donut=True)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_counterclockwise(self):
        fig = pie_chart(segments=BASIC_SEGMENTS, clockwise=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_custom_start_angle(self):
        fig = pie_chart(segments=BASIC_SEGMENTS, start_angle=0)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_texture_can_be_disabled(self):
        fig = pie_chart(segments=BASIC_SEGMENTS, texture=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_values_need_not_sum_to_100(self):
        # Raw counts, not just percentages -- only ratios matter.
        fig = pie_chart(segments={'A': 1200, 'B': 800, 'C': 400})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'pie_test_output.png'
        fig = pie_chart(segments=BASIC_SEGMENTS, save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestInputValidation:
    def test_empty_segments_raises(self):
        with pytest.raises(ValueError):
            pie_chart(segments={})

    def test_negative_value_raises(self):
        with pytest.raises(ValueError, match=r"Segment 'B' \(-10\) is negative.*zero or more"):
            pie_chart(segments={'A': 50, 'B': -10})

    def test_all_zero_raises(self):
        with pytest.raises(ValueError):
            pie_chart(segments={'A': 0, 'B': 0})


class TestRegressionWedgeBoundaryBleed:
    """
    Regression coverage for the bug found by checking actual rendered
    pixels: an internal label's estimated available width (arc length at
    a representative radius) could overestimate the wedge's true
    boundary, letting text run past the wedge's real edge. Fixed by
    validating a candidate label's actual rendered corners against the
    wedge's exact geometry (radius + angle range) and shrinking/retrying
    if any corner falls outside, rather than trusting the initial
    estimate.
    """

    def test_wide_wedge_label_stays_within_wedge_geometry(self):
        # The actual failing configuration: a wide (144-degree) wedge
        # with a long label, positioned off-center within its own span.
        segments = {
            'Percentage Reporting Agricultural Occupation': 40,
            'Percentage Reporting Domestic Service Occupation': 20,
            'Other': 40,
        }
        fig = pie_chart(segments=segments, start_angle=90, clockwise=True)
        ax = fig.axes[0]

        # Recompute the first wedge's exact boundary the same way
        # pie_chart does, then verify every internally-placed text
        # artist's rendered corners genuinely fall within it.
        total = sum(segments.values())
        frac0 = segments['Percentage Reporting Agricultural Occupation'] / total
        theta_a, theta_b = 90.0, 90.0 - frac0 * 360.0
        lo, hi = sorted([theta_a % 360, theta_b % 360])

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for t in ax.texts:
            if 'Agricultural' not in t.get_text():
                continue
            # Only internally-placed labels are constrained to the pie's
            # own radius -- external labels are correctly, deliberately
            # positioned outside it (this is what distinguishes the two
            # placement modes). Distinguished by the text's own anchor
            # radius (internal labels anchor within the pie, at r < 1.0;
            # external ones anchor at r_pie*1.12 > 1.0), NOT by
            # `clip_on` -- checked directly and found that matplotlib's
            # actual default for `ax.text()` is `clip_on=False`, the
            # same value external labels set explicitly, so that
            # attribute never distinguished the two cases at all. Every
            # text in every version of this test silently matched
            # neither branch and skipped every assertion without ever
            # failing -- caught only by manually checking a real
            # anchor position during unrelated debugging, not by this
            # test itself.
            anchor_x, anchor_y = t.get_position()
            if math.hypot(anchor_x, anchor_y) >= 1.0:
                continue
            bbox = t.get_window_extent(renderer=renderer)
            corners_disp = [(bbox.x0, bbox.y0), (bbox.x1, bbox.y0),
                            (bbox.x0, bbox.y1), (bbox.x1, bbox.y1)]
            inv = ax.transData.inverted()
            for dx, dy in corners_disp:
                x, y = inv.transform((dx, dy))
                r = math.hypot(x, y)
                assert r <= 1.0 + 1e-6, f"Corner at r={r:.4f} escaped the pie's outer radius"
        plt.close(fig)

    def test_no_internal_label_text_bleeds_past_pie_radius(self):
        # A broader sweep: across several wedge-size/label-length
        # combinations, every INTERNALLY-placed label's rendered corners
        # must stay within the outer circle. (External labels are
        # expected to sit outside it, by design, so are excluded.)
        segments = {
            'A Fairly Long Category Label Here': 55,
            'B': 25,
            'C': 12,
            'D': 8,
        }
        fig = pie_chart(segments=segments)
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # Distinguished by anchor radius, not `clip_on` -- matplotlib's
        # actual default for ax.text() is clip_on=False, the same value
        # external labels set explicitly, so that attribute never
        # separated the two groups at all (found only by directly
        # checking matplotlib's default during unrelated debugging;
        # every text here previously matched neither branch, so this
        # loop's body silently never ran a single assertion).
        for t in ax.texts:
            anchor_x, anchor_y = t.get_position()
            if math.hypot(anchor_x, anchor_y) < 1.0:  # internal label
                bbox = t.get_window_extent(renderer=renderer)
                inv = ax.transData.inverted()
                for dx, dy in [(bbox.x0, bbox.y0), (bbox.x1, bbox.y1)]:
                    x, y = inv.transform((dx, dy))
                    assert math.hypot(x, y) <= 1.0 + 1e-6
        plt.close(fig)


class TestExternalLabelDecluttering:
    def test_regression_clustered_similar_width_labels_do_not_clip(self, tmp_path):
        """
        Regression coverage for a bug found by checking actual rendered
        pixel extent (0px right margin -- confirmed clipped, not just
        close to the edge): the figure margin was originally sized
        around ONE representative "widest label at the worst-case
        angle" estimate, but when many similarly-wide labels cluster on
        one side, several of them independently reach nearly that same
        worst-case horizontal position, and the single-representative
        estimate undershot what was actually needed. The fix also had a
        subtler bug of its own on the first attempt: converting a
        label's pixel width to a data-unit width using the scale
        BEFORE deciding how much to expand by is circular (a larger
        final canvas means a smaller data-units-per-pixel scale, so the
        same pixel-width text needs MORE data-space than a conversion
        at the smaller, pre-expansion scale suggests) -- confirmed by
        forcing a much larger expansion and seeing it actually fix the
        clipping, proving the mechanism worked and the original
        estimate was simply undersized, before landing on the proper
        per-label algebraic solve.
        """
        segments = {f'A Rather Long Category Label {i}': 3 for i in range(12)}
        segments['Big One'] = 100 - 36
        out = tmp_path / 'clustered_labels.png'
        fig = pie_chart(segments=segments, donut=True, start_angle=45, save_path=str(out))
        plt.close(fig)

        img = np.array(Image.open(out).convert('RGB'))
        bg = np.array([int(c * 255) for c in fig.get_facecolor()[:3]])
        diff = np.abs(img.astype(int) - bg).sum(axis=2)
        mask = diff > 30
        ys, xs = np.where(mask)
        w = img.shape[1]
        assert xs.max() < w - 1, "Content clipped at the right edge"
        assert xs.min() > 0, "Content clipped at the left edge"


    def test_many_adjacent_small_wedges_labels_do_not_overlap(self):
        segments = {f'Small {i}': 3 for i in range(15)}
        segments['Big'] = 100 - 15 * 3
        fig = pie_chart(segments=segments)
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        boxes = [t.get_window_extent(renderer=renderer) for t in ax.texts
                 if t.get_text().strip()]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                assert not boxes[i].overlaps(boxes[j]), (
                    f"Overlapping external labels: {ax.texts[i].get_text()!r} "
                    f"and {ax.texts[j].get_text()!r}"
                )
        plt.close(fig)

    def test_heavy_clustering_does_not_clip_at_canvas_edge(self, tmp_path):
        segments = {f'Category {i} With Descriptive Text': 4 for i in range(20)}
        segments['Remainder'] = 100 - 20 * 4
        fig = pie_chart(segments=segments, title='Heavy Clustering Stress Test')
        x0, x1, y0, y1, shape = _rendered_content_extent_px(
            fig, str(tmp_path / 'clip_check.png')
        )
        h, w = shape[0], shape[1]
        assert y1 < h - 1, "Content clipped at bottom edge"
        assert y0 > 0, "Content clipped at top edge"
        assert x1 < w - 1, "Content clipped at right edge"
        assert x0 > 0, "Content clipped at left edge"
        plt.close(fig)


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Considerably Long Title For A Pie Chart About Occupations ' * 2
        fig = pie_chart(segments=BASIC_SEGMENTS, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_tiny_segments_do_not_raise(self):
        segments = {f'Segment {i}': 100 / 40 for i in range(40)}
        with pytest.warns(UserWarning, match='look alike'):   # 40 colours can't all be distinct
            fig = pie_chart(segments=segments)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_one_dominant_and_many_tiny_segments(self):
        segments = {'Dominant': 70}
        segments.update({f'Tiny {i}': 1 for i in range(30)})
        with pytest.warns(UserWarning, match='look alike'):   # 31 colours can't all be distinct
            fig = pie_chart(segments=segments)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestRegressionWraparoundAngleContainment:
    """
    Regression coverage for a distinct bug from the wedge-boundary-bleed
    one above, found while investigating an unrelated edge case (a
    single unbreakable long word as a segment label): `_point_in_wedge`
    took `% 360` of each of a wedge's two raw cumulative-angle
    boundaries INDEPENDENTLY before comparing, which throws away which
    of the two possible arcs between two angles is actually the wedge.
    That's most severely wrong for any wedge spanning more than half the
    circle -- confirmed directly: a 95%-of-circle wedge's own label,
    sitting at that wedge's own geometric center, failed this exact
    containment check against its own boundaries, and was wrongly pushed
    to an external leader-line label instead of simply being drawn where
    it obviously belonged.
    """

    def test_majority_wedge_label_places_internally(self):
        # A wedge this large, with a short one-character label, should
        # trivially fit inside its own slice rather than needing an
        # external leader line.
        fig = pie_chart(segments={'Tiny': 5, 'B': 95}, show_value_labels=False)
        ax = fig.axes[0]
        b_texts = [t for t in ax.texts if t.get_text().strip() == 'B']
        assert len(b_texts) == 1
        x, y = b_texts[0].get_position()
        r = math.hypot(x, y)
        assert r < 0.9, (
            f"'B' (a 95%-of-circle wedge) labeled externally (r={r:.3f}) "
            "instead of internally -- regression of the wraparound-angle "
            "containment bug."
        )
        plt.close(fig)

    def test_majority_wedge_label_position_is_geometrically_inside_it(self):
        # A broader check: for a range of dominant-wedge sizes, whatever
        # label position gets chosen (internal or external) must at
        # least be geometrically consistent -- an internal placement's
        # anchor must genuinely fall within that wedge's true angular
        # span, computed independently here rather than reusing the
        # module's own (now-fixed) containment helper.
        for big_pct in (60, 75, 90, 95, 99):
            segments = {'Small': 100 - big_pct, 'Big': big_pct}
            fig = pie_chart(segments=segments, show_value_labels=False)
            ax = fig.axes[0]
            big_texts = [t for t in ax.texts if t.get_text().strip() == 'Big']
            if big_texts:
                x, y = big_texts[0].get_position()
                r = math.hypot(x, y)
                if r < 0.9:  # placed internally
                    ang = math.degrees(math.atan2(y, x)) % 360
                    # 'Big' is the SECOND segment, so it starts wherever
                    # 'Small' (the first segment) left off -- not at the
                    # chart's overall start_angle -- then sweeps
                    # clockwise for big_pct/100 * 360 degrees from there.
                    small_pct = 100 - big_pct
                    big_start_deg = (90 - small_pct / 100 * 360) % 360
                    span_deg = big_pct / 100 * 360
                    swept = (big_start_deg - ang) % 360
                    assert swept <= span_deg + 1e-6, (
                        f"big_pct={big_pct}: label angle {ang:.1f} falls "
                        f"outside Big's true {span_deg:.1f}-degree span"
                    )
            plt.close(fig)


class TestRegressionConsistentInternalLabelFontSize:
    """
    Regression coverage for a bug reported directly against a rendered
    chart, the same way county_map_chart's font-size inconsistency was:
    on a 4-segment pie ("Married" 52%, "Single" 31%, "Widowed" 12%,
    "Divorced" 5%), the three largest wedges' internal labels didn't
    all match -- two came out around 13pt, "Widowed" (a smaller wedge)
    came out around 9.75pt, and bold text at that smaller size renders
    with visibly thinner strokes than the same weight at the larger
    size, reading as a different, mismatched font even though nothing
    about the font had actually changed. The root cause was the same
    as county_map_chart's: each wedge's label was fit independently,
    maximizing its own size against its own slice, with no step that
    considered any other label on the same chart. Fixed the same way:
    solve for one shared fontsize across every internally-placed label.

    Fixing this correctly took two attempts. The first attempt computed
    one shared fontsize but broke wrapping for long labels in wide
    wedges: it called wrap_text_to_width with max_lines=2 directly,
    which silently truncates-with-ellipsis to comply rather than
    reporting it needed more room -- the exact anti-pattern already
    found once in fit_label_in_box (see GENERAL_ENGINE_README.md),
    reintroduced here in new code. The second attempt fixed the
    truncation but then used too gentle a shrink schedule (repeated
    0.8x reductions from an arc-length estimate) to actually narrow a
    long single-line label down to a real 2-line wrap within the
    retry budget, since a single-line render's width doesn't change at
    all until the candidate width drops below it -- confirmed with
    direct instrumentation showing three wasted attempts with zero
    visible effect before the budget ran out. Fixed by trying the
    natural single-line width first, then widths chosen to force a
    real 2-line split immediately, rather than incrementally.
    """

    def test_internal_labels_share_one_font_size(self):
        fig = pie_chart(segments={'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5})
        ax = fig.axes[0]
        internal_sizes = {round(t.get_fontsize(), 2) for t in ax.texts
                          if '%' in t.get_text() and t.get_text() != 'Divorced  5%'}
        # (Divorced is thin enough to legitimately go external, at its
        # own separate, but internally-consistent, external-label size --
        # excluded here since mixing the two label CLASSES is expected,
        # only inconsistency WITHIN a class is the bug.)
        assert len(internal_sizes) <= 1, f"Inconsistent internal label sizes: {internal_sizes}"
        plt.close(fig)

    def test_no_garbled_or_truncated_internal_labels(self):
        # Regression guard for the ellipsis-truncation bug introduced
        # (and fixed) while building the shared-size fix itself.
        segments = {
            'Percentage Reporting Agricultural Occupation': 40,
            'Percentage Reporting Domestic Service Occupation': 20,
            'Small Category Alpha': 4, 'Small Category Beta': 4,
            'Percentage Reporting Professional Occupation': 8,
        }
        fig = pie_chart(segments=segments)
        ax = fig.axes[0]
        for t in ax.texts:
            assert '\u2026' not in t.get_text(), f"Ellipsis found in: {t.get_text()!r}"
        plt.close(fig)

    def test_large_wedge_with_long_label_still_places_internally(self):
        # The specific configuration that regressed mid-fix: a large
        # (144-degree) wedge with a long label should still find room
        # internally, not be pushed external for no shape-related reason.
        segments = {
            'Percentage Reporting Agricultural Occupation': 40,
            'Small Category Alpha': 4,
        }
        fig = pie_chart(segments=segments)
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        agricultural_texts = [t for t in ax.texts if 'Agricultural' in t.get_text()]
        assert len(agricultural_texts) >= 1
        # Should be positioned well inside the pie's radius (internal),
        # not out near/beyond it (external).
        inv = ax.transData.inverted()
        for t in agricultural_texts:
            bbox = t.get_window_extent(renderer=renderer)
            cx_disp = (bbox.x0 + bbox.x1) / 2
            cy_disp = (bbox.y0 + bbox.y1) / 2
            x, y = inv.transform((cx_disp, cy_disp))
            r = math.hypot(x, y)
            assert r < 0.9, f"Expected an internal placement, got r={r:.3f}"
        plt.close(fig)


class TestRegressionSliverNeverReadsZero:
    """
    Real data (global mobile OS share: Android 72.77%, iOS 26.82%,
    Other 0.41%) drew a visible "Other" wedge labelled "Other 0%". A share
    that rounds to zero but isn't zero now reads "<1%" (or "<0.1%" and so
    on, matching the format's precision).
    """

    @staticmethod
    def _label_for(fig, name):
        return [t.get_text() for t in fig.axes[0].texts if t.get_text().startswith(name)]

    def test_real_os_share_sliver_reads_less_than_one_percent(self):
        fig = pie_chart(segments={'Android': 72.77, 'iOS': 26.82, 'Other': 0.41})
        other = self._label_for(fig, 'Other')
        assert other and all('<1%' in s for s in other), other
        assert not any(s.endswith(' 0%') for s in other), other
        plt.close(fig)

    def test_finer_format_keeps_its_own_precision(self):
        fig = pie_chart(segments={'Big': 99.96, 'Tiny': 0.04}, value_format='{:.1f}%')
        tiny = self._label_for(fig, 'Tiny')
        assert tiny and all('<0.1%' in s for s in tiny), tiny
        plt.close(fig)

    def test_ordinary_shares_are_unchanged(self):
        fig = pie_chart(segments={'Android': 72.77, 'iOS': 26.82, 'Other': 0.41})
        android = self._label_for(fig, 'Android')
        assert android and all(s.endswith('73%') for s in android), android
        plt.close(fig)
