# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `isa.element-embedded-newline` now deletes an embedded CR/LF instead of
  replacing it with a space — a newline inside a fixed-width ISA element is wrap
  noise, never data, so deleting it stitches the value back to what the sender
  wrote (`RECEIV\r\nER` → `RECEIVER`, not `RECEIV  ER`). (#83)

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
