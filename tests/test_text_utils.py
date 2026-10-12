"""
Tests for dubois_charts.text_utils -- the measurement/fitting layer every chart
type in the package builds on. These are worth testing thoroughly on
their own: a bug here silently affects every chart at once, the way the
"assumed the anchor was screen-space" bug in butterfly.py's inverted
axis or the curve-collision gaps in spiral.py did before they were
caught by looking at actual renders.
"""

import pytest
import matplotlib.pyplot as plt
from dubois_charts import text_utils as tu


class TestMeasureTextPx:
    def test_returns_positive_dimensions(self, fig):
        w, h = tu.measure_text_px(fig, 'Hello World', 12, 'monospace', 'bold')
        assert w > 0
        assert h > 0

    def test_empty_string_has_zero_size(self, fig):
        w, h = tu.measure_text_px(fig, '', 12, 'monospace', 'bold')
        assert w == 0
        assert h == 0

    def test_longer_text_is_wider(self, fig):
        w_short, _ = tu.measure_text_px(fig, 'Hi', 12, 'monospace', 'bold')
        w_long, _ = tu.measure_text_px(fig, 'Hi there, this is longer', 12, 'monospace', 'bold')
        assert w_long > w_short

    def test_larger_fontsize_is_wider(self, fig):
        w_small, _ = tu.measure_text_px(fig, 'Sample', 10, 'monospace', 'bold')
        w_large, _ = tu.measure_text_px(fig, 'Sample', 20, 'monospace', 'bold')
        assert w_large > w_small


class TestGetRendererCaching:
    """
    Regression coverage for a severe performance bug: get_renderer() used
    to call fig.canvas.draw() -- a full redraw of every already-placed
    artist -- on every single call. Any chart that measures text after
    placing a lot of expensive content (snake_chart's per-segment label
    loop, which runs after that segment's rectangles and textures are
    already drawn) paid for a full redraw on every measurement, compounding
    into a severe slowdown as more content accumulated. A 30-segment
    snake_chart went from 130+ seconds to about 1 second after caching the
    renderer per-figure instead of re-drawing every time.
    """

    def test_renderer_is_cached_across_calls(self, fig):
        r1 = tu.get_renderer(fig)
        r2 = tu.get_renderer(fig)
        assert r1 is r2

    def test_different_figures_get_different_renderers(self):
        fig1 = plt.figure()
        fig2 = plt.figure()
        r1 = tu.get_renderer(fig1)
        r2 = tu.get_renderer(fig2)
        assert r1 is not r2
        plt.close(fig1)
        plt.close(fig2)

    def test_measurement_is_correct_even_after_heavy_drawing(self, fig):
        # The actual failing scenario: measure once, draw a lot of
        # expensive content, then measure the same text again -- the
        # second measurement must still be numerically correct (not just
        # fast), since a naive "cache and never validate" fix could
        # silently return stale results instead of merely being slow.
        w_before, h_before = tu.measure_text_px(fig, 'Consistent Text', 12, 'monospace', 'bold')

        ax = fig.add_subplot(111)
        for i in range(20):
            ax.add_patch(plt.Rectangle((i, 0), 0.8, 1, facecolor='red'))

        w_after, h_after = tu.measure_text_px(fig, 'Consistent Text', 12, 'monospace', 'bold')
        assert (w_before, h_before) == (w_after, h_after)

    def test_measurement_correct_after_figure_resize(self):
        # bar_chart grows the figure via fig.set_size_inches() to
        # accommodate a rotated tick label's overflow, potentially after
        # earlier measurements already cached a renderer -- confirm a
        # resize doesn't leave stale, wrong measurements behind. Checked
        # against a fresh figure created directly at the post-resize
        # size, not just for before/after consistency, since consistently
        # wrong would still pass a naive equality check.
        fig = plt.figure(figsize=(6, 4), dpi=150)
        tu.measure_text_px(fig, 'Test String 123', 14, 'monospace', 'bold')  # caches a renderer
        fig.set_size_inches(10, 4, forward=True)
        w_after, h_after = tu.measure_text_px(fig, 'Test String 123', 14, 'monospace', 'bold')

        fresh_fig = plt.figure(figsize=(10, 4), dpi=150)
        w_fresh, h_fresh = tu.measure_text_px(fresh_fig, 'Test String 123', 14, 'monospace', 'bold')

        assert (w_after, h_after) == (w_fresh, h_fresh)
        plt.close(fig)
        plt.close(fresh_fig)

    def test_many_segments_render_quickly(self):
        # A direct performance regression guard, not just a correctness
        # one -- fails (by timing out under pytest-timeout if configured,
        # or just by taking obviously too long under normal CI limits) if
        # the quadratic redraw behavior ever comes back.
        import time
        from dubois_charts.charts.snake import snake_chart
        segments = {f'Segment {i}': 100 / 30 for i in range(30)}
        t0 = time.time()
        with pytest.warns(UserWarning, match='look alike'):   # 30 colours can't all be distinct
            result_fig = snake_chart(segments=segments, n_rows=8)
        elapsed = time.time() - t0
        plt.close(result_fig)
        assert elapsed < 15.0, (
            f"30-segment snake_chart took {elapsed:.1f}s -- expected well "
            "under 15s; possible regression of the renderer-caching fix."
        )


