# x12-tidy

<img src="docs/brand/tidyedi-mark.png" alt="" width="72" height="72" align="right">

[![CI](https://github.com/tidyedi/x12-tidy/actions/workflows/ci.yml/badge.svg)](https://github.com/tidyedi/x12-tidy/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Validate and repair malformed ANSI X12 EDI, built piece by piece. The free
CLI and Python library behind [TidyEDI](https://tidyedi.com).

x12-tidy parses **permissively** and reports **strictly**: it locates the
interchange envelope even in a malformed file and emits a `Diagnostic` for every
deviation from the standard rather than bailing on the first. As it grows, each
piece also reconstructs the structure it parsed into a clean, conformant form —
so the end state is not just "here is what is wrong" but "here is a fixed copy."
The audience is a developer who received a bad file from a trading partner and
needs to know exactly what is non-conformant. (If "X12 linter" is what you
searched for, yes, that too.)

📄 **[Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-isa-line.html)**
— a longer-form engineering note on Step 1: why the naive approaches (fixed
offsets, a regex) fail, and the techniques that replace them. ([Markdown
source](docs/finding-the-isa-line.md).)

See also [`docs/`](docs/) for [`design.md`](docs/design.md) (philosophy,
architecture, the diagnostic-code scheme) and [`docs/diagnostics.md`](docs/diagnostics.md)
(every code x12-tidy can emit — generated, do not edit by hand).

## Status

| Piece | State |
| --- | --- |
| **ISA envelope — Step 1: return the ISA line** (`x12_tidy.isa.extract_isa_line`) | done |
| ISA envelope — Step 2: decompose the ISA line (elements, delimiters, terminator) | not started |
| ISA envelope — recovery (slow path) | drafted in scratch, not packaged |
| GS / ST / structure | not started |

Superseded work (the old fail-fast `check_isa` and the `rules.*` design notes)
is kept in [`attic/`](attic/) for reference, not built.

## Usage

```bash
uv run x12-tidy check path/to/file.edi     # run the checks built so far
uv run x12-tidy codes --area isa            # list diagnostic codes
uv run x12-tidy explain isa.leading-bytes   # detail for one code
```

`check` exit codes: `0` clean (or warnings only), `1` a fatal/error finding,
`2` usage / IO problem.

## Development

```bash
uv sync --extra dev
uv run pre-commit install     # once per clone: guards main, regenerates docs
uv run pytest
uv run python scripts/gen_diagnostics_docs.py   # after changing codes.py
```

All work goes on a feature branch and merges via PR — the `no-commit-to-branch`
hook blocks direct commits to `main`. Cutting a release: [`docs/RELEASING.md`](docs/RELEASING.md).

Design conventions:

- Pure functions over `bytes`, never `str`.
- Diagnostic codes are `area.specific` names defined only in
  `src/x12_tidy/diagnostics/codes.py`; reference `Code.*` symbols, never code
  strings. Tests assert on the symbol.
- `docs/diagnostics.md` is generated; a pre-commit hook and a CI check keep it
  in sync with `codes.py`.

## License

[Apache License 2.0](LICENSE) — © 2026 Michael Schertz. See [`NOTICE`](NOTICE).

"TidyEDI" and the TidyEDI logo are trademarks of Michael Schertz; the license
covers the code, not the name or the mark.
