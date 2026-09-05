# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""The whole-package entry point: cleanse, then QA/QC.

This is the product surface x12-tidy exists to provide: hand it a dirty EDI
file, get back (a) a cleansed payload to use if you want it, and (b) the
complete list of every deviation found -- both what made cleansing necessary
and what QA/QC found once there was a payload to check.

    dirty file
        |
        v
    clean_payload -- can't be cleansed? -> exit with a report, no payload
        |
        v (payload exists)
    check_payload -- always runs to completion, never truncated by severity
        |
        v
    payload + facts + every diagnostic found
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Diagnostic
from x12_tidy.qaqc import EnvelopeFacts, check_payload
from x12_tidy.structure import clean_payload


@dataclass
class TidyResult:
    """The whole pipeline's outcome.

    ``payload`` is ``None`` exactly when the file could not be cleansed at
    all -- nothing to QA/QC, and ``facts`` is ``None`` too. Otherwise
    ``facts`` is always populated, and ``diagnostics`` carries everything
    found across both phases, cleanse first.
    """

    payload: bytes | None
    facts: EnvelopeFacts | None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        return not self.diagnostics


def tidy(dirty: bytes) -> TidyResult:
    """Cleanse ``dirty``, then run QA/QC on the result. See the module
    docstring for the contract."""
    cleaned = clean_payload(dirty)
    if cleaned.payload is None:
        return TidyResult(None, None, list(cleaned.diagnostics))

    qaqc = check_payload(cleaned)
    return TidyResult(
        cleaned.payload, qaqc.facts, list(cleaned.diagnostics) + list(qaqc.diagnostics)
    )
