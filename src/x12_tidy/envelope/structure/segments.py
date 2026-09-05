# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Split an interchange into its raw segments.

A mechanical transform, nothing more. Given the raw bytes of an X12
interchange:

1. locate the ISA line and recover the segment terminator (via
   :mod:`x12_tidy.envelope.isa`);
2. take everything from the ``GS`` functional-group header onward;
3. ``strip`` whitespace **and the segment terminator** from the ends -- this
   drops any trailing whitespace after the final ``IEA`` segment and the
   terminator that closes it, so the split does not leave a trailing empty
   piece. There is nothing to strip from the front: it starts at ``GS``;
4. split on the segment terminator;
5. left-trim whitespace from each piece.

The result is the list of segment byte strings, in order, unchanged except for
the leading whitespace removed in step 5. A segment identifier is alphabetic and comes
first, so leading whitespace is never segment content -- ``lstrip`` cannot reach
a delimiter or an element value. The split is on the *segment terminator* only;
the element separator is never touched, so unused elements (``**``) stay inside
their segment exactly as sent.

:func:`split_segments` keeps the empty pieces that two terminators in a row
produce -- the split faithfully reflects what was sent. :func:`drop_empty_segments`
is the next step: an empty piece is not a segment, so it comes out. QA/QC, which
runs after reconstruction, is where anything is judged. Nothing here raises a
diagnostic, validates, or refuses.

If the ISA line or the segment terminator cannot be recovered, the interchange
cannot be split and the result is an empty list. The reason is on the ISA-phase
diagnostics, which a caller gets from :func:`x12_tidy.envelope.isa.clean_isa_line`.
"""

from __future__ import annotations

from x12_tidy.envelope.isa import extract_isa_line, split_isa_line

#: Bytes trimmed from the front of every segment -- the ASCII whitespace set,
#: matching ``bytes.strip()`` / ``bytes.lstrip()`` with no argument.
_WHITESPACE = b" \t\n\r\x0b\x0c"


def split_segments(dirty: bytes) -> list[bytes]:
    """Return the raw segments of ``dirty`` -- see the module docstring."""
    located = extract_isa_line(dirty)
    if located.isa_line is None:
        return []

    decomposition = split_isa_line(located.isa_line, base_offset=located.isa_start)
    terminator = decomposition.segment_terminator
    if not terminator:
        return []

    contents = dirty[located.isa_start + len(located.isa_line):]
    contents = contents.strip(_WHITESPACE + terminator)
    return [piece.lstrip(_WHITESPACE) for piece in contents.split(terminator)]


def drop_empty_segments(segments: list[bytes]) -> list[bytes]:
    """Return ``segments`` without the empty entries.

    Two segment terminators in a row (``~~``) make :func:`split_segments` emit an
    empty piece -- a faithful record of what was sent, but not a segment. This
    drops them. Still mechanical: no diagnostic, no judgement about *why* the
    terminators were doubled -- that is QA/QC's, after reconstruction.
    """
    return [segment for segment in segments if segment]


def split_elements(segment: bytes, element_separator: bytes) -> list[bytes]:
    """Split one segment into its elements on ``element_separator``.

    ``segment.split(element_separator)[0]`` is the segment identifier; the rest are
    its elements, ISA-style numbering (index 1 is the first element after the
    identifier). Purely mechanical -- no diagnostic, no validation of the identifier or any
    element's content. QA/QC reads elements this way rather than re-splitting
    inline at every call site.
    """
    return segment.split(element_separator)
