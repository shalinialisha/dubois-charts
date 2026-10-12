"""
Before the release, every chart was drawn from real public data, read the
way a user would read it -- with pandas, reshaped as little as possible:
the data for Du Bois's own plates (the #DuBoisChallenge files), census
population by age, unemployment by industry and by county, election
results, COVID-19 deaths by state, energy, temperature and births. Every
value drawn matched its source; these are the things that went wrong,
each checked here with a few rows shaped like the file that showed it.
"""

import datetime
import warnings

import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt

import dubois_charts as dc
from dubois_charts.charts import _common as common
from dubois_charts.charts import choropleth


def _texts(fig):
    return [t.get_text() for ax in fig.axes for t in ax.texts if t.get_text().strip()]


def _renderer(fig):
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _no_warnings(draw):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig = draw()
    return fig, [str(w.message) for w in caught]


# ---------------------------------------------------------------------------
# Rows without a name, and rows given twice
# ---------------------------------------------------------------------------

class TestRegressionRowsWithoutAName:
    """
    Plate 55's file ends in a total whose name cell is empty; pandas reads
    it as NaN, and bar_chart drew a fourth bar called "nan" -- the total,
    three times the others, under a title about three states. A row with
    no name is now an error that says which row it is -- but on a map, where
    it has no place to go, it's left out with a warning.
    """

    STATES = pd.Series(['Virginia', 'North Carolina', 'Georgia', np.nan])
    VALUES = [13933998, 8018466, 12941230, 34893684]

    def test_bar_chart(self):
        with pytest.raises(ValueError, match=r"name missing .* position 3 \(after 'Georgia'\)"):
            dc.bar_chart(self.STATES, self.VALUES)

    def test_butterfly_chart(self):
        with pytest.raises(ValueError, match='name missing'):
            dc.butterfly_chart(self.STATES, [1, 2, 3, 4], [4, 3, 2, 1])

    def test_spiral_chart(self):
        with pytest.raises(ValueError, match='name missing'):
            dc.spiral_chart([1870, 1880, None, 1900], [1, 2, 3, 4])

    def test_pie_and_snake(self):
        segments = pd.Series(self.VALUES, index=self.STATES)
        for chart in (dc.pie_chart, dc.snake_chart):
            with pytest.raises(ValueError, match='name missing'):
                chart(segments)

    def test_series_of_an_area_or_bar_chart(self):
        with pytest.raises(ValueError, match='name missing'):
            dc.stacked_area_chart([1, 2], {'A': [1, 2], np.nan: [3, 4]})
        with pytest.raises(ValueError, match='name missing'):
            dc.bar_chart(['x', 'y'], {'A': [1, 2], None: [3, 4]})

    def test_map_keys(self):
        # On a map, a value with no place is left out with a warning, as a
        # key naming no place is: see TestRegressionPlacesWithNoKey, below.
        with pytest.warns(UserWarning, match='1 value in `data` has no state'):
            fig = dc.state_map_chart(pd.Series([1.0, 2.0], index=['Georgia', np.nan]))
        plt.close(fig)


class TestRegressionRowsGivenTwice:
    """
    Plate 22's file has the year 1880 twice; bar_chart drew two bars called
    1880, in different colours, and said nothing.
    """

    def test_bar_chart_warns(self):
        with pytest.warns(UserWarning, match=r"'1880' appears more than once"):
            fig = dc.bar_chart([1875, 1880, 1880, 1885], [5393885, 5764293, 5764293, 8153390])
        plt.close(fig)

    def test_butterfly_chart_warns(self):
        with pytest.warns(UserWarning, match='more than once'):
            fig = dc.butterfly_chart(['A', 'B', 'A'], [1, 2, 3], [3, 2, 1])
        plt.close(fig)

    def test_names_given_once_draw_without_a_warning(self):
        fig, caught = _no_warnings(lambda: dc.bar_chart([1875, 1880, 1885], [1, 2, 3]))
        assert not any('more than once' in w for w in caught)
        plt.close(fig)

    def test_a_spiral_may_come_back_to_a_name(self):
        # Month names repeat year after year round a spiral.
        months = ['Jan', 'Apr', 'Jul', 'Oct'] * 2
        fig, caught = _no_warnings(lambda: dc.spiral_chart(months, [3, 5, 8, 4, 3, 6, 9, 4]))
        assert not any('more than once' in w for w in caught)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

class TestRegressionDatesStoredAsMidnightSomewhere:
    """
    vega's unemployment-by-industry file stores each month as midnight in
    California, written in UTC: "2000-01-01T08:00:00Z", and 07:00 in
    summer. The x labels read "2000-01-01 08:00" and "2003-05-01 07:00".
    """

    def _monthly_utc(self, n=24):
        dates = pd.date_range('2000-01-01', periods=n, freq='MS', tz='America/Los_Angeles')
        return list(dates.tz_convert('UTC'))

    def test_labels_are_months(self):
        labels = common.category_labels(self._monthly_utc())
        assert labels[:3] == ['Jan 2000', 'Feb 2000', 'Mar 2000']
        assert labels[6] == 'Jul 2000'                   # 07:00, in daylight saving

    def test_midnight_east_of_greenwich_is_the_next_day(self):
        # Midnight in Tokyo is 15:00 the day before in UTC.
        dates = [datetime.datetime(2011, 12, 31, 15), datetime.datetime(2012, 1, 31, 15),
                 datetime.datetime(2012, 2, 29, 15)]
        assert common.category_labels(dates) == ['Jan 2012', 'Feb 2012', 'Mar 2012']

    def test_real_times_of_day_are_kept(self):
        dates = [datetime.datetime(2024, 3, 1, h) for h in (9, 13, 17)]
        assert common.category_labels(dates) == ['2024-03-01 09:00', '2024-03-01 13:00',
                                                 '2024-03-01 17:00']

    def test_pandas_periods_read_like_dates(self):
        months = pd.period_range('2012-01', periods=3, freq='M')
        assert common.category_labels(list(months)) == ['Jan 2012', 'Feb 2012', 'Mar 2012']

    def test_area_chart_x_labels(self):
        x = self._monthly_utc(122)
        fig = dc.stacked_area_chart(x, {'A': np.linspace(400, 900, 122), 'B': np.linspace(300, 200, 122)})
        top = [t.get_text() for t in fig.axes[0].texts if t.get_va() == 'bottom']
        assert top and all(':' not in t for t in top), top
        plt.close(fig)


