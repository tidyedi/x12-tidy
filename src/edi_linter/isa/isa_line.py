"""Return the ISA line.

That is the whole job of this module: given the raw file bytes, hand back the
run of bytes that starts with ``ISA`` and ends immediately before the ``GS``
functional-group header.  That run is the "ISA line" -- what every later step
works from.

This module does **not** parse or validate delimiters, elements, lengths, or
the segment terminator.  It only answers "where does the ISA line begin and
end".  Every non-conformance it has to tolerate to do that still produces a
:class:`~edi_linter.diagnostics.Diagnostic` (permissive parse / strict report,
see ``docs/design.md``).

Flow
----
1. ``isa_start = dirty.find(b"ISA")``
2. not found                              -> ``isa.no-tag`` (fatal), stop
3. ``cleansed = dirty[isa_start:]``
4. ``isa_start != 0``                      -> ``isa.leading-bytes`` (warn), continue
5. ``len(cleansed) < 109``                 -> ``isa.interchange-too-short`` (fatal), stop
6. ``element_separator = cleansed[3:4]``;  ``gs = b"GS" + element_separator``
7. ``cleansed[106:109] == gs``             -> fast path, ``gs_pos = 106``
   else ``gs_pos = cleansed.find(gs)``;  ``-1`` -> ``isa.gs-not-found`` (fatal), stop
8. ``isa_line = cleansed[:gs_pos]``
9. ``isa_line.count(element_separator) < 16`` -> ``isa.separator-count-low`` (fatal), stop
   (an ISA header has exactly 16; fewer means this run is not an ISA line, or
   the ``GS`` we anchored on is a false match earlier in the data)
10. return ``isa_line``

The returned run **includes** the segment terminator and any trailing bytes
(appended newlines, stray spaces) that sit between it and ``GS``.  Splitting
that into ISA01..ISA16 + terminator + trailing junk is the next step's job.

Known limitation
----------------
If leading junk happens to end in ``ISA`` followed by a byte that also works as
the element separator, step 1 anchors on the junk.  Steps 9 and the next step's
element checks catch the result, and ``isa.leading-bytes`` always fires in that
case -- but a smarter multi-candidate ``ISA`` anchor is a possible later
refinement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edi_linter.diagnostics import Code, Diagnostic

ISA_TAG = b"ISA"
GS_TAG = b"GS"

#: A standard fixed-format ISA line is 105 bytes; the 1-byte segment terminator
#: sits at offset 105, so a conformant file has "GS" + element separator here.
STANDARD_GS_OFFSET = 106
#: ISA line + terminator + "GS" + element separator.
MIN_INTERCHANGE_LEN = 109
#: An ISA header is ``ISA`` followed by exactly this many element separators.
ISA_ELEMENT_SEPARATORS = 16


@dataclass
class IsaLineResult:
    """Outcome of :func:`extract_isa_line`.

    ``isa_line`` is ``None`` exactly when a fatal diagnostic was raised.
    ``isa_start`` is the byte offset of the ISA tag in the original input
    (``-1`` if the tag was never found), so callers can map positions back.
    """

    isa_line: bytes | None
    isa_start: int
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.isa_line is not None


def extract_isa_line(dirty: bytes) -> IsaLineResult:
    """Return the ISA line from ``dirty`` -- see the module docstring."""
    diags: list[Diagnostic] = []

    # 1-2. locate the ISA tag
    isa_start = dirty.find(ISA_TAG)
    if isa_start == -1:
        diags.append(Diagnostic(
            Code.ISA_NO_TAG,
            "no 'ISA' segment tag anywhere in the file; not an X12 interchange.",
        ))
        return IsaLineResult(None, -1, diags)

    # 3. drop everything before the ISA tag
    cleansed = dirty[isa_start:]

    # 4. the ISA tag should be the very first byte of the file
    if isa_start != 0:
        diags.append(Diagnostic(
            Code.ISA_LEADING_BYTES,
            f"{isa_start} byte(s) precede the ISA segment ({dirty[:isa_start]!r}); "
            f"stripped before parsing.",
            offset=0,
        ))

    # 5. sanity floor -- below this there is no interchange to work with
    if len(cleansed) < MIN_INTERCHANGE_LEN:
        diags.append(Diagnostic(
            Code.ISA_INTERCHANGE_TOO_SHORT,
            f"only {len(cleansed)} byte(s) from 'ISA' onward; an X12 interchange "
            f"needs at least a {MIN_INTERCHANGE_LEN}-byte ISA line plus a 'GS' "
            f"header.",
            offset=isa_start,
        ))
        return IsaLineResult(None, isa_start, diags)

    # 6. the element separator is, by rule, the 4th byte of the ISA segment
    element_separator = cleansed[3:4]
    gs_identifier = GS_TAG + element_separator

    # 7. find where the ISA line ends == where the GS segment starts
    if cleansed[STANDARD_GS_OFFSET:STANDARD_GS_OFFSET + 3] == gs_identifier:
        gs_pos = STANDARD_GS_OFFSET  # fast path: GS at the standard offset
    else:
        gs_pos = cleansed.find(gs_identifier)
        if gs_pos == -1:
            diags.append(Diagnostic(
                Code.ISA_GS_NOT_FOUND,
                f"no {gs_identifier!r} functional-group header after the ISA "
                f"segment; cannot locate the end of the ISA line.",
                offset=isa_start,
            ))
            return IsaLineResult(None, isa_start, diags)

    # 8. the ISA line: ISA ... up to (not including) GS
    isa_line = cleansed[:gs_pos]

    # 9. an ISA header carries exactly 16 element separators; fewer means this
    #    run is not an ISA line (or the GS we anchored on is a false match)
    separator_count = isa_line.count(element_separator)
    if separator_count < ISA_ELEMENT_SEPARATORS:
        diags.append(Diagnostic(
            Code.ISA_SEPARATOR_COUNT_LOW,
            f"the bytes before {gs_identifier!r} hold only {separator_count} "
            f"element separator(s) ({element_separator!r}); an ISA header has "
            f"{ISA_ELEMENT_SEPARATORS}.",
            offset=isa_start,
        ))
        return IsaLineResult(None, isa_start, diags)

    return IsaLineResult(isa_line, isa_start, diags)
