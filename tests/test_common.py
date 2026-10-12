"""
Tests for dubois_charts.charts._common -- the visual-vocabulary helpers shared
by area.py, bar.py, butterfly.py, and spiral.py (see
GENERAL_ENGINE_README.md for why this was factored out rather than left
duplicated per chart).
"""

import pytest
import matplotlib.pyplot as plt
from dubois_charts.charts import _common as common


class TestGetFont:
    def test_returns_a_nonempty_string(self):
        font = common.get_font()
        assert isinstance(font, str)
        assert len(font) > 0


class TestTextColorFor:
    def test_dark_background_gets_light_text(self):
        color = common.text_color_for('#000000')
        # Should be a light color for legibility on black.
        r, g, b = plt.matplotlib.colors.to_rgb(color)
        assert (r + g + b) / 3 > 0.5

    def test_light_background_gets_dark_text(self):
        color = common.text_color_for('#ffffff')
        r, g, b = plt.matplotlib.colors.to_rgb(color)
        assert (r + g + b) / 3 < 0.5

    def test_returns_valid_hex_color(self):
        color = common.text_color_for('#557799')
        # Should not raise -- confirms it's a color matplotlib recognizes.
        plt.matplotlib.colors.to_rgb(color)


class TestShade:
    def test_lightening_increases_brightness(self):
        base = '#557799'
        lighter = common.shade(base, 0.15)
        r0, g0, b0 = plt.matplotlib.colors.to_rgb(base)
        r1, g1, b1 = plt.matplotlib.colors.to_rgb(lighter)
        assert (r1 + g1 + b1) >= (r0 + g0 + b0)

    def test_darkening_decreases_brightness(self):
        base = '#557799'
        darker = common.shade(base, -0.15)
        r0, g0, b0 = plt.matplotlib.colors.to_rgb(base)
        r1, g1, b1 = plt.matplotlib.colors.to_rgb(darker)
        assert (r1 + g1 + b1) <= (r0 + g0 + b0)

    def test_extreme_lightening_does_not_exceed_white(self):
        color = common.shade('#557799', 5.0)  # absurdly large amount
        r, g, b = plt.matplotlib.colors.to_rgb(color)
        assert max(r, g, b) <= 1.0

    def test_extreme_darkening_does_not_go_below_black(self):
        color = common.shade('#557799', -5.0)
        r, g, b = plt.matplotlib.colors.to_rgb(color)
        assert min(r, g, b) >= 0.0


class TestAddRectTexture:
    def test_zero_width_returns_none_without_crashing(self):
        fig, ax = plt.subplots()
        result = common.add_rect_texture(ax, 0, 0, 0, 5, '#dc143c', seed=1)
        assert result is None
        plt.close(fig)

    def test_zero_height_returns_none_without_crashing(self):
        fig, ax = plt.subplots()
        result = common.add_rect_texture(ax, 0, 0, 5, 0, '#dc143c', seed=1)
        assert result is None
        plt.close(fig)

    def test_normal_rect_returns_an_artist(self):
        fig, ax = plt.subplots()
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        result = common.add_rect_texture(ax, 1, 1, 5, 5, '#dc143c', seed=1)
        assert result is not None
        plt.close(fig)

    def test_reproducible_with_same_seed(self):
        fig1, ax1 = plt.subplots()
        ax1.set_xlim(0, 10); ax1.set_ylim(0, 10)
        im1 = common.add_rect_texture(ax1, 0, 0, 5, 5, '#557799', seed=42)

        fig2, ax2 = plt.subplots()
        ax2.set_xlim(0, 10); ax2.set_ylim(0, 10)
        im2 = common.add_rect_texture(ax2, 0, 0, 5, 5, '#557799', seed=42)

        import numpy as np
        assert np.array_equal(im1.get_array(), im2.get_array())
        plt.close(fig1)
        plt.close(fig2)


class TestAddPatchTexture:
    """
    The generalized (non-rectangle) sibling of add_rect_texture, added
    for pie_chart's wedge shapes -- a wedge is neither an axis-aligned
    rectangle nor a fill_between polygon, so it needed its own clip-path
    plumbing rather than reusing either existing texture helper as-is.
    """

    def test_degenerate_extent_returns_none(self):
        import matplotlib.patches as mpatches
        fig, ax = plt.subplots()
        wedge = mpatches.Wedge((0, 0), 1, 0, 90, transform=ax.transData)
        result = common.add_patch_texture(ax, wedge, '#dc143c', (0, 0, -1, 1), seed=1)
        assert result is None
        plt.close(fig)

    def test_normal_wedge_returns_an_artist(self):
        import matplotlib.patches as mpatches
        fig, ax = plt.subplots()
        ax.set_xlim(-1, 1); ax.set_ylim(-1, 1)
        wedge = mpatches.Wedge((0, 0), 1, 0, 90, transform=ax.transData)
        result = common.add_patch_texture(ax, wedge, '#dc143c', (-1, 1, -1, 1), seed=1)
        assert result is not None
        plt.close(fig)

    def test_reproducible_with_same_seed(self):
        import matplotlib.patches as mpatches
        import numpy as np

        fig1, ax1 = plt.subplots()
        ax1.set_xlim(-1, 1); ax1.set_ylim(-1, 1)
        w1 = mpatches.Wedge((0, 0), 1, 0, 90, transform=ax1.transData)
        im1 = common.add_patch_texture(ax1, w1, '#557799', (-1, 1, -1, 1), seed=7)

        fig2, ax2 = plt.subplots()
        ax2.set_xlim(-1, 1); ax2.set_ylim(-1, 1)
        w2 = mpatches.Wedge((0, 0), 1, 0, 90, transform=ax2.transData)
        im2 = common.add_patch_texture(ax2, w2, '#557799', (-1, 1, -1, 1), seed=7)

        assert np.array_equal(im1.get_array(), im2.get_array())
        plt.close(fig1)
        plt.close(fig2)


