"""
Tests for dubois_charts.charts.area.stacked_area_chart.

Structural/API tests here, not pixel-diffing -- the actual visual
correctness was established through the manual stress tests documented
in GENERAL_ENGINE_README.md (test1_dubois_like.png, test2_stress_long_
labels.png). These tests exist to catch *regressions*: making sure the
function still runs, still validates its input, and still produces
figures with the basic properties later code (or a user) would depend on,
as the package continues to grow.
"""

import numpy as np
import pytest
import matplotlib.pyplot as plt

from dubois_charts.charts.area import stacked_area_chart


BASIC_X = [1790, 1800, 1810, 1820]
BASIC_SERIES = {'Slaves': [92, 88, 86.5, 87], 'Free': [8, 11, 13.5, 13]}


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES,
                                  title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_many_series(self):
        series = {f'Series {i}': [10, 20, 15, 25] for i in range(6)}
        fig = stacked_area_chart(x=BASIC_X, series=series)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_string_categories(self):
        fig = stacked_area_chart(
            x=['North', 'South', 'East', 'West'],
            series={'A': [10, 20, 15, 25], 'B': [90, 80, 85, 75]},
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_two_x_points_minimum_case(self):
        fig = stacked_area_chart(x=[1, 2], series={'A': [10, 20], 'B': [90, 80]})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_texture_and_jitter_can_be_disabled(self):
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES,
                                  texture=False, hand_drawn=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_values_need_not_sum_to_100(self):
        # Explicitly documented as supported -- raw counts, not just
        # percentages.
        fig = stacked_area_chart(
            x=BASIC_X,
            series={'A': [1000, 2000, 1500, 2500], 'B': [500, 800, 700, 900]},
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestInputValidation:
    def test_single_x_point_raises(self):
        """
        Regression coverage for a bug found by rendering a single-point
        stacked_area_chart and looking at the result: it produced a
        nearly blank chart -- no fill, no band labels, no value labels,
        no error -- since an area chart fundamentally has no span to
        fill with only one x-position. Should raise clearly instead,
        the same way spiral_chart already does for its own minimum-
        points requirement.
        """
        with pytest.raises(ValueError, match='at least 2'):
            stacked_area_chart(x=[2020], series={'A': [30], 'B': [70]})


    def test_empty_series_raises(self):
        with pytest.raises(ValueError):
            stacked_area_chart(x=BASIC_X, series={})

    def test_mismatched_series_length_raises(self):
        with pytest.raises(ValueError):
            stacked_area_chart(x=BASIC_X, series={'A': [1, 2, 3]})  # only 3, x has 4

    def test_error_message_names_the_offending_series(self):
        with pytest.raises(ValueError, match='Oddball'):
            stacked_area_chart(x=BASIC_X, series={'Oddball': [1, 2]})


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Very Long Title That Goes On For Quite A While ' * 3
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_long_series_names_do_not_raise(self):
        series = {
            'A Rather Long Descriptive Series Name For Category One': [10, 20, 15, 25],
            'Another Quite Long Descriptive Series Name For Category Two': [90, 80, 85, 75],
        }
        fig = stacked_area_chart(x=BASIC_X, series=series)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_zero_values_do_not_raise(self):
        fig = stacked_area_chart(
            x=BASIC_X, series={'A': [0, 0, 0, 0], 'B': [100, 100, 100, 100]}
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_custom_colors_applied(self):
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES,
                                  colors=['#123456', '#abcdef'])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'area_test_output.png'
        fig = stacked_area_chart(x=BASIC_X, series=BASIC_SERIES, save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestRegressionNegativeValues:
    """
    Regression coverage for a bug found by rendering a negative value
    through stacked_area_chart: since stacking works by cumulatively
    summing each series, a negative component makes the running total
    decrease instead of grow, producing a band boundary that visibly
    dips at that point -- and silently dropping the value label there,
    with no error or other indication anything was wrong. Every other
    magnitude-based chart in the package (bar, butterfly, spiral, snake,
    pie) either already rejected negative values or was fixed to reject
    them in this same session; this brings stacked_area_chart in line.
    """

    def test_negative_value_raises(self):
        with pytest.raises(ValueError, match=r"Series 'A' at 2 \(-5\) is negative.*zero or more"):
            stacked_area_chart(x=[1, 2, 3], series={'A': [10, -5, 20], 'B': [50, 60, 40]})

    def test_negative_value_in_either_series_raises(self):
        with pytest.raises(ValueError, match=r"Series 'B' at 1 \(-5\).*zero or more"):
            stacked_area_chart(x=[1, 2], series={'A': [10, 20], 'B': [-5, 10]})


class TestRegressionConsistentBandLabelFontSize:
    """
    Regression coverage for the same bug found in county_map_chart,
    pie_chart, and snake_chart (see GENERAL_ENGINE_README.md): each
    band's label was fit independently, maximizing its own size against
    its own widest point. On a 3-series chart with varying band
    thickness, band labels came out at 16pt, 13.17pt, and 10.17pt
    respectively -- a 36% spread, and bold text at the smaller sizes
    renders with visibly thinner strokes than the same weight at the
    larger size, reading as a mismatched font even though nothing about
    the font had changed. Checked for here specifically because the
    same pattern had already been found three times elsewhere.
    """

    def test_all_placed_band_labels_share_one_font_size(self):
        fig = stacked_area_chart(
            x=[2018, 2019, 2020, 2021, 2022],
            series={
                'Dominant Category Group': [70, 72, 68, 74, 71],
                'A Somewhat Longer Category Name': [22, 20, 24, 18, 21],
                'An Even Longer Category Description Here': [8, 8, 8, 8, 8],
            },
        )
        ax = fig.axes[0]
        band_label_texts = {'DOMINANT CATEGORY GROUP', 'A SOMEWHAT LONGER',
                            'CATEGORY NAME', 'AN EVEN LONGER',
                            'CATEGORY DESCRIPTION HERE'}
        sizes = {round(t.get_fontsize(), 2) for t in ax.texts
                 if t.get_text() in band_label_texts}
        assert len(sizes) <= 1, f"Inconsistent band label sizes: {sizes}"
        plt.close(fig)

    def test_basic_stress_case_still_consistent(self):
        # The chart used throughout GENERAL_ENGINE_README.md's own
        # documentation -- confirm the fix didn't regress the
        # already-working case it was validated against there.
        fig = stacked_area_chart(
            x=['Northeast Region', 'Southeast Region', 'Midwest Region',
               'Southwest Region', 'Pacific Region', 'Mountain Region'],
            series={
                'Renewable Energy Sources': [12, 18, 9, 22, 30, 25],
                'Natural Gas Generation': [30, 35, 38, 22, 25, 20],
                'Coal-Fired Power Plants': [25, 22, 25, 8, 20, 24],
                'Nuclear Power Facilities': [28, 12, 14, 20, 7, 13],
                'Petroleum and Other': [5, 5, 4, 20, 18, 8],
            },
        )
        ax = fig.axes[0]
        band_names = {'RENEWABLE ENERGY SOURCES', 'NATURAL GAS GENERATION',
                      'COAL-FIRED POWER PLANTS', 'NUCLEAR POWER FACILITIES',
                      'PETROLEUM AND OTHER'}
        sizes = {round(t.get_fontsize(), 2) for t in ax.texts if t.get_text() in band_names}
        assert len(sizes) <= 1, f"Inconsistent band label sizes: {sizes}"
        plt.close(fig)


class TestRegressionSparseAndIrregularSeries:
    """
    Regression coverage for bugs found by running real data (U.S.
    electricity shares for 2001, 2022 and 2024) through the chart.

    Band names can only anchor on a real data point, so on a sparse
    series several names landed on the same column, and every value label
    they touched was dropped instead of moved: 7 of 12 were missing,
    including the current-year figures. Value labels now try positions
    above and below the band's middle, inside their own band, before
    giving up.

    Found alongside it: with irregular spacing (2000, then 2020-2023) the
    x labels were spaced as if the points were even, so 2020-2023 printed
    on top of each other, and neighbouring value labels overlapped too.
    """

    # Shares of US electricity generation (%). Minor sources are left out,
    # so the 2001 column adds up to 97 and the percent sign has to be asked
    # for: it's only automatic when every column adds up to 100.
    SPARSE = dict(x=[2001, 2022, 2024],
                  series={'Natural Gas': [17, 39.6, 43.4], 'Coal': [51, 19.3, 15.1],
                          'Nuclear': [20, 18.0, 18.1], 'Renewables': [9, 22.6, 23.4]},
                  value_format='{:.0f}%')
    IRREGULAR = dict(x=[2000, 2020, 2021, 2022, 2023],
                     series={'North': [30, 32, 33, 31, 30], 'South': [40, 38, 37, 39, 40],
                             'West': [30, 30, 30, 30, 30]})

    @staticmethod
    def _value_labels(fig):
        return [t for t in fig.axes[0].texts if t.get_text().endswith('%')]

    @staticmethod
    def _nearest_x(t, xs):
        pos = t.get_position()[0]
        return min(xs, key=lambda x: abs(x - pos))

    @staticmethod
    def _overlapping_pairs(fig):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        texts = [t for t in fig.axes[0].texts if t.get_text().strip() and not t.get_rotation()]
        boxes = [(t.get_text(), t.get_window_extent(renderer=renderer)) for t in texts]
        pairs = []
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                (na, ba), (nb, bb) = boxes[a], boxes[b]
                if (ba.x0 < bb.x1 - 0.5 and bb.x0 < ba.x1 - 0.5
                        and ba.y0 < bb.y1 - 0.5 and bb.y0 < ba.y1 - 0.5):
                    pairs.append((na, nb))
        return pairs

    def test_sparse_series_keeps_every_value_label(self):
        fig = stacked_area_chart(**self.SPARSE)
        assert len(self._value_labels(fig)) == 12
        plt.close(fig)

    def test_sparse_series_keeps_the_current_year_values(self):
        fig = stacked_area_chart(**self.SPARSE)
        at_2024 = sorted(t.get_text() for t in self._value_labels(fig)
                         if self._nearest_x(t, self.SPARSE['x']) == 2024)
        assert at_2024 == sorted(['43%', '15%', '18%', '23%'])
        plt.close(fig)

    def test_two_point_series_keeps_every_value_label(self):
        fig = stacked_area_chart(x=[2010, 2020], series={'Left': [40, 60], 'Right': [60, 40]})
        assert len(self._value_labels(fig)) == 4
        plt.close(fig)

    def test_moved_value_labels_stay_inside_their_own_band(self):
        fig = stacked_area_chart(**self.SPARSE, hand_drawn=False)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ax = fig.axes[0]
        inv = ax.transData.inverted()
        xs = np.array(self.SPARSE['x'], dtype=float)
        rows = np.array(list(self.SPARSE['series'].values()), dtype=float)
        cum = np.vstack([np.zeros(len(xs)), np.cumsum(rows, axis=0)])
        tol = (ax.get_ylim()[1] - ax.get_ylim()[0]) / ax.get_window_extent(renderer).height
        for t in self._value_labels(fig):
            bb = t.get_window_extent(renderer=renderer)
            (x0, y0), (x1, y1) = inv.transform((bb.x0, bb.y0)), inv.transform((bb.x1, bb.y1))
            inside = any(
                max(np.interp(x0, xs, cum[k]), np.interp(x1, xs, cum[k])) - tol <= y0
                and y1 <= min(np.interp(x0, xs, cum[k + 1]), np.interp(x1, xs, cum[k + 1])) + tol
                for k in range(len(rows)))
            assert inside, f"{t.get_text()!r} pokes outside every band"
        plt.close(fig)

    @pytest.mark.parametrize('case', ['SPARSE', 'IRREGULAR'])
    def test_no_text_overlaps(self, case):
        fig = stacked_area_chart(**getattr(self, case))
        assert self._overlapping_pairs(fig) == []
        plt.close(fig)

    def test_irregular_spacing_keeps_first_and_final_year_labels(self):
        fig = stacked_area_chart(**self.IRREGULAR)
        years = [t.get_text() for t in fig.axes[0].texts if t.get_text().isdigit()]
        assert years[0] == '2000' and years[-1] == '2023'
        plt.close(fig)

    def test_irregular_spacing_prints_no_values_under_unnamed_years(self):
        # Judged on the rendered page: every value label must sit
        # horizontally within the span of a year label that was actually
        # drawn. (Comparing data positions isn't enough -- values at the
        # last column are nudged inward to stay inside the frame.)
        fig = stacked_area_chart(**self.IRREGULAR)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        year_spans = [t.get_window_extent(renderer=renderer)
                      for t in fig.axes[0].texts if t.get_text().isdigit()]
        for t in self._value_labels(fig):
            bb = t.get_window_extent(renderer=renderer)
            cx = (bb.x0 + bb.x1) / 2
            assert any(ys.x0 - 4 <= cx <= ys.x1 + 4 for ys in year_spans), (
                f"{t.get_text()!r} is printed under a year whose label was dropped"
            )
        plt.close(fig)


class TestRegressionDisplayCapitals:
    """Band names and titles keep deliberate mixed case ("iOS") while
    ordinary words are still capitalised."""

    def test_band_name_keeps_brand_capitalisation(self):
        fig = stacked_area_chart(x=[2020, 2021, 2022], series={'Android': [70, 72, 73], 'iOS': [30, 28, 27]})
        names = {t.get_text() for t in fig.axes[0].texts}
        assert 'iOS' in names and 'ANDROID' in names, names
        assert 'IOS' not in names
        plt.close(fig)

    def test_title_keeps_brand_capitalisation(self):
        fig = stacked_area_chart(x=[2020, 2021], series={'A': [50, 60], 'B': [50, 40]},
                                 title='Mobile OS share: iOS vs Android')
        title_text = ' '.join(t.get_text() for t in fig.texts)
        assert 'iOS' in title_text and 'ANDROID' in title_text, title_text
        plt.close(fig)


class TestRegressionTextStaysInsideItsBand:
    """
    A band's name was centred on the band's middle at its thickest data
    point and checked only against the band's thinnest *thickness* under
    it -- not against where the band actually is. A sloping band can be
    thick enough all along a label and still leave it: in the long-names
    case below, "DOMESTIC AND PERSONAL SERVICE" printed across two bands
    and "TRADE AND TRANSPORTATION" dipped into the band beneath, and on 38
    of 40 random datasets some name or value sat partly in another band.
    Value labels had the same gap: the band's middle, their first choice,
    was never checked. Names now go where the band has room across their
    whole width, on two lines if one doesn't fit.
    """

    # GENERAL_ENGINE_README.md's adversarial case: a 130-character title,
    # five long series names, six long categories, thin bands.
    LONG_NAMES = dict(
        x=['South Atlantic Coastal Plain', 'Piedmont and Upland South', 'Mississippi Delta Lowlands',
           'Appalachian Highlands', 'Gulf Coast and Lower Texas', 'Ozark and Ouachita Uplands'],
        series={'Agricultural laborers and tenant farmers': [62, 55, 70, 48, 58, 52],
                'Domestic and personal service': [18, 20, 14, 16, 19, 17],
                'Manufacturing and mechanical industries': [8, 12, 5, 20, 10, 15],
                'Trade and transportation': [7, 8, 6, 9, 8, 9],
                'Professional service': [5, 5, 5, 7, 5, 7]},
        title='The Occupations of Wage Earners in Six Regions of the Southern States, as Returned '
              'by the Enumerators of the Twelfth Census, 1900')

    @staticmethod
    def _text_outside_its_band(fig):
        """Every name and value in the area that isn't wholly inside the
        band under its centre, read off the drawn chart: the band edges
        are the stroked boundary lines, the bottom and the frame's top."""
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        frame = max(ax.lines, key=lambda line: len(line.get_xdata()))
        n = len(frame.get_xdata()) - 5
        xs = np.asarray(frame.get_xdata(), float)[1:n + 1]
        top = np.asarray(frame.get_ydata(), float)[1:n + 1]
        inner = sorted((np.asarray(line.get_ydata(), float) for line in ax.lines
                        if len(line.get_xdata()) == n
                        and np.allclose(np.asarray(line.get_xdata(), float), xs)),
                       key=lambda edge: edge.mean())
        edges = [np.zeros(n)] + inner + [top]
        to_data = ax.transData.inverted()
        y_per_px = (ax.get_ylim()[1] - ax.get_ylim()[0]) / ax.get_window_extent(renderer).height
        problems = []
        for t in ax.texts:
            if t.get_rotation() or not t.get_text().strip():
                continue
            bb = t.get_window_extent(renderer)
            (x0, y0), (x1, y1) = to_data.transform((bb.x0, bb.y0)), to_data.transform((bb.x1, bb.y1))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not (xs[0] <= cx <= xs[-1] and 0 <= cy <= np.interp(cx, xs, top)):
                continue                                # an x label, outside the area
            band = next(k for k in range(len(edges) - 1)
                        if np.interp(cx, xs, edges[k]) <= cy <= np.interp(cx, xs, edges[k + 1]))
            under = np.concatenate(([x0, x1], xs[(xs > x0) & (xs < x1)]))
            floor = np.interp(under, xs, edges[band]).max()
            ceiling = np.interp(under, xs, edges[band + 1]).min()
            if y0 < floor - 0.5 * y_per_px or y1 > ceiling + 0.5 * y_per_px:
                problems.append(t.get_text())
        return problems

    @staticmethod
    def _random(seed):
        rng = np.random.default_rng(seed)
        n, k = int(rng.integers(3, 13)), int(rng.integers(2, 7))
        words = ['wage', 'labour', 'farm', 'tenant', 'service', 'trade', 'mining', 'other']
        series = {' '.join(rng.choice(words, int(rng.integers(1, 4)))) + f' {i}':
                  list(np.round(rng.gamma(2, 10, n) * rng.uniform(0.3, 2), 1)) for i in range(k)}
        return dict(x=list(range(1900, 1900 + 10 * n, 10)), series=series)

    def test_long_names_on_sloping_bands(self):
        fig = stacked_area_chart(**self.LONG_NAMES)
        assert self._text_outside_its_band(fig) == []

    def test_long_names_are_still_mostly_inside(self):
        # Not fixed by sending every name to the legend: as many inside as
        # the chart's own rule asks for, three of the five -- four, with
        # Liberation Mono, but three in the wider DejaVu Sans Mono.
        fig = stacked_area_chart(**self.LONG_NAMES)
        names = [t.get_text() for t in fig.axes[0].texts
                 if not t.get_rotation() and any(c.isalpha() for c in t.get_text())]
        assert len(names) >= 3, names

    @pytest.mark.parametrize('seed', range(12))
    def test_data_that_jumps_about(self, seed):
        fig = stacked_area_chart(**self._random(seed))
        assert self._text_outside_its_band(fig) == []

    def test_a_long_name_goes_on_two_lines_where_one_wont_fit(self):
        # The middle band is only thick around its peak.
        fig = stacked_area_chart([1890, 1900, 1910, 1920, 1930],
                                 {'Farm ownership': [30, 30, 30, 30, 30],
                                  'Manufacturing and mechanical industries': [4, 20, 60, 20, 4],
                                  'Wage labour': [30, 30, 10, 30, 30]})
        texts = [t.get_text() for t in fig.axes[0].texts]
        assert 'MANUFACTURING AND' in texts and 'MECHANICAL INDUSTRIES' in texts, texts
        assert self._text_outside_its_band(fig) == []
