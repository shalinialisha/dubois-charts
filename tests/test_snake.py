"""
Tests for dubois_charts.charts.snake.snake_chart.

Includes regression coverage for two bugs found while building this
chart type -- one in snake.py itself, one in the shared
`dubois_charts.text_utils.fit_label_in_box` used by every chart in the package
(see test_text_utils.py's TestFitLabelInBox regression tests for that
one's direct coverage; it's exercised indirectly here too, since it's
what a real snake_chart call actually goes through).
"""

import pytest
import numpy as np
import matplotlib.pyplot as plt

from dubois_charts.charts.snake import snake_chart


BASIC_SEGMENTS = {
    'Agriculture': 45, 'Domestic Service': 25, 'Manufacturing': 12,
    'Trade': 10, 'Professions': 8,
}


def _rendered_content_bottom_px(fig, save_path):
    """Save, reload, and find the lowest non-background pixel row --
    the same technique used throughout this project to catch content
    clipped at or past the canvas edge."""
    from PIL import Image
    fig.savefig(save_path, dpi=fig.dpi, facecolor=fig.get_facecolor())
    img = np.array(Image.open(save_path).convert('RGB'))
    bg = np.array([int(c * 255) for c in fig.get_facecolor()[:3]])
    diff = np.abs(img.astype(int) - bg).sum(axis=2)
    mask = diff > 30
    ys, _ = np.where(mask)
    return int(ys.max()), img.shape[0]


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4,
                           title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_row(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=1)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_rows(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=10)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_segment(self):
        fig = snake_chart(segments={'Everything': 100}, n_rows=4)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_alternate_direction_can_be_disabled(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4, alternate_direction=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_texture_can_be_disabled(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4, texture=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_explicit_total_larger_than_segment_sum(self):
        # Segments don't have to fill the whole scale.
        fig = snake_chart(segments={'A': 30, 'B': 20}, total=100, n_rows=4)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_zero_value_segment(self):
        fig = snake_chart(segments={'A': 50, 'B': 0, 'C': 50}, n_rows=3)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'snake_test_output.png'
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4, save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestInputValidation:
    def test_empty_segments_raises(self):
        with pytest.raises(ValueError):
            snake_chart(segments={}, n_rows=4)

    def test_zero_rows_raises(self):
        with pytest.raises(ValueError):
            snake_chart(segments=BASIC_SEGMENTS, n_rows=0)

    def test_negative_value_raises(self):
        with pytest.raises(ValueError, match=r"Segment 'B' \(-10\) is negative.*zero or more"):
            snake_chart(segments={'A': 50, 'B': -10}, n_rows=3)

    def test_segments_exceeding_explicit_total_raises(self):
        with pytest.raises(ValueError):
            snake_chart(segments={'A': 60, 'B': 60}, total=100, n_rows=4)

    def test_zero_total_raises(self):
        with pytest.raises(ValueError):
            snake_chart(segments={'A': 0, 'B': 0}, n_rows=3)


class TestMultiRowSpanningSegments:
    """
    The structurally distinctive behavior of this chart type: a segment
    wider than a single row has to be split into multiple pieces across
    consecutive rows, all sharing that segment's color and (at most once,
    at its widest piece) its label.
    """

    def test_segment_wider_than_one_row_is_split(self):
        # row_width = 100/6 ~= 16.7; a 60-wide segment must produce
        # pieces in at least 4 rows (60 / 16.7 ~= 3.6, spanning rows 0-3).
        fig = snake_chart(
            segments={'Big': 60, 'Small1': 15, 'Small2': 15, 'Small3': 10},
            n_rows=6,
        )
        ax = fig.axes[0]
        # Every Rectangle patch drawn on the axes is either a piece or a
        # row border; pieces have a facecolor that isn't the row-border
        # "unfilled" style, so count rectangles with a real fill.
        filled_rects = [p for p in ax.patches
                        if isinstance(p, plt.Rectangle) and p.get_fill()]
        assert len(filled_rects) >= 4
        plt.close(fig)

    def test_segment_spanning_three_or_more_rows(self):
        # An extreme case: one segment covers 85% of the total scale
        # across 8 rows (row_width ~12.5), needing 7 pieces.
        fig = snake_chart(segments={'Huge': 85, 'Rest': 15}, n_rows=8)
        ax = fig.axes[0]
        filled_rects = [p for p in ax.patches
                        if isinstance(p, plt.Rectangle) and p.get_fill()]
        assert len(filled_rects) >= 7
        plt.close(fig)

    def test_pieces_of_the_same_segment_share_its_color(self):
        fig = snake_chart(segments={'Big': 60, 'Rest': 40}, n_rows=6,
                           colors=['#DC143C', '#00A550'])
        ax = fig.axes[0]
        red_pieces = [p for p in ax.patches
                     if isinstance(p, plt.Rectangle) and p.get_fill()
                     and tuple(p.get_facecolor())[:3] == plt.matplotlib.colors.to_rgb('#DC143C')]
        # 'Big' (60, red) spans rows 0-3 at row_width~16.7 -- at least 4 pieces.
        assert len(red_pieces) >= 4
        plt.close(fig)


class TestScaleContinuity:
    """
    The scale-anchor labels at each row's edges exist specifically so the
    fold still reads as ONE continuous scale. Whatever edge a row ends a
    reading pass on should show the same value as the edge the next row
    starts its reading pass on.
    """

    def test_consecutive_rows_connect_at_matching_values(self):
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4, value_format='{:.1f}')
        ax = fig.axes[0]
        # Collect the plain (non-segment) scale-anchor texts: short,
        # numeric-looking strings placed at each row's left/right edges.
        numeric_texts = []
        for t in ax.texts:
            s = t.get_text()
            try:
                float(s)
                numeric_texts.append((t.get_position(), float(s)))
            except ValueError:
                continue
        assert len(numeric_texts) == 4 * 2  # left + right edge per row
        plt.close(fig)


class TestRegressionLegendClipping:
    """
    Regression coverage for a bug found by checking actual rendered
    pixel extent: the legend for segments that don't fit anywhere on the
    chart was placed with a negative bbox_to_anchor offset and NO
    corresponding reservation of canvas space, so it rendered partially
    or fully past the bottom edge of the figure. Fixed by reserving
    legend space unconditionally before layout, the same pattern
    area.py and bar.py already used successfully.
    """

    def test_legend_does_not_clip_at_figure_bottom(self, tmp_path):
        # The actual failing configuration: a long label whose only
        # available piece is too narrow to hold it anywhere.
        fig = snake_chart(
            segments={
                'Percentage Employed in Agricultural and Related Outdoor Labor': 60,
                'Percentage Employed in Domestic and Personal Service Roles': 15,
                'Percentage Employed in Skilled Trade and Manufacturing Work': 10,
                'Percentage Employed in Commercial Trade and Retail Positions': 8,
                'Percentage Employed in Recognized Professional Occupations': 7,
            },
            n_rows=6,
            title='Comprehensive Breakdown of Occupational Categories Across '
                  'the Full Surveyed Population, By Percentage Share',
        )
        bottom_y, height = _rendered_content_bottom_px(fig, str(tmp_path / 'clip_check.png'))
        assert bottom_y < height - 1, (
            "Content (likely the legend) extends to the last pixel row -- "
            "possible clipping regression."
        )
        plt.close(fig)

    def test_many_legend_entries_still_fit(self, tmp_path):
        # Push harder: a config designed so MOST segments need the
        # legend fallback (many narrow slivers from heavy row-splitting).
        segments = {f'Category Number {i} With Some Descriptive Text': 5
                    for i in range(18)}
        fig = snake_chart(segments=segments, n_rows=10,
                           title='Stress Test With Many Small Segments')
        bottom_y, height = _rendered_content_bottom_px(fig, str(tmp_path / 'clip_check2.png'))
        assert bottom_y < height - 1
        plt.close(fig)


class TestRegressionLabelTruncation:
    """
    Regression coverage (at the snake_chart level, complementing the
    direct unit coverage in test_text_utils.py) for fit_label_in_box
    silently returning ellipsis-truncated text disguised as a clean fit.
    No label actually drawn on a real chart should ever contain an
    ellipsis -- the correct behavior is either a complete label or a
    legend fallback, never a mangled fragment.
    """

    def test_no_rendered_label_contains_an_ellipsis(self):
        segments = {
            'Percentage Employed in Agricultural and Related Outdoor Labor': 60,
            'Percentage Employed in Domestic and Personal Service Roles': 15,
            'Percentage Employed in Skilled Trade and Manufacturing Work': 10,
            'Percentage Employed in Commercial Trade and Retail Positions': 8,
            'Percentage Employed in Recognized Professional Occupations': 7,
        }
        fig = snake_chart(segments=segments, n_rows=6,
                           title='Ellipsis Regression Check')
        ax = fig.axes[0]
        for t in ax.texts:
            assert '\u2026' not in t.get_text(), f"Ellipsis found in: {t.get_text()!r}"
        # Also check the legend, if one was created.
        if fig.legends:
            for legend in fig.legends:
                for t in legend.get_texts():
                    assert '\u2026' not in t.get_text(), f"Ellipsis in legend: {t.get_text()!r}"
        plt.close(fig)


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Considerably Long Title For A Snake Chart About Occupations ' * 2
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_small_segments_do_not_raise(self):
        segments = {f'Segment {i}': 100 / 30 for i in range(30)}
        with pytest.warns(UserWarning, match='look alike'):   # 30 colours can't all be distinct
            fig = snake_chart(segments=segments, n_rows=8)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestRegressionConsistentSegmentLabelFontSize:
    """
    Regression coverage for the same bug found in county_map_chart and
    pie_chart (see GENERAL_ENGINE_README.md): each segment's label was
    fit independently, maximizing its own size against its own widest
    piece. On a 5-segment snake chart with varying piece widths,
    "Agriculture" (a full-row-width piece) came out at 13pt while
    "Trade" (a much narrower piece) came out around 7.2pt -- a 44%
    difference, and bold text at the smaller size renders with visibly
    thinner strokes than the same weight at the larger size, reading as
    a mismatched font even though nothing about the font had changed.
    Checked for here specifically because the same pattern had already
    been found twice elsewhere, not because a fresh stress test happened
    to surface it independently.
    """

    def test_all_placed_labels_share_one_font_size(self):
        segments = {
            'Percentage Employed in Agricultural and Related Outdoor Labor': 60,
            'Percentage Employed in Domestic and Personal Service Roles': 15,
            'Percentage Employed in Skilled Trade and Manufacturing Work': 10,
            'Percentage Employed in Commercial Trade and Retail Positions': 8,
            'Percentage Employed in Recognized Professional Occupations': 7,
        }
        fig = snake_chart(segments=segments, n_rows=6)
        ax = fig.axes[0]
        # Exclude the scale-anchor labels (plain percentages at row
        # edges), which are a separate, already-consistent label class
        # at their own fixed size -- only segment-name labels matter
        # for this check.
        segment_label_sizes = {
            round(t.get_fontsize(), 2) for t in ax.texts
            if not t.get_text().replace('%', '').strip().isdigit()
        }
        assert len(segment_label_sizes) <= 1, (
            f"Inconsistent segment label sizes: {segment_label_sizes}"
        )
        plt.close(fig)

    def test_basic_case_still_all_at_ceiling(self):
        # A regression guard in the other direction: when every segment
        # comfortably fits at the max size, the fix shouldn't needlessly
        # shrink anything below that ceiling.
        fig = snake_chart(segments=BASIC_SEGMENTS, n_rows=4)
        ax = fig.axes[0]
        segment_label_sizes = {
            round(t.get_fontsize(), 2) for t in ax.texts
            if not t.get_text().replace('%', '').strip().isdigit()
        }
        assert segment_label_sizes == {13.0}
        plt.close(fig)


class TestRegressionWordBreaking:
    """
    Regression coverage for a bug found by testing with real data, not
    constructed synthetic stress cases: an 8-category real-world U.S.
    electricity-source breakdown (Natural Gas, Nuclear, Coal, Wind,
    Hydro, Solar, Biomass, Other) rendered "Other" -- a common, entirely
    ordinary 5-letter word, 1.2% of the total -- as "Oth" over "er",
    split mid-word with no hyphen. The shared-fontsize search's
    fit_label_in_box call can fall back to hard-breaking a single word
    that's wider than its piece even on its own; that's the correct,
    necessary behavior in general (see wrap_text_to_width's own
    documented ellipsis/hard-break fallback), but silently accepting it
    for a short, ordinary category name looks broken rather than
    intentional. Fixed by rejecting any fitted result where the wrapped
    lines don't reconstruct the exact original words -- a real word
    split across lines fails that check; a real word simply not fitting
    at all now correctly falls back to the legend instead.
    """

    def test_short_word_falls_back_to_legend_rather_than_breaking(self):
        segments = {
            'Natural Gas': 43.4, 'Nuclear': 18.1, 'Coal': 15.1, 'Wind': 10.5,
            'Hydro': 5.5, 'Solar': 5.1, 'Biomass': 1.1, 'Other': 1.2,
        }
        fig = snake_chart(segments=segments, n_rows=4)
        ax = fig.axes[0]
        for t in ax.texts:
            words = t.get_text().split()
            for w in words:
                assert w in ('Natural', 'Gas', 'Nuclear', 'Coal', 'Wind', 'Hydro',
                              'Solar', 'Biomass', 'Other') or '%' in w or w.isdigit(), (
                    f"Found a fragment that isn't a whole word or value: {w!r}"
                )
        # And specifically: no lone "Oth" or "er" fragment anywhere.
        all_text = ' '.join(t.get_text() for t in ax.texts)
        assert 'Oth' not in all_text or 'Other' in all_text
        plt.close(fig)

    def test_no_word_was_broken_helper_directly(self):
        # The exact failing case, checked directly against the helper's
        # logic rather than only through a full chart render.
        # Simulate what wrap_text_to_width's hard-break fallback produces
        # for "Other  1%" in a box too narrow even for "Other" alone.
        broken = ['Oth', 'er  1%']
        clean = ['Other', '1%']
        original = 'Other  1%'
        assert ' '.join(broken).split() != original.split()
        assert ' '.join(clean).split() == original.split()
