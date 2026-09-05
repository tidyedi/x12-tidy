# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Step 2, slice 2 -- reconstruct the canonical ISA line.

Two things are checked:

* **per-case behaviour** -- the right repair or the right refusal for one
  deviation at a time;
* **the round trip** -- for every non-terminal corpus input, reconstructing and
  then re-parsing the reconstruction yields *zero* diagnostics, and a second
  reconstruction is byte-identical (idempotence). This is what makes "clean" a
  testable property rather than a flag.
"""

from __future__ import annotations

import pytest

from _isa_helpers import ISA_ELEMENTS, build_isa
from test_isa_line_roundtrip import _CORPUS
from x12_tidy.diagnostics import Code
from x12_tidy.envelope.isa import (
    ReconstructedIsaLine,
    clean_isa_line,
    extract_isa_line,
    reconstruct_isa_line,
    split_isa_line,
)
from x12_tidy.envelope.isa.reconstruct import CANONICAL_LENGTH, ISA_ELEMENT_WIDTHS


def _elements(**overrides: bytes) -> list[bytes]:
    els = list(ISA_ELEMENTS)
    for name, value in overrides.items():
        els[int(name.removeprefix("isa")) - 1] = value
    return els


def _codes(result: ReconstructedIsaLine) -> list[Code]:
    return [d.code for d in result.diagnostics]


def _wrap(line: bytes, element_separator: bytes, terminator: bytes = b"~") -> bytes:
    """A whole interchange around a reconstructed ISA line, so the reconstruction
    can be fed back through the front of the pipeline. ``terminator`` is the byte
    the ISA line is joined to GS with -- reconstruction preserves the sender's,
    so the round trip must re-wrap with the same one."""
    s = element_separator
    trailer = (
        b"GS" + s + b"PO" + s + b"A" + s + b"B" + s + b"20240101" + s
        + b"1200" + s + b"1" + s + b"X" + s + b"004010~"
        + b"ST" + s + b"850" + s + b"1~SE" + s + b"1" + s + b"1~"
        + b"GE" + s + b"1" + s + b"1~IEA" + s + b"1" + s + b"1~"
    )
    return line + terminator + trailer


# --------------------------------------------------------------------------
# the widths constant is the standard
# --------------------------------------------------------------------------

def test_widths_sum_to_the_canonical_line() -> None:
    # "ISA" (3) + 16 element separators + sum(widths) == 105
    assert 3 + 16 + sum(ISA_ELEMENT_WIDTHS) == CANONICAL_LENGTH
    assert len(ISA_ELEMENT_WIDTHS) == 16


# --------------------------------------------------------------------------
# per-case behaviour
# --------------------------------------------------------------------------

def test_conformant_input_is_returned_unchanged_and_clean() -> None:
    dirty = build_isa()
    result = clean_isa_line(dirty)
    assert result.was_clean
    assert result.isa_line == dirty[: CANONICAL_LENGTH]
    assert result.segment_terminator == b"~"
    assert len(result.elements) == 16


def test_trimmed_blank_fields_are_padded_back() -> None:
    # ISA01/ISA03 are "00", so ISA02/ISA04 are all spaces -- a sender trimmed
    # them to empty. Fixed-offset parsers die here; we pad them back.
    result = clean_isa_line(build_isa(elements=_elements(isa2=b"", isa4=b"")))
    assert result.isa_line is not None
    assert len(result.isa_line) == CANONICAL_LENGTH
    assert _codes(result) == [Code.ISA_ELEMENT_WIDTH, Code.ISA_ELEMENT_WIDTH]
    assert result.elements[1] == b" " * 10
    assert result.elements[3] == b" " * 10


def test_over_padded_field_is_trimmed() -> None:
    result = clean_isa_line(
        build_isa(elements=_elements(isa6=b"SENDER".ljust(25)))
    )
    assert result.isa_line is not None
    assert _codes(result) == [Code.ISA_ELEMENT_WIDTH]
    assert result.elements[5] == b"SENDER".ljust(15)


def test_hard_wrapped_element_newline_becomes_space_then_trims() -> None:
    result = clean_isa_line(
        build_isa(elements=_elements(isa6=b"SENDER".ljust(15) + b"\r\n"))
    )
    assert result.isa_line is not None
    assert Code.ISA_ELEMENT_EMBEDDED_NEWLINE in _codes(result)
    assert result.elements[5] == b"SENDER".ljust(15)


def test_real_data_past_the_fixed_width_is_fatal() -> None:
    # 17 real characters in ISA06's 15-byte field: intent unknowable.
    result = clean_isa_line(
        build_isa(elements=_elements(isa6=b"ACMEWIDGETSCORP01"))
    )
    assert result.isa_line is None
    assert _codes(result) == [Code.ISA_ELEMENT_OVERFLOW]


def test_noncanonical_terminator_is_preserved_not_normalised() -> None:
    # The sender chose "\n" to end segments -- a legal choice. Reconstruction
    # keeps it; it is flagged (a warning) because "~" is the convention.
    result = clean_isa_line(build_isa(term=b"\n"))
    assert result.isa_line is not None
    assert result.segment_terminator == b"\n"
    assert Code.ISA_SEGMENT_TERMINATOR_NONCANONICAL in _codes(result)


def test_stripped_terminator_is_supplied_as_tilde() -> None:
    # Nothing to preserve: GS followed ISA16 directly.
    result = clean_isa_line(build_isa(comp=b":", term=b""))
    assert result.isa_line is not None
    assert result.segment_terminator == b"~"
    assert Code.ISA_SEGMENT_TERMINATOR_STRIPPED in _codes(result)


def test_sender_delimiters_are_kept() -> None:
    result = clean_isa_line(build_isa(sep=b"|", term=b"\n"))
    assert result.isa_line is not None
    assert result.decomposition.element_separator == b"|"
    assert result.segment_terminator == b"\n"
    assert result.isa_line.startswith(b"ISA|")


def test_repetition_separator_element_is_not_rewritten() -> None:
    # ISA11 carries the repetition separator on 00501; even if it were a line
    # break it must survive. Here it is "^" -- just assert it is preserved.
    result = clean_isa_line(
        build_isa(elements=_elements(isa11=b"^", isa12=b"00501"))
    )
    assert result.isa_line is not None
    assert result.decomposition.repetition_separator == b"^"
    assert result.elements[10] == b"^"


def test_internal_spaces_in_an_element_are_preserved() -> None:
    result = clean_isa_line(
        build_isa(elements=_elements(isa6=b"AB CD".ljust(15)))
    )
    assert result.isa_line is not None
    assert result.elements[5] == b"AB CD".ljust(15)  # inner space kept, not collapsed


def test_reconstruct_isa_line_direct_entry() -> None:
    located = extract_isa_line(build_isa(elements=_elements(isa2=b"", isa4=b"")))
    assert located.isa_line is not None
    decomposition = split_isa_line(located.isa_line, base_offset=located.isa_start)

    result = reconstruct_isa_line(decomposition, base_offset=located.isa_start)
    assert result.isa_line is not None
    assert len(result.isa_line) == CANONICAL_LENGTH
    assert result.decomposition is decomposition
    assert _codes(result) == [Code.ISA_ELEMENT_WIDTH, Code.ISA_ELEMENT_WIDTH]


def test_upstream_fatal_is_propagated_with_no_line() -> None:
    result = clean_isa_line(build_isa(sep=b"7"))
    assert result.isa_line is None
    assert Code.ISA_ELEMENT_SEPARATOR_INVALID in _codes(result)


def test_no_isa_tag_returns_none() -> None:
    result = clean_isa_line(b"GS*PO*A*B*20240101*1200*1*X*004010~" * 5)
    assert result.isa_line is None
    assert Code.ISA_NO_IDENTIFIER in _codes(result)


# --------------------------------------------------------------------------
# the round trip, across the corpus
# --------------------------------------------------------------------------

#: Codes this phase is responsible for -- structure, delimiters, junk. Once
#: reconstruction has run, none of these may reappear on a re-parse. Value-level
#: findings (is ISA12 a real version code, is ISA11 the standards identifier)
#: are out of scope and legitimately survive -- and so does
#: ``isa.segment-terminator-noncanonical``: the sender's terminator is
#: deliberately preserved, so re-parsing a "\n"-terminated interchange flags it
#: again. That is correct, not a lingering repair.
_RECONSTRUCTION_OWNS: frozenset[Code] = frozenset({
    Code.ISA_LEADING_BYTES,
    Code.ISA_IDENTIFIER_LOWERCASE,
    Code.ISA_TRAILING_NEWLINE,
    Code.ISA_TRAILING_JUNK,
    Code.ISA_SEGMENT_TERMINATOR_STRIPPED,
    Code.ISA_ELEMENT_EMBEDDED_NEWLINE,
    Code.ISA_ELEMENT_WIDTH,
})


@pytest.mark.parametrize("dirty", [pytest.param(d, id=n) for n, d in _CORPUS])
def test_reconstruction_round_trips(dirty: bytes) -> None:
    first = clean_isa_line(dirty)
    if first.isa_line is None:
        assert first.diagnostics  # a refusal must say why
        return

    assert len(first.isa_line) == CANONICAL_LENGTH

    # re-parse the reconstruction from the front of the pipeline, re-wrapped
    # with the terminator reconstruction preserved
    reparsed = clean_isa_line(
        _wrap(
            first.isa_line,
            first.decomposition.element_separator,
            first.segment_terminator,
        )
    )

    # the line is a fixed point: cleaning it again changes nothing
    assert reparsed.isa_line == first.isa_line
    assert reparsed.elements == first.elements

    # nothing this phase repairs is still outstanding
    lingering = _RECONSTRUCTION_OWNS.intersection(_codes(reparsed))
    assert not lingering, sorted(c.value for c in lingering)
