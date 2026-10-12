"""
Tests for dubois_charts.charts.choropleth.county_map_chart.

This is the one chart in the package whose shapes come from the outside
world (real Georgia county boundaries) rather than being computed by the
chart itself, so a meaningful slice of these tests check data-integrity
properties (does the bundled file actually have 159 counties, does name
matching handle real-world spelling variance) alongside the usual
structural and regression coverage.

Includes a regression test for a layout bug found by looking at the
actual rendered figure: a guessed-at "+1.6 inches" fudge factor for
title and colorbar space left a large blank gap between the map and its
colorbar, because `set_aspect('equal')` silently shrinks the rendered
map to fit whichever dimension of its allocated box is more
constraining. Fixed by solving for the exact required figure height
instead of guessing it.
"""

import math
import os
import warnings

import pytest
import numpy as np
import matplotlib.pyplot as plt

from dubois_charts.charts.choropleth import (
    county_map_chart, _load_counties, _normalize_name, _DEFAULT_GEOJSON_PATH,
)


SAMPLE_DATA = {'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61}


class TestBundledData:
    """The data-integrity checks specific to this chart type: is the
    thing being rendered actually correct, independent of any rendering
    logic."""

    def test_default_geojson_path_is_absolute(self):
        assert os.path.isabs(_DEFAULT_GEOJSON_PATH)

    def test_default_geojson_exists(self):
        assert os.path.exists(_DEFAULT_GEOJSON_PATH)

    def test_loads_159_georgia_counties(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        assert len(counties) == 159

    def test_every_county_has_a_nonempty_polygon(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        for c in counties:
            assert len(c['rings']) > 0
            assert len(c['rings'][0]) >= 3  # a polygon needs at least 3 points

    def test_known_counties_present(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        names = {c['name'] for c in counties}
        for expected in ('Fulton', 'DeKalb', 'Chatham', 'Bibb', 'Cobb'):
            assert expected in names


class TestNameNormalization:
    def test_case_insensitive(self):
        assert _normalize_name('FULTON') == _normalize_name('fulton')

    def test_strips_county_suffix(self):
        assert _normalize_name('Fulton County') == _normalize_name('Fulton')

    def test_strips_spacing_and_punctuation(self):
        assert _normalize_name('De Kalb') == _normalize_name('DeKalb')

    def test_different_counties_normalize_differently(self):
        assert _normalize_name('Fulton') != _normalize_name('Bibb')


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = county_map_chart(data=SAMPLE_DATA)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = county_map_chart(data=SAMPLE_DATA, title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_name_variants_all_match(self):
        # 'DeKalb', 'de kalb county', and 'DEKALB COUNTY' should all
        # resolve to the same county without raising a warning.
        for key in ('DeKalb', 'de kalb county', 'DEKALB COUNTY'):
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                fig = county_map_chart(data={key: 1, 'Fulton': 2}, state='GA', label_counties=[key])
            assert 'DeKalb' in {t.get_text() for t in fig.axes[0].texts}, key
            plt.close(fig)

    def test_two_spellings_of_one_county_are_two_values_for_it(self):
        with pytest.raises(ValueError, match=r"two values for DeKalb: 'DeKalb' and 'de kalb county'"):
            county_map_chart(data={'DeKalb': 1, 'de kalb county': 2}, state='GA')

    def test_single_county(self):
        fig = county_map_chart(data={'Fulton': 50}, state='GA')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_all_counties(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        data = {c['name']: i % 100 for i, c in enumerate(counties)}
        fig = county_map_chart(data=data, label_top_n=0)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_colorbar_can_be_disabled(self):
        fig = county_map_chart(data=SAMPLE_DATA, show_colorbar=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_custom_label_counties(self):
        fig = county_map_chart(data=SAMPLE_DATA, label_counties=['Fulton', 'Bibb'])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_zero_label_top_n_disables_labels(self):
        fig = county_map_chart(data=SAMPLE_DATA, label_top_n=0)
        ax = fig.axes[0]
        assert len(ax.texts) == 0
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'choropleth_test_output.png'
        fig = county_map_chart(data=SAMPLE_DATA, save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestUnmatchedNameHandling:
    def test_regression_label_counties_typo_warns(self):
        """
        Regression coverage: `data`'s unmatched-name handling warns, but
        `label_counties`'s did not -- a typo there used to silently
        result in no label at all, with nothing to distinguish it from
        "this county's shape was just too small or irregular to hold a
        label," which is normal, expected, and not worth a warning.
        Fixed to use the same name-matching warning `data` already had,
        since a typo is a different situation from a shape genuinely
        not having room.
        """
        with pytest.warns(UserWarning, match='did not match'):
            fig = county_map_chart(data={'Fulton': 50}, state='GA',
                                    label_counties=['Not A Real County'])
            plt.close(fig)


    def test_unmatched_name_warns(self):
        with pytest.warns(UserWarning, match='did not match'):
            fig = county_map_chart(data={'Fulton': 50, 'Not A Real County': 10})
            plt.close(fig)

    def test_unmatched_name_does_not_raise(self):
        # A warning, not a crash -- the rest of the data should still render.
        with pytest.warns(UserWarning, match='Not A Real County'):
            fig = county_map_chart(data={'Fulton': 50, 'Not A Real County': 10})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_valid_entries_still_render_alongside_a_typo(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fig = county_map_chart(data={'Fulton': 82, 'Fultonn Countyy': 50})
        ax = fig.axes[0]
        # At least one polygon should be colored per the palette (not
        # everything silently falling back to missing_color).
        colors_used = {tuple(p.get_facecolor()) for p in ax.patches}
        assert len(colors_used) >= 1
        plt.close(fig)


class TestRegressionLayoutGap:
    """
    Regression coverage for the figure-sizing bug: a guessed height
    reservation for title+colorbar left a large blank gap between the
    map and the colorbar, because the axes' equal-aspect constraint
    shrinks the rendered map to fit its allocated box rather than
    filling whatever box it's given. Checked by verifying the map's
    actual rendered patches extend close to both the top and bottom of
    their allocated axes region, not clustered in only part of it.
    """

    def test_map_fills_its_vertical_allocation(self):
        fig = county_map_chart(data=SAMPLE_DATA, title='A Title')
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        axes_bbox = ax.get_window_extent(renderer=renderer)
        patch_bboxes = [p.get_window_extent(renderer=renderer) for p in ax.patches]
        content_top = max(b.y1 for b in patch_bboxes)
        content_bottom = min(b.y0 for b in patch_bboxes)
        # The map's rendered content should occupy the large majority of
        # its allocated axes box vertically, not leave it mostly empty.
        axes_height = axes_bbox.height
        content_height = abs(content_top - content_bottom)
        assert content_height > axes_height * 0.85, (
            f"Map content only fills {content_height / axes_height:.0%} of its "
            "allocated vertical space -- possible layout-gap regression."
        )
        plt.close(fig)

    def test_no_large_blank_band_between_map_and_colorbar(self, tmp_path):
        from PIL import Image
        out = tmp_path / 'gap_check.png'
        fig = county_map_chart(data=SAMPLE_DATA, title='A Title', show_colorbar=True,
                                save_path=str(out))
        plt.close(fig)

        img = np.array(Image.open(out).convert('RGB'))
        bg = np.array([222, 215, 201])  # the cream background, approximately
        diff = np.abs(img.astype(int) - bg).sum(axis=2)
        row_has_content = (diff > 30).any(axis=1)
        content_rows = np.where(row_has_content)[0]
        # Find the longest run of entirely-blank rows within the
        # content's own vertical span -- a large gap here is exactly
        # the symptom the original bug produced.
        span = row_has_content[content_rows.min():content_rows.max()]
        blank_run = 0
        longest_blank_run = 0
        for has_content in span:
            if not has_content:
                blank_run += 1
                longest_blank_run = max(longest_blank_run, blank_run)
            else:
                blank_run = 0
        total_span = content_rows.max() - content_rows.min()
        assert longest_blank_run < total_span * 0.15, (
            f"Found a blank vertical band {longest_blank_run}px long within "
            f"a {total_span}px content span -- possible layout-gap regression."
        )


class TestRegressionLabelShrinkRetry:
    """
    Regression coverage for the label-yield fix: the first version tried
    each candidate label exactly once against an axis-aligned-bounding-
    box estimate, which is frequently too generous for Georgia's often
    elongated or diagonal county shapes, so most requested labels were
    silently skipped even though a smaller size would have fit. Fixed
    with the same shrink-and-retry loop already used by pie_chart's
    wedge labels.
    """

    def test_dense_data_labels_a_reasonable_fraction_of_requested_counties(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        data = {c['name']: i for i, c in enumerate(counties)}
        fig = county_map_chart(data=data, label_top_n=10)
        ax = fig.axes[0]
        placed = len(ax.texts)
        assert placed >= 5, (
            f"Only {placed}/10 requested county labels placed -- "
            "possible regression of the shrink-and-retry fix."
        )
        plt.close(fig)


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Considerably Long Title For A Choropleth Map About County Statistics ' * 2
        fig = county_map_chart(data=SAMPLE_DATA, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_uniform_values_do_not_raise(self):
        # Every county the same value -- degenerate quantile breaks.
        fig = county_map_chart(data={'Fulton': 50, 'Bibb': 50, 'Cobb': 50})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_custom_palette(self):
        fig = county_map_chart(data=SAMPLE_DATA, palette='green')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_custom_n_classes(self):
        fig = county_map_chart(data=SAMPLE_DATA, n_classes=3)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestRegressionConsistentLabelFontSize:
    """
    Regression coverage for a bug reported directly against a rendered
    example, not found by automated stress-testing: "Bibb" and "Cobb"
    labels on the same map didn't visually match. Both were technically
    bold and the same font family, but each county's label had
    independently maximized its own font size against its own polygon
    shape -- Cobb's more constrained shape came out around 6.6pt, Bibb's
    around 10.2pt. Bold text at the smaller size renders with visibly
    thinner, spindlier strokes than the same weight at the larger size,
    reading as a mismatched font on the same map even though neither the
    font family nor the weight had actually changed. Fixed by solving
    for one shared font size across every label on the map. Counties
    whose shape can't hold that shared size were at first dropped; they
    now get a callout outside the state at the same size (see
    TestRegressionLabelPlacement) -- never a size of their own.
    """

    def test_all_rendered_labels_share_one_font_size(self):
        data = {'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61,
                'Cobb': 70, 'Richmond': 48, 'Muscogee': 58, 'Clarke': 66}
        fig = county_map_chart(data=data)
        ax = fig.axes[0]
        sizes = {round(t.get_fontsize(), 3) for t in ax.texts}
        assert len(sizes) <= 1, f"Labels rendered at inconsistent sizes: {sizes}"
        plt.close(fig)

    def test_all_rendered_labels_are_bold(self):
        data = {'Fulton': 82, 'DeKalb': 74, 'Bibb': 61, 'Cobb': 70}
        fig = county_map_chart(data=data)
        ax = fig.axes[0]
        for t in ax.texts:
            assert t.get_fontweight() == 'bold'
        plt.close(fig)

    def test_specific_bibb_and_cobb_case_matches(self):
        # The exact configuration that was originally reported.
        data = {'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61,
                'Cobb': 70, 'Richmond': 48, 'Muscogee': 58, 'Clarke': 66}
        fig = county_map_chart(data=data)
        ax = fig.axes[0]
        by_name = {t.get_text(): t for t in ax.texts}
        if 'Bibb' in by_name and 'Cobb' in by_name:
            assert by_name['Bibb'].get_fontsize() == by_name['Cobb'].get_fontsize()
            assert by_name['Bibb'].get_fontweight() == by_name['Cobb'].get_fontweight()
        plt.close(fig)


# Georgia county unemployment rates (%), from the Bureau of Labor Statistics'
# Local Area Unemployment Statistics as republished by zipdatamaps.com; the
# real data the label bugs below were found on. Names as the source spells
# them ("Mcduffie", "Mcintosh"), which the loose name-matching handles.
_GA_UNEMPLOYMENT_RAW = """Appling 4.2, Atkinson 3.3, Bacon 3.2, Baker 3.9, Baldwin 3.7, Banks 2.8,
Barrow 2.7, Bartow 2.9, Ben Hill 4.0, Berrien 2.8, Bibb 4.3, Bleckley 3.4, Brantley 2.8, Brooks 3.7,
Bryan 2.6, Bulloch 3.6, Burke 5.4, Butts 3.3, Calhoun 3.0, Camden 3.0, Candler 3.0, Carroll 3.1,
Catoosa 2.9, Charlton 3.0, Chatham 2.8, Chattahoochee 6.9, Chattooga 4.0, Cherokee 2.6, Clarke 3.2,
Clay 5.9, Clayton 4.2, Clinch 3.7, Cobb 3.0, Coffee 3.6, Colquitt 3.0, Columbia 3.1, Cook 3.1,
Coweta 2.9, Crawford 3.4, Crisp 3.4, Dade 3.0, Dawson 2.6, Decatur 3.4, DeKalb 3.4, Dodge 3.1,
Dooly 3.7, Dougherty 4.6, Douglas 3.5, Early 4.7, Echols 2.6, Effingham 2.6, Elbert 3.2, Emanuel 3.9,
Evans 3.2, Fannin 2.8, Fayette 3.1, Floyd 3.1, Forsyth 2.6, Franklin 3.6, Fulton 3.4, Gilmer 2.7,
Glascock 3.0, Glynn 2.7, Gordon 3.0, Grady 2.9, Greene 3.3, Gwinnett 3.0, Habersham 2.8, Hall 2.7,
Hancock 4.7, Haralson 3.1, Harris 2.9, Hart 3.1, Heard 3.3, Henry 3.7, Houston 2.9, Irwin 3.5,
Jackson 3.0, Jasper 3.2, Jeff Davis 4.4, Jefferson 4.4, Jenkins 2.9, Johnson 3.7, Jones 3.0,
Lamar 4.4, Lanier 3.2, Laurens 3.5, Lee 2.7, Liberty 3.8, Lincoln 3.8, Long 3.4, Lowndes 3.7,
Lumpkin 3.3, Macon 4.4, Madison 3.0, Marion 3.6, Mcduffie 4.2, Mcintosh 3.2, Meriwether 3.9,
Miller 3.0, Mitchell 3.8, Monroe 2.8, Montgomery 4.8, Morgan 2.7, Murray 3.4, Muscogee 4.0,
Newton 3.8, Oconee 2.5, Oglethorpe 2.7, Paulding 3.1, Peach 3.8, Pickens 2.7, Pierce 3.4, Pike 2.9,
Polk 3.1, Pulaski 3.4, Putnam 3.4, Quitman 6.1, Rabun 2.9, Randolph 3.8, Richmond 4.8, Rockdale 3.8,
Schley 3.5, Screven 4.2, Seminole 4.3, Spalding 3.7, Stephens 4.2, Stewart 5.2, Sumter 4.5,
Talbot 4.0, Taliaferro 3.1, Tattnall 3.6, Taylor 4.0, Telfair 4.8, Terrell 4.4, Thomas 3.2, Tift 3.1,
Toombs 4.5, Towns 3.2, Treutlen 4.2, Troup 2.9, Turner 3.9, Twiggs 4.3, Union 3.4, Upson 3.8,
Walker 3.0, Walton 3.0, Ware 4.2, Warren 4.1, Washington 3.3, Wayne 3.2, Webster 4.1, Wheeler 2.7,
White 2.7, Whitfield 3.7, Wilcox 3.0, Wilkes 3.6, Wilkinson 4.1, Worth 3.5"""
GA_UNEMPLOYMENT = {name + ' County': float(value) for name, value in
                   (item.strip().rsplit(' ', 1) for item in _GA_UNEMPLOYMENT_RAW.replace('\n', ' ').split(','))}
# The same data keyed by the boundary file's own spelling, to look values up by label text.
_BY_LABEL = {c['name']: GA_UNEMPLOYMENT[
    next(k for k in GA_UNEMPLOYMENT if _normalize_name(k) == _normalize_name(c['name']))]
    for c in _load_counties(_DEFAULT_GEOJSON_PATH)}


def _labels(fig):
    return [t.get_text() for t in fig.axes[0].texts if t.get_text()]


class TestRegressionLabelsFollowTheData:
    """
    County labels used to go to the largest counties on the map that had
    data, whatever their values. On real unemployment data that labelled
    Ware, Burke, Laurens, Clinch, Charlton and Emanuel -- rates from 3.0%
    to 5.4% -- and none of the counties a reader would look for: not the
    highest (Chattahoochee, 6.9%) or the lowest (Oconee, 2.5%).

    Labels are now chosen by value (`label_by`, default 'extremes'). The
    old behaviour is still there as label_by='area'.
    """

    def test_default_labels_the_highest_and_lowest_counties(self):
        fig = county_map_chart(GA_UNEMPLOYMENT)
        # The three highest (6.9, 6.1, 5.9), the lowest (2.5), and the two
        # largest of the six counties tied at 2.6 (ties go to the larger).
        assert set(_labels(fig)) == {'Chattahoochee', 'Quitman', 'Clay',
                                     'Oconee', 'Effingham', 'Bryan'}
        plt.close(fig)

    @pytest.mark.parametrize('n', [3, 6, 12])
    def test_highest_labels_the_top_values(self, n):
        fig = county_map_chart(GA_UNEMPLOYMENT, label_by='highest', label_top_n=n)
        labelled = set(_labels(fig))
        assert len(labelled) == n
        others = [v for name, v in _BY_LABEL.items() if name not in labelled]
        assert min(_BY_LABEL[name] for name in labelled) >= max(others)
        plt.close(fig)

    @pytest.mark.parametrize('n', [3, 6, 12])
    def test_lowest_labels_the_bottom_values(self, n):
        fig = county_map_chart(GA_UNEMPLOYMENT, label_by='lowest', label_top_n=n)
        labelled = set(_labels(fig))
        assert len(labelled) == n
        others = [v for name, v in _BY_LABEL.items() if name not in labelled]
        assert max(_BY_LABEL[name] for name in labelled) <= min(others)
        plt.close(fig)

    def test_label_by_area_labels_the_largest_counties(self):
        from dubois_charts.charts.choropleth import _project, _polygon_area
        import math
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        lats = [pt[1] for c in counties for ring in c['rings'] for pt in ring]
        lons = [pt[0] for c in counties for ring in c['rings'] for pt in ring]
        lon0, cos_lat0 = (min(lons) + max(lons)) / 2, math.cos(math.radians(sum(lats) / len(lats)))
        area = {c['name']: sum(_polygon_area(np.array([_project(x, y, lon0, cos_lat0) for x, y in ring]))
                               for ring in c['rings']) for c in counties}
        largest = sorted(area, key=area.get, reverse=True)[:6]
        fig = county_map_chart(GA_UNEMPLOYMENT, label_by='area')
        assert set(_labels(fig)) == set(largest)
        plt.close(fig)

    @pytest.mark.parametrize('n', [6, 12, 20])
    def test_every_requested_label_is_drawn(self, n):
        # Counties too small for their name used to be dropped silently;
        # they now get a callout, so the map carries all n labels.
        fig = county_map_chart(GA_UNEMPLOYMENT, label_top_n=n)
        assert len(_labels(fig)) == n
        plt.close(fig)

    def test_fewer_counties_with_data_than_labels_requested(self):
        fig = county_map_chart(SAMPLE_DATA, label_top_n=10)
        assert set(_labels(fig)) == set(SAMPLE_DATA)
        plt.close(fig)

    def test_labels_do_not_depend_on_the_order_data_was_given_in(self):
        forwards = county_map_chart(GA_UNEMPLOYMENT, label_top_n=10)
        backwards = county_map_chart(dict(reversed(list(GA_UNEMPLOYMENT.items()))), label_top_n=10)
        assert _labels(forwards) == _labels(backwards)
        plt.close(forwards)
        plt.close(backwards)

    def test_unknown_label_by_raises(self):
        with pytest.raises(ValueError, match='label_by'):
            county_map_chart(SAMPLE_DATA, label_by='largest')


def _check_label_geometry(fig):
    """Every label must be entirely inside its own county, or -- a callout --
    entirely outside every county, with a leader line from inside its county
    to its box. No two labels may overlap, no leader line may run through
    another label, and everything must be on the figure. Checked on the
    rendered text boxes, every pixel along their edges."""
    from matplotlib.path import Path as MplPath
    ax = fig.axes[0]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    to_data = ax.transData.inverted()
    counties = _load_counties(_DEFAULT_GEOJSON_PATH)
    paths = {c['name']: MplPath(p.get_xy()) for c, p in zip(counties, ax.patches)}
    leaders = [line for line in ax.lines if len(line.get_xdata()) == 2]
    boxes, problems = {}, []
    for t in ax.texts:
        name, bb = t.get_text(), t.get_window_extent(renderer)
        boxes[name] = bb
        if bb.x0 < 0 or bb.y0 < 0 or bb.x1 > fig.bbox.width or bb.y1 > fig.bbox.height:
            problems.append(f'{name} runs off the figure')
        xs, ys = np.arange(bb.x0, bb.x1 + 1), np.arange(bb.y0, bb.y1 + 1)
        edge = to_data.transform(np.concatenate([
            np.column_stack([xs, np.full_like(xs, bb.y0)]), np.column_stack([xs, np.full_like(xs, bb.y1)]),
            np.column_stack([np.full_like(ys, bb.x0), ys]), np.column_stack([np.full_like(ys, bb.x1), ys])]))
        if paths[name].contains_points(edge).all():
            continue                                            # a label inside its county
        if any(p.contains_points(edge).any() for p in paths.values()):
            problems.append(f'{name} crosses a county boundary')
            continue
        led = False
        for line in leaders:
            (x0, x1), (y0, y1) = line.get_xdata(), line.get_ydata()
            ex, ey = ax.transData.transform([[x1, y1]])[0]
            led |= (paths[name].contains_point((x0, y0))
                    and bb.x0 - 6 <= ex <= bb.x1 + 6 and bb.y0 - 6 <= ey <= bb.y1 + 6)
        if not led:
            problems.append(f'{name} is outside its county with no leader line to it')
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if boxes[a].overlaps(boxes[b]):
                problems.append(f'{a} and {b} overlap')
    for line in leaders:
        (x0, x1), (y0, y1) = line.get_xdata(), line.get_ydata()
        p0, p1 = ax.transData.transform([[x0, y0], [x1, y1]])
        pts = p0 + np.linspace(0, 1, 300)[:, None] * (p1 - p0)
        for name, bb in boxes.items():
            if paths[name].contains_point((x0, y0)):
                continue                                        # its own label
            through = ((pts[:, 0] > bb.x0 + 1) & (pts[:, 0] < bb.x1 - 1)
                       & (pts[:, 1] > bb.y0 + 1) & (pts[:, 1] < bb.y1 - 1))
            if through.any():
                problems.append(f'a leader line runs through {name}')
    return problems


class TestRegressionLabelPlacement:
    """
    Labels were centred on the average of the county outline's vertices,
    which for irregular counties is often a cramped spot or not inside the
    county at all, and only the four corners of the label were checked, so
    a boundary could cut through a label between them. At the default size
    50 of Georgia's 159 names fit at 8pt that way; searching the whole
    county for the roomiest spot fits 105. Counties too small at any size
    get a callout outside the state with a leader line -- which is where
    the extremes of a rate usually are, since small counties swing most.
    """

    @pytest.mark.parametrize('label_by, n', [('extremes', 6), ('extremes', 16), ('highest', 12),
                                             ('lowest', 12), ('area', 10)])
    def test_labels_sit_cleanly_inside_or_outside(self, label_by, n):
        fig = county_map_chart(GA_UNEMPLOYMENT, label_by=label_by, label_top_n=n)
        assert _check_label_geometry(fig) == []
        plt.close(fig)

    def test_small_figure(self):
        fig = county_map_chart(GA_UNEMPLOYMENT, label_top_n=8, figsize=(6, 6))
        assert _check_label_geometry(fig) == []
        plt.close(fig)

    def test_explicit_list_of_small_metro_counties(self):
        fig = county_map_chart(GA_UNEMPLOYMENT, label_counties=[
            'Fulton', 'DeKalb', 'Cobb', 'Clayton', 'Gwinnett', 'Rockdale', 'Henry', 'Douglas'])
        assert len(_labels(fig)) == 8
        assert _check_label_geometry(fig) == []
        plt.close(fig)

    def test_highest_and_lowest_counties_are_called_out(self):
        # Chattahoochee (6.9%) and Oconee (2.5%) are too small for their
        # names; both are labelled anyway, outside the state.
        fig = county_map_chart(GA_UNEMPLOYMENT)
        labels = _labels(fig)
        assert 'Chattahoochee' in labels and 'Oconee' in labels
        leaders = [line for line in fig.axes[0].lines if len(line.get_xdata()) == 2]
        assert len(leaders) >= 2
        plt.close(fig)

    def test_callout_leader_line_goes_around_other_labels(self):
        # On the real maps the nearest free spot rarely puts a label in the
        # way, so set one up: a "state" filling the right of the map and a
        # tall label beside it. The nearest free spot is straight left,
        # past that label -- its leader line would cut through it.
        from dubois_charts.charts.choropleth import _FreeSpace
        state = {'xy_rings': [np.array([[30, 0], [100, 0], [100, 100], [30, 100], [30, 0]], float)]}
        space = _FreeSpace([state], (0, 100), (0, 100), cell=1.0, grow_cells=1)
        space.take_label(19, 50, 9, 30)                  # label covering x 10-28, y 20-80
        (cx, cy), end = space.best_spot((50, 50), 4, 3)
        rows, cols = space._cells_along((50, 50), end)
        assert not space.labels[rows, cols].any(), "leader line runs through the label"
        assert not (10 <= cx <= 28 and 20 <= cy <= 80)

    def test_labels_stay_readable_when_most_counties_are_roomy(self):
        # One small county among the chosen shouldn't shrink every label
        # to the minimum: it gets a callout instead.
        fig = county_map_chart(GA_UNEMPLOYMENT)
        assert fig.axes[0].texts[0].get_fontsize() >= 8
        plt.close(fig)


class TestRegressionColorbarDefaultFormat:
    """
    The colorbar's tick labels defaulted to '{:.0f}', which printed the
    class boundaries of Georgia's county unemployment rates (2.5% to 6.9%)
    as "2 3 3 3 3 4 4 7". The default now follows the data's own precision.
    """

    @staticmethod
    def _ticks(fig):
        return [t.get_text() for t in fig.texts
                if t.get_text() not in ('', 'No data') and t.get_fontsize() == 8]

    def test_rates_print_every_boundary_differently(self):
        fig = county_map_chart(GA_UNEMPLOYMENT)
        assert self._ticks(fig) == ['2.5', '2.8', '3.0', '3.2', '3.4', '3.8', '4.2', '6.9']
        plt.close(fig)

    def test_whole_numbers_still_print_as_whole_numbers(self):
        data = {'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61,
                'Cobb': 70, 'Richmond': 48, 'Muscogee': 58, 'Clarke': 66}
        fig = county_map_chart(data)
        assert self._ticks(fig) == ['48', '55', '58', '61', '66', '70', '74', '82']
        plt.close(fig)

    def test_explicit_format_is_used_as_given(self):
        fig = county_map_chart(GA_UNEMPLOYMENT, value_format='{:.1f}%')
        assert self._ticks(fig)[0] == '2.5%'
        plt.close(fig)


class TestRegressionColourClassesForAnyData:
    """
    Colour classes were seven quantile ranges whatever the data looked
    like. With ties or few distinct values the boundaries coincided: three
    distinct values drew "1 1 1 2 2 3 3 3" with four classes never used, a
    map where every county had the same value read "5 5 5 5 5 5 5 5", two
    counties got five empty classes, n_classes=1 crashed, and the rounded
    boundaries of heavily tied data could show a class as starting at a
    value none of its counties had. Now every boundary is a real county
    value, every class holds at least one county, a handful of distinct
    values get one class each, and colorbar labels are thinned rather than
    overprinted when long numbers crowd them.
    """

    NAMES = [c['name'] for c in _load_counties(_DEFAULT_GEOJSON_PATH)]

    @staticmethod
    def _ticks(fig):
        return [t.get_text() for t in fig.texts
                if t.get_text() not in ('', 'No data') and t.get_fontsize() <= 8]

    @classmethod
    def _fills(cls, fig, data):
        """Fill colour of each county that has data, by name."""
        import matplotlib.colors as mcolors
        return {c['name']: mcolors.to_hex(p.get_facecolor())
                for c, p in zip(_load_counties(_DEFAULT_GEOJSON_PATH), fig.axes[0].patches)
                if c['name'] in data}

    def test_a_few_distinct_values_get_a_class_each(self):
        data = {n: [1.0, 2.0, 3.0][i % 3] for i, n in enumerate(self.NAMES)}
        fig = county_map_chart(data)
        assert self._ticks(fig) == ['1', '2', '3']
        fills = self._fills(fig, data)
        by_value = {v: {fills[n] for n in data if data[n] == v} for v in (1.0, 2.0, 3.0)}
        assert all(len(colours) == 1 for colours in by_value.values())
        assert len(set.union(*by_value.values())) == 3
        plt.close(fig)

    def test_every_county_the_same_value(self):
        data = {n: 5.0 for n in self.NAMES}
        fig = county_map_chart(data)
        assert self._ticks(fig) == ['5']
        assert len(set(self._fills(fig, data).values())) == 1
        plt.close(fig)

    def test_single_county(self):
        fig = county_map_chart({'Fulton': 42}, state='GA')
        assert self._ticks(fig) == ['42']
        plt.close(fig)

    def test_ties_leave_no_empty_class_and_no_repeated_label(self):
        rng = np.random.default_rng(2)
        values = [3.0] * 120 + list(rng.normal(4, 1, 39).round(1))
        data = dict(zip(self.NAMES, values))
        fig = county_map_chart(data)
        ticks = self._ticks(fig)
        assert len(ticks) == len(set(ticks))
        swatches = len(fig.patches)
        assert len(set(self._fills(fig, data).values())) == swatches      # every class is used
        plt.close(fig)

    def test_boundaries_are_values_some_county_has(self):
        rng = np.random.default_rng(5)
        data = dict(zip(self.NAMES, rng.beta(2, 5, 159).round(3)))
        fig = county_map_chart(data)
        values = {round(float(v), 3) for v in data.values()}
        for tick in self._ticks(fig):
            assert round(float(tick.replace(',', '')), 3) in values, tick
        plt.close(fig)

    def test_small_negative_boundaries_never_print_minus_zero(self):
        rng = np.random.default_rng(3)
        data = dict(zip(self.NAMES, rng.normal(0, 0.05, 159).round(3)))
        fig = county_map_chart(data)
        for tick in self._ticks(fig):
            assert not (tick.startswith('-') and float(tick) == 0), tick
        plt.close(fig)

    def test_one_class(self):
        data = {'Fulton': 1, 'Cobb': 2, 'Bibb': 3}
        fig = county_map_chart(data, n_classes=1)
        assert len(set(self._fills(fig, data).values())) == 1
        assert self._ticks(fig) == ['1', '3']
        plt.close(fig)

    @pytest.mark.parametrize('bad', [0, -1, 2.5, True, '7'])
    def test_invalid_n_classes_raises(self, bad):
        with pytest.raises(ValueError, match='n_classes'):
            county_map_chart(SAMPLE_DATA, n_classes=bad)

    @pytest.mark.parametrize('n_classes', [7, 12, 20])
    def test_colorbar_labels_never_overlap(self, n_classes):
        rng = np.random.default_rng(2)
        data = dict(zip(self.NAMES, rng.lognormal(13, 1.2, 159).round(2)))
        fig = county_map_chart(data, n_classes=n_classes)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ticks = sorted((t for t in fig.texts if t.get_text() and t.get_fontsize() <= 8),
                       key=lambda t: t.get_position()[0])
        boxes = [t.get_window_extent(renderer) for t in ticks]
        for a, b in zip(boxes, boxes[1:]):
            assert a.x1 < b.x0, "colorbar labels overlap"
        values = sorted(data.values())
        assert ticks[0].get_text() == f'{values[0]:,.0f}' and ticks[-1].get_text() == f'{values[-1]:,.0f}'
        assert all(t.get_fontsize() >= 7 for t in ticks)
        plt.close(fig)


THREE = ('Fulton', 'DeKalb', 'Cobb')


def _labelled(fig):
    return sorted(t.get_text() for t in fig.axes[0].texts if t.get_text() in THREE)


class TestRegressionCountyKeys:
    """
    US data very often identifies counties by FIPS code (13121 for
    Fulton) or by the Census's own names ("Fulton County, Georgia"), and
    none of that matched: every county drew as missing, with a warning
    listing all the keys as unknown names.
    """

    @pytest.mark.parametrize('keys', [
        (13121, 13089, 13067),                                   # GEOIDs as integers
        ('13121', '13089', '13067'),                             # ... as text
        (13121.0, 13089.0, 13067.0),                             # ... as pandas floats
        ('121', 89, '067'),                                      # county codes alone
        ('0500000US13121', '0500000US13089', '0500000US13067'),  # Census GEO_ID
        ('Fulton County, Georgia', 'DeKalb County, Georgia', 'Cobb County, GA'),
    ])
    def test_every_common_kind_of_key(self, keys):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(dict(zip(keys, (5.0, 4.0, 3.0))), label_top_n=3)
        assert _labelled(fig) == sorted(THREE)
        plt.close(fig)

    def test_label_counties_takes_codes_too(self):
        fig = county_map_chart({'Fulton': 1, 'Cobb': 2, 'Bibb': 3}, label_counties=[13121, '067'])
        assert _labelled(fig) == ['Cobb', 'Fulton']
        plt.close(fig)

    def test_another_states_code_is_named_as_unmatched(self):
        with pytest.warns(UserWarning, match=r"\['01001'\]"):
            fig = county_map_chart({'01001': 3.0, 'Fulton': 2.0})
        plt.close(fig)

    def test_bundled_codes(self):
        counties = {c['name']: c for c in _load_counties(_DEFAULT_GEOJSON_PATH)}
        assert len({c['geoid'] for c in counties.values()}) == 159
        for name, geoid in (('Appling', '13001'), ('Candler', '13043'), ('Fulton', '13121'),
                            ('McDuffie', '13189'), ('Macon', '13193'), ('Worth', '13321')):
            assert counties[name]['geoid'] == geoid and counties[name]['countyfp'] == geoid[2:]


def _square(lon, lat, size, clockwise=False):
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return ring[::-1] if clockwise else ring


def _write_geojson(tmp_path, features, name_key='NAME'):
    import json
    path = tmp_path / 'counties.geojson'
    path.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {name_key: name}, 'geometry': geometry}
        for name, geometry in features]}))
    return str(path)


class TestRegressionBoundaryFiles:
    """
    Boundary files other than the bundled one: a county in several pieces
    (islands) kept only its first piece, a hole -- a county inside another
    -- was painted over in the outer county's colour, and a file whose
    names weren't under NAME crashed with KeyError: 'NAME'.
    """

    FEATURES = [
        # the county inside comes first, so a filled-in hole would cover it
        ('Inner', {'type': 'Polygon', 'coordinates': [_square(-82.5, 33.5, 1)]}),
        ('Outer', {'type': 'Polygon', 'coordinates': [_square(-84, 32, 4),
                                                      _square(-82.5, 33.5, 1, clockwise=True)]}),
        ('Islands', {'type': 'MultiPolygon', 'coordinates': [[_square(-79, 32, 1)],
                                                             [_square(-79, 35, 1)]]}),
    ]
    DATA = {'Inner': 10.0, 'Outer': 1.0, 'Islands': 5.0}

    def test_every_piece_and_every_hole(self, tmp_path):
        import matplotlib.colors as mcolors
        path = _write_geojson(tmp_path, self.FEATURES)
        fig = county_map_chart(self.DATA, geojson_path=path, label_top_n=0, n_classes=3)
        ax = fig.axes[0]
        fig.canvas.draw()
        image = np.asarray(fig.canvas.buffer_rgba())[..., :3]
        filled = [p for p in ax.patches if p.get_fill() and p.get_facecolor()[3] > 0]
        by_colour = {}
        for patch in filled:
            by_colour.setdefault(mcolors.to_hex(patch.get_facecolor()), []).append(patch)
        # both islands are drawn: the middle value, so the middle shade
        shades = sorted(by_colour, key=lambda c: sum(mcolors.to_rgb(c)))
        assert len(shades) == 3 and len(by_colour[shades[1]]) == 2
        # the county inside the hole -- the highest value, so the darkest
        # fill -- shows its own colour at its centre, not the outer county's
        inner = min(filled, key=lambda p: sum(mcolors.to_rgb(p.get_facecolor())))
        box = inner.get_window_extent()
        x, y = int((box.x0 + box.x1) / 2), int((box.y0 + box.y1) / 2)
        drawn = mcolors.to_hex(image[image.shape[0] - 1 - y, x] / 255)
        assert drawn == mcolors.to_hex(inner.get_facecolor())
        plt.close(fig)

    def test_names_under_other_properties(self, tmp_path):
        path = _write_geojson(tmp_path, self.FEATURES, name_key='name')
        fig = county_map_chart(self.DATA, geojson_path=path, label_top_n=0)
        plt.close(fig)
        path = _write_geojson(tmp_path, self.FEATURES, name_key='district')
        with pytest.raises(ValueError, match="no name property.*district"):
            county_map_chart(self.DATA, geojson_path=path)

    def test_a_file_of_several_states_says_so(self, tmp_path):
        path = _write_geojson(tmp_path, [
            ('Washington', {'type': 'Polygon', 'coordinates': [_square(-84, 32, 1)]}),
            ('Washington', {'type': 'Polygon', 'coordinates': [_square(-82, 32, 1)]}),
            ('Adams', {'type': 'Polygon', 'coordinates': [_square(-80, 32, 1)]}),
        ])
        with pytest.raises(ValueError, match='repeat.*Washington.*one state'):
            county_map_chart({'Washington': 1.0, 'Adams': 2.0}, geojson_path=path)


def _text_problems(fig):
    import itertools
    from matplotlib.text import Text
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    boxes = [(t, t.get_window_extent(renderer)) for t in fig.findobj(Text)
             if t.get_visible() and t.get_text().strip()]
    problems = [f'off the figure: {t.get_text()!r}' for t, b in boxes
                if b.x0 < -1 or b.y0 < -1 or b.x1 > width + 1 or b.y1 > height + 1]
    for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
        if min(a.x1, b.x1) - max(a.x0, b.x0) > 1 and min(a.y1, b.y1) - max(a.y0, b.y0) > 1:
            problems.append(f'overlap: {ta.get_text()!r} / {tb.get_text()!r}')
    return problems


class TestRegressionEveryState:
    """
    county_map_chart drew Georgia only: anyone with county data for
    another state couldn't use it. `state=` now draws any state or
    territory from the Census's 2017 county boundaries (bundled from
    us-atlas), with Georgia unchanged as the default.
    """

    # Counties (and county equivalents) per state in the 2017 Census boundaries.
    COUNTS = {'01': 67, '02': 29, '06': 58, '09': 8, '10': 3, '11': 1, '13': 159, '15': 5,
              '22': 64, '24': 24, '29': 115, '44': 5, '48': 254, '51': 133, '72': 78}

    def test_state_by_name_postal_code_or_fips(self):
        from dubois_charts.charts.choropleth import state_fips
        for form in ('Virginia', 'virginia', 'VA', 'va', 51, '51'):
            assert state_fips(form) == '51'
        assert state_fips('District of Columbia') == state_fips('DC') == '11'
        assert state_fips(6) == '06'
        with pytest.raises(ValueError, match="isn't a U.S. state"):
            state_fips('Atlantis')

    def test_every_state_loads_whole_and_uniquely_named(self):
        from dubois_charts.charts.choropleth import STATES, _load_state_counties
        for fips in STATES:
            counties = _load_state_counties(fips)
            assert counties, fips
            assert all(c['geoid'].startswith(fips) for c in counties)
            names = [_normalize_name(c['name']) for c in counties]
            assert len(set(names)) == len(names), fips
            if fips in self.COUNTS and fips != '13':
                assert len(counties) == self.COUNTS[fips], fips
            lons = [pt[0] for c in counties for ring in c['rings'] for pt in ring]
            assert max(lons) - min(lons) < 180, fips      # nothing drawn across the globe

    @pytest.mark.parametrize('state', ['AK', 'HI', 'TX', 'VA', 'TN', 'MI', 'DE', 'MP', 'PR'])
    def test_awkward_shapes_draw_cleanly(self, state):
        from dubois_charts.charts.choropleth import _load_state_counties, state_fips
        counties = _load_state_counties(state_fips(state))
        rng = np.random.default_rng(len(state))
        data = {c['geoid']: float(rng.gamma(4, 2.5)) for c in counties}
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(data, state=state, title=f'{state}: an example by county',
                                   colorbar_label='Rate per 1,000', label_top_n=12)
        width, height = fig.get_size_inches()
        assert 5 <= width <= 9 and height <= 12, (width, height)
        assert _text_problems(fig) == []
        assert len([p for p in fig.axes[0].patches]) >= len(counties)
        plt.close(fig)

    @pytest.mark.parametrize('state, keys, expected', [
        ('VA', ['Fairfax County', 'Fairfax city', 'Richmond city, Virginia', 'Alexandria city'],
         ['Alexandria', 'Fairfax City', 'Fairfax County', 'Richmond City']),
        ('AK', ['Anchorage Municipality', 'Juneau City and Borough', 'Bethel Census Area'],
         ['Anchorage', 'Bethel', 'Juneau']),
        ('MO', ['St. Louis city', 'Saint Louis County', 'Ste. Genevieve County'],
         ['St. Louis City', 'St. Louis County', 'Ste. Genevieve']),
        ('NM', ['Dona Ana County, New Mexico'], ['Doña Ana']),
        ('LA', ['Orleans Parish'], ['Orleans']),
        ('PR', ['Mayaguez Municipio'], ['Mayagüez']),
    ])
    def test_census_style_names(self, state, keys, expected):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart({k: float(i) for i, k in enumerate(keys)}, state=state,
                                   label_counties=keys)
        assert sorted(t.get_text() for t in fig.axes[0].texts) == expected
        plt.close(fig)

    def test_the_state_is_read_from_its_codes(self):
        fig = county_map_chart({'06037': 5.0, '06075': 3.0, '06073': 4.0}, label_top_n=3)
        assert sorted(t.get_text() for t in fig.axes[0].texts) == ['Los Angeles', 'San Diego',
                                                                   'San Francisco']
        plt.close(fig)

    def test_state_and_boundary_file_together_say_so(self):
        with pytest.raises(ValueError, match='not both'):
            county_map_chart(SAMPLE_DATA, state='GA', geojson_path=_DEFAULT_GEOJSON_PATH)

    def test_georgia_is_unchanged(self):
        a = county_map_chart(SAMPLE_DATA, title='Georgia')
        b = county_map_chart(SAMPLE_DATA, title='Georgia', state='GA')
        for fig in (a, b):
            fig.canvas.draw()
        assert np.array_equal(np.asarray(a.canvas.buffer_rgba()), np.asarray(b.canvas.buffer_rgba()))
        plt.close(a)
        plt.close(b)


def _state_data(state, seed):
    from dubois_charts.charts.choropleth import _load_state_counties, state_fips
    rng = np.random.default_rng(seed)
    return {c['geoid']: float(rng.gamma(4, 2.5)) for c in _load_state_counties(state_fips(state))}


def _callouts(fig):
    """(label text, leader length in inches, distance in inches from the
    leader's start to the nearest side of the state's frame) per callout,
    and anything wrong with them: a label over a county, or a leader line
    that doesn't end at exactly one label."""
    from matplotlib.path import Path as MplPath
    ax = fig.axes[0]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    rings = [MplPath(poly) for p in ax.patches for poly in p.get_path().to_polygons()]
    corners = ax.transData.transform(np.concatenate([r.vertices for r in rings]))
    (fx0, fy0), (fx1, fy1) = corners.min(axis=0), corners.max(axis=0)
    to_data = ax.transData.inverted()
    found, problems = [], []
    boxes = [(t.get_text(), t.get_window_extent(renderer)) for t in ax.texts]
    for line in [l for l in ax.lines if len(l.get_xdata()) == 2]:
        (sx, sy), (ex, ey) = ax.transData.transform(line.get_xydata())
        # Its label is the one it ends at: the nearest, within a few pixels.
        gaps = [math.hypot(max(bb.x0 - ex, 0, ex - bb.x1), max(bb.y0 - ey, 0, ey - bb.y1))
                for _, bb in boxes]
        if not gaps or min(gaps) > 6:
            problems.append('a leader line ends at no label')
            continue
        name, bb = boxes[int(np.argmin(gaps))]
        if any(name == other for other, _, _ in found):
            problems.append(f'{name} has two leader lines')
        xs, ys = np.arange(bb.x0, bb.x1 + 1), np.arange(bb.y0, bb.y1 + 1)
        edge = to_data.transform(np.concatenate([
            np.column_stack([xs, np.full_like(xs, bb.y0)]), np.column_stack([xs, np.full_like(xs, bb.y1)]),
            np.column_stack([np.full_like(ys, bb.x0), ys]), np.column_stack([np.full_like(ys, bb.x1), ys])]))
        if any(r.contains_points(edge).any() for r in rings):
            problems.append(f'{name} is over the map')
        found.append((name, float(np.hypot(ex - sx, ey - sy)) / fig.dpi,
                      float(min(sx - fx0, fx1 - sx, sy - fy0, fy1 - sy)) / fig.dpi))
    return found, problems


class TestRegressionCalloutsHaveRoom:
    """
    A callout -- a county's name outside the state, with a leader line to
    it -- could only go inside the map's frame, so on a state that fills
    its frame there was often nowhere for it, and the label was dropped
    without a word: Colorado drew 5 of 8 labels asked for, and Kansas and
    North Dakota lost labels too. On others the label went wherever the
    frame had a gap, however far from its county: Kansas's was two inches
    away in a corner of the frame, Puerto Rico's and Pennsylvania's as far.
    Callouts can now also go beyond the frame -- into the figure's margins
    and, when that's nearer, past them, the figure growing to fit and the
    map keeping its size.
    """

    @pytest.mark.parametrize('state, seed', [('CO', 8), ('CO', 0), ('KS', 4), ('ND', 3)])
    def test_every_label_asked_for_is_drawn(self, state, seed):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            fig = county_map_chart(_state_data(state, seed), state=state, label_top_n=8)
        assert len(fig.axes[0].texts) == 8
        found, problems = _callouts(fig)
        assert found and problems == []
        assert _text_problems(fig) == []
        plt.close(fig)

    @pytest.mark.parametrize('state', ['PA', 'KS', 'PR', 'NE', 'TN', 'IL'])
    def test_a_callout_is_never_far_from_its_county(self, state):
        # No farther than the nearest edge of the state, plus a little for
        # the label: a county in the middle of a state with straight
        # borders can't do better than that.
        from dubois_charts.charts.choropleth import state_fips
        fig = county_map_chart(_state_data(state, int(state_fips(state))), state=state)
        found, problems = _callouts(fig)
        assert found and problems == []
        far = [(name, round(length, 2), round(edge, 2)) for name, length, edge in found
               if length > edge + 0.3]
        assert far == []
        plt.close(fig)

    def test_the_map_keeps_its_size_and_the_figure_grows_around_it(self):
        # Tennessee's callouts go above and below it, North Dakota's beside it.
        for state, n in (('TN', 6), ('ND', 15)):
            data = _state_data(state, 3)
            plain = county_map_chart(data, state=state, label_top_n=0)
            labelled = county_map_chart(data, state=state, label_top_n=n)
            sizes = []
            for fig in (plain, labelled):
                fig.canvas.draw()
                ax = fig.axes[0]
                pts = ax.transData.transform(np.concatenate([p.get_path().vertices for p in ax.patches]))
                swatches = [p.get_window_extent() for p in fig.patches]
                sizes.append((np.round(np.ptp(pts, axis=0), 6).tolist(),
                              [round(b.width, 6) for b in swatches]))
            assert sizes[0] == sizes[1], state           # the map and the colorbar, in pixels
            (pw, ph), (lw, lh) = plain.get_size_inches(), labelled.get_size_inches()
            assert lw >= pw and lh >= ph and (lw, lh) != (pw, ph), state
            plt.close(plain)
            plt.close(labelled)

    def test_labels_with_no_room_are_named_in_a_warning(self):
        # Sixty labels on a 5-inch Virginia: many can't fit, and they used
        # to be left off without a word. Every one is now drawn or named.
        import re
        with pytest.warns(UserWarning, match=r'no room for \d+ of the labels') as record:
            fig = county_map_chart(_state_data('VA', 1), state='VA', label_top_n=60, figsize=(5, 4))
        message = next(str(w.message) for w in record if 'no room' in str(w.message))
        left_off = int(re.search(r'no room for (\d+)', message).group(1))
        assert left_off > 0 and len(fig.axes[0].texts) + left_off == 60
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_a_width_you_give_is_kept(self):
        fig = county_map_chart(_state_data('ND', 3), state='ND', label_top_n=15, figsize=(8, 6))
        assert fig.get_size_inches()[0] == 8
        assert _text_problems(fig) == []
        plt.close(fig)


class TestRegressionNoDataIsExplained:
    """
    Counties without a value were drawn in a gray the colorbar didn't
    mention -- a warm gray that, for a deuteranope, matched one of a
    seven-class crimson map's pinks. The no-data colour is now distinct
    for every reader, and gets its own swatch, "No data", beside the bar.
    """

    @staticmethod
    def _no_data(fig):
        return [t for t in fig.texts if t.get_text() == 'No data']

    @pytest.mark.parametrize('kwargs', [{}, {'figsize': (5, 6)}, {'n_classes': 3},
                                        {'colorbar_label': 'Percentage literate'}])
    def test_a_swatch_when_some_counties_have_no_value(self, kwargs):
        fig = county_map_chart(SAMPLE_DATA, **kwargs)
        assert len(self._no_data(fig)) == 1
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_discrete_classes_too(self):
        fig = county_map_chart({'Fulton': 1, 'DeKalb': 2, 'Cobb': 3})
        assert len(self._no_data(fig)) == 1
        assert _text_problems(fig) == []
        plt.close(fig)

    def test_no_swatch_when_every_county_has_a_value(self):
        counties = _load_counties(_DEFAULT_GEOJSON_PATH)
        fig = county_map_chart({c['name']: float(i) for i, c in enumerate(counties)})
        assert self._no_data(fig) == []
        plt.close(fig)
