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
1. Collect every offset of the exact bytes ``ISA`` (up to
   :data:`MAX_ISA_CANDIDATES`) and try each (step 3). The first that yields a
   clean run wins.
2. If none did: a NUL-interleaved ``I S A`` near the start -> ``isa.tag-utf16``
   (fatal). Otherwise take one lower-case copy of the buffer, collect the
   ``isa`` offsets, and try those case-insensitively (``GS`` matched
   case-insensitively too), carrying ``isa.tag-lowercase`` (error). This also
   rescues a lowercase segment that sits behind junk containing the literal
   uppercase word ``ISA``. If that finds nothing usable either -> ``isa.no-tag``
   (fatal) -- unless a lowercase candidate looked like a real segment start
   (offset 0 or after a non-alphanumeric byte), in which case its failure is
   reported with ``isa.tag-lowercase``.
3. For one candidate:
     a. ``cleansed = dirty[isa_start:]``;  ``len < 109`` -> fail
        (``isa.interchange-too-short``)
     b. ``element_separator = cleansed[3:4]``;  ``gs = b"GS" + separator``
     c. ``cleansed[106:109] == gs`` -> ``gs_pos = 106`` (fast path)
        else ``gs_pos = cleansed.find(gs)``;  not found -> fail
        (``isa.gs-not-found``)
     d. ``isa_line = cleansed[:gs_pos]``;  it must hold **exactly 16** element
        separators -- ``< 16`` -> fail (``isa.separator-count-low``),
        ``> 16`` -> fail (``isa.no-functional-group``: the GS we found is not
        this ISA line's header)
   Any bytes before the winning candidate become ``isa.leading-bytes``
   (warning). If no candidate wins, the **first** candidate's failure is
   reported (with a note if the search cap was hit).

Performance: the common path (an uppercase ``ISA`` that parses) never copies
the buffer. The one full-buffer ``lower()`` happens only when every uppercase
candidate has already failed.

The minimum bar for "this run is an ISA line" -- Step 1 does no component
validation, but a run must clear all three of these to be handed on: (1) it
begins with ``ISA``, (2) it ends immediately before ``GS`` + the element
separator, (3) it holds *exactly* 16 element separators. A run that fails any
of them is not an ISA line: it is reported fatal and does **not** go to the
recovery path. Recovery only ever sees runs that clear this bar but have other
problems (wrong length, bad delimiters, bad element content).

Why exactly 16 and not ``>= 16``: accepting ``>= 16`` let a stray ``GS`` deep in
the transaction body, or leading junk ending in ``ISA`` + a separator-like
byte, produce a plausible-looking but wrong run with no diagnostic. ``> 16`` is
unrecoverable by definition -- a segment whose separator appears in its own data
has no unambiguous parse. Retrying from the next ``ISA`` candidate turns a bad
first guess into either a clean run or an honest fatal.

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
            Code.ISA_NO_FUNCTIONAL_GROUP,
            f"a {gs_identifier!r} sequence sits {gs_pos} byte(s) past the ISA "
            f"tag, but {separator_count} element separator(s) "
            f"({element_separator!r}) precede it -- an ISA header has "
            f"{ISA_ELEMENT_SEPARATORS}, so this is not the functional-group "
            f"header. No GS envelope bounds the ISA segment (the match is "
            f"inside a later segment), or {element_separator!r} occurs inside "
            f"ISA06/ISA08 data.",
            offset=isa_start,
        ))

    return _Attempt(isa_line, None)


def extract_isa_line(dirty: bytes) -> IsaLineResult:
    """Return the ISA line from ``dirty`` -- see the module docstring."""
    # Fast path: exact uppercase ISA tags. The overwhelming common case, and it
    # never copies the buffer.
    upper = _isa_offsets(dirty, ISA_TAG)
    result, upper_failure = _try_all(dirty, upper, case_insensitive=False)
    if result is not None:
        return result

    # No uppercase tag produced an ISA line. UTF-16 only matters when there is
    # no uppercase tag at all.
    if not upper and any(m in dirty[:_UTF16_SCAN_LEN] for m in _UTF16_MARKERS):
        return IsaLineResult(None, -1, [Diagnostic(
            Code.ISA_TAG_UTF16,
            "the ISA tag appears with interleaved NUL bytes; the file looks "
            "UTF-16 encoded. X12 requires a single-byte encoding.",
            offset=0,
        )])

    # Case-insensitive fallback -- one full-buffer lower-case copy, only on this
    # already-failed path. Handles a lowercase/mixed-case ISA tag, including one
    # that sits behind junk containing the literal uppercase word "ISA".
    lowered = dirty.lower()
    ci_failure: tuple[int, Diagnostic] | None = None
    if ISA_TAG.lower() in lowered:
        ci_offsets = _isa_offsets(lowered, ISA_TAG.lower())
        result, ci_failure = _try_all(dirty, ci_offsets, case_insensitive=True)
        if result is not None:
            return result

    # Nothing produced an ISA line. Report the most useful failure.
    if upper_failure is not None:
        isa_start, failure = upper_failure          # an uppercase tag existed
        return IsaLineResult(None, isa_start, _cap_note([failure], len(upper)))
    if ci_failure is not None and _looks_like_segment_start(dirty, ci_failure[0]):
        isa_start, failure = ci_failure             # a real lowercase attempt
        return IsaLineResult(None, isa_start, [
            _lowercase_tag_diagnostic(isa_start), failure,
        ])
    # "isa" only ever appeared inside a word, or not at all.
    return IsaLineResult(None, -1, [Diagnostic(
        Code.ISA_NO_TAG,
        "no 'ISA' segment tag anywhere in the file; not an X12 interchange.",
    )])


def _try_all(
    dirty: bytes, offsets: list[int], *, case_insensitive: bool
) -> tuple[IsaLineResult | None, tuple[int, Diagnostic] | None]:
    """Try each candidate. Return ``(result, None)`` on the first clean run, or
    ``(None, first_failure)`` if every candidate failed / there were none."""
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
            ), None
        if first_failure is None:
            first_failure = (isa_start, attempt.failure)  # type: ignore[assignment]
    return None, first_failure


def _looks_like_segment_start(dirty: bytes, offset: int) -> bool:
    """Whether ``offset`` is where a segment could begin -- start of file, or
    right after a non-alphanumeric byte. Distinguishes a real lowercase ``isa*``
    from ``isa`` buried in a word like "advisable"."""
    return offset == 0 or not dirty[offset - 1: offset].isalnum()


def _cap_note(diags: list[Diagnostic], n_tried: int) -> list[Diagnostic]:
    """Append a note to the last diagnostic if the candidate cap was reached."""
    if n_tried < MAX_ISA_CANDIDATES or not diags:
        return diags
    last = diags[-1]
    return diags[:-1] + [Diagnostic(
        last.code,
        f"{last.message} ({MAX_ISA_CANDIDATES} 'ISA' candidates tried, "
        f"search cap reached -- a later one may be the real segment.)",
        last.offset,
    )]


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
        "the ISA segment tag is not uppercase ('isa' or mixed case); X12 "
        "segment tags are uppercase. Parsed case-insensitively.",
        offset=isa_start,
    )
