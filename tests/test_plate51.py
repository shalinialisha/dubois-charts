"""
Tests for dubois_charts.charts.plate51 -- the pixel-verified historical
recreation of Du Bois' Plate 51.

Unlike the other four chart modules, this one is not meant to be
general-purpose (see GENERAL_ENGINE_README.md's "What's still specific
to plate51.py"), so these tests don't probe arbitrary-input robustness
the way test_area.py / test_bar.py / etc. do. What they guard against
instead is regressing the two things that made this module worth
rewriting in the first place:

  1. The ORIENTATION. The very first draft of this recreation had the
     chart inverted -- black (majority, "slaves") drawn as a small band
     and green (minority, "free") drawn as the dominant fill, exactly
     backwards from the real 1900 original. That mistake would not be
     caught by a test that only checks "does this run without raising"
     -- it produces a perfectly valid-looking chart, just a wrong one.
     TestOrientationRegression below renders the actual figure and
     samples real pixel colors at known (year, height) coordinates,
     the same verification technique used throughout this project's
     pixel analysis, specifically so a reintroduced inversion would be
     caught by running the tests, not by someone noticing the picture
     looks wrong.
  2. The tech-debt fixes from the most recent audit: cwd-dependent file
     paths that silently produced a blank comparison panel when this
     module was used from anywhere other than its own directory, and a
     misleading "ORIGINAL" label on that blank panel.
"""

import os
import warnings

import numpy as np
import pytest
import matplotlib.pyplot as plt

