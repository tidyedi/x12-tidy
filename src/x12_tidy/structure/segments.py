# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Split an interchange into its raw segments.

A mechanical transform, nothing more. Given the raw bytes of an X12
interchange:

1. locate the ISA line and recover the segment terminator (via
   :mod:`x12_tidy.isa`);
2. take everything from the ``GS`` functional-group header onward;
3. ``strip`` whitespace **and the segment terminator** from the ends -- this
   drops any trailing whitespace after the final ``IEA`` segment and the
   terminator that closes it, so the split does not leave a trailing empty
   piece. There is nothing to strip from the front: it starts at ``GS``;
4. split on the segment terminator;
5. left-trim whitespace from each piece.

The result is the list of segment byte strings, in order, unchanged except for
the leading whitespace removed in step 5. A segment tag is alphabetic and comes
first, so leading whitespace is never segment content -- ``lstrip`` cannot reach
a delimiter or an element value. The split is on the *segment terminator* only;
the element separator is never touched, so unused elements (``**``) stay inside
their segment exactly as sent.

Empty pieces from two terminators *in the body* are kept. Dropping them is a
later step (``[s for s in segments if s]``), and QA/QC, which runs after
reconstruction, is where anything is judged. This function raises no diagnostic,
validates nothing, and refuses nothing.

If the ISA line or the segment terminator cannot be recovered, the interchange
cannot be split and the result is an empty list. The reason is on the ISA-phase
diagnostics, which a caller gets from :func:`x12_tidy.isa.clean_isa_line`.
"""

from __future__ import annotations

from x12_tidy.isa import extract_isa_line, split_isa_line

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
