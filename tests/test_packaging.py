"""
Packaging checks: does the package, as it would actually be installed,
declare everything it needs?

Every other test in this suite runs from the source tree (conftest.py puts
the repo root on sys.path) with whatever happens to be installed in the
developer's environment. That is exactly why none of them caught the
problem these tests guard against: scipy was used -- lazily, inside the
texture functions and plate51.py -- but never declared as a dependency,
and the two data files the code opens at runtime (the Georgia county
boundaries and the Plate 51 reference scan) were never listed as package
data. From the source tree with scipy already installed, everything
worked. From a clean `pip install` into a fresh virtual environment, five
of the seven chart functions crashed with ModuleNotFoundError on their
default settings, and county_map_chart couldn't find its own data.

These tests read pyproject.toml directly, so they catch the same mistakes
without having to build and install the package.
"""

import ast
import glob
import os
import sys

import pytest

try:
    import tomllib                     # standard library from Python 3.11
except ImportError:                    # Python 3.10: the same parser, as a package
    tomllib = pytest.importorskip("tomli")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "dubois_charts")
CHARTS_DIR = os.path.join(PKG_DIR, "charts")

# Import name -> distribution name, where the two differ.
_DIST_NAME = {"PIL": "pillow", "sklearn": "scikit-learn", "yaml": "pyyaml"}


def _pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)


def _declared_dependencies():
    names = set()
    for spec in _pyproject()["project"]["dependencies"]:
        name = spec.split(";")[0]  # drop environment markers
        for sep in "<>=!~[ ":
            name = name.split(sep)[0]
        names.add(name.strip().lower())
    return names


def _third_party_imports():
    """Top-level modules imported anywhere under dubois_charts/, at any
    indentation -- lazy imports inside functions count, since that is
    exactly where scipy was hiding. Standard-library modules and dubois_charts
    itself are excluded. Returns {module: first file that imports it}."""
    stdlib = set(sys.stdlib_module_names)
    found = {}
    for path in sorted(glob.glob(os.path.join(PKG_DIR, "**", "*.py"), recursive=True)):
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                top = module.split(".")[0]
                if top in stdlib or top == "dubois_charts":
                    continue
                found.setdefault(top, os.path.relpath(path, ROOT))
    return found


def _package_data_matches(package="dubois_charts.charts"):
    """Files under dubois_charts/charts/ matched by pyproject's package-data
    globs, as paths relative to dubois_charts/charts/."""
    patterns = (_pyproject().get("tool", {}).get("setuptools", {})
                .get("package-data", {}).get(package, []))
    matched = set()
    for pattern in patterns:
        for path in glob.glob(os.path.join(CHARTS_DIR, pattern)):
            matched.add(os.path.relpath(path, CHARTS_DIR))
    return matched


def _runtime_data_files():
    """Data files the code actually opens at runtime, taken from the
    modules' own path constants rather than a hand-maintained list, so a
    renamed or moved file shows up here automatically."""
    from dubois_charts.charts import choropleth, plate51
    return {
        "county_map_chart's county boundaries": choropleth._DEFAULT_GEOJSON_PATH,
        "county_map_chart's boundaries for every state": choropleth._US_COUNTIES_PATH,
        "the licence of those boundaries": os.path.join(CHARTS_DIR, "data", "us-atlas-LICENSE.txt"),
        "plate51's reference scan": plate51._DEFAULT_REFERENCE_PATH,
    }


def test_every_third_party_import_is_a_declared_dependency():
    declared = _declared_dependencies()
    missing = {module: where for module, where in _third_party_imports().items()
               if _DIST_NAME.get(module, module).lower() not in declared}
    assert not missing, (
        "Imported by the package but not declared in pyproject.toml "
        f"[project].dependencies (module -> first file using it): {missing}. "
        "A clean `pip install` won't install these, so the code that "
        "imports them fails for users even though it works from the "
        "source tree."
    )


def test_scipy_specifically_is_declared():
    # The exact dependency that was missing, pinned down by name in case
    # the general scan above is ever loosened.
    assert "scipy" in _declared_dependencies()


@pytest.mark.parametrize("label", ["county_map_chart's county boundaries",
                                   "county_map_chart's boundaries for every state",
                                   "the licence of those boundaries",
                                   "plate51's reference scan"])
def test_runtime_data_file_ships_with_the_package(label):
    path = _runtime_data_files()[label]
    assert os.path.exists(path), f"{label} is missing from the source tree: {path}"
    rel = os.path.relpath(path, CHARTS_DIR)
    assert rel in _package_data_matches(), (
        f"{label} ({rel}) isn't matched by [tool.setuptools.package-data] "
        "in pyproject.toml, so it won't be included in an installed copy "
        "of the package."
    )
