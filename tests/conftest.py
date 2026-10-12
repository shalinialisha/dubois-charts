"""
Shared pytest configuration.

Sets the Agg (non-interactive, file-only) backend before any test imports
matplotlib.pyplot, since these tests run headless and several chart
functions call fig.canvas.get_renderer() / fig.savefig(), which need a
real renderer backend to exist even when nothing is actually displayed.
"""

import os
import sys

# Make sure `import dubois_charts` resolves to the package in this repo even if
# it isn't pip-installed -- mirrors how every manual test script in this
# project has run it, so `pytest` works the same way without requiring
# `pip install -e .` first.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pytest


@pytest.fixture(autouse=True)
def _close_figures():
    """Close every figure a test leaves open: a map of the country's 3,200
    counties is large, and a few left open add up over the suite."""
    yield
    plt.close('all')


@pytest.fixture
def only_matplotlibs_fonts():
    """Hide every font but the ones that ship with matplotlib (DejaVu, STIX,
    Computer Modern) -- what a machine with no fonts of its own offers."""
    from tests._fonts import matplotlibs_fonts_only
    with matplotlibs_fonts_only():
        yield


@pytest.fixture
def fig():
    """A fresh figure for text_utils measurement tests, closed afterward
    so repeated test runs don't accumulate open figures in memory."""
    f = plt.figure(figsize=(8, 6), dpi=100)
    yield f
    plt.close(f)
