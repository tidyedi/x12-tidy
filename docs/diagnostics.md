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
| `isa.identifier-lowercase` | error | ISA segment identifier is not uppercase |
| `isa.identifier-utf16` | fatal | File appears to be UTF-16 encoded |
| `isa.interchange-too-short` | fatal | Too short to be an X12 interchange |
| `isa.isa11-not-standards-id` | error | ISA11 is not the standards identifier on an older version |
| `isa.isa16-missing` | fatal | Nothing follows ISA15 in the ISA line |
| `isa.leading-bytes` | warning | Bytes precede the ISA segment |
| `isa.no-functional-group` | fatal | ISA segment is not bounded by a GS functional-group header |
| `isa.no-identifier` | fatal | No ISA segment identifier in the file |
| `isa.repetition-separator-invalid` | error | The repetition separator is not a usable delimiter |
| `isa.repetition-separator-missing` | error | No repetition separator for a version that has one |
| `isa.segment-terminator-invalid` | fatal | The segment terminator is an alphanumeric byte |
| `isa.segment-terminator-noncanonical` | warning | The segment terminator is not the tilde |
| `isa.segment-terminator-stripped` | error | No segment terminator after ISA16 |
| `isa.separator-count-low` | fatal | Fewer than 16 element separators before GS |
| `isa.trailing-junk` | warning | Unexpected bytes between the segment terminator and GS |
| `isa.trailing-newline` | warning | Line breaks between the segment terminator and GS |
| `isa.usage-indicator-invalid` | error | ISA15 is not a recognized usage indicator |
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

### `isa.identifier-lowercase`

*error* — ISA segment identifier is not uppercase

The segment identifier was found as 'isa' or mixed case (e.g. 'Isa'). X12 segment identifiers are uppercase. x12-tidy matched it case-insensitively and continued -- a file with a non-uppercase ISA identifier almost certainly has every other segment identifier the same way, which downstream steps must also tolerate.

### `isa.identifier-utf16`

*fatal* — File appears to be UTF-16 encoded

The bytes 'I', 'S', 'A' appear separated by NUL bytes near the start of the file, which is what a UTF-16-encoded 'ISA' looks like. X12 interchanges must use a single-byte encoding (ASCII, Latin-1, or UTF-8 without a wide encoding). This is fatal rather than transcoded: guessing the byte order and trusting or inferring a BOM before parsing has even started is exactly the kind of guess x12-tidy refuses to make elsewhere. Re-export the file in a single-byte encoding and try again.

### `isa.interchange-too-short`

*fatal* — Too short to be an X12 interchange

Fewer than 109 bytes follow the 'ISA' identifier -- not enough room for a 105-byte ISA line, its segment terminator, and a 'GS' header. A real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far longer, so there is nothing to recover.

### `isa.isa11-not-standards-id`

*error* — ISA11 is not the standards identifier on an older version

ISA12 is a version before 00403, where ISA11 is the Interchange Control Standards Identifier and must be 'U'. It holds something else. ISA11 is informational on these versions -- it is not used to parse anything -- so this does not block the interchange, but the value is wrong.

### `isa.isa16-missing`

*fatal* — Nothing follows ISA15 in the ISA line

After the 16th element separator there are no bytes at all -- no ISA16 (which carries the component separator), no segment terminator. The ISA line ends where ISA16 should begin, so none of the trailing delimiters can be recovered.

### `isa.leading-bytes`

*warning* — Bytes precede the ISA segment

One or more bytes appear before the ISA segment. A conformant X12 file begins with 'ISA' as its very first byte. Common causes are a UTF-8 byte-order mark, whitespace, or transport headers left in by the sender. x12-tidy strips them and continues; the reported bytes are what was removed.

### `isa.no-functional-group`

*fatal* — ISA segment is not bounded by a GS functional-group header

Every ISA interchange opens a GS functional group, and x12-tidy ends the ISA line at that GS header. A 'GS' + element separator was found, but the run of bytes to it holds more than the 16 element separators an ISA header has -- so it is not the header. Either there is no GS envelope and the match lies inside a later segment's data, or the element separator occurs inside ISA06 / ISA08 data (an unparseable segment). The ISA line cannot be bounded; not recoverable.

### `isa.no-identifier`

*fatal* — No ISA segment identifier in the file

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

The segment terminator is a non-alphanumeric byte -- often a carriage return or line feed -- but not '~'. Which byte serves as a delimiter is the sender's choice; X12 does not dictate it, so this is a legal interchange and reconstruction preserves the terminator as-is. Noted because '~' is the near-universal convention and downstream tools may assume it.