from dubois_charts.charts import plate51
from dubois_charts.charts._common import get_font as common_get_font


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = plate51.create_plate_51()
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_texture_and_jitter_toggle_independently(self):
        for add_texture in (True, False):
            for add_jitter in (True, False):
                fig = plate51.create_plate_51(add_texture=add_texture, add_jitter=add_jitter)
                assert isinstance(fig, plt.Figure)
                plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'plate51_test_output.png'
        fig = plate51.create_plate_51(save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestDataIntegrity:
    """
    The constants themselves, not the rendering -- a typo in these numbers
    would silently produce a confidently-wrong historical chart.
    """

    def test_years_slave_and_free_arrays_are_same_length(self):
        assert len(plate51.YEARS) == len(plate51.SLAVE_PCT) == len(plate51.FREE_PCT)

    def test_slave_and_free_sum_to_approximately_100_every_year(self):
        # Not an exact-100 assertion: the source archive's own data.csv
        # has 1800 as Slave=88 / Free=11, summing to 99, not 100. That
        # 1-point gap was verified against the actual drawn "11%" label
        # on the original plate (see PLATE51_README.md's pixel-tracing
        # methodology) rather than assumed to be a transcription slip --
        # Du Bois' team evidently rounded each column independently from
        # the underlying census fractions, which doesn't always sum to a
        # clean 100. Correcting it to force an exact 100 would trade
        # historical fidelity for a tidier invariant, which is the wrong
        # trade for a "pixel-verified" recreation. The tolerance here
        # exists to catch a *real* data-entry error (anything more than
        # rounding-scale) without flagging this known, verified exception.
        for yr, slave, free in zip(plate51.YEARS, plate51.SLAVE_PCT, plate51.FREE_PCT):
            assert slave + free == pytest.approx(100.0, abs=1.0), (
                f"Year {yr}: {slave} + {free} = {slave + free}, off by more "
                "than the known ~1-point historical rounding slack"
            )

    def test_slaves_are_the_majority_until_emancipation(self):
        # Every year except the last (1870, post-13th-Amendment) should
        # show slaves as the clear majority -- this is the whole reason
        # the chart reads as a heavy black mass with a thin green ribbon.
        for yr, slave, free in zip(plate51.YEARS[:-1], plate51.SLAVE_PCT[:-1], plate51.FREE_PCT[:-1]):
            assert slave > free, f"Year {yr}: expected slave% > free%, got {slave} vs {free}"

    def test_final_year_is_full_emancipation(self):
        assert plate51.SLAVE_PCT[-1] == 0.0
        assert plate51.FREE_PCT[-1] == 100.0
        assert plate51.YEARS[-1] == 1870


@pytest.fixture(scope='module')
def rendered_plate51(tmp_path_factory):
    out = tmp_path_factory.mktemp('plate51') / 'orientation_check.png'
    fig = plate51.create_plate_51(add_texture=False, add_jitter=False,
                                   save_path=str(out))
    plt.close(fig)
    from PIL import Image
    img = np.array(Image.open(out).convert('RGB'))
    return img, out


class TestOrientationRegression:
    """
    Regression coverage for the original inverted-axis bug: renders the
    actual figure and samples real pixel colors at known coordinates,
    rather than trusting the fill_between call arguments in isolation
    (which could themselves be silently swapped in a future edit without
    any test noticing, if the check stayed purely at the source-code
    level instead of the rendered-pixel level).
    """

    def test_bottom_of_chart_is_black_not_green(self, rendered_plate51):
        img, _ = rendered_plate51
        h, w, _ = img.shape
        # Near the bottom of the image, well inside the colored chart
        # area (not the cream margin), should be the near-black "slaves"
        # fill -- if orientation were ever inverted again, this would be
        # green instead.
        y = int(h * 0.9)
        x = int(w * 0.5)
        r, g, b = img[y, x]
        assert int(r) + int(g) + int(b) < 150, (
            f"Expected near-black at bottom-center, got RGB({r},{g},{b}) "
            "-- possible orientation regression (inverted axis)."
        )

    def test_top_of_colored_area_is_green_not_black(self, rendered_plate51):
        img, _ = rendered_plate51
        h, w, _ = img.shape
        # Just inside the top of the colored chart area (below the year
        # numerals, which sit above it) should be the green "free" fill.
        # The row also crosses the "FREE - LIBRE" lettering, so it's the
        # row's typical colour that counts: a single pixel at the centre
        # landed on the "I" with matplotlib 3.11's letter spacing.
        y = int(h * 0.32)
        r, g, b = np.median(img[y, int(w * 0.2):int(w * 0.8)], axis=0)
        # Green fill measured at #57845c -- g should clearly dominate r and b.
        assert g > r and g > b, (
            f"Expected green-dominant color near the top of the chart, got "
            f"RGB({r},{g},{b}) -- possible orientation regression."
        )

    def test_green_region_is_much_smaller_than_black_region(self, rendered_plate51):
        img, _ = rendered_plate51
        h, w, _ = img.shape
        # Sample a vertical strip through the middle of the chart (avoiding
        # text) and count green-ish vs black-ish pixels -- green should be
        # a small minority, matching "thin ribbon at the top" rather than
        # "dominant fill", for most of the chart's width.
        x = int(w * 0.15)  # left side, away from the SLAVES/ESCLAVES text
        column = img[int(h * 0.25):int(h * 0.95), x]
        greenish = np.sum((column[:, 1].astype(int) > column[:, 0].astype(int) + 15) &
                           (column[:, 1].astype(int) > column[:, 2].astype(int) + 15))
        blackish = np.sum(column.sum(axis=1) < 150)
        assert blackish > greenish * 3, (
            f"Expected black pixels to dominate this column ({blackish} black "
            f"vs {greenish} green) -- possible orientation regression."
        )


class TestVerifiedColors:
    """
    Guards against the specific pixel-sampled hex values (see the module
    docstring's methodology section) being "corrected" back to generic,
    unverified colors.
    """

    def test_colors_match_pixel_sampled_values(self):
        assert plate51.COLOR_GREEN == '#57845c'
        assert plate51.COLOR_BLACK == '#1d1d1d'

    def test_cream_background_matches_shared_common_value(self):
        from dubois_charts.charts._common import COLOR_CREAM
        assert plate51.COLOR_CREAM == COLOR_CREAM


class TestSharedInfrastructure:
    """
    Regression coverage for the tech-debt fix that removed plate51.py's
    own duplicate copy of `_get_font()` in favor of the shared
    `_common.get_font`. If a future edit reintroduces a local copy, this
    fails rather than silently drifting out of sync again.
    """

    def test_get_font_is_the_shared_common_implementation(self):
        assert plate51._get_font is common_get_font


class TestGeometryHelpers:
    def test_densify_preserves_endpoints(self):
        years = [1790, 1800, 1810]
        values = [10.0, 20.0, 30.0]
        xs, ys = plate51._densify(years, values, points_per_segment=5)
        assert xs[0] == years[0]
        assert ys[0] == values[0]
        assert xs[-1] == years[-1]
        assert ys[-1] == values[-1]

    def test_densify_x_is_monotonic(self):
        xs, _ = plate51._densify(plate51.YEARS, plate51.FREE_PCT, points_per_segment=10)
        assert np.all(np.diff(xs) >= 0)

    def test_jitter_leaves_endpoints_exact(self):
        y = np.linspace(0, 100, 50)
        x = np.linspace(1790, 1860, 50)
        jittered = plate51._hand_drawn_jitter(x, y, amplitude=1.0, seed=1)
        assert jittered[0] == y[0]
        assert jittered[-1] == y[-1]

    def test_jitter_does_not_move_points_far(self):
        y = np.linspace(0, 100, 50)
        x = np.linspace(1790, 1860, 50)
        jittered = plate51._hand_drawn_jitter(x, y, amplitude=0.3, seed=1)
        # Small amplitude should mean small deviation -- this should read
        # as a wobble, not a distortion of the underlying data.
        assert np.max(np.abs(jittered - y)) < 3.0

    def test_spaced_inserts_gaps_between_every_character(self):
        assert plate51._spaced('AB') == 'A B'
        assert plate51._spaced('SLAVES') == 'S L A V E S'


class TestSideBySideRegressionPathHandling:
    """
    Regression coverage for the tech-debt fixes to create_side_by_side's
    file-path handling: it used to default to a bare relative filename
    (cwd-dependent, silently produced a blank panel from any other
    working directory) and write its intermediate render to a bare
    filename in the cwd instead of a real temp file.
    """

    def test_default_reference_path_is_absolute(self):
        # A bare relative filename here would be the exact bug being
        # guarded against -- it must be anchored to the module's own
        # location, not left to resolve against whatever the caller's
        # cwd happens to be.
        assert os.path.isabs(plate51._DEFAULT_REFERENCE_PATH)

    def test_default_reference_path_exists(self):
        assert os.path.exists(plate51._DEFAULT_REFERENCE_PATH)

    def test_works_from_an_unrelated_working_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fig = plate51.create_side_by_side(save_path='comparison.png')
            plt.close(fig)
            # No warning should fire -- the reference image should still
            # be found via the module-relative default even though cwd
            # is now somewhere that has never heard of this package.
            assert not any('not found' in str(w.message) for w in caught)
        assert (tmp_path / 'comparison.png').exists()

    def test_missing_reference_image_warns_rather_than_failing_silently(self, tmp_path):
        with pytest.warns(UserWarning, match='not found'):
            fig = plate51.create_side_by_side(
                original_path=str(tmp_path / 'does_not_exist.jpg'),
                save_path=str(tmp_path / 'out.png'),
            )
            plt.close(fig)

    def test_intermediate_temp_file_is_cleaned_up(self, tmp_path):
        # The intermediate render used to be a bare filename in the cwd;
        # confirm no such artifact is left behind in the cwd after a call.
        before = set(os.listdir('.'))
        fig = plate51.create_side_by_side(save_path=str(tmp_path / 'out.png'))
        plt.close(fig)
        after = set(os.listdir('.'))
        assert after == before


class TestRegressionFigsizeValidation:
    """
    Regression coverage for a bug found by checking plate51.py against
    the same category of issue already fixed in all seven general chart
    functions: `create_plate_51` exposes `figsize` and `dpi` just like
    the others, but had never been wired up to `validate_figsize`. A
    degenerate figsize didn't fail immediately -- it failed later and
    more confusingly, inside PIL during `savefig`, as a bare
    `SystemError: tile cannot extend outside image` that names neither
    the input nor the real cause, discovered only once a save was
    actually attempted (a call without `save_path` didn't fail at all,
    making the underlying problem easy to miss).
    """

    def test_zero_figsize_raises_clearly(self):
        with pytest.raises(ValueError, match='positive'):
            plate51.create_plate_51(figsize=(0, 0))

    def test_negative_figsize_raises_clearly(self):
        with pytest.raises(ValueError, match='positive'):
            plate51.create_plate_51(figsize=(-5, 10))

    def test_zero_dpi_raises_clearly(self):
        with pytest.raises(ValueError, match='dpi'):
            plate51.create_plate_51(dpi=0)

    def test_valid_figsize_still_works(self):
        fig = plate51.create_plate_51(figsize=(8.0, 10.3))
        assert isinstance(fig, plt.Figure)
        plt.close(fig)