class TestRegressionXLabelsAtRoundValues:
    """
    Labels thinned to every k-th point from the first: monthly figures
    read "Jan 2000, May 2003, Sep 2006", and years from 1874 every third,
    "1874, 1877, 1880". They now fall on round values -- each January,
    every fifth or tenth year -- a line's height apart at least.
    """

    def _x_labels(self, fig):
        return [t.get_text() for t in fig.axes[0].texts if t.get_va() == 'bottom' and t.get_text()]

    def test_months_are_labelled_in_january(self):
        x = pd.date_range('2000-01-01', periods=122, freq='MS')
        fig = dc.stacked_area_chart(x, {'A': np.linspace(400, 900, 122)})
        labels = self._x_labels(fig)
        assert len(labels) >= 4
        assert all(t.startswith('Jan ') for t in labels[:-1]), labels      # the last is the last point
        assert labels[-1] == 'Feb 2010'
        plt.close(fig)

    def test_years_are_round(self):
        years = list(range(1873, 1900))
        fig = dc.stacked_area_chart(years, {'A': np.linspace(1, 2, len(years))}, figsize=(7, 7))
        labels = [int(t) for t in self._x_labels(fig)]
        assert labels[0] == 1873 and labels[-1] == 1899
        inner = labels[1:-1]
        step = inner[1] - inner[0]
        assert step in (2, 5, 10) and all(y % step == 0 for y in inner), labels
        plt.close(fig)

    def test_labels_are_a_line_apart(self):
        # US electricity by source, 2000-2023: all 24 years, 10 pixels apart.
        x = list(range(2000, 2024))
        fig = dc.stacked_area_chart(x, {'A': np.linspace(1, 2, 24), 'B': np.linspace(2, 1, 24)})
        renderer = _renderer(fig)
        boxes = sorted((t.get_window_extent(renderer) for t in fig.axes[0].texts
                        if t.get_va() == 'bottom' and t.get_text()), key=lambda b: b.x0)
        for a, b in zip(boxes, boxes[1:]):
            assert b.x0 - a.x1 >= 0.95 * a.height, (a, b)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------

class TestRegressionHalvesRoundUp:
    """
    Python rounds halves to the nearest even digit: Plate 27's 4.5% read
    "4%" on the pie and "4.5%" on the butterfly chart of the same data, and
    Plate 19's 1,102,866.5 acres read "1,102,866". Labels round halves up,
    as people do.
    """

    @pytest.mark.parametrize('fmt, value, expected', [
        ('{:.0f}', 4.5, '5'),
        ('{:,.0f}', 1102866.5, '1,102,867'),
        ('{:.0f}%', 2.5, '3%'),
        ('{:+.2f}', -2.675, '-2.68'),          # as written, not the binary fraction just below
        ('{:.0%}', 0.125, '13%'),
        ('${:,.2f}', 1234.565, '$1,234.57'),
        ('{:.0f}', 4.4, '4'),
        ('{:g}', 1234567.0, '1.23457e+06'),    # other formats are Python's own
        ('{:.2e}', 4.105e-07, '4.10e-07'),
        ('{:,}', 1234.5, '1,234.5'),
    ])
    def test_format_value(self, fmt, value, expected):
        assert common.format_value(fmt, value) == expected

    def test_numpy_numbers(self):
        assert common.format_value('{:.0f}', np.float64(0.5)) == '1'
        assert common.format_value('{:,.0f}', np.int64(1234)) == '1,234'

    def test_on_a_chart(self):
        fig = dc.bar_chart(['a', 'b'], [4.5, 1102866.5], value_format='{:,.0f}')
        assert {'5', '1,102,867'} <= set(_texts(fig))
        plt.close(fig)


# ---------------------------------------------------------------------------
# Pies of published percentages
# ---------------------------------------------------------------------------

class TestRegressionPublishedPercentagesKeepTheirValues:
    """
    Plate 60's percentages add up to 100.5, as rounded percentages do; the
    pie labelled each with its share of 100.5, so the published 13.4%
    read "13.3%" -- four of the five labels disagreed with the source.
    """

    CRIME = {'Government': 0.7, 'Society': 13.4, 'Persons': 27.6, 'Property': 48.2,
             'Miscellaneous': 10.6}

    def test_labels_are_the_values(self):
        fig = dc.pie_chart(self.CRIME, value_format='{:.1f}%')
        text = ' '.join(_texts(fig))
        for value in ('13.4%', '27.6%', '48.2%', '10.6%'):
            assert value in text, (value, text)
        plt.close(fig)

    def test_other_totals_are_shares(self):
        fig = dc.pie_chart({'A': 30, 'B': 10})
        text = ' '.join(_texts(fig))
        assert '75%' in text and '25%' in text
        plt.close(fig)

    def test_a_name_ending_in_a_number_keeps_its_gap_before_the_value(self):
        # Plate 11: "Cities / Over / 10000 9%" read as if 10000 went with 9%.
        fig = dc.pie_chart({'Cities Over 10000': 9, 'Cities 5000-10000': 1, 'Cities 2500-5000': 4,
                            'Country and Villages': 86})
        texts = _texts(fig)
        for value in ('9%', '1%', '4%'):
            ending = [t for t in texts if t.endswith(value) and t.strip() != value]
            assert ending and all(t.endswith('  ' + value) for t in ending), texts
        plt.close(fig)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Snake charts
# ---------------------------------------------------------------------------

