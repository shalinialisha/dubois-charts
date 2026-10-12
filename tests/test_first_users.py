"""
Before the first release, two people who had never seen the package used
it from scratch: one as a new user, with data of their own and the
mistakes people make; one checking every claim the documentation makes
against the code. These are the problems they found, each checked here
so it stays fixed.
"""

import warnings

import numpy as np
import pandas as pd
import pytest
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import dubois_charts as dc
from dubois_charts import text_utils as tu
from dubois_charts.charts import _common as common


def _texts(fig):
    return [t.get_text() for ax in fig.axes for t in ax.texts if t.get_text().strip()]


def _renderer(fig):
    fig.canvas.draw()
    return fig.canvas.get_renderer()


# ---------------------------------------------------------------------------
# pandas values are matched to their categories by index
# ---------------------------------------------------------------------------

class TestRegressionPandasValuesFollowTheirIndex:
    """
    The bar, butterfly, area and spiral charts took a pandas Series's
    values in order, ignoring its index. A pivot table's rows come sorted
    ('0-4', '10-14', '5-9'), so a population pyramid put the 10-14 figures
    on the 5-9 row, with nothing to show anything was wrong.
    """

    def test_a_pivot_table_in_a_butterfly_chart(self):
        rows = pd.DataFrame({'age': ['0-4', '5-9', '10-14'] * 2, 'sex': ['M'] * 3 + ['F'] * 3,
                             'pop': [100, 200, 300, 101, 201, 301]})
        by = rows.pivot_table(index='age', columns='sex', values='pop')
        assert list(by.index) == ['0-4', '10-14', '5-9']          # sorted as text
        fig = dc.butterfly_chart(['0-4', '5-9', '10-14'], by['M'], by['F'])
        assert _texts(fig)[:6] == ['100', '200', '300', '101', '201', '301']

    def test_a_series_in_another_order_in_a_bar_chart(self):
        s = pd.Series({'Atlanta': 4.1, 'Savannah': 2.6, 'Macon': 0.8})
        fig = dc.bar_chart(['Atlanta', 'Macon', 'Savannah'], s)
        assert _texts(fig) == ['4.1', 'Atlanta', '0.8', 'Macon', '2.6', 'Savannah']

    def test_dataframe_rows_in_another_order_in_a_grouped_bar_chart(self):
        df = pd.DataFrame({'2010': [10, 20, 30], '2020': [11, 21, 31]}, index=['Ohio', 'Iowa', 'Utah'])
        fig = dc.bar_chart(['Utah', 'Ohio', 'Iowa'], df)
        assert _texts(fig) == ['30', '31', 'Utah', '10', '11', 'Ohio', '20', '21', 'Iowa']

    def test_dataframe_rows_in_another_order_in_an_area_chart(self):
        d = pd.DataFrame({'a': [1, 2, 3], 'b': [10, 20, 30]}, index=[2022, 2020, 2021])
        fig = dc.stacked_area_chart([2020, 2021, 2022], d, show_band_labels=False)
        assert [t for t in _texts(fig) if t in ('10', '20', '30')] == ['20', '30', '10']

    def test_years_as_keys_in_a_spiral_chart(self):
        # pandas 3 makes a RangeIndex of evenly spaced whole numbers: these
        # years are labels, not positions.
        v = pd.Series({1990: 5, 2000: 9, 2010: 14})
        fig = dc.spiral_chart([2010, 2000, 1990], v)
        assert sorted(_texts(fig)) == ['1990  5', '2000  9', '2010  14']

    def test_default_index_and_row_numbers_are_positions(self):
        filtered = pd.DataFrame({'v': [5, 6, 7, 8]}).iloc[1:]['v']     # index 1, 2, 3
        assert _texts(dc.bar_chart(['x', 'y', 'z'], filtered)) == ['6', 'x', '7', 'y', '8', 'z']
        plain = pd.Series([1, 2, 3])
        assert _texts(dc.bar_chart(['x', 'y', 'z'], plain)) == ['1', 'x', '2', 'y', '3', 'z']

    def test_an_index_naming_only_some_categories_is_an_error(self):
        s = pd.Series({'Atlanta': 1, 'Macon': 2, 'Augusta': 3})
        with pytest.raises(ValueError, match=r"no value for 'Savannah'; values for 'Augusta'"):
            dc.bar_chart(['Atlanta', 'Macon', 'Savannah'], s)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _bars(fig, colours):
    return [p for p in fig.axes[0].patches if isinstance(p, Rectangle) and p.get_fill()
            and mpl.colors.to_hex(p.get_facecolor()) in colours]


