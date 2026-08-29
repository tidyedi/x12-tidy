"""Return the ISA line.

That is the whole job of this module: given the raw file bytes, hand back the
run of bytes that starts with ``ISA`` and ends immediately before the ``GS``
functional-group header. That run is the "ISA line" -- what every later step
works from.

This module does **not** parse or validate delimiters, elements, lengths, or
the segment terminator. It only answers "where does the ISA line begin and
end". Every non-conformance it has to tolerate to do that still produces a
:class:`~edi_linter.diagnostics.Diagnostic` (permissive parse / strict report,
see ``docs/design.md``).

Flow
----
1. Collect every offset of ``ISA`` in the file (up to
   :data:`MAX_ISA_CANDIDATES`). If there is none:
     * NUL-interleaved ``I S A`` near the start -> ``isa.tag-utf16`` (fatal)
     * a lowercase ``isa`` somewhere -> switch to case-insensitive matching
       and carry an ``isa.tag-lowercase`` (error)
     * otherwise -> ``isa.no-tag`` (fatal)
2. Try each candidate in order. For one candidate:
     a. ``cleansed = dirty[isa_start:]``;  ``len < 109`` -> fail
        (``isa.interchange-too-short``)
     b. ``element_separator = cleansed[3:4]``;  ``gs = b"GS" + separator``
     c. ``cleansed[106:109] == gs`` -> ``gs_pos = 106`` (fast path)
        else ``gs_pos = cleansed.find(gs)``;  not found -> fail
        (``isa.gs-not-found``)
     d. ``isa_line = cleansed[:gs_pos]``;  it must hold **exactly 16** element
        separators -- ``< 16`` -> fail (``isa.separator-count-low``),
        ``> 16`` -> fail (``isa.separator-count-high``)
3. The first candidate that yields an exactly-16 run wins. Any bytes before it
   become ``isa.leading-bytes`` (warning). If no candidate wins, the **first**
   candidate's failure is reported.

Why "exactly 16": an ISA header has exactly 16 element separators. Accepting
``>= 16`` let a stray ``GS`` deep in the transaction body, or leading junk that
ends in ``ISA`` + a separator-like byte, produce a plausible-looking but wrong
run with no diagnostic. Requiring exactly 16 -- and retrying from the next
``ISA`` candidate -- turns those into either a clean recovery or an honest
fatal.

The returned run **includes** the segment terminator and any trailing bytes
(appended newlines, stray spaces) between it and ``GS``. Splitting that into
ISA01..ISA16 + terminator + trailing junk is the next step's job.
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
#: Cap on how many ``ISA`` occurrences to try before giving up -- guards against
#: a pathological file that is mostly the bytes ``ISA``.
MAX_ISA_CANDIDATES = 16
#: What a UTF-16-encoded ``ISA`` tag looks like (LE, then BE).
_UTF16_MARKERS = (b"I\x00S\x00A", b"\x00I\x00S\x00A")
#: How far into the file to look for the UTF-16 markers.
_UTF16_SCAN_LEN = 512


@dataclass
class IsaLineResult:
    """Outcome of :func:`extract_isa_line`.

    ``isa_line`` is ``None`` exactly when a fatal diagnostic was raised.
    ``isa_start`` is the byte offset of the winning (or, on failure, the first
    tried) ISA tag in the original input -- ``-1`` if no tag was found at all.
    """

    isa_line: bytes | None
    isa_start: int
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.isa_line is not None


@dataclass
class _Attempt:
    """What trying one ISA-tag candidate produced."""

    isa_line: bytes | None
    failure: Diagnostic | None  # set iff isa_line is None


def _isa_offsets(haystack: bytes, tag: bytes = ISA_TAG) -> list[int]:
    offsets: list[int] = []
    at = haystack.find(tag)
    while at != -1 and len(offsets) < MAX_ISA_CANDIDATES:
        offsets.append(at)
        at = haystack.find(tag, at + 1)
    return offsets


def _try_candidate(
    dirty: bytes, isa_start: int, *, case_insensitive: bool
) -> _Attempt:
    cleansed = dirty[isa_start:]

    # a. sanity floor -- below this there is no interchange to work with
    if len(cleansed) < MIN_INTERCHANGE_LEN:
        return _Attempt(None, Diagnostic(
            Code.ISA_INTERCHANGE_TOO_SHORT,
            f"only {len(cleansed)} byte(s) from the ISA tag onward; an X12 "
            f"interchange needs at least a {MIN_INTERCHANGE_LEN}-byte ISA line "
            f"plus a 'GS' header.",
            offset=isa_start,
        ))

    # b. the element separator is, by rule, the 4th byte of the ISA segment
    element_separator = cleansed[3:4]
    gs_identifier = GS_TAG + element_separator

    hay = cleansed.lower() if case_insensitive else cleansed
    needle = gs_identifier.lower() if case_insensitive else gs_identifier

    # c. find where the ISA line ends == where the GS segment starts
    if hay[STANDARD_GS_OFFSET:STANDARD_GS_OFFSET + 3] == needle:
        gs_pos = STANDARD_GS_OFFSET  # fast path: GS at the standard offset
    else:
        gs_pos = hay.find(needle)
        if gs_pos == -1:
            return _Attempt(None, Diagnostic(
                Code.ISA_GS_NOT_FOUND,
                f"no {gs_identifier!r} functional-group header after the ISA "
                f"segment; cannot locate the end of the ISA line.",
                offset=isa_start,
            ))

    # d. the run must hold exactly 16 element separators
    isa_line = cleansed[:gs_pos]
    separator_count = isa_line.count(element_separator)
    if separator_count < ISA_ELEMENT_SEPARATORS:
        return _Attempt(None, Diagnostic(
            Code.ISA_SEPARATOR_COUNT_LOW,
            f"the bytes before {gs_identifier!r} hold only {separator_count} "
            f"element separator(s) ({element_separator!r}); an ISA header has "
            f"{ISA_ELEMENT_SEPARATORS}.",
            offset=isa_start,
        ))
    if separator_count > ISA_ELEMENT_SEPARATORS:
        return _Attempt(None, Diagnostic(
            Code.ISA_SEPARATOR_COUNT_HIGH,
            f"the bytes before {gs_identifier!r} hold {separator_count} element "
            f"separator(s) ({element_separator!r}); an ISA header has exactly "
            f"{ISA_ELEMENT_SEPARATORS}. The separator occurs inside ISA data, "
            f"or the line ran past a stray 'GS'.",
            offset=isa_start,
        ))

    return _Attempt(isa_line, None)


def extract_isa_line(dirty: bytes) -> IsaLineResult:
    """Return the ISA line from ``dirty`` -- see the module docstring."""
    offsets = _isa_offsets(dirty)
    case_insensitive = False

    if not offsets:
        # No uppercase ISA tag. Two salvageable explanations before giving up.
        if any(m in dirty[:_UTF16_SCAN_LEN] for m in _UTF16_MARKERS):
            return IsaLineResult(None, -1, [Diagnostic(
                Code.ISA_TAG_UTF16,
                "the ISA tag appears with interleaved NUL bytes; the file looks "
                "UTF-16 encoded. X12 requires a single-byte encoding.",
                offset=0,
            )])
        # One full-buffer lower-case copy, only on this already-failed path.
        lowered = dirty.lower()
        if ISA_TAG.lower() in lowered:
            offsets = _isa_offsets(lowered, ISA_TAG.lower())
            case_insensitive = True
        else:
            return IsaLineResult(None, -1, [Diagnostic(
                Code.ISA_NO_TAG,
                "no 'ISA' segment tag anywhere in the file; not an X12 "
                "interchange.",
            )])

    first_failure: tuple[int, Diagnostic] | None = None
    for isa_start in offsets:
        attempt = _try_candidate(
            dirty, isa_start, case_insensitive=case_insensitive
        )
        if attempt.isa_line is not None:
            return IsaLineResult(
                attempt.isa_line,
                isa_start,
                _context_diagnostics(dirty, isa_start, case_insensitive),
            )
        if first_failure is None:
            first_failure = (isa_start, attempt.failure)  # type: ignore[assignment]

    assert first_failure is not None  # offsets is non-empty here
    isa_start, failure = first_failure
    diags: list[Diagnostic] = []
    if case_insensitive:
        diags.append(_lowercase_tag_diagnostic(isa_start))
    diags.append(failure)
    return IsaLineResult(None, isa_start, diags)


def _context_diagnostics(
    dirty: bytes, isa_start: int, case_insensitive: bool
) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    if case_insensitive:
        diags.append(_lowercase_tag_diagnostic(isa_start))
    if isa_start != 0:
        diags.append(Diagnostic(
            Code.ISA_LEADING_BYTES,
            f"{isa_start} byte(s) precede the ISA segment "
            f"({dirty[:isa_start]!r}); stripped before parsing.",
            offset=0,
        ))
    return diags


def _lowercase_tag_diagnostic(isa_start: int) -> Diagnostic:
    return Diagnostic(
        Code.ISA_TAG_LOWERCASE,
        "the ISA segment tag is lowercase; X12 segment tags are uppercase. "
        "Parsed case-insensitively.",
        offset=isa_start,
    )
