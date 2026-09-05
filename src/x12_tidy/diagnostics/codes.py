# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""The diagnostic code registry -- the single source of truth.

Every finding x12-tidy can emit has an entry here.  Nothing else defines a
code: modules reference the :class:`Code` members, tests assert on them, and the
human-readable views (``docs/diagnostics.md``, ``x12-tidy codes``) are
*generated* from this file.  See ``docs/design.md`` for the full scheme.

Rules
-----
* Code strings are ``area.specific`` -- a closed ``area`` vocabulary
  (:data:`AREAS`), kebab-case within each part, a dot between.  No numbers.
* The ``area`` is the *subject* of the finding, never the code path that
  raised it (a short-ISA-line problem found while recovering is still
  ``isa.*``).
* ``default_severity`` is a starting point; user config may override it
  per-code later (including to ``"ignore"``).  Severity is resolved at
  *report* time, never stored on a :class:`~x12_tidy.diagnostics.Diagnostic`.
* A retired code is never reused.  A material change in meaning is a new code;
  the old one stays here marked ``deprecated=True``.

Adding a code
-------------
1. ``x12-tidy codes --area <area>`` -- check nothing already covers it.
2. Add a :class:`Code` member and a :class:`CodeMeta` row to :data:`META`.
3. Build: the generated docs update, CI checks the registry stays consistent
   with what the modules actually emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Severity = Literal["fatal", "error", "warning"]
#: ``fatal`` also stops parsing; ``error`` and ``warning`` are advisory.

#: The closed set of code areas -- the subject each finding is *about*.
#: Grows roughly once a year; keep it to X12 envelope structure.
AREAS: tuple[str, ...] = ("isa", "gs", "st", "delimiter", "structure")