class TestFitFontsizeToWidth:
    def test_fits_within_bounds(self, fig):
        fs = tu.fit_fontsize_to_width(fig, 'A modest amount of text', 300,
                                       'monospace', 'bold', max_fontsize=24, min_fontsize=6)
        assert 6 <= fs <= 24

    def test_short_text_gets_max_fontsize(self, fig):
        # Plenty of room -- should settle at (or essentially at) the max.
        fs = tu.fit_fontsize_to_width(fig, 'Hi', 5000,
                                       'monospace', 'bold', max_fontsize=24, min_fontsize=6)
        assert fs == pytest.approx(24, abs=0.5)

    def test_result_actually_fits(self, fig):
        text = 'A reasonably long piece of sample text'
        max_w = 250
        fs = tu.fit_fontsize_to_width(fig, text, max_w, 'monospace', 'bold',
                                       max_fontsize=30, min_fontsize=6)
        w, _ = tu.measure_text_px(fig, text, fs, 'monospace', 'bold')
        assert w <= max_w + 1  # binary search tolerance

    def test_empty_text_returns_max_fontsize(self, fig):
        fs = tu.fit_fontsize_to_width(fig, '', 100, 'monospace', 'bold',
                                       max_fontsize=24, min_fontsize=6)
        assert fs == 24

    def test_impossible_width_returns_floor_not_below(self, fig):
        # Even a single character won't fit in 1px at any size >= min --
        # should degrade to min_fontsize rather than raising or going
        # negative.
        fs = tu.fit_fontsize_to_width(fig, 'A very long sentence indeed', 1,
                                       'monospace', 'bold', max_fontsize=24, min_fontsize=6)
        assert fs == pytest.approx(6, abs=0.5)


class TestWrapTextToWidth:
    def test_short_text_stays_one_line(self, fig):
        lines = tu.wrap_text_to_width(fig, 'Short', 500, 12, 'monospace', 'bold')
        assert len(lines) == 1
        assert lines[0] == 'Short'

    def test_long_text_wraps_to_multiple_lines(self, fig):
        text = 'This is a considerably long sentence that will need to wrap'
        lines = tu.wrap_text_to_width(fig, text, 150, 12, 'monospace', 'bold')
        assert len(lines) > 1

    def test_every_line_fits_the_budget(self, fig):
        text = 'This is a considerably long sentence that will need to wrap onto several lines'
        max_w = 200
        lines = tu.wrap_text_to_width(fig, text, max_w, 12, 'monospace', 'bold')
        for line in lines:
            w, _ = tu.measure_text_px(fig, line, 12, 'monospace', 'bold')
            assert w <= max_w + 1

    def test_no_words_lost(self, fig):
        text = 'one two three four five six seven eight'
        lines = tu.wrap_text_to_width(fig, text, 100, 12, 'monospace', 'bold')
        rejoined = ' '.join(lines)
        assert set(rejoined.split()) == set(text.split())

    def test_respects_max_lines(self, fig):
        text = 'one two three four five six seven eight nine ten eleven twelve'
        lines = tu.wrap_text_to_width(fig, text, 60, 12, 'monospace', 'bold', max_lines=2)
        assert len(lines) <= 2

    def test_single_word_wider_than_budget_does_not_crash(self, fig):
        # A pathological case: one "word" (e.g. a long number or slug)
        # wider than the entire budget on its own. Should hard-break
        # rather than infinite-loop or raise.
        lines = tu.wrap_text_to_width(fig, 'Supercalifragilisticexpialidocious', 50,
                                       12, 'monospace', 'bold')
        assert len(lines) >= 1
        assert all(isinstance(ln, str) and ln for ln in lines)


class TestFitTitle:
    def test_short_title_stays_one_line(self, fig):
        lines, fs = tu.fit_title(fig, 'Short Title', 600, start_fontsize=16,
                                  fontfamily='monospace', fontweight='bold')
        assert len(lines) == 1
        assert fs > 0

    def test_long_title_wraps_rather_than_shrinking_to_illegible(self, fig):
        text = ('A Very Long Title That Definitely Cannot Fit On One Line '
                'No Matter How Much It Is Shrunk Because It Is Simply Too Long')
        lines, fs = tu.fit_title(fig, text, 400, start_fontsize=16,
                                  fontfamily='monospace', fontweight='bold', min_fontsize=9)
        assert len(lines) > 1
        assert fs >= 9

    def test_respects_max_lines(self, fig):
        text = ' '.join(['word'] * 60)
        lines, fs = tu.fit_title(fig, text, 200, start_fontsize=16,
                                  fontfamily='monospace', fontweight='bold', max_lines=3)
        assert len(lines) <= 3

    def test_all_words_preserved_across_wrapped_lines(self, fig):
        text = 'The quick brown fox jumps over the lazy dog repeatedly'
        lines, fs = tu.fit_title(fig, text, 250, start_fontsize=16,
                                  fontfamily='monospace', fontweight='bold', max_lines=5)
        assert set(' '.join(lines).split()) == set(text.split())


