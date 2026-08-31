# Releasing x12-tidy

Releases publish to PyPI via **Trusted Publishing** (OIDC, no API token) — see
`.github/workflows/release.yml`. A release is cut by pushing a `v*` tag; the
workflow builds, tests, and publishes.

## Checklist

Work on a branch, open a PR, merge, then tag from `main`.

1. **Changelog / notes** — make sure `main` since the last tag is release-ready
   (tests green, docs regenerated).
2. **Bump the version** in both places (they must match):
   - `pyproject.toml` → `[project] version`
   - `src/x12_tidy/__init__.py` → `__version__`
3. **Local check:**
   ```bash
   uv sync --extra dev
   uv run pytest -q
   uv run python scripts/gen_diagnostics_docs.py --check
   uv build          # sanity: wheel + sdist build clean
   ```
4. Merge the version-bump PR to `main`.
5. **Tag and push** from an up-to-date `main`:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
6. Watch the **Release** workflow. On success the version is live at
   <https://pypi.org/project/x12-tidy/>.
7. **Create the GitHub Release** for the tag (release notes).

## First real release only

The following are deferred until the first non-placeholder version is on PyPI
(the current `0.0.1` is a name-reservation placeholder and would misrepresent
the code):

- [ ] **Add the PyPI badges to `README.md`**, in the badge row under the
      `# x12-tidy` heading, before the CI and license badges:
      ```markdown
      [![PyPI](https://img.shields.io/pypi/v/x12-tidy)](https://pypi.org/project/x12-tidy/)
      [![Python](https://img.shields.io/pypi/pyversions/x12-tidy)](https://pypi.org/project/x12-tidy/)
      ```
- [ ] Add an install line to the README quick-start (`pip install x12-tidy` /
      `uv add x12-tidy`).
- [ ] Confirm the PyPI project description (rendered from `README.md`) looks
      right — relative links resolve against the repo, badges load.
