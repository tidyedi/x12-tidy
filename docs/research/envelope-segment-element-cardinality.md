# Research: element cardinality of the envelope control segments across X12 releases

**Date:** 2026-09-06
**Reason:** the `codes.py` review parked "ST/SE element cardinality" as a possible
new diagnostic (`SE*8*0001*JUNK~` passes silently today). Before designing that
check we need the authorized element count for each envelope segment, and whether
it is stable across X12 releases.

**Method:** the control-segment structure lives in X12.5 (Interchange Control
Structures) and X12.6 (Application Control Structure); Stedi mirrors the segment
dictionary per release at `stedi.com/edi/x12-<release>/segment/<SEG>`.

Check the **earliest** release (003010) and the **latest** (008010) first. If
they agree, every release in between agrees — done, no further checks. If they
differ, bisect the release list to find where it changed.

- ISA, GS, GE, SE, IEA — 003010 and 008010 identical → no bisect.
- ST — 003010 = 2, 008010 = 3 → bisect: 005010 = 3, so the change is at or below
  005010; 004010 = 2 and 004020 = 3, and those are consecutive releases →
  pinned: the change is release **004020**.

---

## Result

| segment | authorized data elements | stable across releases? |
|---|---|---|
| **ISA** | **16** (ISA01–ISA16) | **yes** — 16 in every release that defines ISA |
| **GS**  | **8** (GS01–GS08) | **yes** — 8 from 003010 through 008010 |
| **GE**  | **2** (GE01–GE02) | **yes** |
| **ST**  | **2** through 004010; **3** (ST03 added, optional) from **004020** onward | **NO — changed once, at 004020** |
| **SE**  | **2** (SE01–SE02) | **yes** — 2 from 003010 through 008010 |
| **IEA** | **2** (IEA01–IEA02) | **yes** |

So five of the six are fixed for the life of the standard. **ST is the only one
that changed**, and only once.

---

## ST — the one moving part

| release | ST elements | ST03 |
|---|---|---|
| 003010 | 2 | absent |
| 003060 | 2 | absent |
| 004010 | 2 | absent |
| **004020** | **3** | **added** — element 1705, *Implementation Convention Reference*, **optional** |
| 004030 | 3 | present |
| 005010 | 3 | present |
| 007010 | 3 | present |
| 008010 | 3 | present |

Key points:

- **ST03 is optional in every release that has it.** A 2-element `ST*850*0001~`
  is conformant in *all* releases, before and after 004020. What changed at
  004020 is the *maximum* legal element count, 2 → 3.
- ST03 carries the implementation-convention reference (the same kind of
  version/guide string as GS08). HIPAA TR3s from 005010 onward *require* it by
  convention, but that is an implementation-guide rule, not the base standard.
- Translators (e.g. IBM Gentran 6.1+) accepted an ST03 before 004020; for
  **strict** reporting an ST03 on a pre-004020 interchange is a sender deviation
  to flag, not honour — same posture x12-tidy already takes for the ISA11
  repetition-separator cutoff at 00403 (see assumptions A4).

---

## ISA — a note on availability, not count

Stedi documents ISA only from **003040** onward; it reports "Segment ISA is not
present in X12 Release 3010". The pre-003040 interchange envelope predates the
modern fixed-length ISA. Where ISA exists it is always 16 elements. This matches
assumption **A2** (16 elements, 003xxx–008xxx; 002xx functionally extinct).
`GE`/`SE`/`ST` exist back to 003010; `IEA` tracks `ISA`.

---

## Implication for the cardinality diagnostic (design input, not decided)

If x12-tidy adds an "envelope segment has the wrong element count" check, the
rule table is:

| segment | rule |
|---|---|
| ISA | exactly 16 — **already enforced** (the "exactly 16 element separators" gate) |
| GS  | exactly 8 |
| GE  | exactly 2 |
| SE  | exactly 2 |
| IEA | exactly 2 |
| ST  | 2 or 3; a present ST03 is standards-valid only when the interchange version (ISA12 / GS08) ≥ 004020; **ST04 or beyond is always invalid** |

**Shipped (2026-09-06): the coarse rule.** `structure.segment-element-count`
(error) uses exactly the table above *except* the ST03 version gate: a 3-element
`ST` is accepted in every release. Rationale and the plan to revisit are in
`DIAGNOSTICS-REVIEW.md` → "Deferred refinement — no version gate on ST03". In
short: a pre-004020 ST03 is a narrow edge, the interchange version is already in
hand so the gate is cheap to add later, and its severity is itself undecided.
Natural time to revisit: the transaction-set content parser, which will validate
every segment against a release-specific dictionary anyway.

---

## Sources

Per-release segment dictionaries (Stedi), `stedi.com/edi/x12-<release>/segment/<SEG>`.
Pages that establish each row (endpoints, plus the ST bisect path):

- GS / GE / SE / IEA — releases `003010` and `008010` (identical → done)
- ISA — `003010` (not present), `003040` (16), `008010` (16)
- ST — `003010` (2), `008010` (3); bisect `005010` (3), `004010` (2), `004020` (3)

Corroborating / background:

- ST03 = *Implementation Convention Reference*, optional, precedence over GS08:
  <https://www.stedi.com/edi/x12/segment/ST>
- IBM — "What are the segments ST/03 (ASC X12) and UNH/06 (EDIFACT)?" (Gentran
  6.1+ support): <https://www.ibm.com/support/pages/what-are-segments-st03-asc-x12-and-unh06-edifact-sci29456>
- Cleo — "Important Changes for X12 Version 5010" (5010 TR3s use ST03):
  <https://www.cleo.com/blog/important-changes-for-x12-version-5010-hipaa-transactions>
- Assumptions A2 / A4 (this repo's memory) — ISA 16 elements, per-version meaning
  drift.

**Not obtained:** verbatim X12.5/X12.6 control-segment tables per release (the
standard is paywalled). Stedi's per-release dictionary is a faithful mirror and
the 003010↔008010 endpoints agree on every count except ST.
