<!-- GENERATED from src/edi_linter/diagnostics/codes.py -- do not edit -- run scripts/gen_diagnostics_docs.py -->

# Diagnostic codes

Every finding the linter can emit. Codes are `area.specific`; the `area` is the subject of the finding. `default severity` is a starting point that user config can override per-code (including to `ignore`).

## `isa`

| code | severity | title |
| --- | --- | --- |
| `isa.gs-not-found` | fatal | No GS header found after the ISA segment |
| `isa.interchange-too-short` | fatal | Too short to be an X12 interchange |
| `isa.leading-bytes` | warning | Bytes precede the ISA segment |
| `isa.no-tag` | fatal | No ISA segment tag in the file |
| `isa.separator-count-low` | fatal | Fewer than 16 element separators before GS |

### `isa.gs-not-found`

*fatal* — No GS header found after the ISA segment

The linter locates the end of the ISA line by finding the 'GS' functional-group header that follows it (matched as 'GS' plus the element separator). No such header was found, so the ISA line cannot be bounded.

### `isa.interchange-too-short`

*fatal* — Too short to be an X12 interchange

Fewer than 109 bytes follow the 'ISA' tag -- not enough room for a 105-byte ISA line, its segment terminator, and a 'GS' header. A real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far longer, so there is nothing to recover.

### `isa.leading-bytes`

*warning* — Bytes precede the ISA segment

One or more bytes appear before the ISA segment. A conformant X12 file begins with 'ISA' as its very first byte. Common causes are a UTF-8 byte-order mark, whitespace, or transport headers left in by the sender. The linter strips them and continues; the reported bytes are what was removed.

### `isa.no-tag`

*fatal* — No ISA segment tag in the file

The byte sequence 'ISA' does not appear anywhere in the file, so there is no X12 interchange to inspect. Nothing downstream can run.

### `isa.separator-count-low`

*fatal* — Fewer than 16 element separators before GS

An ISA header carries exactly 16 element separators (ISA*ISA01*..*ISA16). The run of bytes before the 'GS' header holds fewer than that, so it is not a valid ISA line -- either elements were dropped, or the 'GS' the linter anchored on is a false match inside earlier data.
