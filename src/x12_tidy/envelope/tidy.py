# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""The whole-package entry point: split, then cleanse and QA/QC each interchange.

This is the product surface x12-tidy exists to provide: hand it a dirty EDI
file -- one interchange, or a flat-file batch of several concatenated ones --
get back one :class:`TidyResult` per interchange found, each with (a) a
cleansed payload to use if you want it, and (b) the complete list of every
deviation found for that interchange -- both what made cleansing necessary and
what QA/QC found once there was a payload to check.

    dirty file
        |
        v
    split_interchanges -- one chunk per ISA..IEA, mechanical, no diagnostics
        |
        v (for each chunk, independently -- no delimiters or state shared)
    clean_payload -- can't be cleansed? -> exit with a report, no payload
        |
        v (payload exists)
    check_payload -- always runs to completion, never truncated by severity
        |
        v
    payload + facts + every diagnostic found, for *this* interchange

A chunk with no recoverable ``ISA`` at all produces a ``TidyResult`` with no
payload and no facts, same as the previous single-interchange contract. If
literally nothing in the file resembles an interchange, that is still exactly
one such result -- never an empty list -- so a caller always has something to
report to the person holding the bad file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Diagnostic
from x12_tidy.envelope.isa import decode_utf16, extract_isa_line
from x12_tidy.envelope.qaqc import EnvelopeFacts, check_payload
from x12_tidy.envelope.structure import clean_payload, split_interchanges


@dataclass
class TidyResult:
    """One interchange's outcome.

    ``payload`` is ``None`` exactly when this interchange could not be
    cleansed at all -- nothing to QA/QC, and ``facts`` is ``None`` too.
    Otherwise ``facts`` is always populated, and ``diagnostics`` carries
    everything found across both phases, cleanse first.
    """

    payload: bytes | None
    facts: EnvelopeFacts | None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        return not self.diagnostics


def tidy(dirty: bytes) -> list[TidyResult]:
    """Split ``dirty`` into interchanges, then cleanse and audit each one
    independently. See the module docstring for the contract.

    Always returns at least one result: a file with no recoverable ``ISA`` at
    all comes back as a single fatal-only result, the same shape as any other
    unparseable interchange, rather than an empty list.
    """
    chunks = split_interchanges(dirty)
    if not chunks:
        return [_refused(decode_utf16(dirty) or dirty)]

    results = [_tidy_one(chunk) for chunk in chunks]

    # split_interchanges' chunks are always contiguous and gap-free (see its
    # module docstring), so this is exactly how far into dirty it got.
    consumed = sum(len(chunk) for chunk in chunks)
    trailing = (decode_utf16(dirty) or dirty)[consumed:]
    if trailing.strip():
        # Real, un-recovered content after the last interchange found --
        # report why, rather than silently dropping it. Pure trailing
        # whitespace (a newline after the last IEA) is not this: that's
        # ordinary and every chunk before it already accounted for its own
        # trailing junk via isa.leading-bytes on the *next* chunk, so there
        # is nothing left to explain when there is no next chunk.
        results.append(_refused(trailing))

    return results


def _tidy_one(chunk: bytes) -> TidyResult:
    cleaned = clean_payload(chunk)
    if cleaned.payload is None:
        return TidyResult(None, None, list(cleaned.diagnostics))

    qaqc = check_payload(cleaned)
    return TidyResult(
        cleaned.payload, qaqc.facts, list(cleaned.diagnostics) + list(qaqc.diagnostics)
    )


def _refused(remainder: bytes) -> TidyResult:
    """A ``TidyResult`` for bytes that never even yielded an ISA line --
    carries only why, via the same Step 1 diagnostics ``clean_payload`` would
    have produced."""
    isa_result = extract_isa_line(remainder)
    return TidyResult(None, None, list(isa_result.diagnostics))
