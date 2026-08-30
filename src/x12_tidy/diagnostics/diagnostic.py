# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""The :class:`Diagnostic` record -- one finding.

Deliberately tiny and severity-free.  A diagnostic says *what* is wrong
(:class:`~x12_tidy.diagnostics.codes.Code`), *in prose* (``message``, built at
the call site with the specifics of this occurrence), and *where* (``offset``, a
byte position into the file).

Severity is **not** here.  It is resolved when results are reported, from the
registry default and any user-config override -- so a config loaded after
parsing still applies, and the same code cannot end up with different
severities depending on which module raised it.  See ``docs/design.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from x12_tidy.diagnostics.codes import Code


@dataclass(frozen=True)
class Diagnostic:
    code: Code
    message: str
    offset: int | None = None

    def __str__(self) -> str:
        loc = f" at byte {self.offset}" if self.offset is not None else ""
        return f"[{self.code.value}]{loc} {self.message}"
