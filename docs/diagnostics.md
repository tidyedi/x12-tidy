<!-- GENERATED from src/x12_tidy/diagnostics/codes.py -- do not edit -- run scripts/gen_diagnostics_docs.py -->

# Diagnostic codes

Every finding x12-tidy can emit. Codes are `area.specific`; the `area` is the subject of the finding. `default severity` is a starting point that user config can override per-code (including to `ignore`).

## `isa`

| code | severity | title |
| --- | --- | --- |
| `isa.gs-not-found` | fatal | No GS header found after the ISA segment |
| `isa.interchange-too-short` | fatal | Too short to be an X12 interchange |
| `isa.leading-bytes` | warning | Bytes precede the ISA segment |
| `isa.no-functional-group` | fatal | ISA segment is not bounded by a GS functional-group header |
| `isa.no-tag` | fatal | No ISA segment tag in the file |
| `isa.separator-count-low` | fatal | Fewer than 16 element separators before GS |
| `isa.tag-lowercase` | error | ISA segment tag is not uppercase |
| `isa.tag-utf16` | fatal | File appears to be UTF-16 encoded |

### `isa.gs-not-found`

*fatal* — No GS header found after the ISA segment

x12-tidy locates the end of the ISA line by finding the 'GS' functional-group header that follows it (matched as 'GS' plus the element separator). No such header was found, so the ISA line cannot be bounded.

### `isa.interchange-too-short`

*fatal* — Too short to be an X12 interchange

Fewer than 109 bytes follow the 'ISA' tag -- not enough room for a 105-byte ISA line, its segment terminator, and a 'GS' header. A real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far longer, so there is nothing to recover.

### `isa.leading-bytes`

*warning* — Bytes precede the ISA segment

One or more bytes appear before the ISA segment. A conformant X12 file begins with 'ISA' as its very first byte. Common causes are a UTF-8 byte-order mark, whitespace, or transport headers left in by the sender. x12-tidy strips them and continues; the reported bytes are what was removed.

### `isa.no-functional-group`

*fatal* — ISA segment is not bounded by a GS functional-group header

Every ISA interchange opens a GS functional group, and x12-tidy ends the ISA line at that GS header. A 'GS' + element separator was found, but the run of bytes to it holds more than the 16 element separators an ISA header has -- so it is not the header. Either there is no GS envelope and the match lies inside a later segment's data, or the element separator occurs inside ISA06 / ISA08 data (an unparseable segment). The ISA line cannot be bounded; not recoverable.

### `isa.no-tag`

*fatal* — No ISA segment tag in the file

The byte sequence 'ISA' does not appear anywhere in the file, so there is no X12 interchange to inspect. Nothing downstream can run.

### `isa.separator-count-low`

*fatal* — Fewer than 16 element separators before GS

An ISA header carries exactly 16 element separators (ISA*ISA01*..*ISA16); that count is part of the minimum bar for calling a run an ISA line at all. The run before the 'GS' header holds fewer -- element separators were removed, or the 'GS' anchored on is a false match inside earlier data. Every candidate ISA tag was tried; none produced a 16-separator run. This is not an ISA line and is not recoverable.

### `isa.tag-lowercase`

*error* — ISA segment tag is not uppercase

The segment tag was found as 'isa' or mixed case (e.g. 'Isa'). X12 segment tags are uppercase. x12-tidy matched it case-insensitively and continued -- a file with a non-uppercase ISA tag almost certainly has every other segment tag the same way, which downstream steps must also tolerate.

### `isa.tag-utf16`

*fatal* — File appears to be UTF-16 encoded

The bytes 'I', 'S', 'A' appear separated by NUL bytes near the start of the file, which is what a UTF-16-encoded 'ISA' looks like. X12 interchanges must use a single-byte encoding (ASCII, Latin-1, or UTF-8 without a wide encoding). Re-export the file and try again.
