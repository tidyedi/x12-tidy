"""Tests for piece 1: ISA envelope bootstrap."""

from __future__ import annotations

from x12_tidy.envelope import check_isa


def build_isa(
    sep: bytes = b"*",
    term: bytes = b"~",
    comp: bytes = b":",
    *,
    n_elements: int = 16,
) -> bytes:
    """Build a syntactically well-formed ISA segment (+ terminator).

    ``n_elements`` lets a test deliberately produce the wrong count.
    """

    fields = [
        b"00",
        b" " * 10,
        b"00",
        b" " * 10,
        b"ZZ",
        b"SENDER".ljust(15),
        b"ZZ",
        b"RECEIVER".ljust(15),
        b"240101",
        b"1200",
        b"U",
        b"00401",
        b"000000001",
        b"0",
        b"P",
        comp,
    ]
    fields = fields[:n_elements]
    return b"ISA" + sep + sep.join(fields) + term


def build_interchange(sep: bytes = b"*", term: bytes = b"~", comp: bytes = b":") -> bytes:
    """An ISA followed by just enough of a GS segment for piece 1."""

    return build_isa(sep, term, comp) + b"GS" + sep + b"PO" + term


def test_valid_interchange_star_delimited() -> None:
    result = check_isa(build_interchange())
    assert result.ok
    assert result.diagnostics == []
    assert result.element_separator == ord("*")
    assert result.segment_terminator == ord("~")
    assert result.elements is not None
    assert len(result.elements) == 16
    assert result.elements[4] == b"ZZ"


def test_valid_interchange_pipe_delimited() -> None:
    result = check_isa(build_interchange(sep=b"|", term=b"\n"))
    assert result.ok
    assert result.element_separator == ord("|")
    assert result.segment_terminator == ord("\n")


def test_empty_file() -> None:
    result = check_isa(b"")
    assert not result.ok
    assert [d.code for d in result.diagnostics] == ["ISA001"]


def test_utf8_bom_rejected() -> None:
    result = check_isa(b"\xef\xbb\xbf" + build_interchange())
    assert not result.ok
    assert result.diagnostics[0].code == "ISA002"
    assert "BOM" in result.diagnostics[0].message or "byte-order" in result.diagnostics[0].message


def test_leading_whitespace_rejected() -> None:
    result = check_isa(b"\r\n" + build_interchange())
    assert not result.ok
    assert result.diagnostics[0].code == "ISA002"


def test_not_edi_at_all() -> None:
    result = check_isa(b"hello world, not edi")
    assert not result.ok
    assert result.diagnostics[0].code == "ISA002"


def test_truncated_after_isa_tag() -> None:
    result = check_isa(b"ISA")
    assert not result.ok
    assert result.diagnostics[0].code == "ISA003"


def test_no_gs_segment() -> None:
    result = check_isa(build_isa())  # ISA + terminator, no GS
    assert not result.ok
    assert result.diagnostics[0].code == "ISA004"
    assert result.element_separator == ord("*")  # still discovered


def test_wrong_element_count() -> None:
    data = build_isa(n_elements=15) + b"GS*PO~"
    result = check_isa(data)
    assert not result.ok
    codes = [d.code for d in result.diagnostics]
    assert "ISA005" in codes
    assert result.elements is not None and len(result.elements) == 15


def test_alphanumeric_separator_warns_but_parses() -> None:
    # '7' does not occur in any field value or in the "ISA" tag.
    result = check_isa(build_interchange(sep=b"7"))
    assert result.ok
    codes = [d.code for d in result.diagnostics]
    assert codes == ["ISA100"]
    assert result.element_separator == ord("7")


# --- permissive-parse / strict-report reworks --------------------------


def test_leading_junk_reported_but_envelope_still_parsed() -> None:
    junk = b">>> forwarded by a trading partner >>>\n"
    result = check_isa(junk + build_interchange())
    codes = [d.code for d in result.diagnostics]
    assert "ISA002" in codes  # the junk is flagged
    assert not result.ok  # ISA002 is an error
    # ...but parsing continued from the ISA tag:
    assert result.isa_offset == len(junk)
    assert result.element_separator == ord("*")
    assert result.segment_terminator == ord("~")
    assert result.elements is not None and len(result.elements) == 16


def test_utf8_bom_is_recoverable_leading_data() -> None:
    result = check_isa(b"\xef\xbb\xbf" + build_interchange())
    assert not result.ok
    assert result.diagnostics[0].code == "ISA002"
    assert result.isa_offset == 3
    assert result.elements is not None and len(result.elements) == 16


def test_no_isa_tag_anywhere_is_unrecoverable() -> None:
    result = check_isa(b"GS*PO*S*R*240101*1200*1*X~ST*850*0001~SE*2*0001~")
    assert not result.ok
    assert [d.code for d in result.diagnostics] == ["ISA002"]
    assert result.isa_offset is None


def test_extra_crlf_after_terminator_stepped_over() -> None:
    # a sender that appends "\r\n" after every segment terminator
    result = check_isa(build_isa() + b"\r\nGS*PO~")
    assert result.segment_terminator == ord("~")
    assert result.elements is not None and len(result.elements) == 16
    assert [d.code for d in result.diagnostics] == ["ISA101"]
    assert result.ok  # only a warning


def test_pipe_terminator_not_mistaken_for_extra_newline() -> None:
    # LF is the real terminator here; the ISA16 ':' before it must not be
    # mistaken for the terminator.
    result = check_isa(build_interchange(sep=b"|", term=b"\n"))
    assert result.ok
    assert result.diagnostics == []
    assert result.segment_terminator == ord("\n")


def test_stripped_element_flagged_by_length() -> None:
    data = build_isa(n_elements=15) + b"GS*PO~"
    result = check_isa(data)
    codes = [d.code for d in result.diagnostics]
    assert "ISA006" in codes  # non-standard byte length
    assert "ISA005" in codes  # and the wrong element count
    assert not result.ok


def test_right_count_wrong_width_flagged_by_length_only() -> None:
    # 16 elements, but ISA02 is padded to 11 instead of 10 -> 106-byte segment.
    fat = b"ISA*00*" + b" " * 11 + b"*00*" + b" " * 10 + (
        b"*ZZ*SENDER         *ZZ*RECEIVER       "
        b"*240101*1200*U*00401*000000001*0*P*:~GS*PO~"
    )
    result = check_isa(fat)
    codes = [d.code for d in result.diagnostics]
    assert codes == ["ISA006"]
    assert result.elements is not None and len(result.elements) == 16


def test_collects_multiple_independent_deviations() -> None:
    result = check_isa(b"\xef\xbb\xbf" + build_interchange(sep=b"7"))
    codes = [d.code for d in result.diagnostics]
    assert "ISA002" in codes  # BOM
    assert "ISA100" in codes  # alphanumeric separator
    assert not result.ok
