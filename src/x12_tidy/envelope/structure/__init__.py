# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Whole-interchange structure.

The ISA-line work (:mod:`x12_tidy.envelope.isa`) stops at the header. This package picks
up the rest of the interchange.

* :func:`split_interchanges` -- split raw bytes into one chunk per
  ``ISA``..``IEA`` interchange, for a flat file holding more than one.
* :func:`split_segments` -- split *one* interchange into its raw segments.
* :func:`drop_empty_segments` -- drop the empty pieces two terminators in a row
  leave behind.
* :func:`clean_payload` -- assemble the cleansed whole-file payload: clean ISA
  line + clean (empty-free) segments, rejoined on the sender's terminator.

All but ``clean_payload`` are mechanical transforms: no diagnostics, no
validation, no refusal. ``clean_payload`` is the one-call pipeline built on
``split_segments`` and the ISA-line work, and it does refuse (propagating the
ISA phase's fatal) when there is no ISA line to build from. Envelope QA/QC runs
later, after reconstruction. ``split_interchanges`` is a level above all of
these -- it decides what one call to the rest of the pipeline should even see;
:func:`x12_tidy.envelope.tidy.tidy` is what loops it.
"""

from __future__ import annotations

from x12_tidy.envelope.structure.interchanges import split_interchanges
from x12_tidy.envelope.structure.payload import ReconstructedPayload, clean_payload
from x12_tidy.envelope.structure.segments import (
    drop_empty_segments,
    split_elements,
    split_segments,
)

__all__ = [
    "split_interchanges",
    "split_segments",
    "drop_empty_segments",
    "split_elements",
    "ReconstructedPayload",
    "clean_payload",
]
