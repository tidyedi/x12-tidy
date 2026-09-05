# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Whole-interchange structure.

The ISA-line work (:mod:`x12_tidy.isa`) stops at the header. This package picks
up the rest of the interchange.

* :func:`split_segments` -- split the interchange into its raw segments.
* :func:`drop_empty_segments` -- drop the empty pieces two terminators in a row
  leave behind.
* :func:`clean_payload` -- assemble the cleansed whole-file payload: clean ISA
  line + clean (empty-free) segments, rejoined on the sender's terminator.

The first two are mechanical transforms: no diagnostics, no validation, no
refusal. ``clean_payload`` is the one-call pipeline built on top of them, and
it does refuse (propagating the ISA phase's fatal) when there is no ISA line to
build from. Envelope QA/QC runs later, after reconstruction.
"""

from __future__ import annotations

from x12_tidy.structure.payload import ReconstructedPayload, clean_payload
from x12_tidy.structure.segments import (
    drop_empty_segments,
    split_elements,
    split_segments,
)

__all__ = [
    "split_segments",
    "drop_empty_segments",
    "split_elements",
    "ReconstructedPayload",
    "clean_payload",
]
