"""
Tests for the maps of the whole country: `state_map_chart`, and
`county_map_chart` drawing every county.

Before these, data by state, or county data from several states, drew an
empty map of Georgia with a warning -- and a county named with its state
("Cook County, Illinois") was silently matched to Georgia's county of
the same name.
"""

import math
import warnings

import numpy as np
import pytest
import matplotlib.pyplot as plt

import dubois_charts as dc
from dubois_charts.charts.choropleth import (
    county_map_chart, state_map_chart, STATES, _LOWER_48, _INSETS, _conic_equal_area,
    _load_us_counties, _country_states,
)
from tests.test_choropleth import _text_problems, _callouts


# Resident population by state, 2020 census, millions (rounded).
POP = {'CA': 39.5, 'TX': 29.1, 'FL': 21.5, 'NY': 20.2, 'PA': 13.0, 'IL': 12.8, 'OH': 11.8,
       'GA': 10.7, 'NC': 10.4, 'MI': 10.1, 'NJ': 9.3, 'VA': 8.6, 'WA': 7.7, 'AZ': 7.2,
       'MA': 7.0, 'TN': 6.9, 'IN': 6.8, 'MD': 6.2, 'MO': 6.2, 'WI': 5.9, 'CO': 5.8, 'MN': 5.7,
       'SC': 5.1, 'AL': 5.0, 'LA': 4.7, 'KY': 4.5, 'OR': 4.2, 'OK': 4.0, 'CT': 3.6, 'UT': 3.3,
       'IA': 3.2, 'NV': 3.1, 'AR': 3.0, 'MS': 2.96, 'KS': 2.9, 'NM': 2.1, 'NE': 1.96,
       'ID': 1.84, 'WV': 1.79, 'HI': 1.46, 'NH': 1.38, 'ME': 1.36, 'RI': 1.10, 'MT': 1.08,
       'DE': 0.99, 'SD': 0.89, 'ND': 0.78, 'AK': 0.73, 'DC': 0.69, 'VT': 0.64, 'WY': 0.58}
FIPS = {postal: fips for fips, (postal, _) in STATES.items()}
NAMES = {postal: name for postal, name in STATES.values()}
from dubois_charts.charts.choropleth import MISSING_COLOR
MISSING = MISSING_COLOR.lower()


def _labels(fig):
    return sorted(t.get_text() for t in fig.axes[0].texts)


def _filled(fig):
    return [p for p in fig.axes[0].patches if p.get_fill()]


def _project(lon, lat, state):
    project, k, (ox, oy) = _INSETS.get(state, _LOWER_48)
    x, y = project(np.array([lon]), np.array([lat]))
    return float(k * x[0] + ox), float(k * y[0] + oy)