### `isa.segment-terminator-stripped`

*error* — No segment terminator after ISA16

The GS functional-group header follows ISA16 with no segment terminator between them. The position is structurally known, so the terminator is reconstructed as '~', but the sender's file does not conform.

### `isa.separator-count-low`

*fatal* — Fewer than 16 element separators before GS

An ISA header carries exactly 16 element separators (ISA*ISA01*..*ISA16); that count is part of the minimum bar for calling a run an ISA line at all. The run before the 'GS' header holds fewer -- element separators were removed, or the 'GS' anchored on is a false match inside earlier data. Every candidate ISA identifier was tried; none produced a 16-separator run. This is not an ISA line and is not recoverable.

### `isa.trailing-junk`

*warning* — Unexpected bytes between the segment terminator and GS

Bytes that are not line breaks sit between the ISA segment terminator and the GS header -- stray spaces, a comment, or transport framing. Not part of the interchange under any legal delimiter choice -- non-conformant, like isa.trailing-newline -- and stripped on reconstruction.

### `isa.trailing-newline`

*warning* — Line breaks between the segment terminator and GS

One or more carriage-return or line-feed bytes sit between the ISA segment terminator and the GS header. X12 joins segments with the terminator alone; the sender has appended a newline. Common and harmless, but non-conformant -- stripped on reconstruction.

### `isa.usage-indicator-invalid`

*error* — ISA15 is not a recognized usage indicator

ISA15 (Usage Indicator) must be 'T' (Test), 'P' (Production), or 'I' (Information) -- all three are legitimate values, so this only fires when it is none of them. Which of the three is present is not itself a defect and is reported separately as an informational fact, not a diagnostic.

### `isa.version-unrecognized`

*warning* — ISA12 is not a recognised version code

ISA12 -- the Interchange Control Version Number -- is not a 5-digit code. Whether ISA11 is a repetition separator depends on this value, so ISA11 is left opaque and not treated as a delimiter.

## `gs`

| code | severity | title |
| --- | --- | --- |
| `gs.control-number-duplicate` | fatal | GS06 is reused by another functional group in this interchange |
| `gs.control-number-mismatch` | fatal | GS06 does not match GE02 |
| `gs.control-number-not-numeric` | fatal | GS06 is not all-numeric |
| `gs.count-not-numeric` | fatal | GE01 is not all-numeric |
| `gs.missing-ge` | fatal | No GE segment closes this functional group |
| `gs.responsible-agency-invalid` | error | GS07 is not a recognized responsible agency code |
| `gs.transaction-set-count-mismatch` | fatal | GE01 does not match the number of transaction sets found |
| `gs.version-mismatch` | fatal | GS08 does not agree with the interchange's version (ISA12) |

### `gs.control-number-duplicate`

*fatal* — GS06 is reused by another functional group in this interchange

Each functional group's Group Control Number (GS06) must be unique within the interchange, so its GE can be unambiguously matched back to it.

### `gs.control-number-mismatch`

*fatal* — GS06 does not match GE02

The Group Control Number set in the GS segment (GS06) must equal the one echoed back in the GE segment (GE02).

### `gs.control-number-not-numeric`

*fatal* — GS06 is not all-numeric

GS06 (Group Control Number) is defined as numeric (type N0). A non-numeric value cannot be a valid control number, regardless of whether it happens to match GE02.

### `gs.count-not-numeric`

*fatal* — GE01 is not all-numeric

GE01 (Number of Transaction Sets Included) is defined as numeric. A non-numeric value cannot be a valid count.

### `gs.missing-ge`

*fatal* — No GE segment closes this functional group

Every GS functional group must be closed by a matching GE segment before the next GS or the interchange trailer. None was found; the group's boundary was inferred from the next such marker so that everything inside it could still be checked.

### `gs.responsible-agency-invalid`

*error* — GS07 is not a recognized responsible agency code

GS07 (Responsible Agency Code) must be 'X' (Accredited Standards Committee X12) or 'T' (Transportation Data Coordinating Committee) -- the complete code list for this element.

### `gs.transaction-set-count-mismatch`

*fatal* — GE01 does not match the number of transaction sets found

GE01 (Number of Transaction Sets Included) must equal the actual count of ST segments in the functional group.

### `gs.version-mismatch`

*fatal* — GS08 does not agree with the interchange's version (ISA12)

