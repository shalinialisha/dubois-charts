"""
Tests for dubois_charts.colors module
"""

import numpy as np
import pytest
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from dubois_charts import colors


class TestColorPalettes:
    """Test color palette functions"""
    
    def test_get_palette_primary(self):
        """Test getting primary palette"""
        palette = colors.get_palette('primary')
        assert 'crimson' in palette
        assert 'gold' in palette
        assert 'black' in palette
        assert 'tan' in palette
        assert palette['crimson'] == '#DC143C'
    
    def test_get_palette_extended(self):
        """Test getting extended palette"""
        palette = colors.get_palette('extended')
        assert len(palette) > 4
        assert 'green' in palette
        assert 'purple' in palette
    
    def test_get_palette_invalid(self):
        """Test invalid palette name"""
        with pytest.raises(ValueError):
            colors.get_palette('nonexistent')
    
    def test_get_sequential_crimson(self):
        """Test sequential crimson palette"""
        seq = colors.get_sequential('crimson')
        assert len(seq) == 8
        assert all(isinstance(c, str) for c in seq)
        assert all(c.startswith('#') for c in seq)
    
    def test_get_sequential_custom_n(self):
        """Test sequential palette with custom n"""
        seq = colors.get_sequential('crimson', n=5)
        assert len(seq) == 5
    
    def test_get_sequential_invalid(self):
        """Test invalid sequential color"""
        with pytest.raises(ValueError):
            colors.get_sequential('invalid')
    
    def test_get_categorical(self):
        """Test categorical palette"""
        cat = colors.get_categorical(4)
        assert len(cat) == 4
        assert cat[0] == colors.DUBOIS_CLASSIC_4[0]
    
    def test_get_categorical_large(self):
        """Test categorical palette with more than 8 colors"""
        cat = colors.get_categorical(12)
        assert len(cat) == 12
    
    def test_get_diverging(self):
        """Test diverging palette"""
        div = colors.get_diverging(7)
        assert len(div) == 7
    
    def test_get_diverging_even_number(self, capsys):
        """An even number of colours is what's returned -- it used to print
        a warning and return one more than asked for."""
        div = colors.get_diverging(6)
        assert len(div) == 6
        assert div[0] == colors.DUBOIS_DIVERGING[0] and div[-1] == colors.DUBOIS_DIVERGING[-1]
        assert capsys.readouterr().out == ''


class TestColorConversion:
    """Test color conversion functions"""
    
    def test_hex_to_rgb(self):
        """Test hex to RGB conversion"""
        rgb = colors.hex_to_rgb('#DC143C')
        assert len(rgb) == 3
        assert all(0 <= c <= 1 for c in rgb)
        # Test approximate values
        assert abs(rgb[0] - 0.863) < 0.01  # Red
        assert abs(rgb[1] - 0.078) < 0.01  # Green
        assert abs(rgb[2] - 0.235) < 0.01  # Blue
    
    def test_rgb_to_hex(self):
        """Test RGB to hex conversion"""
        hex_color = colors.rgb_to_hex(1.0, 0.0, 0.0)
        assert hex_color.lower() == '#ff0000'
    
    def test_round_trip_conversion(self):
        """Test converting hex -> RGB -> hex"""
        original = '#DC143C'
        rgb = colors.hex_to_rgb(original)
        converted = colors.rgb_to_hex(*rgb)
        assert converted.lower() == original.lower()


class TestQuickAccess:
    """Test quick access color variables"""
    
    def test_quick_access_colors(self):
        """Test module-level color variables"""
        assert colors.crimson == '#DC143C'
        assert colors.gold == '#D4AF37'
        assert colors.black == '#000000'
        assert colors.tan == '#D2B48C'


