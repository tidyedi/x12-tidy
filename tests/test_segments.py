# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""``split_segments`` -- the mechanical interchange split.

The contract is deliberately small: split everything from ``GS`` onward on the
segment terminator, left-trim whitespace from each piece, return the list. No
diagnostics, no validation, no refusal. These tests pin exactly that and the
things it must *not* do -- never split on an element separator, never touch a
segment's right-hand side, never drop an empty piece.
"""

from __future__ import annotations

from _isa_helpers import build_isa
from x12_tidy.structure import split_segments

# The trailer baked into ``build_isa`` -- segments joined on "~", one unused
# element ("**") in the BEG segment. The terminator closing the final IEA is
# stripped before the split, so there is no trailing empty piece.
_CLEAN_SEGMENTS = [
    b"GS*PO*SENDERGS*RECEIVERID*20240101*1200*1*X*004010",
    b"ST*850*0001",
    b"BEG*00*NE*PO0001**20240101",
    b"SE*2*0001",
    b"GE*1*1",
    b"IEA*1*000000001",
]


def test_clean_interchange_splits_into_its_segments() -> None:
    assert split_segments(build_isa()) == _CLEAN_SEGMENTS


def test_unused_element_is_not_split() -> None:
    # "BEG*00*NE*PO0001**20240101" -- the "**" (BEG04 unused) must survive
    # intact; the split is on the terminator, never the element separator.
    segments = split_segments(build_isa())
    assert b"BEG*00*NE*PO0001**20240101" in segments


def test_newlines_between_segments_are_left_trimmed() -> None:
    raw = build_isa().replace(b"~", b"~\r\n")
    assert split_segments(raw) == _CLEAN_SEGMENTS


def test_indentation_between_segments_is_left_trimmed() -> None:
    raw = build_isa().replace(b"~", b"~\r\n\t   ")
    assert split_segments(raw) == _CLEAN_SEGMENTS


def test_trailing_whitespace_and_final_terminator_are_stripped() -> None:
    raw = build_isa() + b"\r\n\r\n   \t"
    # The trailing whitespace and the terminator closing IEA come off before
    # the split -- no trailing empty piece.
    assert split_segments(raw) == _CLEAN_SEGMENTS
    assert split_segments(raw)[-1] == b"IEA*1*000000001"


def test_right_hand_side_of_a_segment_is_never_touched() -> None:
    # A space-padded final element is real data -- only the front is trimmed.
    trailer = b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0001~REF*ZZ*VALUE   ~SE*3*0001~GE*1*1~IEA*1*000000001~"
    segments = split_segments(build_isa(trailer=trailer))
    assert b"REF*ZZ*VALUE   " in segments


def test_two_terminators_in_the_body_keep_the_empty_piece() -> None:
    trailer = b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0001~~SE*2*0001~GE*1*1~IEA*1*000000001~"
    segments = split_segments(build_isa(trailer=trailer))
    # the body "~~" leaves an empty piece; the terminator closing IEA does not
    assert segments == [
        b"GS*PO*A*B*20240101*1200*1*X*004010",
        b"ST*850*0001",
        b"",
        b"SE*2*0001",
        b"GE*1*1",
        b"IEA*1*000000001",
    ]


def test_leading_junk_before_isa_does_not_affect_the_body_split() -> None:
    assert split_segments(build_isa(pre=b"MAILER PREAMBLE\r\n")) == _CLEAN_SEGMENTS


def test_non_standard_terminator_is_what_the_split_uses() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010\r"
        b"ST*850*0001\rSE*1*0001\rGE*1*1\rIEA*1*000000001\r"
    )
    raw = build_isa(term=b"\r", trailer=trailer)
    assert split_segments(raw) == [
        b"GS*PO*A*B*20240101*1200*1*X*004010",
        b"ST*850*0001",
        b"SE*1*0001",
        b"GE*1*1",
        b"IEA*1*000000001",
    ]


def test_non_standard_element_separator_is_left_inside_the_segment() -> None:
    raw = build_isa(sep=b"|")
    segments = split_segments(raw)
    assert segments[0] == b"GS|PO|SENDERGS|RECEIVERID|20240101|1200|1|X|004010"
    assert segments[2] == b"BEG|00|NE|PO0001||20240101"


def test_not_an_interchange_returns_empty_list() -> None:
    assert split_segments(b"this is not an edi file at all") == []


def test_empty_input_returns_empty_list() -> None:
    assert split_segments(b"") == []
