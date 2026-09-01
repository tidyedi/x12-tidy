# x12-tidy design

The reference for *why* x12-tidy is built the way it is. Mechanics live in
module docstrings; this document holds the decisions that span modules. It gains
one section per step as the project moves forward.

For narrative walk-throughs: [Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)
([source](finding-the-elusive-isa-line.md)) covers Step 1 — the real-world
violations, why fixed offsets and a regex both fail, and the five techniques.
[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)
([source](those-pesky-delimiters.md)) covers Step 2 — recovering the four
delimiters from a run whose byte offsets have all shifted.

---

## 1. Philosophy: permissive parse, strict report

x12-tidy exists because many real-world X12 senders violate the standard. The
audience is a developer who has received a bad file from a trading partner and
needs to know *exactly* what is non-conformant — so they can push back on the
sender or handle it deliberately.

So x12-tidy does **not** fail fast on the first problem. It parses
permissively — locating the ISA segment, the delimiters, the structure even in a
malformed file — and emits a `Diagnostic` for **every** deviation it finds along
the way. Nothing is silently repaired: every recovery step that tolerates a
non-conformance also records it.

It does **not** rely on fixed byte offsets (e.g. "the segment terminator is at
offset 105"), because senders strip empty elements and every offset after that
point shifts.

Observed violations x12-tidy must catch:

- a byte-order mark or stray bytes before the ISA segment
- stripped empty ISA elements — the ISA segment is no longer its standard
  105-byte fixed length
- extra newlines (CR / LF) appended after segment terminators

Input is always `bytes`, never `str`. BOM and "no leading data" checks are only
meaningful at the byte level, and byte-oriented logic ports cleanly to Rust (a
possible later move for speed).

### Vocabulary

| term | meaning |
| --- | --- |
| `dirty` | the raw file bytes, exactly as received |
| `cleansed` | `dirty` with everything before the first `ISA` tag removed |
| *identify* | emit a diagnostic and continue |
| *identify and exit* | emit a diagnostic and stop (a `fatal`) |

---

## 2. The ISA envelope: a two-path architecture

Reading the ISA envelope splits into two paths:

- **Standard gate (fast path).** Locate the ISA line, confirm it is
  byte-standard (`GS` sits at offset 106), then read it at fixed offsets. This
  is the common case and it is cheap.
- **Recovery (slow path).** When the gate's fixed-offset check fails — stripped
  elements, re-padded elements, appended newlines — fall back to a permissive,
  content-anchored parse.

Both paths produce the **same shape** of output so downstream steps do not care
which ran: the run of bytes from `ISA` up to (but not including) the `GS`
functional-group header, plus a list of `Diagnostic`s.

### Step 1 — return the ISA line

`x12_tidy.isa.extract_isa_line(dirty) -> IsaLineResult`

Step 1's entire job is to return that byte run. It does **not** parse or
validate delimiters, elements, lengths, or the terminator — it only finds where
the ISA line begins and ends. See the module docstring for the step-by-step
flow.

**The minimum bar for "this run is an ISA line".** No component validation
happens here, but a run must clear all three of these to be handed on:

1. it begins with `ISA`
2. it ends immediately before `GS` + the element separator
3. it holds **exactly** 16 element separators

A run that fails any of them is not an ISA line — reported fatal, and it does
**not** go to recovery. Recovery (a later step) only ever sees runs that clear
this bar but have other problems: wrong length, bad delimiters, bad element
content.

Key points:

- The end of the ISA line is found by locating `GS` + element separator, not by
  trusting offset 105/106. Offset 106 is used only as a fast-path shortcut that
  yields the identical result.
- **Multi-candidate anchoring.** The file may contain the bytes `ISA` before the
  real segment (in an email header, a filename, junk that ends in `ISA*`). Step 1
  collects every `ISA` offset (capped at `MAX_ISA_CANDIDATES`) and tries each in
  turn; the first that yields a clean run wins, and the bytes before it become
  `isa.leading-bytes`.
- **Exactly 16 element separators, not `>= 16`.** Accepting `>= 16` let a stray
  `GS` deep in the transaction body, or a junk `ISA*` prefix, produce a
  plausible-looking but wrong run with no diagnostic. Both directions are fatal
  and **terminal** — a run with the wrong count is not an ISA line and does not
  go to recovery:
  - `< 16` → `isa.separator-count-low` — element separators were removed, or the
    `GS` anchored on is a false match inside earlier data.
  - `> 16` → `isa.no-functional-group` — the `GS` that was found is not this ISA
    line's header (too many separators precede it). Either there is no GS
    envelope and the match is inside a later segment, or the element separator
    occurs inside ISA06/ISA08 data (an unparseable segment). The diagnostic
    leads with the structural fact — no functional-group header — rather than
    the separator count, which is the symptom.

  When no candidate yields exactly 16, the **first** candidate's failure is
  reported.
- **Lowercase and wide encodings.** The uppercase `ISA` candidates are tried
  first (no buffer copy). Only if none parse: a NUL-interleaved `I S A` near the
  start → `isa.tag-utf16` (fatal, "re-export the file"); otherwise one
  lower-case copy of the buffer, and the `isa` offsets are tried
  case-insensitively (`GS` matched case-insensitively too) carrying
  `isa.tag-lowercase` (error). This also rescues a lowercase segment sitting
  behind junk that contains the literal uppercase word `ISA`. A file with a
  non-uppercase ISA tag has non-uppercase tags throughout, which later steps
  must tolerate.
- The returned run **includes** the segment terminator and any trailing bytes
  (appended newlines, stray spaces, even a comment line) between it and `GS`.
  Splitting that run into ISA01–ISA16 + terminator + trailing junk is the next
  step.

Not caught here (Step 2's job): the element separator being alphanumeric or a
control byte, the separator colliding with the terminator, element widths, a
duplicated `ISA` tag inside an otherwise-16-separator run.

**Residual limitation.** If leading junk is itself shaped *exactly* like an ISA
line — the bytes `ISA`, then 16 element separators, then `GS` + that separator,
spanning ≥ 109 bytes — Step 1 accepts it and returns it, with no diagnostic (or
only `isa.leading-bytes` if it is not at offset 0). Real-world junk (BOMs, mail
and transport headers, filenames, file magic) does not look like this; it takes
something deliberately ISA-segment-shaped prepended to the file. The earlier,
weaker form of this — junk merely *ending* in `ISA` + a separator-like byte — is
handled: that junk does not carry 16 separators, so the retry moves on to the
real segment.

### Step 2 — decompose the run

`x12_tidy.isa.split_isa_line(run) -> IsaDelimiters` is the first slice: recover
the four X12 delimiters — element separator (`run[3]`), repetition separator
(`ISA11`, only for version `00403`+), component separator (value of `ISA16`),
segment terminator (one byte, by rule) — by splitting the run on the element
separator rather than reading any byte offset. See
[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)
for the walk-through, and the module docstring for the flow.

**Severity rule for delimiters.** A finding is fatal *at this step* only if it
blocks parsing the interchange outright. The element separator and the segment
terminator are needed by every segment → an unusable one is fatal. The component
separator (composite elements) and the repetition separator (repeats) are
conditional → an unusable one is an `error`, which the body parser escalates to
fatal at the first segment that needs it.

**The decompose is lossless.** For any run `split_isa_line` does not fatal,
`element_separator.join(run.split(element_separator)) == run` — the seventeen
pieces (`ISA`, ISA01–ISA15, `ISA16` + terminator + trailing) are a complete,
reversible account of the run. `tests/test_isa_line_roundtrip.py` proves this
across the corpus: every input is *either* a clean refusal (no line, or not
usable, always with a `fatal`) *or* a lossless account. There is no third
outcome — no silent wrong answer, no partial parse, no crash.

### Step 2, slice 2 — reconstruct the canonical ISA line

`x12_tidy.isa.reconstruct_isa_line(run, delimiters) -> ...` (also reachable as
`clean_isa_line(dirty)`, which runs Step 1 → slice 1 → slice 2 in one call).
See the module docstring in `isa/reconstruct.py` for the flow.

**The methodology, and why it beats a fixed-offset parser.** A conventional X12
reader trusts byte positions: the ISA line is 105 bytes, the terminator is at
105, each element is at a known offset. One right-trimmed blank field — a sender
sends `ISA*00**00**ZZ*…` with ISA02/ISA04 empty instead of ten spaces — and
every offset downstream is wrong; the reader is dead on arrival.

x12-tidy inverts the dependency. The only things it must be *certain* of are the
four delimiters, so it earns those first, from structure alone (Step 1's minimum
bar + slice 1), making no assumption about length or width. Once slice 1 returns
**no fatal**, the delimiters are trustworthy and width stops being load-bearing:

1. split the run on the element separator → exactly sixteen elements (guaranteed
   by the non-fatal parse);
2. within each *text* element, replace any `\r` / `\n` with a space — a
   hard-wrapped ISA segment. This is safe **only here**: before the delimiters
   are known a `\r`/`\n` could be the terminator or a delimiter, so ISA16 (its
   value *is* the component separator) and ISA11 (when it carries the repetition
   separator, version `00403`+) are excluded by position;
3. normalise each element to its fixed width
   `(2,10,2,10,2,15,2,15,6,4,1,5,9,1,1,1)` — pad a short one with spaces, trim
   one that is long by trailing spaces only;
4. reassemble: `ISA` + the sixteen elements joined on the (unchanged) element
   separator = 105 bytes. The terminator is normalised to `~` and returned
   alongside (it is not one of the 105).

The sender's element, component, and repetition separators are **kept as-is** —
any valid non-alphanumeric byte is conformant; only the terminator is
normalised.

**What reconstruction repairs** (each with a `Diagnostic`):

| finding | code | severity | action |
| --- | --- | --- | --- |
| `\r`/`\n` inside a text element | `isa.element-embedded-newline` | warning | → space, then re-measure |
| element shorter than its fixed width | `isa.element-width` | **error** | space-pad on the right |
| element longer only by trailing spaces | `isa.element-width` | **error** | trim to width |

`isa.element-width` is an **error, not a warning**: a non-105-byte ISA line
cannot be read by conventional VAN services or any fixed-offset parser, so the
interchange is unprocessable until it is repaired.

**What makes reconstruction refuse** (`isa_line` is `None`, one `fatal`):

| finding | code | why not a guess |
| --- | --- | --- |
| anything slice 1 already made fatal | — | propagated |
| element longer than its width with **real data** in the overflow | `isa.element-overflow` | intent is unknowable — a dropped element separator merged two fields, or the sender overran the field. Either guess risks corrupting an identifier (sender/receiver ID, control number). |
| reassembled line not 105 bytes | `isa.line-length` | a guard; should never fire once the per-element widths hold |

**The round-trip acceptance test.** `tests/test_reconstruct.py`: for every
non-terminal corpus input, reconstruct, then re-parse the reconstruction through
the whole pipeline. The reconstructed line is a **fixed point** — cleaning it
again returns the identical bytes and elements — and none of the codes
reconstruction owns (`isa.element-*`, `isa.leading-bytes`, `isa.trailing-*`,
`isa.segment-terminator-*`, `isa.line-length`) reappears. Value-level findings
(`isa.version-unrecognized`, `isa.isa11-not-standards-id`) are **out of scope**
for this phase and may legitimately survive a round trip.

**Scope boundary.** Reconstruction validates and repairs *structure* — widths,
delimiters, the terminator, the length. It does **not** judge element *values*:
whether ISA05 is a real qualifier, ISA09 a real date, ISA15 a valid usage
indicator, or whether ISA13 matches IEA02. That is later work (the GS/ST
envelope QA/QC phase).

**Open naming question.** `clean_isa_line(dirty)` is currently the one-call
pipeline entry point. The name overloads "cleaning the ISA line", which through
Step 1 and slice 1 meant *recovering the delimiters so a clean-up is possible* —
not producing the cleansed artifact. The raw-bytes-in → cleansed-contents-out
orchestrator is really the whole-document cleanse (below), not an ISA-line
function. This is flagged for resolution before the phase is finalised.

**Not built yet — the whole-document cleanse.** Reconstruction produces a clean
ISA *line*; it does not yet return cleansed *contents*. That step, once the
terminator is known: `raw.split(segment_terminator)` → each piece must start
with a valid segment tag → strip the inter-segment junk (line wrapping,
transport framing) that sits after *every* terminator, not just the ISA line's →
rejoin on `~` → splice in the reconstructed ISA line. It gets its own
`structure.*` diagnostic. This is what makes the tool hand back a cleaned
interchange rather than a cleaned header.

The recovery path (a permissive re-parse when the standard gate fails) is
drafted in scratch (`recover_isa_line.py`) and folds into this work.

---

## 3. Diagnostic codes

### The record

`x12_tidy.diagnostics.Diagnostic(code, message, offset)`

- `code` — a `Code` enum member, the stable identity of the finding.
- `message` — prose built at the call site with the specifics of *this*
  occurrence (the actual bad bytes, the real offset). Must read on its own
  without the code beside it.
- `offset` — a byte position into the original input, or `None`.

There is **no severity on the record.** Severity is resolved when results are
reported (see below), so a config loaded after parsing still applies and a code
cannot end up with different severities depending on which module raised it.

### The code scheme

Codes are strings of the form `area.specific` — a closed `area` vocabulary,
kebab-case within each part, a dot between. **No numbers.**

A sequential number needs a global counter, and a global counter is a
serialization point that concurrent feature branches cannot share — two
developers both take the next number, both merge, and the number is ambiguous.
A descriptive name allocated by *what the finding is* has no counter: the
namespace is naturally partitioned by what each developer is working on. Two
branches adding two different codes touch different lines and merge cleanly; two
branches adding the *same* code conflict, which is the correct outcome.

- **`area` is the subject of the finding, never the code path that raised it.**
  A short-ISA-line problem found while recovering is still `isa.line-length`,
  not `recovery.*`. Closed vocabulary: `isa`, `gs`, `st`, `delimiter`,
  `structure`. It grows roughly once a year.
- The enum member name is the code string upper-cased with `.`/`-` → `_`:
  `isa.leading-bytes` ↔ `Code.ISA_LEADING_BYTES`.
- A retired code is **never reused**. A material change in meaning is a new
  code; the old one stays in the registry marked `deprecated`.

### The registry is code, not a document

`src/x12_tidy/diagnostics/codes.py` — a `Code` enum plus a `META` dict of
`CodeMeta(default_severity, title, explanation, deprecated)` — is the **single
source of truth**.

The recurring failure mode this avoids: a reference *document* gets copied for
personal use, the copies drift, and developers waste time because the code they
believed was correct is actually something else. A document can be forked. Code
is imported. Modules reference `Code.X` symbols (never string literals — a typo
fails immediately); tests assert on the symbol.

`CodeMeta` deliberately omits `emitted_by` (goes stale; a test derives it
instead), `since` (git blame), and `related_codes` (rots).

### Severity

`default_severity` (`fatal` / `error` / `warning`; `fatal` also stops parsing)
is a *starting point*. When the user-config layer lands, a receiver will be able
to override it per-code — bump `isa.leading-bytes` to `error`, or set a code to
`ignore`. Resolution happens at report time in exactly one place
(`resolved_severity`): `config override → registry default`. Exit-code logic is
also at report time — any `fatal` or `error` after resolution → non-zero exit.

### Readable views — all generated, never hand-authored

| view | audience | how |
| --- | --- | --- |
| `docs/diagnostics.md` | anyone browsing the repo / GitHub | generated by `scripts/gen_diagnostics_docs.py`, committed, banner-marked |
| `x12-tidy codes` / `codes --area isa` / `explain <code>` | developers at the terminal | rendered live from `codes.py`, writes nothing |

A normal lint run generates nothing; `codes.py` is imported once per process
like any module.

### Keeping it from drifting

- **pre-commit hook** regenerates `docs/diagnostics.md` whenever `codes.py` is
  staged — the developer forgets nothing.
- **CI** runs `scripts/gen_diagnostics_docs.py --check` and fails the build if
  the committed file is stale (catches `--no-verify` and web edits).
- **`tests/test_codes_registry.py`** asserts every `Code` is registered, every
  registered code is actually emitted by some module (or `deprecated`), names
  match `area.specific`, and there are no duplicates.

### Adding a code — the workflow

1. `x12-tidy codes --area <area>` — check nothing already covers the
   situation; `x12-tidy explain <code>` on anything close.
2. If nothing fits, add a `Code` member and a `META` row to `codes.py`.
3. Build. The generated views update; CI enforces consistency.
