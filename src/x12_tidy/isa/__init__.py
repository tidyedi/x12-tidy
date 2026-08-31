# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""ISA interchange-envelope checks.

* :func:`extract_isa_line` -- Step 1: return the ISA line (``ISA`` .. before
  ``GS``).
* :func:`split_isa_line` -- Step 2, slice 1: recover the four delimiters from
  that run.
"""

from __future__ import annotations

from x12_tidy.isa.delimiters import IsaDelimiters, split_isa_line
from x12_tidy.isa.isa_line import IsaLineResult, extract_isa_line

__all__ = [
    "IsaLineResult",
    "extract_isa_line",
    "IsaDelimiters",
    "split_isa_line",
]
