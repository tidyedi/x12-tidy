# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Step 2, slice 2: reconstruct the canonical ISA line.

The methodology, and why it works where fixed-offset parsers do not:

* :func:`~x12_tidy.isa.extract_isa_line` and
  :func:`~x12_tidy.isa.split_isa_line` exist only to recover the four
  delimiters, and they do it from *structure* (the ``ISA`` tag, the ``GS``
  boundary, exactly sixteen element separators) -- never from a byte offset or
  an element width. So they succeed on an ISA line that is the "wrong" length.
* Once those delimiters are in hand with **no fatal**, width stops being
  load-bearing. The run splits into exactly sixteen elements on the element
  separator; each element is then normalised to its fixed width; the line is
  reassembled. A blank fixed-width field the sender right-trimmed -- which kills
  a conventional parser outright -- is simply padded back here.

Repairs (each carries a diagnostic so a human can veto):

* a ``\r`` / ``\n`` inside an element -> replaced with a space, then the element
  is measured. The delimiters are known, so a byte that *is* a delimiter --
  ISA16 (always the component separator) and ISA11 when it carries the
  repetition separator -- is left untouched.
* an element shorter than its fixed width -> space-padded on the right.
* an element longer than its width by trailing spaces only -> trimmed.
* the segment terminator -> normalised to ``~`` (it is not part of the 105-byte
  line; it is returned alongside).

Refuses -- ``isa_line`` is ``None``, one fatal diagnostic:

* anything :func:`split_isa_line` already made fatal -- propagated.
* an element longer than its width with **real data** in the overflow
  (``isa.element-overflow``). We cannot know the sender's intent -- a dropped
  element separator merging two fields, or an overrun field -- and guessing
  risks corrupting an identifier.
* a reassembled line that is somehow not 105 bytes (``isa.line-length``) -- a
  guard that should never fire once the per-element widths hold.

Scope: **structure only** -- widths, delimiters, the terminator, the length. Not
element *values* (is ISA05 a real qualifier, ISA09 a real date, does ISA13 match
IEA02). That is later work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic
from x12_tidy.isa.delimiters import IsaDelimiters, split_isa_line
from x12_tidy.isa.isa_line import extract_isa_line

#: Fixed byte width of each ISA element, ISA01..ISA16. The sum is 86; with the
#: ``ISA`` tag (3 bytes) and the sixteen element separators (16) that makes the
#: canonical 105-byte ISA line.
ISA_ELEMENT_WIDTHS: tuple[int, ...] = (
    2, 10, 2, 10, 2, 15, 2, 15, 6, 4, 1, 5, 9, 1, 1, 1,
)
#: Length of the canonical ISA line -- the ``ISA`` tag through ISA16, **without**
#: the segment terminator (a separate byte that would sit at offset 105).
CANONICAL_LENGTH = 105
#: The terminator every reconstructed line is normalised to.
CANONICAL_TERMINATOR = b"~"

_ISA_TAG = b"ISA"
_LINE_BREAKS = (b"\r", b"\n")
#: 1-based index of ISA16 (always the component separator) and ISA11 (the
#: repetition separator, version-gated). Elements whose *value is a delimiter*
#: are never rewritten.
_COMPONENT_SEPARATOR_INDEX = 16
_REPETITION_SEPARATOR_INDEX = 11


@dataclass
class CleanIsaLine:
    """The canonical ISA line and every deviation found producing it.

    ``isa_line`` is the 105-byte canonical line, or ``None`` when the input is
    terminally broken. ``elements`` is the sixteen width-correct element values
    (empty when ``isa_line`` is ``None``). ``diagnostics`` spans the whole
    pipeline: locating the run, recovering the delimiters, and reconstruction.
    """

    isa_line: bytes | None
    elements: tuple[bytes, ...]
    element_separator: bytes
    repetition_separator: bytes | None
    component_separator: bytes
    segment_terminator: bytes
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        """The input needed no repair and tripped no finding."""
        return not self.diagnostics


def clean_isa_line(dirty: bytes) -> CleanIsaLine:
    """Locate, recover delimiters, and reconstruct the canonical ISA line from
    raw bytes. See the module docstring for the repair / refuse contract."""
    located = extract_isa_line(dirty)
    diagnostics: list[Diagnostic] = list(located.diagnostics)

    if located.isa_line is None:
        return CleanIsaLine(None, (), b"", None, b"", b"", diagnostics)

    delimiters = split_isa_line(located.isa_line, base_offset=located.isa_start)
    diagnostics += delimiters.diagnostics

    return _finish(located.isa_line, delimiters, diagnostics, located.isa_start)


def reconstruct_isa_line(
    run: bytes, delimiters: IsaDelimiters, *, base_offset: int = 0
) -> CleanIsaLine:
    """Reconstruct the canonical line from an already-located run and its
    recovered delimiters. :func:`clean_isa_line` is the usual entry point; use
    this when the run and delimiters are already in hand. ``base_offset`` is
    added to every diagnostic offset."""
    return _finish(run, delimiters, list(delimiters.diagnostics), base_offset)


def _finish(
    run: bytes,
    delimiters: IsaDelimiters,
    diagnostics: list[Diagnostic],
    base_offset: int,
) -> CleanIsaLine:
    if not delimiters.usable:
        return CleanIsaLine(
            None, (),
            delimiters.element_separator, delimiters.repetition_separator,
            delimiters.component_separator, delimiters.segment_terminator,
            diagnostics,
        )

    line, elements, rebuild_diagnostics = _rebuild(
        run, delimiters, base_offset=base_offset
    )
    diagnostics += rebuild_diagnostics

    return CleanIsaLine(
        line,
        elements,
        delimiters.element_separator,
        delimiters.repetition_separator,
        delimiters.component_separator,
        CANONICAL_TERMINATOR if line is not None else delimiters.segment_terminator,
        diagnostics,
    )


def _rebuild(
    run: bytes, delimiters: IsaDelimiters, *, base_offset: int
) -> tuple[bytes | None, tuple[bytes, ...], list[Diagnostic]]:
    """The reconstruction itself. ``(line, elements, diagnostics)`` -- ``line``
    is ``None`` and ``elements`` empty on a fatal."""
    diagnostics: list[Diagnostic] = []

    # delimiters.usable guarantees exactly 17 parts: "ISA", ISA01..ISA15, then
    # ISA16 + terminator + trailing. ISA16's value is the component separator.
    parts = run.split(delimiters.element_separator)
    raw_elements = [*parts[1:16], parts[16][:1]]

    carries_repetition_separator = delimiters.repetition_separator is not None

    elements: list[bytes] = []
    for index, (raw, width) in enumerate(
        zip(raw_elements, ISA_ELEMENT_WIDTHS), start=1
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
        _ISA_TAG
        + delimiters.element_separator
        + delimiters.element_separator.join(elements)
    )

    if len(line) != CANONICAL_LENGTH:
        diagnostics.append(Diagnostic(
            Code.ISA_LINE_LENGTH,
            f"the reconstructed ISA line is {len(line)} byte(s), not "
            f"{CANONICAL_LENGTH}; refusing to emit a non-conformant line.",
            offset=base_offset,
        ))
        return None, (), diagnostics

    return line, tuple(elements), diagnostics