class TestRegressionGroupedBarsKeepTheirThickness:
    """
    The gap between grouped bars was a fixed share of the row, most of
    each bar's room from four series on: five series of bars were a pixel
    or two thick, and six or more drew upside down.
    """

    @pytest.mark.parametrize('n_series', [2, 3, 4, 5, 6, 7, 10])
    def test_each_bar_fills_most_of_its_room(self, n_series):
        series = {f'S{k}': [3 + k, 5, 2] for k in range(n_series)}
        fig = dc.bar_chart(['A', 'B', 'C'], series)
        colours = {mpl.colors.to_hex(c) for c in dc.get_categorical(n_series)}
        bars = _bars(fig, colours)
        assert len(bars) == 3 * n_series
        room = (1 - 2 * 0.16) / n_series        # each bar's share of its row
        assert all(bar.get_height() >= 0.6 * room for bar in bars)      # and none upside down


class TestRegressionLegendsStayOnTheFigure:
    """
    Legends had a fixed four columns and a fixed row's room: long names ran
    off both sides of the figure, a second row sat on top of the chart,
    and matplotlib's column-by-column filling put the names out of order.
    """

    LONG = ['Accessories and spare parts', 'Extended warranties', 'Gift cards and vouchers',
            'Refurbished devices', 'Licensing income']

    def _check(self, fig, names):
        renderer = _renderer(fig)
        legend = fig.legends[0]
        box = legend.get_window_extent(renderer)
        assert box.x0 >= -0.5 and box.x1 <= fig.bbox.width + 0.5 and box.y0 >= -0.5
        texts = legend.get_texts()
        text_boxes = [t.get_window_extent(renderer) for t in texts]
        chart_bottom = min(ax.get_window_extent(renderer).y0 for ax in fig.axes)
        assert max(b.y1 for b in text_boxes) <= chart_bottom + 0.5
        # Read across each row, then down. (A row's names are level to
        # within a pixel or so, not exactly: matplotlib 3.11 rounds them.)
        rows = []
        for t, b in sorted(zip(texts, text_boxes), key=lambda tb: -tb[1].y1):
            if rows and rows[-1][0] - b.y1 < b.height / 2:
                rows[-1][1].append((b.x0, t.get_text()))
            else:
                rows.append((b.y1, [(b.x0, t.get_text())]))
        reading = [name for _, row in rows for _, name in sorted(row)]
        assert reading == names

    def test_grouped_bars_with_long_series_names(self):
        fig = dc.bar_chart(['North', 'South'], {n: [1 + k, 2 + k] for k, n in enumerate(self.LONG)})
        self._check(fig, self.LONG)

    def test_six_series_read_in_order(self):
        years = [str(y) for y in range(2019, 2025)]
        fig = dc.bar_chart(['A', 'B'], {y: [1, 2] for y in years})
        self._check(fig, years)

    def test_area_chart_names_too_thin_for_their_bands(self):
        names = ['Main product line'] + self.LONG
        series = {name: [90, 88, 85] if k == 0 else [1.5, 2, 2.5] for k, name in enumerate(names)}
        fig = dc.stacked_area_chart([2021, 2022, 2023], series)
        self._check(fig, self.LONG)

    @pytest.mark.parametrize('chart', ['bar', 'area'])
    def test_a_legend_too_big_for_a_small_figure_overlaps_with_a_warning(self, chart):
        # Not a crash: given all the room it needed, the legend left the
        # chart none ("bottom cannot be >= top", or an IndexError).
        names = [f'A rather long series name number {i}' for i in range(12)]
        with pytest.warns(UserWarning, match='needs more room than the figure has'):
            if chart == 'bar':
                dc.bar_chart(['x', 'y'], {n: [1, 2] for n in names}, figsize=(4, 2),
                             show_value_labels=False)
            else:
                dc.stacked_area_chart([1, 2, 3], {n: [1, 2, 3] for n in names}, figsize=(4, 2))

    def test_snake_names_too_long_for_their_segments(self):
        names = ['Rent'] + self.LONG
        fig = dc.snake_chart(dict(zip(names, [80, 3, 3, 3, 3, 3])), n_rows=3)
        on_the_snake = ' '.join(t.get_text() for t in fig.axes[0].texts)
        listed = [n for n in self.LONG if n.split()[0] not in on_the_snake]
        assert len(listed) >= 2
        # Listed with their values: named only in the legend, they had no number anywhere.
        self._check(fig, [f'{n}  3' for n in listed])


