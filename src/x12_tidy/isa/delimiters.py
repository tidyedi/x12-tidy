# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Step 2, slice 1: parse the delimiters out of the ISA line.

:func:`~x12_tidy.isa.extract_isa_line` (Step 1) hands back the run of bytes from
``ISA`` to just before ``GS`` -- guaranteed to hold *exactly* 16 element
separators and to end at the ``GS`` boundary. That is enough to recover every
X12 delimiter without ever trusting a byte offset.

Delimiters
----------
* **element separator** -- ``run[3]``, by rule the 4th byte of the segment.
* **repetition separator** -- ISA11, but *only* when ISA12 (the version code) is
  ``00403`` or later. Before that, ISA11 is the Interchange Control Standards
  Identifier ``U`` and there is no repetition separator.
* **component separator** -- the value of ISA16: the first byte after the 16th
  element separator.
* **segment terminator** -- the one byte after that. One byte, by rule -- which
  is what makes ``~\r\n`` / ``\r\r`` / ``~\n`` decompose deterministically
  instead of ambiguously.

Method
------
Split the run on the element separator: 17 pieces come back -- ``ISA``,
ISA01..ISA15, then ``ISA16 + terminator + trailing``. Everything is read from
that split, so stripped or re-padded elements -- which shift every byte offset
-- do not matter: the separator *count* and the ``GS`` boundary do not move.

Severity
--------
One rule: **a delimiter finding is fatal here only if it blocks parsing the
interchange outright.** The element separator and the segment terminator are
needed for every segment, so an unusable one is fatal. The component separator
(composite elements) and the repetition separator (repeated data elements) are
only needed if the body actually uses them -- an unusable one is an ``error``
now, and the body parser escalates it to fatal at the exact segment that needs
it, if one ever does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic, resolved_severity

#: ``ISA`` + ISA01..ISA16.
ISA_ELEMENT_SEPARATORS = 16
#: The canonical segment terminator; a non-``~`` terminator is normalised to it.
CANONICAL_TERMINATOR = b"~"
#: ISA11's value for interchanges that predate the repetition separator.
STANDARDS_IDENTIFIER = b"U"
#: First ISA12 version code in which ISA11 is the repetition separator
#: (version 004030). Codes are 5-digit zero-padded, so a bytes comparison works.
REPETITION_SEPARATOR_MIN_VERSION = b"00403"


@dataclass
class IsaDelimiters:
    """The delimiters recovered from an ISA-line run.

    Field values are filled in best-effort even when a fatal was raised, so the
    diagnostics always have context; check :attr:`usable` before trusting them.
    ``repetition_separator`` is ``None`` when the version predates it or when
    ISA11 does not carry one.
    """

    element_separator: bytes
    repetition_separator: bytes | None
    component_separator: bytes
    segment_terminator: bytes
    trailing: bytes
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """No diagnostic resolves to ``fatal`` -- the interchange can be parsed
        with these delimiters (some may still be non-conformant)."""
        return not any(
            resolved_severity(d.code) == "fatal" for d in self.diagnostics
        )


def _is_alnum(byte: bytes) -> bool:
    return len(byte) == 1 and byte.isalnum()


def _version_has_repetition_separator(version: bytes) -> bool | None:
    """Whether ISA11 is the repetition separator for this ISA12 code.

    ``None`` when ``version`` is not a recognisable 5-digit version code.
    """
    if len(version) == 5 and version.isdigit():
        return version >= REPETITION_SEPARATOR_MIN_VERSION
    return None


