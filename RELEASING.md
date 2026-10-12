# Releasing

A release is a version of the repository -- a tag, and a GitHub release
made from it -- and, once the repository is public, the same version on
PyPI.

## Each release

1. Run `python tools/check_real_data.py` and look at the pictures it
   draws in `real-data-check/` (CONTRIBUTING.md, "Real data").
2. Set the new version in `dubois_charts/__init__.py` (`__version__`) --
   the only place it's written -- and in CHANGELOG.md give that
   version's section today's date in place of "Unreleased".
3. Commit, tag the commit with the version and push both:

   ```bash
   git tag v0.2.0
   git push origin main v0.2.0
   ```

   A version tag runs the *Tests* workflow in full: on Linux, Python 3.10
   to 3.15, the oldest supported numpy, matplotlib and scipy, the image
   comparisons, and a build installed into a clean environment; on macOS
   and Windows, Python 3.10 and 3.15. Wait for it to pass.
4. Publish a release on GitHub from that tag. While the repository is
   private, that's the whole release: people with access to it install
   that version with
   `pip install git+https://github.com/OWNER/dubois-charts.git@v0.2.0`.
   Once the repository is public, publishing the release also uploads the
   package to PyPI, as below.

A version number is used once: if something is wrong with a release, fix
it and release the next version.

## PyPI

Publishing a release on GitHub runs `.github/workflows/release.yml`,
which builds the package, checks it, and -- if the repository is public
-- uploads it to PyPI. PyPI trusts that workflow directly ("trusted
publishing"), so no password or token is kept anywhere. From a private
repository the upload is skipped: a package on PyPI whose source and
issues no one can see isn't much use.

Once, before the first upload:

1. Make the repository public (*Settings -> General -> Danger Zone*).
2. In README.md -- which is also the package's page on PyPI -- replace
   "isn't on PyPI yet" and the instructions after it with
   `pip install dubois-charts`, and take out the note that the
   repository is private. Make the picture and the links to files in the
   repository absolute, or they lead nowhere on PyPI: the picture
   `https://raw.githubusercontent.com/OWNER/dubois-charts/main/docs/gallery.png`,
   the files `https://github.com/OWNER/dubois-charts/blob/main/...`.
3. Create an account on [pypi.org](https://pypi.org) and turn on
   two-factor authentication. Under *Your account -> Publishing*, add a
   **pending publisher**:
   - PyPI project name: `dubois-charts`
   - Owner and repository: the GitHub owner and repository name
   - Workflow name: `release.yml`
   - Environment name: `pypi`
4. On GitHub, under *Settings -> Environments*, create an environment
   called `pypi`, and add yourself as a required reviewer there, so that
   every upload waits for your approval. (On GitHub's free plan,
   environments are for public repositories only -- another reason the
   upload waits until the repository is public.)
