# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""The interchange-envelope layer.

Everything that locates and cleans the X12 interchange envelope -- ISA/IEA,
GS/GE, ST/SE -- and renders a verdict on it. It stops at transaction-set
business content, which is where the next package begins.

* :mod:`x12_tidy.envelope.isa` -- locate the ISA line, recover the delimiters,
  reconstruct the canonical 105-byte line.
* :mod:`x12_tidy.envelope.structure` -- split the interchange into segments,
  drop the empty pieces, assemble the cleansed payload (``clean_payload``).
* :mod:`x12_tidy.envelope.qaqc` -- envelope / control-number / count QA/QC,
  once a payload exists (``check_payload``).
* :mod:`x12_tidy.envelope.tidy` -- the one-call entry point: ``tidy(dirty)``
  runs ``clean_payload`` then ``check_payload``.

:mod:`x12_tidy.diagnostics` (the finding record and the code registry) is
shared and stays at the top level.
"""

from __future__ import annotations

from x12_tidy.envelope.isa import (
    ReconstructedIsaLine,
    clean_isa_line,
    extract_isa_line,
    reconstruct_isa_line,
    split_isa_line,
)
from x12_tidy.envelope.qaqc import EnvelopeFacts, QaQcResult, check_payload
from x12_tidy.envelope.structure import ReconstructedPayload, clean_payload
from x12_tidy.envelope.tidy import TidyResult, tidy

__all__ = [
    "tidy",
    "TidyResult",
    "clean_payload",
    "ReconstructedPayload",
    "check_payload",
    "QaQcResult",
    "EnvelopeFacts",
    "clean_isa_line",
    "reconstruct_isa_line",
    "extract_isa_line",
    "split_isa_line",
    "ReconstructedIsaLine",
]
