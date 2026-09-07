<h1>
  <img src="https://raw.githubusercontent.com/tidyedi/x12-tidy/main/docs/images/brand/tidyedi-mark.png" alt="" width="48" height="48" align="left">
  &nbsp;x12-tidy
</h1>

[![PyPI](https://img.shields.io/pypi/v/x12-tidy)](https://pypi.org/project/x12-tidy/)
[![Python](https://img.shields.io/pypi/pyversions/x12-tidy)](https://pypi.org/project/x12-tidy/)
[![CI](https://github.com/tidyedi/x12-tidy/actions/workflows/ci.yml/badge.svg)](https://github.com/tidyedi/x12-tidy/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/tidyedi/x12-tidy/blob/main/LICENSE)

![x12-tidy — validate and repair malformed ANSI X12 EDI](https://raw.githubusercontent.com/tidyedi/x12-tidy/main/docs/images/brand/social-card-1280x640.png)

Validate and repair malformed ANSI X12 EDI, built piece by piece. The free
CLI and Python library behind [TidyEDI](https://repair.tidyedi.com).

x12-tidy parses **permissively** and reports **strictly**: it locates the
interchange envelope even in a malformed file and emits a `Diagnostic` for every
deviation from the standard rather than bailing on the first. As it grows, each
piece also reconstructs the structure it parsed into a clean, conformant form —
so the end state is not just "here is what is wrong" but "here is a fixed copy."
The audience is a developer who received a bad file from a trading partner and
needs to know exactly what is non-conformant. (If "X12 linter" is what you
searched for, yes, that too.)

## Docs

**Engineering notes** — the method, then one note per piece of the parse, at
[docs.tidyedi.com](https://docs.tidyedi.com):

- [The x12-tidy Method](https://docs.tidyedi.com/the-x12-tidy-method.html)
  — the one idea: earn the delimiters from structure first, then the rest is easy
- [Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)
  — locating the ISA line when fixed byte offsets and a regex both fail
- [Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)
  — reading the four delimiters from a line whose byte offsets have moved
- [Reconstructing the ISA Line](https://docs.tidyedi.com/reconstructing-the-isa-line.html)
  — rebuilding the canonical 105-byte line once the delimiters are trusted
- [Reassembling the Interchange](https://docs.tidyedi.com/reassembling-the-interchange.html)
  — splitting the body into segments and rejoining it with the ISA line into one payload
- [Auditing the Envelope](https://docs.tidyedi.com/auditing-the-envelope.html)
  — checking whether the interchange's own bookkeeping (pairing, counts, control numbers) is honest

**Using it** — [`docs/using-x12-tidy.md`](https://github.com/tidyedi/x12-tidy/blob/main/docs/using-x12-tidy.md):
the CLI, the `tidy()` one-call API, the lower-level building blocks, and
formatting your own report.

**Reference** — [`design.md`](https://github.com/tidyedi/x12-tidy/blob/main/docs/design.md)
(architecture, the diagnostic-code scheme) ·
[`docs/diagnostics.md`](https://github.com/tidyedi/x12-tidy/blob/main/docs/diagnostics.md)
(every code, generated) ·
the [`docs/`](https://github.com/tidyedi/x12-tidy/tree/main/docs) folder holds
the Markdown sources and PDFs.

## Status

| Piece | State |
| --- | --- |
| **ISA envelope — locate the ISA line** (`x12_tidy.envelope.isa.extract_isa_line`) | done |
| **ISA envelope — recover the four delimiters** (`x12_tidy.envelope.isa.split_isa_line`) | done |
| **ISA envelope — reconstruct the canonical line** (`x12_tidy.envelope.isa.reconstruct_isa_line`) | done |
| **Whole-document cleanse** (`x12_tidy.envelope.structure.clean_payload`) | done |
| **GS / ST / structure — envelope and control-number QA/QC** (`x12_tidy.envelope.qaqc.check_payload`) | done |

## Usage

```bash
pip install x12-tidy       # or: uv add x12-tidy
```

```bash
x12-tidy check path/to/file.edi      # run the checks built so far
x12-tidy codes --area isa            # list diagnostic codes
x12-tidy explain isa.leading-bytes   # detail for one code
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
hook blocks direct commits to `main`. Cutting a release:
[`docs/RELEASING.md`](https://github.com/tidyedi/x12-tidy/blob/main/docs/RELEASING.md).

Design conventions:

- Pure functions over `bytes`, never `str`.
- Diagnostic codes are `area.specific` names defined only in
  `src/x12_tidy/diagnostics/codes.py`; reference `Code.*` symbols, never code
  strings. Tests assert on the symbol.
- `docs/diagnostics.md` is generated; a pre-commit hook and a CI check keep it
  in sync with `codes.py`.

## License

[Apache License 2.0](https://github.com/tidyedi/x12-tidy/blob/main/LICENSE) — © 2026 Michael Schertz.
See [`NOTICE`](https://github.com/tidyedi/x12-tidy/blob/main/NOTICE).

"TidyEDI" and the TidyEDI logo are trademarks of Michael Schertz; the license
covers the code, not the name or the mark.
