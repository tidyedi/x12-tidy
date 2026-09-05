# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --extra dev                      # set up the environment
uv run pre-commit install                # once per clone — guards main, regenerates diagnostics.md
uv run pytest -q                          # full suite (fast, no network, ~0.1s)
uv run pytest tests/test_reconstruct.py::test_sender_delimiters_are_kept   # a single test
uv run python scripts/gen_diagnostics_docs.py           # regenerate docs/diagnostics.md after editing codes.py
uv run python scripts/gen_diagnostics_docs.py --check   # what CI runs — fails if the doc is stale
uv run x12-tidy check path/to/file.edi    # run the checks built so far against a file
```

CI runs exactly two things: `pytest -q` and the `--check` above. There is no lint
or type-check gate — `ruff`/`mypy` are not configured and pre-existing style
warnings are not treated as failures. Don't add a lint step or "fix" unrelated
style unless asked.

All work goes on a feature branch and merges via PR. The `no-commit-to-branch`
pre-commit hook blocks direct commits to `main`.

## What this tool is

Parse **permissively**, report **strictly**. Locate the X12 interchange envelope
even in a malformed file, and emit a `Diagnostic` for *every* deviation from the
standard rather than bailing on the first. Each piece, as it's built, also
**reconstructs** a clean conformant form of what it parsed.

Evaluation lens (important — see `docs/design.md` and the engineering notes): a
terminal input handled with a clean refusal (no result + a `fatal` diagnostic
saying why) **is a success**, not a gap. Do not measure a piece by "parses
everything"; measure it by "correct outcome for every input class."

## Architecture

### The method — anchor on structure, never byte offset

A conventional X12 reader trusts the ISA line's fixed byte positions (element
separator at 3, component separator at 104, terminator at 105, `GS` at 106). One
right-trimmed blank element shifts every offset and the parse collapses. This
codebase inverts that: **recover the delimiters from structure first**, using
only the weakest facts that pin them down (starts with `ISA`, ends just before
`GS`, exactly 16 element separators). Once that returns without a fatal, element
width stops being load-bearing and everything downstream is ordinary parsing plus
repair. `docs/the-x12-tidy-method.md` is the full statement.

### The ISA pipeline (`src/x12_tidy/isa/`)

`clean_isa_line(dirty)` chains three stages, each in its own module, each
returning a result object that accumulates diagnostics from every prior stage:

1. `isa_line.py` — `extract_isa_line` → `IsaLineResult`. Locates the run from
   `ISA` to just before `GS`; strips leading junk (BOM, transport framing).
2. `delimiters.py` — `split_isa_line` → `IsaDecomposition`. Recovers the four
   delimiters and splits the run into 16 raw elements **once** (downstream never
   re-splits). `.usable` = no fatal.
3. `reconstruct.py` — `reconstruct_isa_line` → `ReconstructedIsaLine`. Pads/trims
   each element to its fixed width, reassembles the canonical 105-byte line.
   `.was_clean` = no diagnostics at all.

Delimiters are the **sender's choice** — X12 does not dictate them. Reconstruction
preserves whatever bytes the sender used, including a non-`~` segment terminator;
it only fixes things that cannot be a legal delimiter (wrong element widths,
trailing junk after the terminator, embedded CR/LF). It never guesses intent: an
element overrunning its width with real data is `fatal`, not a truncation.

### Whole-interchange structure (`src/x12_tidy/structure/`)

`split_segments` / `drop_empty_segments` — purely mechanical transforms over
`bytes`, **no diagnostics, no validation, no refusal**. They split the interchange
on the recovered segment terminator and drop `~~` empties. `clean_payload` is
the one-call pipeline built on top of them: clean ISA line + clean (empty-free)
segments, rejoined on the sender's own terminator into one `ReconstructedPayload`.
It refuses (propagating the ISA phase's fatal) exactly when there is no ISA line
to build from; it does no per-segment repair and no envelope judgement — that is
QA/QC, next.

### Envelope QA/QC (`src/x12_tidy/qaqc/`)

`check_payload(ReconstructedPayload) -> QaQcResult` runs once a payload exists.
One pass over `.segments` (a small open-group/open-transaction-set stack) covers
everything decided so far: `ISA`/`IEA`, `GS`/`GE`, `ST`/`SE` pairing and nesting;
control-number agreement and uniqueness; segment/transaction-set/group counts
(`SE01`/`GE01`/`IEA01`); the A5 tag-shape gate; `ISA12`/`GS08` version agreement;
`ISA15` and `GS07` value validity; and foreign content (a segment with no
structurally valid place to be — this is where all `structure.*`/`gs.*`/`st.*`
diagnostics live). Deliberately not covered, no decision made: `ISA05`/`ISA07`
qualifiers, `ISA14`, `GS01`, `ST01` shape, date/time format, `TA1`, `BIN`/`BDS`,
and multiple interchanges in one file.

**`fatal` means something different here than in the ISA-reconstruction phase.**
A payload already exists by the time QA/QC runs, so nothing it finds can undo
that — `fatal` is a display/trust signal ("don't use this payload"), never a
stop signal. Every check always runs to completion regardless of what's found;
nothing in `qaqc` aborts the walk early. Contrast the ISA phase, where `fatal`
does stop parsing.

`x12_tidy.tidy.tidy(dirty: bytes) -> TidyResult` is the whole-package entry
point: `clean_payload` then `check_payload`, one combined diagnostic list
(cleanse findings first). `payload`/`facts` are both `None` only when the file
could not be cleansed at all.

### Diagnostics (`src/x12_tidy/diagnostics/`)

- `Diagnostic` is **severity-free**: code + prose message + byte offset. Nothing
  more.
- `codes.py` is the **single source of truth** for every finding. Modules
  reference `Code.*` members; tests assert on them; **never** use the raw
  `"area.specific"` string. `docs/diagnostics.md` and `x12-tidy codes` are
  generated from this file.
- Severity is resolved at **report time** by `resolved_severity(code)` (registry
  default today, user-config override later), so it's never stored on a
  `Diagnostic` and a config loaded after parsing still applies. `fatal` also
  stops parsing; `error`/`warning` are advisory.
- Code strings are `area.specific`, closed `AREAS` vocabulary, no numbers. The
  `area` is the *subject* of the finding, never the module that raised it (a
  short-ISA-line problem found during recovery is still `isa.*`).
- Adding a code: check `x12-tidy codes --area <area>` first; add the `Code`
  member + `CodeMeta` row; the generated doc and a CI check keep everything
  consistent.

## Tests

- `tests/_isa_helpers.py` — `build_isa()` assembles a whole synthetic interchange
  with every delimiter and element configurable, so each test expresses **exactly
  one deviation**.
- `tests/test_isa_line.py` defines `CASES`, a named corpus reused by
  `test_isa_line_roundtrip.py` and `test_reconstruct.py` (cross-module test
  imports work via pytest's default path insertion).
- Two complementary styles: **per-case** (one deviation → the right repair or the
  right refusal) and **corpus round-trip** (reconstruct → re-parse the
  reconstruction → it's a byte-identical fixed point and none of the codes that
  phase *owns* reappears). Value-level and deliberately-preserved findings (e.g.
  a non-`~` terminator) legitimately survive a round trip.

## Conventions

- Pure functions over `bytes`, never `str`.
- Type hints everywhere; `pathlib.Path` over `os.path`.
- `docs/` holds four engineering notes as `.md` + hand-maintained `.html` + `.pdf`
  plus SVG figures in `docs/figures/`; served at docs.tidyedi.com via GitHub
  Pages. Keep prose and figures in sync with code changes — there is no `.html`
  generator, so edit the `.md` and `.html` together; PDFs are re-printed from the
  live site.
