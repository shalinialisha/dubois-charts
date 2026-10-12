"""
Fonts for the tests: a way to hide every font but the ones that ship
with matplotlib (DejaVu, STIX, Computer Modern) -- what a machine with no
fonts of its own offers, and the same on every machine.
"""

import contextlib
import os

import matplotlib
import matplotlib.font_manager as fm
import pytest

from dubois_charts.charts import _common


def clear_font_caches():
    fm.fontManager._findfont_cached.cache_clear()
    fm._get_font.cache_clear()
    _common._installed_fonts.cache_clear()


@contextlib.contextmanager
def matplotlibs_fonts_only():
    bundled = os.path.abspath(os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data'))
    patch = pytest.MonkeyPatch()
    patch.setattr(fm.fontManager, 'ttflist',
                  [f for f in fm.fontManager.ttflist
                   if os.path.abspath(f.fname).startswith(bundled)])
    clear_font_caches()
    try:
        yield
    finally:
        patch.undo()
        clear_font_caches()
