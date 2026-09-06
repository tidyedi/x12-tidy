# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""x12-tidy: validate and repair malformed ANSI X12 EDI documents.

The free command-line tool and Python library behind TidyEDI
(https://tidyedi.com). See ``docs/design.md`` for the design.

The one call most callers want::

    from x12_tidy import tidy
    result = tidy(dirty_bytes)      # -> TidyResult

* :mod:`x12_tidy.envelope` -- locate and clean the interchange envelope
  (ISA/IEA, GS/GE, ST/SE); ``tidy``, ``clean_payload``, ``check_payload`` are
  re-exported here for convenience.
* :mod:`x12_tidy.diagnostics` -- the finding record (``Diagnostic``) and the
  code registry, shared by every layer.
"""

from x12_tidy.envelope import (
    EnvelopeFacts,
    QaQcResult,
    ReconstructedIsaLine,
    ReconstructedPayload,
    TidyResult,
    check_payload,
    clean_isa_line,
    clean_payload,
    tidy,
)

__version__ = "0.1.0"

__all__ = [
    "tidy",
    "TidyResult",
    "clean_payload",
    "ReconstructedPayload",
    "check_payload",
    "QaQcResult",
    "EnvelopeFacts",
    "clean_isa_line",
    "ReconstructedIsaLine",
]
