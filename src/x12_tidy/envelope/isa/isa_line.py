# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Return the ISA line.

That is the whole job of this module: given the raw file bytes, hand back the
run of bytes that starts with ``ISA`` and ends immediately before the ``GS``
functional-group header. That run is the "ISA line" -- what every later step
works from.

This module does **not** parse or validate delimiters, elements, lengths, or
the segment terminator. It only answers "where does the ISA line begin and
end". Every non-conformance it has to tolerate to do that still produces a
:class:`~x12_tidy.diagnostics.Diagnostic` (permissive parse / strict report,
see ``docs/design.md``).

Flow
----
1. Collect every offset of the exact bytes ``ISA`` (up to
   :data:`MAX_ISA_CANDIDATES`) and try each (step 3). The first that yields a
   clean run wins.
0. A NUL-interleaved ``I S A`` near the start (or a UTF-16 BOM) -> the buffer is
   transcoded from UTF-16 to single-byte and re-parsed, carrying
   ``isa.identifier-utf16`` (warning). Offsets then index the transcoded bytes.
2. If no uppercase ``ISA`` yielded a run: take one lower-case copy of the
   buffer, collect the ``isa`` offsets, and try those case-insensitively (``GS`` matched
   case-insensitively too), carrying ``isa.identifier-lowercase`` (error). This also
   rescues a lowercase segment that sits behind junk containing the literal
   uppercase word ``ISA``. If that finds nothing usable either -> ``isa.no-identifier``
   (fatal) -- unless a lowercase candidate looked like a real segment start
   (offset 0 or after a non-alphanumeric byte), in which case its failure is
   reported with ``isa.identifier-lowercase``.
3. For one candidate:
     a. ``cleansed = dirty[isa_start:]``;  ``len < 109`` -> fail
        (``isa.interchange-too-short``)
     b. ``element_separator = cleansed[3:4]``;  ``gs = b"GS" + separator``
     c. ``cleansed[106:109] == gs`` -> ``gs_pos = 106`` (fast path); else count
        forward to the **16th** occurrence of the element separator (not: search
        for ``gs`` first) -- fewer than 16 anywhere left in the buffer -> fail
        (``isa.separator-count-low``). From just past that 16th separator, scan
        forward for ``gs``, but only through non-alphanumeric bytes (a real or
        absent ISA16, the terminator, tolerated trailing junk); the moment an
        ordinary letter/digit turns up that isn't itself the start of ``gs``,
        stop -- it proves ``gs`` would be the tail of some other field's value,
        not a real token -- and fail (``isa.element-separator-invalid`` if
        ``cleansed[3:4]`` is itself a letter or digit -- the search token was
        meaningless; otherwise ``isa.gs-not-found``)
     d. ``isa_line = cleansed[:gs_pos]``;  it must hold **exactly 16** element
        separators -- ``< 16`` -> fail (``isa.separator-count-low``),
        ``> 16`` -> fail (``isa.separator-count-high``: an extra separator byte,
        e.g. a delimiter collision, sits between the 16th separator and ``gs_pos``
        -- rare now that ``gs_pos`` is found by counting rather than by search,
        but still possible on the offset-106 fast path or when trailing junk
        itself contains the separator byte)
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

Why exactly 16 and not ``>= 16``: a 17th occurrence of the element separator
turning up before ``GS`` + separator is confirmed is a delimiter *collision*
-- ISA16 (the component separator) or the segment terminator equals the
element separator -- so the boundary is unrecoverable by definition, not
merely an extra count to tolerate. (A separate danger -- a naive search for
``GS`` text landing inside a stray ``GS*`` deep in the transaction body, or in
leading junk, and *coincidentally* counting 16 separators up to that false
match -- is why Step 1 counts to the 16th separator by *position* before ever
searching for ``GS``, rather than the reverse; see the worked example in
``finding-the-elusive-isa-line.md`` §5.3. That is an ordering choice, not this
16-vs-more-than-16 boundary.) Retrying from the next ``ISA`` candidate turns a
bad first guess into either a clean run or an honest fatal.

The returned run **includes** the segment terminator and any trailing bytes
(appended newlines, stray spaces) between it and ``GS``. Splitting that into
ISA01..ISA16 + terminator + trailing junk is the next step's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic

ISA_IDENTIFIER = b"ISA"
GS_IDENTIFIER = b"GS"

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
#: What a UTF-16-encoded ``ISA`` identifier looks like: LE is ``I . S . A``, BE
#: is ``. I . S . A`` (``.`` = NUL). The BE marker contains the LE marker, so a
#: caller must test BE first.
_UTF16_MARKERS = (b"I\x00S\x00A", b"\x00I\x00S\x00A")
#: How far into the file to look for the UTF-16 markers.
_UTF16_SCAN_LEN = 512


