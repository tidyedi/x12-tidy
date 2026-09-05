# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Step 2, slice 2: reconstruct the canonical ISA line.

The methodology, and why it works where fixed-offset parsers do not:

* :func:`~x12_tidy.envelope.isa.extract_isa_line` and
  :func:`~x12_tidy.envelope.isa.split_isa_line` exist only to recover the four
  delimiters, and they do it from *structure* (the ``ISA`` identifier, the ``GS``
  boundary, exactly sixteen element separators) -- never from a byte offset or
  an element width. So they succeed on an ISA line that is the "wrong" length.
* Once :class:`~x12_tidy.envelope.isa.IsaDecomposition` comes back with **no fatal**,
  width stops being load-bearing. The sixteen elements are already split
  (:attr:`IsaDecomposition.elements` -- no second split here); each is
  normalised to its fixed width, and the line is reassembled at 105 bytes. A
  blank fixed-width field the sender right-trimmed -- which kills a conventional
  parser outright -- is simply padded back.

Repairs (each carries a diagnostic so a human can veto):

* a ``\r`` / ``\n`` inside an element -> replaced with a space, then the element
  is measured. The delimiters are known, so a byte that *is* a delimiter --
  ISA16 (always the component separator) and ISA11 when it carries the
  repetition separator -- is left untouched.
* an element shorter than its fixed width -> space-padded on the right.
* an element longer than its width by trailing spaces only -> trimmed.

The delimiters are **not** repaired. Which byte serves as the element,
component, repetition, and segment delimiter is the sender's choice -- X12 does
not dictate it -- so reconstruction preserves whatever the sender used. A
segment terminator of ``\n`` stays ``\n``; it is never rewritten to ``~``. The
105-byte line carries no terminator (it is a separate byte);
``ReconstructedIsaLine.segment_terminator`` reports the sender's byte, and the
eventual whole-interchange rejoin uses it. Bytes that *cannot* be a legal
delimiter -- trailing ``\r\n`` or spaces after the real terminator, an
alphanumeric terminator -- are a different matter and are stripped or refused by
:func:`split_isa_line`. Only when the sender omitted the terminator entirely
(GS followed ISA16 directly) is ``~`` supplied, because there is no byte to
preserve.

Refuses -- ``isa_line`` is ``None``, one fatal diagnostic:

* anything :func:`split_isa_line` already made fatal -- propagated.
* an element longer than its width with **real data** in the overflow
  (``isa.element-overflow``). We cannot know the sender's intent -- a dropped
  element separator merging two fields, or an overrun field -- and guessing
  risks corrupting an identifier.

Scope: **structure only** -- widths, delimiters, the terminator, the length. Not
element *values* (is ISA05 a real qualifier, ISA09 a real date, does ISA13 match
IEA02). That is later work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic
from x12_tidy.envelope.isa.delimiters import IsaDecomposition, split_isa_line
from x12_tidy.envelope.isa.isa_line import extract_isa_line

#: Fixed byte width of each ISA element, ISA01..ISA16. The sum is 86; with the
#: ``ISA`` identifier (3 bytes) and the sixteen element separators (16) that makes the
#: canonical 105-byte ISA line.
ISA_ELEMENT_WIDTHS: tuple[int, ...] = (
    2, 10, 2, 10, 2, 15, 2, 15, 6, 4, 1, 5, 9, 1, 1, 1,
)
#: Length of the canonical ISA line -- the ``ISA`` identifier through ISA16, **without**
#: the segment terminator (a separate byte that would sit at offset 105).
CANONICAL_LENGTH = 105

_ISA_IDENTIFIER = b"ISA"
_LINE_BREAKS = (b"\r", b"\n")
#: 1-based index of ISA16 (always the component separator) and ISA11 (the
#: repetition separator, version-gated). Elements whose *value is a delimiter*
#: are never rewritten.
_COMPONENT_SEPARATOR_INDEX = 16
_REPETITION_SEPARATOR_INDEX = 11


@dataclass
class ReconstructedIsaLine:
    """The canonical ISA line and every deviation found producing it.

    ``isa_line`` is the 105-byte canonical line, or ``None`` when the input is
    terminally broken. ``elements`` is the sixteen width-correct element values
    (empty when ``isa_line`` is ``None``). ``decomposition`` is the slice-1
    result this was built from (``None`` only when Step 1 never returned a run).
    ``diagnostics`` spans the whole pipeline: locating the run, recovering the
    delimiters, and reconstruction.
    """

    isa_line: bytes | None
    elements: tuple[bytes, ...]
    decomposition: IsaDecomposition | None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        """The input needed no repair and tripped no finding."""
        return not self.diagnostics

    @property
    def segment_terminator(self) -> bytes:
        """The segment terminator to rejoin the interchange with -- the byte the
        sender chose, preserved as-is (a ``\\n`` terminator stays ``\\n``). It is
        ``~`` only when the sender omitted the terminator and it had to be
        supplied. Empty when Step 1 never returned a run.

        This is ``decomposition.segment_terminator``; the property exists so
        callers holding a :class:`ReconstructedIsaLine` need not reach through.
        """
        if self.decomposition is not None:
            return self.decomposition.segment_terminator
        return b""


