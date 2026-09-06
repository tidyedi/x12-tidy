# Diagnostic code review — 2026-09

**Single source of truth for the `codes.py` registry review.** Every decision
lands here first. `docs/diagnostics.md` is the generated *current* state; this
file is the *review* state (what changes, what's accepted, what's blocked).

Status legend:

| | meaning |
|---|---|
| ✅ **done** | change is implemented (see branch) |
| 🔶 **decided** | agreed, not yet implemented |
| 🔬 **research** | blocked on confirming an X12 rule |
| ✔️ **accepted** | reviewed, no change (incl. by silence — an un-flagged code is accepted) |
| 💭 **open** | raised, not yet decided |

Rule: *if a code was not raised during the review, it is accepted as-is.*

---

## Summary

- **47 codes** reviewed. **3 removed** (`isa.line-length`, `isa.segment-terminator-noncanonical`, `isa.trailing-newline`), **2 severity changes** (`isa.segment-terminator-stripped` → fatal; `isa.identifier-utf16` → warning + transcode), **4 renamed**, **13 more reworded**, **~26 accepted unchanged**.
- Research blocker **RESOLVED** (2026-09-06, A6/A7). Items A–C on `main` (#74). D closed (no change). E (`\r\n`→`\n`) and F (`isa.identifier-utf16` transcode) **✅ done**.
- **Only open item:** envelope segment cardinality (add the code, or not).

### Severity / existence changes

| code | change | status |
|---|---|---|
| `isa.line-length` | **removed** — unreachable guard | ✅ on `main` (#67) |
| `isa.segment-terminator-noncanonical` | **removed** — non-`~` terminator is the sender's lawful choice, not a deviation | ✅ on `main` (#71) |
| `isa.trailing-newline` | **removed** — CR/LF suffix after the terminator is conformant (A7) | ✅ on `main` (#74) |
| `isa.segment-terminator-stripped` | error → **fatal** — refuse, stop fabricating `~` | ✅ on `main` (#71) |
| `isa.identifier-utf16` | fatal → **warning** — transcode UTF-16→single-byte + warn | ✅ done (branch `refactor/utf16-transcode`) |

---

## Full table

`slug →` = rename. Blank disposition = accepted as-is.

| code | sev | status | disposition |
|---|---|---|---|
| `isa.component-separator-invalid` | error | ✔️ | — |
| `isa.delimiter-collision` | fatal | ✔️ | — |
| `isa.delimiter-misaligned` | fatal | ✅ done | reworded: names ISA16 + "a byte equal to the element separator inside ISA06/ISA08"; "delimiter-shaped bytes" gone (branch `refactor/isa-delimiter-terminator-rewording`) |
| `isa.element-embedded-newline` | warning | ✔️ | — |
| `isa.element-overflow` | fatal | ✔️ | — |
| `isa.element-separator-invalid` | fatal | ✅ done | reworded — "X12 does not restrict which byte a sender may use as a delimiter, but a letter or digit cannot be told apart from data"; refuses on recoverability, not prohibition. Title → "letter or digit" |
| `isa.element-width` | error | ✔️ | — |
| `isa.gs-not-found` | fatal | ✅ done | reworded to contrast with `isa.separator-count-high` (this one = no `GS`+separator anywhere after ISA) |
| `isa.interchange-too-short` | fatal | ✔️ | — |
| `isa.isa11-not-standards-id` | error | ✅ done | retitled "ISA11 must be 'U' on versions before 00403"; explanation notes ISA11 became the repetition separator at 00403 |
| `isa.isa16-missing` | fatal | ✅ done | retitled "ISA16 is missing"; explanation names it as the component-separator element |
| `isa.leading-bytes` | warning | ✔️ | — |
| `isa.line-length` | — | ✅ removed | unreachable guard; on `main` (#67) |
| `isa.separator-count-high` (was `isa.no-functional-group`) | fatal | ✅ done | renamed (`ISA_SEPARATOR_COUNT_HIGH`), retitled "More than 16 element separators before GS", reworded to pair with `isa.separator-count-low` |
| `isa.no-identifier` (was `isa.no-tag`) | fatal | ✅ done | renamed (#67); title simplified to "No ISA segment in the file" (this PR) |
| `isa.repetition-separator-invalid` | error | ✔️ | — |
| `isa.repetition-separator-missing` | error | ✔️ | — |
| `isa.segment-terminator-invalid` | fatal | ✅ done | reworded — "X12 does not restrict delimiter bytes, but a letter or digit cannot be told apart from segment data". Title → "letter or digit". Gate kept |
| `isa.segment-terminator-noncanonical` | — | ✅ removed | this PR — code, emit site, and `_RECONSTRUCTION_OWNS` entry all gone; a non-`~` terminator is now preserved silently |
| `isa.segment-terminator-stripped` | error → **fatal** | ✅ done | this PR — `split_isa_line` now refuses (returns not-usable) instead of fabricating `~`; reworded; removed from `_RECONSTRUCTION_OWNS`; `CANONICAL_TERMINATOR` constant deleted |
| `isa.separator-count-low` | fatal | ✔️ | — (pairs with `isa.separator-count-high`) |
| `isa.identifier-lowercase` (was `isa.tag-lowercase`) | error | ✅ renamed | branch `refactor/tag-to-identifier` (`f08294b`). "tag" → "segment identifier" done (slug, enum, title, explanation, `isa_line.py` message) |
| `isa.identifier-utf16` (was `isa.tag-utf16`) | fatal → **warning** | ✅ done | `extract_isa_line` transcodes a UTF-16 buffer to single-byte (`decode_utf16` in `isa_line.py`; BOM or marker → byte order; Latin-1 with `replace`) and re-parses; `split_segments` does the same. Warning, not fatal. Offsets then index the transcoded bytes — stated in the finding. `finding-the-elusive-isa-line` note reversed accordingly (PDF not reprinted). Branch `refactor/utf16-transcode` |
| `isa.trailing-junk` | warning | ✅ done | now fires only for non-newline trailing bytes (spaces, comment, transport framing); a CR/LF suffix is unflagged. Body-level `split_segments` consistency gap left as item D |
| `isa.trailing-newline` | — | ✅ removed | CR/LF suffix after the terminator is conformant (A7, X12.5 §4.3 / RFI 2207). Enum, `CodeMeta`, emit site, `_RECONSTRUCTION_OWNS` all gone. `\r\n`-no-`~` 2-byte-terminator handling is item E |
| `isa.usage-indicator-invalid` | error | ✔️ | — |
| `isa.version-unrecognized` | warning | ✔️ | — |
| `gs.control-number-duplicate` | fatal | ✔️ | — |
| `gs.control-number-mismatch` | fatal | ✔️ | — |
| `gs.control-number-not-numeric` | fatal | ✔️ | — |
| `gs.count-not-numeric` | fatal | ✔️ | — |
| `gs.missing-ge` | fatal | ✔️ | — |
| `gs.responsible-agency-invalid` | error | ✅ done | retitled "GS07 does not name a known standards organization"; explanation cites element 455 and says X / T are the only values X12 defines for it |
| `gs.transaction-set-count-mismatch` | fatal | ✔️ | — |
| `gs.version-mismatch` | fatal | ✔️ | — |
| `st.control-number-duplicate` | fatal | ✔️ | — |
| `st.control-number-mismatch` | fatal | ✔️ | Reviewed — explanation is fine (names ST02 / SE02 specifically). SE holds SE01 (count) too; the code already checks it via `st.count-not-numeric` / `st.segment-count-mismatch` |
| `st.count-not-numeric` | fatal | ✔️ | — |
| `st.missing-se` | fatal | ✔️ | — |
| `st.segment-count-mismatch` | fatal | ✔️ | — |
| `structure.control-number-mismatch` | fatal | ✔️ | — |
| `structure.control-number-not-numeric` | fatal | ✔️ | — |
| `structure.count-not-numeric` | fatal | ✔️ | — |
| `structure.foreign-content` | fatal | ✅ done | retitled "Segment outside the envelope structure" |
| `structure.functional-group-count-mismatch` | fatal | ✔️ | — |
| `structure.missing-iea` | fatal | ✔️ | — |
| `structure.identifier-invalid` (was `structure.tag-shape-invalid`) | error | ✅ done | renamed (#67); retitled "A segment identifier does not begin with an uppercase letter"; explanation notes IDs may contain digits (`N1`, `PO1`, `G62`) (this PR) |

---

## Research blocker — RESOLVED 2026-09-06

**What bytes are legal X12 delimiters?** Answer: the standard defines **no
permitted character set**. Only two normative rules — (1) the four delimiters
must all differ (X12.6 §3.4; RFI #2026); (2) a delimiter byte must not appear as
data anywhere in the interchange except inside a binary element (X12.6 §3.4;
TR3 §B.1.1.2.5; RFI #1815, #2026). Delimiters are explicitly *not* restricted to
`* ^ : ~`, and **may be non-printable control characters** — that is the
recommended choice (TR3 §B.1.1.2.2–B.1.1.2.3). Recorded as assumption **A6**.

**CR/LF around the segment terminator** — valid at the sender's discretion,
X12.5 §4.3 / §A.3.1, RFI #2207. Recorded as assumption **A7**.

Alignment (dispositions):

- ✅ `isa.element-separator-invalid`, `isa.segment-terminator-invalid` — kept the
  `fatal` gate (an alphanumeric delimiter is structurally unrecoverable),
  reworded: dropped "X12 element separators are non-alphanumeric"; now says the
  byte can't be told apart from data so x12-tidy refuses "on that ground, not
  because the byte is forbidden". Titles changed "alphanumeric byte" → "letter or
  digit". Runtime messages aligned.
- ✅ `isa.delimiter-misaligned` — reworded: names ISA16 and "a byte equal to the
  element separator occurring inside ISA06 or ISA08 data"; dropped
  "delimiter-shaped bytes".
- ✅ `isa.trailing-newline` — **removed** (enum, `CodeMeta`, emit site,
  `_RECONSTRUCTION_OWNS`). A bare CR/LF/CRLF after the terminator is conformant
  (A7): kept in `IsaDecomposition.trailing`, out of the canonical line, not
  flagged.
- ✅ `isa.trailing-junk` — **kept**, now fires only for non-newline trailing
  bytes (spaces, comment, transport framing). Explanation note about
  `isa.trailing-newline` removed.
- ✅ **item D** — inter-segment junk consistency: **no change.** Newlines are
  already stripped silently at every boundary; the only asymmetry was that a
  stray *space* after the ISA terminator is reported (`isa.trailing-junk`) while
  spaces between body segments are stripped silently. Owner's call: works as is,
  not an issue.
- ✅ **item E** — `\r\n` terminator normalises to `\n`. `split_isa_line` maps a
  `\r` immediately followed by `\n` to a `\n` terminator (CR dropped as a DOS
  line ending); `split_segments` collapses `\r\n`→`\n` before splitting. A
  CRLF-delimited interchange now cleans to LF, not to a lone CR. Terminator
  stays one byte — no invariant change. A lone `\r` with no `\n` is still kept
  as the sender's choice. Docs + `delimiters-terminator.svg` updated.
- ✅ **item F** — `isa.identifier-utf16` fatal → **warning**. `decode_utf16`
  (`isa_line.py`) transcodes a UTF-16 buffer to single-byte; `extract_isa_line`
  and `split_segments` both call it and re-parse. Byte order from the BOM or from
  which marker is found. Every offset then indexes the transcoded bytes — the
  finding says so. The "why UTF-16 is fatal" note in
  `finding-the-elusive-isa-line` is now "why UTF-16 is transcoded" (PDF gated).

Items A–C on `main` (#74); D closed (no change); E on `main` (#75); F branch
`refactor/utf16-transcode`.

---

## Possible new code (not decided)

- **Envelope segment element cardinality** — nothing flags an unexpected extra
  element in `ST` / `SE` (`SE*8*0001*JUNK~` passes silently). Would be a new
  `st.*` / envelope code.

  Cardinality validated across releases 003010–008010
  (`docs/research/envelope-segment-element-cardinality.md`, 2026-09-06):

  | segment | authorized elements | stable? |
  |---|---|---|
  | ISA | 16 | yes — already enforced |
  | GS | 8 | yes |
  | GE | 2 | yes |
  | SE | 2 | yes |
  | IEA | 2 | yes |
  | ST | 2, or **3 from release 004020** (ST03 = Implementation Convention Reference, optional) | **changed once, at 004020** |

  ST is the only one that moves. ST03 is *optional* in every release that has it,
  so a 2-element ST is always valid; what changed at 004020 is the max, 2 → 3.
  A coarse rule ("ST 2–3, all others exact") needs no version logic; gating ST03
  on ISA12/GS08 ≥ 004020 is a refinement (same posture as the ISA11 `00403`
  cutoff). Open: whether pre-004020 ST03 warrants its own severity.

---

## Misleading `isa.gs-not-found` when byte 4 is not a delimiter — ✅ FIXED

Raised 2026-09-06 (owner). When the ISA element separators are stripped so that
byte 4 of the ISA segment is alphanumeric (e.g. an interchange pasted out of a
PDF: `ISA00 00 01...` with no `*`), `extract_isa_line` took byte 4 as the
separator by rule, built the boundary token `GS` + that byte (`GS0`), failed to
find it, and refused with **`isa.gs-not-found`** — misleading, because the `GS`
segment is present (`GSCT...`); the real defect is that **byte 4 is not a valid
delimiter**.

Root cause was ordering: `extract_isa_line` (locate) uses byte 4 as a *locating*
token before `split_isa_line` (stage 2, where `isa.element-separator-invalid`
lives) ever runs. When stage 1 refused, stage 2 never saw the run.

**Fix (done):** in `isa_line.py::_try_candidate`, the `gs_pos == -1` branch now
checks `element_separator.isalnum()` — if the derived separator is a letter or
digit, it returns **`isa.element-separator-invalid`** (fatal, root cause) instead
of `isa.gs-not-found`. Same severity, same refusal, accurate reason. The
"alphanumeric separator, GS at 106" case is unaffected (fast path, never reaches
this branch). "Invalid", not "missing" — a byte is present, it just cannot be a
delimiter; no `isa.element-separator-missing` code, `invalid` covers it. One test
case added to `tests/test_isa_line.py` `CASES`.

---

## Implementation tracking

| item | state |
|---|---|
| `DIAGNOSTICS-REVIEW.md` | on `main` (#67) |
| "tag" → "segment identifier" sweep (4 renames + prose) | ✅ on `main` (#67) |
| remove `isa.line-length` | ✅ on `main` (#67) |
| `docs/using-x12-tidy.md` | ✅ on `main` (#67) |
| envelope package (`x12_tidy.envelope`) | ✅ on `main` (#69) |
| `docs/images/` consolidation | ✅ on `main` (#70) |
| **11 decided review items** (rewords + the 2 behaviour changes) | ✅ done — this PR |
| top-level `from x12_tidy import tidy` re-export | ✅ this PR |
| `qaqc/envelope.py` → `qaqc/checks.py` | ✅ this PR |
| README / docs/README link to `using-x12-tidy.md` | ✅ this PR |
| research-gated wording — `isa.element-separator-invalid` / `isa.segment-terminator-invalid` / `isa.delimiter-misaligned` reword + remove `isa.trailing-newline` | ✅ on `main` (#74) (items A–C) |
| item D — inter-segment junk consistency | ✅ no change — owner's call, works as is |
| item E — `\r\n` terminator normalises to `\n` | ✅ branch `refactor/crlf-terminator-normalises-to-lf` |
| item F — `isa.identifier-utf16` fatal→warning transcode | ✅ branch `refactor/utf16-transcode` |
| envelope segment cardinality | not started — undecided (counts validated, A8) |
| 4 note **PDFs** re-printed | ✅ this PR — regenerated from the fixed HTML (headless Chrome) |
| delimiter/terminator legality research (A6, A7) + `docs/research/` note | ✅ branch `docs/delimiter-research-and-dlms-sample` |
| `isa.gs-not-found` → `isa.element-separator-invalid` when byte 4 is alnum | ✅ branch `docs/delimiter-research-and-dlms-sample` |
| `samples/` — DLMS 831 interchange + README | ✅ branch `docs/delimiter-research-and-dlms-sample` |
