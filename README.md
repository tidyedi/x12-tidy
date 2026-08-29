# edi-linter

A linter for X12 EDI flat files, built piece by piece.

It parses **permissively** and reports **strictly**: it locates the interchange
envelope even in a malformed file, then emits a `Diagnostic` for every deviation
from the standard rather than bailing on the first. The audience is a developer
who received a bad file from a trading partner and needs to know exactly what is
non-conformant.

📄 **[Finding the Elusive ISA Line](https://ubeast.github.io/edi-linter/finding-the-isa-line.html)**
— a longer-form engineering note on Step 1: why the naive approaches (fixed
offsets, a regex) fail, and the techniques that replace them. ([Markdown
source](docs/finding-the-isa-line.md).)

See also [`docs/`](docs/) for [`design.md`](docs/design.md) (philosophy,
architecture, the diagnostic-code scheme) and [`docs/diagnostics.md`](docs/diagnostics.md)
(every code the linter can emit — generated, do not edit by hand).

## Status

| Piece | State |
| --- | --- |
| **ISA envelope — Step 1: return the ISA line** (`edi_linter.isa.extract_isa_line`) | done |
| ISA envelope — Step 2: decompose the ISA line (elements, delimiters, terminator) | not started |
| ISA envelope — recovery (slow path) | drafted in scratch, not packaged |
| GS / ST / structure | not started |

Superseded work (the old fail-fast `check_isa` and the `rules.*` design notes)
is kept in [`attic/`](attic/) for reference, not built.

## Usage

```bash
uv run edi-linter check path/to/file.edi     # run the checks built so far
uv run edi-linter codes --area isa            # list diagnostic codes
uv run edi-linter explain isa.leading-bytes   # detail for one code
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
hook blocks direct commits to `main`.

Design conventions:

- Pure functions over `bytes`, never `str`.
- Diagnostic codes are `area.specific` names defined only in
  `src/edi_linter/diagnostics/codes.py`; reference `Code.*` symbols, never code
  strings. Tests assert on the symbol.
- `docs/diagnostics.md` is generated; a pre-commit hook and a CI check keep it
  in sync with `codes.py`.
