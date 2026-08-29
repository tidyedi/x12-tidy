"""ISA interchange-envelope checks.

* :func:`extract_isa_line` -- Step 1: return the ISA line (``ISA`` .. before
  ``GS``).
"""

from __future__ import annotations

from x12_tidy.isa.isa_line import IsaLineResult, extract_isa_line

__all__ = ["IsaLineResult", "extract_isa_line"]
