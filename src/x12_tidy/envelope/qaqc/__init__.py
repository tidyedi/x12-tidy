# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Envelope QA/QC -- runs once :func:`~x12_tidy.envelope.structure.clean_payload` has
produced a payload.

* :func:`check_payload` -- the one-call entry point.
* :class:`QaQcResult` -- its outcome: diagnostics + :class:`EnvelopeFacts`.
* :class:`EnvelopeFacts` -- plain facts about the interchange, not diagnostics.

See :mod:`x12_tidy.envelope.qaqc.envelope` for the full scope (what's checked, what's
deliberately not) and the severity contract.
"""

from __future__ import annotations

from x12_tidy.envelope.qaqc.envelope import EnvelopeFacts, QaQcResult, check_payload

__all__ = ["EnvelopeFacts", "QaQcResult", "check_payload"]
