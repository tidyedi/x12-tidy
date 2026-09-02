<!-- GENERATED from src/x12_tidy/diagnostics/codes.py -- do not edit -- run scripts/gen_diagnostics_docs.py -->

# Diagnostic codes

Every finding x12-tidy can emit. Codes are `area.specific`; the `area` is the subject of the finding. `default severity` is a starting point that user config can override per-code (including to `ignore`).

## `isa`

| code | severity | title |
| --- | --- | --- |
| `isa.component-separator-invalid` | error | The component separator is not a usable delimiter |
| `isa.delimiter-collision` | fatal | Two delimiters are the same byte |
| `isa.delimiter-misaligned` | fatal | The ISA line cannot be decomposed at the element separator |
| `isa.element-embedded-newline` | warning | A carriage return or line feed sits inside an ISA element |
| `isa.element-overflow` | fatal | An ISA element holds non-space data past its fixed width |
| `isa.element-separator-invalid` | fatal | The element separator is an alphanumeric byte |
| `isa.element-width` | error | An ISA element is not its fixed width |
| `isa.gs-not-found` | fatal | No GS header found after the ISA segment |
| `isa.interchange-too-short` | fatal | Too short to be an X12 interchange |
| `isa.isa11-not-standards-id` | error | ISA11 is not the standards identifier on an older version |
| `isa.isa16-missing` | fatal | Nothing follows ISA15 in the ISA line |
| `isa.leading-bytes` | warning | Bytes precede the ISA segment |
| `isa.line-length` | fatal | The reconstructed ISA line is not 105 bytes |
| `isa.no-functional-group` | fatal | ISA segment is not bounded by a GS functional-group header |
| `isa.no-tag` | fatal | No ISA segment tag in the file |
| `isa.repetition-separator-invalid` | error | The repetition separator is not a usable delimiter |
| `isa.repetition-separator-missing` | error | No repetition separator for a version that has one |
| `isa.segment-terminator-invalid` | fatal | The segment terminator is an alphanumeric byte |
| `isa.segment-terminator-noncanonical` | warning | The segment terminator is not the tilde |
| `isa.segment-terminator-stripped` | error | No segment terminator after ISA16 |
| `isa.separator-count-low` | fatal | Fewer than 16 element separators before GS |
| `isa.tag-lowercase` | error | ISA segment tag is not uppercase |
| `isa.tag-utf16` | fatal | File appears to be UTF-16 encoded |
| `isa.trailing-junk` | error | Unexpected bytes between the segment terminator and GS |
| `isa.trailing-newline` | warning | Line breaks between the segment terminator and GS |
| `isa.version-unrecognized` | warning | ISA12 is not a recognised version code |

### `isa.component-separator-invalid`

*error* — The component separator is not a usable delimiter

ISA16 -- the component (sub-element) separator -- is an alphanumeric byte or a space, so it collides with element data or padding. This is reported as an error here because many interchanges carry no composite elements; the body parser escalates it to fatal at the first segment that does.

### `isa.delimiter-collision`

*fatal* — Two delimiters are the same byte

The segment terminator is the same byte as the element separator or the component separator. Segment boundaries then cannot be told apart from element or composite boundaries anywhere in the interchange, so it cannot be parsed.

### `isa.delimiter-misaligned`

*fatal* — The ISA line cannot be decomposed at the element separator

Splitting the ISA line on the element separator did not land the component separator and segment terminator on delimiter-shaped bytes. The usual cause is an element separator byte occurring inside ISA06 or ISA08 data, which shifts every field after it. The line holds the right number of separators but the wrong boundaries, so it cannot be trusted.

### `isa.element-embedded-newline`

*warning* — A carriage return or line feed sits inside an ISA element

An ISA element value contains a CR or LF byte -- almost always a sender that hard-wrapped the ISA segment across lines. The delimiters are already known at this point, so the byte cannot be a delimiter (ISA11 when it carries the repetition separator, and ISA16, are left untouched); it is replaced with a space and the element is then measured against its fixed width.

### `isa.element-overflow`

*fatal* — An ISA element holds non-space data past its fixed width

This element is longer than its fixed width and the overflow is real data, not padding. There is no way to know the sender's intent -- an element separator may have been dropped, merging two fields, or the sender may have overrun the field. Guessing either way risks corrupting an identifier, so the ISA line is not reconstructed.

### `isa.element-separator-invalid`

*fatal* — The element separator is an alphanumeric byte

The 4th byte of the ISA segment -- the element separator -- is a letter or digit. It cannot be distinguished from the data inside elements, so no segment in the interchange can be split reliably. X12 element separators are non-alphanumeric (commonly '*').

### `isa.element-width`

*error* — An ISA element is not its fixed width

Every ISA element has a fixed width -- ISA06 is 15 bytes, ISA13 is 9, and so on. This element was shorter (space-padded on the right to fit) or longer only by trailing spaces (trimmed). The value itself is unchanged. A sender that right-trims blank fixed-width fields is the usual cause. This is an error, not a warning: the ISA line is no longer 105 bytes, and conventional VAN services and fixed-offset parsers cannot read the interchange at all until it is repaired.

### `isa.gs-not-found`

*fatal* — No GS header found after the ISA segment

x12-tidy locates the end of the ISA line by finding the 'GS' functional-group header that follows it (matched as 'GS' plus the element separator). No such header was found, so the ISA line cannot be bounded.

### `isa.interchange-too-short`

*fatal* — Too short to be an X12 interchange