class TestRegressionNamesKeepTheirSizeBesideSlivers:
    """
    Every name in an area chart's bands, or a snake's segments, shares one
    size; when most names couldn't fit at any size, that size dropped to
    the smallest, so a band filling most of the chart was named in 8pt
    type because of thin bands that were never going to hold their names.
    """

    def test_area_chart(self):
        series = {'Main product line': [90, 88, 85, 84, 80],
                  'Accessories and spare parts': [2, 2, 3, 3, 4],
                  'Extended warranties': [2, 2.5, 2.5, 2, 2.5], 'Gift cards': [1.5, 1.5, 2, 2, 2]}
        fig = dc.stacked_area_chart([2019, 2020, 2021, 2022, 2023], series)
        main = [t for t in fig.axes[0].texts if t.get_text() == 'MAIN PRODUCT LINE']
        assert main and main[0].get_fontsize() >= 12

    def test_snake_chart(self):
        fig = dc.snake_chart({'Water': 71.0, 'Land': 28.9, 'Freshwater lakes and rivers': 0.08,
                              'Glaciers': 0.02})
        named = {t.get_text().split()[0]: t.get_fontsize() for t in fig.axes[0].texts
                 if t.get_text().startswith(('Water', 'Land'))}
        assert named and min(named.values()) >= 12


class TestRegressionSnakeScaleCanBeRead:
    """
    The marks at the ends of a snake's rows -- its only scale -- were drawn
    inside the row, in dark ink over whatever segment was there: "3,500 €"
    on navy and "2,625 €" on black couldn't be read. They go under the
    rows now, on the background.
    """

    def test_scale_marks_are_off_the_segments(self):
        budget = {'Rent': 1150, 'Food': 620, 'Utilities': 260, 'Transport': 98, 'Childcare': 310,
                  'Insurance': 145, 'Phone': 45, 'Other': 152, 'Clothes': 90, 'Leisure': 210,
                  'Savings': 400, 'Interest': 20}
        fig = dc.snake_chart(budget, n_rows=4, value_format='{:,.0f} €',
                             colors=['#000080', '#000000'] * 6)
        renderer = _renderer(fig)
        ax = fig.axes[0]
        pieces = [p.get_window_extent(renderer) for p in ax.patches if p.get_fill()]
        ends = ax.get_xlim()
        marks = [t for t in ax.texts if t.get_position()[0] in ends]
        assert len(marks) == 8
        for mark in marks:
            box = mark.get_window_extent(renderer)
            for piece in pieces:
                assert not (box.x0 < piece.x1 - 1 and box.x1 > piece.x0 + 1
                            and box.y0 < piece.y1 - 1 and box.y1 > piece.y0 + 1), mark.get_text()

    def test_a_number_keeps_its_unit_on_its_line(self):
        fig = plt.figure(dpi=150)
        lines = tu.wrap_text_to_width(fig, 'Sonstiges 152\u00a0€',
                                      tu.measure_text_px(fig, 'Sonstiges 152', 13, 'monospace', 'bold')[0] + 2,
                                      13, 'monospace', 'bold')
        assert lines == ['Sonstiges', '152\u00a0€']