class TestFitLabelInBox:
    def test_fits_easily_returns_single_line(self, fig):
        result = tu.fit_label_in_box(fig, 'OK', 500, 200, 'monospace', 'bold',
                                      max_fontsize=20, min_fontsize=7, max_lines=2)
        assert result is not None
        lines, fs = result
        assert lines == ['OK']

    def test_genuinely_impossible_returns_none(self, fig):
        # A long label in a tiny box -- should gracefully report "no
        # room" rather than returning something that overflows, which is
        # exactly the contract callers (e.g. area.py's band labels)
        # depend on to fall back to a legend instead of forcing an
        # overlap.
        result = tu.fit_label_in_box(
            fig, 'This label is far too long for this box', 20, 10,
            'monospace', 'bold', max_fontsize=20, min_fontsize=7, max_lines=2
        )
        assert result is None

    def test_result_actually_fits_when_not_none(self, fig):
        text = 'A moderately long label'
        max_w, max_h = 150, 80
        result = tu.fit_label_in_box(fig, text, max_w, max_h, 'monospace', 'bold',
                                      max_fontsize=20, min_fontsize=7, max_lines=3)
        if result is not None:
            lines, fs = result
            for ln in lines:
                w, _ = tu.measure_text_px(fig, ln, fs, 'monospace', 'bold')
                assert w <= max_w + 2

    def test_never_silently_returns_truncated_text(self, fig):
        """
        Regression coverage for a bug found while building snake_chart:
        fit_label_in_box's internal wrap loop called
        wrap_text_to_width(..., max_lines=n_lines), but wrap_text_to_width
        itself truncates-with-ellipsis to satisfy exactly that many lines
        when the real content needs more -- so the `len(lines) > n_lines`
        guard could never fire (the truncated result already complies by
        construction), and a genuinely-too-long label could come back
        looking like a clean, complete fit with an ellipsis silently
        baked into it. Per this function's own documented contract, a
        label that doesn't fit should come back as None (a signal to
        fall back to a legend), never as truncated text disguised as
        success.

        This specific text/box combination was the actual failing case:
        it rendered as "...Recognized Professional…" on a live chart
        before the fix.
        """
        text = 'Percentage Employed in Recognized Professional Occupations  7%'
        result = tu.fit_label_in_box(fig, text, max_width_px=90, max_height_px=79,
                                      fontfamily='monospace', fontweight='bold',
                                      max_fontsize=13, min_fontsize=7, max_lines=2)
        if result is not None:
            lines, fs = result
            assert not any('\u2026' in ln for ln in lines), (
                f"fit_label_in_box returned truncated text instead of None: {lines}"
            )

    def test_many_box_sizes_never_produce_ellipsis(self, fig):
        # Sweep a range of box sizes for the same over-long text -- at
        # every size, the result must be either a complete (non-
        # truncated) fit or None, never something in between.
        text = 'Percentage Employed in Recognized Professional Occupations  7%'
        for w in (40, 80, 120, 200, 350, 504):
            for h in (20, 40, 78.6, 120):
                result = tu.fit_label_in_box(fig, text, w, h, 'monospace', 'bold',
                                              max_fontsize=13, min_fontsize=7, max_lines=2)
                if result is not None:
                    lines, fs = result
                    assert not any('\u2026' in ln for ln in lines), (
                        f"Ellipsis at box ({w}x{h}): {lines}"
                    )


class TestChooseTickLabelStyle:
    def test_short_labels_plenty_of_room_no_rotation(self, fig):
        style = tu.choose_tick_label_style(fig, ['A', 'B', 'C'], available_width_px=900,
                                            n_labels=3, fontsize=12)
        assert style['rotation'] == 0
        assert style['step'] == 1

    def test_long_labels_tight_space_escalates(self, fig):
        labels = [f'A Fairly Long Category Label Number {i}' for i in range(10)]
        style = tu.choose_tick_label_style(fig, labels, available_width_px=400,
                                            n_labels=10, fontsize=13)
        # Should escalate to SOMETHING more aggressive than plain
        # horizontal at full size -- either shrink, rotate, or thin out.
        assert (style['rotation'] != 0 or style['step'] > 1
                or style['fontsize'] < 13)

    def test_zero_labels_does_not_crash(self, fig):
        style = tu.choose_tick_label_style(fig, [], available_width_px=500,
                                            n_labels=0, fontsize=12)
        assert style['step'] == 1

    def test_step_never_exceeds_label_count(self, fig):
        labels = [f'Extremely Long Category Label {i}' * 3 for i in range(5)]
        style = tu.choose_tick_label_style(fig, labels, available_width_px=50,
                                            n_labels=5, fontsize=12)
        assert style['step'] <= 5
