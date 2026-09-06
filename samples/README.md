# Sample EDI interchanges

Real-world sample files used to exercise x12-tidy end to end. Each one is checked
in verbatim from its source, with its provenance and what it demonstrates
recorded here.

Run one with:

```bash
uv run x12-tidy check samples/<file>.edi
```

---

## `dlms-831-application-control-totals.edi`

**Source:** Defense Logistics Management Standards (DLMS). Distributed by DLMS as
a worked ISA/GS/ST example alongside the notes below.

**DLMS's own annotations of the file:**

> - Data Element Separator = `*` (Asterisk). Defined in the fourth position of
>   the ISA Segment.
> - Component Element Separator = `|` (Pipe / Vertical Bar). Defined in the 3rd
>   to last position of the ISA segment.
> - Segment Terminator = `~` (Tilde). First occurrence defines the segment
>   termination.

**Notable features (why it's a good test):**

- The ISA segment is split across **two physical lines** — a line break falls
  inside ISA08.
- Several ISA elements are **shorter than their fixed width**, padded with a
  single space instead of the full run (`ISA02`, `ISA04` = 1 byte; `ISA06`,
  `ISA08` carry a stray trailing space). This is exactly the "right-trimmed blank
  element shifts every byte offset" case the x12-tidy method is built for.
- Component separator is `|`, and `|` is then used for real inside `RCD` and the
  composite in `RCD01` (`EA|2|1`).
- `ISA11` is `U` while `ISA12` is `00403` — at 004030 `ISA11` is the repetition
  separator, not the standards-ID `U`.
- A newline sits between the ISA segment terminator and `GS`.
- **The ISA segment carries 17 element separators, not 16** — there is a stray
  `*` between `ISA16` (`|`) and the terminator (`~`), i.e. the run ends `...*|*~`
  rather than `...*|~`. DLMS's prose ("`|` in the 3rd-to-last position") matches
  the bytes as written, so the extra separator is in the sample as distributed.

**What x12-tidy reports (as distributed):**

```
[FATAL isa.separator-count-high] ... 17 element separator(s) (b'*') precede [GS] --
an ISA header has 16, so this is not the functional-group header.
```

A clean refusal with a specific reason. Per the project's evaluation lens
(`docs/design.md`), that is the **correct outcome** for this input: the structural
anchor (exactly 16 element separators between `ISA` and `GS`) does not hold, so
the tool stops rather than guess which `*` is spurious.

**What it reports once the single stray `*` is removed** (`...*|*~` → `...*|~`) —
kept here only to show the downstream findings the fatal currently masks:

```
[ERROR   isa.repetition-separator-missing] ISA12 00403 defines ISA11 as the repetition
                                           separator, but ISA11 is 'U'.
[ERROR   isa.element-width]                 ISA02 is 1 byte; padded to 10.
[ERROR   isa.element-width]                 ISA04 is 1 byte; padded to 10.
[ERROR   isa.element-width]                 ISA06 is 11 bytes; padded to 15.
[ERROR   isa.element-width]                 ISA08 is 11 bytes; padded to 15.
[WARNING isa.trailing-newline]              newline between the terminator and GS.
[WARNING isa.element-embedded-newline]      ISA08 contains a line-feed byte; replaced with a space.
```

**Ties to the diagnostic-code review** (`DIAGNOSTICS-REVIEW.md`): this file is the
concrete artifact for two items under review —

- `isa.trailing-newline` — the newline after `~` here is now known to be
  conformant (assumption A7; `docs/research/x12-delimiter-and-terminator-legality.md`),
  so this finding should go away.
- `isa.separator-count-high` — whether a single stray `*` immediately before the
  terminator should be recoverable rather than fatal is an open question this
  sample raises but the review has not decided.
