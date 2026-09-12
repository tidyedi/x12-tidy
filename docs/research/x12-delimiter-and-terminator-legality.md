# Research: what bytes are legal X12 delimiters, and is CR/LF around the segment terminator conformant?

**Date:** 2026-09-06
**Reason:** the `codes.py` review (`DIAGNOSTICS-REVIEW.md`) parked the wording of
three diagnostics and the existence of a fourth on an unconfirmed premise — that
X12 delimiters must be drawn from some restricted character set ("punctuation",
"non-alphanumeric"). This note settles the premise from primary sources and
records every source consulted.

This is a research log, not an engineering note. The durable conclusions live as
assumptions **A6** and **A7** in the assumptions memory; the code dispositions
live in `DIAGNOSTICS-REVIEW.md`.

---

## Question 1 — which byte values may be used as the four delimiters?

### Finding

**The X12 standard defines no permitted character set for delimiters.** A
delimiter may be any byte. Only two rules constrain the choice:

1. **Uniqueness.** The data element separator, component (sub-element) separator,
   repetition separator, and segment terminator must all be different from one
   another. A character assigned as one delimiter cannot also serve as another.
2. **Non-collision with data.** Once a byte is named as a delimiter in the ISA
   header, it must not appear as data in any element value anywhere in the
   interchange — with the single exception of its incidental appearance inside a
   binary (`BIN` / `BDS`) data element, whose length is counted, not delimited.

Everything else is convention. The asterisk / caret / colon / tilde set is what
ASC X12 happens to use in its Technical Report examples; the standard states
outright that delimiters are **not restricted** to those. A delimiter **may be a
non-printable control character** (e.g. the C0 information separators
`0x1C`–`0x1F`), and choosing a byte from *outside* the basic and extended
character sets is in fact the recommended practice, precisely because such a byte
cannot collide with data (rule 2 becomes impossible to violate).

### Primary sources

- **X12.6 (Application Control Structure), paragraph 3.4** — quoted consistently
  across the X12 Requests for Interpretation below:
  > "Delimiters are specified in the interchange header and shall not be used in
  > a data element value elsewhere in the interchange with the exception of their
  > possible appearance in the binary data element."

- **X12 RFI #2026 — "Delimiter in non-comp field"**
  <https://x12.org/resources/requests-for-interpretation/rfi-2026-delimiter-non-comp-field-0>
  Q: may a non-composite element (835 NM109) contain the byte used as the
  component element separator? A: no — cites X12.6 §3.4; *"a character identified
  in the ISA16 as the Component Element Separator must not be used elsewhere in
  the interchange as a data element character. The sender bears sole
  responsibility."* Also cites the 005010X221 835 TR3, Appendix B,
  **§B.1.1.2.5**: *"Once specified in the interchange header, the delimiters are
  not to be used in a data element value elsewhere in the interchange."*

- **X12 RFI #1815 — "Delimiters in data fields"**
  <https://x12.org/resources/requests-for-interpretation/rfi-1815-delimiters-data-fields>
  > "The X12 standard does not allow characters assigned as delimiters to be used
  > as characters within the data elements of an interchange. This is true for
  > all four delimiters and applies to both simple and composite data elements."

  And the key clarification that there is **no blanket ban on any character**:
  > "the asterisk, caret, colon, and tilde may be used compliantly in data
  > elements of an interchange that does not assign them as delimiters. Only the
  > delimiters assigned in that specific interchange cannot be used within its
  > data elements."

  References X12.5 (Interchange Control Structures) and TR3 Appendix B.

### Secondary sources (corroborating, not authoritative)

- **Oracle / Sun B2B Suite — ASC X12 OTD Library User's Guide, "Setting Delimiters"**
  <https://docs.oracle.com/cd/E19398-01/820-1278/agecg/index.html>
  Default set: `~` segment terminator, `*` element separator, `:` sub-element,
  `+` repetition (4020+). *"There is flexibility in the delimiters that are used,
  and no suggested delimiters are recommended as part of the X12 standards."*

- **EDIdEv — "Delimiters"**
  <https://secure.edidev.net/edidev-ca/help/Using/Using_Delimiters/Using_Delimiters.htm>
  States the uniqueness rule; does not restrict the character set. Notes the
  Group Separator (`0x1D`) / Unit Separator (`0x1F`) / File Separator (`0x1C`)
  control characters can serve as element separator / component separator /
  segment terminator respectively — i.e. control-character delimiters are normal.

- **IntuitionLabs — "X12 EDI Format: A Technical Guide"**
  <https://intuitionlabs.ai/articles/x12-edi-format-technical-guide>
  > "Characters such as `*`, `:`, `~`, and `^` are common examples, not universal
  > defaults ... trading partners can agree to use other valid delimiter
  > characters."
  Also: delimiters may be *"non-printable characters, or printable characters
  outside of the basic and extended character sets"* (attributes this to TR3
  Appendix **§B.1.1.2.2** and **§B.1.1.2.3**), and notes that to configure a
  control-character delimiter in tooling one passes its escaped UTF-16 code unit
  (`\uXXXX`).

- **SAP Community — "Separators in ANSI X12 EDI Message"**
  <https://blogs.sap.com/2014/04/05/separators-in-ansi-x12-edi-message/>
  Same default set; same "configurable, must not appear in data" framing.

### Not obtained

- The verbatim text of X12.6 §3.4 and of TR3 Appendix B §B.1.1.2.2–B.1.1.2.5
  (the standard and the TR3s are paywalled). Every RFI above quotes §3.4
  identically, so the wording is reliable second-hand.
