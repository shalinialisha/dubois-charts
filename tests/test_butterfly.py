"""
Tests for dubois_charts.charts.butterfly.butterfly_chart.

Includes regression tests for both bugs documented in
GENERAL_ENGINE_README.md:
  1. Value labels on the inverted left axis growing back into their own
     bars because `ha='left'` is a screen-space direction that means
     something different once an axis is inverted.
  2. Long header labels overflowing both figure edges at once because
     they only had shrink-to-fit, no wrap fallback.
"""

import pytest
import matplotlib.pyplot as plt

from dubois_charts.charts.butterfly import butterfly_chart


BASIC_CATEGORIES = ['Agriculture', 'Domestic Service', 'Trade', 'Professions']
BASIC_LEFT = [52, 38, 6, 4]
BASIC_RIGHT = [31, 55, 8, 6]


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = butterfly_chart(categories=BASIC_CATEGORIES,
                               left_values=BASIC_LEFT, right_values=BASIC_RIGHT)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_headers_and_title(self):
        fig = butterfly_chart(categories=BASIC_CATEGORIES,
                               left_values=BASIC_LEFT, right_values=BASIC_RIGHT,
                               left_label='Male', right_label='Female',
                               title='Occupations by Sex')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_category(self):
        fig = butterfly_chart(categories=['Only'], left_values=[10], right_values=[20])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_categories(self):
        cats = [f'Cat {i}' for i in range(12)]
        fig = butterfly_chart(categories=cats,
                               left_values=list(range(12)),
                               right_values=list(range(12, 24)))
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_asymmetric_scale_uses_shared_max(self):
        # One side much larger than the other -- should still render
        # without error, sharing one scale (the documented behavior).
        fig = butterfly_chart(categories=['A', 'B'], left_values=[5, 8],
                               right_values=[500, 800])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_zero_values(self):
        fig = butterfly_chart(categories=['A', 'B'], left_values=[0, 10],
                               right_values=[10, 0])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestInputValidation:
    def test_empty_categories_raises(self):
        with pytest.raises(ValueError):
            butterfly_chart(categories=[], left_values=[], right_values=[])

    def test_mismatched_left_length_raises(self):
        with pytest.raises(ValueError):
            butterfly_chart(categories=['A', 'B'], left_values=[1], right_values=[1, 2])

    def test_mismatched_right_length_raises(self):
        with pytest.raises(ValueError):
            butterfly_chart(categories=['A', 'B'], left_values=[1, 2], right_values=[1])


class TestRegressionInvertedAxisAlignment:
    """
    Regression coverage for the ha='left'/'right' inverted-axis bug: the
    left axis is inverted (0 at center, growing outward to the left), so
    a value label meant to sit just past a bar's outer edge needs
    ha='right' there specifically -- ha='left' was found (via an actual
    render) to grow the label back into the bar instead of away from it.
    """

    def test_left_axis_value_labels_use_right_alignment(self):
        fig = butterfly_chart(categories=['A', 'B'], left_values=[30, 50],
                               right_values=[20, 40], value_format='{:.0f}%')
        ax_l = fig.axes[0]  # left axis is added first
        value_texts = [t for t in ax_l.texts if '%' in t.get_text()]
        assert len(value_texts) > 0
        for t in value_texts:
            assert t.get_ha() == 'right'
        plt.close(fig)

    def test_right_axis_value_labels_use_left_alignment(self):
        fig = butterfly_chart(categories=['A', 'B'], left_values=[30, 50],
                               right_values=[20, 40], value_format='{:.0f}%')
        ax_r = fig.axes[1]  # right axis is added second
        value_texts = [t for t in ax_r.texts if '%' in t.get_text()]
        assert len(value_texts) > 0
        for t in value_texts:
            assert t.get_ha() == 'left'
        plt.close(fig)