GS08 (Version/Release/Industry Identifier Code) must agree with ISA12 (Interchange Control Version Number) on the version and release. Compared with leading zeros stripped from both sides, since real-world senders commonly send GS08 as '4010' rather than the textbook zero-padded '004010'. Runs regardless of GS07.

## `st`

| code | severity | title |
| --- | --- | --- |
| `st.control-number-duplicate` | fatal | ST02 is reused by another transaction set in this functional group |
| `st.control-number-mismatch` | fatal | ST02 does not match SE02 |
| `st.count-not-numeric` | fatal | SE01 is not all-numeric |
| `st.missing-se` | fatal | No SE segment closes this transaction set |
| `st.segment-count-mismatch` | fatal | SE01 does not match the actual segment count |

### `st.control-number-duplicate`

*fatal* — ST02 is reused by another transaction set in this functional group

Each transaction set's Control Number (ST02) must be unique within its functional group, so its SE can be unambiguously matched back to it. Unlike GS06/control numbers elsewhere, ST02 is alphanumeric (type AN), not numeric -- uniqueness is still required even though numeric format is not.

### `st.control-number-mismatch`

*fatal* — ST02 does not match SE02

The Transaction Set Control Number set in the ST segment (ST02) must equal the one echoed back in the SE segment (SE02).

### `st.count-not-numeric`

*fatal* — SE01 is not all-numeric

SE01 (Number of Included Segments) is defined as numeric. A non-numeric value cannot be a valid count.

### `st.missing-se`

*fatal* — No SE segment closes this transaction set

Every ST transaction set must be closed by a matching SE segment before the next ST, the enclosing GE, or the interchange trailer. None was found; the transaction set's boundary was inferred from the next such marker so that everything inside it could still be checked.

### `st.segment-count-mismatch`

*fatal* — SE01 does not match the actual segment count

SE01 (Number of Included Segments) must equal the actual count of segments in the transaction set, from ST through SE inclusive.

## `structure`

| code | severity | title |
| --- | --- | --- |
| `structure.control-number-mismatch` | fatal | ISA13 does not match IEA02 |
| `structure.control-number-not-numeric` | fatal | ISA13 is not all-numeric |
| `structure.count-not-numeric` | fatal | IEA01 is not all-numeric |
| `structure.foreign-content` | fatal | A segment appears where none is structurally valid |
| `structure.functional-group-count-mismatch` | fatal | IEA01 does not match the number of functional groups found |
| `structure.identifier-invalid` | error | A segment identifier is not uppercase alphabetic |
| `structure.missing-iea` | fatal | No IEA segment closes the interchange |

### `structure.control-number-mismatch`

*fatal* — ISA13 does not match IEA02

The Interchange Control Number set in the ISA segment (ISA13) must equal the one echoed back in the IEA segment (IEA02). A mismatch usually indicates a corrupted or hand-edited file.

### `structure.control-number-not-numeric`

*fatal* — ISA13 is not all-numeric

ISA13 (Interchange Control Number) is defined as numeric (type N0). A non-numeric value cannot be a valid control number, regardless of whether it happens to match IEA02.

### `structure.count-not-numeric`

*fatal* — IEA01 is not all-numeric

IEA01 (Number of Included Functional Groups) is defined as numeric. A non-numeric value cannot be a valid count.

### `structure.foreign-content`

*fatal* — A segment appears where none is structurally valid

A segment sits outside any recognized structural context -- before the first functional group, between a functional group's close and the next one, after the interchange trailer, or a closing segment (SE, GE, IEA) with nothing open to close -- including a second IEA once the interchange is already closed. This covers every shape of 'a segment turned up in a place the envelope structure does not allow', including a body segment with no open transaction set to belong to.

### `structure.functional-group-count-mismatch`

*fatal* — IEA01 does not match the number of functional groups found

IEA01 (Number of Included Functional Groups) must equal the actual count of GS segments in the interchange.

### `structure.identifier-invalid`

*error* — A segment identifier is not uppercase alphabetic

Every X12 segment identifier begins with an uppercase letter (X12.6). A segment whose identifier does not -- lowercase, numeric, empty -- cannot be identified as a real segment.

### `structure.missing-iea`

*fatal* — No IEA segment closes the interchange

Every ISA interchange must be closed by a matching IEA segment. None was found before the end of the file. This is QA/QC's 'fatal' -- a display/trust signal, not a stop: the rest of the payload is still scanned and every other finding is still reported.
