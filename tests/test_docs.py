"""
The documentation, checked against the code: every Python example in
README.md runs, every example in a docstring gives the output it shows,
and every parameter of every chart is described in its docstring.

Before the first release, nine of the README's nineteen examples failed
when run as they were written (a missing import, or data they never
defined), several docstring examples showed output their code doesn't
give, and no chart's docstring described `background`, `dpi` or `font`.
"""

import doctest
import importlib
import inspect
import io
import os
import re
import warnings

import pytest
import matplotlib as mpl
import matplotlib.pyplot as plt

import dubois_charts as dc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, 'README.md')


def _readme_examples():
    if not os.path.exists(README):          # (not every copy of the tests has it)
        return []
    with open(README, encoding='utf-8') as f:
        return re.findall(r'```python\n(.*?)```', f.read(), re.S)


@pytest.mark.parametrize('number', range(len(_readme_examples())))
def test_readme_example_runs_as_written(number, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)              # where an example that saves a file saves it
    code = _readme_examples()[number]
    try:
        with mpl.rc_context(), warnings.catch_warnings():
            warnings.simplefilter('error')   # and without a warning
            exec(compile(code, f'README.md example {number + 1}', 'exec'), {'__name__': '__main__'})
    finally:
        dc.set_colorblind_safe(False)
        dc.themes.reset_theme()
        plt.close('all')


MODULES = ['dubois_charts', 'dubois_charts.colors', 'dubois_charts.themes',
           'dubois_charts.text_utils', 'dubois_charts.charts.bar', 'dubois_charts.charts.area',
           'dubois_charts.charts.butterfly', 'dubois_charts.charts.spiral',
           'dubois_charts.charts.snake', 'dubois_charts.charts.pie',
           'dubois_charts.charts.choropleth', 'dubois_charts.charts.plate51']


@pytest.mark.parametrize('name', MODULES)
def test_docstring_examples_give_what_they_show(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module(name)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
    report = io.StringIO()
    try:
        with mpl.rc_context(), warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for test in doctest.DocTestFinder().find(module, name):
                runner.run(test, out=report.write)
    finally:
        dc.set_colorblind_safe(False)
        dc.themes.reset_theme()
        plt.close('all')
    assert runner.failures == 0, report.getvalue()


def _described(function):
    names = set()
    for line in inspect.getdoc(function).splitlines():
        match = re.match(r'([a-z_]\w*(?:, [a-z_]\w*)*)(?: :|$)', line)
        if match:
            names.update(match.group(1).split(', '))
    return names


@pytest.mark.parametrize('chart', [dc.bar_chart, dc.stacked_area_chart, dc.butterfly_chart,
                                   dc.spiral_chart, dc.snake_chart, dc.pie_chart,
                                   dc.county_map_chart, dc.state_map_chart],
                         ids=lambda f: f.__name__)
def test_every_parameter_is_described(chart):
    described = _described(chart)
    if chart is dc.state_map_chart:          # "The other parameters are as for county_map_chart"
        described |= _described(dc.county_map_chart)
    missing = [p for p in inspect.signature(chart).parameters if p not in described]
    assert not missing, f'{chart.__name__} does not describe {missing}'
