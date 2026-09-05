# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Step 2, slice 1 -- ``split_isa_line`` recovers the delimiters from the run.

Two kinds of case:

* **pipeline** -- ``build_isa`` -> ``extract_isa_line`` -> ``split_isa_line``,
  the real path. Proves the delimiters come out of a run Step 1 actually
  returns, including from stripped and re-padded ISA lines.
* **direct** -- a hand-built run handed straight to ``split_isa_line``, for the
  structural failures (misaligned split, ISA16 absent, collisions) that Step 1's
  exactly-16 gate keeps from ever reaching it through the pipeline.
"""

from __future__ import annotations

import pytest

from _isa_helpers import ISA_ELEMENTS, build_isa
from x12_tidy.diagnostics import Code, resolved_severity
from x12_tidy.envelope.isa import extract_isa_line, split_isa_line


def run_of(**kwargs: object) -> bytes:
    """The ISA-line run Step 1 returns for ``build_isa(**kwargs)``."""
    result = extract_isa_line(build_isa(**kwargs))  # type: ignore[arg-type]
    assert result.isa_line is not None, result.diagnostics
    return result.isa_line


def elements_with(**overrides: bytes) -> list[bytes]:
    """A copy of ``ISA_ELEMENTS`` with named ISA elements replaced,
    e.g. ``elements_with(isa11=b"^", isa12=b"00501")``."""
    els = list(ISA_ELEMENTS)
    for name, value in overrides.items():
        els[int(name.removeprefix("isa")) - 1] = value
    return els


def codes(diags: object) -> list[Code]:
    return [d.code for d in diags]  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# the happy path
# --------------------------------------------------------------------------

def test_conformant_interchange_has_four_clean_delimiters() -> None:
    d = split_isa_line(run_of())
    assert d.element_separator == b"*"
    assert d.component_separator == b":"
    assert d.segment_terminator == b"~"
    assert d.repetition_separator is None  # ISA12 00401 predates it
    assert d.trailing == b""
    assert d.diagnostics == []
    assert d.usable


def test_repetition_separator_is_read_when_the_version_has_one() -> None:
    d = split_isa_line(run_of(elements=elements_with(isa11=b"^", isa12=b"00501")))
    assert d.repetition_separator == b"^"
    assert d.diagnostics == []
    assert d.usable


# --------------------------------------------------------------------------
# the whole point: length-independence
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    pytest.param({}, id="conformant"),
    pytest.param(
        {"elements": [b"00", b"", b"00", b"", b"ZZ", b"SENDER".ljust(15),
                      b"ZZ", b"RECEIVER".ljust(15), b"240101", b"1200", b"U",
                      b"00401", b"000000001", b"0", b"P"]},
        id="ISA02+ISA04 stripped (short line)",
    ),
    pytest.param(
        {"elements": [b"00", b" " * 10, b"00", b" " * 10, b"ZZ",
                      b"SENDER".ljust(25), b"ZZ", b"RECEIVER".ljust(15),
                      b"240101", b"1200", b"U", b"00401", b"000000001",
                      b"0", b"P"]},
        id="ISA06 padded wide (long line)",
    ),
])
def test_delimiters_are_independent_of_element_widths(kwargs: dict) -> None:
    d = split_isa_line(run_of(**kwargs))
    assert (d.element_separator, d.component_separator, d.segment_terminator) \
        == (b"*", b":", b"~")
    assert d.diagnostics == []


# --------------------------------------------------------------------------
# pipeline cases -- one deviation at a time
# --------------------------------------------------------------------------

def test_pipe_separator_and_lf_terminator() -> None:
    d = split_isa_line(run_of(sep=b"|", term=b"\n"))
    assert (d.element_separator, d.component_separator, d.segment_terminator) \
        == (b"|", b":", b"\n")
    assert codes(d.diagnostics) == [Code.ISA_SEGMENT_TERMINATOR_NONCANONICAL]
    assert d.usable  # a non-tilde terminator is a warning


def test_tilde_crlf_terminator_splits_deterministically() -> None:
    d = split_isa_line(run_of(term=b"~\r\n"))
    assert d.segment_terminator == b"~"
    assert d.trailing == b"\r\n"
    assert codes(d.diagnostics) == [Code.ISA_TRAILING_NEWLINE]
    assert d.usable


def test_bare_crlf_terminator_is_one_byte_by_rule() -> None:
    d = split_isa_line(run_of(term=b"\r\n"))
    # the 1-byte rule: \r is the terminator, \n falls to trailing
    assert d.segment_terminator == b"\r"
    assert d.trailing == b"\n"
    assert Code.ISA_SEGMENT_TERMINATOR_NONCANONICAL in codes(d.diagnostics)
    assert Code.ISA_TRAILING_NEWLINE in codes(d.diagnostics)
    assert d.usable


def test_stray_space_before_gs_is_junk() -> None:
    d = split_isa_line(run_of(term=b"~ "))
    assert d.segment_terminator == b"~"
    assert d.trailing == b" "
    assert codes(d.diagnostics) == [Code.ISA_TRAILING_JUNK]
    assert d.usable  # error, not fatal


def test_alphanumeric_element_separator_is_fatal() -> None:
    d = split_isa_line(run_of(sep=b"7"))
    assert d.element_separator == b"7"
    assert codes(d.diagnostics) == [Code.ISA_ELEMENT_SEPARATOR_INVALID]
    assert not d.usable


def test_stripped_segment_terminator_is_reconstructed() -> None:
    d = split_isa_line(run_of(comp=b":", term=b""))
    assert d.segment_terminator == b"~"
    assert codes(d.diagnostics) == [Code.ISA_SEGMENT_TERMINATOR_STRIPPED]
    assert d.usable


def test_terminator_equal_to_component_separator_is_fatal() -> None:
    d = split_isa_line(run_of(comp=b":", term=b":"))
    assert Code.ISA_DELIMITER_COLLISION in codes(d.diagnostics)
    assert not d.usable


# --------------------------------------------------------------------------
# ISA11 / ISA12 -- the repetition separator, version-gated at 00403
# --------------------------------------------------------------------------

def test_repetition_separator_missing_on_a_version_that_has_one() -> None:
    d = split_isa_line(run_of(elements=elements_with(isa11=b"U", isa12=b"00501")))
    assert d.repetition_separator is None
    assert codes(d.diagnostics) == [Code.ISA_REPETITION_SEPARATOR_MISSING]
    assert d.usable  # error -- body parser escalates iff a segment repeats


def test_alphanumeric_repetition_separator_is_error_not_fatal() -> None:
    d = split_isa_line(run_of(elements=elements_with(isa11=b"R", isa12=b"00501")))
    assert d.repetition_separator is None  # never hand back a garbage delimiter
    assert codes(d.diagnostics) == [Code.ISA_REPETITION_SEPARATOR_INVALID]
    assert d.usable  # error -- body parser escalates iff a segment repeats


def test_multibyte_isa11_is_reported_not_handed_back() -> None:
    # a dropped element separator lets ISA11 swallow the next field
    run = _run([b"x"] * 10 + [b"^GARBAGE", b"00501"] + [b"x"] * 3 + [b":~"])
    d = split_isa_line(run)
    assert d.repetition_separator is None
    assert Code.ISA_REPETITION_SEPARATOR_INVALID in codes(d.diagnostics)
    assert d.usable  # still only an error at this stage


def test_isa11_not_u_on_an_older_version_is_error() -> None:
    d = split_isa_line(run_of(elements=elements_with(isa11=b"X", isa12=b"00401")))
    assert d.repetition_separator is None
    assert codes(d.diagnostics) == [Code.ISA_ISA11_NOT_STANDARDS_ID]
    assert d.usable


def test_unrecognised_version_leaves_isa11_opaque() -> None:
    d = split_isa_line(run_of(elements=elements_with(isa11=b"^", isa12=b"BOGUS")))
    assert d.repetition_separator is None
    assert codes(d.diagnostics) == [Code.ISA_VERSION_UNRECOGNIZED]
    assert d.usable


def test_version_00402_has_no_repetition_separator() -> None:
    # ISA11 "U" is correct here; 004020 predates the repetition separator.
    d = split_isa_line(run_of(elements=elements_with(isa11=b"U", isa12=b"00402")))
    assert d.repetition_separator is None
    assert d.diagnostics == []


# --------------------------------------------------------------------------
# direct cases -- structural failures Step 1's gate hides from the pipeline
# --------------------------------------------------------------------------

def _run(elements: list[bytes]) -> bytes:
    """A bare ISA-line run: ``ISA`` + 15 elements + a 16th piece, on ``*``."""
    return b"*".join([b"ISA", *elements])


def test_isa16_absent_is_fatal() -> None:
    d = split_isa_line(run_of(comp=b"", term=b""))  # run ends at the 16th sep
    assert codes(d.diagnostics) == [Code.ISA_ISA16_MISSING]
    assert not d.usable


def test_split_landing_on_data_bytes_is_fatal() -> None:
    # 15 elements + a 16th piece that is two data bytes -> component sep and
    # terminator both land on alphanumerics.
    run = _run([b"x"] * 10 + [b"U", b"00401"] + [b"x"] * 3 + [b"AB"])
    d = split_isa_line(run)
    assert codes(d.diagnostics) == [Code.ISA_DELIMITER_MISALIGNED]
    assert not d.usable


def test_terminator_on_a_data_byte_is_fatal() -> None:
    run = _run([b"x"] * 10 + [b"U", b"00401"] + [b"x"] * 3 + [b":X"])
    d = split_isa_line(run)
    assert Code.ISA_SEGMENT_TERMINATOR_INVALID in codes(d.diagnostics)
    assert not d.usable


def test_wrong_element_count_is_fatal() -> None:
    run = _run([b"x"] * 5 + [b":~"])  # only 6 pieces after ISA, not 16
    d = split_isa_line(run)
    assert codes(d.diagnostics) == [Code.ISA_DELIMITER_MISALIGNED]
    assert not d.usable


def test_offsets_are_shifted_by_base_offset() -> None:
    run = run_of(sep=b"7")
    d = split_isa_line(run, base_offset=100)
    (bad,) = [x for x in d.diagnostics
              if x.code is Code.ISA_ELEMENT_SEPARATOR_INVALID]
    assert bad.offset == 103  # base_offset + 3


# --------------------------------------------------------------------------
# the severity rule is wired to the registry
# --------------------------------------------------------------------------

def test_fatal_and_conditional_codes_have_the_right_default_severity() -> None:
    fatal = [
        Code.ISA_ELEMENT_SEPARATOR_INVALID,
        Code.ISA_SEGMENT_TERMINATOR_INVALID,
        Code.ISA_DELIMITER_COLLISION,
        Code.ISA_DELIMITER_MISALIGNED,
        Code.ISA_ISA16_MISSING,
    ]
    conditional = [
        Code.ISA_COMPONENT_SEPARATOR_INVALID,
        Code.ISA_REPETITION_SEPARATOR_INVALID,
        Code.ISA_REPETITION_SEPARATOR_MISSING,
    ]
    assert all(resolved_severity(c) == "fatal" for c in fatal)
    assert all(resolved_severity(c) == "error" for c in conditional)
