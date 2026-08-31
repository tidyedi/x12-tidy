# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""The diagnostic code registry -- the single source of truth.

Every finding x12-tidy can emit has an entry here.  Nothing else defines a
code: modules reference the :class:`Code` members, tests assert on them, and the
human-readable views (``docs/diagnostics.md``, ``x12-tidy codes``) are
*generated* from this file.  See ``docs/design.md`` for the full scheme.

Rules
-----
* Code strings are ``area.specific`` -- a closed ``area`` vocabulary
  (:data:`AREAS`), kebab-case within each part, a dot between.  No numbers.
* The ``area`` is the *subject* of the finding, never the code path that
  raised it (a short-ISA-line problem found while recovering is still
  ``isa.*``).
* ``default_severity`` is a starting point; user config may override it
  per-code later (including to ``"ignore"``).  Severity is resolved at
  *report* time, never stored on a :class:`~x12_tidy.diagnostics.Diagnostic`.
* A retired code is never reused.  A material change in meaning is a new code;
  the old one stays here marked ``deprecated=True``.

Adding a code
-------------
1. ``x12-tidy codes --area <area>`` -- check nothing already covers it.
2. Add a :class:`Code` member and a :class:`CodeMeta` row to :data:`META`.
3. Build: the generated docs update, CI checks the registry stays consistent
   with what the modules actually emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Severity = Literal["fatal", "error", "warning"]
#: ``fatal`` also stops parsing; ``error`` and ``warning`` are advisory.

#: The closed set of code areas -- the subject each finding is *about*.
#: Grows roughly once a year; keep it to X12 envelope structure.
AREAS: tuple[str, ...] = ("isa", "gs", "st", "delimiter", "structure")


class Code(Enum):
    """Stable identity for every kind of finding.

    The *value* is the ``area.specific`` string that appears in output and in
    tests.  The *member name* is that string upper-cased with ``.``/``-`` ->
    ``_`` (so ``isa.leading-bytes`` <-> ``Code.ISA_LEADING_BYTES``).
    """

    # -- isa: locating and bounding the ISA line (Step 1) --
    ISA_NO_TAG = "isa.no-tag"
    ISA_TAG_LOWERCASE = "isa.tag-lowercase"
    ISA_TAG_UTF16 = "isa.tag-utf16"
    ISA_LEADING_BYTES = "isa.leading-bytes"
    ISA_INTERCHANGE_TOO_SHORT = "isa.interchange-too-short"
    ISA_GS_NOT_FOUND = "isa.gs-not-found"
    ISA_SEPARATOR_COUNT_LOW = "isa.separator-count-low"
    ISA_NO_FUNCTIONAL_GROUP = "isa.no-functional-group"

    @property
    def area(self) -> str:
        return self.value.split(".", 1)[0]


@dataclass(frozen=True)
class CodeMeta:
    """Everything about a code except its identity.

    ``title`` is a short, static, generic line (no per-occurrence detail --
    that goes in the :class:`~x12_tidy.diagnostics.Diagnostic` message).
    ``explanation`` is the paragraph shown by ``x12-tidy explain``.
    """

    default_severity: Severity
    title: str
    explanation: str
    deprecated: bool = False


