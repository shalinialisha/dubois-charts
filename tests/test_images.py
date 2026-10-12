"""
Image comparison: each chart below is drawn and compared, pixel by pixel,
with a reference image in tests/baseline/.

Every other test checks properties of a chart -- text on the figure, no
two labels overlapping, labels inside their shapes -- which can all hold
while a chart quietly changes look. These catch that. Until now the
comparison was made by hand, against renders kept from round to round.

A picture depends on the exact matplotlib (and the FreeType it was built
with), numpy and scipy (the texture), so the references are only compared
on the versions they were drawn with (tests/baseline/environment.json);
elsewhere these tests are skipped. The "Image comparison" job on GitHub
installs exactly the versions that file names, and fails rather than skips
if they still don't match. Every font but matplotlib's own is
hidden while the charts are drawn, so they're in DejaVu Sans Mono with
DejaVu Sans as the only fallback, whatever fonts a machine has.

After a deliberate change to how charts look, draw new references with

    python tests/test_images.py

and look at every one before committing them.
"""

import json
import os
import platform
import sys

import pytest
import numpy as np
import scipy
import matplotlib

HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(HERE))
    matplotlib.use('Agg')

import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib import ft2font                                   # noqa: E402

import dubois_charts as dc                                       # noqa: E402
from dubois_charts.charts._common import get_font                # noqa: E402

BASELINE = os.path.join(HERE, 'baseline')
FONT = 'DejaVu Sans Mono'
DPI = 72
TOLERANCE = 1.0          # root-mean-square difference of 0-255 pixel values


def _environment():
    return {'matplotlib': matplotlib.__version__, 'freetype': ft2font.__freetype_version__,
            'numpy': np.__version__, 'scipy': scipy.__version__}


# Data shared with other tests.

def _georgia_unemployment():
    from tests.test_choropleth import GA_UNEMPLOYMENT
    return GA_UNEMPLOYMENT


def _virginia():
    from tests.test_choropleth import _state_data
    return _state_data('VA', 4)


def _state_populations():
    from tests.test_country_maps import POP
    return POP


def _pie_for_colour_blind_readers():
    dc.set_colorblind_safe(True)
    try:
        return dc.pie_chart({'Agriculture': 30, 'Domestic service': 22, 'Manufacturing': 14,
                                 'Trade': 11, 'Transport': 9, 'Professions': 6, 'Mining': 5,
                                 'Other': 3}, title='Eight colours for every reader')
    finally:
        dc.set_colorblind_safe(False)


def _plate_51():
    from dubois_charts.charts.plate51 import create_plate_51
    return create_plate_51()


OCCUPATIONS = ['Agriculture', 'Domestic Service', 'Manufacturing', 'Trade', 'Professions']

