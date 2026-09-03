# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Whole-interchange structure.

The ISA-line work (:mod:`x12_tidy.isa`) stops at the header. This package picks
up the rest of the interchange.

* :func:`split_segments` -- split the interchange into its raw segments. A
  mechanical transform: no diagnostics, no validation, no refusal. Envelope
  QA/QC runs later, after reconstruction.
"""

from __future__ import annotations

from x12_tidy.structure.segments import split_segments

__all__ = ["split_segments"]
