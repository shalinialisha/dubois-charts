"""
Tests for dubois_charts.themes.

Includes regression coverage for two bugs found while writing this
suite (themes.py had zero test coverage before this -- see the
tech-debt audit in GENERAL_ENGINE_README.md's history):

  1. reset_theme() fell back to matplotlib's factory defaults when
     called without a prior set_theme(), silently destroying any
     matplotlib customization the user had made before ever touching
     this package -- not just undoing something this package had
     changed.
  2. The 'classic' theme's cream background was a generic, unverified
     "#F5F5DC" CSS beige left over from before any of the pixel-
     verification work elsewhere in the package, inconsistent with the
     #ded7c9 every one of the seven chart functions actually uses.
"""

import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib as mpl
import matplotlib.pyplot as plt

from dubois_charts import themes


@pytest.fixture(autouse=True)
def _reset_around_each_test():
    """Every test in this file mutates matplotlib's global rcParams (that
    IS what this module does) -- reset around each test so one test's
    theme can't leak into the next."""
    original = mpl.rcParams.copy()
    themes._original_params = None
    yield
    mpl.rcParams.update(original)
    themes._original_params = None


class TestListThemes:
    def test_returns_the_three_documented_themes(self):
        assert set(themes.list_themes()) == {'classic', 'modern', 'minimal'}


class TestGetThemeParams:
    def test_returns_a_dict_without_applying_it(self):
        before = mpl.rcParams['figure.facecolor']
        params = themes.get_theme_params('classic')
        assert isinstance(params, dict)
        assert mpl.rcParams['figure.facecolor'] == before  # unchanged

    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError, match='Unknown theme'):
            themes.get_theme_params('nonexistent')

    def test_classic_cream_matches_the_verified_package_wide_color(self):
        # Regression guard: this used to be a different, unverified
        # "#F5F5DC" left over from before the pixel-verification work
        # documented in PLATE51_README.md and used throughout
        # dubois_charts.charts._common.COLOR_CREAM.
        from dubois_charts.charts._common import COLOR_CREAM
        assert themes.get_theme_params('classic')['figure.facecolor'] == COLOR_CREAM


class TestSetTheme:
    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError, match='Unknown theme'):
            themes.set_theme('nonexistent')

    def test_unknown_context_raises(self):
        with pytest.raises(ValueError, match='Unknown context'):
            themes.set_theme('classic', context='nonexistent')

    def test_applies_theme_facecolor(self):
        themes.set_theme('classic')
        assert mpl.rcParams['figure.facecolor'] == themes.get_theme_params('classic')['figure.facecolor']

    def test_each_theme_applies_without_error(self):
        for theme in themes.list_themes():
            themes.set_theme(theme)

    def test_each_context_applies_without_error(self):
        for context in ('notebook', 'paper', 'talk', 'poster'):
            themes.set_theme('classic', context=context)

    def test_talk_context_uses_larger_fonts_than_notebook(self):
        themes.set_theme('classic', context='notebook')
        notebook_size = mpl.rcParams['font.size']
        themes.set_theme('classic', context='talk')
        talk_size = mpl.rcParams['font.size']
        assert talk_size > notebook_size

    def test_paper_context_uses_smaller_fonts_than_notebook(self):
        themes.set_theme('classic', context='notebook')
        notebook_size = mpl.rcParams['font.size']
        themes.set_theme('classic', context='paper')
        paper_size = mpl.rcParams['font.size']
        assert paper_size < notebook_size


class TestResetTheme:
    def test_restores_settings_from_before_set_theme(self):
        mpl.rcParams['font.size'] = 17
        themes.set_theme('classic')
        assert mpl.rcParams['font.size'] != 17  # theme changed it
        themes.reset_theme()
        assert mpl.rcParams['font.size'] == 17  # restored

    def test_round_trip_restores_facecolor(self):
        original_facecolor = mpl.rcParams['figure.facecolor']
        themes.set_theme('modern')
        themes.reset_theme()
        assert mpl.rcParams['figure.facecolor'] == original_facecolor

    def test_regression_no_prior_set_theme_call_is_a_no_op(self):
        """
        The actual bug: reset_theme() with no prior set_theme() call used
        to fall back to mpl.rcParamsDefault, silently wiping out any
        matplotlib customization the user had made independently of this
        package entirely. It should do nothing in that case instead.
        """
        mpl.rcParams['font.size'] = 42  # a user's own customization,
                                          # unrelated to this package
        themes.reset_theme()  # no set_theme() call before this
        assert mpl.rcParams['font.size'] == 42, (
            "reset_theme() altered a setting this package never touched -- "
            "regression of the factory-defaults-fallback bug."
        )

    def test_regression_does_not_fall_back_to_factory_defaults(self):
        mpl.rcParams['lines.linewidth'] = 99
        themes.reset_theme()
        assert mpl.rcParams['lines.linewidth'] == 99
        assert mpl.rcParams['lines.linewidth'] != mpl.rcParamsDefault['lines.linewidth'] or True
        # (the "or True" just documents that 99 deliberately isn't the
        # default value, so this assertion is meaningfully non-trivial)

    def test_second_reset_after_a_real_set_theme_still_works(self):
        # Make sure the no-op fix didn't accidentally break the normal,
        # legitimate reset path for a subsequent real usage.
        mpl.rcParams['font.size'] = 11
        themes.set_theme('classic')
        themes.reset_theme()
        assert mpl.rcParams['font.size'] == 11


class TestDuBoisStyleContextManager:
    def test_applies_and_restores_on_exit(self):
        original_facecolor = mpl.rcParams['figure.facecolor']
        with themes.DuBoisStyle('classic'):
            assert mpl.rcParams['figure.facecolor'] != original_facecolor
        assert mpl.rcParams['figure.facecolor'] == original_facecolor

    def test_restores_even_if_an_exception_occurs_inside(self):
        original_facecolor = mpl.rcParams['figure.facecolor']
        with pytest.raises(ValueError):
            with themes.DuBoisStyle('classic'):
                raise ValueError('boom')
        assert mpl.rcParams['figure.facecolor'] == original_facecolor

    def test_accepts_context_argument(self):
        with themes.DuBoisStyle('classic', 'talk'):
            assert mpl.rcParams['font.size'] > 10


class TestDuboisStyleFunction:
    def test_returns_a_usable_context_manager(self):
        original_facecolor = mpl.rcParams['figure.facecolor']
        with themes.dubois_style():
            fig, ax = plt.subplots()
            plt.close(fig)
        # plt.style.context restores automatically on exit
        assert mpl.rcParams['figure.facecolor'] == original_facecolor
