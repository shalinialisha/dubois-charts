# Contributing to dubois-charts

Thank you for your interest in contributing to dubois-charts! This project aims to honor W.E.B. Du Bois's legacy by making his innovative data visualization principles accessible to modern practitioners.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your Python version and OS

### Suggesting Features

We welcome feature suggestions! Please open an issue with:
- A clear description of the feature
- Why it would be useful
- How it relates to Du Bois's work (if applicable)

### Contributing Code

1. **Fork the repository**
   ```bash
   # Click "Fork" on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/dubois-charts.git
   cd dubois-charts
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

5. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

6. **Run tests**
   ```bash
   pytest tests/ -v
   ```

7. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add feature: description of your feature"
   ```

8. **Push and create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then go to GitHub and create a Pull Request.

## Code Style Guidelines

- **PEP 8**: Follow Python's style guide
- **Type hints**: Add type hints to function signatures
- **Docstrings**: Use NumPy-style docstrings, as below
- **Comments**: Explain *why*, not *what*
- **Names**: Use descriptive variable and function names

### Example:

```python
def get_diverging(n: int = 7, colorblind_safe: bool = None) -> List[str]:
    """
    Get a diverging color palette.

    Parameters
    ----------
    n : int
        Number of colors needed. An odd number has the neutral cream in
        the middle; an even one doesn't.
    colorblind_safe : bool, optional
        Crimson to blue instead of crimson to green. By default, whatever
        `set_colorblind_safe()` last set.

    Returns
    -------
    List[str]
        List of hex color codes from one extreme through neutral to the other

    Examples
    --------
    >>> colors = get_diverging(7)
    >>> len(colors)
    7
    """
    # Implementation
```

## Testing

- Write tests for all new features -- for a bug, a test that fails
  without the fix
- Ensure all existing tests pass
- Aim for >80% code coverage
- Python 3.10 to 3.15 are supported. The automatic tests on GitHub run
  all of them on Linux for every push to `main` and every pull request,
  with the oldest supported numpy, matplotlib and scipy too; and 3.10 and
  3.15 on macOS and Windows for a version tag, or from *Actions -> Tests
  -> Run workflow*
- `tests/test_docs.py` runs every Python example in README.md and every
  docstring example, and checks that every chart's docstring describes
  all its parameters: keep them runnable, and describe new parameters

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=dubois_charts --cov-report=html