def _crosses(p, q, curve):
    """Does the segment p-q cross the polyline `curve` (N x 2) away from p?"""
    a, b = curve[:-1], curve[1:]
    d, e = q - p, b - a
    denom = d[0] * e[:, 1] - d[1] * e[:, 0]
    w = a - p
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / denom
        u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / denom
    hit = (denom != 0) & (t > 0.02) & (t < 1) & (u >= 0) & (u <= 1)
    return bool(hit.any())


class TestRegressionSpiralLabelsBesideTheirOwnLoop:
    """
    A label pushed out from a point on an inner loop could land past the
    next loop out -- clear of the line, but reading as that loop's: on a
    chart of carbon dioxide at Mauna Loa, 1960's and 1975's values sat by
    the outer loop. A label without a leader line now has no loop between
    it and its point.
    """

    def test_carbon_dioxide(self):
        years = [1960, 1965, 1970, 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024]
        ppm = [316.9, 320.0, 325.7, 331.1, 338.8, 346.4, 354.4, 360.8, 369.7, 379.8, 389.9,
               401.0, 414.2, 424.6]
        fig = dc.spiral_chart(years, ppm)
        ax = fig.axes[0]
        curve = np.column_stack(ax.lines[0].get_data())
        points = [np.array(c.center) for c in ax.patches if isinstance(c, plt.Circle)]
        leaders = [np.column_stack(line.get_data())[0] for line in ax.lines[1:]]
        renderer = _renderer(fig)
        to_data = ax.transData.inverted()
        checked = 0
        for text in ax.texts:
            i = years.index(int(text.get_text().split()[0]))
            point = points[i]
            if any(np.allclose(point, start) for start in leaders):
                continue
            (x0, y0), (x1, y1) = to_data.transform(text.get_window_extent(renderer).get_points())
            nearest = np.array([np.clip(point[0], x0, x1), np.clip(point[1], y0, y1)])
            assert not _crosses(point, nearest, curve), text.get_text()
            checked += 1
        assert checked >= 3


class TestRegressionNumbersShowTheDigitsTheyHave:
    """
    Data needing more than two decimals printed with three significant
    figures of the smallest value, whatever the data had: 0.012 as
    "0.01200". And a butterfly chart's sides shared one format, so 0.012
    on one side printed 1,250,000 on the other as "1,250,000.0000".
    """

    @pytest.mark.parametrize('values, expected', [
        ([0.012, 0.034, 0.005], '{:,.3f}'),
        ([0.0018, 0.0017, 0.0054, 0.0121, 0.0723], '{:,.4f}'),
        ([33.333333, 66.666667], '{:,.2f}'),
        ([12.6, 6.48], '{:,.2f}'),
        ([1250000, 980000], '{:,.0f}'),
        ([0.123456789, 12.3456789], '{:,.3f}'),
    ])
    def test_default_format(self, values, expected):
        assert common.default_value_format(values) == expected

    def test_bar_labels(self):
        assert _texts(dc.bar_chart(['A', 'B', 'C'], [0.012, 0.034, 0.005]))[::2] == [
            '0.012', '0.034', '0.005']

    def test_butterfly_sides_of_very_different_sizes(self):
        with pytest.warns(UserWarning, match='too short to see'):
            fig = dc.butterfly_chart(['Exports', 'Imports', 'Re-exports', 'Services', 'Transfers'],
                                     [1250000, 980000, 45000, 310000, 1200],
                                     [12.5, 9.8, 0.45, 3.1, 0.012])
        texts = _texts(fig)
        assert '1,250,000' in texts and '0.012' in texts


# ---------------------------------------------------------------------------
# Maps: keys that name the wrong place, or none
# ---------------------------------------------------------------------------

