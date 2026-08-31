# x12-tidy — rule catalog

One table per build piece. Every row is a single check the linter performs:
its severity, what the emitted message should tell the reader, and any safe
cleaning action. This file is the human-facing companion to the code.

**Rule codes.** Each rule will get a permanent, stable code — assigned once,
never renumbered, never reused — so tests can assert on it (message wording
stays free to change), a developer can suppress one finding by it, and CI and
bug reports can name a finding unambiguously. The scheme is not chosen yet: an
`ISAnnn` scheme is out because it collides with the X12 element names
`ISA01`..`ISA16`. Until then codes are tracked as `(tbd)` and kept out of the
table to save width; the `#` column is display order only and renumbers when
rules are inserted.

**Approval.** Each piece has two tables — **Approved** and **Not yet
approved**. A rule keeps its number when it moves between them, so numbers may
be out of order in a table; that is expected. A piece is done when its
Not-yet-approved table is empty.

**Group / Sub-category.** `Group` is a short slug naming the part of the file
a rule inspects (`filecheck`, `isa_line`, …); rules in the same group are
typically evaluated from one shared piece of work. `Sub-category` names the
specific aspect within that group (`delimiter`, `number of elements`, …); it is
a fixed slug and need not match the wording of the check (e.g. `delimiter`
covers the element separator).
`?` = not yet assigned.

## Conventions

**Philosophy — permissive parse, strict report.** The audience is a developer
who has received a non-conformant file from a trading partner. The linter
locates the envelope and delimiters even in a malformed file, then emits a
diagnostic for *every* deviation. It reports problems; it never repairs them
silently.

**Cleaning action** — where a deviation has a safe, unambiguous remediation,
the rule names it. A cleaning action is only ever applied on explicit request
(and to a copy), never as part of a lint run. `—` means there is no safe
automatic fix; the developer must go back to the sender.

**Severity** — one axis, and it fully determines whether parsing stops.

| Severity | Meaning | Parsing |
|----------|---------|---------|
| `fatal` | A violation that also leaves the rest of the file unparseable. Clears `ok`. | **stops** — the linter records the diagnostic and returns |
| `error` | A conformance violation the linter can parse past. Clears `ok`. | **continues** — later independent problems are still reported |
| `warning` | Unusual, not a violation. Does not clear `ok`. | continues |

**Diagnostic shape** — `Diagnostic(code, severity, message, offset)`, where
`offset` is a byte offset into the source file (or `None`).

---

## Piece 1 — ISA envelope bootstrap

`x12_tidy.envelope.check_isa(data: bytes) -> IsaResult`

An X12 interchange begins with a single fixed-layout `ISA` segment. Its
delimiters are declared positionally inside it, which lets the linter discover
them before it knows anything else about the file.

#### ✅ Approved

| # | Group | Sub-category | Check | Severity | Message intent | Cleaning action |
|---|-------|--------------|-------|----------|----------------|-----------------|
| 1 | `filecheck` | `not empty` | File is not empty | fatal | The file contains no bytes. There is no interchange to lint. | — |
| 2 | `isa_line` | `presence` | **From the single `ISA` search** — a match exists | fatal | No `ISA` tag appears anywhere in the file. The file is not a recognizable X12 interchange, so no further checks can run. | — |
| 3 | `isa_line` | `position` | **From the single `ISA` search** — the match is at byte 0 | error | The first `ISA` tag begins at byte N, not byte 0. The N preceding byte(s) are _\<identification\>_. An X12 interchange must begin at byte 0; the standard permits no byte-order mark and no leading whitespace. Parsing continues from the `ISA` tag. | Remove every byte before the `ISA` tag. |
| 4 | `isa_line` | `delimiter` | **From the single `ISA` search** — position 4, the element separator, is present | fatal | The `ISA` tag occupies positions 1–3; position 4 is always the element separator for the whole interchange. The file ends at position 3, so the element separator is absent, the ISA header cannot be read, and the interchange is truncated. | — |
| 5 | `isa_line` | `delimiter` | The element separator at position 4 is not alphanumeric | fatal | The element separator at position 4 is `0xNN` (`'X'`), an alphanumeric character. X12 delimiters must be non-alphanumeric, so the ISA segment cannot be split into elements. | — |

**One search, three rules (2, 3, 4).** The linter calls `find(b"ISA")` exactly
once; that call's result offset feeds rules 2–4. No rule runs its own search.

- offset `-1` (no match) → **rule 2** fires (fatal, stop).
- offset `> 0` → **rule 3** fires (error, continue from that offset).
- offset `0` → rules 2 and 3 pass.
- position 4 (offset `+ 3`) is past the end of the file → **rule 4** fires (fatal, stop).

In rule 3, _\<identification\>_ describes the leading bytes: a recognized
byte-order mark, printable text (quoted and truncated), whitespace, or a hex
preview otherwise. The X12 standard has no BOM, so a BOM is just one possible
value of the leading bytes, not a rule of its own.

#### ☐ Not yet approved

| # | Group | Sub-category | Check | Severity | Message intent | Cleaning action |
|---|-------|--------------|-------|----------|----------------|-----------------|
| 6 | `?` | `?` | A `GS` + element-separator header follows the ISA envelope | fatal | No `GS` functional-group header follows the `ISA` segment. Either the interchange contains no functional groups, or the ISA segment terminator could not be located. Parsing cannot continue. | — |
| 7 | `?` | `?` | The `GS` header is not implausibly close to the `ISA` tag | fatal | A `GS` + separator sequence appears at byte N. That is too early for a complete 16-element ISA to have ended, so the ISA header is malformed or truncated. | — |
| 8 | `?` | `?` | No stray CR/LF bytes sit between the segment terminator and `GS` | warning | N line-break byte(s) appear between the ISA segment terminator and the `GS` header. X12 joins segments with the terminator alone, so the sender has appended extra newline(s). The linter tolerates this but reports it as non-conformant. | — |
| 9 | `isa_line` | `number of elements` | The ISA segment splits into exactly 16 data elements (ISA01–ISA16) | error | The ISA segment split into N data elements. X12 requires exactly 16, ISA01 through ISA16, so element(s) have been added or lost. | — |
| 10 | `?` | `?` | The ISA segment is exactly 105 bytes, segment terminator excluded | error | The ISA segment is N bytes long. X12 fixes it at 105 bytes, excluding the segment terminator, so the sender has stripped element(s) or padded them to a non-standard width. | — |

### Result fields (`IsaResult`)

| Field | Set when |
|-------|----------|
| `ok` | Always. `True` only if no `error`-severity diagnostics were produced. |
| `diagnostics` | Always. |
| `isa_offset` | The `ISA` tag was located (rules 2–3). |
| `element_separator` | The byte after the `ISA` tag was readable (rule 4). |
| `segment_terminator` | The segment terminator was resolved (rules 6, 8). |
| `isa_segment` | Same as above — the raw ISA segment bytes, terminator excluded. |
| `elements` | The ISA segment was split (rule 9); the list even when the count is wrong. |

---

## Piece 2 — (not yet scoped)

To be defined with the user before any code is written.