class Code(Enum):
    """Stable identity for every kind of finding.

    The *value* is the ``area.specific`` string that appears in output and in
    tests.  The *member name* is that string upper-cased with ``.``/``-`` ->
    ``_`` (so ``isa.leading-bytes`` <-> ``Code.ISA_LEADING_BYTES``).
    """

    # -- isa: locating and bounding the ISA line (Step 1) --
    ISA_NO_TAG = "isa.no-tag"
    ISA_TAG_LOWERCASE = "isa.tag-lowercase"
    ISA_TAG_UTF16 = "isa.tag-utf16"
    ISA_LEADING_BYTES = "isa.leading-bytes"
    ISA_INTERCHANGE_TOO_SHORT = "isa.interchange-too-short"
    ISA_GS_NOT_FOUND = "isa.gs-not-found"
    ISA_SEPARATOR_COUNT_LOW = "isa.separator-count-low"
    ISA_NO_FUNCTIONAL_GROUP = "isa.no-functional-group"

    # -- isa: parsing the delimiters out of the ISA line (Step 2, slice 1) --
    ISA_ISA16_MISSING = "isa.isa16-missing"
    ISA_DELIMITER_MISALIGNED = "isa.delimiter-misaligned"
    ISA_DELIMITER_COLLISION = "isa.delimiter-collision"
    ISA_ELEMENT_SEPARATOR_INVALID = "isa.element-separator-invalid"
    ISA_COMPONENT_SEPARATOR_INVALID = "isa.component-separator-invalid"
    ISA_REPETITION_SEPARATOR_INVALID = "isa.repetition-separator-invalid"
    ISA_REPETITION_SEPARATOR_MISSING = "isa.repetition-separator-missing"
    ISA_ISA11_NOT_STANDARDS_ID = "isa.isa11-not-standards-id"
    ISA_SEGMENT_TERMINATOR_INVALID = "isa.segment-terminator-invalid"
    ISA_SEGMENT_TERMINATOR_STRIPPED = "isa.segment-terminator-stripped"
    ISA_SEGMENT_TERMINATOR_NONCANONICAL = "isa.segment-terminator-noncanonical"
    ISA_VERSION_UNRECOGNIZED = "isa.version-unrecognized"
    ISA_TRAILING_NEWLINE = "isa.trailing-newline"
    ISA_TRAILING_JUNK = "isa.trailing-junk"

    # -- isa: reconstructing the canonical ISA line (Step 2, slice 2) --
    ISA_ELEMENT_EMBEDDED_NEWLINE = "isa.element-embedded-newline"
    ISA_ELEMENT_WIDTH = "isa.element-width"
    ISA_ELEMENT_OVERFLOW = "isa.element-overflow"
    ISA_LINE_LENGTH = "isa.line-length"

    # -- isa: QA/QC on a standalone ISA element value (post-reconstruction) --
    ISA_USAGE_INDICATOR_INVALID = "isa.usage-indicator-invalid"

    # -- structure: interchange-level envelope QA/QC (ISA/IEA) --
    STRUCTURE_MISSING_IEA = "structure.missing-iea"
    STRUCTURE_CONTROL_NUMBER_MISMATCH = "structure.control-number-mismatch"
    STRUCTURE_FUNCTIONAL_GROUP_COUNT_MISMATCH = (
        "structure.functional-group-count-mismatch"
    )
    STRUCTURE_CONTROL_NUMBER_NOT_NUMERIC = "structure.control-number-not-numeric"
    STRUCTURE_COUNT_NOT_NUMERIC = "structure.count-not-numeric"
    STRUCTURE_TAG_SHAPE_INVALID = "structure.tag-shape-invalid"
    STRUCTURE_FOREIGN_CONTENT = "structure.foreign-content"

    # -- gs: functional-group-level envelope QA/QC (GS/GE) --
    GS_MISSING_GE = "gs.missing-ge"
    GS_CONTROL_NUMBER_MISMATCH = "gs.control-number-mismatch"
    GS_TRANSACTION_SET_COUNT_MISMATCH = "gs.transaction-set-count-mismatch"
    GS_CONTROL_NUMBER_NOT_NUMERIC = "gs.control-number-not-numeric"
    GS_COUNT_NOT_NUMERIC = "gs.count-not-numeric"
    GS_CONTROL_NUMBER_DUPLICATE = "gs.control-number-duplicate"
    GS_VERSION_MISMATCH = "gs.version-mismatch"
    GS_RESPONSIBLE_AGENCY_INVALID = "gs.responsible-agency-invalid"

    # -- st: transaction-set-level envelope QA/QC (ST/SE) --
    ST_MISSING_SE = "st.missing-se"
    ST_CONTROL_NUMBER_MISMATCH = "st.control-number-mismatch"
    ST_SEGMENT_COUNT_MISMATCH = "st.segment-count-mismatch"
    ST_COUNT_NOT_NUMERIC = "st.count-not-numeric"
    ST_CONTROL_NUMBER_DUPLICATE = "st.control-number-duplicate"

    @property
    def area(self) -> str:
        return self.value.split(".", 1)[0]


@dataclass(frozen=True)
class CodeMeta:
    """Everything about a code except its identity.

    ``title`` is a short, static, generic line (no per-occurrence detail --
    that goes in the :class:`~x12_tidy.diagnostics.Diagnostic` message).
    ``explanation`` is the paragraph shown by ``x12-tidy explain``.
    """

    default_severity: Severity
    title: str
    explanation: str
    deprecated: bool = False


