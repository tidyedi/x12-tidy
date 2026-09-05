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

- **47 codes** reviewed. **1 removed**, **1 to remove**, **2 severity changes**, **4 renamed (✅ done)**, **10 more reword**, **29 accepted unchanged**.
- **1 research blocker** gates 3–5 items.
- **1 verified defect** beyond wording (`isa.segment-terminator-stripped`), resolved by the severity decision.
- **1 gap** → possible new code (ST/SE cardinality).
- **`isa.identifier-utf16` transcode = an explicit TODO for a later discussion** (user) — do not implement without a go-ahead.

### Severity / existence changes (the only 4)

| code | current | → | status |
|---|---|---|---|
| `isa.line-length` | fatal | **removed** — unreachable guard | ✅ branch `refactor/remove-isa-line-length` (`013e252`, unmerged) |
| `isa.segment-terminator-noncanonical` | warning | **removed** — non-`~` terminator is the sender's lawful choice, not a deviation | 🔶 |
| `isa.segment-terminator-stripped` | error | **fatal** — stop fabricating `~`; refuse | 🔶 |
| `isa.identifier-utf16` (was `isa.tag-utf16`) | fatal | **warning** — transcode UTF-16→single-byte + warn | 🔬 TODO for a later discussion; gated on the delimiter research + an explicit go-ahead |

---

## Full table

`slug →` = rename. Blank disposition = accepted as-is.

| code | sev | status | disposition |
|---|---|---|---|
| `isa.component-separator-invalid` | error | ✔️ | — |
| `isa.delimiter-collision` | fatal | ✔️ | — |
| `isa.delimiter-misaligned` | fatal | 🔶 / 🔬 | reword: name ISA16, name the "element separator inside ISA06/ISA08" cause, drop "delimiter-shaped bytes"; final wording waits on the delimiter research |
| `isa.element-embedded-newline` | warning | ✔️ | — |
| `isa.element-overflow` | fatal | ✔️ | — |
| `isa.element-separator-invalid` | fatal | 🔬 | reword pending research (rests on "delimiters are non-alphanumeric" — unconfirmed) |
| `isa.element-width` | error | ✔️ | — |
| `isa.gs-not-found` | fatal | 🔶 | reword to contrast with `isa.no-functional-group` / `separator-count-*`: THIS = no `GS`+separator appears anywhere after ISA |
| `isa.interchange-too-short` | fatal | ✔️ | — |
| `isa.isa11-not-standards-id` | error | 🔶 | retitle "ISA11 must be `U` on versions before 00403" |
| `isa.isa16-missing` | fatal | 🔶 | retitle to name ISA16 (it carries the component separator); drop "Nothing follows ISA15" |
| `isa.leading-bytes` | warning | ✔️ | — |
| `isa.line-length` | fatal | ✅ **removed** | unreachable; branch `refactor/remove-isa-line-length` |
| `isa.no-functional-group` | fatal | 🔶 | **`slug → isa.separator-count-high`** (`ISA_SEPARATOR_COUNT_HIGH`); pairs with `isa.separator-count-low`. A `GS`+separator was found but the run to it holds >16 element separators |
| `isa.no-identifier` (was `isa.no-tag`) | fatal | ✅ renamed | branch `refactor/tag-to-identifier` (`f08294b`). "tag" → "segment identifier" done. Title-simplification ("No ISA segment in the file") still open |
| `isa.repetition-separator-invalid` | error | ✔️ | — |
| `isa.repetition-separator-missing` | error | ✔️ | — |
| `isa.segment-terminator-invalid` | fatal | 🔶 / 🔬 | KEEP the gate. Drop "The terminator was probably stripped by the sender" (speculation). Retitle pending research. Co-fires with `isa.trailing-junk` in real cases — leave for later |
| `isa.segment-terminator-noncanonical` | warning | 🔶 **remove** | non-`~` terminator is legal; not a deviation. Also drop it from the round-trip `_RECONSTRUCTION_OWNS` set |
| `isa.segment-terminator-stripped` | error | 🔶 **→ fatal** | Verified defect: fabricating `~` cascades (a `\n`-terminated file with the terminator stripped → `split_segments` collapses the body → false `gs.missing-ge` + `structure.missing-iea`). Decision (Option A): refuse. Reword to drop "reconstructed as `~`". Remove from `_RECONSTRUCTION_OWNS`. `CANONICAL_TERMINATOR` may become unused |
| `isa.separator-count-low` | fatal | ✔️ | — (its pair `separator-count-high` arrives via the `no-functional-group` rename) |
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
| `gs.responsible-agency-invalid` | error | 🔶 | Retitle so it doesn't read as a trading party. GS07 (X12 data element **455**) names the standards body: `X` = Accredited Standards Committee X12, `T` = Transportation Data Coordinating Committee. Explanation should cite element 455. **Verify** 455 has no other valid values |
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
| `structure.foreign-content` | fatal | 🔶 | Keep the check. Retitle "Segment outside the envelope structure" — current "A segment appears where none is structurally valid" is too abstract; lean on the per-occurrence message |
| `structure.functional-group-count-mismatch` | fatal | ✔️ | — |
| `structure.missing-iea` | fatal | ✔️ | — |
| `structure.identifier-invalid` (was `structure.tag-shape-invalid`) | error | ✅ renamed / 🔶 wording | Rename + "tag" → "segment identifier" done (`f08294b`). **STILL OPEN:** retitle "A segment identifier does not begin with an uppercase letter" — current title still says "not uppercase alphabetic", but the check is first byte `isalpha()+isupper()` (A5); IDs may contain digits (`N1`, `PO1`, `G62`) |

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

| item | branch | state |
|---|---|---|
| remove `isa.line-length` | `refactor/remove-isa-line-length` (`013e252`) | committed, **not pushed / not merged** |
| this doc | `docs/diagnostics-review` | pushed, no PR |
| "tag" → "segment identifier" sweep (4 code renames + all prose) | `refactor/tag-to-identifier` (`f08294b`) | committed, **not pushed / not merged**; 377 tests green |
| everything else | — | not started |

- `docs/using-x12-tidy.md` (developer usage guide) is written but **untracked**.
- The 4 engineering-note **PDFs** still contain "tag" (`finding-the-elusive-isa-line.pdf` ×2, `reconstructing-the-isa-line.pdf` ×1). Re-printing them is **gated** — needs an explicit go-ahead in the moment.
