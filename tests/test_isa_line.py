# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Step 1 -- ``extract_isa_line`` returns the ISA line.

Each case checks the diagnostic codes and, when a line is returned, the
contract: it starts with ``ISA``, is a prefix of ``dirty[isa_start:]``, and the
bytes right after it start with ``GS``.
"""

from __future__ import annotations

import pytest

from x12_tidy.diagnostics import Code
from x12_tidy.isa import IsaLineResult, extract_isa_line

# --- fixtures --------------------------------------------------------------

# 15 conformant ISA01..ISA15 values (ISA16, the component separator, is added
# by build_isa as the last field before the terminator).
ISA_ELEMENTS = [
    b"00", b" " * 10, b"00", b" " * 10, b"ZZ", b"SENDER".ljust(15),
    b"ZZ", b"RECEIVER".ljust(15), b"240101", b"1200", b"U", b"00401",
    b"000000001", b"0", b"P",
]

# A realistic interchange trailer so ``cleansed`` is always well over 109 bytes
# even when the ISA line under test has been shortened by a bad sender.
TRAILER = (
    b"GS*PO*SENDERGS*RECEIVERID*20240101*1200*1*X*004010~"
    b"ST*850*0001~BEG*00*NE*PO0001**20240101~SE*2*0001~"
    b"GE*1*1~IEA*1*000000001~"
)


def isa_segment(sep: bytes = b"*", comp: bytes = b":",
                elements: list[bytes] | None = None) -> bytes:
    els = ISA_ELEMENTS if elements is None else elements
    return sep.join([b"ISA", *els, comp])  # ISA .. ISA16, no terminator yet


def build_isa(
    sep: bytes = b"*",
    term: bytes = b"~",
    comp: bytes = b":",
    elements: list[bytes] | None = None,
    trailer: bytes = TRAILER,
    pre: bytes = b"",
) -> bytes:
    return pre + isa_segment(sep, comp, elements) + term + trailer.replace(b"*", sep)


def _assert_contract(dirty: bytes, r: IsaLineResult) -> None:
    """The run starts with an ISA tag, is a prefix of dirty[isa_start:], and is
    immediately followed by a GS tag (case-insensitive -- a lowercase file is
    parsed case-insensitively)."""
    if r.isa_line is None:
        return
    assert r.isa_line[:3].upper() == b"ISA"
    cleansed = dirty[r.isa_start:]
    assert cleansed.startswith(r.isa_line)
    assert cleansed[len(r.isa_line):][:2].upper() == b"GS"


# (name, dirty, expected_codes, isa_line_expected)
CASES: list[tuple[str, bytes, list[Code], bool]] = [
    ("conformant, GS at offset 106", build_isa(), [], True),
    ("UTF-8 BOM before ISA",
     build_isa(pre=b"\xef\xbb\xbf"), [Code.ISA_LEADING_BYTES], True),
    ("human text before ISA",
     build_isa(pre=b"sent 2024-01-01\r\n"), [Code.ISA_LEADING_BYTES], True),
    ("no ISA tag at all",
     b"GS*PO*A*B*20240101*1200*1*X*004010~ST*850*1~SE*1*1~GE*1*1~IEA*1*1~",
     [Code.ISA_NO_TAG], False),
    ("too short to be an interchange",
     b"ISA*00*x~GS*", [Code.ISA_INTERCHANGE_TOO_SHORT], False),
    ("newline appended after terminator (~\\r\\n)",
     build_isa(term=b"~\r\n"), [], True),
    ("bare \\r\\n terminator (2 bytes)",
     build_isa(term=b"\r\n"), [], True),
    ("space between terminator and GS",
     build_isa(term=b"~ "), [], True),
    ("ISA02 & ISA04 stripped -> short ISA line",
     build_isa(elements=[b"00", b"", b"00", b"", b"ZZ", b"SENDER".ljust(15),
                         b"ZZ", b"RECEIVER".ljust(15), b"240101", b"1200",
                         b"U", b"00401", b"000000001", b"0", b"P"]),
     [], True),
    ("ISA06 padded wide -> long ISA line",
     build_isa(elements=[b"00", b" " * 10, b"00", b" " * 10, b"ZZ",
                         b"SENDER".ljust(25), b"ZZ", b"RECEIVER".ljust(15),
                         b"240101", b"1200", b"U", b"00401", b"000000001",
                         b"0", b"P"]),
     [], True),
    ("only 14 element separators in the ISA",
     build_isa(elements=ISA_ELEMENTS[:13]), [Code.ISA_SEPARATOR_COUNT_LOW], False),
    ("no GS segment after the ISA",
     build_isa(trailer=b"ST*850*0001~BEG*00*NE*PO1**20240101~SE*2*0001~"
                       b"GE*1*1~IEA*1*000000001~ZZZZZZZZZZZZZZZZZZZZ~"),
     [Code.ISA_GS_NOT_FOUND], False),
    ("alphanumeric element separator '7', GS at 106",
     build_isa(sep=b"7"), [], True),
    ("pipe separator, LF terminator",
     build_isa(sep=b"|", term=b"\n"), [], True),
    ("literal 'GS' text inside ISA06, real GS follows",
     build_isa(elements=[b"00", b" " * 10, b"00", b" " * 10, b"ZZ",
                         b"XGSY".ljust(15), b"ZZ", b"RECEIVER".ljust(15),
                         b"240101", b"1200", b"U", b"00401", b"000000001",
                         b"0", b"P"]),
     [], True),

    # --- retry: junk that contains 'ISA', real interchange follows ---
    ("'ISA' in leading junk (DISASTER), then real interchange",
     b"THIS IS A DISASTER\n" + build_isa(),
     [Code.ISA_LEADING_BYTES], True),
    ("junk ends in 'ISA' + separator, then real interchange",
     b"memo: ISA*" + build_isa(),
     [Code.ISA_LEADING_BYTES], True),
    ("first 'ISA' has no usable GS, second is the real one",
     b"ISA is coming\n" + build_isa(),
     [Code.ISA_LEADING_BYTES], True),

    # --- retry exhausted: no candidate yields a 16-separator line ---
    ("no GS envelope, only a stray REF*GS* deep in the data",
     isa_segment() + b"~ST*850*1~REF*GS*99~SE*1*1~GE*1*1~IEA*1*1~" + b"P" * 60,
     [Code.ISA_NO_FUNCTIONAL_GROUP], False),
    ("only 14 element separators, every candidate tried",
     build_isa(elements=ISA_ELEMENTS[:13]),
     [Code.ISA_SEPARATOR_COUNT_LOW], False),

    # --- lowercase / wide-encoding ---
    ("lowercase 'isa' segment tag",
     build_isa().lower(),
     [Code.ISA_TAG_LOWERCASE], True),
    ("mixed-case 'Isa' tag",
     build_isa().replace(b"ISA", b"Isa", 1),
     [Code.ISA_TAG_LOWERCASE], True),
    ("uppercase 'ISA' in junk, real segment is lowercase",
     b"SUBJECT: ISA FILE\r\n" + build_isa().lower(),
     [Code.ISA_TAG_LOWERCASE, Code.ISA_LEADING_BYTES], True),
    ("plain text with 'isa' only inside a word, no EDI",
     b"this reading is advisable for everyone involved. " * 4,
     [Code.ISA_NO_TAG], False),
    ("UTF-16LE encoded file",
     build_isa().decode().encode("utf-16-le"),
     [Code.ISA_TAG_UTF16], False),
    ("UTF-16BE encoded file",
     build_isa().decode().encode("utf-16-be"),
     [Code.ISA_TAG_UTF16], False),
]


@pytest.mark.parametrize(
    "dirty,expected_codes,isa_line_expected",
    [pytest.param(d, c, l, id=n) for n, d, c, l in CASES],
)
def test_extract_isa_line(
    dirty: bytes, expected_codes: list[Code], isa_line_expected: bool
) -> None:
    r = extract_isa_line(dirty)
    got = [d.code for d in r.diagnostics]
    for code in expected_codes:
        assert code in got, f"expected {code} in {got}"
    assert (r.isa_line is not None) == isa_line_expected
    _assert_contract(dirty, r)


def test_offsets_point_into_the_original_input() -> None:
    r = extract_isa_line(b"\xef\xbb\xbf" + build_isa())
    (leading,) = [d for d in r.diagnostics if d.code is Code.ISA_LEADING_BYTES]
    assert leading.offset == 0
    assert r.isa_start == 3