class TestRegressionSnakeNumbers:
    """
    Plate 26's 22 occupations: "STEAM RAILWAY EMPLOYEES" was named on the
    snake without its 7,440 -- the name fitted, the number didn't -- and
    the 17 occupations listed in the legend had no number anywhere. Plate
    31's legend listed only "Rent", which was 0. And 17 newspapers over 5
    rows are 3.4 a row, but the marks at the rows' ends read "0 ... 3",
    "7 ... 3", "7 ... 10".
    """

    OCCUPATIONS = {'AGRICULTURAL LABORERS': 98400, 'FARMERS AND PLANTERS': 63012, 'LABORERS': 29723,
                   'STEAM RAILWAY EMPLOYEES': 7440, 'SERVANTS': 7000, 'DRAYMEN, HACKMEN': 4390,
                   'CARPENTERS AND JOINERS': 3781, 'SAW AND PLANING MILL EMPLOYEES': 2471,
                   'MESSENGERS': 1970, 'WOOD CHOPPERS': 1399, 'BLACKSMITHS': 1328, 'CLERGYMEN': 1277,
                   'MASONS': 1243, 'BARBERS': 899, 'MERCHANTS': 837}

    def test_every_name_has_its_number(self):
        fig = dc.snake_chart(self.OCCUPATIONS)
        values = {name: f'{v:,}' for name, v in self.OCCUPATIONS.items()}
        on_snake = ' '.join(t.get_text().replace('\n', ' ') for t in fig.axes[0].texts)
        legend = [t.get_text().replace('\n', ' ') for t in fig.legends[0].get_texts()]
        for name, value in values.items():
            listed = [entry for entry in legend if entry.startswith(name + ' ')]
            if listed:
                assert listed[0].endswith(value), listed
            else:
                assert f'{name} {value}' in ' '.join(on_snake.split()), (name, on_snake)
        plt.close(fig)

    def test_a_zero_is_listed_as_zero(self):
        fig = dc.snake_chart({'Rent': 0, 'Food': 29, 'Clothes': 16, 'Tax': 4.5, 'Other': 50.5},
                             total=100, value_format='{:g}%')
        legend = [t.get_text() for t in fig.legends[0].get_texts()]
        assert legend == ['Rent  0%'], legend
        plt.close(fig)

    def test_scale_marks_show_where_rows_end(self):
        fig = dc.snake_chart({'Magazines': 3, 'Daily Papers': 3, 'School Papers': 11}, n_rows=5)
        marks = {t.get_text() for t in fig.axes[0].texts if t.get_fontsize() == 9}
        assert {'3.4', '6.8', '10.2', '13.6'} <= marks, marks
        plt.close(fig)

    def test_round_rows_keep_round_marks(self):
        fig = dc.snake_chart({'A': 45, 'B': 25, 'C': 30}, n_rows=5)
        marks = {t.get_text() for t in fig.axes[0].texts if t.get_fontsize() == 9}
        assert {'20%', '40%', '60%'} <= marks, marks
        plt.close(fig)


# ---------------------------------------------------------------------------
# Spirals
# ---------------------------------------------------------------------------

class TestRegressionSpiralOfMonths:
    """
    Four years of monthly Seattle temperatures made 6.9 turns at the
    default of a turn every seven points: January 2012 was at the top,
    January 2013 at 9 o'clock. Months now make a turn a year.
    """

    def _curve(self, fig):
        return np.column_stack(fig.axes[0].lines[0].get_data())

    def test_months_make_a_turn_a_year(self):
        months = pd.date_range('2012-01-01', periods=48, freq='MS')
        values = 15 + 8 * np.sin(np.arange(48) / 12 * 2 * np.pi)
        with pytest.warns(UserWarning, match='loops of the spiral run into each other'):
            a = dc.spiral_chart(months, values, show_value_labels=False)
            b = dc.spiral_chart(months, values, show_value_labels=False, revolutions=47 / 12)
        assert np.allclose(self._curve(a), self._curve(b))
        plt.close(a)
        plt.close(b)

    def test_a_period_index_too(self):
        months = pd.period_range('2012-01', periods=36, freq='M')
        values = np.linspace(5, 25, 36)
        a = dc.spiral_chart(months, values, show_value_labels=False)
        b = dc.spiral_chart(months, values, show_value_labels=False, revolutions=35 / 12)
        assert np.allclose(self._curve(a), self._curve(b))
        plt.close(a)
        plt.close(b)

    def test_labels_do_not_run_together(self):
        # Births by month, 2014: "Dec 339,726" ran into "Jan 329,962".
        births = [329962, 300899, 326267, 322329, 336504, 335435, 357476, 356066, 350497, 344064,
                  318655, 339726]
        with pytest.warns(UserWarning, match='far from zero'):
            fig = dc.spiral_chart(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
                                   'Oct', 'Nov', 'Dec'], births,
                                  title='Births in the United States, 2014')
        renderer = _renderer(fig)
        boxes = [t.get_window_extent(renderer) for t in fig.axes[0].texts]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a.y1, b.y1) - max(a.y0, b.y0) > 0:          # side by side
                    gap = max(b.x0 - a.x1, a.x0 - b.x1)
                    assert gap >= 0.5 * a.height, (a, b)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------

class TestRegressionMissingValuesOnMaps:
    """
    A rate worked out from two tables -- deaths by state from one,
    population from another -- is NaN wherever either has no row. A map
    with any NaN was an error; with the NaNs, the states named two ways
    ('PR' in one table, 'Puerto Rico' in the other) were "two values for
    Puerto Rico". A missing value is now no data, drawn as such.
    """

    def test_a_missing_value_is_no_data(self):
        fig = dc.state_map_chart({'California': 1.0, 'Texas': np.nan, 'New York': 3.0, 'Ohio': 2.0})
        assert 'No data' in _texts(fig) or any(t.get_text() == 'No data' for t in fig.texts)
        plt.close(fig)

    def test_two_names_for_a_place_with_no_value(self):
        data = pd.Series({'CA': 1.0, 'TX': 2.0, 'NY': 3.0, 'PR': np.nan, 'Puerto Rico': np.nan,
                          'Guam': np.nan})
        fig = dc.state_map_chart(data)
        plt.close(fig)

    def test_a_value_wins_over_a_missing_one(self):
        fig = dc.county_map_chart({'Fulton': 5.0, 'Fulton County': np.nan, 'Bibb': 3.0, 'Cobb': 4.0})
        plt.close(fig)

    def test_nothing_but_missing_values(self):
        with pytest.raises(ValueError, match='every value in `data` is missing'):
            dc.state_map_chart({'CA': np.nan, 'TX': None})

    def test_infinity_is_still_an_error(self):
        with pytest.raises(ValueError, match='non-finite'):
            dc.state_map_chart({'CA': 1.0, 'TX': np.inf})


