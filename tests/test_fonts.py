"""
Tests of how the charts cope with the fonts a machine actually has.

Every chart had only been drawn with Liberation Mono, the Linux stand-in
for Courier. A Mac or a Windows machine has Courier New instead, and a
minimal one only the DejaVu fonts that ship with matplotlib; matplotlib
3.11 also began logging a warning whenever a fallback font lacked bold.
Drawing everything with other fonts found what's tested here.
"""

import logging

import pytest
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

import dubois_charts as dc
from dubois_charts import text_utils as tu
from dubois_charts.charts._common import get_font
from tests.test_choropleth import GA_UNEMPLOYMENT, _text_problems, _state_data

# only_matplotlibs_fonts, the fixture most of these use, is in conftest.py.


class TestRegressionFontChoice:

    def test_courier_new_is_preferred_to_dejavu(self, monkeypatch):
        # A Mac or Windows machine: Courier New, no Liberation fonts -- and
        # DejaVu Sans Mono, which matplotlib always has. DejaVu was tried
        # first, so Courier New was never used.
        entries = [f for f in fm.fontManager.ttflist if f.name == 'DejaVu Sans Mono']
        assert entries
        import dataclasses
        courier = dataclasses.replace(entries[0], name='Courier New')
        monkeypatch.setattr(fm.fontManager, 'ttflist', entries + [courier])
        assert get_font() == 'Courier New'

    def test_matplotlibs_own_monospace_when_there_is_nothing_else(self, only_matplotlibs_fonts):
        assert get_font() == 'DejaVu Sans Mono'

    def test_fallback_fonts_without_bold_are_not_logged(self):
        # matplotlib 3.11 logs this for every bold text drawn while a
        # regular-only CJK font is in the family list.
        logger = logging.getLogger('matplotlib.font_manager')

        def kept(name):
            record = logger.makeRecord(logger.name, logging.WARNING, __file__, 0,
                                       'findfont: Failed to find font weight %s for %s, now using %s.',
                                       ('bold', name, 400), None)
            return all(f.filter(record) for f in logger.filters)

        assert not kept('WenQuanYi Zen Hei')
        assert not kept('Noto Sans CJK JP')
        assert kept('Some Font Someone Chose')


class TestRegressionLabelSizeOnAPixel:
    """
    A map's labels share one size: 8pt when most fit, smaller only to
    fit most names. The test of "most" was a share of the names that fit
    at all -- and with a Courier whose 6pt text is a pixel shorter, two
    tiny Georgia counties started to fit at 6pt, the share at 8pt fell
    below 60%, and every label went to 6pt. It now counts callouts.
    """

    def test_a_pixel_does_not_shrink_every_label(self, monkeypatch):
        measure = tu.measure_text_px

        def one_pixel_shorter_at_6pt(fig, text, fontsize, *args, **kwargs):
            w, h = measure(fig, text, fontsize, *args, **kwargs)
            return (w, h - 1) if fontsize == 6 else (w, h)

        monkeypatch.setattr(tu, 'measure_text_px', one_pixel_shorter_at_6pt)
        fig = dc.county_map_chart(GA_UNEMPLOYMENT)
        assert {t.get_fontsize() for t in fig.axes[0].texts} == {8}
        plt.close(fig)


class TestEveryChartWithOnlyMatplotlibsFonts:
    """DejaVu Sans Mono is wider and taller than Courier: every chart must
    still lay out cleanly in it."""

    def test_bar(self, only_matplotlibs_fonts):
        names = [f'Category number {i} with a long name' for i in range(40)]
        fig = dc.bar_chart(names, list(range(40)), title='Forty rows with long names, in DejaVu')
        assert _text_problems(fig) == []

    @pytest.mark.filterwarnings('ignore:get_categorical')     # 30 colours: expected
    def test_pie(self, only_matplotlibs_fonts):
        fig = dc.pie_chart({f'Slice {i}': float(i + 1) for i in range(30)}, title='Thirty slices')
        assert _text_problems(fig) == []

    @pytest.mark.filterwarnings('ignore:get_categorical')     # 40 colours: expected
    def test_snake(self, only_matplotlibs_fonts):
        fig = dc.snake_chart({f'Segment {i}': float(i % 7 + 1) for i in range(40)},
                                 title='Forty segments')
        assert _text_problems(fig) == []

    def test_spiral(self, only_matplotlibs_fonts):
        fig = dc.spiral_chart([str(1870 + 10 * i) for i in range(8)],
                                  [45, 62, 89, 140, 210, 305, 420, 510], title='A spiral')
        assert _text_problems(fig) == []

    def test_area_and_butterfly(self, only_matplotlibs_fonts):
        fig = dc.stacked_area_chart(['1890', '1900', '1910', '1920'],
                                        {'Wage labour and day work': [37, 35, 34, 35],
                                         'Tenant farming': [55, 52, 48, 40],
                                         'Farm ownership': [8, 13, 18, 25]},
                                        title='Land tenure')
        assert _text_problems(fig) == []
        fig = dc.butterfly_chart(['Agriculture', 'Domestic service', 'Trade'], [52, 38, 6],
                                     [31, 55, 8], left_label='Male', right_label='Female')
        assert _text_problems(fig) == []

    def test_maps(self, only_matplotlibs_fonts):
        from tests.test_country_maps import POP
        for fig in (dc.county_map_chart(GA_UNEMPLOYMENT, label_top_n=12),
                    dc.state_map_chart(POP, label_top_n=15)):
            assert _text_problems(fig) == []

    def test_crowded_callouts_keep_their_lines_apart(self, only_matplotlibs_fonts):
        # In DejaVu, Virginia's King George, Caroline and Hanover were
        # stacked in reverse order, every pair of lines crossing, and no
        # two of the labels could trade places. They're now re-placed as
        # a group, in the order of their counties.
        from tests.test_country_maps import TestRegressionLeaderLinesDontCross
        fig = dc.county_map_chart(_state_data('VA', 4), state='VA', label_top_n=15)
        assert len(fig.axes[0].texts) == 15
        assert TestRegressionLeaderLinesDontCross._crossings(fig) == 0
        assert _text_problems(fig) == []