def decode_utf16(dirty: bytes) -> bytes | None:
    """Return ``dirty`` transcoded from UTF-16 to single-byte, or ``None`` if it
    is not UTF-16.

    A conformant X12 interchange is a single-byte stream; a UTF-16 export
    interleaves a NUL with every character and nothing downstream can parse it.
    Valid X12 content is ASCII, so the transcription is lossless -- a byte that
    somehow lands outside Latin-1 becomes ``?``. Byte order comes from the BOM
    when present, otherwise from which ``ISA`` marker is found.

    Offsets into the returned bytes do **not** map to the original file; the
    caller that surfaces this must say so.
    """
    head = dirty[:_UTF16_SCAN_LEN]
    if dirty[:2] in (b"\xff\xfe", b"\xfe\xff"):
        codec = "utf-16"                     # the BOM carries the byte order
    elif _UTF16_MARKERS[1] in head:          # BE -- must be tested before LE
        codec = "utf-16-be"
    elif _UTF16_MARKERS[0] in head:          # LE
        codec = "utf-16-le"
    else:
        return None
    try:
        return dirty.decode(codec).encode("latin-1", "replace")
    except (UnicodeDecodeError, ValueError):
        return None


@dataclass
class IsaLineResult:
    """Outcome of :func:`extract_isa_line`.

    ``isa_line`` is ``None`` exactly when a fatal diagnostic was raised.
    ``isa_start`` is the byte offset of the winning (or, on failure, the first
    tried) ISA identifier in the original input -- ``-1`` if no identifier was found at all.
    """

    isa_line: bytes | None
    isa_start: int
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.isa_line is not None


@dataclass
class IsaCandidateAttempt:
    """What trying one ISA-identifier candidate produced.

    ``confirmed_structure`` is True once the run has established a genuine,
    complete 16-element-separator ISA shape -- even if it then fails to find
    a valid GS header, or the separator count turns out too high once GS is
    found. A caller deciding whether a *failed* candidate is probably
    coincidental junk (weak evidence, safe to skip and try the next ``ISA``)
    or a real, if broken, interchange (strong evidence -- this candidate is
    what it is, not something to search past) should read this field, not
    the specific failure code: real junk essentially never accidentally
    produces exactly 16 real element separators in the right shape.
    """

    isa_line: bytes | None
    failure: Diagnostic | None  # set iff isa_line is None
    confirmed_structure: bool


def _isa_offsets(haystack: bytes, identifier: bytes = ISA_IDENTIFIER) -> list[int]:
    offsets: list[int] = []
    at = haystack.find(identifier)
    while at != -1 and len(offsets) < MAX_ISA_CANDIDATES:
        offsets.append(at)
        at = haystack.find(identifier, at + 1)
    return offsets


def _nth_occurrence(haystack: bytes, needle: bytes, n: int) -> int:
    """0-indexed position of the ``n``-th occurrence of ``needle`` in
    ``haystack``, or ``-1`` if it occurs fewer than ``n`` times."""
    pos = -1
    for _ in range(n):
        pos = haystack.find(needle, pos + 1)
        if pos == -1:
            return -1
    return pos


def _gs_after_boundary(
    haystack: bytes, start: int, needle: bytes, element_separator: bytes
) -> int:
    """Search forward from ``start`` for ``needle``, but only through bytes
    that could plausibly be ISA16 (or its absence), the terminator, or
    tolerated trailing junk -- never an alphanumeric byte, and never another
    occurrence of ``element_separator`` itself. Either one stops the search
    immediately (unless it's the start of ``needle``): an alphanumeric byte
    means real element content, so ``needle`` starting later would be the
    tail of some other field's value, not a real token; the element separator
    has no business appearing in this gap at all -- seeing it here is proof
    we're inside field-delimited content, not the terminator-and-junk zone.
    Returns ``-1`` if no match is found before that happens (or before the
    end of ``haystack``)."""
    pos = start
    while pos < len(haystack):
        if haystack[pos:pos + len(needle)] == needle:
            return pos
        byte = haystack[pos:pos + 1]
        if byte.isalnum() or byte == element_separator:
            return -1
        pos += 1
    return -1