def split_isa_line(run: bytes, *, base_offset: int = 0) -> IsaDelimiters:
    """Recover the delimiters from ``run`` -- the byte run from
    :func:`~x12_tidy.isa.extract_isa_line`. ``base_offset`` is the offset of
    ``run`` within the original input, added to every diagnostic offset.

    See the module docstring for the method and the severity rule.
    """
    diags: list[Diagnostic] = []
    element_separator = run[3:4]

    if len(element_separator) != 1:
        diags.append(Diagnostic(
            Code.ISA_DELIMITER_MISALIGNED,
            f"the run is {len(run)} byte(s) -- too short to hold an ISA segment "
            "tag and an element separator.",
            offset=base_offset,
        ))
        return IsaDelimiters(element_separator, None, b"", b"", b"", diags)

    parts = run.split(element_separator)

    # Step 1 guarantees exactly 16 element separators -> 17 parts. A different
    # count means split_isa_line was handed a run Step 1 would not have
    # returned, or the element separator occurs inside its own element data.
    if len(parts) != ISA_ELEMENT_SEPARATORS + 1:
        diags.append(Diagnostic(
            Code.ISA_DELIMITER_MISALIGNED,
            f"splitting the ISA-line run on {element_separator!r} yields "
            f"{len(parts) - 1} element(s), not {ISA_ELEMENT_SEPARATORS}; the "
            f"element separator is wrong or occurs inside ISA06/ISA08 data.",
            offset=base_offset,
        ))
        return IsaDelimiters(element_separator, None, b"", b"", b"", diags)

    version = parts[12]
    isa11 = parts[11]
    tail = parts[16]  # ISA16 + terminator + trailing
    tail_offset = base_offset + len(run) - len(tail)

    if not tail:
        diags.append(Diagnostic(
            Code.ISA_ISA16_MISSING,
            "nothing follows ISA15 in the run: no ISA16, component separator, "
            "or segment terminator.",
            offset=tail_offset,
        ))
        return IsaDelimiters(element_separator, None, b"", b"", b"", diags)

    component_separator = tail[0:1]
    after = tail[1:]

    if not after:
        # Only the component separator is present; GS came straight after it.
        segment_terminator = CANONICAL_TERMINATOR
        trailing = b""
        diags.append(Diagnostic(
            Code.ISA_SEGMENT_TERMINATOR_STRIPPED,
            "no segment terminator after ISA16 -- GS followed immediately. "
            f"Reconstructed as {CANONICAL_TERMINATOR!r}.",
            offset=tail_offset + 1,
        ))
    else:
        segment_terminator = after[0:1]
        trailing = after[1:]

    # --- element separator: needed for every segment -> fatal if unusable ---
    if _is_alnum(element_separator):
        diags.append(Diagnostic(
            Code.ISA_ELEMENT_SEPARATOR_INVALID,
            f"the element separator is {element_separator!r}, an alphanumeric "
            "byte; it cannot be told apart from element data, so no segment in "
            "the interchange can be reliably parsed.",
            offset=base_offset + 3,
        ))

    # --- component separator vs terminator: both alnum == misaligned split ---
    component_alnum = _is_alnum(component_separator)
    terminator_alnum = _is_alnum(segment_terminator)

    if component_alnum and terminator_alnum:
        diags.append(Diagnostic(
            Code.ISA_DELIMITER_MISALIGNED,
            "the bytes where the component separator and segment terminator "
            f"belong ({tail[:2]!r}) are both alphanumeric; the ISA line cannot "
            "be decomposed (an element separator most likely occurs inside "
            "ISA06 or ISA08 data).",
            offset=tail_offset,
        ))
    else:
        if component_alnum:
            diags.append(Diagnostic(
                Code.ISA_COMPONENT_SEPARATOR_INVALID,
                f"the component separator (ISA16) is {component_separator!r}, "
                "an alphanumeric byte; it collides with data. This is fatal "
                "only if a segment carries a composite element.",
                offset=tail_offset,
            ))
        elif component_separator == b" ":
            diags.append(Diagnostic(
                Code.ISA_COMPONENT_SEPARATOR_INVALID,
                "the component separator (ISA16) is a space; it collides with "
                "element padding. Fatal only if a segment carries a composite "
                "element.",
                offset=tail_offset,
            ))
        if after and terminator_alnum:
            diags.append(Diagnostic(
                Code.ISA_SEGMENT_TERMINATOR_INVALID,
                f"the segment terminator is {segment_terminator!r}, an "
                "alphanumeric byte -- it is data, not a delimiter. Segments "
                "cannot be split.",
                offset=tail_offset + 1,
            ))

    # --- non-canonical but usable terminator (\r, \n, |, ...) ---
    if (
        after
        and not terminator_alnum
        and segment_terminator not in (
            b"", b" ", CANONICAL_TERMINATOR,
            element_separator, component_separator,
        )
    ):
        diags.append(Diagnostic(
            Code.ISA_SEGMENT_TERMINATOR_NONCANONICAL,
            f"the segment terminator is {segment_terminator!r}, not "
            f"{CANONICAL_TERMINATOR!r}; it is usable but will be normalised.",
            offset=tail_offset + 1,
        ))

    # --- collisions that block parsing outright ---
    if segment_terminator and segment_terminator == element_separator:
        diags.append(Diagnostic(
            Code.ISA_DELIMITER_COLLISION,
            f"the segment terminator and the element separator are the same "
            f"byte ({segment_terminator!r}); segment and element boundaries "
            "are indistinguishable.",
            offset=tail_offset + 1,
        ))
    if segment_terminator and segment_terminator == component_separator:
        diags.append(Diagnostic(
            Code.ISA_DELIMITER_COLLISION,
            f"the segment terminator and the component separator are the same "
            f"byte ({segment_terminator!r}); segment and composite boundaries "
            "are indistinguishable.",
            offset=tail_offset + 1,
        ))

    # --- repetition separator (ISA11), gated on the ISA12 version code ---
    repetition_separator: bytes | None = None
    has_repetition = _version_has_repetition_separator(version)
    if has_repetition is None:
        diags.append(Diagnostic(
            Code.ISA_VERSION_UNRECOGNIZED,
            f"ISA12 is {version!r}, not a recognised X12 version code; whether "
            "ISA11 is a repetition separator cannot be determined, so it is "
            "left opaque.",
            offset=base_offset,
        ))
    elif has_repetition:
        if isa11 in (b"", STANDARDS_IDENTIFIER):
            diags.append(Diagnostic(
                Code.ISA_REPETITION_SEPARATOR_MISSING,
                f"ISA12 {version!r} defines ISA11 as the repetition separator, "
                f"but ISA11 is {isa11!r}; repetition is unsupported for this "
                "interchange.",
                offset=base_offset,
            ))
        elif len(isa11) != 1:
            # ISA11 is a fixed 1-byte field; a longer value means an element
            # separator was dropped and ISA11 has swallowed following data.
            diags.append(Diagnostic(
                Code.ISA_REPETITION_SEPARATOR_INVALID,
                f"the repetition separator (ISA11) is {isa11!r}, {len(isa11)} "
                "bytes; it must be exactly one. Repetition is unusable.",
                offset=base_offset,
            ))
        elif _is_alnum(isa11):
            diags.append(Diagnostic(
                Code.ISA_REPETITION_SEPARATOR_INVALID,
                f"the repetition separator (ISA11) is {isa11!r}, an "
                "alphanumeric byte; it collides with data. Fatal only if a "
                "segment repeats a data element.",
                offset=base_offset,
            ))
        elif isa11 in (element_separator, component_separator,
                       segment_terminator):
            diags.append(Diagnostic(
                Code.ISA_REPETITION_SEPARATOR_INVALID,
                f"the repetition separator (ISA11) is {isa11!r}, the same byte "
                "as another delimiter. Fatal only if a segment repeats a data "
                "element.",
                offset=base_offset,
            ))
        else:
            repetition_separator = isa11
    else:
        if isa11 != STANDARDS_IDENTIFIER:
            diags.append(Diagnostic(
                Code.ISA_ISA11_NOT_STANDARDS_ID,
                f"ISA12 {version!r} predates the repetition separator, so ISA11 "
                f"must be {STANDARDS_IDENTIFIER!r}; it is {isa11!r}. Not treated "
                "as a delimiter.",
                offset=base_offset,
            ))

    # --- trailing bytes between the terminator and GS ---
    if trailing:
        trailing_offset = tail_offset + 2
        if all(byte in b"\r\n" for byte in trailing):
            diags.append(Diagnostic(
                Code.ISA_TRAILING_NEWLINE,
                f"{len(trailing)} line-break byte(s) sit between the segment "
                "terminator and GS; the sender appended a newline.",
                offset=trailing_offset,
            ))
        else:
            diags.append(Diagnostic(
                Code.ISA_TRAILING_JUNK,
                f"{len(trailing)} byte(s) sit between the segment terminator "
                f"and GS ({trailing!r}); they are not part of the interchange.",
                offset=trailing_offset,
            ))

    return IsaDelimiters(
        element_separator,
        repetition_separator,
        component_separator,
        segment_terminator,
        trailing,
        diags,
    )