class TestPaletteConstants:
    """Test palette constant definitions"""
    
    def test_dubois_primary(self):
        """Test primary palette constant"""
        assert len(colors.DUBOIS_PRIMARY) == 4
        assert all(isinstance(v, str) for v in colors.DUBOIS_PRIMARY.values())
    
    def test_dubois_classic_3(self):
        """Test 3-color classic palette"""
        assert len(colors.DUBOIS_CLASSIC_3) == 3
    
    def test_dubois_classic_4(self):
        """Test 4-color classic palette"""
        assert len(colors.DUBOIS_CLASSIC_4) == 4
    
    def test_dubois_categorical_8(self):
        """Test 8-color categorical palette"""
        assert len(colors.DUBOIS_CATEGORICAL_8) == 8
    
    def test_sequential_palettes(self):
        """Test sequential palette constants"""
        assert len(colors.CRIMSON_SEQUENTIAL) == 8
        assert len(colors.GOLD_SEQUENTIAL) == 8
        assert len(colors.GREEN_SEQUENTIAL) == 8


# Published CIEDE2000 test data: Sharma, Wu & Dalal (2005), "The CIEDE2000
# color-difference formula: implementation notes, supplementary test data,
# and mathematical observations", Table 1. The pairs cover the formula's
# traps -- hue angles either side of 0/360 degrees, achromatic colours,
# near-neutrals -- that a plausible-looking implementation gets wrong.
SHARMA_PAIRS = [
    ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
    ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
    ((50, 2.8361, -74.0200), (50, 0, -82.7485), 3.4412),
    ((50, -1.3802, -84.2814), (50, 0, -82.7485), 1.0000),
    ((50, -1.1848, -84.8006), (50, 0, -82.7485), 1.0000),
    ((50, -0.9009, -85.5211), (50, 0, -82.7485), 1.0000),
    ((50, 0, 0), (50, -1, 2), 2.3669),
    ((50, -1, 2), (50, 0, 0), 2.3669),
    ((50, 2.49, -0.001), (50, -2.49, 0.0009), 7.1792),
    ((50, 2.49, -0.001), (50, -2.49, 0.0010), 7.1792),
    ((50, 2.49, -0.001), (50, -2.49, 0.0011), 7.2195),
    ((50, 2.49, -0.001), (50, -2.49, 0.0012), 7.2195),
    ((50, -0.001, 2.49), (50, 0.0009, -2.49), 4.8045),
    ((50, 2.5, 0), (73, 25, -18), 27.1492),
    ((50, 2.5, 0), (61, -5, 29), 22.8977),
    ((50, 2.5, 0), (56, -27, -3), 31.9030),
    ((50, 2.5, 0), (58, 24, 15), 19.4535),
    ((50, 2.5, 0), (50, 3.1736, 0.5854), 1.0000),
    ((50, 2.5, 0), (50, 3.2972, 0), 1.0000),
    ((50, 2.5, 0), (50, 1.8634, 0.5757), 1.0000),
    ((50, 2.5, 0), (50, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


class TestColourDifference:
    """The colour maths the extended palette is built and checked with."""

    @pytest.mark.parametrize('lab1, lab2, expected', SHARMA_PAIRS)
    def test_ciede2000_matches_published_test_data(self, lab1, lab2, expected):
        assert colors._ciede2000(lab1, lab2)[0] == pytest.approx(expected, abs=5e-5)

    def test_ciede2000_works_row_by_row(self):
        lab1 = np.array([p[0] for p in SHARMA_PAIRS], dtype=float)
        lab2 = np.array([p[1] for p in SHARMA_PAIRS], dtype=float)
        expected = [p[2] for p in SHARMA_PAIRS]
        assert colors._ciede2000(lab1, lab2) == pytest.approx(expected, abs=5e-5)

    def test_lab_of_known_colours(self):
        white, red, black = colors._to_lab(['#FFFFFF', '#FF0000', '#000000'])
        assert white == pytest.approx([100, 0, 0], abs=0.01)
        assert red == pytest.approx([53.24, 80.09, 67.20], abs=0.01)
        assert black == pytest.approx([0, 0, 0], abs=1e-9)


def _all_pairs(palette):
    lab = colors._to_lab(palette)
    return {(palette[i], palette[j]): float(colors._ciede2000(lab[i], lab[j])[0])
            for i in range(len(palette)) for j in range(i + 1, len(palette))}


class TestRegressionColoursRepeatAfterEight:
    """
    get_categorical(n) used to start the eight colours over for n > 8, so
    the ninth category came out in the first one's crimson. Found on real
    data: a bar chart of the ten most populous countries drew India and
    Russia in the same crimson, and China and DR Congo in the same gold.

    Up to 20 categories the palette now continues with DUBOIS_CATEGORICAL_20,
    where no two colours look more alike than the closest pair of the
    original eight; past that, each category still gets a colour of its own,
    with a warning once some of them look alike.
    """

    OLD = {1: ['#DC143C'], 2: ['#DC143C', '#D4AF37'], 3: ['#DC143C', '#D4AF37', '#000000'],
           4: ['#DC143C', '#D4AF37', '#00A550', '#000000']}

    @pytest.mark.parametrize('n', range(1, 9))
    def test_up_to_eight_nothing_changed(self, n):
        expected = self.OLD.get(n, colors.DUBOIS_CATEGORICAL_8[:n])
        assert colors.get_categorical(n) == expected

    def test_twenty_starts_with_the_original_eight(self):
        assert colors.DUBOIS_CATEGORICAL_20[:8] == colors.DUBOIS_CATEGORICAL_8

    @pytest.mark.parametrize('n', range(9, 21))
    def test_no_colour_repeats_up_to_twenty(self, n):
        palette = [c.lower() for c in colors.get_categorical(n)]
        assert len(palette) == n
        assert len(set(palette)) == n

    def test_no_two_of_the_twenty_look_more_alike_than_crimson_and_rose(self):
        pairs = _all_pairs(colors.DUBOIS_CATEGORICAL_20)
        closest = min(pairs, key=pairs.get)
        assert pairs[closest] >= 15.0, f"{closest} are only {pairs[closest]:.1f} apart"
        # ... and the closest pair is still the one from the original eight
        assert set(closest) == {'#DC143C', '#E75480'}

    def test_every_colour_stands_out_from_the_paper(self):
        from dubois_charts.charts._common import COLOR_CREAM
        assert colors._PAPER.lower() == COLOR_CREAM.lower()
        lab = colors._to_lab(colors.DUBOIS_CATEGORICAL_20)
        against_paper = colors._ciede2000(colors._to_lab([COLOR_CREAM])[0], lab)
        assert against_paper.min() >= 15.0

    def test_list_matches_the_procedure_that_chose_it(self):
        assert [c.lower() for c in colors.DUBOIS_CATEGORICAL_20] == colors._build_categorical_20()

    def test_past_twenty_each_category_still_gets_its_own_colour(self):
        with pytest.warns(UserWarning, match='look alike'):
            palette = colors.get_categorical(60)
        assert len(set(c.lower() for c in palette)) == 60

    def test_warns_only_once_colours_actually_look_alike(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            colors.get_categorical(20)
            colors.get_categorical(21)     # the 21st happens to clear the bar too
        with pytest.warns(UserWarning, match='look alike'):
            colors.get_categorical(22)

    def test_adding_a_category_never_recolours_the_others(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for n in range(9, 60):
                assert colors.get_categorical(n + 1)[:n] == colors.get_categorical(n)

    def test_repeats_with_a_warning_only_once_every_tone_is_used(self):
        available = len(colors.DUBOIS_CATEGORICAL_20) + len(colors._colors_after_20())
        with pytest.warns(UserWarning, match='repeat'):
            palette = colors.get_categorical(available + 5)
        assert len(palette) == available + 5
        assert len(set(c.lower() for c in palette[:available])) == available

    def test_theme_colour_cycle_has_all_twenty(self):
        from dubois_charts import themes
        cycle = [d['color'] for d in themes.DUBOIS_THEME['axes.prop_cycle']]
        assert cycle == colors.DUBOIS_CATEGORICAL_20


def _bar_colours(fig):
    bars = [p for p in fig.axes[0].patches if p.get_fill()]
    return [mcolors.to_hex(p.get_facecolor()) for p in bars]


class TestRegressionChartsGiveEachCategoryItsOwnColour:
    POPULATION = dict(
        categories=['India', 'China', 'United States', 'Indonesia', 'Pakistan', 'Nigeria',
                    'Brazil', 'Bangladesh', 'Russia', 'Congo, Dem. Rep.'],
        values=[1457.44, 1417.73, 346.37, 284.62, 274.07, 235.09, 212.42, 174.62, 144.43, 116.31],
    )

    def test_ten_most_populous_countries(self):
        from dubois_charts.charts.bar import bar_chart
        fig = bar_chart(**self.POPULATION)
        bar_colours = _bar_colours(fig)
        assert len(bar_colours) == 10
        assert len(set(bar_colours)) == 10
        plt.close(fig)

    def test_bar_chart_with_many_bars_does_not_warn(self):
        # Each bar is labelled with its category, so similar shades past
        # the twentieth can't be misread -- no warning needed.
        import warnings
        from dubois_charts.charts.bar import bar_chart
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = bar_chart(categories=[f'County {i}' for i in range(30)], values=list(range(1, 31)))
        assert len(set(_bar_colours(fig))) == 30
        plt.close(fig)

    def test_stacked_area_with_twelve_series(self):
        from dubois_charts.charts.area import stacked_area_chart
        fig = stacked_area_chart(x=[2000, 2010, 2020],
                                 series={f'Source {i}': [5 + i, 6 + i, 7 + i] for i in range(12)})
        # (skipping the invisible alpha=0 shapes the texture is clipped to)
        bands = [mcolors.to_hex(c.get_facecolor()[0]) for c in fig.axes[0].collections
                 if len(c.get_facecolor()) and c.get_facecolor()[0][3] > 0]
        assert len(bands) == 12
        assert len(set(bands)) == 12
        plt.close(fig)

    def test_pie_with_twelve_slices(self):
        from dubois_charts.charts.pie import pie_chart
        from matplotlib.patches import Wedge
        fig = pie_chart(segments={f'Slice {i}': 10 + i for i in range(12)})
        wedges = [mcolors.to_hex(p.get_facecolor()) for ax in fig.axes for p in ax.patches
                  if isinstance(p, Wedge)]
        assert len(set(wedges)) == 12
        plt.close(fig)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestRegressionSequentialSingleColour:
    """get_sequential(n=1) divided by zero (the spacing formula divides by
    n - 1). county_map_chart asks for one colour when every county has the
    same value, so it crashed too."""

    @pytest.mark.parametrize('name', ['crimson', 'gold', 'green'])
    def test_one_colour_is_the_middle_of_the_range(self, name):
        full = colors.get_sequential(name)
        assert colors.get_sequential(name, n=1) == [full[len(full) // 2]]



class TestColourBlindReaders:
    """
    The classic palette's crimson and green look alike to red-green
    colour-blind readers (about one man in twelve): 6.4 apart in CIEDE2000
    as a deuteranope sees them. There was no way to check a palette, and
    no palette made for them.
    """

    def test_grays_look_the_same_to_everyone(self):
        grays = ['#000000', '#808080', '#ffffff', '#3c3c3c']
        for kind in colors.COLORBLINDNESS:
            seen = colors.simulate_colorblindness(grays, kind)
            for a, b in zip(grays, seen):
                assert np.allclose(colors.hex_to_rgb(a), colors.hex_to_rgb(b), atol=2 / 255), kind

    def test_red_and_green_as_a_deuteranope_sees_them(self):
        # Machado, Oliveira & Fernandes (2009) at full severity.
        assert colors.simulate_colorblindness(['#DC143C', '#00A550'], 'deuteranopia') == \
            ['#8b7e35', '#968b56']
        with pytest.raises(ValueError, match='deuteranopia'):
            colors.simulate_colorblindness(['#DC143C'], 'red-green')

    def test_the_classic_palette_is_not_enough(self):
        assert colors.closest_pair_for_every_reader(colors.get_categorical(4)) < 7

    def test_colorblind_palette_is_rederived_exactly(self):
        assert colors._build_colorblind_8() == [c.lower() for c in colors.DUBOIS_COLORBLIND_8]

    @pytest.mark.parametrize('n', range(2, 9))
    def test_every_reader_tells_the_colours_apart(self, n):
        palette = colors.get_categorical(n, colorblind_safe=True)
        assert len(palette) == n
        assert colors.closest_pair_for_every_reader(palette) >= 15

    def test_past_eight_a_warning_says_so(self):
        with pytest.warns(UserWarning, match='past eight categories'):
            palette = colors.get_categorical(12, colorblind_safe=True)
        assert len(set(palette)) == 12

    def test_set_colorblind_safe_changes_every_chart(self):
        import dubois_charts as dc
        from matplotlib.colors import to_hex
        try:
            dc.set_colorblind_safe()
            fig = dc.pie_chart({'A': 4, 'B': 3, 'C': 2, 'D': 1})
            wedges = [p for p in fig.axes[0].patches if hasattr(p, 'theta1')]
            assert {to_hex(w.get_facecolor()) for w in wedges} == \
                {c.lower() for c in colors.DUBOIS_COLORBLIND_8[:4]}
            assert colors.get_diverging(7)[-1] == colors.DUBOIS_DIVERGING_COLORBLIND[-1]
        finally:
            dc.set_colorblind_safe(False)
        assert colors.get_categorical(4) == colors.DUBOIS_CLASSIC_4

    def test_diverging_sides_stay_apart(self):
        # Each colour and its mirror on the other side, for every reader.
        def apart(a, b):
            return min(float(colors._ciede2000(v[0], v[1:2])[0]) for v in colors._views([a, b]))

        div = colors.get_diverging(7, colorblind_safe=True)
        assert [apart(div[i], div[-1 - i]) >= low for i, low in enumerate((20, 15, 10))] == [True] * 3
        classic = colors.get_diverging(7, colorblind_safe=False)
        assert apart(classic[0], classic[-1]) < 20     # crimson and green, as a deuteranope sees them


class TestRegressionMapClassesForEveryReader:
    """
    get_sequential() took evenly spaced entries of hand-picked lists whose
    steps weren't even: two of a map's seven gold classes were 4.2 apart
    in CIEDE2000, hard to tell apart for anyone, and two of the seven
    crimson ones 3.8 apart as a tritanope sees them. The palettes now run
    at evenly spaced perceived lightness.
    """

    @pytest.mark.parametrize('name', ['crimson', 'gold', 'green'])
    @pytest.mark.parametrize('n', [3, 4, 5, 6, 7])
    def test_neighbouring_classes_are_clearly_different(self, name, n):
        seq = colors.get_sequential(name, n)
        views = colors._views(seq)
        closest = min(float(colors._ciede2000(v[i], v[i + 1:i + 2])[0])
                      for v in views for i in range(n - 1))
        assert closest >= 7

    @pytest.mark.parametrize('name', ['crimson', 'gold', 'green'])
    def test_lists_are_rederived_exactly(self, name):
        assert colors._build_sequential(name) == colors.get_sequential(name)

    @pytest.mark.parametrize('name', ['crimson', 'gold', 'green'])
    def test_light_to_dark(self, name):
        lightness = colors._to_lab(colors.get_sequential(name, 7))[:, 0]
        assert np.all(np.diff(lightness) < 0)

    def test_no_data_is_distinct_from_every_class_for_every_reader(self):
        from dubois_charts.charts.choropleth import MISSING_COLOR
        for name in ('crimson', 'gold', 'green'):
            for n in range(2, 9):
                seq = colors.get_sequential(name, n)
                for view in colors._views(seq + [MISSING_COLOR]):
                    assert float(colors._ciede2000(view[-1], view[:-1]).min()) >= 12, (name, n)