META: dict[Code, CodeMeta] = {
    Code.ISA_NO_TAG: CodeMeta(
        default_severity="fatal",
        title="No ISA segment tag in the file",
        explanation=(
            "The byte sequence 'ISA' does not appear anywhere in the file, so "
            "there is no X12 interchange to inspect. Nothing downstream can run."
        ),
    ),
    Code.ISA_TAG_LOWERCASE: CodeMeta(
        default_severity="error",
        title="ISA segment tag is not uppercase",
        explanation=(
            "The segment tag was found as 'isa' or mixed case (e.g. 'Isa'). "
            "X12 segment tags are uppercase. x12-tidy matched it "
            "case-insensitively and continued -- a file with a non-uppercase "
            "ISA tag almost certainly has every other segment tag the same way, "
            "which downstream steps must also tolerate."
        ),
    ),
    Code.ISA_TAG_UTF16: CodeMeta(
        default_severity="fatal",
        title="File appears to be UTF-16 encoded",
        explanation=(
            "The bytes 'I', 'S', 'A' appear separated by NUL bytes near the "
            "start of the file, which is what a UTF-16-encoded 'ISA' looks "
            "like. X12 interchanges must use a single-byte encoding (ASCII, "
            "Latin-1, or UTF-8 without a wide encoding). Re-export the file and "
            "try again."
        ),
    ),
    Code.ISA_LEADING_BYTES: CodeMeta(
        default_severity="warning",
        title="Bytes precede the ISA segment",
        explanation=(
            "One or more bytes appear before the ISA segment. A conformant X12 "
            "file begins with 'ISA' as its very first byte. Common causes are a "
            "UTF-8 byte-order mark, whitespace, or transport headers left in by "
            "the sender. x12-tidy strips them and continues; the reported "
            "bytes are what was removed."
        ),
    ),
    Code.ISA_INTERCHANGE_TOO_SHORT: CodeMeta(
        default_severity="fatal",
        title="Too short to be an X12 interchange",
        explanation=(
            "Fewer than 109 bytes follow the 'ISA' tag -- not enough room for a "
            "105-byte ISA line, its segment terminator, and a 'GS' header. A "
            "real interchange (ISA / GS / ST / ... / SE / GE / IEA) is far "
            "longer, so there is nothing to recover."
        ),
    ),
    Code.ISA_GS_NOT_FOUND: CodeMeta(
        default_severity="fatal",
        title="No GS header found after the ISA segment",
        explanation=(
            "x12-tidy locates the end of the ISA line by finding the 'GS' "
            "functional-group header that follows it (matched as 'GS' plus the "
            "element separator). No such header was found, so the ISA line "
            "cannot be bounded."
        ),
    ),
    Code.ISA_SEPARATOR_COUNT_LOW: CodeMeta(
        default_severity="fatal",
        title="Fewer than 16 element separators before GS",
        explanation=(
            "An ISA header carries exactly 16 element separators (ISA*ISA01*.."
            "*ISA16); that count is part of the minimum bar for calling a run "
            "an ISA line at all. The run before the 'GS' header holds fewer -- "
            "element separators were removed, or the 'GS' anchored on is a "
            "false match inside earlier data. Every candidate ISA tag was "
            "tried; none produced a 16-separator run. This is not an ISA line "
            "and is not recoverable."
        ),
    ),
    Code.ISA_NO_FUNCTIONAL_GROUP: CodeMeta(
        default_severity="fatal",
        title="ISA segment is not bounded by a GS functional-group header",
        explanation=(
            "Every ISA interchange opens a GS functional group, and x12-tidy "
            "ends the ISA line at that GS header. A 'GS' + element separator "
            "was found, but the run of bytes to it holds more than the 16 "
            "element separators an ISA header has -- so it is not the header. "
            "Either there is no GS envelope and the match lies inside a later "
            "segment's data, or the element separator occurs inside ISA06 / "
            "ISA08 data (an unparseable segment). The ISA line cannot be "
            "bounded; not recoverable."
        ),
    ),
}


def meta(code: Code) -> CodeMeta:
    """Registry row for ``code`` (raises :class:`KeyError` if unregistered)."""
    return META[code]


def resolved_severity(code: Code) -> Severity:
    """The severity to report ``code`` at, right now.

    This is the single report-time resolution point.  Today it is just the
    registry default; when the user-config layer lands it becomes
    ``config override -> registry default`` (and may return ``"ignore"``).
    """
    return META[code].default_severity


def all_codes() -> list[Code]:
    """Every registered code, ordered by area then code string."""
    return sorted(Code, key=lambda c: (AREAS.index(c.area), c.value))
