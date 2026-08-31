"""Piece 1: ISA envelope bootstrap.

An X12 interchange begins with a single ISA segment. Unlike every other
segment it is fixed-layout, which lets us discover the delimiters (which are
themselves declared *positionally* inside ISA) before we know anything else
about the file.

This module implements the first slice of validation, following the project
rule of **permissive parsing, strict reporting**: locate the ISA envelope and
its delimiters even in a malformed file, then emit a :class:`Diagnostic` for
*every* deviation instead of bailing on the first one.

What it checks:

1. the file is not empty -- ``ISA001`` (unrecoverable)
2. an ``ISA`` tag exists; if it is not the very first bytes (a BOM or other
   leading data precedes it) that is reported as ``ISA002`` but parsing
   continues from wherever ``ISA`` was found. If no ``ISA`` appears anywhere,
   ``ISA002`` is unrecoverable.
3. the byte at ``isa_offset + 3`` is taken as the **element separator**; an
   alphanumeric choice is unusual and warned as ``ISA100``
4. the ISA segment runs up to the first ``GS`` + element-separator sequence.
   The byte immediately before it is the **segment terminator**; a run of
   CR/LF bytes wedged between the terminator and ``GS`` (a common sender bug --
   a newline appended after every segment) is stepped over and warned as
   ``ISA101``. No ``GS`` at all is ``ISA004`` (unrecoverable -- without it we
   cannot tell where ISA ends).
5. splitting the ISA segment on the element separator must yield the tag
   ``ISA`` followed by exactly 16 data elements -- otherwise ``ISA005``
6. the ISA segment (terminator excluded) must be exactly 105 bytes, the X12
   fixed length. A different length means the sender stripped or re-padded
   element(s) -- ``ISA006``. This is checked independently of rule 5 because a
   file can have 16 elements of the wrong width, or the right byte count split
   into the wrong number of elements.

Everything operates on ``bytes``: BOM / encoding detection is only meaningful
at the byte level, and staying byte-oriented keeps a future Rust port a
mechanical translation.

Known limitations left for a later piece / discussion:

* Rule 4 trusts the first literal ``GS`` + separator. ``GS`` can in theory
  appear inside ISA06/ISA08 data; a fixed-offset cross-check is deliberately
  *not* used because senders strip elements and shift every offset.
* Rule 2's ISA search prefers an ``ISA`` whose 4th byte is non-alphanumeric
  (a plausible separator), then falls back to the first literal ``ISA``. Junk
  containing the exact bytes ``ISA`` followed by punctuation could still fool
  it.
* When the segment terminator itself is CR or LF, a preceding stray CR (a
  ``\\r\\n`` terminator pair) is left attached to ISA16 rather than reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Diagnostic

_ISA_TAG = b"ISA"
_ELEMENT_SEPARATOR_OFFSET = 3  # 4th byte of the segment, 0-indexed
_EXPECTED_ELEMENT_COUNT = 16
# "ISA" (3) + 16 element separators (16) + the 16 fixed-width elements (86),
# with the segment terminator excluded.
_EXPECTED_ISA_SEGMENT_LEN = 105

_CR = 0x0D
_LF = 0x0A
_SPACE = 0x20

# Byte-order marks that must never precede ISA.
_BOMS: dict[bytes, str] = {
    b"\xef\xbb\xbf": "UTF-8",
    b"\xff\xfe\x00\x00": "UTF-32 LE",
    b"\x00\x00\xfe\xff": "UTF-32 BE",
    b"\xff\xfe": "UTF-16 LE",
    b"\xfe\xff": "UTF-16 BE",
}


@dataclass
class IsaResult:
    """Outcome of :func:`check_isa`.

    ``ok`` is True only when no error-severity diagnostics were produced
    (warnings do not clear it). Every other field is filled in on a
    best-effort basis: each is set as soon as it is known, so a later failure
    still leaves the earlier discoveries available for inspection.
    """

    ok: bool
    diagnostics: list[Diagnostic] = field(default_factory=list)
    isa_offset: int | None = None
    element_separator: int | None = None
    segment_terminator: int | None = None
    isa_segment: bytes | None = None
    elements: list[bytes] | None = None


def check_isa(data: bytes) -> IsaResult:
    """Run piece 1 against the raw bytes of an EDI file."""

    diags: list[Diagnostic] = []
    result = IsaResult(ok=False, diagnostics=diags)

    # (1) not empty -- nothing to recover from --------------------------------
    if not data:
        diags.append(Diagnostic.error("ISA001", "file is empty", offset=0))
        return result

    # (2) find the ISA tag, tolerating a BOM or other leading data -----------
    isa_offset = _find_isa_start(data)
    if isa_offset is None:
        diags.append(_no_isa_diagnostic(data))
        return result
    result.isa_offset = isa_offset
    if isa_offset != 0:
        # Recoverable: report the junk, then carry on from the ISA tag.
        diags.append(_leading_data_diagnostic(data[:isa_offset]))

    # (3) element separator == byte at isa_offset + 3 -----------------------
    sep_index = isa_offset + _ELEMENT_SEPARATOR_OFFSET
    if sep_index >= len(data):
        diags.append(
            Diagnostic.error(
                "ISA003",
                "file ends immediately after the 'ISA' tag; cannot read the "
                "element separator",
                offset=len(data),
            )
        )
        return result

    sep = data[sep_index]
    result.element_separator = sep
    if _is_ascii_alnum(sep):
        diags.append(
            Diagnostic.warning(
                "ISA100",
                f"element separator {_byte_repr(sep)} is alphanumeric, which "
                "is unusual for X12",
                offset=sep_index,
            )
        )

    # (4) locate the first "GS" + separator after the ISA tag --------------
    needle = b"GS" + bytes([sep])
    gs_idx = data.find(needle, sep_index + 1)
    if gs_idx == -1:
        diags.append(
            Diagnostic.error(
                "ISA004",
                "could not find a 'GS' functional-group header after the ISA "
                f"envelope (searched for 'GS' + {_byte_repr(sep)}); cannot "
                "determine where the ISA segment ends",
            )
        )
        return result
    if gs_idx < isa_offset + len(_ISA_TAG) + 2:
        # 'GS' + sep cannot legitimately start before "ISA" + sep + a byte.
        diags.append(
            Diagnostic.error(
                "ISA004",
                f"found 'GS' + {_byte_repr(sep)} at offset {gs_idx}, too early "
                "to be a real functional-group header",
                offset=gs_idx,
            )
        )
        return result

    # segment terminator: the byte before "GS", stepping past any extra
    # CR/LF line breaks a sender appended after the real terminator.
    term_index, extra_newlines = _resolve_terminator(data, isa_offset, gs_idx, sep)
    result.segment_terminator = data[term_index]
    isa_segment = data[isa_offset:term_index]
    result.isa_segment = isa_segment
    if extra_newlines:
        diags.append(
            Diagnostic.warning(
                "ISA101",
                f"{extra_newlines} stray line-break byte(s) between the ISA "
                "segment terminator and the 'GS' header; X12 segments are "
                "delimited by the terminator alone",
                offset=term_index + 1,
            )
        )

    # (5) split on the element separator -> "ISA" + 16 data elements -------
    elements = isa_segment.split(bytes([sep]))[1:]
    result.elements = elements
    if len(elements) != _EXPECTED_ELEMENT_COUNT:
        diags.append(
            Diagnostic.error(
                "ISA005",
                f"ISA header split into {len(elements)} data element(s); "
                f"expected {_EXPECTED_ELEMENT_COUNT} (ISA01..ISA16)",
                offset=isa_offset,
            )
        )

    # (6) fixed length -- independent of the element count ----------------
    if len(isa_segment) != _EXPECTED_ISA_SEGMENT_LEN:
        diags.append(
            Diagnostic.error(
                "ISA006",
                f"ISA segment is {len(isa_segment)} bytes; the X12 ISA is a "
                f"fixed {_EXPECTED_ISA_SEGMENT_LEN} bytes (segment terminator "
                "excluded). Element(s) were likely stripped or re-padded by "
                "the sender",
                offset=isa_offset,
            )
        )

    result.ok = not any(d.severity == "error" for d in diags)
    return result


# --- helpers ------------------------------------------------------------


def _find_isa_start(data: bytes) -> int | None:
    """Return the offset of the ISA tag, or None if there is no ``ISA``.

    Prefers an ``ISA`` whose following byte is non-alphanumeric (a plausible
    element separator) so we skip ``ISA`` appearing inside a word; falls back
    to the first literal occurrence.
    """

    first = data.find(_ISA_TAG)
    if first == -1:
        return None
    idx = first
    while idx != -1:
        sep_pos = idx + _ELEMENT_SEPARATOR_OFFSET
        if sep_pos < len(data) and not _is_ascii_alnum(data[sep_pos]):
            return idx
        idx = data.find(_ISA_TAG, idx + 1)
    return first


def _resolve_terminator(
    data: bytes, isa_offset: int, gs_idx: int, sep: int
) -> tuple[int, int]:
    """Locate the segment-terminator byte before ``GS``.

    Returns ``(terminator_index, extra_newline_count)``. ``extra_newline_count``
    is the number of CR/LF bytes sitting between the real terminator and the
    ``GS`` header -- a sender that appends a newline after every segment.
    """

    provisional = gs_idx - 1
    if data[provisional] not in (_CR, _LF):
        return provisional, 0

    # Walk back over a run of CR/LF bytes to the first byte that isn't one.
    q = provisional
    while q > isa_offset and data[q] in (_CR, _LF):
        q -= 1
    candidate = data[q]

    # Is that byte a real terminator, or ISA content (typically the ISA16
    # component separator) that legitimately precedes a CR/LF terminator? Use
    # a provisional split -- with the CR/LF as terminator -- to recover ISA16.
    provisional_elements = data[isa_offset:provisional].split(bytes([sep]))[1:]
    component_sep = (
        provisional_elements[-1][:1]
        if len(provisional_elements) == _EXPECTED_ELEMENT_COUNT
        and provisional_elements[-1]
        else b""
    )
    if (
        not _is_ascii_alnum(candidate)
        and candidate not in (_CR, _LF, _SPACE)
        and candidate != sep
        and bytes([candidate]) != component_sep
    ):
        return q, provisional - q
    # The CR/LF byte immediately before GS was itself the terminator.
    return provisional, 0


def _no_isa_diagnostic(data: bytes) -> Diagnostic:
    for raw, name in _BOMS.items():
        if data.startswith(raw):
            return Diagnostic.error(
                "ISA002",
                f"file begins with a {name} byte-order mark and contains no "
                "'ISA' segment",
                offset=0,
            )
    return Diagnostic.error(
        "ISA002",
        f"no 'ISA' segment found anywhere in the file (starts with {data[:16]!r})",
        offset=0,
    )


def _leading_data_diagnostic(leading: bytes) -> Diagnostic:
    for raw, name in _BOMS.items():
        if leading.startswith(raw):
            rest = leading[len(raw) :]
            extra = f" plus {len(rest)} more byte(s)" if rest else ""
            return Diagnostic.error(
                "ISA002",
                f"file begins with a {name} byte-order mark{extra}; the 'ISA' "
                "segment must be the very first bytes",
                offset=0,
            )
    return Diagnostic.error(
        "ISA002",
        f"{len(leading)} byte(s) precede the 'ISA' segment ({leading[:32]!r}); "
        "the 'ISA' segment must be the very first bytes",
        offset=0,
    )


def _is_ascii_alnum(byte: int) -> bool:
    return byte < 128 and chr(byte).isalnum()


def _byte_repr(byte: int) -> str:
    ch = chr(byte)
    if byte < 128 and ch.isprintable() and not ch.isspace():
        return f"0x{byte:02X} ({ch!r})"
    return f"0x{byte:02X}"
