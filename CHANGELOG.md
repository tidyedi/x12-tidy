# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Bad envelopes no longer certify their parents.** An envelope (`ST`/`SE`,
  `GS`/`GE`) is now only "good" if it closed, its stated count matches the
  real count of *good* children, and its closer's control number matches its
  opener's — not just a numeric match, since two envelopes whose segments got
  interleaved can still show a coincidentally-correct count. A bad `ST`/`SE`
  is excluded from its `GS`'s good count outright, so a `GS` containing even
  one bad transaction set is itself never good — even if `GE01` happens to
  numerically match what's left after excluding it. Same pattern one level up
  for `GS`/`IEA`. Each level tracks its own children's good/bad status
  explicitly rather than inferring it from a downstream mismatch, which would
  miss the rare case where the numbers still coincidentally add up. This is
  strictly a validation-only concept — `EnvelopeFacts.functional_group_count`
  and `.transaction_set_count` remain raw, unconditional tallies of what was
  actually seen, unaffected by this change.
- **`isa.version-too-old`** (fatal) — refuses an ISA12 release below `00304`
  (release 003040), the earliest release documented to define the ISA
  segment at all (Stedi's per-release segment dictionaries report "Segment
  ISA is not present in X12 Release 3010"). x12-tidy has not verified a
  standard for anything earlier, so the 16-element, 105-byte ISA shape a
  parse assumes cannot be trusted for a file that claims to predate it.
  (#88)

### Changed

- `isa.separator-count-high` no longer fires for "no real `GS` header anywhere
  in the file" (a stray `REF*GS*` with no functional-group envelope) or "ISA
  missing elements, but a real `GS` follows" — both now report
  `isa.gs-not-found`, which names the actual problem. `isa.separator-count-high`
  still fires for a genuine delimiter collision between the 16th separator and
  the real `GS` header.

### Fixed

- `isa.element-embedded-newline` now deletes an embedded CR/LF instead of
  replacing it with a space — a newline inside a fixed-width ISA element is wrap
  noise, never data, so deleting it stitches the value back to what the sender
  wrote (`RECEIV\r\nER` → `RECEIVER`, not `RECEIV  ER`). (#83)
- **Silent mis-parse on a truncated ISA line.** When the ISA segment was
  missing elements and immediately followed by a real `GS` segment,
  `extract_isa_line`'s separator-count check could land on a coincidental
  match inside `GS`'s own field data (e.g. `SENDERGS*`) and accept it as the
  ISA boundary with **no diagnostic at all**. Step 1 now counts forward to the
  16th element separator first, then only accepts `GS` if everything up to it
  is non-alphanumeric and not another element separator — the
  ISA06/ISA08-embedded-`GS` and deep-in-transaction-body `REF*GS*` false-match
  cases are eliminated structurally instead of being caught after the fact.
- **A `GS` missing its `GE` was still counted toward the interchange's own
  functional-group tally.** `_close_group` incremented the interchange-level
  count before checking whether `GE` was even found, so a broken group could
  silently satisfy `IEA01` instead of triggering
  `structure.functional-group-count-mismatch`. Fixed as part of the cascade
  above.
- **ISA13 padding and comparison.** A short ISA13 (Interchange Control
  Number, the one ISA element typed numeric) is now space-padded on the
  *left* — right-justified, matching its numeric type — instead of the
  right like every other ISA element, and never zero-filled: inventing
  digits to fill it out would assert a value beyond what the sender
  actually sent. Separately, the ISA13-vs-IEA02 comparison now trims
  padding and compares as strings, not as numbers — ISA13 is fixed-width
  while IEA02 is an ordinary delimited field and is typically not padded
  at all, so a byte-for-byte comparison was spuriously reporting
  `structure.control-number-mismatch` for control numbers that actually
  agreed. (#88)

### Documentation

- `design.md`: corrected a note claiming a literal `ISA` inside an ISA06/ISA08
  element value was an uncaught gap deferred to Step 2 — nothing past Step 1
  ever searches for those bytes, so there was never anything to catch.
- `finding-the-elusive-isa-line.md` (and its published `.html`) rewritten to
  match the new Step 1 mechanism above, with a worked example of the bug it
  fixes; §5.3 and `design.md`'s multi-candidate note now flag explicitly that
  "keep the first ISA that parses" is single-interchange behavior, not yet a
  policy for a flat file containing several real, independent interchanges
  (tracked separately, see `auditing-the-envelope.md` §7).
- `auditing-the-envelope.md` (and its `.html`) §3: documents the good/bad
  cascade above, and that it's validation-only, never reflected in
  `EnvelopeFacts`.

## [0.1.0] — 2026-09-07

First release. Everything that locates and cleans the X12 interchange
**envelope** — parse permissively, report strictly, and reconstruct a
conformant form of whatever was parsed.

### Added

- **ISA line** — locate the `ISA` run in a file that strips, prepends to, or
  re-encodes it; recover the four delimiters from structure rather than byte
  offset; reconstruct the canonical 105-byte line
  (`x12_tidy.envelope.isa`).
- **Whole-payload cleanse** — split the interchange on the recovered segment
  terminator, drop empty segments, rejoin on the sender's own terminator into
  one `ReconstructedPayload` (`x12_tidy.envelope.structure.clean_payload`).
- **Envelope QA/QC** — one pass over the segments checking `ISA`/`IEA`,
  `GS`/`GE`, `ST`/`SE` pairing and nesting; control-number agreement and
  uniqueness; segment/transaction-set/group counts; envelope-segment element
  cardinality; `ISA12`/`GS08` version agreement; `ISA15` and `GS07` value
  validity; and foreign content
  (`x12_tidy.envelope.qaqc.check_payload`).
- **`tidy(dirty: bytes) -> TidyResult`** — the one-call entry point
  (cleanse, then audit), re-exported as `x12_tidy.tidy`.
- **`x12-tidy` CLI** — `check`, `codes`, and `explain`.
- **Diagnostic-code registry** — severity-free `Diagnostic` (code + message +
  byte offset); severity resolved at report time; `docs/diagnostics.md` and
  `x12-tidy codes` generated from `codes.py` and kept in sync by CI.
- Six engineering notes at [docs.tidyedi.com](https://docs.tidyedi.com).

### Not covered (deliberately, for a later release)

Multiple interchanges in one file; `ISA05`/`ISA07` qualifiers; `ISA14`;
`GS01`; `ST01` shape; date/time format; `TA1`; `BIN`/`BDS`; transaction-set
content.

[Unreleased]: https://github.com/tidyedi/x12-tidy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tidyedi/x12-tidy/releases/tag/v0.1.0