class TestValidateFinite:
    """
    Regression coverage for a bug found by actually rendering a NaN
    through several chart types, not just reasoning about it: a NaN or
    infinite value used to either crash deep inside matplotlib with an
    unhelpful low-level error ("Axis limits cannot be NaN or Inf",
    "cannot convert float NaN to integer") or, worse, silently render as
    a completely invisible, unlabeled bar with no error at all -- and in
    one observed case appeared to have thrown off the axis scale for the
    *other*, perfectly valid values in the same chart. Every one of the
    seven chart functions now routes through this shared check first.
    """

    def test_all_finite_values_pass_silently(self):
        common.validate_finite([1, 2, 3], "context")  # should not raise

    def test_nan_raises_value_error(self):
        with pytest.raises(ValueError, match='non-finite'):
            common.validate_finite([1, float('nan'), 3], "context")

    def test_inf_raises_value_error(self):
        with pytest.raises(ValueError, match='non-finite'):
            common.validate_finite([1, float('inf'), 3], "context")

    def test_negative_inf_raises_value_error(self):
        with pytest.raises(ValueError, match='non-finite'):
            common.validate_finite([1, float('-inf'), 3], "context")

    def test_error_names_the_offending_entry_by_label(self):
        with pytest.raises(ValueError, match='Bravo'):
            common.validate_finite([1, float('nan'), 3], "context",
                                    names=['Alpha', 'Bravo', 'Charlie'])

    def test_error_names_all_offending_entries(self):
        with pytest.raises(ValueError) as exc_info:
            common.validate_finite([float('nan'), 1, float('inf')], "context",
                                    names=['Alpha', 'Bravo', 'Charlie'])
        assert 'Alpha' in str(exc_info.value)
        assert 'Charlie' in str(exc_info.value)
        assert 'Bravo' not in str(exc_info.value)

    def test_falls_back_to_index_without_names(self):
        with pytest.raises(ValueError, match='index 1'):
            common.validate_finite([1, float('nan'), 3], "context")

    def test_works_on_2d_arrays(self):
        with pytest.raises(ValueError, match='non-finite'):
            common.validate_finite([[1, 2], [3, float('nan')]], "context")


class TestValidateFiniteAcrossAllCharts:
    """
    The same regression, exercised through the actual public API of
    every chart function rather than only the shared helper in
    isolation -- confirms each of the seven entry points was actually
    wired up to call it, not just that the helper itself works.
    """

    def test_bar_chart_nan(self):
        from dubois_charts.charts.bar import bar_chart
        with pytest.raises(ValueError, match='non-finite'):
            bar_chart(categories=['A', 'B'], values=[10, float('nan')])

    def test_bar_chart_inf(self):
        from dubois_charts.charts.bar import bar_chart
        with pytest.raises(ValueError, match='non-finite'):
            bar_chart(categories=['A', 'B'], values=[10, float('inf')])

    def test_stacked_area_chart_nan(self):
        from dubois_charts.charts.area import stacked_area_chart
        with pytest.raises(ValueError, match='non-finite'):
            stacked_area_chart(x=[1, 2, 3], series={'A': [1, 2, float('nan')], 'B': [3, 2, 1]})

    def test_butterfly_chart_nan(self):
        from dubois_charts.charts.butterfly import butterfly_chart
        with pytest.raises(ValueError, match='non-finite'):
            butterfly_chart(categories=['A', 'B'], left_values=[10, float('nan')],
                             right_values=[5, 5])

    def test_spiral_chart_nan(self):
        from dubois_charts.charts.spiral import spiral_chart
        with pytest.raises(ValueError, match='non-finite'):
            spiral_chart(categories=[1, 2, 3], values=[10, float('nan'), 30])

    def test_snake_chart_nan(self):
        from dubois_charts.charts.snake import snake_chart
        with pytest.raises(ValueError, match='non-finite'):
            snake_chart(segments={'A': 10, 'B': float('nan')})

    def test_pie_chart_nan(self):
        from dubois_charts.charts.pie import pie_chart
        with pytest.raises(ValueError, match='non-finite'):
            pie_chart(segments={'A': 10, 'B': float('nan')})

    def test_county_map_chart_infinity(self):
        # (A missing value -- NaN -- on a map is no data for that county;
        # see test_real_data.py. Infinity is still an error.)
        from dubois_charts.charts.choropleth import county_map_chart
        with pytest.raises(ValueError, match='non-finite'):
            county_map_chart(data={'Fulton': 50, 'Bibb': float('inf')})


