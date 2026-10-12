"""
Tests for dubois_charts.charts.bar.bar_chart.

Includes a regression test for the specific bug documented in
GENERAL_ENGINE_README.md: a self-canceling expression
(`-0.015 * xlim_max / (right_frac - left_frac) * (right_frac - left_frac)`)
that reduced to a data-unit value being used where an axes-fraction
offset was needed, caught by re-reading the geometry rather than by a
broken render. That specific bug is gone now, but the test suite should
not silently let something like it back in.
"""

import pytest
import matplotlib.pyplot as plt

from dubois_charts.charts.bar import bar_chart


BASIC_CATEGORIES = ['Agriculture', 'Domestic Service', 'Trade', 'Professions']
BASIC_VALUES = [45, 25, 10, 8]


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = bar_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = bar_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                         title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_sort_descending(self):
        fig = bar_chart(categories=['B', 'A', 'C'], values=[5, 50, 10],
                         sort_descending=True)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_category(self):
        fig = bar_chart(categories=['Only One'], values=[42])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_categories(self):
        cats = [f'Category {i}' for i in range(25)]
        vals = list(range(25))
        fig = bar_chart(categories=cats, values=vals)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_grouped_series(self):
        fig = bar_chart(
            categories=['A', 'B', 'C'],
            values={'Urban': [10, 20, 30], 'Rural': [40, 50, 60]},
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_zero_value_bar(self):
        fig = bar_chart(categories=['A', 'B'], values=[0, 50])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_all_zero_values(self):
        fig = bar_chart(categories=['A', 'B', 'C'], values=[0, 0, 0])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestInputValidation:
    def test_empty_categories_raises(self):
        with pytest.raises(ValueError):
            bar_chart(categories=[], values=[])

    def test_mismatched_single_series_length_raises(self):
        with pytest.raises(ValueError):
            bar_chart(categories=['A', 'B', 'C'], values=[1, 2])

    def test_mismatched_grouped_series_length_raises(self):
        with pytest.raises(ValueError):
            bar_chart(categories=['A', 'B'], values={'X': [1, 2, 3]})

    def test_grouped_error_names_the_series(self):
        with pytest.raises(ValueError, match='Weird'):
            bar_chart(categories=['A', 'B'], values={'Weird': [1, 2, 3]})


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Substantially Long Title For A Bar Chart About Occupations ' * 2
        fig = bar_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_long_category_labels_do_not_raise(self):
        cats = [
            'A Very Long Category Label That Will Need To Wrap Or Shrink',
            'Another Similarly Long Category Label For Good Measure',
        ]
        fig = bar_chart(categories=cats, values=[30, 60])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_no_category_label_rendered_at_the_figure_edge(self):
        # Regression guard for the fixed x-position bug: every category
        # label's text anchor should land at a sane (finite, bounded)
        # axes-fraction x, not at some degenerate value produced by a
        # canceled-out expression. We can't easily assert the *visual*
        # non-clipping without image analysis, but we can assert the
        # geometry itself is sane.
        fig = bar_chart(categories=['Domestic Service', 'Trade'], values=[25, 10])
        ax = fig.axes[0]
        texts = [t for t in ax.texts if t.get_text() in ('Domestic Service', 'Trade')]
        assert len(texts) >= 1
        for t in texts:
            x, _ = t.get_position()
            assert abs(x) < 1.0  # small axes-fraction offset, not something absurd
        plt.close(fig)

    def test_custom_value_format(self):
        fig = bar_chart(categories=['A', 'B'], values=[1234, 5678],
                         value_format='${:,.0f}')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'bar_test_output.png'
        fig = bar_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                         save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestDivergingValues:
    """
    Coverage for diverging (mixed positive/negative) data support.

    Earlier in this package's development, a negative value rendered as
    a completely invisible bar with no value label and no error, since
    every bar grew rightward from a fixed x=0 axis start with no visible
    range on the other side. That was fixed by rejecting negative values
    outright -- correct given the rendering model at the time, but a
    real limitation: GDP growth rates, profit/loss, and other
    legitimately-signed real-world data had no path through this
    function at all. `bar_chart` now supports diverging data properly:
    each bar still grows from a shared x=0 origin, but rightward for a
    positive value and leftward for a negative one, with a visible
    origin line when the data actually spans both signs and each
    value's label drawn on the outward side of its own bar.
    """

    def test_mixed_sign_values_render_without_error(self):
        fig = bar_chart(categories=['A', 'B', 'C'], values=[-20, 30, 40])
        plt.close(fig)

    def test_all_negative_values_render_without_error(self):
        fig = bar_chart(categories=['A', 'B', 'C'], values=[-5, -20, -12])
        plt.close(fig)

    def test_negative_value_in_grouped_series_renders_without_error(self):
        fig = bar_chart(categories=['A', 'B'], values={'X': [10, 20], 'Y': [-5, 15]})
        plt.close(fig)

    def test_mixed_sign_axis_spans_both_directions(self):
        fig = bar_chart(categories=['A', 'B'], values=[-8, 12])
        ax = fig.axes[0]
        xlim_lo, xlim_hi = ax.get_xlim()
        assert xlim_lo < 0 < xlim_hi
        plt.close(fig)

    def test_all_positive_axis_still_starts_at_zero(self):
        # The default, still-most-common case must be completely
        # unaffected by diverging support existing at all.
        fig = bar_chart(categories=['A', 'B'], values=[10, 20])
        ax = fig.axes[0]
        xlim_lo, _ = ax.get_xlim()
        assert xlim_lo == 0
        plt.close(fig)

    def test_all_negative_axis_ends_at_zero(self):
        fig = bar_chart(categories=['A', 'B'], values=[-10, -20])
        ax = fig.axes[0]
        _, xlim_hi = ax.get_xlim()
        assert xlim_hi == 0
        plt.close(fig)

    def test_zero_line_drawn_when_diverging(self):
        fig = bar_chart(categories=['A', 'B'], values=[-8, 12])
        ax = fig.axes[0]
        zero_lines = [ln for ln in ax.get_lines()
                     if list(ln.get_xdata()) == [0, 0]]
        assert len(zero_lines) >= 1
        plt.close(fig)

    def test_negative_value_label_does_not_collide_with_category_label(self):
        # The exact regression this feature's first implementation
        # attempt introduced: a category name and its own bar's negative
        # value label overlapping when the bar's magnitude approaches
        # the axis extreme. Checked via actual rendered bounding boxes.
        fig = bar_chart(
            categories=['Ireland', 'Qatar'],
            values=[12.6, -8.65],
            value_format='{:.1f}%',
        )
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ax = fig.axes[0]
        by_text = {t.get_text(): t for t in ax.texts}
        cat_box = by_text['Qatar'].get_window_extent(renderer=renderer)
        val_box = by_text['-8.7%'].get_window_extent(renderer=renderer)
        overlaps = cat_box.x0 < val_box.x1 and val_box.x0 < cat_box.x1
        assert not overlaps, (
            f"'Qatar' ({cat_box.x0:.0f}-{cat_box.x1:.0f}) overlaps "
            f"'-8.7%' ({val_box.x0:.0f}-{val_box.x1:.0f})"
        )
        plt.close(fig)

    def test_negative_value_label_on_left_positive_on_right(self):
        fig = bar_chart(categories=['A', 'B'], values=[-8, 12], value_format='{:.0f}%')
        ax = fig.axes[0]
        by_text = {t.get_text(): t for t in ax.texts}
        assert by_text['-8%'].get_ha() == 'right'
        assert by_text['12%'].get_ha() == 'left'
        plt.close(fig)

    def test_sort_descending_still_works_with_mixed_signs(self):
        fig = bar_chart(
            categories=['A', 'B', 'C'], values=[-10, 20, -5], sort_descending=True,
        )
        ax = fig.axes[0]
        cat_texts = [t.get_text() for t in ax.texts if t.get_text() in ('A', 'B', 'C')]
        # B (20) should sort first (largest), then C (-5), then A (-10).
        assert cat_texts == ['B', 'C', 'A']
        plt.close(fig)


class TestRegressionDefaultValueFormat:
    """
    The default value_format used to be '{:.0f}%', so any raw number got
    a percent sign: India's 2025 population in millions rendered as
    "1457%". The default is now a plain number with thousands separators
    and just enough decimals; percentages are asked for explicitly.
    """

    @staticmethod
    def _labels(fig, candidates):
        return sorted(t.get_text() for t in fig.axes[0].texts if t.get_text() in candidates)

    def test_raw_counts_get_no_percent_sign(self):
        fig = bar_chart(categories=['India', 'China'], values=[1457.44, 1417.73])
        texts = [t.get_text() for t in fig.axes[0].texts]
        assert not any('%' in s for s in texts), texts
        assert self._labels(fig, {'1,457.44', '1,417.73'}) == ['1,417.73', '1,457.44']
        plt.close(fig)

    def test_whole_numbers_print_without_decimals(self):
        fig = bar_chart(categories=['Berlin', 'Madrid'], values=[3913644, 3506730])
        assert self._labels(fig, {'3,913,644', '3,506,730'}) == ['3,506,730', '3,913,644']
        plt.close(fig)

    def test_every_label_uses_the_same_precision(self):
        fig = bar_chart(categories=['Ireland', 'India', 'Qatar'], values=[12.6, 6.48, -8.65])
        assert self._labels(fig, {'12.60', '6.48', '-8.65'}) == ['-8.65', '12.60', '6.48']
        plt.close(fig)

    def test_explicit_value_format_still_wins(self):
        fig = bar_chart(categories=['A', 'B'], values=[45, 25], value_format='{:.0f}%')
        assert self._labels(fig, {'45%', '25%'}) == ['25%', '45%']
        plt.close(fig)
