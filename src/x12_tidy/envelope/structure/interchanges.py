# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Split raw bytes into one chunk per interchange.

A file (or a flat-file batch) can legitimately hold more than one ``ISA``..
``IEA`` interchange concatenated back to back -- each one self-delimited, each
free to declare its own delimiters, none of them junk to discard in favor of
"the" interchange. :func:`split_segments`
(:mod:`x12_tidy.envelope.structure.segments`) has no notion of this: given raw
bytes, it locates one ``ISA`` and then splits everything from ``GS`` onward
all the way to the end of the buffer, so a second interchange's segments are
read as if they belonged to the first.

:func:`split_interchanges` is what the rest of the pipeline is looped over,
once per chunk, to fix that (see :mod:`x12_tidy.envelope.tidy`). It does not
parse or validate a single byte of any interchange's content -- it only
answers "where does one interchange end and the next begin". Each returned
chunk still needs the full single-interchange pipeline (locate the ISA line,
recover its own delimiters, reconstruct, audit) run on it independently; nothing
here assumes, borrows, or carries forward delimiters from one chunk to the
next, because nothing here is allowed to -- that would be exactly the mistake
that makes a second interchange's own delimiters unrecoverable if they differ
from the first's.

One interchange's bytes run from its ``ISA`` through:

1. its own ``IEA`` segment, inclusive -- the ordinary, well-formed case; or
2. wherever the next real ``ISA`` begins, if no ``IEA`` closes this one --
   the same "recover from a missing closer by treating the next recognizable
   boundary as the assumed end" pattern used everywhere else in this tool
   (see :mod:`x12_tidy.envelope.qaqc.checks`); or
3. the end of the input, if there is no next ``ISA`` either -- this is the
   last (possibly broken) interchange in the file.

Finding a chunk's own ``IEA`` is unambiguous once its delimiters are known: it
walks the chunk's segments (bytes already split on the recovered segment
terminator, exactly as :func:`~x12_tidy.envelope.structure.segments.split_segments`
would), and a segment identifier is only ever the text before the first
element separator in an already-delimited segment -- there is no raw-byte
substring search here, and so none of the ambiguity that
:mod:`x12_tidy.envelope.isa.isa_line` has to guard against when it is still
looking for the *first* ``ISA``.