class TestValidateFigsize:
    """
    Regression coverage for a bug found by rendering bar_chart with
    figsize=(0, 0): matplotlib itself validates `dpi` (a non-positive
    dpi raises a clean error there), but happily accepts a degenerate
    figsize, which doesn't fail until this package's own layout math
    divides by the resulting zero pixel dimension several calls deep,
    surfacing as a raw, unhelpful ZeroDivisionError instead of a
    message naming the actual problem.
    """

    def test_valid_figsize_passes_silently(self):
        common.validate_figsize((8, 6), 150)  # should not raise

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match='positive'):
            common.validate_figsize((0, 6), 150)

    def test_zero_height_raises(self):
        with pytest.raises(ValueError, match='positive'):
            common.validate_figsize((8, 0), 150)

    def test_negative_dimension_raises(self):
        with pytest.raises(ValueError, match='positive'):
            common.validate_figsize((-1, 6), 150)

    def test_nan_dimension_raises(self):
        with pytest.raises(ValueError, match='positive'):
            common.validate_figsize((float('nan'), 6), 150)

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError, match='pair of numbers'):
            common.validate_figsize('not a tuple', 150)

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match='pair of numbers'):
            common.validate_figsize((8, 6, 4), 150)

    def test_zero_dpi_raises(self):
        with pytest.raises(ValueError, match='dpi'):
            common.validate_figsize((8, 6), 0)

    def test_negative_dpi_raises(self):
        with pytest.raises(ValueError, match='dpi'):
            common.validate_figsize((8, 6), -150)


class TestValidateFigsizeAcrossAllCharts:
    """
    The same regression, exercised through the actual public API of
    every chart function -- confirms each entry point actually calls
    the shared check before its own layout math runs, not just that the
    helper itself works in isolation.
    """

    def test_bar_chart_zero_figsize(self):
        from dubois_charts.charts.bar import bar_chart
        with pytest.raises(ValueError, match='positive'):
            bar_chart(categories=['A', 'B'], values=[10, 20], figsize=(0, 0))

    def test_stacked_area_chart_zero_figsize(self):
        from dubois_charts.charts.area import stacked_area_chart
        with pytest.raises(ValueError, match='positive'):
            stacked_area_chart(x=[1, 2], series={'A': [1, 2]}, figsize=(0, 0))

    def test_butterfly_chart_zero_figsize(self):
        from dubois_charts.charts.butterfly import butterfly_chart
        with pytest.raises(ValueError, match='positive'):
            butterfly_chart(categories=['A'], left_values=[1], right_values=[1], figsize=(5, 0))

    def test_spiral_chart_nan_figsize(self):
        from dubois_charts.charts.spiral import spiral_chart
        with pytest.raises(ValueError, match='positive'):
            spiral_chart(categories=[1, 2], values=[1, 2], figsize=(float('nan'), 5))

    def test_snake_chart_bad_type_figsize(self):
        from dubois_charts.charts.snake import snake_chart
        with pytest.raises(ValueError, match='pair of numbers'):
            snake_chart(segments={'A': 50, 'B': 50}, figsize='bad')

    def test_pie_chart_zero_figsize(self):
        from dubois_charts.charts.pie import pie_chart
        with pytest.raises(ValueError, match='positive'):
            pie_chart(segments={'A': 50, 'B': 50}, figsize=(0, 0))

    def test_county_map_chart_zero_figsize(self):
        from dubois_charts.charts.choropleth import county_map_chart
        with pytest.raises(ValueError, match='positive'):
            county_map_chart(data={'Fulton': 50}, state='GA', figsize=(0, 0))