class TestRegressionCountiesTheMapNoLongerHas:
    """
    Public county data from before 2015 -- vega's unemployment file,
    plotly's demographics, Du Bois's own 1890 Georgia -- names counties
    the bundled 2017 boundaries don't have. The warning listed bare codes,
    or misled: "'Bedford city' -- Radford?" (a different city, already in
    the data), "'CAMPBELL' is a county of Kentucky...: is `state` right?"
    (it was Georgia's until 1932).
    """

    def _warning(self, draw):
        with pytest.warns(UserWarning, match='did not match') as caught:
            fig = draw()
        plt.close(fig)
        return ' '.join(str(w.message) for w in caught)

    def test_codes(self):
        data = {'13121': 1.0, '13089': 2.0, '46113': 3.0, '2270': 4.0, '51515': 5.0}
        text = self._warning(lambda: dc.county_map_chart(data, state='US'))
        assert 'Oglala Lakota' in text and 'Kusilvak' in text and 'Bedford County' in text

    def test_names(self):
        data = {'Anchorage': 1.0, 'Juneau': 2.0, 'Wade Hampton Census Area': 3.0}
        text = self._warning(lambda: dc.county_map_chart(data, state='AK'))
        assert 'renamed Kusilvak Census Area' in text

    def test_no_misleading_close_match(self):
        data = {'Radford city': 1.0, 'Fairfax County': 2.0, 'Bedford County': 3.0, 'Bedford city': 4.0}
        text = self._warning(lambda: dc.county_map_chart(data, state='VA'))
        assert 'Radford?' not in text and 'became part of Bedford County' in text

    def test_georgia_in_1890(self):
        from dubois_charts.charts.choropleth import _load_state_counties
        names = [c['name'].upper() for c in _load_state_counties('13')][:130]
        data = dict.fromkeys(names, 1.0)
        data.update({'CAMPBELL': 2.0, 'MILTON': 1.0, names[0] + '02': 1.0})
        text = self._warning(lambda: dc.county_map_chart(data))
        assert 'is `state` right?' not in text
        assert "'CAMPBELL' was merged into Fulton County in 1932" in text
        assert f"a second row for {names[0].title()}" in text or 'a second row for' in text

    def test_a_name_no_county_has_now(self):
        from dubois_charts.charts.choropleth import _load_state_counties
        names = [c['name'] for c in _load_state_counties('13')][:100]
        data = dict.fromkeys(names, 1.0)
        data['Jackson County, 1850 boundaries'] = 2.0     # nothing like a county anywhere
        data['Lincoln'] = 3.0                             # Georgia has one: matched
        data['Kalamazoo'] = 4.0                           # Michigan's
        text = self._warning(lambda: dc.county_map_chart(data))
        assert "'Kalamazoo' isn't among Georgia's counties" in text, text


class TestRegressionSignedValuesOnMaps:
    """
    The 2020 presidential margin by county, from -87 to +93: on the one
    light-to-dark crimson scale, narrow wins for each side shared a class,
    "-6 to +17". Data with both signs now have a class boundary at zero,
    and by default a diverging scale, green below zero and crimson above.
    """

    def test_classes_break_at_zero(self):
        rng = np.random.default_rng(1)
        values = np.concatenate([rng.uniform(-87, 0, 300), rng.uniform(0, 93, 1500)])
        edges, discrete = choropleth._classify(values, 7)
        assert not discrete
        assert 0.0 in edges
        assert (edges < 0).sum() == 3 and (edges > 0).sum() == 4      # 3 classes below, 4 above

    def test_a_side_with_few_values(self):
        values = np.array([-5.0, -5.0] + list(np.linspace(1, 50, 200)))
        edges, _ = choropleth._classify(values, 7)
        assert list(edges[:2]) == [-5.0, 0.0]
        assert len(edges) - 1 == 7                      # the rest go above zero

    def test_unsigned_classes_are_as_before(self):
        values = np.linspace(1, 100, 50)
        positions = np.round(np.linspace(0, 1, 8) * 49).astype(int)
        edges, _ = choropleth._classify(values, 7)
        assert np.array_equal(edges, np.unique(np.sort(values)[positions]))

    def _swatches(self, fig):
        return [p.get_facecolor() for p in fig.patches][:-1] or [p.get_facecolor() for p in fig.patches]

    def test_diverging_by_default(self):
        from dubois_charts.charts.choropleth import _load_state_counties
        names = [c['name'] for c in _load_state_counties('13')]
        values = np.linspace(-40, 60, len(names))
        fig = dc.county_map_chart(dict(zip(names, values)), value_format='{:+.0f}')
        colours = [p.get_facecolor() for p in fig.patches]
        assert colours[0][1] > colours[0][0]                 # the lowest class green
        assert colours[-1][0] > colours[-1][1]               # the highest crimson
        assert '+0' in [t.get_text() for t in fig.texts]
        plt.close(fig)

    def test_a_sequential_palette_can_still_be_chosen(self):
        from dubois_charts.charts.choropleth import _load_state_counties
        names = [c['name'] for c in _load_state_counties('13')]
        fig = dc.county_map_chart(dict(zip(names, np.linspace(-40, 60, len(names)))), palette='crimson')
        colours = [p.get_facecolor() for p in fig.patches]
        assert all(c[0] >= c[1] for c in colours)
        plt.close(fig)

    def test_colour_blind_readers_get_blue(self):
        dc.set_colorblind_safe(True)
        try:
            fig = dc.state_map_chart({'CA': -3.0, 'TX': -1.0, 'NY': 2.0, 'OH': 4.0, 'FL': 1.0})
        finally:
            dc.set_colorblind_safe(False)
        colours = [p.get_facecolor() for p in fig.patches]
        assert colours[0][2] > colours[0][0]                 # blue, not green
        plt.close(fig)

    def test_no_data_beside_blue_is_dark(self):
        dc.set_colorblind_safe(True)
        try:
            fig = dc.state_map_chart({'CA': -3.0, 'TX': -1.0, 'NY': 2.0, 'OH': 4.0, 'FL': 1.0})
        finally:
            dc.set_colorblind_safe(False)
        ax = fig.axes[0]
        fills = {tuple(np.round(p.get_facecolor()[:3], 3)) for p in ax.patches}
        dark = tuple(np.round(plt.matplotlib.colors.to_rgb(choropleth.MISSING_COLOR_BESIDE_BLUE), 3))
        assert dark in fills
        plt.close(fig)

    def test_an_unknown_palette(self):
        with pytest.raises(ValueError, match="`palette` must be one of"):
            dc.state_map_chart({'CA': 1.0, 'TX': 2.0}, palette='viridis')

    @pytest.mark.parametrize('negative, positive', [(1, 1), (1, 6), (3, 4), (4, 3), (6, 1)])
    def test_every_class_differs_from_no_data(self, negative, positive):
        from dubois_charts import colors
        for safe in (False, True):
            colors.set_colorblind_safe(safe)
            try:
                edges = np.array(list(range(-negative, 0)) + list(range(0, positive + 1)), dtype=float)
                classes = choropleth._class_colors(None, edges, len(edges) - 1)
            finally:
                colors.set_colorblind_safe(False)
            assert len(classes) == negative + positive
            missing = (choropleth.MISSING_COLOR_BESIDE_BLUE if safe else choropleth.MISSING_COLOR)
            for view in colors._views(classes + [missing]):
                assert float(colors._ciede2000(view[-1], view[:-1]).min()) >= 12


