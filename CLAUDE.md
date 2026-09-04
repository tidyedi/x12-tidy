# x12-tidy

Validate and repair malformed ANSI X12 EDI. The free CLI and Python library behind
[TidyEDI](https://tidyedi.com). Repo lives under the **`tidyedi/`** org, not `ubeast/`.

## The design stance

- **Parse permissively, report strictly.** Locate the interchange envelope even in a
  malformed file; emit a `Diagnostic` for every deviation from the standard rather
  than bailing on the first.
- Each piece also **reconstructs** the structure it parsed into a clean, conformant
  form — the end state is "here is a fixed copy," not just "here is what's wrong."
- **The method:** earn the four delimiters from structure first; once you have them,
  the rest of the parse follows. The engineering notes in `docs/` (published to
  docs.tidyedi.com) cover it, one note per parse piece.

## Zero runtime dependencies

`dependencies = []` and it stays that way — **standard library only** in
`src/x12_tidy/`. Dev-only tools (`pytest`, `pre-commit`) are in the `dev` extra.

## Layout

```
src/x12_tidy/                the package — cli.py:main, parser pieces, codes registry
tests/                       _isa_helpers.py holds shared fixtures
scripts/gen_diagnostics_docs.py   generates docs/diagnostics.md FROM the code
conftest.py (repo root)      adds repo root to sys.path so tests can import scripts/
docs/                        GitHub Pages site (CNAME docs.tidyedi.com) — brand assets,
                             SVG figures, engineering notes as .md + .html + .pdf
```

## Env & checks

Python 3.11+. `uv sync --extra dev`. `pre-commit` is configured.

```bash
uv run pytest -q
uv run python scripts/gen_diagnostics_docs.py --check   # CI fails if docs are stale
uv build
```

## Gotcha

When you add or change a `Diagnostic`, **regenerate the docs**
(`python scripts/gen_diagnostics_docs.py`, without `--check`) and commit the result —
CI runs the `--check` form and will fail otherwise.
