# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""ISA interchange-envelope checks.

* :func:`extract_isa_line` -- Step 1: return the ISA line (``ISA`` .. before
  ``GS``).
* :func:`split_isa_line` -- Step 2, slice 1: recover the four delimiters from
  that run.
* :func:`clean_isa_line` / :func:`reconstruct_isa_line` -- Step 2, slice 2:
  reconstruct the canonical 105-byte ISA line from the run and its delimiters.
"""

from __future__ import annotations

from x12_tidy.envelope.isa.delimiters import IsaDecomposition, split_isa_line
from x12_tidy.envelope.isa.isa_line import IsaLineResult, extract_isa_line
from x12_tidy.envelope.isa.reconstruct import (
    ReconstructedIsaLine,
    clean_isa_line,
    reconstruct_isa_line,
)

__all__ = [
    "IsaLineResult",
    "extract_isa_line",
    "IsaDecomposition",
    "split_isa_line",
    "ReconstructedIsaLine",
    "clean_isa_line",
    "reconstruct_isa_line",
]