class TestStateMapChart:

    @pytest.mark.parametrize('form', ['postal', 'name', 'lower', 'fips_int', 'fips_str', 'geo_id'])
    def test_every_form_of_state_key(self, form):
        key = {'postal': lambda p: p, 'name': lambda p: NAMES[p], 'lower': lambda p: NAMES[p].lower(),
               'fips_int': lambda p: int(FIPS[p]), 'fips_str': lambda p: FIPS[p],
               'geo_id': lambda p: f'0400000US{FIPS[p]}'}[form]
        data = {key(p): v for p, v in POP.items()}
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = state_map_chart(data)
        from matplotlib.colors import to_hex
        assert all(to_hex(p.get_facecolor()) != MISSING for p in _filled(fig))
        plt.close(fig)

    def test_dc_by_any_name(self):
        for key in ('District of Columbia', 'DC', 'D.C.', 'Washington, D.C.', '11'):
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                fig = state_map_chart({key: 1.0, 'MD': 2.0}, label_states=[key])
            assert _labels(fig) == ['District of Columbia'], key
            plt.close(fig)

    def test_keys_that_match_no_state_are_named(self):
        with pytest.warns(UserWarning, match=r"matched no state .*\['Californa', 'United States'\]"):
            state_map_chart({'Californa': 1.0, 'United States': 2.0, 'Texas': 3.0})
        with pytest.raises(ValueError, match='look like counties: .*county_map_chart'):
            state_map_chart({'06037': 1.0, '17031': 2.0})
        with pytest.warns(UserWarning, match="not on the map of the country"):
            state_map_chart(dict(POP, GU=0.17, VI=0.09))
        plt.close('all')

    def test_puerto_rico_only_when_the_data_have_it(self):
        without = state_map_chart(POP)
        with_pr = state_map_chart(dict(POP, PR=3.3), label_states=['PR'])
        assert len(_filled(with_pr)) > len(_filled(without))
        assert _labels(with_pr) == ['Puerto Rico']
        plt.close('all')

    def test_labels_and_callouts_draw_cleanly(self):
        for n in (6, 15, 51):
            fig = state_map_chart(POP, title='Population by state, 2020', colorbar_label='Millions',
                                  label_top_n=n)
            assert len(fig.axes[0].texts) == n
            assert _text_problems(fig) == []
            found, problems = _callouts(fig)
            assert problems == []
            plt.close(fig)

    def test_the_small_eastern_states_get_callouts(self):
        small = ['RI', 'DE', 'CT', 'NJ', 'MA', 'MD', 'NH', 'VT']
        fig = state_map_chart(POP, label_states=small)
        found, problems = _callouts(fig)
        assert problems == [] and sorted(name for name, _, _ in found) == sorted(NAMES[p] for p in small)
        plt.close(fig)

    def test_the_district_of_columbia_gets_a_dot(self):
        # Too small to see on the map; a dot in its colour shows it.
        fig = state_map_chart({'DC': 100.0, 'MD': 1.0, 'VA': 2.0}, n_classes=3)
        dots = [l for l in fig.axes[0].lines if len(l.get_xdata()) == 1 and l.get_markersize() > 4]
        assert len(dots) == 1
        assert dots[0].get_markerfacecolor() not in (MISSING,)
        plt.close(fig)

    def test_alaska_and_hawaii_are_inset_below_the_lower_48(self):
        anchorage = _project(-149.9, 61.2, '02')
        honolulu = _project(-157.86, 21.3, '15')
        san_diego, el_paso, seattle = (_project(-117.16, 32.72, '06'), _project(-106.49, 31.76, '48'),
                                       _project(-122.33, 47.61, '53'))
        assert anchorage[1] < san_diego[1] and honolulu[1] < san_diego[1]
        assert anchorage[0] < el_paso[0] and honolulu[0] < el_paso[0]
        assert seattle[1] > san_diego[1]

    def test_the_projection_is_equal_area(self):
        # Albers' projection keeps areas: a 1-degree cell's projected area
        # goes as the sine-difference of its latitudes.
        project = _conic_equal_area((29.5, 45.5), 96, (-0.6, 38.7))

        def cell_area(lat):
            lons = np.array([-90.0, -89.0, -89.0, -90.0])
            lats = np.array([lat, lat, lat + 1.0, lat + 1.0])
            fine = np.linspace(0, 1, 200)
            ring_lon = np.concatenate([lons[i] + (lons[(i + 1) % 4] - lons[i]) * fine for i in range(4)])
            ring_lat = np.concatenate([lats[i] + (lats[(i + 1) % 4] - lats[i]) * fine for i in range(4)])
            x, y = project(ring_lon, ring_lat)
            return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

        ratio = cell_area(30) / cell_area(45)
        expected = ((math.sin(math.radians(31)) - math.sin(math.radians(30)))
                    / (math.sin(math.radians(46)) - math.sin(math.radians(45))))
        assert ratio == pytest.approx(expected, rel=1e-4)

    def test_exported(self):
        assert dc.state_map_chart is state_map_chart
        assert dc.charts.state_map_chart is state_map_chart


