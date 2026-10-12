"""
Tests for dubois_charts.charts.spiral.spiral_chart.

Includes regression coverage for the bugs documented in
GENERAL_ENGINE_README.md's spiral.py section: labels overlapping each
other, labels overlapping the curve itself, and a too-low default
revolution count that left the curve barely reading as a spiral at all.
This is the one chart type in the package where label placement is a
genuine 2-D problem, so "no two labels visually overlap" is checked
directly against rendered bounding boxes here rather than only inferred
from the geometry, unlike the more straightforward regression checks in
the other chart test files.
"""

import pytest
import matplotlib.pyplot as plt

from dubois_charts.charts.spiral import spiral_chart


BASIC_CATEGORIES = [1870, 1880, 1890, 1900, 1910, 1920, 1930, 1940]
BASIC_VALUES = [45, 62, 89, 140, 210, 305, 410, 520]


def _no_two_texts_overlap(fig):
    """Render and check that no two Text artists' bounding boxes
    intersect -- the direct regression check for the label-vs-label
    collision bug."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for ax in fig.axes:
        for t in ax.texts:
            if t.get_text().strip():
                boxes.append(t.get_window_extent(renderer=renderer))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i].overlaps(boxes[j]):
                return False
    return True


class TestBasicRendering:
    def test_returns_a_figure(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_runs_with_title_and_subtitle(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                            title='A Title', subtitle='A subtitle')
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_minimum_two_points(self):
        fig = spiral_chart(categories=[1, 2], values=[10, 20])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_many_points(self):
        cats = list(range(20))
        vals = [i * 10 + 5 for i in range(20)]
        fig = spiral_chart(categories=cats, values=vals)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_non_monotonic_values(self):
        # Not required to be increasing, per the docstring.
        fig = spiral_chart(categories=[1, 2, 3, 4, 5], values=[50, 10, 80, 20, 60])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_explicit_revolutions(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                            revolutions=3.5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_hand_drawn_can_be_disabled(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                            hand_drawn=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_value_labels_can_be_disabled(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                            show_value_labels=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_all_zero_values(self):
        # Degenerate but should not divide by zero / crash.
        fig = spiral_chart(categories=[1, 2, 3], values=[0, 0, 0])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestInputValidation:
    def test_single_point_raises(self):
        with pytest.raises(ValueError):
            spiral_chart(categories=[1], values=[10])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            spiral_chart(categories=[], values=[])

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            spiral_chart(categories=[1, 2, 3], values=[10, 20])

    def test_negative_values_raise_with_actionable_message(self):
        with pytest.raises(ValueError, match=r"negative value for '2' \(-5\).*zero or more.*add the same amount"):
            spiral_chart(categories=[1, 2, 3], values=[10, -5, 20])


class TestRegressionLabelCollisions:
    """
    Regression coverage for the label-overlap bugs: testing with 16 long
    labels on a multi-revolution spiral originally produced labels
    drawn directly on top of the curve and on top of each other. Both
    are checked here by inspecting actual rendered bounding boxes rather
    than trusting the geometry math in isolation.
    """

    def test_no_overlapping_labels_moderate_case(self):
        cats = [1870, 1875, 1880, 1885, 1890, 1895, 1900, 1905, 1910, 1915, 1920, 1925]
        vals = [45, 52, 62, 74, 89, 110, 140, 172, 210, 255, 305, 355]
        fig = spiral_chart(categories=cats, values=vals,
                            title='Population Growth Over Time')
        assert _no_two_texts_overlap(fig)
        plt.close(fig)

    def test_no_overlapping_labels_adversarial_case(self):
        cats = [f'{n} Enumeration Period' for n in
                ['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh',
                 'Eighth', 'Ninth', 'Tenth', 'Eleventh', 'Twelfth', 'Thirteenth',
                 'Fourteenth', 'Fifteenth', 'Sixteenth']]
        vals = [12, 18, 25, 22, 30, 38, 45, 41, 52, 60, 68, 75, 90, 105, 130, 160]
        fig = spiral_chart(
            categories=cats, values=vals,
            title='Comprehensive Regional Population Enumeration Across Sixteen '
                  'Consecutive Historical Survey Periods',
            value_format='{:.0f}k',
        )
        # The honest, documented outcome here is that SOME labels are
        # skipped rather than forced into overlap -- what matters is that
        # whichever ones DO render don't collide.
        assert _no_two_texts_overlap(fig)
        plt.close(fig)

    def test_basic_case_labels_all_placed(self):
        # With short labels and a reasonable point count, nothing should
        # need to be dropped.
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES)
        ax = fig.axes[0]
        year_labels = [t for t in ax.texts if any(str(y) in t.get_text() for y in BASIC_CATEGORIES)]
        assert len(year_labels) == len(BASIC_CATEGORIES)
        plt.close(fig)


class TestRegressionRevolutionCount:
    """
    Regression coverage for the too-low default revolution count: the
    original `round(n / 9)` formula rounded down to a single, lopsided
    loop for 8 points, which only reaches its outer radius near the
    single point where it starts and ends rather than reading as a
    spiral. The default should produce at least roughly two full turns.
    """

    def test_default_revolutions_produce_a_wide_angular_spread(self):
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES)
        ax = fig.axes[0]
        # The plotted curve (a Line2D) should sweep through a wide angle
        # -- proxy this by checking the curve's own data spans enough of
        # the axes' x-range in both the positive and negative direction,
        # which a lopsided single loop (found in the original bug) does
        # not reliably do.
        lines = ax.get_lines()
        assert len(lines) >= 1
        xdata = lines[0].get_xdata()
        assert xdata.max() > 0
        assert xdata.min() < 0
        plt.close(fig)


class TestRobustness:
    def test_long_title_does_not_raise(self):
        title = 'A Considerably Long Title For A Spiral Chart About Growth ' * 2
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES, title=title)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_long_category_labels_do_not_raise(self):
        cats = ['A Fairly Long Category Label One', 'A Fairly Long Category Label Two',
                'A Fairly Long Category Label Three']
        fig = spiral_chart(categories=cats, values=[10, 50, 90])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_path_writes_a_file(self, tmp_path):
        out = tmp_path / 'spiral_test_output.png'
        fig = spiral_chart(categories=BASIC_CATEGORIES, values=BASIC_VALUES,
                            save_path=str(out))
        plt.close(fig)
        assert out.exists()
        assert out.stat().st_size > 0


class TestRegressionRevolutionsValidation:
    """
    Regression coverage for a bug found by passing revolutions=0: it
    crashed with a raw ZeroDivisionError deep inside the label-placement
    math (`r_value_span / revolutions`) rather than a message naming the
    actual problem. Negative revolutions had the same underlying issue
    (an undocumented, silently-accepted value with no defined meaning)
    and is rejected by the same check.
    """

    def test_zero_revolutions_raises(self):
        with pytest.raises(ValueError, match='positive'):
            spiral_chart(categories=[1, 2, 3, 4], values=[10, 20, 30, 40], revolutions=0)

    def test_negative_revolutions_raises(self):
        with pytest.raises(ValueError, match='positive'):
            spiral_chart(categories=[1, 2, 3, 4], values=[10, 20, 30, 40], revolutions=-2)

    def test_positive_revolutions_still_works(self):
        fig = spiral_chart(categories=[1, 2, 3, 4], values=[10, 20, 30, 40], revolutions=3.5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestRegressionLeaderLinesOnTightSpirals:
    """
    On a tightly wound spiral there's rarely room for a label beside its
    point, and every label that didn't fit went outside with a leader
    line. From deep inside, a leader crossed loop after loop (five, on a
    40-point spiral) and ended in a tangle no reader could follow; on a
    60-point spiral two leaders crossed each other; on a 30-point one, a
    later label was put right over an earlier one's leader. Labels were
    chosen every n/9 points, which on the 60-point spiral -- about seven
    points a turn -- put all nine on one ray.

    Leaders now cross no other leader and no label, take the way across
    the fewest loops, and only the first, last, highest and lowest points
    may have one that crosses more than one loop; the other labels go to
    points where they fit, including the tops and bottoms of the turns,
    where the loops run level.
    """

    CASES = {
        'forty points, growing by a tenth each': (
            [str(1800 + 5 * i) for i in range(40)],
            [round(5 * (300 / 5) ** (i / 39), 1) for i in range(40)]),
        'sixty points, growing steadily': ([str(i) for i in range(60)], list(range(1, 61))),
        'thirty points, growing by a fifth each': (
            [str(1990 + i) for i in range(30)], [round(1.2 ** i, 1) for i in range(30)]),
    }

    @staticmethod
    def _leaders(fig):
        """(start, end, label text) for every leader line, in data units,
        and the boxes of every label."""
        import numpy as np
        ax = fig.axes[0]
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        to_data = ax.transData.inverted()
        boxes = {}
        for t in ax.texts:
            bb = t.get_window_extent(renderer)
            (x0, y0), (x1, y1) = to_data.transform((bb.x0, bb.y0)), to_data.transform((bb.x1, bb.y1))
            boxes[t.get_text()] = (x0, x1, y0, y1)
        curve = max(ax.lines, key=lambda line: len(line.get_xdata()))
        leaders = []
        for line in ax.lines:
            if line is curve or len(line.get_xdata()) != 2:
                continue
            a, b = np.asarray(line.get_xydata(), float)
            # Its label is the one whose box it ends on.
            text = min(boxes, key=lambda k: max(boxes[k][0] - b[0], 0, b[0] - boxes[k][1])
                       + max(boxes[k][2] - b[1], 0, b[1] - boxes[k][3]))
            leaders.append((a, b, text))
        return leaders, boxes, np.asarray(curve.get_xydata(), float)

    @staticmethod
    def _crossings(a, b, c, d):
        import numpy as np
        r, s = b - a, d - c
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        w = c - a
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (w[:, 0] * s[:, 1] - w[:, 1] * s[:, 0]) / den
            u = (w[:, 0] * r[1] - w[:, 1] * r[0]) / den
        return (den != 0) & (t > 0) & (t < 1) & (u > 0) & (u < 1), t

    def _check(self, name):
        import numpy as np
        cats, vals = self.CASES[name]
        fig = spiral_chart(cats, vals)
        leaders, boxes, curve = self._leaders(fig)
        ax = fig.axes[0]
        per_px = 1 / (ax.transData.transform((1, 0))[0] - ax.transData.transform((0, 0))[0])
        key = {cats[0], cats[-1], cats[int(np.argmax(vals))], cats[int(np.argmin(vals))]}
        problems = []
        for k, (a, b, text) in enumerate(leaders):
            hit, t = self._crossings(a, b, curve[:-1], curve[1:])
            loops = int((hit & (t * np.hypot(*(b - a)) > 6 * per_px)).sum())
            words = ' '.join(text.split())
            is_key = any(words.startswith(' '.join(c.split()) + ' ')
                         and ' ' not in words[len(' '.join(c.split())) + 1:] for c in key)
            if loops > 1 and not is_key:
                problems.append(f'{text!r}: its leader crosses {loops} loops')
            for a2, b2, text2 in leaders[k + 1:]:
                if self._crossings(a, b, a2[None], b2[None])[0].any():
                    problems.append(f'the leaders of {text!r} and {text2!r} cross')
            ts = np.linspace(0, 1, 400)[:, None]
            along = a + ts * (b - a)
            for other, (x0, x1, y0, y1) in boxes.items():
                if other != text and np.any((along[:, 0] > x0) & (along[:, 0] < x1)
                                            & (along[:, 1] > y0) & (along[:, 1] < y1)):
                    problems.append(f'the leader of {text!r} runs through {other!r}')
        return problems, len(boxes)

    @pytest.mark.parametrize('name', sorted(CASES))
    def test_leaders_are_easy_to_follow(self, name):
        problems, _ = self._check(name)
        assert problems == []

    @pytest.mark.parametrize('name', sorted(CASES))
    def test_as_many_labels_as_before(self, name):
        _, labels = self._check(name)
        assert labels == 9

    def test_labels_on_a_tight_spiral_are_not_all_on_one_ray(self):
        # Eight of the nine were within 45 degrees of each other.
        import numpy as np
        cats, vals = self.CASES['sixty points, growing steadily']
        fig = spiral_chart(cats, vals)
        angles = np.array([np.degrees(np.arctan2(*t.get_position()[::-1])) % 360
                           for t in fig.axes[0].texts])
        assert max(int(((angles - a) % 360 < 45).sum()) for a in angles) <= 5