- The DLA/DLMS ADC 1275 "Special Characters and Delimiters" PDF
  (<https://www.dla.mil/Portals/104/Documents/DLMS/ADC/ADC_1275_DLMS_Spec_Characters_Delimiters.pdf>)
  — server returns HTTP 403 to automated fetches. DLMS is known to map its
  delimiters onto the C0 information-separator control characters, which is
  itself evidence that control-character delimiters are standard-conformant.

---

## Question 2 — is a CR / LF around the segment terminator conformant?

### Finding

**Yes, at the sender's discretion.** A carriage return, a line feed, or both may
be used *as* a segment terminator, or appended *after* the segment terminator as
a suffix (the near-universal `~\r\n` layout). Equally, an interchange with no
CR/LF anywhere — every segment on one line — is conformant. None of these is a
deviation.

### Primary source

- **X12 RFI #2207 — "Segment Delimiters"**
  <https://x12.org/resources/requests-for-interpretation/rfi-2207-segment-delimiters>
  Q: *"Are carriage returns, line feeds, or a combination of both acceptable to
  be used as a segment terminator?"*
  A: *"these characters are recognized as valid for use in EDI interchanges at
  the discretion of the sender, as noted in **X12.5 section 4.3** and **section
  A.3.1**."* Adds that trading-partner agreements are outside the standard.

### Secondary sources

- **BizTalk Server docs — "Segment terminator for an X12 interchange"** and
  **"Configuring Fallback Charset and Separator Properties (X12)"**
  <https://learn.microsoft.com/en-us/previous-versions/troubleshoot/biztalk/accelerators/segment-terminator-x12-encoded-interchange>
  <https://learn.microsoft.com/en-us/biztalk/core/configuring-fallback-charset-and-separator-properties-x12>
  Model the terminator as *terminator byte + optional suffix* where suffix ∈
  {None, CR, LF, CR LF}. Confirms the receiver must read the delimiters from the
  ISA rather than assume them.

- **Tek-Tips — "CRLF use for a segment delimiter in X12"**
  <https://www.tek-tips.com/threads/crlf-use-for-a-segment-delimiter-in-x12.676585/>
  and **walmartlabs/gozer #45 — "Support EDI X12 files that have all segments on
  one line"** <https://github.com/walmartlabs/gozer/issues/45>
  Practitioner consensus: CR/LF is optional formatting; a single-line interchange
  is valid; parsers must not depend on line breaks.

### Not obtained

- Verbatim X12.5 §4.3 / §A.3.1 (paywalled). RFI #2207 is a direct quote of the
  operative clause.
- Confirmation of whether the standard treats a CR/LF *suffix* (terminator byte
  then CR/LF) distinctly from CR/LF *as* the terminator. RFI #2207 answers only
  the "as the terminator" form explicitly; tooling universally accepts the suffix
  form, and A7 is written to cover both. If a stricter reading is ever needed,
  the suffix case is the one to revisit.

---

## How this maps to the diagnostics under review

See `DIAGNOSTICS-REVIEW.md` → "Research blocker — RESOLVED" for the agreed
dispositions. In brief:

| code | effect of this research | status |
|---|---|---|
| `isa.element-separator-invalid` | premise ("X12 element separators are non-alphanumeric") is **not a standards rule**; keep the `fatal` gate as a *structural-recoverability* heuristic, reword the message to say so | ✅ done |
| `isa.segment-terminator-invalid` | same — keep the gate, drop the standards claim from the prose | ✅ done |
| `isa.delimiter-misaligned` | reword: name ISA16, name the "byte equal to the element separator inside ISA06/ISA08" cause | ✅ done |
| `isa.trailing-newline` | **removed** — a bare CR/LF/CRLF after the ISA terminator is conformant (A7); kept in the tail, out of the canonical line, not flagged | ✅ done |
| `isa.trailing-junk` | **kept** for genuine foreign bytes only (spaces, comment, transport framing) | ✅ done |
| `\r\n` terminator | CR immediately followed by LF normalises to LF, CR dropped as DOS framing — **not unconditional**: a lone CR with nothing after it stays as the sender's own 1-byte terminator, untouched; whether the standard treats a CR/LF *suffix* differently from CR/LF *as* the terminator itself is still unresolved (see "Not obtained" above) | ✅ done |
| `isa.identifier-utf16` | fatal → **warning** — a UTF-16 buffer is transcoded to single-byte (byte order from the BOM or which "ISA" marker is found) and re-parsed rather than refused | ✅ done |

A concrete artifact that exercises `isa.separator-count-high` (and, before its
removal, `isa.trailing-newline`) is checked in at
`samples/dlms-831-application-control-totals.edi`; see `samples/README.md`.

---

## Search trail (queries run 2026-09-06)

1. `ASC X12.6 delimiters definition "segment terminator" "data element separator" allowed characters rule`
2. `X12.6 "basic character set" "extended character set" delimiters control characters IS1 IS2 IS3 IS4 segment terminator`
3. `X12.6 delimiters "should be selected" OR "delimiter characters" recommended asterisk tilde control character hex "1D" segment terminator EDI`
4. `X12 segment terminator carriage return line feed after tilde "suffix" OR "CR/LF" conformant EDI standard`
5. `x12.org RFI segment terminator carriage return line feed permitted whitespace between segments`

Pages fetched: RFI #1815, RFI #2026, RFI #2207 (x12.org); BizTalk X12 character-set
page (learn.microsoft.com); EDIdEv delimiters page; IntuitionLabs technical guide.
Fetch failures: dla.mil ADC 1275 PDF (403), edi.aaltsys.info (connection refused).