class TestBackgroundContrastAcrossAllCharts:
    """
    Regression coverage for a serious, widespread bug found by actually
    rendering a dark background and looking at the result: `background`
    is a documented parameter on every one of the seven chart functions,
    but only fill-based text (a label drawn on top of a colored bar,
    wedge, or band) ever went through contrast-aware color selection.
    Everything else -- titles, axis/category labels, borders, legends,
    external labels -- used a hardcoded near-black COLOR_INK constant
    that never checked against the actual background, so a dark
    background made nearly all of that text and every border invisible.

    Fixed by computing `ink_color = text_color_for(background)` once per
    chart (treating the background itself as a fill needing contrast-
    appropriate ink, the same logic already used for data fills) and
    using it everywhere COLOR_INK used to be hardcoded.

    These tests check the property directly: with a dark background,
    every rendered text artist's color must actually BE light (not
    assumed from the code, computed the same way _text_color_for itself
    decides "light or dark").
    """

    DARK_BG = '#1a1a2e'

    @staticmethod
    def _is_light(color):
        r, g, b = plt.matplotlib.colors.to_rgb(color)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance > 0.5

    def test_bar_chart_text_is_light_on_dark_background(self):
        from dubois_charts.charts.bar import bar_chart
        fig = bar_chart(categories=['Agriculture', 'Trade', 'Manufacturing'],
                         values=[45, 30, 25], background=self.DARK_BG)
        ax = fig.axes[0]
        # Category and value labels sit directly on the background (not
        # on a data fill), so these specifically must be light.
        outside_labels = [t for t in ax.texts
                          if t.get_text() in ('Agriculture', 'Trade', 'Manufacturing',
                                               '45', '30', '25')]
        assert len(outside_labels) == 6  # three category names and three values
        for t in outside_labels:
            assert self._is_light(t.get_color()), f"{t.get_text()!r} is not light: {t.get_color()}"
        plt.close(fig)

    def test_stacked_area_chart_axis_labels_light_on_dark_background(self):
        from dubois_charts.charts.area import stacked_area_chart
        fig = stacked_area_chart(x=[2018, 2019, 2020], series={'A': [30, 40, 35], 'B': [70, 60, 65]},
                                  background=self.DARK_BG)
        ax = fig.axes[0]
        year_labels = [t for t in ax.texts if t.get_text() in ('2018', '2019', '2020')]
        assert len(year_labels) == 3
        for t in year_labels:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_butterfly_chart_headers_light_on_dark_background(self):
        from dubois_charts.charts.butterfly import butterfly_chart
        fig = butterfly_chart(categories=['A', 'B'], left_values=[30, 40], right_values=[20, 50],
                               left_label='Male', right_label='Female', background=self.DARK_BG)
        header_texts = [t for t in fig.axes[0].texts if 'MALE' in t.get_text().upper()]
        header_texts += [t for t in fig.axes[1].texts if 'FEMALE' in t.get_text().upper()]
        assert len(header_texts) >= 2
        for t in header_texts:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_spiral_chart_point_labels_light_on_dark_background(self):
        from dubois_charts.charts.spiral import spiral_chart
        fig = spiral_chart(categories=[1870, 1880, 1890, 1900], values=[10, 20, 30, 40],
                            background=self.DARK_BG)
        ax = fig.axes[0]
        point_labels = [t for t in ax.texts if any(str(y) in t.get_text() for y in (1870, 1880, 1890, 1900))]
        assert len(point_labels) > 0
        for t in point_labels:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_snake_chart_scale_labels_light_on_dark_background(self):
        from dubois_charts.charts.snake import snake_chart
        fig = snake_chart(segments={'A': 60, 'B': 40}, n_rows=2, background=self.DARK_BG)
        ax = fig.axes[0]
        scale_labels = [t for t in ax.texts if t.get_text() in ('0%', '50%', '100%')]
        assert len(scale_labels) > 0
        for t in scale_labels:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_pie_chart_external_label_light_on_dark_background(self):
        from dubois_charts.charts.pie import pie_chart
        fig = pie_chart(segments={'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5},
                         background=self.DARK_BG)
        ax = fig.axes[0]
        external = [t for t in ax.texts if 'Divorced' in t.get_text()]
        assert len(external) >= 1
        for t in external:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_county_map_chart_colorbar_labels_light_on_dark_background(self):
        from dubois_charts.charts.choropleth import county_map_chart
        fig = county_map_chart(data={'Fulton': 82, 'Bibb': 61, 'Cobb': 70}, background=self.DARK_BG)
        # Colorbar tick labels are drawn via fig.text, not ax.text.
        colorbar_labels = [t for t in fig.texts
                           if t.get_text().replace('.', '').lstrip('-').isdigit()]
        assert len(colorbar_labels) > 0
        for t in colorbar_labels:
            assert self._is_light(t.get_color())
        plt.close(fig)

    def test_default_light_background_still_uses_dark_ink(self):
        # The other half of the regression: confirm the fix didn't
        # accidentally invert behavior for the normal (light) default
        # background -- ink should stay dark there, as it always was.
        from dubois_charts.charts.bar import bar_chart
        fig = bar_chart(categories=['A', 'B'], values=[10, 20])  # default light background
        ax = fig.axes[0]
        labels = [t for t in ax.texts if t.get_text() in ('A', 'B', '10', '20')]
        assert len(labels) == 4  # two category names and two values
        for t in labels:
            assert not self._is_light(t.get_color()), (
                f"{t.get_text()!r} unexpectedly light on the default light background"
            )
        plt.close(fig)


class TestTextureStrengthCalibration:
    """
    Regression coverage for a quality bug reported directly, not found
    by automated testing: the original texture strength (0.14) produced
    pixel variance so small (measured directly on a real rendered bar:
    only 4 unique colors across a wide horizontal strip, a min-max range
    of 3 RGB units out of 255) that it read as a flat, textureless fill,
    defeating the entire point of a "hand-painted" effect this package
    is meant to have.

    Raising the strength alone wasn't the whole fix: at a strength that
    looked good on saturated mid-tone colors (crimson, gold), a large
    near-black fill looked distractingly noisy in an actual chart
    render, even though an isolated small swatch of the same color at
    the same strength didn't show the problem as clearly. Fixed by
    dampening the effective strength for dark base colors specifically,
    checked here as a monotonic, bounded relationship rather than a
    single hardcoded pass/fail number.
    """

    def test_texture_variance_is_meaningfully_visible(self):
        rgba = common._grain_rgba('#dc143c', seed=1)
        rgb = rgba[:, :, :3]
        # The original 0.14 strength produced a std dev well under 1 (out
        # of 255) on real rendered pixels; this should now be clearly larger.
        std_0_to_255 = rgb.std() * 255
        assert std_0_to_255 > 2.0, (
            f"Texture variance ({std_0_to_255:.2f}) is too small to read as visible texture"
        )

    def test_dark_colors_get_dampened_relative_to_midtone_colors(self):
        # Near-black should end up with LESS actual pixel variance than a
        # saturated mid-tone color, even though both start from the same
        # nominal strength -- confirming the dampening is actually wired
        # in, not just present as unused code.
        dark_rgba = common._grain_rgba('#1d1d1d', seed=1)
        midtone_rgba = common._grain_rgba('#dc143c', seed=1)
        dark_std = dark_rgba[:, :, :3].std()
        midtone_std = midtone_rgba[:, :, :3].std()
        assert dark_std < midtone_std

    def test_dampening_is_monotonic_in_lightness(self):
        # As base lightness increases from near-black, the effective
        # texture variance should increase too (up to the point full
        # strength kicks in), not jump around unpredictably.
        colors_by_lightness = ['#0d0d0d', '#1d1d1d', '#404040', '#808080']
        stds = [common._grain_rgba(c, seed=1)[:, :, :3].std() for c in colors_by_lightness]
        assert all(stds[i] <= stds[i + 1] + 1e-9 for i in range(len(stds) - 1)), (
            f"Texture variance isn't monotonic with lightness: {stds}"
        )

    def test_plate51_has_its_own_independent_texture_unaffected(self):
        # plate51.py's texture is separately, historically calibrated --
        # confirm this shared-engine change didn't reach into it.
        from dubois_charts.charts import plate51
        assert not hasattr(plate51, '_grain_rgba'), (
            "plate51.py should have its own separate texture implementation, "
            "not share _common.py's _grain_rgba"
        )


class TestDefaultValueFormat:
    """Unit checks for the plain-number default used by bar_chart."""

    @pytest.mark.parametrize('values, expected', [
        ([45, 25, 8], ['45', '25', '8']),
        ([1457.44, 346.37], ['1,457.44', '346.37']),
        ([12.6, 6.48], ['12.60', '6.48']),
        ([3913644, 816614], ['3,913,644', '816,614']),
        ([0.00123, 0.0045], ['0.00123', '0.00450']),   # small values don't collapse to "0.00"
        ([0.1 + 0.2, 1.0], ['0.3', '1.0']),             # float noise doesn't force extra decimals
        ([-5, -20], ['-5', '-20']),
    ])
    def test_formats(self, values, expected):
        fmt = common.default_value_format(values)
        assert [fmt.format(v) for v in values] == expected

    def test_never_adds_a_percent_sign(self):
        assert '%' not in common.default_value_format([45, 25, 12])


class TestDisplayCaps:
    """Unit checks for the capitalisation used by titles, butterfly headers
    and area band names."""

    @pytest.mark.parametrize('text, expected', [
        ('Android', 'ANDROID'),
        ('iOS', 'iOS'),
        ('Mobile OS share (iOS vs Android)', 'MOBILE OS SHARE (iOS VS ANDROID)'),
        ("McDonald's revenue", "McDonald's REVENUE"),
        ('DeKalb County', 'DeKalb COUNTY'),
        ('Output in kWh', 'OUTPUT IN kWh'),
        ('Coca-Cola', 'COCA-COLA'),       # hyphenated ordinary words are still capitalised
        ('Kraków', 'KRAKÓW'),
        ('USA', 'USA'),
        ('2025-2026', '2025-2026'),
    ])
    def test_cases(self, text, expected):
        assert common.display_caps(text) == expected


class TestFormatNonzero:
    """Unit checks for the '<1%' formatting used by pie_chart."""

    @pytest.mark.parametrize('fmt, value, expected', [
        ('{:.0f}%', 0.41, '<1%'),
        ('{:.0f}%', 0.5, '1%'),       # halves round up, as people round them
        ('{:.0f}%', 0.49, '<1%'),
        ('{:.0f}%', 0.6, '1%'),
        ('{:.1f}%', 0.04, '<0.1%'),
        ('{:.1f}%', 0.4, '0.4%'),
        ('{:.0f}%', 0.0, '0%'),       # a true zero still says zero
        ('{:.0f}%', 72.77, '73%'),
        ('{:.0f}% share', 0.2, '<1% share'),
    ])
    def test_cases(self, fmt, value, expected):
        assert common.format_nonzero(fmt, value) == expected


class TestRegressionFrameNeverCutsText:
    """
    bar_chart and butterfly_chart drew their frame at the axis limits while
    value labels sit just past each bar's end, so the frame line cut
    through the label of the longest bar and of any bar close to it:
    "1,4|17.73" on real population data, "91%" on real Android/iOS share,
    both signs on diverging charts. The frames now enclose the labels.
    Checked on rendered boxes: no frame edge may pass through any text,
    and every frame must stay inside the figure.
    """

    CASES = [
        ('bar', dict(categories=['India', 'China', 'United States'],
                     values=[1457.44, 1417.73, 346.37])),
        ('bar', dict(categories=['Ireland', 'Germany', 'Iraq', 'Qatar'],
                     values=[12.6, 0.2, -6.77, -8.65], value_format='{:+.1f}%')),
        ('bar', dict(categories=['A', 'B', 'C'], values=[-5, -19.5, -20])),
        ('bar', dict(categories=['North', 'South'],
                     values={'2024': [3.2, -1.5], '2025': [-2.0, 4.5]}, value_format='{:+.1f}%')),
        ('bar', dict(categories=['Amazon', 'Walmart'], values=[715, 713], value_format='${:.0f}B')),
        ('butterfly', dict(categories=['Asia-Pacific', 'Africa', 'Latin America', 'North America'],
                           left_values=[82.03, 85.15, 90.90, 41.61],
                           right_values=[17.97, 14.85, 9.10, 58.13],
                           left_label='Android', right_label='iOS')),
        ('butterfly', dict(categories=['0-14', '15-64', '65+'], left_values=[31.2, 99.1, 18.0],
                           right_values=[30.0, 98.4, 22.5], value_format='{:.1f} million')),
    ]

    @staticmethod
    def _render(kind, kwargs):
        from dubois_charts.charts.bar import bar_chart
        from dubois_charts.charts.butterfly import butterfly_chart
        return (bar_chart if kind == 'bar' else butterfly_chart)(**kwargs)

    @pytest.mark.parametrize('kind, kwargs', CASES)
    def test_no_frame_edge_passes_through_text(self, kind, kwargs):
        from matplotlib.patches import Rectangle
        fig = self._render(kind, kwargs)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        fig_w = fig.get_size_inches()[0] * fig.dpi
        texts = [t for t in fig.texts if t.get_text().strip()]
        texts += [t for ax in fig.axes for t in ax.texts if t.get_text().strip()]
        frames = [p for ax in fig.axes for p in ax.patches
                  if isinstance(p, Rectangle) and not p.get_fill()]
        assert frames
        for frame in frames:
            fb = frame.get_window_extent(renderer)
            assert fb.x0 >= -0.5 and fb.x1 <= fig_w + 0.5, "frame runs off the figure"
            for t in texts:
                tb = t.get_window_extent(renderer)
                for edge_x in (fb.x0, fb.x1):
                    assert not (tb.x0 + 0.5 < edge_x < tb.x1 - 0.5
                                and tb.y0 < fb.y1 and fb.y0 < tb.y1), (
                        f"frame edge runs through {t.get_text()!r}")
                for edge_y in (fb.y0, fb.y1):
                    assert not (tb.y0 + 0.5 < edge_y < tb.y1 - 0.5
                                and tb.x0 < fb.x1 and fb.x0 < tb.x1), (
                        f"frame edge runs through {t.get_text()!r}")
        plt.close(fig)

    def test_frame_stays_at_the_bars_when_value_labels_are_off(self):
        # Nothing to enclose, so the frame keeps its old position: the
        # longest bar's end at 98% of the frame's width, as before.
        from matplotlib.patches import Rectangle
        from dubois_charts.charts.bar import bar_chart
        fig = bar_chart(categories=['A', 'B'], values=[10, 5], show_value_labels=False)
        ax = fig.axes[0]
        frame = [p for p in ax.patches if isinstance(p, Rectangle) and not p.get_fill()][0]
        assert frame.get_x() == 0
        assert frame.get_width() == pytest.approx(10 * 1.02)
        plt.close(fig)


class TestRegressionColorsArgument:
    """
    A `colors` list the caller passes. Found while fixing the palette:
    stacked_area_chart and multi-series bar_chart given fewer colours than
    series stopped halfway through drawing with a bare IndexError, and an
    empty list crashed the other charts with a ZeroDivisionError. Where
    colour is the only thing telling series apart, too few is now a clear
    error; where every item is labelled, a short list still repeats (one
    colour for every bar, or two alternating, is a legitimate choice).
    """

    def test_area_with_too_few_colours_says_so(self):
        from dubois_charts.charts.area import stacked_area_chart
        with pytest.raises(ValueError, match='2 colours for 3 series'):
            stacked_area_chart(x=[1, 2, 3], series={'a': [1, 2, 3], 'b': [2, 3, 4], 'c': [3, 4, 5]},
                               colors=['#DC143C', '#D4AF37'])

    def test_grouped_bars_with_too_few_colours_says_so(self):
        from dubois_charts.charts.bar import bar_chart
        with pytest.raises(ValueError, match='1 colour for 3 series'):
            bar_chart(categories=['A', 'B'], values={'x': [1, 2], 'y': [3, 4], 'z': [5, 6]},
                      colors=['#DC143C'])

    @pytest.mark.parametrize('chart', ['bar', 'pie', 'snake', 'area'])
    def test_empty_colours_list_says_so(self, chart):
        from dubois_charts.charts.bar import bar_chart
        from dubois_charts.charts.pie import pie_chart
        from dubois_charts.charts.snake import snake_chart
        from dubois_charts.charts.area import stacked_area_chart
        call = {
            'bar': lambda: bar_chart(categories=['A', 'B'], values=[1, 2], colors=[]),
            'pie': lambda: pie_chart(segments={'a': 1, 'b': 2}, colors=[]),
            'snake': lambda: snake_chart(segments={'a': 1, 'b': 2}, colors=[]),
            'area': lambda: stacked_area_chart(x=[1, 2], series={'a': [1, 2]}, colors=[]),
        }[chart]
        with pytest.raises(ValueError, match='empty'):
            call()

    def test_one_colour_string_colours_every_bar(self):
        from dubois_charts.charts.bar import bar_chart
        import matplotlib.colors as mcolors
        fig = bar_chart(categories=['A', 'B', 'C'], values=[1, 2, 3], colors='#DC143C')
        fills = {mcolors.to_hex(p.get_facecolor()) for p in fig.axes[0].patches if p.get_fill()}
        assert fills == {'#dc143c'}
        plt.close(fig)

    def test_short_list_still_repeats_where_every_item_is_labelled(self):
        from dubois_charts.charts.bar import bar_chart
        import matplotlib.colors as mcolors
        fig = bar_chart(categories=['A', 'B', 'C', 'D'], values=[4, 3, 2, 1],
                        colors=['#DC143C', '#000000'])
        fills = [mcolors.to_hex(p.get_facecolor()) for p in fig.axes[0].patches if p.get_fill()]
        assert sorted(fills) == ['#000000', '#000000', '#dc143c', '#dc143c']
        plt.close(fig)


class TestFastTextureMatchesTheOriginal:
    """
    The texture was made about twice as fast -- the long vertical blur as
    a cached matrix product, the colour blend a channel at a time -- on
    the condition that it draws exactly what it drew before. These pin
    that down against the original computations.
    """

    @pytest.mark.parametrize('shape', [(220, 220), (300, 260), (40, 500)])
    def test_streak_field_matches_scipy(self, shape):
        import numpy as np
        from scipy.ndimage import gaussian_filter
        noise = np.random.RandomState(5).normal(0, 1, size=shape)
        assert np.allclose(common.streak_field(noise), gaussian_filter(noise, sigma=(45, 1.2)),
                           rtol=0, atol=1e-12)

    def test_paint_grain_matches_the_original_formula(self):
        import numpy as np
        rng = np.random.RandomState(9)
        combined = rng.normal(0, 0.4, size=(220, 220))
        for colour in ('#DC143C', '#000000', '#FFFFFF', '#D4AF37'):
            base = np.array(plt.matplotlib.colors.to_rgb(colour))
            light = np.array(plt.matplotlib.colors.to_rgb(common.shade(colour, 0.12)))
            dark = np.array(plt.matplotlib.colors.to_rgb(common.shade(colour, -0.12)))
            amount = (combined * 0.65)[..., None]
            toward = np.where((combined > 0)[..., None], light - base, base - dark)
            original = np.dstack([np.clip(base + amount * toward, 0, 1), np.ones((220, 220))])
            assert np.array_equal(common.paint_grain(combined, 0.65, base, light, dark), original)


class TestRegressionGrainInOneImage:
    """
    Every textured shape -- bar, butterfly bar, snake piece, pie wedge,
    area band -- had an image of its own, made and drawn at a few
    milliseconds apiece: with a few hundred of them that was most of a
    4-5 second chart (300 bars took 4.2 seconds, a 200-row butterfly 4.9).
    The grain of a whole axes is now one GrainLayer, sampled into a single
    picture when the chart is drawn, with the noise of the first 24 shapes
    reused after that. These check that it's one picture, that it looks as
    the separate images did, and that a figure with it still pickles.
    """

    @staticmethod
    def _bars(n):
        import warnings
        import numpy as np
        from dubois_charts.charts.bar import bar_chart
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')      # (some rows unlabelled, in some fonts)
            return bar_chart([f'Item {i}' for i in range(n)],
                             list(np.random.default_rng(0).gamma(2, 10, n)))

    def test_hundreds_of_bars_are_one_image(self):
        fig = self._bars(300)
        ax = fig.axes[0]
        assert len(ax.images) == 0
        layers = [a for a in ax.get_children() if isinstance(a, common.GrainLayer)]
        assert len(layers) == 1 and len(layers[0].shapes) > 250
        plt.close(fig)

    def test_noise_is_made_for_the_first_shapes_only(self, monkeypatch):
        calls = []
        made = common._grain_noise
        monkeypatch.setattr(common, '_grain_noise', lambda *a: calls.append(a) or made(*a))
        fig = self._bars(300)
        fig.canvas.draw()
        assert len(calls) == common.GrainLayer.REUSE
        plt.close(fig)

    @pytest.mark.parametrize('chart', ['bar', 'pie', 'area', 'snake'])
    def test_it_looks_as_separate_images_did(self, chart):
        """The picture against one clipped image per shape, the old way."""
        import io
        import numpy as np
        from PIL import Image
        from matplotlib.patches import PathPatch
        import dubois_charts as dc
        make = {
            'bar': lambda: dc.bar_chart(['A', 'B', 'C', 'D'], [45, -25, 12, 30]),
            'pie': lambda: dc.pie_chart({'Married': 52, 'Single': 31, 'Widowed': 12,
                                             'Divorced': 5}),
            'area': lambda: dc.stacked_area_chart([1890, 1900, 1910],
                                                      {'Owners': [8, 13, 18], 'Tenants': [55, 52, 48]}),
            'snake': lambda: dc.snake_chart({'One': 45, 'Two': 25, 'Three': 12, 'Four': 10}),
        }[chart]

        def png(fig):
            out = io.BytesIO()
            fig.savefig(out, format='png', dpi=fig.dpi)
            return np.asarray(Image.open(out).convert('RGB')).astype(float)

        fig = make()
        layer = next(a for a in fig.axes[0].get_children() if isinstance(a, common.GrainLayer))
        composite = png(fig)
        layer.set_visible(False)
        for shape in layer.shapes:
            image = fig.axes[0].imshow(shape.get_array(), extent=shape.extent, origin='lower',
                                       aspect='auto', zorder=2.4, interpolation='bilinear')
            image.set_clip_path(PathPatch(shape.path, transform=fig.axes[0].transData))
        separate = png(fig)
        assert composite.shape == separate.shape
        difference = np.abs(composite - separate)
        # Off by a level here and there (numpy's arithmetic, not Agg's), and
        # by more at a handful of pixels on the edges between pie wedges.
        assert np.sqrt((difference ** 2).mean()) < 1.0
        assert (difference.max(axis=2) > 12).mean() < 0.0005
        plt.close(fig)

    def test_a_figure_with_grain_still_pickles(self):
        import io
        import pickle
        import numpy as np
        from PIL import Image
        fig = self._bars(30)
        before, after = io.BytesIO(), io.BytesIO()
        fig.savefig(before, format='png', dpi=60)
        pickle.loads(pickle.dumps(fig)).savefig(after, format='png', dpi=60)
        assert np.array_equal(np.asarray(Image.open(before)), np.asarray(Image.open(after)))
        plt.close(fig)

    def test_grain_is_drawn_at_the_resolution_it_is_saved_at(self):
        # Not drawn once and blown up: saved at twice the resolution, the
        # picture is made twice the size, from the shapes' own grain.
        import io
        fig = self._bars(5)
        layer = next(a for a in fig.axes[0].get_children() if isinstance(a, common.GrainLayer))
        fig.savefig(io.BytesIO(), format='png', dpi=fig.dpi)
        small = layer._drawn[1].shape
        fig.savefig(io.BytesIO(), format='png', dpi=fig.dpi * 2)
        large = layer._drawn[1].shape
        assert abs(large[0] - 2 * small[0]) <= 2 and abs(large[1] - 2 * small[1]) <= 2
        plt.close(fig)


class TestRegressionChartsKeepShowingInJupyter:
    """
    Every chart draws its text literally -- maths parsing and LaTeX off --
    and used matplotlib's rc_context for it, which on the way out put back
    *every* setting. matplotlib switches `interactive` on when it makes a
    Jupyter session's first figure; when that figure was one of these
    charts, rc_context switched it off again, and Jupyter showed no figure
    from then on: in a notebook only the first chart appeared. Now just
    the two text settings are changed and put back.
    """

    def test_a_setting_changed_while_drawing_is_kept(self):
        import matplotlib

        @common.literal_text
        def chart():
            matplotlib.interactive(True)     # what a Jupyter session's first figure does
            return plt.figure()

        before = matplotlib.is_interactive()
        try:
            matplotlib.interactive(False)
            plt.close(chart())
            assert matplotlib.is_interactive()
        finally:
            matplotlib.interactive(before)

    def test_the_text_settings_are_put_back(self):
        @common.literal_text
        def chart():
            assert plt.rcParams['text.parse_math'] is False
            assert plt.rcParams['text.usetex'] is False
            raise RuntimeError('a chart that fails part way')

        with plt.rc_context({'text.parse_math': True}):
            with pytest.raises(RuntimeError):
                chart()
            assert plt.rcParams['text.parse_math'] is True