class TestRegressionCountyDataFromSeveralStates:
    """
    County data from several states drew Georgia, with every key unmatched;
    a county named with its state matched Georgia's county of that name.
    """

    def test_fips_codes_from_several_states_draw_the_country(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart({'17031': 5.1, '48201': 4.3, '06037': 4.8})
        assert len(_filled(fig)) > 3000
        assert _labels(fig) == ['Cook, IL', 'Harris, TX', 'Los Angeles, CA']
        plt.close(fig)

    def test_names_with_their_state_draw_the_country(self):
        data = {'Cook County, Illinois': 5.1, 'Harris County, Texas': 4.3,
                'Los Angeles County, California': 4.8, 'Fulton County, Georgia': 3.9}
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(data)
        assert _labels(fig) == ['Cook, IL', 'Fulton, GA', 'Harris, TX', 'Los Angeles, CA']
        plt.close(fig)

    def test_names_with_one_state_draw_that_state(self):
        data = {'Cook County, Illinois': 5.1, 'Lake County, Illinois': 3.0, 'DuPage County, IL': 4.0}
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(data)
        assert len(_filled(fig)) == 102                      # Illinois' counties
        assert _labels(fig) == ['Cook', 'DuPage', 'Lake']
        plt.close(fig)

    def test_another_states_county_is_not_georgias(self):
        # Georgia has a Cook County too: Illinois's used to be drawn there.
        from matplotlib.colors import to_hex
        with pytest.warns(UserWarning, match=r"\['Cook County, Illinois'\].*state='US'"):
            fig = county_map_chart({'Cook County, Illinois': 5.0, 'Fulton': 3.0, 'Bibb': 4.0},
                                   label_counties=['Cook', 'Fulton'])
        texts = {t.get_text() for t in fig.axes[0].texts}
        assert texts == {'Cook', 'Fulton'}
        from dubois_charts.charts.choropleth import _load_counties, _DEFAULT_GEOJSON_PATH
        names = [c['name'] for c in _load_counties(_DEFAULT_GEOJSON_PATH)]
        cook = fig.axes[0].patches[names.index('Cook')]
        assert to_hex(cook.get_facecolor()) == MISSING
        plt.close(fig)

    def test_bare_names_on_the_country_map_say_why(self):
        with pytest.warns(UserWarning, match='give the state too'):
            county_map_chart({'Cook': 5.0, 'Harris': 3.0, '17031': 4.0}, state='US')
        with pytest.raises(ValueError, match='give the state too'):
            county_map_chart({'Cook': 5.0, 'Harris': 3.0}, state='US')
        plt.close('all')

    def test_states_given_to_county_map_chart_point_to_state_map_chart(self):
        with pytest.warns(UserWarning, match='state_map_chart'):
            county_map_chart({'California': 5.0, 'Texas': 3.0, 'Fulton': 2.0}, state='GA')
        with pytest.raises(ValueError, match='state_map_chart'):
            county_map_chart({'California': 5.0, 'Texas': 3.0})
        plt.close('all')

    def test_puerto_rico_when_the_data_have_it(self):
        fig = county_map_chart({'72127': 5.0, '06037': 3.0, '36061': 4.0})
        assert 'San Juan, PR' in _labels(fig)
        plt.close(fig)

    def test_every_county_draws_cleanly(self):
        counties = _load_us_counties(_country_states(set()))
        rng = np.random.default_rng(5)
        data = {c['geoid']: float(rng.gamma(3, 2)) for c in counties}
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(data, title='A rate by county', colorbar_label='Rate',
                                   label_top_n=10)
        assert len(fig.axes[0].texts) == 10
        # No county's name fits inside it at this scale: every label is a
        # callout, at 9pt rather than the 11pt nothing would otherwise stop.
        assert {t.get_fontsize() for t in fig.axes[0].texts} == {9}
        assert _text_problems(fig) == []
        found, problems = _callouts(fig)
        assert len(found) == 10 and problems == []
        plt.close(fig)


class TestRegressionLeaderLinesDontCross:
    """
    Callouts were placed one at a time, each at the spot nearest its
    county, so a later label's leader line could cross an earlier one's:
    with 15 labels, 9 of the 56 state maps had lines crossing. Spots whose
    line would cross another now cost a little more, and lines that still
    cross get their labels swapped or one of them moved.
    """

    @staticmethod
    def _crossings(fig):
        def side(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        lines = [l.get_xydata() for l in fig.axes[0].lines if len(l.get_xdata()) == 2]
        return sum(side(q[0], q[1], p[0]) * side(q[0], q[1], p[1]) < 0
                   and side(p[0], p[1], q[0]) * side(p[0], p[1], q[1]) < 0
                   for i, p in enumerate(lines) for q in lines[i + 1:])

    @pytest.mark.parametrize('state, seed', [('TN', 1), ('TN', 5), ('CA', 3), ('VA', 2),
                                             ('VA', 4), ('KY', 3)])
    def test_no_two_leader_lines_cross(self, state, seed):
        from tests.test_choropleth import _state_data
        fig = county_map_chart(_state_data(state, seed), state=state, label_top_n=15)
        assert len(fig.axes[0].texts) == 15
        assert self._crossings(fig) == 0
        assert _text_problems(fig) == []
        found, problems = _callouts(fig)
        assert problems == []
        plt.close(fig)