META: dict[Code, CodeMeta] = {
    Code.ISA_NO_TAG: CodeMeta(
        default_severity="fatal",
        title="No ISA segment tag in the file",
        explanation=(
            "The byte sequence 'ISA' does not appear anywhere in the file, so "
            "there is no X12 interchange to inspect. Nothing downstream can run."
        ),
    ),
    Code.ISA_TAG_LOWERCASE: CodeMeta(
        default_severity="error",
        title="ISA segment tag is not uppercase",
        explanation=(
            "The segment tag was found as 'isa' or mixed case (e.g. 'Isa'). "
            "X12 segment tags are uppercase. x12-tidy matched it "
            "case-insensitively and continued -- a file with a non-uppercase "
            "ISA tag almost certainly has every other segment tag the same way, "
            "which downstream steps must also tolerate."
        ),
    ),
    Code.ISA_TAG_UTF16: CodeMeta(
        default_severity="fatal",
        title="File appears to be UTF-16 encoded",
        explanation=(
            "The bytes 'I', 'S', 'A' appear separated by NUL bytes near the "
            "start of the file, which is what a UTF-16-encoded 'ISA' looks "
            "like. X12 interchanges must use a single-byte encoding (ASCII, "
            "Latin-1, or UTF-8 without a wide encoding). Re-export the file and "
            "try again."
        ),
    ),
    Code.ISA_LEADING_BYTES: CodeMeta(
        default_severity="warning",
        title="Bytes precede the ISA segment",
        explanation=(
            "One or more bytes appear before the ISA segment. A conformant X12 "
            "file begins with 'ISA' as its very first byte. Common causes are a "
            "UTF-8 byte-order mark, whitespace, or transport headers left in by "
            "the sender. x12-tidy strips them and continues; the reported "
            "bytes are what was removed."
        ),
    ),
    Code.ISA_INTERCHANGE_TOO_SHORT: CodeMeta(
        default_severity="fatal",
        title="Too short to be an X12 interchange",
        explanation=(
            "Fewer than 109 bytes follow the 'ISA' tag -- not enough room for a "
            "105-byte ISA line, its segment terminator, and a 'GS' header. A "
            "real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far "
            "longer, so there is nothing to recover."
        ),
    ),
    Code.ISA_GS_NOT_FOUND: CodeMeta(
        default_severity="fatal",
        title="No GS header found after the ISA segment",
        explanation=(
            "x12-tidy locates the end of the ISA line by finding the 'GS' "
            "functional-group header that follows it (matched as 'GS' plus the "
            "element separator). No such header was found, so the ISA line "
            "cannot be bounded."
        ),
    ),
    Code.ISA_SEPARATOR_COUNT_LOW: CodeMeta(
        default_severity="fatal",
        title="Fewer than 16 element separators before GS",
        explanation=(
            "An ISA header carries exactly 16 element separators (ISA*ISA01*.."
            "*ISA16); that count is part of the minimum bar for calling a run "
            "an ISA line at all. The run before the 'GS' header holds fewer -- "
            "element separators were removed, or the 'GS' anchored on is a "
            "false match inside earlier data. Every candidate ISA tag was "
            "tried; none produced a 16-separator run. This is not an ISA line "
            "and is not recoverable."
        ),
    ),
    Code.ISA_NO_FUNCTIONAL_GROUP: CodeMeta(
        default_severity="fatal",
        title="ISA segment is not bounded by a GS functional-group header",
        explanation=(
            "Every ISA interchange opens a GS functional group, and x12-tidy "
            "ends the ISA line at that GS header. A 'GS' + element separator "
            "was found, but the run of bytes to it holds more than the 16 "
            "element separators an ISA header has -- so it is not the header. "
            "Either there is no GS envelope and the match lies inside a later "
            "segment's data, or the element separator occurs inside ISA06 / "
            "ISA08 data (an unparseable segment). The ISA line cannot be "
            "bounded; not recoverable."
        ),
    ),

    # -- isa: parsing the delimiters (Step 2, slice 1) --
    Code.ISA_ISA16_MISSING: CodeMeta(
        default_severity="fatal",
        title="Nothing follows ISA15 in the ISA line",
        explanation=(
            "After the 16th element separator there are no bytes at all -- no "
            "ISA16 (which carries the component separator), no segment "
            "terminator. The ISA line ends where ISA16 should begin, so none "
            "of the trailing delimiters can be recovered."
        ),
    ),
    Code.ISA_DELIMITER_MISALIGNED: CodeMeta(
        default_severity="fatal",
        title="The ISA line cannot be decomposed at the element separator",
        explanation=(
            "Splitting the ISA line on the element separator did not land the "
            "component separator and segment terminator on delimiter-shaped "
            "bytes. The usual cause is an element separator byte occurring "
            "inside ISA06 or ISA08 data, which shifts every field after it. "
            "The line holds the right number of separators but the wrong "
            "boundaries, so it cannot be trusted."
        ),
    ),
    Code.ISA_DELIMITER_COLLISION: CodeMeta(
        default_severity="fatal",
        title="Two delimiters are the same byte",
        explanation=(
            "The segment terminator is the same byte as the element separator "
            "or the component separator. Segment boundaries then cannot be "
            "told apart from element or composite boundaries anywhere in the "
            "interchange, so it cannot be parsed."
        ),
    ),
    Code.ISA_ELEMENT_SEPARATOR_INVALID: CodeMeta(
        default_severity="fatal",
        title="The element separator is an alphanumeric byte",
        explanation=(
            "The 4th byte of the ISA segment -- the element separator -- is a "
            "letter or digit. It cannot be distinguished from the data inside "
            "elements, so no segment in the interchange can be split reliably. "
            "X12 element separators are non-alphanumeric (commonly '*')."
        ),
    ),
    Code.ISA_COMPONENT_SEPARATOR_INVALID: CodeMeta(
        default_severity="error",
        title="The component separator is not a usable delimiter",
        explanation=(
            "ISA16 -- the component (sub-element) separator -- is an "
            "alphanumeric byte or a space, so it collides with element data or "
            "padding. This is reported as an error here because many "
            "interchanges carry no composite elements; the body parser "
            "escalates it to fatal at the first segment that does."
        ),
    ),
    Code.ISA_REPETITION_SEPARATOR_INVALID: CodeMeta(
        default_severity="error",
        title="The repetition separator is not a usable delimiter",
        explanation=(
            "ISA11 -- the repetition separator, for ISA12 version 00403 and "
            "later -- is an alphanumeric byte or is the same byte as another "
            "delimiter. It is reported as an error here because repetition is "
            "optional; the body parser escalates it to fatal at the first "
            "segment that repeats a data element."
        ),
    ),
    Code.ISA_REPETITION_SEPARATOR_MISSING: CodeMeta(
        default_severity="error",
        title="No repetition separator for a version that has one",
        explanation=(
            "ISA12 is version 00403 or later, where ISA11 is the repetition "
            "separator, but ISA11 is blank or still holds the old standards "
            "identifier 'U'. Repeated data elements cannot be parsed; "
            "downstream must treat repetition as unsupported."
        ),
    ),
    Code.ISA_ISA11_NOT_STANDARDS_ID: CodeMeta(
        default_severity="error",
        title="ISA11 is not the standards identifier on an older version",
        explanation=(
            "ISA12 is a version before 00403, where ISA11 is the Interchange "
            "Control Standards Identifier and must be 'U'. It holds something "
            "else. ISA11 is informational on these versions -- it is not used "
            "to parse anything -- so this does not block the interchange, but "
            "the value is wrong."
        ),
    ),
    Code.ISA_SEGMENT_TERMINATOR_INVALID: CodeMeta(
        default_severity="fatal",
        title="The segment terminator is an alphanumeric byte",
        explanation=(
            "The byte after ISA16 -- the segment terminator -- is a letter or "
            "digit, so it is data, not a delimiter. Every segment in the "
            "interchange ends with this byte, so none of them can be split. "
            "The terminator was probably stripped by the sender."
        ),
    ),
    Code.ISA_SEGMENT_TERMINATOR_STRIPPED: CodeMeta(
        default_severity="error",
        title="No segment terminator after ISA16",
        explanation=(
            "The GS functional-group header follows ISA16 with no segment "
            "terminator between them. The position is structurally known, so "
            "the terminator is reconstructed as '~', but the sender's file "
            "does not conform."
        ),
    ),
    Code.ISA_SEGMENT_TERMINATOR_NONCANONICAL: CodeMeta(
        default_severity="warning",
        title="The segment terminator is not the tilde",
        explanation=(
            "The segment terminator is a non-alphanumeric byte -- often a "
            "carriage return or line feed -- but not '~'. Which byte serves as "
            "a delimiter is the sender's choice; X12 does not dictate it, so "
            "this is a legal interchange and reconstruction preserves the "
            "terminator as-is. Noted because '~' is the near-universal "
            "convention and downstream tools may assume it."
        ),
    ),
    Code.ISA_VERSION_UNRECOGNIZED: CodeMeta(
        default_severity="warning",
        title="ISA12 is not a recognised version code",
        explanation=(
            "ISA12 -- the Interchange Control Version Number -- is not a "
            "5-digit code. Whether ISA11 is a repetition separator depends on "
            "this value, so ISA11 is left opaque and not treated as a "
            "delimiter."
        ),
    ),
    Code.ISA_TRAILING_NEWLINE: CodeMeta(
        default_severity="warning",
        title="Line breaks between the segment terminator and GS",
        explanation=(
            "One or more carriage-return or line-feed bytes sit between the "
            "ISA segment terminator and the GS header. X12 joins segments with "
            "the terminator alone; the sender has appended a newline. Common "
            "and harmless, but non-conformant -- stripped on reconstruction."
        ),
    ),
    Code.ISA_TRAILING_JUNK: CodeMeta(
        default_severity="warning",
        title="Unexpected bytes between the segment terminator and GS",
        explanation=(
            "Bytes that are not line breaks sit between the ISA segment "
            "terminator and the GS header -- stray spaces, a comment, or "
            "transport framing. Not part of the interchange under any legal "
            "delimiter choice -- non-conformant, like isa.trailing-newline -- "
            "and stripped on reconstruction."
        ),
    ),

    # -- isa: reconstructing the canonical ISA line (Step 2, slice 2) --
    Code.ISA_ELEMENT_EMBEDDED_NEWLINE: CodeMeta(
        default_severity="warning",
        title="A carriage return or line feed sits inside an ISA element",
        explanation=(
            "An ISA element value contains a CR or LF byte -- almost always a "
            "sender that hard-wrapped the ISA segment across lines. The "
            "delimiters are already known at this point, so the byte cannot be "
            "a delimiter (ISA11 when it carries the repetition separator, and "
            "ISA16, are left untouched); it is replaced with a space and the "
            "element is then measured against its fixed width."
        ),
    ),
    Code.ISA_ELEMENT_WIDTH: CodeMeta(
        default_severity="error",
        title="An ISA element is not its fixed width",
        explanation=(
            "Every ISA element has a fixed width -- ISA06 is 15 bytes, ISA13 is "
            "9, and so on. This element was shorter (space-padded on the right "
            "to fit) or longer only by trailing spaces (trimmed). The value "
            "itself is unchanged. A sender that right-trims blank fixed-width "
            "fields is the usual cause. This is an error, not a warning: the "
            "ISA line is no longer 105 bytes, and conventional VAN services and "
            "fixed-offset parsers cannot read the interchange at all until it "
            "is repaired."
        ),
    ),
    Code.ISA_ELEMENT_OVERFLOW: CodeMeta(
        default_severity="fatal",
        title="An ISA element holds non-space data past its fixed width",
        explanation=(
            "This element is longer than its fixed width and the overflow is "
            "real data, not padding. There is no way to know the sender's "
            "intent -- an element separator may have been dropped, merging two "
            "fields, or the sender may have overrun the field. Guessing either "
            "way risks corrupting an identifier, so the ISA line is not "
            "reconstructed."
        ),
    ),
    Code.ISA_LINE_LENGTH: CodeMeta(
        default_severity="fatal",
        title="The reconstructed ISA line is not 105 bytes",
        explanation=(
            "After padding every element to its fixed width and rejoining on "
            "the element separator, the ISA line is not the required 105 bytes. "
            "This should not happen once the per-element widths hold; it is a "
            "guard that refuses to emit a non-conformant line."
        ),
    ),

    # -- isa: QA/QC on a standalone ISA element value --
    Code.ISA_USAGE_INDICATOR_INVALID: CodeMeta(
        default_severity="error",
        title="ISA15 is not a recognized usage indicator",
        explanation=(
            "ISA15 (Usage Indicator) must be 'T' (Test), 'P' (Production), or "
            "'I' (Information) -- all three are legitimate values, so this only "
            "fires when it is none of them. Which of the three is present is not "
            "itself a defect and is reported separately as an informational "
            "fact, not a diagnostic."
        ),
    ),

    # -- structure: interchange-level envelope QA/QC --
    Code.STRUCTURE_MISSING_IEA: CodeMeta(
        default_severity="fatal",
        title="No IEA segment closes the interchange",
        explanation=(
            "Every ISA interchange must be closed by a matching IEA segment. "
            "None was found before the end of the file. This is QA/QC's "
            "'fatal' -- a display/trust signal, not a stop: the rest of the "
            "payload is still scanned and every other finding is still "
            "reported."
        ),
    ),
    Code.STRUCTURE_CONTROL_NUMBER_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="ISA13 does not match IEA02",
        explanation=(
            "The Interchange Control Number set in the ISA segment (ISA13) "
            "must equal the one echoed back in the IEA segment (IEA02). A "
            "mismatch usually indicates a corrupted or hand-edited file."
        ),
    ),
    Code.STRUCTURE_FUNCTIONAL_GROUP_COUNT_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="IEA01 does not match the number of functional groups found",
        explanation=(
            "IEA01 (Number of Included Functional Groups) must equal the "
            "actual count of GS segments in the interchange."
        ),
    ),
    Code.STRUCTURE_CONTROL_NUMBER_NOT_NUMERIC: CodeMeta(
        default_severity="fatal",
        title="ISA13 is not all-numeric",
        explanation=(
            "ISA13 (Interchange Control Number) is defined as numeric (type "
            "N0). A non-numeric value cannot be a valid control number, "
            "regardless of whether it happens to match IEA02."
        ),
    ),
    Code.STRUCTURE_COUNT_NOT_NUMERIC: CodeMeta(
        default_severity="fatal",
        title="IEA01 is not all-numeric",
        explanation=(
            "IEA01 (Number of Included Functional Groups) is defined as "
            "numeric. A non-numeric value cannot be a valid count."
        ),
    ),
    Code.STRUCTURE_TAG_SHAPE_INVALID: CodeMeta(
        default_severity="error",
        title="A segment tag is not uppercase alphabetic",
        explanation=(
            "Every X12 segment tag begins with an uppercase letter (X12.6). A "
            "segment whose tag does not -- lowercase, numeric, empty -- cannot "
            "be identified as a real segment."
        ),
    ),
    Code.STRUCTURE_FOREIGN_CONTENT: CodeMeta(
        default_severity="fatal",
        title="A segment appears where none is structurally valid",
        explanation=(
            "A segment sits outside any recognized structural context -- "
            "before the first functional group, between a functional group's "
            "close and the next one, after the interchange trailer, or a "
            "closing segment (SE, GE, IEA) with nothing open to close -- "
            "including a second IEA once the interchange is already closed. "
            "This covers every shape of 'a segment turned up in a place the "
            "envelope structure does not allow', including a body segment "
            "with no open transaction set to belong to."
        ),
    ),

    # -- gs: functional-group-level envelope QA/QC --
    Code.GS_MISSING_GE: CodeMeta(
        default_severity="fatal",
        title="No GE segment closes this functional group",
        explanation=(
            "Every GS functional group must be closed by a matching GE "
            "segment before the next GS or the interchange trailer. None was "
            "found; the group's boundary was inferred from the next such "
            "marker so that everything inside it could still be checked."
        ),
    ),
    Code.GS_CONTROL_NUMBER_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="GS06 does not match GE02",
        explanation=(
            "The Group Control Number set in the GS segment (GS06) must equal "
            "the one echoed back in the GE segment (GE02)."
        ),
    ),
    Code.GS_TRANSACTION_SET_COUNT_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="GE01 does not match the number of transaction sets found",
        explanation=(
            "GE01 (Number of Transaction Sets Included) must equal the actual "
            "count of ST segments in the functional group."
        ),
    ),
    Code.GS_CONTROL_NUMBER_NOT_NUMERIC: CodeMeta(
        default_severity="fatal",
        title="GS06 is not all-numeric",
        explanation=(
            "GS06 (Group Control Number) is defined as numeric (type N0). A "
            "non-numeric value cannot be a valid control number, regardless of "
            "whether it happens to match GE02."
        ),
    ),
    Code.GS_COUNT_NOT_NUMERIC: CodeMeta(
        default_severity="fatal",
        title="GE01 is not all-numeric",
        explanation=(
            "GE01 (Number of Transaction Sets Included) is defined as "
            "numeric. A non-numeric value cannot be a valid count."
        ),
    ),
    Code.GS_CONTROL_NUMBER_DUPLICATE: CodeMeta(
        default_severity="fatal",
        title="GS06 is reused by another functional group in this interchange",
        explanation=(
            "Each functional group's Group Control Number (GS06) must be "
            "unique within the interchange, so its GE can be unambiguously "
            "matched back to it."
        ),
    ),
    Code.GS_VERSION_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="GS08 does not agree with the interchange's version (ISA12)",
        explanation=(
            "GS08 (Version/Release/Industry Identifier Code) must agree with "
            "ISA12 (Interchange Control Version Number) on the version and "
            "release. Compared with leading zeros stripped from both sides, "
            "since real-world senders commonly send GS08 as '4010' rather than "
            "the textbook zero-padded '004010'. Runs regardless of GS07."
        ),
    ),
    Code.GS_RESPONSIBLE_AGENCY_INVALID: CodeMeta(
        default_severity="error",
        title="GS07 is not a recognized responsible agency code",
        explanation=(
            "GS07 (Responsible Agency Code) must be 'X' (Accredited Standards "
            "Committee X12) or 'T' (Transportation Data Coordinating "
            "Committee) -- the complete code list for this element."
        ),
    ),

    # -- st: transaction-set-level envelope QA/QC --
    Code.ST_MISSING_SE: CodeMeta(
        default_severity="fatal",
        title="No SE segment closes this transaction set",
        explanation=(
            "Every ST transaction set must be closed by a matching SE segment "
            "before the next ST, the enclosing GE, or the interchange trailer. "
            "None was found; the transaction set's boundary was inferred from "
            "the next such marker so that everything inside it could still be "
            "checked."
        ),
    ),
    Code.ST_CONTROL_NUMBER_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="ST02 does not match SE02",
        explanation=(
            "The Transaction Set Control Number set in the ST segment (ST02) "
            "must equal the one echoed back in the SE segment (SE02)."
        ),
    ),
    Code.ST_SEGMENT_COUNT_MISMATCH: CodeMeta(
        default_severity="fatal",
        title="SE01 does not match the actual segment count",
        explanation=(
            "SE01 (Number of Included Segments) must equal the actual count "
            "of segments in the transaction set, from ST through SE inclusive."
        ),
    ),
    Code.ST_COUNT_NOT_NUMERIC: CodeMeta(
        default_severity="fatal",
        title="SE01 is not all-numeric",
        explanation=(
            "SE01 (Number of Included Segments) is defined as numeric. A "
            "non-numeric value cannot be a valid count."
        ),
    ),
    Code.ST_CONTROL_NUMBER_DUPLICATE: CodeMeta(
        default_severity="fatal",
        title="ST02 is reused by another transaction set in this functional group",
        explanation=(
            "Each transaction set's Control Number (ST02) must be unique "
            "within its functional group, so its SE can be unambiguously "
            "matched back to it. Unlike GS06/control numbers elsewhere, ST02 "
            "is alphanumeric (type AN), not numeric -- uniqueness is still "
            "required even though numeric format is not."
        ),
    ),
}


def meta(code: Code) -> CodeMeta:
    """Registry row for ``code`` (raises :class:`KeyError` if unregistered)."""
    return META[code]


def resolved_severity(code: Code) -> Severity:
    """The severity to report ``code`` at, right now.

    This is the single report-time resolution point.  Today it is just the
    registry default; when the user-config layer lands it becomes
    ``config override -> registry default`` (and may return ``"ignore"``).
    """
    return META[code].default_severity


def all_codes() -> list[Code]:
    """Every registered code, ordered by area then code string."""
    return sorted(Code, key=lambda c: (AREAS.index(c.area), c.value))
