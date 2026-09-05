# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""``clean_payload`` -- assembly only.

Cleans the ISA line, splits and cleans the body, glues everything back
together on the sender's own terminator. Per-segment repair, identifier validation,
and envelope checks are QA/QC's job, after this -- these tests only pin the
assembly contract and the refusal.
"""

from __future__ import annotations

from _isa_helpers import ISA_ELEMENTS, build_isa
from x12_tidy.diagnostics import Code
from x12_tidy.envelope.structure import ReconstructedPayload, clean_payload


def _codes(result: ReconstructedPayload) -> list[Code]:
    return [d.code for d in result.diagnostics]


def test_clean_input_round_trips_byte_identical() -> None:
    dirty = build_isa()
    result = clean_payload(dirty)
    assert result.payload == dirty
    assert result.was_clean


def test_segments_field_excludes_empty_pieces() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0001~~"
        b"SE*2*0001~GE*1*1~IEA*1*000000001~"
    )
    dirty = build_isa(trailer=trailer)
    result = clean_payload(dirty)
    assert b"" not in result.segments


def test_double_terminator_collapses_to_one_on_reassembly() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0001~~"
        b"SE*2*0001~GE*1*1~IEA*1*000000001~"
    )
    dirty = build_isa(trailer=trailer)
    result = clean_payload(dirty)
    assert b"~~" not in result.payload
    assert result.payload == (
        result.isa_result.isa_line + b"~"
        + b"~".join(result.segments) + b"~"
    )


def test_non_standard_terminator_is_preserved_through_reassembly() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010\r"
        b"ST*850*0001\rSE*1*0001\rGE*1*1\rIEA*1*000000001\r"
    )
    dirty = build_isa(term=b"\r", trailer=trailer)
    result = clean_payload(dirty)
    assert result.payload == dirty
    assert result.isa_result.segment_terminator == b"\r"


def test_isa_line_repair_is_reflected_in_the_payload() -> None:
    # ISA05 ("ZZ") right-trimmed to one byte -- padded back on reconstruction.
    els = list(ISA_ELEMENTS)
    els[4] = b"Z"
    dirty = build_isa(elements=els)

    result = clean_payload(dirty)
    assert result.payload is not None
    assert Code.ISA_ELEMENT_WIDTH in _codes(result)
    assert not result.was_clean
    # the repaired ISA line, not the dirty one, anchors the payload
    assert result.payload.startswith(result.isa_result.isa_line)


def test_refuses_when_isa_line_cannot_be_recovered() -> None:
    result = clean_payload(b"this is not an edi file at all")
    assert result.payload is None
    assert result.segments == ()
    assert result.diagnostics  # a refusal must say why
    assert Code.ISA_NO_IDENTIFIER in _codes(result)


def test_refuses_on_empty_input() -> None:
    result = clean_payload(b"")
    assert result.payload is None
    assert result.segments == ()
    assert result.diagnostics
