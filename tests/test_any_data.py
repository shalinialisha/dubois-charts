"""
Every chart with whatever data someone brings.

These come from a stress test that ran all seven chart functions over a
few hundred input variations -- containers (lists, tuples, numpy arrays,
pandas objects), number types, magnitudes from 1e-7 to 1e13, one to a
hundred categories, and label text with currency signs, CJK characters,
long names and numbers where text was expected -- and checked every
render for crashes, unclear errors, overlapping or clipped text, and
numbers printed wrongly. Each class below is one thing it found, and
fails against the code from before the fix.
"""

import datetime
import itertools
import warnings

import numpy as np
import pytest
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.text import Text

import dubois_charts as dc
from dubois_charts.charts import _common as common

L4 = ['Alpha', 'Beta', 'Gamma', 'Delta']
V4 = [40, 25, 20, 15]
LONG = 'A considerably long category name that goes on and on for a while'


def _texts(fig):
    return [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]


def _text_problems(fig):
    """Rendered text running off the figure, or overlapping other text."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    boxes = [(t, t.get_window_extent(renderer)) for t in _texts(fig)]
    problems = [f'off the figure: {t.get_text()[:30]!r}' for t, b in boxes
                if b.x0 < -1 or b.y0 < -1 or b.x1 > width + 1 or b.y1 > height + 1]
    for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
        if min(a.x1, b.x1) - max(a.x0, b.x0) > 1 and min(a.y1, b.y1) - max(a.y0, b.y0) > 1:
            problems.append(f'overlap: {ta.get_text()[:20]!r} / {tb.get_text()[:20]!r}')
    return problems


ALL_CHARTS = {
    'bar': lambda **kw: dc.bar_chart(kw.pop('labels', L4), kw.pop('values', V4), **kw),
    'area': lambda **kw: dc.stacked_area_chart(
        [2000, 2010, 2020], dict(zip(kw.pop('labels', L4)[:3], ([50, 30, 15], [20, 35, 40], [30, 35, 45]))), **kw),
    'butterfly': lambda **kw: dc.butterfly_chart(kw.pop('labels', L4), V4, V4, **kw),
    'spiral': lambda **kw: dc.spiral_chart(kw.pop('labels', L4), V4, **kw),
    'snake': lambda **kw: dc.snake_chart(dict(zip(kw.pop('labels', L4), V4)), **kw),
    'pie': lambda **kw: dc.pie_chart(dict(zip(kw.pop('labels', L4), V4)), **kw),
    'map': lambda **kw: dc.county_map_chart({'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61}, **kw),
}


class TestRegressionDollarSignsAreText:
    """
    matplotlib reads text between two dollar signs as math: the label
    "$5-$10" rendered as an italic "5-10" and the title "Spending: $5 to $10
    per day" as "SPENDING: 5TO10 PER DAY". Every chart now draws text
    literally, and ignores a global `text.usetex` that would turn "%" and
    "_" in ordinary labels into LaTeX errors.
    """

    @pytest.mark.parametrize('chart', list(ALL_CHARTS))
    def test_no_text_is_parsed_as_math(self, chart):
        fig = ALL_CHARTS[chart](title='Spending: $5 to $10 per day')
        assert all(t.get_parse_math() is False for t in _texts(fig))
        plt.close(fig)

    def test_currency_labels_come_out_as_written(self):
        fig = dc.bar_chart(['$5-$10', 'Under $5', '$10+'], [3, 2, 1])
        fig.canvas.draw()
        drawn = {t.get_text() for t in fig.axes[0].texts}
        assert {'$5-$10', 'Under $5', '$10+'} <= drawn
        # rendered as text, so as wide as the literal string
        renderer = fig.canvas.get_renderer()
        label = next(t for t in fig.axes[0].texts if t.get_text() == '$5-$10')
        assert label.get_window_extent(renderer).width > 40
        plt.close(fig)

    @pytest.mark.parametrize('chart', list(ALL_CHARTS))
    def test_global_usetex_is_ignored(self, chart):
        with plt.rc_context({'text.usetex': True}):
            fig = ALL_CHARTS[chart](title='100% of_the_total')
            fig.canvas.draw()          # would fail running LaTeX on "%" and "_"
        assert all(t.get_usetex() is False for t in _texts(fig))
        plt.close(fig)


class TestRegressionTextInAnyScript:
    """
    Every chart drew in one monospace font, so Chinese, Japanese and Korean
    labels rendered as empty boxes. Text now falls back, glyph by glyph, to
    whichever installed font has the character.
    """

    def test_font_stack_puts_the_chart_font_first_and_only_lists_installed_fonts(self):
        chosen = common.get_font()           # installed: Liberation Mono, Courier New, ...
        stack = common.font_stack(chosen)
        assert stack[0] == chosen
        installed = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
        assert all(f in installed for f in stack[1:])
        assert len(stack) == len(set(stack))
        assert common.font_stack(('DejaVu Sans', 'DejaVu Sans Mono'))[:2] == ('DejaVu Sans', 'DejaVu Sans Mono')
        with pytest.warns(UserWarning, match="'A', 'B' are not an installed font"):
            assert common.font_stack(('A', 'B'))[0] == common.get_font()

    @pytest.mark.parametrize('chart', ['bar', 'pie', 'snake', 'spiral'])
    def test_cjk_labels_render_when_a_cjk_font_is_installed(self, chart):
        installed = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
        cjk = [f for f in common.FALLBACK_FONTS if 'CJK' in f or f in (
            'Source Han Sans', 'WenQuanYi Zen Hei', 'IPAGothic', 'Droid Sans Fallback',
            'Hiragino Sans', 'PingFang SC', 'Microsoft YaHei', 'Malgun Gothic', 'Yu Gothic', 'SimHei')]
        if not any(f in installed for f in cjk):
            pytest.skip('no CJK font installed on this machine')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fig = ALL_CHARTS[chart](labels=['東京', '北京', '서울', 'Delta'])
            fig.canvas.draw()
        missing = [str(w.message) for w in caught if 'Glyph' in str(w.message)]
        assert missing == []
        plt.close(fig)


class TestRegressionInputContainers:
    """
    pie_chart and snake_chart called `segments.values()`, which on a pandas
    Series is an array, not a method: passing one crashed with "'numpy.ndarray'
    object is not callable". A DataFrame of series gave bar_chart "The truth
    value of an array ... is ambiguous", and stacked_area_chart crashed
    upper-casing an integer series name.
    """

    def test_integer_names_and_categories(self):
        for fig in (dc.stacked_area_chart([1, 2], {2023: [1, 2], 2024: [2, 1]}),
                    dc.bar_chart([2021, 2022], [1, 2]),
                    dc.pie_chart({1: 3, 2: 4}),
                    dc.snake_chart({1: 3, 2: 4})):
            assert isinstance(fig, plt.Figure)
            plt.close(fig)

    def test_pandas_series_and_dataframes(self):
        pd = pytest.importorskip('pandas')
        segments = pd.Series({'Alpha': 40, 'Beta': 25, 'Gamma': 20})
        frame = pd.DataFrame({'2023': [4, 3], '2024': [5, 1]}, index=['North', 'South'])
        figs = [dc.pie_chart(segments), dc.snake_chart(segments),
                dc.bar_chart(list(frame.index), frame),
                dc.stacked_area_chart([2000, 2010], frame),
                dc.county_map_chart(pd.Series({'Fulton': 2.5, 'Cobb': 3.5}))]
        bar = figs[2]
        assert len([p for p in bar.axes[0].patches if p.get_fill()]) == 4     # two series of two
        for fig in figs:
            plt.close(fig)

    def test_numbers_of_any_kind(self):
        import decimal
        import fractions
        for values in (np.array(V4, dtype=np.int64), np.array(V4, dtype=np.float32),
                       [decimal.Decimal(v) for v in V4], [fractions.Fraction(v, 3) for v in V4],
                       ['40', '25', '20', '15']):
            fig = dc.bar_chart(L4, values)
            plt.close(fig)


class TestRegressionNumbersAndDatesAsLabels:
    """
    Categories, series names and segment names that weren't strings were
    printed the way Python prints them. pandas turns a column of years into
    floats whenever it has a gap, and dates into Timestamps, so labels read
    "2018.0", "2018-01-01 00:00:00" or "2018-01-01T00:00:00.000000" (the
    spiral even wrapped that one mid-number), and arithmetic left labels
    like "0.30000000000000004". They're now written the way a person would
    write them.
    """

    def test_label_rules(self):
        labels = common.category_labels
        assert labels([2018.0, 2019.0]) == ['2018', '2019']
        assert labels(np.array([2018, 2019], dtype=float)) == ['2018', '2019']
        assert labels([0.1 + 0.2, 0.6]) == ['0.3', '0.6']
        assert labels([0.5, 1.0, 1.5]) == ['0.5', '1.0', '1.5']        # floats share decimals
        assert labels([1, 2.5, 3]) == ['1', '2.5', '3']                # ints stay as written
        assert labels(np.array([0.1, 1234.567], dtype=np.float32)) == ['0.100', '1234.567']
        assert labels([True, False, None]) == ['True', 'False', 'None']
        assert labels(['2018.0', 'North']) == ['2018.0', 'North']      # text is never changed
        assert labels([datetime.date(2020, 1, 1), datetime.date(2021, 1, 1)]) == ['2020', '2021']
        assert labels([datetime.date(2024, 1, 1), datetime.date(2024, 2, 1)]) == ['Jan 2024', 'Feb 2024']
        assert labels([datetime.date(2024, 1, 1)]) == ['2024-01-01']   # one date: that day
        assert labels([datetime.datetime(2024, 3, 1, 9, 30), datetime.datetime(2024, 3, 1, 14)]) == [
            '2024-03-01 09:30', '2024-03-01 14:00']
        assert labels(np.array(['2018-01-01', '2019-01-01'], dtype='datetime64[ns]')) == ['2018', '2019']

    def test_tidying_never_merges_two_categories(self):
        assert common.category_labels([0.3, 0.1 + 0.2]) == ['0.3', '0.30000000000000004']
        assert common.category_labels(['2018', 2018.0]) == ['2018', '2018.0']

    @pytest.mark.parametrize('chart', ['bar', 'butterfly', 'spiral', 'area', 'area names', 'pie', 'snake'])
    @pytest.mark.parametrize('kind', ['float years', 'Timestamps', 'datetime64'])
    def test_charts_draw_tidy_labels(self, chart, kind):
        pd = pytest.importorskip('pandas')
        years = pd.date_range('2018-01-01', periods=4, freq='YS')
        cats = {'float years': [2018.0, 2019.0, 2020.0, 2021.0],
                'Timestamps': list(years),
                'datetime64': years.values}[kind]
        fig = {
            'bar': lambda: dc.bar_chart(cats, V4),
            'butterfly': lambda: dc.butterfly_chart(cats, V4, V4),
            'spiral': lambda: dc.spiral_chart(cats, V4),
            'area': lambda: dc.stacked_area_chart(cats, {'A': V4, 'B': V4}),
            'area names': lambda: dc.stacked_area_chart(
                ['a', 'b', 'c'], pd.DataFrame(np.ones((3, 4)), columns=cats)),
            'pie': lambda: dc.pie_chart(pd.Series(V4, index=cats)),
            'snake': lambda: dc.snake_chart(pd.Series(V4, index=cats)),
        }[chart]()
        fig.canvas.draw()
        texts = [t.get_text() for t in _texts(fig)]
        plt.close(fig)
        assert any('2018' in t for t in texts), texts
        assert not [t for t in texts if '2018.0' in t or '00:00' in t or 'T00' in t], texts

    @pytest.mark.parametrize('chart', list(ALL_CHARTS))
    def test_a_title_can_be_a_number(self, chart):
        # e.g. a DataFrame's column name; this crashed every chart with
        # "expected string or bytes-like object, got 'int'"
        fig = ALL_CHARTS[chart](title=2024, subtitle=2025.0)
        fig.canvas.draw()
        texts = [t.get_text() for t in _texts(fig)]
        plt.close(fig)
        assert '2024' in texts and '2025' in texts, texts

    def test_side_and_colorbar_labels_can_be_numbers(self):
        fig = dc.butterfly_chart(L4, V4, V4, left_label=2023, right_label=2024.0)
        fig.canvas.draw()
        assert {'2023', '2024'} <= {t.get_text() for t in _texts(fig)}
        plt.close(fig)
        fig = dc.county_map_chart({'Fulton': 82, 'Cobb': 74}, colorbar_label=2024)
        fig.canvas.draw()
        assert '2024' in {t.get_text() for t in _texts(fig)}
        plt.close(fig)

    @pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), 'NaT'])
    def test_missing_x_is_named(self, bad):
        pd = pytest.importorskip('pandas')
        if bad == 'NaT':
            x = [pd.Timestamp('2020-01-01'), pd.NaT, pd.Timestamp('2022-01-01')]
        else:
            x = [2000, bad, 2020]
        with pytest.raises(ValueError, match=r'missing or infinite value at position 1'):
            dc.stacked_area_chart(x, {'A': [1, 2, 3], 'B': [3, 2, 1]})


class TestRegressionClearErrors:
    """
    A missing value was reported as "NaN or infinity", a word where a number
    belonged failed deep inside with numpy's or Python's own message, and a
    bad `value_format` either did the same or silently labelled every bar
    with the same text.
    """

    @pytest.mark.parametrize('chart', ['bar', 'butterfly', 'spiral', 'pie', 'snake'])
    def test_missing_value_is_named(self, chart):
        call = {
            'bar': lambda: dc.bar_chart(L4, [40, None, 20, 15]),
            'butterfly': lambda: dc.butterfly_chart(L4, [40, None, 20, 15], V4),
            'spiral': lambda: dc.spiral_chart(L4, [40, None, 20, 15]),
            'pie': lambda: dc.pie_chart(dict(zip(L4, [40, None, 20, 15]))),
            'snake': lambda: dc.snake_chart(dict(zip(L4, [40, None, 20, 15]))),
        }[chart]
        with pytest.raises(ValueError, match=r"missing.*Beta"):
            call()

    def test_text_where_a_number_belongs_is_named(self):
        with pytest.raises(ValueError, match=r"isn't a number for Beta: 'n/a'"):
            dc.bar_chart(L4, [40, 'n/a', 20, 15])
        with pytest.raises(ValueError, match=r"isn't a number for Fulton"):
            dc.county_map_chart({'Fulton': 'twelve', 'Cobb': 2})

    @pytest.mark.parametrize('chart', ['bar', 'area', 'butterfly', 'spiral', 'snake', 'pie', 'map'])
    def test_bad_value_format_says_so(self, chart):
        with pytest.raises(ValueError, match='value_format'):
            ALL_CHARTS[chart](value_format='{:.0d}')
        with pytest.raises(ValueError, match='placeholder'):
            ALL_CHARTS[chart](value_format='units')


class TestRegressionNumbersForAnyData:
    """
    stacked_area_chart, butterfly_chart and snake_chart defaulted to
    '{:.0f}%' whatever they were given: raw counts printed as "1900%",
    electricity in GWh as "4100000000%", fractions as "0%". spiral_chart's
    '{:.0f}' printed every value below 1 as "0", and tiny values printed as
    "0.000000" everywhere. Defaults now follow the data, with a percent
    sign only when the values really are percentages of their total.
    """

    @staticmethod
    def _value_texts(fig):
        return [t.get_text() for ax in fig.axes for t in ax.texts
                if any(ch.isdigit() for ch in t.get_text())]

    def test_raw_counts_get_no_percent_sign(self):
        raw = {'Coal': [1900, 1100, 700], 'Gas': [600, 1000, 1600]}
        for fig in (dc.stacked_area_chart([2000, 2010, 2020], raw),
                    dc.butterfly_chart(['A', 'B'], [1900, 600], [700, 1600]),
                    dc.snake_chart({'Coal': 1900, 'Gas': 600, 'Oil': 450})):
            texts = self._value_texts(fig)
            assert texts and not any('%' in t for t in texts), texts
            plt.close(fig)

    def test_shares_of_100_keep_their_percent_sign(self):
        for fig in (dc.stacked_area_chart([2000, 2010], {'A': [60, 30], 'B': [40, 70]}),
                    dc.butterfly_chart(['A', 'B'], [52, 48], [31, 69]),
                    dc.snake_chart({'A': 60, 'B': 25, 'C': 15})):
            texts = [t for t in self._value_texts(fig) if t not in ('2000', '2010')]   # x labels
            assert texts and all(t.endswith('%') for t in texts), texts
            plt.close(fig)

    def test_fractions_are_not_rounded_to_zero(self):
        fig = dc.spiral_chart(L4, [0.41, 0.25, 0.2, 0.14])
        assert any('0.41' in t for t in self._value_texts(fig))
        plt.close(fig)
        fig = dc.stacked_area_chart([1, 2], {'A': [0.41, 0.3], 'B': [0.25, 0.2]})
        assert '0.41' in self._value_texts(fig)
        plt.close(fig)

    def test_tiny_values_are_not_all_zero(self):
        fig = dc.bar_chart(L4, [4.1e-7, 2.5e-7, 2e-7, 1.4e-7])
        texts = self._value_texts(fig)
        values = [t for t in texts if 'e-07' in t]
        assert len(values) == 4 and len(set(values)) == 4
        plt.close(fig)

    def test_default_format_rules(self):
        assert common.default_value_format([4.1e-7, 2e-7]) == '{:.2e}'
        assert common.default_value_format([4.1e15, 2e15]) == '{:.2e}'
        assert common.default_value_format(np.array([0.1, 0.25], dtype=np.float32)) == '{:,.2f}'
        assert common.default_value_format(np.array([0.1, 0.5], dtype=np.float32)) == '{:,.1f}'
        assert common.default_value_format_for([60, 40], [100]) == '{:,.0f}%'
        assert common.default_value_format_for([60, 37], [97]) == '{:,.0f}'


class TestRegressionAreaChartForAnyX:
    """
    stacked_area_chart placed its x labels at 2% of the data's height above
    the plot while reserving only their height plus 14px, so on a chart
    with no title the year labels ran off the top of the image. Dates were
    spaced evenly however irregular, pandas dates printed as "2020-01-01
    00:00:00", unsorted x zig-zagged the areas, 30 or more points made the
    figure 16 x 16.8 inches, and with 100 points the last year had no label
    and values sat under years that had none.
    """

    SERIES = {'Coal': [50, 30, 15], 'Gas': [20, 35, 40], 'Renewables': [30, 35, 45]}

    @staticmethod
    def _x_labels(fig):
        ax = fig.axes[0]
        return [t for t in ax.texts if t.get_transform() is not ax.transData
                and t.get_va() in ('bottom', 'top') and not t.get_text().endswith('%')]

    @pytest.mark.parametrize('title', [None, 'With a title'])
    def test_no_text_off_the_figure(self, title):
        fig = dc.stacked_area_chart([2000, 2010, 2020], self.SERIES, title=title)
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_dates_are_spaced_by_time_and_labelled_compactly(self):
        x = [datetime.date(2020, 1, 1), datetime.date(2021, 1, 1), datetime.date(2030, 1, 1)]
        fig = dc.stacked_area_chart(x, self.SERIES)
        labels = {t.get_text(): t.get_position()[0] for t in self._x_labels(fig)}
        assert {'2020', '2030'} <= set(labels)
        if '2021' in labels:
            assert labels['2021'] - labels['2020'] < (labels['2030'] - labels['2020']) / 5
        plt.close(fig)

    def test_pandas_dates(self):
        pd = pytest.importorskip('pandas')
        fig = dc.stacked_area_chart(pd.date_range('2020-01-01', periods=3, freq='YS'), self.SERIES)
        assert [t.get_text() for t in self._x_labels(fig)] == ['2020', '2021', '2022']
        plt.close(fig)

    def test_unsorted_x_draws_the_same_chart_as_sorted(self):
        order = [2, 0, 1]
        shuffled = {k: [v[i] for i in order] for k, v in self.SERIES.items()}
        a = dc.stacked_area_chart([2000, 2010, 2020], self.SERIES)
        b = dc.stacked_area_chart([[2000, 2010, 2020][i] for i in order], shuffled)
        texts = lambda fig: sorted((round(t.get_position()[0], 6), t.get_text()) for t in fig.axes[0].texts)
        assert texts(a) == texts(b)
        plt.close(a)
        plt.close(b)

    def test_repeated_x_is_an_error(self):
        with pytest.raises(ValueError, match='repeated'):
            dc.stacked_area_chart([2000, 2000, 2010], self.SERIES)

    def test_a_hundred_points(self):
        n = 100
        series = {k: list(np.linspace(v[0], v[-1], n)) for k, v in self.SERIES.items()}
        fig = dc.stacked_area_chart(list(range(1900, 1900 + n)), series)
        assert fig.get_size_inches()[0] <= 11
        labels = self._x_labels(fig)
        assert '1999' in [t.get_text() for t in labels]
        label_x = sorted({t.get_position()[0] for t in labels})
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        left, right = self._area_edges_px(ax, 1900, 1999)
        # Every number is drawn in a column whose year is named: centred on
        # it, except in the first and last columns, where value labels are
        # kept flush with the edge of the drawn area, just inside it.
        for t in ax.texts:
            if not t.get_text().endswith('%'):
                continue
            v = t.get_position()[0]
            nearest = min(label_x, key=lambda x: abs(x - v))
            if abs(v - nearest) < 1e-6:
                continue
            box = t.get_window_extent(renderer)
            assert 0 < box.x0 - left < 10 or 0 < right - box.x1 < 10, (t.get_text(), v)
        assert _text_problems(fig) == []
        plt.close(fig)

    @staticmethod
    def _area_edges_px(ax, first_x, last_x):
        return ax.transData.transform((first_x, 0))[0], ax.transData.transform((last_x, 0))[0]

    @pytest.mark.parametrize('x', [[2000, 2010, 2020], list(range(1900, 2000)),
                                   [datetime.date(2024, m, 1) for m in (1, 2, 3, 4, 5, 6)]],
                             ids=['3 points', '100 points', 'dates'])
    def test_labels_stay_inside_the_drawn_area(self, x):
        # Labels near either end were clamped inside the plot, which has a
        # little padding beyond the drawn area, so they hung over the
        # area's border: white numbers on the cream background lost a
        # digit ("1,900" read ",900").
        n = len(x)
        series = {k: list(np.linspace(v[0] * 30, v[-1] * 30, n)) for k, v in self.SERIES.items()}
        fig = dc.stacked_area_chart(x, series)
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        if isinstance(x[0], datetime.date):
            import matplotlib.dates as mdates
            first, last = (mdates.date2num(datetime.datetime(d.year, d.month, d.day)) for d in (x[0], x[-1]))
        else:
            first, last = x[0], x[-1]
        left, right = self._area_edges_px(ax, first, last)
        top = ax.get_ylim()[1]
        inside = [t for t in ax.texts
                  if t.get_transform() is ax.transData and 0 <= t.get_position()[1] <= top]
        assert len(inside) >= 6          # band names and value labels
        for t in inside:
            box = t.get_window_extent(renderer)
            assert box.x0 >= left + 2 and box.x1 <= right - 2, (t.get_text(), box.x0 - left, right - box.x1)
        plt.close(fig)


class TestRegressionLongLabels:
    """
    One long label ballooned pie_chart to 24-26 inches and spiral_chart to
    17-19 inches (they scaled the whole figure to fit it on one line), and
    shrank every other category label in bar_chart and butterfly_chart to
    8pt. Long labels now wrap.
    """

    @pytest.mark.parametrize('chart, size', [('pie', (9, 9)), ('spiral', (7, 7.6))])
    def test_figure_keeps_its_size(self, chart, size):
        fig = ALL_CHARTS[chart](labels=[LONG, 'Beta', LONG + ' too', 'Delta'])
        assert tuple(np.round(fig.get_size_inches(), 1)) == size
        assert _text_problems(fig) == []
        plt.close(fig)

    @pytest.mark.parametrize('chart', ['bar', 'butterfly'])
    def test_one_long_label_does_not_shrink_the_rest(self, chart):
        fig = ALL_CHARTS[chart](labels=[LONG, 'Beta', 'Gamma', 'Delta'])
        sizes = {t.get_fontsize() for t in _texts(fig) if t.get_text() in ('Beta', 'Gamma', 'Delta')}
        assert sizes == {12.5}
        assert _text_problems(fig) == []
        plt.close(fig)


class TestRegressionPieOutsideLabels:
    """
    Outside labels sat at their wedge's own angle, so a cluster of thin
    wedges near 12 o'clock stacked its labels straight down across the
    biggest slice. They now go in a column on each side of the pie, spread
    up and down around their wedges. Room for the columns is reserved only
    when labels actually go outside, so a pie whose labels all fit inside
    fills its space, and a long name in a big slice stays inside it.
    """

    @staticmethod
    def _over_pie(fig):
        from matplotlib.patches import Wedge
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        wedge = next(p for p in ax.patches if isinstance(p, Wedge))
        inverse = ax.transData.inverted()
        over = []
        for t in ax.texts:
            if t.get_ha() in ('left', 'right'):
                b = t.get_window_extent(renderer)
                pts = inverse.transform([[x, y] for x in np.linspace(b.x0, b.x1, 12)
                                         for y in np.linspace(b.y0, b.y1, 5)])
                if np.any(np.hypot(*(pts - wedge.center).T) < wedge.r * 0.98):
                    over.append(t.get_text())
        return over

    @pytest.mark.parametrize('segments', [
        {**{f'{LONG} {i}': 1 for i in range(8)}, 'Big': 92},
        {**{f'Small {i}': 3 for i in range(15)}, 'Big': 55},
        {'Huge': 1e9, **{f'Tiny {i}': 1 for i in range(10)}},
        {f'Slice {i}': 1 + i % 5 for i in range(60)},
    ])
    @pytest.mark.filterwarnings('ignore:get_categorical')     # 60 colours: expected
    def test_outside_labels_never_cover_the_pie_or_each_other(self, segments):
        fig = dc.pie_chart(segments)
        assert self._over_pie(fig) == []
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_a_pie_with_every_label_inside_fills_its_space(self):
        from matplotlib.patches import Wedge
        fig = dc.pie_chart({'A': 50, 'B': 30, 'C': 20})
        ax = fig.axes[0]
        wedge = next(p for p in ax.patches if isinstance(p, Wedge))
        radius_px = wedge.r * ax.transData.get_matrix()[0, 0]
        assert radius_px > 0.4 * min(fig.bbox.width, fig.bbox.height)
        plt.close(fig)

    def test_words_are_never_broken_inside_a_wedge(self):
        fig = dc.pie_chart({'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5})
        words = {w for t in fig.axes[0].texts for w in t.get_text().split()}
        assert 'Divorced' in words
        plt.close(fig)

    LONG_NAMES = {'Agriculture, forestry and fishing': 62, 'Domestic and personal service': 28,
                  'Manufacturing and mechanical industries': 5, 'Trade and transportation': 2.5,
                  'Professions': 1.5, 'Other': 1}

    @staticmethod
    def _radius_px(fig):
        from matplotlib.patches import Wedge
        ax = fig.axes[0]
        wedge = next(p for p in ax.patches if isinstance(p, Wedge))
        return wedge.r * ax.transData.get_matrix()[0, 0]

    @pytest.mark.parametrize('figsize, smallest_radius', [((9, 9), 0.3), ((12, 6), 0.35), ((6, 10), 0.3)])
    def test_the_pie_uses_the_room_beside_its_labels(self, figsize, smallest_radius):
        # Room for a label column was reserved on both sides of the pie,
        # and above and below it, wherever the labels were: with every
        # outside label on the left, a 9-inch pie came out 3.5 inches across
        # beside an empty strip, and in a 12 x 6 figure it was a dot 0.5
        # inches across, with its labels printed on top of each other.
        fig = dc.pie_chart(self.LONG_NAMES, figsize=figsize)
        radius = self._radius_px(fig)
        shorter = min(fig.bbox.width, fig.bbox.height)
        assert radius > smallest_radius * shorter, (radius, shorter)
        assert self._over_pie(fig) == []
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_wrapped_outside_labels_are_balanced(self):
        fig = dc.pie_chart(self.LONG_NAMES)
        texts = [t.get_text() for t in fig.axes[0].texts if t.get_ha() in ('left', 'right')]
        # (2.5 is "3%": halves round up, as people round them.)
        assert 'Trade and\ntransportation 3%' in texts, texts
        plt.close(fig)


class TestRegressionSpiralForAnyData:
    """
    spiral_chart only ever tried labels right beside their point, so on a
    tightly wound 40-point spiral it drew one label of the nine it tried;
    at half a revolution a label was pushed off the page; and with a few
    points over many revolutions the curve, drawn with 14 samples between
    points however many turns that spanned, came out as a jagged star.
    """

    def test_forty_points_get_their_labels(self):
        fig = dc.spiral_chart([f'Item {i}' for i in range(40)], list(range(1, 41)))
        labels = [t.get_text() for t in fig.axes[0].texts]
        assert len(labels) >= 8
        assert any(t.startswith('Item 39') for t in labels)      # the last point
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_half_a_revolution_keeps_every_label_on_the_figure(self):
        fig = dc.spiral_chart(L4, V4, revolutions=0.5)
        assert len(fig.axes[0].texts) == 4
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_many_revolutions_draw_a_smooth_curve(self):
        fig = dc.spiral_chart(L4, V4, revolutions=12)
        curve = max(fig.axes[0].lines, key=lambda line: len(line.get_xdata()))
        assert len(curve.get_xdata()) >= 12 * 100
        plt.close(fig)


class TestRegressionUserSettings:
    """Charts keep their own look whatever the user has set in matplotlib."""

    @pytest.mark.parametrize('setting', [
        ('style', 'dark_background'), ('style', 'ggplot'),
        ('rc', {'font.size': 24}), ('rc', {'figure.dpi': 300}), ('rc', {'font.family': 'serif'}),
    ])
    @pytest.mark.parametrize('chart', list(ALL_CHARTS))
    def test_no_text_problems(self, setting, chart):
        kind, value = setting
        context = plt.style.context(value) if kind == 'style' else plt.rc_context(value)
        with context:
            fig = ALL_CHARTS[chart]()
            assert _text_problems(fig) == []
        plt.close(fig)


class TestRegressionLargeData:
    """
    Every chart with hundreds to thousands of points. Bar and butterfly
    charts drew 200 rows' labels at 12.5pt in 16px rows, on top of each
    other, and half off the top of the figure (a size whose one line was
    taller than the row still counted as fitting); a title on a figure
    taller than 20 inches overlapped the chart; a 200-slice pie's outside
    labels ran off the figure; a snake chart squeezed itself into a third
    of the figure for a legend at 100 segments and crashed from about 170.
    """

    @staticmethod
    def _walk(n, start=100.0):
        rng = np.random.default_rng(1)
        return list(np.maximum(1, start + np.cumsum(rng.normal(0, 3, n))).round(1))

    def test_label_rows(self):
        assert common.rows_to_label(10, 30, 20) == list(range(10))
        assert common.rows_to_label(10, 10, 20) == [0, 3, 6, 9]
        assert common.rows_to_label(11, 10, 20) == [0, 3, 6, 10]   # the last row always
        assert common.rows_to_label(0, 10, 20) == []

    def test_a_size_taller_than_the_row_does_not_fit(self):
        fig = plt.figure(dpi=150)
        fs, lines = common.fit_label_column(fig, ['Item 1', 'Item 2'], 400, 16, 'DejaVu Sans Mono')
        line_h = dc.text_utils.measure_text_px(fig, 'Xg', fs, 'DejaVu Sans Mono', 'bold')[1]
        assert line_h <= 0.95 * 16 or fs == 8.0
        plt.close(fig)

    def test_two_hundred_bars_each_get_a_label(self):
        fig = dc.bar_chart([f'Country {i}' for i in range(200)], self._walk(200),
                               title='Two hundred bars', texture=False)
        names = [t for t in fig.axes[0].texts if t.get_text().startswith('Country')]
        assert len(names) == 200
        assert _text_problems(fig) == []
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        title = next(t for t in fig.texts if t.get_text() == 'TWO HUNDRED BARS')
        assert title.get_window_extent(renderer).y0 >= fig.axes[0].get_window_extent(renderer).y1
        plt.close(fig)

    def test_a_thousand_bars_label_one_row_in_k(self):
        with pytest.warns(UserWarning, match='one row in'):
            fig = dc.bar_chart([f'Item {i}' for i in range(1000)], self._walk(1000), texture=False)
        names = [t.get_text() for t in fig.axes[0].texts if t.get_text().startswith('Item')]
        assert 'Item 0' in names and 'Item 999' in names and 100 < len(names) < 1000
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_grouped_bars_too_close_for_value_labels(self):
        values = {s: self._walk(100) for s in 'ABC'}
        with pytest.warns(UserWarning, match='too close for value labels'):
            fig = dc.bar_chart([f'Item {i}' for i in range(100)], values, texture=False)
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_two_hundred_butterfly_rows(self):
        fig = dc.butterfly_chart([f'Row {i}' for i in range(200)], self._walk(200), self._walk(200),
                                     texture=False)
        names = [t for t in fig.texts if t.get_text().startswith('Row')]
        assert len(names) == 200
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_two_hundred_pie_slices(self):
        segments = {f'Slice {i}': v for i, v in enumerate(self._walk(200, 10))}
        with pytest.warns(UserWarning):
            fig = dc.pie_chart(segments, texture=False)
        assert TestRegressionPieOutsideLabels._over_pie(fig) == []
        assert _text_problems(fig) == []
        plt.close(fig)

    @pytest.mark.parametrize('n', [100, 200])
    def test_a_snake_of_many_segments(self, n):
        segments = {f'Segment {i}': v for i, v in enumerate(self._walk(n, 10))}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fig = dc.snake_chart(segments, texture=False)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        legend = fig.legends[0].get_window_extent(renderer)
        snake = fig.axes[0].get_window_extent(renderer)
        assert legend.y0 >= -1 and legend.y1 <= snake.y0         # under the snake, on the figure
        assert snake.height >= 0.55 * fig.bbox.height           # the snake isn't squeezed
        assert _text_problems(fig) == []
        plt.close(fig)