def try_isa_candidate(
    dirty: bytes, isa_start: int, *, case_insensitive: bool = False
) -> IsaCandidateAttempt:
    """Try exactly one ``ISA``-identifier candidate at ``isa_start`` -- no
    retry, no trying a different offset on failure. See
    :class:`IsaCandidateAttempt` on why a caller enumerating candidates
    itself (rather than using :func:`extract_isa_line`'s own retry, built for
    skipping leading junk ahead of a single interchange) needs this distinct
    from a plain success/failure result."""
    cleansed = dirty[isa_start:]

    # a. sanity floor -- below this there is no interchange to work with
    if len(cleansed) < MIN_INTERCHANGE_LEN:
        return IsaCandidateAttempt(None, Diagnostic(
            Code.ISA_INTERCHANGE_TOO_SHORT,
            f"only {len(cleansed)} byte(s) from the ISA identifier onward; an X12 "
            f"interchange needs at least a {MIN_INTERCHANGE_LEN}-byte ISA line "
            f"plus a 'GS' header.",
            offset=isa_start,
        ), confirmed_structure=False)

    # b. the element separator is, by rule, the 4th byte of the ISA segment
    element_separator = cleansed[3:4]
    gs_identifier = GS_IDENTIFIER + element_separator

    hay = cleansed.lower() if case_insensitive else cleansed
    needle = gs_identifier.lower() if case_insensitive else gs_identifier

    # c. find where the ISA line ends == where the GS segment starts
    if hay[STANDARD_GS_OFFSET:STANDARD_GS_OFFSET + 3] == needle:
        gs_pos = STANDARD_GS_OFFSET  # fast path: GS at the standard offset
    else:
        # Walk to the 16th element separator -- the byte the standard says
        # must precede ISA16 -- instead of searching for 'GS' first. Searching
        # for 'GS' first risks anchoring on a lookalike (inside ISA06/ISA08
        # data, or deep in a later segment when the real GS is missing);
        # counting separators first means the content of any element, or of
        # later segments, is never even examined as a candidate.
        sixteenth_sep = _nth_occurrence(hay, element_separator, ISA_ELEMENT_SEPARATORS)
        if sixteenth_sep == -1:
            return IsaCandidateAttempt(None, Diagnostic(
                Code.ISA_SEPARATOR_COUNT_LOW,
                f"fewer than {ISA_ELEMENT_SEPARATORS} element separator(s) "
                f"({element_separator!r}) appear anywhere after the ISA "
                f"identifier; an ISA header has {ISA_ELEMENT_SEPARATORS}, so "
                f"there is no GS header to find and the segment terminator "
                f"cannot be determined.",
                offset=isa_start,
            ), confirmed_structure=False)
        # Everything from here to GS must be ISA16 (present or, tolerated,
        # absent), the terminator, and non-alphanumeric trailing junk (a
        # stray space, appended '\r\n') -- never ordinary element content,
        # and never another element separator (that would mean we're inside
        # field-delimited content, not the terminator-and-junk gap). The
        # moment either turns up and isn't itself the start of a real GS
        # match, GS is not a token here, it's the tail of some other field's
        # value (e.g. 'SENDERGS*') -- stop rather than keep searching, so
        # that coincidence is refused, not silently accepted.
        gs_pos = _gs_after_boundary(hay, sixteenth_sep + 1, needle, element_separator)
        if gs_pos == -1:
            # The GS boundary is searched for as 'GS' + the 4th ISA byte. If
            # that byte is a letter or digit it is element data, not a
            # delimiter -- the search token is meaningless, so the real fault
            # is the separator, not a missing GS (which is usually present in
            # the file, just not as 'GS' + that byte). Report the root cause;
            # delimiters.py would otherwise never get to raise it.
            if element_separator.isalnum():
                return IsaCandidateAttempt(None, Diagnostic(
                    Code.ISA_ELEMENT_SEPARATOR_INVALID,
                    f"the element separator (4th byte of the ISA segment) is "
                    f"{element_separator!r}, a letter or digit -- it cannot be "
                    f"told apart from element data, so the ISA line can be "
                    f"neither delimited nor bounded.",
                    offset=isa_start + 3,
                ), confirmed_structure=True)
            return IsaCandidateAttempt(None, Diagnostic(
                Code.ISA_GS_NOT_FOUND,
                f"no {gs_identifier!r} functional-group header anywhere after "
                f"the 16th element separator ({element_separator!r}) and "
                f"ISA16; cannot locate the end of the ISA line.",
                offset=isa_start,
            ), confirmed_structure=True)

    # d. the run must hold exactly 16 element separators
    isa_line = cleansed[:gs_pos]
    separator_count = isa_line.count(element_separator)
    if separator_count < ISA_ELEMENT_SEPARATORS:
        # Only reachable via the fast path (offset 106) -- the slow path
        # above already guarantees at least 16 by construction.
        return IsaCandidateAttempt(None, Diagnostic(
            Code.ISA_SEPARATOR_COUNT_LOW,
            f"the bytes before {gs_identifier!r} hold only {separator_count} "
            f"element separator(s) ({element_separator!r}); an ISA header has "
            f"{ISA_ELEMENT_SEPARATORS}.",
            offset=isa_start,
        ), confirmed_structure=False)
    if separator_count > ISA_ELEMENT_SEPARATORS:
        return IsaCandidateAttempt(None, Diagnostic(
            Code.ISA_SEPARATOR_COUNT_HIGH,
            f"a {gs_identifier!r} sequence sits {gs_pos} byte(s) past the ISA "
            f"identifier, but {separator_count} element separator(s) "
            f"({element_separator!r}) precede it -- an ISA header has "
            f"{ISA_ELEMENT_SEPARATORS}, so this is not the functional-group "
            f"header. No GS envelope bounds the ISA segment (the match is "
            f"inside a later segment), or {element_separator!r} occurs inside "
            f"ISA06/ISA08 data.",
            offset=isa_start,
        ), confirmed_structure=True)

    return IsaCandidateAttempt(isa_line, None, confirmed_structure=True)