# Run specific test file
pytest tests/test_colors.py -v
```

### Reference images

`tests/test_images.py` compares nineteen charts, pixel by pixel, with
the images in `tests/baseline/`. They're compared only with the exact
matplotlib, FreeType, numpy and scipy they were drawn with (listed in
`tests/baseline/environment.json`) and skipped otherwise; the *Image
comparison* job on GitHub installs exactly those. If a change is meant
to change how charts look, draw the references again in that
environment, look at every one, and commit them with the change:

```bash
pip install "matplotlib==3.10.9" "numpy==2.4.4" "scipy==1.17.1"
python tests/test_images.py
```

When the job fails, the images that differ -- each with a picture of
the difference -- are attached to the run as *image-differences*.

### Real data

`tools/check_real_data.py` draws every chart from about forty-five
public data files -- Du Bois's own data for the plates, census,
election, employment, COVID-19, energy, climate and price files, two
Excel workbooks, a table of a column a day, and names of places round
the world -- read with pandas the way a new user would, and reports
which drew, which warned and which stopped with an error (ten should:
data with a missing value, a negative one, a sign or a "%" where a
number belongs, a single x for an area, or places that aren't American
states on the state map). It downloads about 80 MB the first time, and
reads the Excel files with openpyxl (`pip install openpyxl`):

```bash
python tools/check_real_data.py           # pictures in real-data-check/
```

Run it before a release and look at the pictures. Anything it finds
gets a test in `tests/test_real_data.py`, made from a few rows shaped
like the file that showed it, so the test suite itself needs no network.

## Documentation

- Update README.md if you add new features
- Add docstrings to all public functions
- Include examples in docstrings
- Update type hints
- Note the change in CHANGELOG.md, in the section of the version not yet
  released

The tutorial, `docs/tutorial.ipynb`, is kept with its output, so that
GitHub shows the charts. After changing a chart, run it again:

```bash
pip install -e ".[tutorial]"
jupyter nbconvert --to notebook --execute --inplace docs/tutorial.ipynb
```

`examples/basic_usage.py` draws the images in `examples/`, and
`docs/make_gallery.py` makes the picture at the top of the README from
them.

## Areas Where We Need Help

The package now has eight chart types (`bar_chart`, `stacked_area_chart`,
`butterfly_chart`, `spiral_chart`, `snake_chart`, `pie_chart`,
`county_map_chart`, `state_map_chart`), a shared text-fitting engine
(`text_utils.py`), a pixel-verified historical recreation (`plate51.py`),
and about 1,050 tests. See `dubois_charts/charts/GENERAL_ENGINE_README.md` for
the full history of what each chart type needed and what testing found
along the way -- most of what used to be listed here as "high priority"
is done; this section reflects what's genuinely still open.

### Known limitations

Found by running each chart on real data pulled from the web, then on a
stress test of arbitrary data (every input type, size, magnitude and
label text we could think of); details in `GENERAL_ENGINE_README.md`
under "Testing with real data pulled from the web" and "Any data: a
stress test of the first seven charts". Everything else those tests found is
fixed, including repeating colours past eight categories, county labels
chosen by size, colour classes with tied values, `$` signs turning text
into maths, percent signs on data that isn't a percentage, and pandas
years and dates printed as "2018.0" or "2018-01-01 00:00:00".

- Past 20 categories some colours inevitably look alike
  (`get_categorical` warns when they do). Grouping small categories into
  "Other" reads better.
- Emoji draw as empty boxes unless the machine has an emoji font made
  of outlines, which matplotlib draws in black and white (Segoe UI Emoji,
  Noto Emoji or Symbola); Apple's and Google's color emoji are pictures it
  can't draw. Other
  scripts -- Chinese, Japanese, Korean, Arabic, Cyrillic, accented Latin
  -- draw with whichever common font for them is installed (the list is
  `FALLBACK_FONTS` in `dubois_charts/charts/_common.py`).
- On a tightly wound spiral there's no room for most labels beside their
  points, so they go to the points where there is, chiefly on the outer
  turns; only the first, last, highest and lowest points get a leader
  line from deep inside.
- `county_map_chart`'s bundled boundaries for states other than Georgia
  are the Census's 2017 counties. Connecticut's 2022 switch to planning
  regions (data keyed 09110, 09120, ...) and Alaska's 2019 split of
  Valdez-Cordova into Chugach and Copper River aren't in them;
  `geojson_path=` with newer boundaries draws those.
- A callout for a small county in the middle of a state with straight
  borders (Iowa, Kansas, Oklahoma) has a long leader line, because the
  nearest place outside the state is its edge; with many such labels
  (15-20) the map gets crowded. A smaller `label_top_n`, or an explicit
  `label_counties` list, keeps it readable. Labelling all 50 states of
  `state_map_chart` works, but the Northeast's two dozen callouts leave
  a few leader lines crossing.

### High Priority

1. **More geography**: the maps cover the United States -- any state's
   counties, the whole country's counties, and the country by state.
   Other countries' regions work through `geojson_path` one region set
   at a time, in the simple projection meant for one state; a bundled
   world or other-country map would need its own projection and
   insets.
2. **More of the original plates**, recreated and checked against the
   Library of Congress scans the way `plate51.py` is.

### Medium Priority

3. **plate51.py's remaining known gaps**: font letterform accuracy and
   more realistic hand-drawn jitter, documented in `PLATE51_README.md`.
4. **More tutorials**: `docs/tutorial.ipynb` goes through every chart
   type; worked examples on particular kinds of data (Census tables,
   survey results, time series) would help.

### Lower Priority

5. **Integrations**: support other plotting backends (Plotly, Altair)
   for people who don't want a matplotlib `Figure` specifically.
6. **Performance**: a chart of a few hundred bars takes a few seconds,
   most of it matplotlib drawing the labels and writing the image; a
   chart of thousands of points may still have spots worth profiling.


## Historical Accuracy

When adding features inspired by Du Bois's work:
- Reference specific plates when possible
- Include historical context in documentation
- Balance authenticity with modern usability
- Cite sources (Library of Congress, Du Bois book, etc.)

## Code Review Process

All contributions go through code review:
- Maintainers will review your PR
- Address feedback constructively
- Be patient - reviews may take a few days
- Once approved, your PR will be merged!

## Recognition

Contributors will be:
- Mentioned in the changelog (CHANGELOG.md)
- Credited in documentation

## Questions?

- Open an issue on GitHub
- Check existing issues and PRs
- Read the documentation

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to honor Du Bois's legacy and create something valuable for the community.

---

Thank you for contributing to dubois-charts! 🎨