class TestRegressionMapKeysThatMatchTheWrongPlaceOrNone:
    """
    Map data that matched nothing drew a blank map; two keys for one place
    kept the last quietly; Virginia's "Richmond" coloured the rural county,
    not the city, without a word; Florida's county names, with no `state`,
    drew Georgia's counties of the same names; and Connecticut's current
    county codes matched nothing, with only the usual warning.
    """

    def test_no_data_is_an_error(self):
        with pytest.raises(ValueError, match='empty'):
            dc.county_map_chart({})
        with pytest.raises(ValueError, match='empty'):
            dc.state_map_chart({})

    def test_data_that_match_nothing_are_an_error(self):
        with pytest.raises(ValueError, match=r"none of the keys .*'Fultn' -- Fulton\?"):
            dc.county_map_chart({'Nowhere': 1, 'Fultn': 2}, state='GA')
        with pytest.raises(ValueError, match='none of the keys'):
            dc.state_map_chart({'Atlantis': 1})

    def test_two_keys_for_one_place_are_an_error(self):
        with pytest.raises(ValueError, match="two values for New York: 'NY' and 'New York'"):
            dc.state_map_chart({'NY': 5, 'New York': 9})
        with pytest.raises(ValueError, match="two values for Fulton"):
            dc.county_map_chart({'Fulton': 5, '13121': 9}, state='GA')

    def test_a_name_a_county_shares_with_a_city_says_which_it_took(self):
        with pytest.warns(UserWarning, match="'Richmond' to be Richmond County, not Richmond City"):
            dc.county_map_chart({'Richmond': 3.1, 'Roanoke': 2.8, 'Arlington': 1.9}, state='VA')
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            dc.county_map_chart({'Richmond city': 3.1, 'Roanoke County': 2.8}, state='VA')

    def test_another_states_names_draw_that_state(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = dc.county_map_chart({'Cuyahoga': 4.9, 'Franklin': 3.8, 'Hamilton': 4.1})
        assert {'Cuyahoga', 'Franklin', 'Hamilton'} <= set(_texts(fig))

    def test_names_several_states_have_say_so(self):
        with pytest.warns(UserWarning, match='counties in 5 states: Arkansas, Florida, Georgia'):
            dc.county_map_chart({'Polk': 5.1, 'Lee': 4.3, 'Marion': 4.8})
        with pytest.raises(ValueError, match="aren't all Georgia's.*3 states: California, "
                                             "Florida, Indiana"):
            dc.county_map_chart({'Orange': 1.0, 'Lake': 2.0})

    def test_connecticuts_planning_regions_are_explained(self):
        with pytest.raises(ValueError, match="Connecticut's nine planning regions"):
            dc.county_map_chart({'09110': 1.0, '09120': 2.0})

    def test_a_table_is_an_error_not_its_column_names(self):
        df = pd.DataFrame({'rate': [1.0, 2.0]}, index=['Fulton', 'Bibb'])
        with pytest.raises(TypeError, match=r"df\['rate'\]"):
            dc.county_map_chart(df)
        with pytest.raises(TypeError, match='one column'):
            dc.pie_chart(df)


# ---------------------------------------------------------------------------
# Mistakes, and what the package says about them
# ---------------------------------------------------------------------------

class TestRegressionErrorsSayHowToFixThem:

    def test_a_dict_of_single_values_in_a_bar_chart(self):
        with pytest.raises(TypeError, match=r"bar_chart\(list\(d\), list\(d.values\(\)\)\)"):
            dc.bar_chart(['A', 'B'], {'A': 1, 'B': 2})

    def test_a_fraction_of_a_row(self):
        with pytest.raises(ValueError, match='whole number of rows'):
            dc.snake_chart({'a': 1, 'b': 2}, n_rows=2.5)

    def test_negative_values_are_named(self):
        with pytest.raises(ValueError, match=r"'Trade' \(-3\)"):
            dc.butterfly_chart(['Farm', 'Trade'], [5, -3], [4, 2])
        with pytest.raises(ValueError, match=r"Segment 'b' \(-1\)"):
            dc.pie_chart({'a': 2, 'b': -1})

    def test_a_font_that_isnt_installed(self, caplog):
        with pytest.warns(UserWarning, match="'No Such Font' is not an installed font") as caught:
            fig = dc.bar_chart(['a', 'b'], [1, 2], font='No Such Font')
            fig.canvas.draw()
        assert len([w for w in caught if 'installed font' in str(w.message)]) == 1
        assert not [r for r in caplog.records if 'No Such Font' in r.getMessage()]


class TestRegressionNothingPrinted:
    """Charts printed "Saved: ..." whenever they saved; a library shouldn't print."""

    @pytest.mark.parametrize('chart', ['bar', 'butterfly', 'area', 'spiral', 'snake', 'pie',
                                       'county', 'state'])
    def test_saving_prints_nothing(self, chart, tmp_path, capsys):
        path = str(tmp_path / 'chart.png')
        draw = {
            'bar': lambda: dc.bar_chart(['a', 'b'], [1, 2], save_path=path),
            'butterfly': lambda: dc.butterfly_chart(['a', 'b'], [1, 2], [2, 1], save_path=path),
            'area': lambda: dc.stacked_area_chart([1, 2], {'a': [1, 2]}, save_path=path),
            'spiral': lambda: dc.spiral_chart([1, 2, 3], [1, 2, 3], save_path=path),
            'snake': lambda: dc.snake_chart({'a': 1, 'b': 2}, save_path=path),
            'pie': lambda: dc.pie_chart({'a': 1, 'b': 2}, save_path=path),
            'county': lambda: dc.county_map_chart({'Fulton': 1, 'Bibb': 2}, state='GA',
                                                  save_path=path),
            'state': lambda: dc.state_map_chart({'GA': 1, 'TX': 2}, save_path=path),
        }[chart]
        draw()
        assert capsys.readouterr().out == ''

    def test_show_palette_returns_its_figure(self, capsys, tmp_path):
        fig = dc.colors.show_palette('primary', save_path=str(tmp_path / 'p.png'))
        assert isinstance(fig, plt.Figure)
        assert capsys.readouterr().out == ''


# ---------------------------------------------------------------------------
# Themes put back only what they changed
# ---------------------------------------------------------------------------

class TestRegressionThemesPutBackOnlyWhatTheyChanged:
    """
    reset_theme() put back every setting as it was before the first
    set_theme(), undoing settings of the user's own made in between, and
    -- like the theme blocks -- switching off the interactive mode
    matplotlib turns on at a notebook's first figure, after which the
    notebook showed no more figures.
    """

    @pytest.fixture(autouse=True)
    def _restore(self):
        with mpl.rc_context():
            yield
        dc.themes.reset_theme()

    def test_a_setting_the_theme_never_touches_survives_reset(self):
        dc.set_theme()
        mpl.rcParams['image.cmap'] = 'magma'
        dc.set_theme('modern')
        dc.reset_theme()
        assert mpl.rcParams['image.cmap'] == 'magma'

    def test_reset_puts_back_what_the_theme_changed(self):
        before = mpl.rcParams['axes.facecolor']
        dc.set_theme()
        dc.set_theme('minimal', 'talk')
        dc.reset_theme()
        assert mpl.rcParams['axes.facecolor'] == before

    def test_interactive_mode_survives_reset(self):
        mpl.rcParams['interactive'] = False
        dc.set_theme()
        mpl.rcParams['interactive'] = True       # what a notebook's first figure does
        dc.reset_theme()
        assert mpl.rcParams['interactive']

    @pytest.mark.parametrize('block', ['dubois_style', 'DuBoisStyle'])
    def test_interactive_mode_survives_a_theme_block(self, block):
        mpl.rcParams['interactive'] = False
        with getattr(dc.themes, block)():
            assert mpl.rcParams['axes.facecolor'] == '#ded7c9'
            mpl.rcParams['interactive'] = True
        assert mpl.rcParams['interactive']
        assert mpl.rcParams['axes.facecolor'] != '#ded7c9' or plt.rcParamsDefault['axes.facecolor'] == '#ded7c9'
