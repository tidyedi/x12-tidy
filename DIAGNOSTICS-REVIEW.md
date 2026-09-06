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

- **47 codes** reviewed. **2 removed** (`isa.line-length`, `isa.segment-terminator-noncanonical`), **1 severity change** (`isa.segment-terminator-stripped` → fatal), **4 renamed**, **10 more reworded**, **29 accepted unchanged** — all ✅ done and on `main` except the research-gated wording (3 codes) and the `isa.identifier-utf16` transcode.
- **1 research blocker** gates the wording of `isa.element-separator-invalid`, `isa.segment-terminator-invalid`, `isa.delimiter-misaligned` and the `trailing-junk`/`trailing-newline` decision.
- **1 gap** → possible new code (ST/SE cardinality).
- **`isa.identifier-utf16` transcode = an explicit TODO for a later discussion** (user) — do not implement without a go-ahead.

### Severity / existence changes

| code | change | status |
|---|---|---|
| `isa.line-length` | **removed** — unreachable guard | ✅ on `main` (#67) |
| `isa.segment-terminator-noncanonical` | **removed** — non-`~` terminator is the sender's lawful choice, not a deviation | ✅ done (this PR) |
| `isa.segment-terminator-stripped` | error → **fatal** — refuse, stop fabricating `~` | ✅ done (this PR) |
| `isa.identifier-utf16` | fatal → **warning** — transcode UTF-16→single-byte + warn | 🔬 TODO for a later discussion; gated on the delimiter research + an explicit go-ahead |

---

## Full table

`slug →` = rename. Blank disposition = accepted as-is.

| code | sev | status | disposition |
|---|---|---|---|
| `isa.component-separator-invalid` | error | ✔️ | — |
| `isa.delimiter-collision` | fatal | ✔️ | — |
| `isa.delimiter-misaligned` | fatal | 🔬 | reword pending the delimiter research (name ISA16, name the "separator inside ISA06/ISA08" cause, drop "delimiter-shaped bytes") |
| `isa.element-embedded-newline` | warning | ✔️ | — |
| `isa.element-overflow` | fatal | ✔️ | — |
| `isa.element-separator-invalid` | fatal | 🔬 | reword pending research (rests on "delimiters are non-alphanumeric" — unconfirmed) |
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
| `isa.segment-terminator-invalid` | fatal | 🔶 done / 🔬 | speculation line dropped (this PR); gate kept. Retitle still pending the delimiter research. Co-fire with `isa.trailing-junk` left for later |
| `isa.segment-terminator-noncanonical` | — | ✅ removed | this PR — code, emit site, and `_RECONSTRUCTION_OWNS` entry all gone; a non-`~` terminator is now preserved silently |
| `isa.segment-terminator-stripped` | error → **fatal** | ✅ done | this PR — `split_isa_line` now refuses (returns not-usable) instead of fabricating `~`; reworded; removed from `_RECONSTRUCTION_OWNS`; `CANONICAL_TERMINATOR` constant deleted |
| `isa.separator-count-low` | fatal | ✔️ | — (pairs with `isa.separator-count-high`) |
| `isa.identifier-lowercase` (was `isa.tag-lowercase`) | error | ✅ renamed | branch `refactor/tag-to-identifier` (`f08294b`). "tag" → "segment identifier" done (slug, enum, title, explanation, `isa_line.py` message) |
| `isa.identifier-utf16` (was `isa.tag-utf16`) | fatal | ✅ renamed / 🔬 severity | Rename done (`f08294b`). **STILL A TODO FOR LATER DISCUSSION** (user, do not implement yet): fatal → warning via transcode UTF-16→single-byte + warn — endianness is already detected (`I\x00S\x00A` LE vs `\x00I\x00S\x00A` BE), valid X12 is all-ASCII so lossless. "How to ingest" guidance → future `intake` package. Gated on the delimiter research + an explicit go-ahead |
| `isa.trailing-junk` | warning | 🔬 | Keep for genuine foreign bytes (comment, transport framing). Resolve the consistency gap: identical junk after `GS~`/`ST~`/etc. is stripped silently by `split_segments` — flag uniformly (likely `structure.*`) or strip silently everywhere |
| `isa.trailing-newline` | warning | 🔬 | Decision tree: **if a CR/LF segment-terminator suffix is conformant** → drop it. **If not** → merge with `isa.trailing-junk` into one `isa.content-after-terminator`. Separate bug regardless: a `\r\n`-terminated file with no `~` → the 1-byte terminator rule takes `\r` as terminator, `\n` as trailing → spurious finding about half a line ending |
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

## Research blocker

**What bytes are legal X12 delimiters?** The model wrongly said "punctuation";
non-alphanumeric non-punctuation bytes (control chars `0x1C`–`0x1F`, etc.) are
legal in practice. Get the exact X12.6 statement, add it as a cited assumption
alongside A1–A5 (see the assumptions note), then align:

- `isa.element-separator-invalid`, `isa.segment-terminator-invalid`, `isa.delimiter-misaligned` — wording
- `isa.trailing-junk` / `isa.trailing-newline` — whether a CR/LF suffix is even a deviation
- `isa.tag-utf16` — unblocks the transcode change

Also to confirm: whether X12.6 sanctions a CR/LF **segment-terminator suffix**.

---

## Possible new code (not decided)

- **ST/SE element cardinality** — nothing flags an unexpected extra element in
  `ST` or `SE` (`SE*5*0001*JUNK~` passes silently). Would be a new `st.*` code.

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
| research-gated wording (3 codes) + `trailing-*` decision | not started — needs the X12.6 delimiter rule |
| `isa.identifier-utf16` transcode | not started — explicit later-discussion TODO |
| ST/SE cardinality | not started — undecided |
| 4 note **PDFs** re-printed | ✅ this PR — regenerated from the fixed HTML (headless Chrome) |