CASES = {
    'bar': lambda: dc.bar_chart(
        OCCUPATIONS, [45, 25, 12, 10, 8], title='Occupations of Negroes in Georgia',
        value_format='{:.0f}%', sort_descending=True),
    'bar_grouped': lambda: dc.bar_chart(
        OCCUPATIONS[:4], {'Urban': [15, 30, 22, 20], 'Rural': [65, 15, 5, 8]},
        title='Occupations by Community Type', value_format='{:.0f}%'),
    'bar_negative': lambda: dc.bar_chart(
        ['Germany', 'France', 'Italy', 'Spain', 'Poland', 'Greece'],
        [-0.3, 0.9, 0.7, 2.5, 0.2, -1.1], title='Growth, Gains and Losses',
        value_format='{:+.1f}%'),
    'bar_forty_long_names': lambda: dc.bar_chart(
        [f'Category number {i} with a long name' for i in range(40)], list(range(40)),
        title='Forty rows with long names'),
    # The two cases of the first area-chart fixes (GENERAL_ENGINE_README.md,
    # "area.py"): one the fixes were made for -- a 130-character title, five
    # long series names, six long categories, thin bands -- and one with
    # short labels they weren't.
    'area_long_names_thin_bands': lambda: dc.stacked_area_chart(
        ['South Atlantic Coastal Plain', 'Piedmont and Upland South', 'Mississippi Delta Lowlands',
         'Appalachian Highlands', 'Gulf Coast and Lower Texas', 'Ozark and Ouachita Uplands'],
        {'Agricultural laborers and tenant farmers': [62, 55, 70, 48, 58, 52],
         'Domestic and personal service': [18, 20, 14, 16, 19, 17],
         'Manufacturing and mechanical industries': [8, 12, 5, 20, 10, 15],
         'Trade and transportation': [7, 8, 6, 9, 8, 9],
         'Professional service': [5, 5, 5, 7, 5, 7]},
        title='The Occupations of Wage Earners in Six Regions of the Southern States, as Returned '
              'by the Enumerators of the Twelfth Census, 1900'),
    'area_short_labels': lambda: dc.stacked_area_chart(
        [1890, 1900, 1910, 1920, 1930],
        {'Farm Ownership': [8, 13, 18, 22, 25], 'Tenant Farming': [55, 52, 48, 44, 40],
         'Wage Labor': [37, 35, 34, 34, 35]},
        title='Land Tenure Status Over Time',
        subtitle='Percentage of surveyed agricultural households'),
    'butterfly': lambda: dc.butterfly_chart(
        OCCUPATIONS[:2] + OCCUPATIONS[3:], [52, 38, 6, 4], [31, 55, 8, 6],
        left_label='Male', right_label='Female', title='Occupations by Sex'),
    'spiral': lambda: dc.spiral_chart(
        [1870, 1880, 1890, 1900, 1910, 1920], [45, 62, 89, 140, 210, 305],
        title='Population Growth Over Time', subtitle='Estimated population, in thousands'),
    'spiral_forty_points_tight': lambda: dc.spiral_chart(
        [str(1800 + 5 * i) for i in range(40)],
        [round(5 * (300 / 5) ** (i / 39), 1) for i in range(40)], title='Forty points'),
    'snake': lambda: dc.snake_chart(
        dict(zip(OCCUPATIONS, [45, 25, 12, 10, 8])), title='Occupations, Folded to Fit'),
    'pie': lambda: dc.pie_chart(
        {'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5}, title='Conjugal Condition'),
    'pie_twelve_long_names': lambda: dc.pie_chart(
        {f'A slice with a long name, number {i}': float(13 - i) for i in range(12)},
        title='Twelve slices'),
    'pie_colour_blind_safe': _pie_for_colour_blind_readers,
    'county_map_no_data': lambda: dc.county_map_chart(
        {'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61, 'Cobb': 70, 'Richmond': 48,
         'Muscogee': 58, 'Clarke': 66},
        title='Percentage Reporting Literacy, By County', colorbar_label='Percentage literate'),
    'county_map_rates': lambda: dc.county_map_chart(
        _georgia_unemployment(), title='Unemployment rate by county', label_top_n=12),
    'county_map_virginia_callouts': lambda: dc.county_map_chart(
        _virginia(), state='VA', label_top_n=15),
    'county_map_country': lambda: dc.county_map_chart(
        {'17031': 5.1, '48201': 4.3, '06037': 4.8}, title='Three counties'),
    'state_map': lambda: dc.state_map_chart(
        _state_populations(), title='Population by State, 2020',
        colorbar_label='Millions of residents'),
    'plate51': _plate_51,
}


def _draw(name, path):
    assert get_font() == FONT, 'every font but matplotlib\'s own should be hidden'
    fig = CASES[name]()
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)


def _baseline_environment():
    path = os.path.join(BASELINE, 'environment.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.parametrize('name', sorted(CASES))
def test_chart_looks_as_it_did(name, tmp_path, only_matplotlibs_fonts):
    from matplotlib.testing.compare import compare_images
    from matplotlib.testing.exceptions import ImageComparisonFailure
    expected = _baseline_environment()
    if expected is None:
        pytest.skip('no reference images yet: run python tests/test_images.py')
    here = _environment()
    if any(here[k] != expected.get(k) for k in here):
        message = f'the reference images were drawn with {expected}; this machine has {here}'
        if os.environ.get('DUBOIS_CHARTS_REQUIRE_IMAGE_TESTS'):     # set by the "Image comparison" job
            pytest.fail(message)
        pytest.skip(message)
    reference = os.path.join(BASELINE, f'{name}.png')
    if not os.path.exists(reference):
        pytest.fail(f'no reference image for {name}: run python tests/test_images.py')
    actual = str(tmp_path / f'{name}.png')
    _draw(name, actual)
    try:
        result = compare_images(reference, actual, tol=TOLERANCE)
    except ImageComparisonFailure as e:          # a different size, most often
        pytest.fail(f'{name} no longer looks as it did: {e}')
    assert result is None, f'{name} no longer looks as it did: {result}'


def test_every_reference_image_is_still_drawn():
    """A reference left behind by a renamed case would never be compared."""
    if not os.path.isdir(BASELINE):
        pytest.skip('no reference images yet')
    pngs = {f[:-4] for f in os.listdir(BASELINE) if f.endswith('.png')}
    assert pngs == set(CASES)


if __name__ == '__main__':
    from tests._fonts import matplotlibs_fonts_only
    os.makedirs(BASELINE, exist_ok=True)
    for old in os.listdir(BASELINE):
        if old.endswith('.png') and old[:-4] not in CASES:
            os.remove(os.path.join(BASELINE, old))
    with matplotlibs_fonts_only():
        for name in sorted(CASES):
            _draw(name, os.path.join(BASELINE, f'{name}.png'))
            print('drew', name)
    with open(os.path.join(BASELINE, 'environment.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(_environment(), python=platform.python_version()), f, indent=2)
        f.write('\n')
    print('environment:', _environment())