class TestRegressionCalloutsSideBySide:
    """
    Callouts side by side were 8-10 pixels apart: "McCone, MT Hand, SD"
    and "Emporia Greensville Petersburg" read as one name. They're now
    an em apart at least.
    """

    @pytest.mark.parametrize('seed', [5, 6, 10])
    def test_virginia(self, seed):
        from tests.test_choropleth import _state_data
        fig = dc.county_map_chart(_state_data('VA', seed), state='VA', label_top_n=15)
        renderer = _renderer(fig)
        ax = fig.axes[0]
        starts = {tuple(np.round(line.get_xydata()[1], 6)) for line in ax.lines if len(line.get_xdata()) == 2}
        boxes = [t.get_window_extent(renderer) for t in ax.texts]
        assert starts and len(boxes) >= 5
        em = ax.texts[0].get_fontsize() * fig.dpi / 72
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a.y1, b.y1) - max(a.y0, b.y0) > 0.5 * min(a.height, b.height):
                    assert max(b.x0 - a.x1, a.x0 - b.x1) >= 0.9 * em, (a, b)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Grouped bars
# ---------------------------------------------------------------------------

class TestRegressionGroupNamesCentred:
    """
    A group's name sat level with the top of its second bar, half a gap
    below the group's middle: the last bar stops a gap short of the next.
    """

    def test_names_are_level_with_the_middle_of_their_bars(self):
        fig = dc.bar_chart(['1880', '1890', '1898'], {'Savannah': [194392, 550145, 872737],
                                                      'Atlanta': [227955, 768256, 1308995]},
                           texture=False)
        renderer = _renderer(fig)
        ax = fig.axes[0]
        bars = sorted((p.get_window_extent(renderer) for p in ax.patches
                       if abs(p.get_width()) > 0 and p.get_height() < 1), key=lambda b: -b.y1)
        names = [t for t in ax.texts if t.get_text() in ('1880', '1890', '1898')]
        for k, name in enumerate(sorted(names, key=lambda t: -t.get_window_extent(renderer).y1)):
            group = bars[2 * k: 2 * k + 2]
            middle = (max(b.y1 for b in group) + min(b.y0 for b in group)) / 2
            box = name.get_window_extent(renderer)
            assert abs((box.y0 + box.y1) / 2 - middle) <= 2.0, (name.get_text(), box, middle)
        plt.close(fig)


def test_a_missing_value_says_how_to_leave_it_out():
    with pytest.raises(ValueError, match=r'\.dropna\(\)'):
        dc.bar_chart(['India', 'Kosovo'], [0.27, np.nan])


# ---------------------------------------------------------------------------
# A second pass: files read with nothing parsed, dense series, and the
# keys and numbers published data comes with
# ---------------------------------------------------------------------------

def _x_label_texts(fig):
    return [t for t in fig.axes[0].texts if t.get_va() == 'bottom' and t.get_text()]


class TestRegressionDatesWrittenAsText:
    """
    A CSV file's dates are text until they're parsed, and pd.read_csv
    doesn't parse them unless asked. The area chart printed
    "2000-01-01T08:00:00.000Z" over its first point, spaced the dates
    evenly whatever the gaps between them, and a spiral of months didn't
    make its turn a year.
    """

    def test_iso_text_reads_as_a_date(self):
        assert common.as_datetime('2020-03-01') == datetime.datetime(2020, 3, 1)
        assert common.as_datetime('2020-03') == datetime.datetime(2020, 3, 1)
        assert common.as_datetime('2020-03-01 14:30') == datetime.datetime(2020, 3, 1, 14, 30)
        stamp = common.as_datetime('2000-01-01T08:00:00.000Z')
        assert stamp.utcoffset() == datetime.timedelta(0) and stamp.hour == 8

    @pytest.mark.parametrize('text', ['2020', '2020-13-01', 'Q1 2020', '1,234', '2020/03-01',
                                      '1/22/20', 'Junk 2000'])
    def test_other_text_is_not_a_date(self, text):
        assert common.as_datetime(text) is None

    def test_labels(self):
        assert common.category_labels(['2001-01-01', '2002-01-01']) == ['2001', '2002']
        assert common.category_labels(['2000-01-01T08:00:00.000Z', '2000-02-01T08:00:00.000Z']) == [
            'Jan 2000', 'Feb 2000']

    def test_area_chart_places_text_dates_by_time(self):
        # vega's unemployment by industry, its dates left as text.
        x = [d.strftime('%Y-%m-%dT08:00:00.000Z') for d in pd.date_range('2000-01-01', periods=122, freq='MS')]
        fig = dc.stacked_area_chart(x, {'A': np.linspace(400, 900, 122), 'B': np.linspace(300, 200, 122)})
        labels = [t.get_text() for t in _x_label_texts(fig)]
        assert labels[0] == 'Jan 2000' and labels[-1] == 'Feb 2010', labels
        assert not any('T' in t for t in labels), labels
        plt.close(fig)
        # Uneven gaps are drawn uneven: 2000, 2001 and 2010 aren't evenly spaced.
        fig = dc.stacked_area_chart(['2000-01-01', '2001-01-01', '2010-01-01'], {'A': [1, 2, 3]})
        xs = fig.axes[0].collections[0].get_paths()[0].vertices[:, 0]
        span = np.ptp(xs)
        assert np.isclose(np.ptp(np.unique(np.round(xs, 6))[:2]), span / 10, rtol=0.05)
        plt.close(fig)

    def test_spiral_of_text_months_turns_a_year(self):
        months = [f'{y}-{m:02d}-01' for y in (2012, 2013) for m in range(1, 13)]
        values = np.linspace(10, 40, 24)
        a = dc.spiral_chart(months, values, show_value_labels=False)
        b = dc.spiral_chart(months, values, show_value_labels=False, revolutions=23 / 12)
        assert np.allclose(np.column_stack(a.axes[0].lines[0].get_data()),
                           np.column_stack(b.axes[0].lines[0].get_data()))
        plt.close(a)
        plt.close(b)