class TestRegressionHeaderWrapping:
    def test_regression_wrapped_header_does_not_clip_at_canvas_top(self, tmp_path):
        """
        Regression coverage for a bug found by checking actual rendered
        pixel extent (0px top margin -- confirmed clipped): the header
        block's RESERVED space (header_block_px) and the header's actual
        DRAWING position were computed by two independent formulas that
        had no guaranteed relationship to each other -- the drawing loop
        used a hardcoded "1.03" axes-fraction starting offset that
        wasn't derived from header_block_px at all. For a long header
        wrapped to two lines, the two disagreed enough that the topmost
        line's rendered top edge ran past the literal top edge of the
        canvas. Fixed by deriving the drawing position directly from
        header_block_px instead of an independent constant, so the two
        can't silently diverge again.
        """
        from PIL import Image
        import numpy as np

        out = tmp_path / 'header_clip_check.png'
        fig = butterfly_chart(
            categories=[f'A Fairly Long Category Description Number {i}' for i in range(8)],
            left_values=[1, 1, 1, 1, 1, 1, 1, 90],
            right_values=[90, 1, 1, 1, 1, 1, 1, 1],
            left_label='A Very Long Header Label For The Left Side Of This Chart',
            right_label='A Very Long Header Label For The Right Side Of This Chart',
            save_path=str(out),
        )
        plt.close(fig)

        img = np.array(Image.open(out).convert('RGB'))
        bg = np.array([int(c * 255) for c in fig.get_facecolor()[:3]])
        diff = np.abs(img.astype(int) - bg).sum(axis=2)
        mask = diff > 30
        ys, _ = np.where(mask)
        assert ys.min() > 0, "Header text clipped at the top edge of the canvas"


    """
    Regression coverage for the header-overflow bug: an 86-character
    header only had shrink-to-fit and ran off both figure edges at once,
    colliding with its counterpart in the middle. Headers should now
    wrap rather than overflow when shrinking alone isn't enough.
    """

    def test_extremely_long_headers_do_not_raise(self):
        fig = butterfly_chart(
            categories=['A', 'B', 'C'],
            left_values=[20, 40, 10], right_values=[30, 15, 50],
            left_label='Households Reporting Below-Threshold Income In This '
                        'Extremely Long Header Test Case',
            right_label='Households Reporting Above-Threshold Income In This '
                        'Extremely Long Header Test Case',
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_short_headers_still_render_as_single_line(self):
        fig = butterfly_chart(categories=BASIC_CATEGORIES,
                               left_values=BASIC_LEFT, right_values=BASIC_RIGHT,
                               left_label='Male', right_label='Female')
        ax_l = fig.axes[0]
        header_texts = [t.get_text() for t in ax_l.texts if 'MALE' in t.get_text().upper()]
        assert len(header_texts) == 1
        plt.close(fig)


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Considerably Long Title For A Butterfly Chart Comparison ' * 2
        fig = butterfly_chart(categories=BASIC_CATEGORIES,
                               left_values=BASIC_LEFT, right_values=BASIC_RIGHT,
                               title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_long_category_labels_do_not_raise(self):
        cats = [
            'A Rather Long Category Description Here',
            'Another Long Category Description As Well',
        ]
        fig = butterfly_chart(categories=cats, left_values=[10, 20], right_values=[30, 40])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'butterfly_test_output.png'
        fig = butterfly_chart(categories=BASIC_CATEGORIES,
                               left_values=BASIC_LEFT, right_values=BASIC_RIGHT,
                               save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestRegressionNegativeValues:
    """
    Regression coverage for a bug found by rendering a negative value
    through butterfly_chart: each bar's length represents a magnitude
    extending outward from the shared center axis, and a negative value
    rendered as a completely invisible bar with no value label and no
    error -- the same failure pattern found in bar_chart, since the left
    axis is also anchored at a fixed x=0 with no visible range beyond it
    in the negative direction.
    """

    def test_negative_left_value_raises(self):
        with pytest.raises(ValueError, match=r"`left_values` has a negative value for 'A' \(-20\).*zero or more"):
            butterfly_chart(categories=['A', 'B'], left_values=[-20, 30], right_values=[10, 20])

    def test_negative_right_value_raises(self):
        with pytest.raises(ValueError, match=r"`right_values` has a negative value for 'B' \(-5\).*zero or more"):
            butterfly_chart(categories=['A', 'B'], left_values=[10, 20], right_values=[30, -5])


class TestRegressionHeaderCapitals:
    """
    Headers are drawn in capitals, but they used to be measured and wrapped
    in their original case and only upper-cased when drawn. Two bugs came
    from that:

    - "iOS" became "IOS" (found on real Android/iOS market-share data),
      while pie_chart, which doesn't force capitals, kept "iOS".
    - In a proportional font capitals are wider than lowercase, so long
      headers ran past their half of the chart -- by up to 114px in
      DejaVu Sans and Liberation Serif. Invisible in the default monospace
      font, where both cases are the same width.

    Headers are now converted with display_caps before measuring, which
    also keeps deliberate mixed case.
    """

    @staticmethod
    def _headers(fig):
        return [t for ax in fig.axes[:2] for t in ax.texts
                if t.get_transform() == ax.transAxes and t.get_text().strip()]

    def test_brand_capitalisation_survives(self):
        fig = butterfly_chart(categories=['A', 'B'], left_values=[82, 85], right_values=[18, 15],
                              left_label='Android', right_label='iOS')
        assert sorted(t.get_text() for t in self._headers(fig)) == ['ANDROID', 'iOS']
        plt.close(fig)

    @staticmethod
    def _long_header_chart(show_value_labels):
        # DejaVu Sans ships with matplotlib, so this font is always available.
        return butterfly_chart(categories=['A', 'B'], left_values=[30, 20], right_values=[25, 35],
                               left_label='share of adults with a college degree today',
                               right_label='wage earners in manufacturing industries',
                               font='DejaVu Sans', show_value_labels=show_value_labels)

    @pytest.mark.parametrize('show_value_labels', [True, False])
    def test_long_headers_fit_the_width_they_were_wrapped_to(self, show_value_labels):
        # The exact property the bug broke: headers are wrapped to 92% of
        # their panel's width, so the drawn text must fit that width. With
        # the old measure-lowercase-draw-capitals behaviour, these headers
        # came out 117-128px wider than that. (Checking against the frame alone isn't
        # enough: frames now widen to enclose value labels, and on this
        # data an oversized header happens to fit the wider frame.)
        fig = self._long_header_chart(show_value_labels)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for ax in fig.axes[:2]:
            panel_w = ax.get_window_extent(renderer).width
            for t in self._headers(fig):
                if t.axes is ax:
                    w = t.get_window_extent(renderer).width
                    assert w <= panel_w * 0.92 + 1, (
                        f"{t.get_text()!r} is {w:.0f}px wide, more than the "
                        f"{panel_w * 0.92:.0f}px it was wrapped to fit"
                    )
        plt.close(fig)

    @pytest.mark.parametrize('show_value_labels', [True, False])
    def test_long_headers_stay_inside_their_frame(self, show_value_labels):
        from matplotlib.patches import Rectangle
        fig = self._long_header_chart(show_value_labels)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for ax in fig.axes[:2]:
            frame = [p for p in ax.patches if isinstance(p, Rectangle) and not p.get_fill()][0]
            fb = frame.get_window_extent(renderer)
            for t in self._headers(fig):
                if t.axes is ax:
                    tb = t.get_window_extent(renderer)
                    assert tb.x0 >= fb.x0 - 0.5 and tb.x1 <= fb.x1 + 0.5, (
                        f"{t.get_text()!r} runs past its frame"
                    )
        plt.close(fig)
