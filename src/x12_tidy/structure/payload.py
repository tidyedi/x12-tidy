# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Assemble the cleansed payload -- the whole-file counterpart to
:func:`x12_tidy.isa.clean_isa_line`.

Scope: **assembly only**. This cleans the ISA line, splits the rest into
segments, drops the empty pieces, and glues everything back together on the
sender's own segment terminator. It does not repair a body segment, check that
a segment tag is a real tag, or validate envelope/control-number consistency
(``GS``/``ST`` nesting, counts, ``IEA02`` vs ``ISA13``) -- that is QA/QC, which
runs after this, once there is a clean payload to run it against.

:func:`clean_payload` refuses exactly when :func:`~x12_tidy.isa.clean_isa_line`
does: no payload, only the propagated diagnostics that say why. A file whose
ISA line cannot be recovered has nothing to split or rejoin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Diagnostic
from x12_tidy.isa import ReconstructedIsaLine, clean_isa_line
from x12_tidy.structure.segments import drop_empty_segments, split_segments


@dataclass
class ReconstructedPayload:
    """The cleansed whole-file bytes, or ``None`` when the ISA line could not
    be recovered.

    ``isa_result`` is the full :class:`~x12_tidy.isa.ReconstructedIsaLine` this
    was built from -- delimiters, the reconstructed ISA line, and every
    ISA-phase diagnostic. ``segments`` is the cleaned body (empty pieces
    dropped), in order, byte-for-byte what
    :func:`~x12_tidy.structure.split_segments` returned -- no per-segment
    repair happens here. Empty (``()``) on refusal.

    ``diagnostics`` is the ISA-phase diagnostics; ``split_segments`` and
    ``drop_empty_segments`` are purely mechanical and emit none today.
    """

    payload: bytes | None
    isa_result: ReconstructedIsaLine
    segments: tuple[bytes, ...]
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        """The input needed no repair and tripped no finding."""
        return not self.diagnostics


def clean_payload(dirty: bytes) -> ReconstructedPayload:
    """Clean the ISA line, split and clean the body, reassemble one payload.
    See the module docstring for scope and the refusal contract."""
    isa_result = clean_isa_line(dirty)
    if isa_result.isa_line is None:
        return ReconstructedPayload(None, isa_result, (), list(isa_result.diagnostics))

    segments = tuple(drop_empty_segments(split_segments(dirty)))
    terminator = isa_result.segment_terminator
    body = b"".join(segment + terminator for segment in segments)
    payload = isa_result.isa_line + terminator + body

    return ReconstructedPayload(
        payload, isa_result, segments, list(isa_result.diagnostics)
    )
