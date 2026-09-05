# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Envelope QA/QC -- ``check_payload`` and ``tidy``.

Covers only the decided checks: envelope pairing (GS/GE, ST/SE, ISA/IEA),
control-number and count agreement, control-number uniqueness, the A5
identifier-shape gate, ISA12/GS08 version agreement, ISA15 validity, and GS07
validity. Rows without a decision (ISA05/07, ISA14, GS01, ST01 shape,
date/time format) are deliberately not tested here because they are not
built.
"""

from __future__ import annotations

from _isa_helpers import build_isa
from x12_tidy.diagnostics import Code
from x12_tidy.qaqc import check_payload
from x12_tidy.structure import clean_payload
from x12_tidy.tidy import tidy

# A hand-verified fully-correct interchange: one functional group, one
# transaction set, three segments in it (ST, BEG, SE -- SE01 counts SE itself).
_CLEAN_TRAILER = (
    b"GS*PO*SENDERGS*RECEIVERID*20240101*1200*1*X*004010~"
    b"ST*850*0001~BEG*00*NE*PO0001**20240101~SE*3*0001~"
    b"GE*1*1~IEA*1*000000001~"
)


def _codes(diagnostics) -> list[Code]:
    return [d.code for d in diagnostics]


def test_fully_correct_interchange_has_no_findings() -> None:
    result = check_payload(clean_payload(build_isa(trailer=_CLEAN_TRAILER)))
    assert result.diagnostics == []
    assert result.was_clean


def test_facts_are_extracted_regardless_of_validity() -> None:
    result = check_payload(clean_payload(build_isa(trailer=_CLEAN_TRAILER)))
    facts = result.facts
    assert facts is not None
    assert facts.sender_id.strip() == b"SENDER"
    assert facts.receiver_id.strip() == b"RECEIVER"
    assert facts.usage_indicator == b"P"
    assert facts.interchange_version == b"00401"
    assert facts.group_versions == (b"004010",)
    assert facts.functional_group_count == 1
    assert facts.transaction_set_count == 1
    assert facts.segment_count == 6  # GS,ST,BEG,SE,GE,IEA


def test_missing_iea() -> None:
    trailer = b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*1~SE*2*1~GE*1*1~"
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_MISSING_IEA in _codes(result.diagnostics)


def test_isa13_iea02_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"IEA*1*000000001", b"IEA*1*000000002")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_CONTROL_NUMBER_MISMATCH in _codes(result.diagnostics)


def test_functional_group_count_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"IEA*1*000000001", b"IEA*2*000000001")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert (
        Code.STRUCTURE_FUNCTIONAL_GROUP_COUNT_MISMATCH in _codes(result.diagnostics)
    )


def test_isa13_not_numeric() -> None:
    from _isa_helpers import ISA_ELEMENTS

    els = list(ISA_ELEMENTS)
    els[12] = b"ABC000001"
    trailer = _CLEAN_TRAILER.replace(b"000000001", b"ABC000001")
    result = check_payload(clean_payload(build_isa(elements=els, trailer=trailer)))
    assert Code.STRUCTURE_CONTROL_NUMBER_NOT_NUMERIC in _codes(result.diagnostics)


def test_missing_ge() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*1~SE*1*1~"
        b"IEA*1*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_MISSING_GE in _codes(result.diagnostics)


def test_gs06_ge02_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"GE*1*1~", b"GE*1*2~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_CONTROL_NUMBER_MISMATCH in _codes(result.diagnostics)


def test_transaction_set_count_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"GE*1*1~", b"GE*2*1~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_TRANSACTION_SET_COUNT_MISMATCH in _codes(result.diagnostics)


def test_gs06_not_numeric() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*ABC*X*004010~ST*850*0001~"
        b"BEG*00*NE*PO0001**20240101~SE*3*0001~GE*1*ABC~IEA*1*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_CONTROL_NUMBER_NOT_NUMERIC in _codes(result.diagnostics)


def test_gs06_duplicate_across_groups() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0001~"
        b"BEG*00*NE*PO0001**20240101~SE*3*0001~GE*1*1~"
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*0002~"
        b"BEG*00*NE*PO0002**20240101~SE*3*0002~GE*1*1~"
        b"IEA*2*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_CONTROL_NUMBER_DUPLICATE in _codes(result.diagnostics)


def test_missing_se() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*1~GE*0*1~"
        b"IEA*1*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.ST_MISSING_SE in _codes(result.diagnostics)


def test_st02_se02_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"SE*3*0001~", b"SE*3*9999~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.ST_CONTROL_NUMBER_MISMATCH in _codes(result.diagnostics)


def test_segment_count_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"SE*3*0001~", b"SE*99*0001~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.ST_SEGMENT_COUNT_MISMATCH in _codes(result.diagnostics)


def test_se01_not_numeric() -> None:
    trailer = _CLEAN_TRAILER.replace(b"SE*3*0001~", b"SE*THREE*0001~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.ST_COUNT_NOT_NUMERIC in _codes(result.diagnostics)


def test_st02_duplicate_within_group() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~"
        b"ST*850*0001~BEG*00*NE*PO0001**20240101~SE*3*0001~"
        b"ST*850*0001~BEG*00*NE*PO0002**20240101~SE*3*0001~"
        b"GE*2*1~IEA*1*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.ST_CONTROL_NUMBER_DUPLICATE in _codes(result.diagnostics)


def test_tag_shape_invalid() -> None:
    trailer = _CLEAN_TRAILER.replace(
        b"BEG*00*NE*PO0001**20240101~", b"beg*00*NE*PO0001**20240101~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_IDENTIFIER_INVALID in _codes(result.diagnostics)


def test_foreign_content_after_iea() -> None:
    # Content before the first GS can never reach QA/QC: extract_isa_line
    # defines the ISA line as ending immediately before GS, so anything
    # between them is consumed and reported by the ISA phase itself (either
    # isa.trailing-junk, or a fatal isa.no-functional-group refusal if it
    # disturbs the 16-separator count) -- it never becomes a body segment.
    # Content after IEA has no such owner, so it is the reachable case of
    # "structurally outside any envelope."
    trailer = _CLEAN_TRAILER + b"XX*JUNK~"
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_FOREIGN_CONTENT in _codes(result.diagnostics)


def test_duplicate_iea_is_foreign_content() -> None:
    # Two IEAs -- e.g. two interchanges' trailers accidentally concatenated,
    # or a sender bug that double-emits the trailer -- must not silently pass
    # as clean just because the second one happens to repeat the same numbers.
    trailer = _CLEAN_TRAILER + b"IEA*1*000000001~"
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_FOREIGN_CONTENT in _codes(result.diagnostics)
    # The real IEA's numbers still check out against the real counts.
    assert Code.STRUCTURE_CONTROL_NUMBER_MISMATCH not in _codes(result.diagnostics)
    assert (
        Code.STRUCTURE_FUNCTIONAL_GROUP_COUNT_MISMATCH
        not in _codes(result.diagnostics)
    )


def test_body_segment_outside_any_transaction_set_is_foreign_content() -> None:
    trailer = (
        b"GS*PO*A*B*20240101*1200*1*X*004010~REF*ZZ*STRAY~"
        b"ST*850*1~SE*1*1~GE*1*1~IEA*1*000000001~"
    )
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.STRUCTURE_FOREIGN_CONTENT in _codes(result.diagnostics)


def test_version_mismatch() -> None:
    trailer = _CLEAN_TRAILER.replace(b"004010", b"005010")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_VERSION_MISMATCH in _codes(result.diagnostics)


def test_version_match_tolerates_leading_zero_drop() -> None:
    # ISA12="00401" -> stripped "401"; GS08="4010" (no leading zeros) should
    # still match, per the real-world convention decision.
    trailer = _CLEAN_TRAILER.replace(b"*004010~", b"*4010~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_VERSION_MISMATCH not in _codes(result.diagnostics)


def test_version_match_ignores_industry_suffix() -> None:
    trailer = _CLEAN_TRAILER.replace(b"*004010~", b"*005010X222A1~")
    # ISA12 stays "00401" (from build_isa's default elements) -- mismatched on
    # purpose here since the suffix doesn't change the version itself.
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_VERSION_MISMATCH in _codes(result.diagnostics)


def test_version_check_runs_regardless_of_gs07() -> None:
    trailer = _CLEAN_TRAILER.replace(b"*X*004010~", b"*T*005010~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_VERSION_MISMATCH in _codes(result.diagnostics)


def test_gs07_invalid() -> None:
    trailer = _CLEAN_TRAILER.replace(b"*X*004010~", b"*Q*004010~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_RESPONSIBLE_AGENCY_INVALID in _codes(result.diagnostics)


def test_gs07_t_is_valid() -> None:
    trailer = _CLEAN_TRAILER.replace(b"*X*004010~", b"*T*004010~")
    result = check_payload(clean_payload(build_isa(trailer=trailer)))
    assert Code.GS_RESPONSIBLE_AGENCY_INVALID not in _codes(result.diagnostics)


def test_usage_indicator_invalid() -> None:
    from _isa_helpers import ISA_ELEMENTS

    els = list(ISA_ELEMENTS)
    els[14] = b"X"
    result = check_payload(
        clean_payload(build_isa(elements=els, trailer=_CLEAN_TRAILER))
    )
    assert Code.ISA_USAGE_INDICATOR_INVALID in _codes(result.diagnostics)


def test_usage_indicator_valid_values_are_not_flagged() -> None:
    from _isa_helpers import ISA_ELEMENTS

    for value in (b"T", b"P", b"I"):
        els = list(ISA_ELEMENTS)
        els[14] = value
        result = check_payload(
            clean_payload(build_isa(elements=els, trailer=_CLEAN_TRAILER))
        )
        assert Code.ISA_USAGE_INDICATOR_INVALID not in _codes(result.diagnostics)


def test_check_payload_on_refused_cleanse_returns_empty_result() -> None:
    result = check_payload(clean_payload(b"not an edi file"))
    assert result.facts is None
    assert result.diagnostics == []


def test_tidy_returns_payload_facts_and_all_diagnostics() -> None:
    result = tidy(build_isa(trailer=_CLEAN_TRAILER))
    assert result.payload is not None
    assert result.facts is not None
    assert result.was_clean


def test_tidy_refuses_cleanly_when_uncleansable() -> None:
    result = tidy(b"not an edi file at all")
    assert result.payload is None
    assert result.facts is None
    assert result.diagnostics  # a refusal must say why