def extract_isa_line(dirty: bytes) -> IsaLineResult:
    """Return the ISA line from ``dirty`` -- see the module docstring."""
    # UTF-16? Transcode to single-byte and parse that. The notice is a warning,
    # not a refusal -- valid X12 content is ASCII, so the transcription is
    # lossless. Every offset from here on indexes the transcoded bytes.
    transcoded = decode_utf16(dirty)
    if transcoded is not None:
        inner = extract_isa_line(transcoded)
        notice = Diagnostic(
            Code.ISA_IDENTIFIER_UTF16,
            "the file is UTF-16 encoded -- the ISA identifier appears with "
            "interleaved NUL bytes. Transcoded to single-byte and parsed; every "
            "offset below indexes the transcoded bytes, not the original file.",
            offset=0,
        )
        return IsaLineResult(
            inner.isa_line, inner.isa_start, [notice, *inner.diagnostics]
        )

    # Fast path: exact uppercase ISA identifiers. The overwhelming common case, and it
    # never copies the buffer.
    upper = _isa_offsets(dirty, ISA_IDENTIFIER)
    result, upper_failure = _try_all(dirty, upper, case_insensitive=False)
    if result is not None:
        return result

    # Case-insensitive fallback -- one full-buffer lower-case copy, only on this
    # already-failed path. Handles a lowercase/mixed-case ISA identifier, including one
    # that sits behind junk containing the literal uppercase word "ISA".
    lowered = dirty.lower()
    ci_failure: tuple[int, Diagnostic] | None = None
    if ISA_IDENTIFIER.lower() in lowered:
        ci_offsets = _isa_offsets(lowered, ISA_IDENTIFIER.lower())
        result, ci_failure = _try_all(dirty, ci_offsets, case_insensitive=True)
        if result is not None:
            return result

    # Nothing produced an ISA line. Report the most useful failure.
    if upper_failure is not None:
        isa_start, failure = upper_failure          # an uppercase identifier existed
        return IsaLineResult(None, isa_start, _cap_note([failure], len(upper)))
    if ci_failure is not None and _looks_like_segment_start(dirty, ci_failure[0]):
        isa_start, failure = ci_failure             # a real lowercase attempt
        return IsaLineResult(None, isa_start, [
            _lowercase_tag_diagnostic(isa_start), failure,
        ])
    # "isa" only ever appeared inside a word, or not at all.
    return IsaLineResult(None, -1, [Diagnostic(
        Code.ISA_NO_IDENTIFIER,
        "no 'ISA' segment identifier anywhere in the file; not an X12 interchange.",
    )])


def _try_all(
    dirty: bytes, offsets: list[int], *, case_insensitive: bool
) -> tuple[IsaLineResult | None, tuple[int, Diagnostic] | None]:
    """Try each candidate. Return ``(result, None)`` on the first clean run, or
    ``(None, first_failure)`` if every candidate failed / there were none."""
    first_failure: tuple[int, Diagnostic] | None = None
    for isa_start in offsets:
        attempt = try_isa_candidate(
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
        Code.ISA_IDENTIFIER_LOWERCASE,
        "the ISA segment identifier is not uppercase ('isa' or mixed case); X12 "
        "segment identifiers are uppercase. Parsed case-insensitively.",
        offset=isa_start,
    )