class TestRegressionDailyFigures:
    """
    Four years of daily COVID-19 deaths by state (the New York Times'
    file): the x labels fell every 238th day from the first,
    "2020-01-25, 2020-09-19, 2021-05-15", and the hand-drawn wobble, one
    at every point, drew each boundary as a seismograph.
    """

    def _chart(self, **kw):
        days = pd.date_range('2020-01-25', '2023-03-23', freq='D')
        n = len(days)
        return dc.stacked_area_chart(days, {'A': np.linspace(10, 900, n), 'B': np.linspace(5, 400, n),
                                            'C': np.full(n, 300.0)}, show_value_labels=False, **kw)

    def test_labels_name_round_months(self):
        fig = self._chart()
        labels = [t.get_text() for t in _x_label_texts(fig)]
        assert labels[0] == '2020-01-25' and labels[-1] == '2023-03-23', labels
        inner = labels[1:-1]
        assert len(inner) >= 3
        assert all(t.isdigit() or t[:3] in ('Jan', 'Apr', 'Jul', 'Oct', 'Mar', 'Sep', 'May', 'Nov',
                                            'Feb', 'Jun', 'Aug', 'Dec') for t in inner), labels
        assert not any(t.count('-') == 2 for t in inner), labels
        plt.close(fig)

    def test_the_wobble_is_smooth(self):
        fig = self._chart()
        n = len(pd.date_range('2020-01-25', '2023-03-23', freq='D'))
        exact = np.linspace(10, 900, n) + np.linspace(5, 400, n)    # where A and B meet C
        line = next(line for line in fig.axes[0].lines
                    if len(line.get_ydata()) == n and abs(line.get_ydata()[-1] - exact[-1]) < 1)
        wobble = np.asarray(line.get_ydata()) - exact
        assert np.abs(wobble).max() > 0.5                       # it still wobbles...
        # ...but from day to day only a little: the wobble at every point
        # moved by about 0.005 of the chart's height from one day to the next.
        assert np.abs(np.diff(wobble)).max() < 0.0015 * 1600, np.abs(np.diff(wobble)).max()
        plt.close(fig)


class TestRegressionManyYearsLabelledLevel:
    """
    Population of five countries, 1960-2025, and US energy use, 1965-2024:
    with over sixty years, the labels were tilted 45 degrees, every other
    year, with a column of numbers under each. Numbers and dates now stay
    level, at round steps.
    """

    def test_level_and_round(self):
        years = list(range(1960, 2026))
        fig = dc.stacked_area_chart(years, {'China': np.linspace(667, 1406, 66),
                                            'India': np.linspace(436, 1464, 66)})
        labels = _x_label_texts(fig)
        assert all(t.get_rotation() == 0 for t in labels)
        inner = [int(t.get_text()) for t in labels[1:-1]]
        assert len(inner) >= 4 and all(y % 5 == 0 for y in inner), inner
        plt.close(fig)

    def test_text_categories_still_tilt(self):
        regions = [f'Region number {i}' for i in range(14)]
        fig = dc.stacked_area_chart(regions, {'A': np.arange(1, 15)})
        assert any(t.get_rotation() for t in _x_label_texts(fig))
        plt.close(fig)


class TestRegressionDecimalsOfATypicalValue:
    """
    Our World in Data publishes energy use to three decimals of a
    terawatt-hour, and solar power's first years are a few thousandths:
    the tiniest value set the precision of every label, "11,072.753".
    """

    @pytest.mark.parametrize('values, expected', [
        ([2249.404, 11072.753, 5000.1, 0.003], '{:,.0f}'),
        ([72.39, 1463.87, 250.1234], '{:,.1f}'),
        ([32.958, 21.784, 8.849, 0.281], '{:,.2f}'),
        ([12.5, 9.8, 0.45, 3.1, 0.012], '{:,.3f}'),        # still "0.012" among ones
        ([0.00077, 0.01176, 0.0034], '{:,.5f}'),
    ])
    def test_formats(self, values, expected):
        assert common.default_value_format(values) == expected

    def test_area_chart_labels(self):
        fig = dc.stacked_area_chart([1965, 1966, 1967], {'Coal': [3224.244, 3433.077, 3414.659],
                                                         'Oil': [6414.477, 7457.961, 8176.191]})
        numbers = [t for t in _texts(fig) if t[:1].isdigit() and ',' in t]
        assert numbers and not any('.' in t for t in numbers), numbers
        plt.close(fig)


class TestRegressionSnakeMarksAreRound:
    """
    Shares of the world's electricity, published to three decimals: the
    marks at the rows' ends read "20.000%" and "40.000%".
    """

    def test_marks(self):
        shares = {'Coal': 32.958, 'Gas': 21.784, 'Hydro': 13.959, 'Nuclear': 8.849, 'Wind': 8.539,
                  'Solar': 8.745, 'Oil': 2.649, 'Bioenergy': 2.236, 'Other': 0.281}
        fig = dc.snake_chart(shares)
        marks = {t.get_text() for t in fig.axes[0].texts if t.get_fontsize() == 9}
        assert {'20%', '40%', '60%', '80%'} <= marks, marks
        plt.close(fig)