Fewer than 109 bytes follow the 'ISA' tag -- not enough room for a 105-byte ISA line, its segment terminator, and a 'GS' header. A real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far longer, so there is nothing to recover.

### `isa.isa11-not-standards-id`

*error* — ISA11 is not the standards identifier on an older version

ISA12 is a version before 00403, where ISA11 is the Interchange Control Standards Identifier and must be 'U'. It holds something else. ISA11 is informational on these versions -- it is not used to parse anything -- so this does not block the interchange, but the value is wrong.

### `isa.isa16-missing`

*fatal* — Nothing follows ISA15 in the ISA line

After the 16th element separator there are no bytes at all -- no ISA16 (which carries the component separator), no segment terminator. The ISA line ends where ISA16 should begin, so none of the trailing delimiters can be recovered.

### `isa.leading-bytes`

*warning* — Bytes precede the ISA segment

One or more bytes appear before the ISA segment. A conformant X12 file begins with 'ISA' as its very first byte. Common causes are a UTF-8 byte-order mark, whitespace, or transport headers left in by the sender. x12-tidy strips them and continues; the reported bytes are what was removed.

### `isa.line-length`

*fatal* — The reconstructed ISA line is not 105 bytes

After padding every element to its fixed width and rejoining on the element separator, the ISA line is not the required 105 bytes. This should not happen once the per-element widths hold; it is a guard that refuses to emit a non-conformant line.

### `isa.no-functional-group`

*fatal* — ISA segment is not bounded by a GS functional-group header

Every ISA interchange opens a GS functional group, and x12-tidy ends the ISA line at that GS header. A 'GS' + element separator was found, but the run of bytes to it holds more than the 16 element separators an ISA header has -- so it is not the header. Either there is no GS envelope and the match lies inside a later segment's data, or the element separator occurs inside ISA06 / ISA08 data (an unparseable segment). The ISA line cannot be bounded; not recoverable.

### `isa.no-tag`

*fatal* — No ISA segment tag in the file

The byte sequence 'ISA' does not appear anywhere in the file, so there is no X12 interchange to inspect. Nothing downstream can run.

### `isa.repetition-separator-invalid`

*error* — The repetition separator is not a usable delimiter

ISA11 -- the repetition separator, for ISA12 version 00403 and later -- is an alphanumeric byte or is the same byte as another delimiter. It is reported as an error here because repetition is optional; the body parser escalates it to fatal at the first segment that repeats a data element.

### `isa.repetition-separator-missing`

*error* — No repetition separator for a version that has one

ISA12 is version 00403 or later, where ISA11 is the repetition separator, but ISA11 is blank or still holds the old standards identifier 'U'. Repeated data elements cannot be parsed; downstream must treat repetition as unsupported.

### `isa.segment-terminator-invalid`

*fatal* — The segment terminator is an alphanumeric byte

The byte after ISA16 -- the segment terminator -- is a letter or digit, so it is data, not a delimiter. Every segment in the interchange ends with this byte, so none of them can be split. The terminator was probably stripped by the sender.

### `isa.segment-terminator-noncanonical`

*warning* — The segment terminator is not the tilde

The segment terminator is a usable non-alphanumeric byte -- often a carriage return or line feed -- but not '~'. The interchange parses; the reconstructed ISA line normalises the terminator to '~'.

### `isa.segment-terminator-stripped`

*error* — No segment terminator after ISA16

The GS functional-group header follows ISA16 with no segment terminator between them. The position is structurally known, so the terminator is reconstructed as '~', but the sender's file does not conform.

### `isa.separator-count-low`

*fatal* — Fewer than 16 element separators before GS

An ISA header carries exactly 16 element separators (ISA*ISA01*..*ISA16); that count is part of the minimum bar for calling a run an ISA line at all. The run before the 'GS' header holds fewer -- element separators were removed, or the 'GS' anchored on is a false match inside earlier data. Every candidate ISA tag was tried; none produced a 16-separator run. This is not an ISA line and is not recoverable.

### `isa.tag-lowercase`

*error* — ISA segment tag is not uppercase

The segment tag was found as 'isa' or mixed case (e.g. 'Isa'). X12 segment tags are uppercase. x12-tidy matched it case-insensitively and continued -- a file with a non-uppercase ISA tag almost certainly has every other segment tag the same way, which downstream steps must also tolerate.

### `isa.tag-utf16`

*fatal* — File appears to be UTF-16 encoded

The bytes 'I', 'S', 'A' appear separated by NUL bytes near the start of the file, which is what a UTF-16-encoded 'ISA' looks like. X12 interchanges must use a single-byte encoding (ASCII, Latin-1, or UTF-8 without a wide encoding). Re-export the file and try again.

### `isa.trailing-junk`

*error* — Unexpected bytes between the segment terminator and GS

Bytes that are not line breaks sit between the ISA segment terminator and the GS header -- stray spaces, a comment, or transport framing. They are not part of the interchange and are stripped on reconstruction.

### `isa.trailing-newline`

*warning* — Line breaks between the segment terminator and GS

One or more carriage-return or line-feed bytes sit between the ISA segment terminator and the GS header. X12 joins segments with the terminator alone; the sender has appended a newline. Common and harmless, but non-conformant -- stripped on reconstruction.

### `isa.version-unrecognized`

*warning* — ISA12 is not a recognised version code

ISA12 -- the Interchange Control Version Number -- is not a 5-digit code. Whether ISA11 is a repetition separator depends on this value, so ISA11 is left opaque and not treated as a delimiter.
