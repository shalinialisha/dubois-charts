"""
Tests of what changes from one operating system to another.

The test suite had only ever run on Linux. These were found by reading
the code for what Windows and macOS do differently.
"""


import pytest

from dubois_charts.charts import choropleth


class TestRegressionFilesAreReadAsUTF8:
    """
    The bundled county boundaries were opened without saying how they
    were encoded, so Windows -- which reads text in its own code page,
    cp1252 -- would have turned "Doña Ana" into "DoÃ±a Ana" and
    "Mayagüez" into "MayagÃ¼ez": the labels garbled, and data spelled
    properly matching nothing.
    """

    @pytest.fixture
    def windows_default_encoding(self, monkeypatch):
        real_open = open

        def cp1252_by_default(file, mode='r', *args, **kwargs):
            if 'b' not in mode and 'encoding' not in kwargs and len(args) < 2:
                kwargs['encoding'] = 'cp1252'
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(choropleth, 'open', cp1252_by_default, raising=False)
        choropleth._us_topology.cache_clear()
        choropleth._state_counties.cache_clear()
        yield
        monkeypatch.undo()
        choropleth._us_topology.cache_clear()
        choropleth._state_counties.cache_clear()

    def test_accented_county_names(self, windows_default_encoding):
        names = {c['name'] for c in choropleth._load_state_counties('35')}
        assert 'Doña Ana' in names
        names = {c['name'] for c in choropleth._load_state_counties('72')}
        assert {'Mayagüez', 'Bayamón', 'Añasco'} <= names

    def test_your_own_geojson(self, windows_default_encoding, tmp_path):
        path = tmp_path / 'one.geojson'
        path.write_bytes(('{"type": "FeatureCollection", "features": [{"type": "Feature", '
                          '"properties": {"NAME": "Doña Ana"}, "geometry": {"type": "Polygon", '
                          '"coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}]}').encode('utf-8'))
        assert [c['name'] for c in choropleth._load_counties(str(path))] == ['Doña Ana']