class TestRegressionSpiralLoopsThatMeet:
    """
    Monthly carbon dioxide at Mauna Loa (313 to 414 parts per million)
    drew 62 turns as one solid red ring, and monthly births a tangle; the
    chart said nothing. It now warns, and says what to do.
    """

    def _months(self, n):
        return pd.date_range('2015-01-01', periods=n, freq='MS')

    def test_far_from_zero(self):
        i = np.arange(60)
        co2 = 400 + 0.2 * i + 3 * np.sin(i / 12 * 2 * np.pi)
        with pytest.warns(UserWarning, match=r'far from zero.*values minus'):
            fig = dc.spiral_chart(self._months(60), co2, show_value_labels=False)
        plt.close(fig)

    def test_a_season(self):
        i = np.arange(48)
        with pytest.warns(UserWarning, match='season'):
            fig = dc.spiral_chart(self._months(48), 15 + 8 * np.sin(i / 12 * 2 * np.pi),
                                  show_value_labels=False)
        plt.close(fig)

    def test_many_turns(self):
        i = np.arange(240)
        with pytest.warns(UserWarning, match='fewer points'):
            fig = dc.spiral_chart(self._months(240), 300 + 20 * np.sin(i / 12 * 2 * np.pi),
                                  show_value_labels=False)
        plt.close(fig)

    @pytest.mark.parametrize('values', [
        [45, 62, 89, 140, 210, 305],                                   # the README's
        [round(5 * (300 / 5) ** (k / 39), 1) for k in range(40)],     # forty points, growing
        list(np.linspace(0, 99, 62)),                                 # a rise from a baseline
    ])
    def test_growth_is_quiet(self, values):
        fig, caught = _no_warnings(lambda: dc.spiral_chart([str(k) for k in range(len(values))],
                                                           values))
        assert not [w for w in caught if 'loops' in w], caught
        plt.close(fig)


class TestRegressionPlacesWithNoKey:
    """
    The New York Times' county file has no FIPS code for New York City or
    for "Unknown", so the obvious df.set_index('fips')['deaths'] had NaN
    keys -- an error that stopped the chart -- and pandas had made the
    rest floats, 1001.0. A value with no place is now left out with a
    warning, as a key naming no place is, and 1001.0 is Alabama's 01001.
    """

    def test_county_map(self):
        data = pd.Series([160.0, 593.0, 81.0, 40000.0, 1200.0],
                         index=[1001.0, 1003.0, 13121.0, np.nan, np.nan])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fig = dc.county_map_chart(data)
        messages = [str(w.message) for w in caught]
        assert any('2 values in `data` have no county' in m for m in messages), messages
        assert not any('did not match' in m for m in messages), messages
        plt.close(fig)

    def test_state_map(self):
        with pytest.warns(UserWarning, match='1 value in `data` has no state'):
            fig = dc.state_map_chart(pd.Series([3.0, 4.0, 5.0], index=['GA', 'TX', None]))
        plt.close(fig)


class TestRegressionUnmatchedCodesExplained:
    """
    County election results come with Alaska's election districts as its
    "counties", 02901 to 02940 (read as int, 2901 to 2940), and the New
    York Times' file with the Northern Mariana Islands and the Virgin
    Islands. The warning listed forty codes without a word about whose
    they were.
    """

    def test_whose_codes(self):
        data = {code: 1.0 for code in range(2901, 2941)}
        data.update({1001: 2.0, 13121: 3.0, 69110: 4.0, 78010: 5.0})
        with pytest.warns(UserWarning) as caught:
            fig = dc.county_map_chart(data)
        text = ' '.join(str(w.message) for w in caught)
        assert "'02901' to '02940' are Alaska's codes" in text, text
        assert 'island territories' in text and "state='MP'" in text, text
        assert 'and 30 more' in text                       # forty codes aren't all listed
        plt.close(fig)


class TestRegressionMultiIndexNames:
    """
    df.groupby(['year', 'month']).sum() names each row with a tuple, and a
    chart of it read "(2000, 1)" and "('Germany', '15-40')".
    """

    def test_labels(self):
        assert common.category_labels([(2000, 1), (2000, 2)]) == ['2000, 1', '2000, 2']
        assert common.category_labels([(2000.0, 'Jan'), (2001.0, 'Jan')]) == ['2000, Jan', '2001, Jan']

    def test_bar_chart(self):
        index = pd.MultiIndex.from_tuples([('Germany', '15-40'), ('Negroes', '15-40')])
        s = pd.Series([37.3, 54.0], index=index)
        fig = dc.bar_chart(s.index, s)
        assert {'Germany, 15-40', 'Negroes, 15-40'} <= set(_texts(fig))
        plt.close(fig)


class TestRegressionNumbersWrittenForPeople:
    """
    plotly's county file writes its shares as text, "7.47%": the error
    said only that '7.47%' isn't a number. It now says how to make it one.
    """

    @pytest.mark.parametrize('text, hint', [
        ('7.47%', r"rstrip\('%'\)"), ('1,234,567', "thousands=','"), ('$1,250', 'currency sign'),
    ])
    def test_hint(self, text, hint):
        with pytest.raises(ValueError, match=hint):
            dc.bar_chart(['A', 'B'], ['5', text])

    def test_a_word_has_no_hint(self):
        with pytest.raises(ValueError) as e:
            dc.bar_chart(['A', 'B'], ['5', 'n/a'])
        assert 'pandas' not in str(e.value)


# ---------------------------------------------------------------------------
# A third pass, on macOS: the same pictures looked at again, and more data
# ---------------------------------------------------------------------------

class TestRegressionAveragesOfLargeNumbers:
    """
    FiveThirtyEight's births, averaged by day of the week, are about
    12,000 with fifteen decimals; the labels read "11,897.83". Rounding
    noise was allowed up to a millionth of each value, which from about
    5,000 up is more than half a hundredth, so two decimals counted as
    "exact" for any such value.
    """

    def test_format(self):
        means = [11897.830140485314, 13122.444444444445, 12910.766283524905, 8562.57343550447]
        assert common.default_value_format(means) == '{:,.0f}'

    def test_exact_decimals_are_kept(self):
        assert common.default_value_format([1234.56, 99.99, 12345678.93]) == '{:,.2f}'
        assert common.default_value_format([0.1 + 0.2, 1.5]) == '{:,.1f}'
        assert common.default_value_format(np.array([12.6, 6.48], dtype=np.float32)) == '{:,.2f}'

    def test_bar_labels(self):
        fig = dc.bar_chart(['Mon', 'Tue', 'Sat'], [11897.830140485314, 13122.444444444445, 8562.57343550447])
        assert {'11,898', '13,122', '8,563'} <= set(_texts(fig)), _texts(fig)
        plt.close(fig)


