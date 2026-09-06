# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

r"""Envelope QA/QC -- checks that run once a cleansed payload exists.

Scope: everything decided in the QA/QC design pass -- envelope pairing
(``GS``/``GE``, ``ST``/``SE``, and the interchange's own ``ISA``/``IEA``),
control-number and count agreement, control-number uniqueness, segment-identifier
shape (the A5 gate), the ``ISA12``/``GS08`` version check, ``ISA15`` usage
indicator validity, and ``GS07`` responsible-agency validity. Deliberately
**not** covered here (no decision made yet, do not add without one): ``ISA05``/
``ISA07`` qualifiers, ``ISA14``, ``GS01``, ``ST01`` shape, or any date/time
format check. Also not covered: multiple interchanges in one file -- `.segments`
already assumes a single interchange (a known gap in
:func:`~x12_tidy.envelope.structure.split_segments`, tracked separately, not fixed
here).

**Severity here means something different from the ISA-reconstruction phase.**
A payload already exists by the time this runs -- nothing found here can undo
that. So ``fatal`` is a display/trust signal ("don't use this payload"), never
a stop signal: every check below always runs to completion, on every segment,
regardless of what's found. Nothing in this module ever aborts the walk early.

One pass over the segment list (`.segments` from
:class:`~x12_tidy.envelope.structure.ReconstructedPayload`) drives all of it: a small
stack tracks the currently-open functional group and, inside it, the
currently-open transaction set. Pairing failures, nesting violations, and
count/control-number mismatches all fall out of that one walk. A missing
closer (``GE``/``SE``/``IEA``) is recovered from by treating the next
recognizable boundary as the assumed end, so everything nested inside a broken
envelope is still checked rather than skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from x12_tidy.diagnostics import Code, Diagnostic
from x12_tidy.envelope.structure.payload import ReconstructedPayload
from x12_tidy.envelope.structure.segments import split_elements

_VALID_USAGE_INDICATORS = (b"T", b"P", b"I")
_VALID_RESPONSIBLE_AGENCIES = (b"X", b"T")


def _is_numeric(value: bytes) -> bool:
    stripped = value.strip()
    return bool(stripped) and stripped.isdigit()


def _identifier_shape_valid(identifier: bytes) -> bool:
    first = identifier[:1]
    return bool(first) and first.isalpha() and first.isupper()


def _element(elements: list[bytes], index: int) -> bytes:
    """``elements[index]`` or ``b""`` if the segment is short that field --
    real-world truncated segments should not crash the walk."""
    return elements[index] if len(elements) > index else b""


@dataclass
class EnvelopeFacts:
    """Plain facts about the interchange, extracted during the QA/QC walk.

    Not diagnostics -- reported regardless of whether anything else is wrong,
    the way ``ISA15``'s Test/Production/Information disclosure works.
    """

    sender_qualifier: bytes
    sender_id: bytes
    receiver_qualifier: bytes
    receiver_id: bytes
    interchange_date: bytes
    interchange_time: bytes
    interchange_version: bytes
    usage_indicator: bytes
    group_versions: tuple[bytes, ...]
    functional_group_count: int
    transaction_set_count: int
    segment_count: int


@dataclass
class QaQcResult:
    """Outcome of :func:`check_payload`.

    ``facts`` is ``None`` only when there was no payload to check at all.
    ``diagnostics`` is every QA/QC finding -- always the complete list; see
    the module docstring on why ``fatal`` never truncates it.
    """

    facts: EnvelopeFacts | None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def was_clean(self) -> bool:
        return not self.diagnostics


@dataclass
class _TransactionSetContext:
    st02: bytes
    segment_count: int  # includes the ST segment itself


@dataclass
class _GroupContext:
    gs06: bytes
    transaction_set_count: int = 0
    st02_seen: set[bytes] = field(default_factory=set)
    current_st: _TransactionSetContext | None = None


class _Walker:
    def __init__(self, isa_elements: tuple[bytes, ...]) -> None:
        self._isa12 = _element(list(isa_elements), 11)
        self._isa13 = _element(list(isa_elements), 12)
        self.diagnostics: list[Diagnostic] = []
        self._gs_count = 0
        self._gs06_seen: set[bytes] = set()
        self._group_versions: list[bytes] = []
        self._total_transaction_sets = 0
        self._current_group: _GroupContext | None = None
        self._iea_elements: list[bytes] | None = None

    def run(self, segments: tuple[bytes, ...], element_separator: bytes) -> None:
        for segment in segments:
            elements = split_elements(segment, element_separator)
            identifier = elements[0] if elements else b""
            self._check_identifier_shape(identifier, segment)
            self._dispatch(identifier, elements, segment)

        if self._current_group is not None:
            self._close_group(self._current_group, None)  # never found GE
            self._current_group = None

        self._check_iea()

    def _check_identifier_shape(self, identifier: bytes, segment: bytes) -> None:
        if not _identifier_shape_valid(identifier):
            self.diagnostics.append(Diagnostic(
                Code.STRUCTURE_IDENTIFIER_INVALID,
                f"segment {segment!r} has a identifier that does not begin with an "
                "uppercase letter.",
            ))

    def _dispatch(self, identifier: bytes, elements: list[bytes], segment: bytes) -> None:
        if identifier == b"GS":
            if self._current_group is not None:
                self._close_group(self._current_group, None)  # never found GE
            self._current_group = self._open_group(elements)
            return
        if identifier == b"ST":
            if self._current_group is None:
                self._foreign_content(segment, "ST outside any functional group")
                return
            if self._current_group.current_st is not None:
                self._close_st(self._current_group, None)  # never found SE
            st02 = _element(elements, 2)
            self._current_group.current_st = _TransactionSetContext(
                st02=st02, segment_count=1
            )
            return
        if identifier == b"SE":
            group = self._current_group
            if group is None or group.current_st is None:
                self._foreign_content(segment, "SE with no matching ST")
                return
            group.current_st.segment_count += 1
            self._close_st(group, elements)
            return
        if identifier == b"GE":
            if self._current_group is None:
                self._foreign_content(segment, "GE with no matching GS")
                return
            self._close_group(self._current_group, elements)
            self._current_group = None
            return
        if identifier == b"IEA":
            if self._iea_elements is not None:
                self._foreign_content(
                    segment, "IEA with the interchange already closed"
                )
                return
            if self._current_group is not None:
                self._close_group(self._current_group, None)  # never found GE
                self._current_group = None
            self._iea_elements = elements
            return

        # An ordinary body segment -- must belong to an open transaction set.
        group = self._current_group
        if group is None or group.current_st is None:
            self._foreign_content(segment, "segment outside any transaction set")
            return
        group.current_st.segment_count += 1

    def _foreign_content(self, segment: bytes, reason: str) -> None:
        self.diagnostics.append(Diagnostic(
            Code.STRUCTURE_FOREIGN_CONTENT,
            f"segment {segment!r} is structurally out of place: {reason}.",
        ))

    def _open_group(self, elements: list[bytes]) -> _GroupContext:
        gs06 = _element(elements, 6)
        gs07 = _element(elements, 7)
        gs08 = _element(elements, 8)
        self._group_versions.append(gs08)

        if gs07 not in _VALID_RESPONSIBLE_AGENCIES:
            self.diagnostics.append(Diagnostic(
                Code.GS_RESPONSIBLE_AGENCY_INVALID,
                f"GS07 is {gs07!r}; must be 'X' or 'T'.",
            ))

        isa12_stripped = self._isa12.strip().lstrip(b"0")
        gs08_stripped = gs08.strip().lstrip(b"0")
        if not gs08_stripped.startswith(isa12_stripped):
            self.diagnostics.append(Diagnostic(
                Code.GS_VERSION_MISMATCH,
                f"GS08 {gs08!r} does not agree with ISA12 {self._isa12!r}.",
            ))

        return _GroupContext(gs06=gs06)

    def _close_st(
        self, group: _GroupContext, se_elements: list[bytes] | None
    ) -> None:
        st_ctx = group.current_st
        assert st_ctx is not None
        group.transaction_set_count += 1
        self._total_transaction_sets += 1

        if st_ctx.st02 in group.st02_seen:
            self.diagnostics.append(Diagnostic(
                Code.ST_CONTROL_NUMBER_DUPLICATE,
                f"ST02 {st_ctx.st02!r} is reused within this functional group.",
            ))
        else:
            group.st02_seen.add(st_ctx.st02)

        if se_elements is None:
            self.diagnostics.append(Diagnostic(
                Code.ST_MISSING_SE,
                f"ST {st_ctx.st02!r} has no matching SE.",
            ))
            group.current_st = None
            return

        se01 = _element(se_elements, 1)
        se02 = _element(se_elements, 2)

        if not _is_numeric(se01):
            self.diagnostics.append(Diagnostic(
                Code.ST_COUNT_NOT_NUMERIC,
                f"SE01 is {se01!r}; must be numeric.",
            ))
        elif int(se01.strip()) != st_ctx.segment_count:
            self.diagnostics.append(Diagnostic(
                Code.ST_SEGMENT_COUNT_MISMATCH,
                f"SE01 is {se01!r} but {st_ctx.segment_count} segment(s) "
                "were found (ST through SE inclusive).",
            ))

        if se02 != st_ctx.st02:
            self.diagnostics.append(Diagnostic(
                Code.ST_CONTROL_NUMBER_MISMATCH,
                f"ST02 {st_ctx.st02!r} does not match SE02 {se02!r}.",
            ))

        group.current_st = None

    def _close_group(
        self, group: _GroupContext, ge_elements: list[bytes] | None
    ) -> None:
        if group.current_st is not None:
            self._close_st(group, None)  # never found SE

        self._gs_count += 1
        if group.gs06 in self._gs06_seen:
            self.diagnostics.append(Diagnostic(
                Code.GS_CONTROL_NUMBER_DUPLICATE,
                f"GS06 {group.gs06!r} is reused within this interchange.",
            ))
        else:
            self._gs06_seen.add(group.gs06)

        if not _is_numeric(group.gs06):
            self.diagnostics.append(Diagnostic(
                Code.GS_CONTROL_NUMBER_NOT_NUMERIC,
                f"GS06 is {group.gs06!r}; must be numeric.",
            ))

        if ge_elements is None:
            self.diagnostics.append(Diagnostic(
                Code.GS_MISSING_GE,
                f"GS {group.gs06!r} has no matching GE.",
            ))
            return

        ge01 = _element(ge_elements, 1)
        ge02 = _element(ge_elements, 2)

        if not _is_numeric(ge01):
            self.diagnostics.append(Diagnostic(
                Code.GS_COUNT_NOT_NUMERIC,
                f"GE01 is {ge01!r}; must be numeric.",
            ))
        elif int(ge01.strip()) != group.transaction_set_count:
            self.diagnostics.append(Diagnostic(
                Code.GS_TRANSACTION_SET_COUNT_MISMATCH,
                f"GE01 is {ge01!r} but {group.transaction_set_count} "
                "transaction set(s) were found.",
            ))

        if ge02 != group.gs06:
            self.diagnostics.append(Diagnostic(
                Code.GS_CONTROL_NUMBER_MISMATCH,
                f"GS06 {group.gs06!r} does not match GE02 {ge02!r}.",
            ))

    def _check_iea(self) -> None:
        if self._iea_elements is None:
            self.diagnostics.append(Diagnostic(
                Code.STRUCTURE_MISSING_IEA,
                "no IEA segment closes the interchange.",
            ))
            return

        iea01 = _element(self._iea_elements, 1)
        iea02 = _element(self._iea_elements, 2)

        if not _is_numeric(iea01):
            self.diagnostics.append(Diagnostic(
                Code.STRUCTURE_COUNT_NOT_NUMERIC,
                f"IEA01 is {iea01!r}; must be numeric.",
            ))
        elif int(iea01.strip()) != self._gs_count:
            self.diagnostics.append(Diagnostic(
                Code.STRUCTURE_FUNCTIONAL_GROUP_COUNT_MISMATCH,
                f"IEA01 is {iea01!r} but {self._gs_count} functional group(s) "
                "were found.",
            ))

        if iea02 != self._isa13:
            self.diagnostics.append(Diagnostic(
                Code.STRUCTURE_CONTROL_NUMBER_MISMATCH,
                f"ISA13 {self._isa13!r} does not match IEA02 {iea02!r}.",
            ))

    def facts(self, isa_elements: tuple[bytes, ...], segment_count: int) -> EnvelopeFacts:
        els = list(isa_elements)
        isa15 = _element(els, 14).strip()
        return EnvelopeFacts(
            sender_qualifier=_element(els, 4),
            sender_id=_element(els, 5),
            receiver_qualifier=_element(els, 6),
            receiver_id=_element(els, 7),
            interchange_date=_element(els, 8),
            interchange_time=_element(els, 9),
            interchange_version=self._isa12,
            usage_indicator=isa15,
            group_versions=tuple(self._group_versions),
            functional_group_count=self._gs_count,
            transaction_set_count=self._total_transaction_sets,
            segment_count=segment_count,
        )


def check_payload(result: ReconstructedPayload) -> QaQcResult:
    """Run every decided QA/QC check against an already-cleansed payload.

    ``result.payload`` must not be ``None`` -- a refused cleanse has nothing
    to check, and this returns an empty result immediately if it is. See the
    module docstring for scope and the severity contract.
    """
    if result.payload is None or result.isa_result.decomposition is None:
        return QaQcResult(None, [])

    isa_elements = result.isa_result.elements
    isa15 = _element(list(isa_elements), 14).strip()

    diagnostics: list[Diagnostic] = []
    if isa15 not in _VALID_USAGE_INDICATORS:
        diagnostics.append(Diagnostic(
            Code.ISA_USAGE_INDICATOR_INVALID,
            f"ISA15 is {isa15!r}; must be 'T', 'P', or 'I'.",
        ))

    isa13 = _element(list(isa_elements), 12)
    if not _is_numeric(isa13):
        diagnostics.append(Diagnostic(
            Code.STRUCTURE_CONTROL_NUMBER_NOT_NUMERIC,
            f"ISA13 is {isa13!r}; must be numeric.",
        ))

    walker = _Walker(isa_elements)
    element_separator = result.isa_result.decomposition.element_separator
    walker.run(result.segments, element_separator)
    diagnostics.extend(walker.diagnostics)

    facts = walker.facts(isa_elements, len(result.segments))
    return QaQcResult(facts, diagnostics)
