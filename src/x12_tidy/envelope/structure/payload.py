# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Assemble the cleansed payload -- the whole-file counterpart to
:func:`x12_tidy.envelope.isa.clean_isa_line`.

Scope: **assembly only**. This cleans the ISA line, splits the rest into
segments, drops the empty pieces, and glues everything back together on the
sender's own segment terminator. It does not repair a body segment, check that
a segment identifier is a real identifier, or validate envelope/control-number consistency
(``GS``/``ST`` nesting, counts, ``IEA02`` vs ``ISA13``) -- that is QA/QC, which
runs after this, once there is a clean payload to run it against.

:func:`clean_payload` refuses exactly when :func:`~x12_tidy.envelope.isa.clean_isa_line`
does: no payload, only the propagated diagnostics that say why. A file whose
ISA line cannot be recovered has nothing to split or rejoin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic
from x12_tidy.envelope.isa import ReconstructedIsaLine, clean_isa_line, decode_utf16
from x12_tidy.envelope.structure.segments import drop_null_rows, split_segments


@dataclass
class ReconstructedPayload:
    """The cleansed whole-file bytes, or ``None`` when the ISA line could not
    be recovered.

    ``isa_result`` is the full :class:`~x12_tidy.envelope.isa.ReconstructedIsaLine` this
    was built from -- delimiters, the reconstructed ISA line, and every
    ISA-phase diagnostic. ``segments`` is the cleaned body (empty pieces
    dropped), in order, byte-for-byte what
    :func:`~x12_tidy.envelope.structure.split_segments` returned -- no per-segment
    repair happens here. Empty (``()``) on refusal.

    ``diagnostics`` is the ISA-phase diagnostics; ``split_segments`` and
    ``drop_null_rows`` are purely mechanical and emit none today.
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
    isa_result = clean_isa_line(dirty)  # detects + transcodes UTF-16 itself,
    # emitting isa.identifier-utf16 -- dirty must stay untranscoded going in,
    # or that diagnostic never fires.
    if isa_result.isa_line is None:
        return ReconstructedPayload(None, isa_result, (), list(isa_result.diagnostics))

    # clean_isa_line already determined whether dirty is UTF-16. If it isn't,
    # split_segments needs no transcoding at all -- skip calling decode_utf16
    # a second time on every ordinary (non-UTF-16) file. Only the rare UTF-16
    # case pays for a second transcode; ReconstructedIsaLine has nowhere to
    # carry the whole transcoded buffer forward for reuse today.
    was_utf16 = any(
        d.code == Code.ISA_IDENTIFIER_UTF16 for d in isa_result.diagnostics
    )
    body_source = (decode_utf16(dirty) or dirty) if was_utf16 else dirty
    segments = tuple(drop_null_rows(split_segments(body_source)))
    terminator = isa_result.segment_terminator
    body = b"".join(segment + terminator for segment in segments)
    payload = isa_result.isa_line + terminator + body

    return ReconstructedPayload(
        payload, isa_result, segments, list(isa_result.diagnostics)
    )