def clean_isa_line(dirty: bytes) -> ReconstructedIsaLine:
    """Locate, recover delimiters, and reconstruct the canonical ISA line from
    raw bytes. See the module docstring for the repair / refuse contract."""
    located = extract_isa_line(dirty)
    if located.isa_line is None:
        return ReconstructedIsaLine(None, (), None, list(located.diagnostics))

    decomposition = split_isa_line(located.isa_line, base_offset=located.isa_start)
    result = reconstruct_isa_line(decomposition, base_offset=located.isa_start)
    result.diagnostics = list(located.diagnostics) + result.diagnostics
    return result


def reconstruct_isa_line(
    decomposition: IsaDecomposition, *, base_offset: int = 0
) -> ReconstructedIsaLine:
    """Reconstruct the canonical line from a slice-1 :class:`IsaDecomposition`.
    :func:`clean_isa_line` is the usual entry point; use this when the
    decomposition is already in hand. ``base_offset`` is added to every
    reconstruction diagnostic offset.

    The returned ``diagnostics`` carries the decomposition's findings followed
    by reconstruction's.
    """
    diagnostics: list[Diagnostic] = list(decomposition.diagnostics)

    if not decomposition.usable:
        return ReconstructedIsaLine(None, (), decomposition, diagnostics)

    line, elements, rebuild_diagnostics = _rebuild(
        decomposition, base_offset=base_offset
    )
    diagnostics += rebuild_diagnostics
    return ReconstructedIsaLine(line, elements, decomposition, diagnostics)


def _rebuild(
    decomposition: IsaDecomposition, *, base_offset: int
) -> tuple[bytes | None, tuple[bytes, ...], list[Diagnostic]]:
    """The reconstruction itself. ``(line, elements, diagnostics)`` -- ``line``
    is ``None`` and ``elements`` empty on a fatal."""
    diagnostics: list[Diagnostic] = []
    element_separator = decomposition.element_separator
    carries_repetition_separator = decomposition.repetition_separator is not None

    elements: list[bytes] = []
    for index, (raw, width) in enumerate(
        zip(decomposition.elements, ISA_ELEMENT_WIDTHS), start=1
    ):
        name = f"ISA{index:02d}"
        value = raw
        is_delimiter_element = index == _COMPONENT_SEPARATOR_INDEX or (
            index == _REPETITION_SEPARATOR_INDEX and carries_repetition_separator
        )

        # A CR/LF inside a text element -- a hard-wrapped ISA segment. Safe to
        # rewrite: the delimiters are known, and a byte that is a delimiter is
        # excluded above.
        if not is_delimiter_element and any(b in value for b in _LINE_BREAKS):
            rewritten = value.replace(b"\r", b" ").replace(b"\n", b" ")
            diagnostics.append(Diagnostic(
                Code.ISA_ELEMENT_EMBEDDED_NEWLINE,
                f"{name} contains "
                f"{sum(value.count(b) for b in _LINE_BREAKS)} carriage-return/"
                f"line-feed byte(s) ({value!r}); replaced with spaces.",
                offset=base_offset,
            ))
            value = rewritten

        if len(value) < width:
            diagnostics.append(Diagnostic(
                Code.ISA_ELEMENT_WIDTH,
                f"{name} is {len(value)} byte(s); padded with spaces to its "
                f"fixed width of {width}.",
                offset=base_offset,
            ))
            value = value.ljust(width)
        elif len(value) > width:
            overflow = value[width:]
            if overflow.strip(b" ") == b"":
                diagnostics.append(Diagnostic(
                    Code.ISA_ELEMENT_WIDTH,
                    f"{name} is {len(value)} byte(s), over its fixed width of "
                    f"{width} by trailing spaces only; trimmed.",
                    offset=base_offset,
                ))
                value = value[:width]
            else:
                diagnostics.append(Diagnostic(
                    Code.ISA_ELEMENT_OVERFLOW,
                    f"{name} is {len(value)} byte(s) and holds non-space data "
                    f"past its fixed width of {width} ({value!r}); the sender's "
                    "intent is unknowable (a dropped element separator, or an "
                    "overrun field).",
                    offset=base_offset,
                ))
                return None, (), diagnostics

        elements.append(value)

    line = (
        _ISA_IDENTIFIER + element_separator + element_separator.join(elements)
    )

    # Every element above is forced to its fixed width (or the function has
    # already returned on overflow), so the length is arithmetically fixed.
    # A tripwire for a future change to the reconstruction, never a real input.
    assert len(line) == CANONICAL_LENGTH

    return line, tuple(elements), diagnostics
