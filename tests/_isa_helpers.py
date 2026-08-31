# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Builders for synthetic X12 interchanges, shared by the ISA test modules.

``build_isa`` assembles a whole interchange (ISA line + a realistic trailer)
with every delimiter and every ISA element configurable, so a test can express
exactly one deviation at a time.
"""

from __future__ import annotations

# 15 conformant ISA01..ISA15 values. ISA16 (the component separator) is appended
# by :func:`isa_segment` as the last field before the terminator. ISA11 is "U"
# and ISA12 is "00401" -- an interchange with no repetition separator.
ISA_ELEMENTS: list[bytes] = [
    b"00", b" " * 10, b"00", b" " * 10, b"ZZ", b"SENDER".ljust(15),
    b"ZZ", b"RECEIVER".ljust(15), b"240101", b"1200", b"U", b"00401",
    b"000000001", b"0", b"P",
]

# A realistic interchange trailer so ``cleansed`` is always well over 109 bytes
# even when the ISA line under test has been shortened by a bad sender.
TRAILER: bytes = (
    b"GS*PO*SENDERGS*RECEIVERID*20240101*1200*1*X*004010~"
    b"ST*850*0001~BEG*00*NE*PO0001**20240101~SE*2*0001~"
    b"GE*1*1~IEA*1*000000001~"
)


def isa_segment(
    sep: bytes = b"*",
    comp: bytes = b":",
    elements: list[bytes] | None = None,
) -> bytes:
    """``ISA`` .. ISA16 joined on ``sep`` -- no terminator yet."""
    els = ISA_ELEMENTS if elements is None else elements
    return sep.join([b"ISA", *els, comp])


def build_isa(
    sep: bytes = b"*",
    term: bytes = b"~",
    comp: bytes = b":",
    elements: list[bytes] | None = None,
    trailer: bytes = TRAILER,
    pre: bytes = b"",
) -> bytes:
    """A whole interchange: optional leading junk, the ISA segment, its
    terminator, then a trailer whose ``*`` delimiters are swapped for ``sep``."""
    return pre + isa_segment(sep, comp, elements) + term + trailer.replace(b"*", sep)