class TestRegressionSpiralLabelsKeptApart:
    """
    The rise in CO2 at Mauna Loa, year by year: the first point's label,
    "1958  0", was put beside the last one's, "2020  99", no farther from
    it than the two spaces inside each -- "2020  99  1958  0".
    """

    def test_gap_wider_than_inside_a_label(self):
        years = np.arange(1958, 2021)
        rise = 0.012 * (years - 1958) ** 2 + 0.85 * (years - 1958)
        fig = dc.spiral_chart(years, rise, value_format='{:.0f}')
        renderer = _renderer(fig)
        texts = [t for t in fig.axes[0].texts if t.get_text()]
        probe = fig.text(0, 0, 'X  X', fontsize=texts[0].get_fontsize(), fontweight='bold',
                         fontfamily=texts[0].get_fontfamily())
        probe2 = fig.text(0, 0, 'XX', fontsize=texts[0].get_fontsize(), fontweight='bold',
                          fontfamily=texts[0].get_fontfamily())
        inner = probe.get_window_extent(renderer).width - probe2.get_window_extent(renderer).width
        boxes = [t.get_window_extent(renderer) for t in texts]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a.y1, b.y1) - max(a.y0, b.y0) > 0:          # side by side
                    assert max(b.x0 - a.x1, a.x0 - b.x1) >= 1.5 * inner, (a, b)
        plt.close(fig)


class TestRegressionOneColumnForAnArea:
    """
    An Excel workbook of sales, or Brent crude's daily price: the area
    chart given one column of the table, df['Price'], read its row
    numbers as series names and each price as a series of its own, and
    stopped with "object of type 'float' has no len()".
    """

    def test_a_named_column(self):
        df = pd.DataFrame({'Date': ['1987-05-20', '1987-05-21', '1987-05-22'],
                           'Price': [18.63, 18.45, 18.55]})
        fig = dc.stacked_area_chart(df['Date'], df['Price'])
        assert 'PRICE' in _texts(fig) or 'Price' in [t.get_text() for t in fig.texts]
        plt.close(fig)

    def test_an_unnamed_series(self):
        fig = dc.stacked_area_chart([2001, 2002, 2003], pd.Series([3.0, 4.0, 5.0]))
        plt.close(fig)


class TestRegressionCountriesOnTheStateMap:
    """
    Johns Hopkins' COVID-19 cases by country, given to state_map_chart:
    the map drew Georgia -- the country's cases on the American state --
    and only warned about the other 200 countries. Provinces of Canada
    were "none of the keys is a state", with no word that the map is of
    the United States only.
    """

    COUNTRIES = {c: float(i + 1) for i, c in enumerate(
        ['Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Argentina', 'Armenia',
         'Australia', 'Austria', 'Azerbaijan', 'Bahamas', 'Georgia'])}

    def test_countries(self):
        with pytest.raises(ValueError, match=r"11 of the 12 keys .* not states of the United "
                                             r"States.*'Georgia' would have been drawn as the American state"):
            dc.state_map_chart(self.COUNTRIES)

    def test_provinces(self):
        with pytest.raises(ValueError, match='United States only'):
            dc.state_map_chart({'Ontario': 3.0, 'Quebec': 2.0, 'Alberta': 1.0})

    def test_a_few_strays_still_only_warn(self):
        data = {'California': 1.0, 'Texas': 2.0, 'Ohio': 3.0, 'Guam': 4.0, 'USA': 10.0}
        fig, caught = _no_warnings(lambda: dc.state_map_chart(data))
        assert any('matched no state' in w for w in caught), caught
        plt.close(fig)


class TestRegressionDatesWrittenOtherWays:
    """
    vega's stock prices date each month "Jan 1 2000"; read as text, a
    pivot of them sorts "Apr 1 2000" first and "Sep 1 2009" last, and the
    area chart drew ten years of prices in that order, without a word.
    vega's GitHub commits are "2015/01/01 01:00:00", and Johns Hopkins'
    COVID-19 table heads a column a day "1/22/20": both were text.
    """

    @pytest.mark.parametrize('text, expected', [
        ('Jan 1 2000', datetime.datetime(2000, 1, 1)),
        ('January 15, 2000', datetime.datetime(2000, 1, 15)),
        ('1 Feb 2000', datetime.datetime(2000, 2, 1)),
        ('01-Feb-2000', datetime.datetime(2000, 2, 1)),
        ('Sept. 2001', datetime.datetime(2001, 9, 1)),
        ('2015/01/01 01:00:00', datetime.datetime(2015, 1, 1, 1)),
        ('2015/01/31', datetime.datetime(2015, 1, 31)),
    ])
    def test_read_as_dates(self, text, expected):
        assert common.as_datetime(text) == expected

    def test_numbers_and_slashes_when_the_dates_tell(self):
        assert common.as_datetimes(['1/22/20', '1/23/20']) == [datetime.datetime(2020, 1, 22),
                                                             datetime.datetime(2020, 1, 23)]
        assert common.as_datetimes(['22/01/2020', '01/02/2020']) == [datetime.datetime(2020, 1, 22),
                                                                   datetime.datetime(2020, 2, 1)]
        assert common.as_datetimes(['1/2/20', '3/4/20']) == [None, None]     # either way round

    def test_text_among_text_is_left_alone(self):
        assert common.category_labels(['Mar 2020', 'Total']) == ['Mar 2020', 'Total']

    def test_a_pivot_of_them_is_drawn_in_order(self):
        months = pd.date_range('2000-01-01', periods=24, freq='MS')
        long = pd.DataFrame({'date': [f"{d:%b} 1 {d.year}" for d in months] * 2,
                             'symbol': ['MSFT'] * 24 + ['IBM'] * 24,
                             'price': list(range(24)) + list(range(100, 124))})
        p = long.pivot(index='date', columns='symbol', values='price')     # sorted as text
        assert p.index[0] == 'Apr 1 2000'
        fig = dc.stacked_area_chart(p.index, p, show_value_labels=False)
        labels = [t.get_text() for t in _x_label_texts(fig)]
        assert labels[0] == 'Jan 2000' and labels[-1] == 'Dec 2001', labels
        tops = fig.axes[0].collections[-1].get_paths()[0].vertices
        assert tops[:, 1].max() == pytest.approx(23 + 123, rel=0.02)
        plt.close(fig)


class TestRegressionScientificNotationFromOneValue:
    """
    COVID-19 cases in millions are a few millionths in the first days of
    2020: the smallest value set every label in scientific notation,
    "3.71e+01" for 37.1 million.
    """

    def test_format(self):
        fmt = common.default_value_format([0.000001, 0.000002, 0.0013, 25.9, 37.1, 44.7, 12.03])
        assert 'e' not in fmt, fmt

    def test_tiny_values_still_are(self):
        assert common.default_value_format([4.1e-7, 3.2e-7, 9e-8]) == '{:.2e}'
