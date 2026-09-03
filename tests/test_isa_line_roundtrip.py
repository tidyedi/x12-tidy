# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Corpus round-trip: for *every* input, one of two clean outcomes holds.

The claim under test (see the ISA-line design note):

    For any bytes, ``extract_isa_line`` + ``split_isa_line`` either

    (A) **refuse cleanly** -- return no ISA line / ``not usable``, with at least
        one diagnostic that resolves to ``fatal``; or

    (B) **fully account for the ISA line** -- return the run from ``ISA`` to
        just before ``GS``, plus four well-formed delimiters, such that the run
        splits into exactly 16 elements on the element separator and re-joining
        them reproduces the run byte-for-byte (a lossless decomposition).

There is no third outcome: no silent wrong answer, no partial parse, no crash.

This is *not* the canonical-reconstruction round trip (pad to fixed widths,
re-parse to zero diagnostics) -- that lives in ``test_reconstruct.py``. It is
the decomposition round trip: whatever we hand back is a complete, reversible
account of the bytes we were given.
"""

from __future__ import annotations

import pytest

from _isa_helpers import ISA_ELEMENTS, build_isa
from test_isa_line import CASES as _EXTRACT_CASES
from x12_tidy.diagnostics import resolved_severity
from x12_tidy.isa import extract_isa_line, split_isa_line


def _elements(**overrides: bytes) -> list[bytes]:
    els = list(ISA_ELEMENTS)
    for name, value in overrides.items():
        els[int(name.removeprefix("isa")) - 1] = value
    return els


# The corpus: every Step 1 case, every delimiter-deviation build, the
# "carriage return anywhere" cases, plus truncation and byte-mutation fuzz.
_CORPUS: list[tuple[str, bytes]] = [
    *((n, d) for n, d, _codes, _line in _EXTRACT_CASES),
    # delimiter deviations exercised in test_delimiters.py
    ("pipe sep, LF term", build_isa(sep=b"|", term=b"\n")),
    ("~CRLF term", build_isa(term=b"~\r\n")),
    ("bare CRLF term", build_isa(term=b"\r\n")),
    ("stray space before GS", build_isa(term=b"~ ")),
    ("alnum element sep", build_isa(sep=b"7")),
    ("stripped terminator", build_isa(comp=b":", term=b"")),
    ("terminator == component sep", build_isa(comp=b":", term=b":")),
    ("rep sep on 00501", build_isa(elements=_elements(isa11=b"^", isa12=b"00501"))),
    ("rep sep missing on 00501",
     build_isa(elements=_elements(isa11=b"U", isa12=b"00501"))),
    ("alnum rep sep on 00501",
     build_isa(elements=_elements(isa11=b"R", isa12=b"00501"))),
    ("ISA11 not U on 00401",
     build_isa(elements=_elements(isa11=b"X", isa12=b"00401"))),
    ("unrecognised version", build_isa(elements=_elements(isa12=b"BOGUS"))),
    ("00402 has no rep sep",
     build_isa(elements=_elements(isa11=b"U", isa12=b"00402"))),
    # carriage return *anywhere* in the ISA line -- the point is location-agnostic
    ("CR inside ISA06 value",
     build_isa(elements=_elements(isa6=b"SENDER".ljust(15) + b"\r\n"))),
    ("CR inside ISA02 padding",
     build_isa(elements=_elements(isa2=b"  \r\n      "))),
    ("CR inside ISA15 value",
     build_isa(elements=_elements(isa15=b"P\r\n"))),
]

# truncation fuzz: cut the conformant interchange at every 5th byte
_conformant = build_isa()
for _cut in range(0, len(_conformant), 5):
    _CORPUS.append((f"truncated@{_cut}", _conformant[:_cut]))

# byte-mutation fuzz: flip one byte in the ISA line region, deterministic sweep
for _pos in range(0, 106, 3):
    _mut = bytearray(_conformant)
    _mut[_pos] ^= 0x20
    _CORPUS.append((f"mutate@{_pos}", bytes(_mut)))


def _has_fatal(diags: object) -> bool:
    return any(resolved_severity(d.code) == "fatal" for d in diags)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "dirty", [pytest.param(d, id=n) for n, d in _CORPUS]
)
def test_clean_refusal_or_lossless_account(dirty: bytes) -> None:
    result = extract_isa_line(dirty)

    # --- outcome (A): Step 1 refused ---
    if result.isa_line is None:
        assert result.diagnostics, "a refusal must say why"
        assert _has_fatal(result.diagnostics), "a refusal must be fatal"
        return

    # Step 1 returned a run -- the locating contract must hold
    run = result.isa_line
    cleansed = dirty[result.isa_start:]
    assert run[:3].upper() == b"ISA"
    assert cleansed.startswith(run)
    assert cleansed[len(run):][:2].upper() == b"GS"

    delimiters = split_isa_line(run, base_offset=result.isa_start)

    # --- outcome (A): Step 2 refused ---
    if not delimiters.usable:
        assert _has_fatal(delimiters.diagnostics), "an unusable result must be fatal"
        return

    # --- outcome (B): a complete, reversible account of the run ---
    assert len(delimiters.element_separator) == 1
    assert len(delimiters.component_separator) == 1
    assert len(delimiters.segment_terminator) == 1
    assert (
        delimiters.repetition_separator is None
        or len(delimiters.repetition_separator) == 1
    )

    parts = run.split(delimiters.element_separator)
    assert len(parts) == 17, "exactly ISA + ISA01..ISA16"
    assert parts[0].upper() == b"ISA"

    # the decomposition is lossless: elements re-joined on the element separator
    # reproduce the run byte-for-byte
    assert delimiters.element_separator.join(parts) == run

    # the recovered delimiters really are the bytes at their structural spots
    assert run[3:4] == delimiters.element_separator
    last = parts[16]
    assert last[0:1] == delimiters.component_separator
    tail = last[1:]
    if tail:  # terminator present in the bytes (not reconstructed from nothing)
        assert tail[0:1] == delimiters.segment_terminator
        assert tail[1:] == delimiters.trailing