A chunk includes whatever bytes sit **before** its own ``ISA`` too -- back to
wherever the previous chunk ended (or the start of the file, for the first
one) -- rather than starting exactly at ``ISA`` and silently dropping them.
That is deliberate: those bytes are handed to the normal single-interchange
pipeline next (see :mod:`x12_tidy.envelope.tidy`), and it is
:func:`~x12_tidy.envelope.isa.extract_isa_line` that already knows how to
rediscover and report them as ``isa.leading-bytes`` -- this module does not
duplicate that judgement, it just avoids throwing the bytes away first. One
consequence: chunks are always contiguous and gap-free, so summing their
lengths always equals exactly how far into ``dirty`` this function got.
"""

from __future__ import annotations

from x12_tidy.envelope.isa import (
    IsaCandidateAttempt,
    decode_utf16,
    split_isa_line,
    try_isa_candidate,
)

#: Bytes trimmed from the front of every segment before checking its
#: identifier -- matches segments.py's own leading-whitespace tolerance.
_WHITESPACE = b" \t\n\r\x0b\x0c"

#: The uppercase-only identifier this module searches for -- see
#: _next_isa_candidate's docstring on why lowercase isn't handled here.
ISA_IDENTIFIER = b"ISA"


def split_interchanges(dirty: bytes) -> list[bytes]:
    """Return ``dirty`` split into one bytes-slice per interchange. See the
    module docstring for exactly where each slice starts and ends.

    Purely mechanical, like :func:`~x12_tidy.envelope.structure.segments.split_segments`:
    no diagnostics, no validation, no refusal. An input with no recoverable
    ``ISA`` at all -- including an empty one -- returns ``[]``; the caller
    (:func:`x12_tidy.envelope.tidy.tidy`) is what turns that into a reported
    finding, the same way :func:`~x12_tidy.envelope.structure.clean_payload`
    already does for a single interchange.

    Deliberately does **not** use :func:`~x12_tidy.envelope.isa.extract_isa_line`'s
    own multi-candidate retry to find each interchange's ``ISA``: that retry
    is built to skip genuine leading junk (a BOM, an email header) ahead of a
    *single* interchange by trying candidates until one succeeds -- which
    would just as happily skip straight past an entire real-but-broken
    interchange (a well-formed ``ISA`` with no ``GS`` after it, say) and
    silently fold it into the *next* interchange's ``isa.leading-bytes``,
    discarding it as if it were never there. This walks candidates itself
    with :func:`~x12_tidy.envelope.isa.try_isa_candidate` (no retry) instead,
    stopping at the first one whose structure is confirmed (16 real element
    separators found, whether or not a ``GS`` then turns up) rather than the
    first one that fully succeeds -- see :func:`_next_isa_candidate`.
    """
    dirty = decode_utf16(dirty) or dirty  # transcode once; everything below
    # indexes this (possibly transcoded) buffer consistently, the same way
    # split_segments does for a single interchange.
    chunks: list[bytes] = []
    offset = 0
    while offset < len(dirty):
        found = _next_isa_candidate(dirty, offset)
        if found is None:
            break
        isa_start, attempt = found

        if attempt.isa_line is not None:
            body_start = isa_start + len(attempt.isa_line)
            end = _find_own_iea_end(dirty, body_start, attempt.isa_line)
        else:
            # Confirmed ISA structure, but no GS ever followed -- there is no
            # "body" to search for an IEA in at all. This interchange is
            # broken from the very first segment; bound it the same way as
            # "found IEA-searching but never found one": by the next real
            # ISA, or the end of the input.
            end = None

        if end is None:
            next_found = _next_isa_candidate(dirty, isa_start + len(ISA_IDENTIFIER))
            end = next_found[0] if next_found is not None else len(dirty)

        # Include any junk between offset and isa_start in this chunk rather
        # than dropping it -- running the normal pipeline on this chunk lets
        # extract_isa_line rediscover and report it as isa.leading-bytes,
        # exactly as it would for a single-interchange file. Chunks stay
        # contiguous this way: chunk i's length is exactly how far offset
        # advances, with no gap and no overlap.
        chunks.append(dirty[offset:end])
        offset = end

    return chunks


def _next_isa_candidate(
    dirty: bytes, offset: int
) -> tuple[int, IsaCandidateAttempt] | None:
    """The first ``ISA`` candidate from ``offset`` onward that is either a
    genuine success or a *confirmed-structure* failure (see
    :class:`~x12_tidy.envelope.isa.IsaCandidateAttempt`) -- skipping only
    candidates weak enough to be coincidental junk. Returns ``None`` if
    nothing in the rest of ``dirty`` even starts with ``ISA``.

    Uppercase ``ISA`` only, unlike :func:`~x12_tidy.envelope.isa.extract_isa_line`
    -- a lowercase identifier for anything but the very first (or last, via
    :mod:`x12_tidy.envelope.tidy`'s own fallback) interchange in a batch is
    not yet handled; see the module docstring.
    """
    at = dirty.find(ISA_IDENTIFIER, offset)
    while at != -1:
        attempt = try_isa_candidate(dirty, at)
        if attempt.isa_line is not None or attempt.confirmed_structure:
            return at, attempt
        at = dirty.find(ISA_IDENTIFIER, at + 1)
    return None


def _find_own_iea_end(dirty: bytes, body_start: int, isa_line: bytes) -> int | None:
    """Byte offset in ``dirty``, right after the first ``IEA`` segment's own
    terminator, searching forward from ``body_start`` -- but only through
    segments that still belong to *this* interchange. A new ``ISA`` turning
    up first means this interchange never closed; that is not this
    interchange's ``IEA``, and is reported ``None`` the same as never finding
    one at all. Delimiters are recovered from ``isa_line`` alone -- never
    borrowed from any other interchange."""
    decomposition = split_isa_line(isa_line)
    terminator = decomposition.segment_terminator
    element_separator = decomposition.element_separator
    if not terminator:
        return None

    pos = body_start
    while True:
        term_pos = dirty.find(terminator, pos)
        if term_pos == -1:
            return None
        identifier = dirty[pos:term_pos].lstrip(_WHITESPACE).split(
            element_separator, 1
        )[0]
        pos = term_pos + len(terminator)
        if identifier == b"IEA":
            return pos
        if identifier == b"ISA":
            return None
