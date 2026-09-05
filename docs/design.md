# x12-tidy design

The reference for *why* x12-tidy is built the way it is. Mechanics live in
module docstrings; this document holds the decisions that span modules. It gains
one section per step as the project moves forward.

For narrative walk-throughs, the engineering notes at
[docs.tidyedi.com](https://docs.tidyedi.com):
[The x12-tidy Method](https://docs.tidyedi.com/the-x12-tidy-method.html) is the
spine — earn the delimiters from structure first. Then
[Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)
(locating the run — real-world violations, why fixed offsets and a regex both
fail),
[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)
(recovering the four delimiters from a run whose byte offsets have all shifted),
and
[Reconstructing the ISA Line](https://docs.tidyedi.com/reconstructing-the-isa-line.html)
(rebuilding the canonical 105-byte line once the delimiters are trusted).

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
| `cleansed` | `dirty` with everything before the first `ISA` identifier removed |
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

`x12_tidy.envelope.isa.extract_isa_line(dirty) -> IsaLineResult`

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
  - `> 16` → `isa.separator-count-high` — the `GS` that was found is not this ISA
    line's header (more than 16 separators precede it). Either there is no GS
    envelope and the match is inside a later segment, or the element separator
    occurs inside ISA06/ISA08 data (an unparseable segment). Pairs with
    `isa.separator-count-low`.

  When no candidate yields exactly 16, the **first** candidate's failure is
  reported.
- **Lowercase and wide encodings.** The uppercase `ISA` candidates are tried
  first (no buffer copy). Only if none parse: a NUL-interleaved `I S A` near the
  start → `isa.identifier-utf16` (fatal, "re-export the file"); otherwise one
  lower-case copy of the buffer, and the `isa` offsets are tried
  case-insensitively (`GS` matched case-insensitively too) carrying
  `isa.identifier-lowercase` (error). This also rescues a lowercase segment sitting
  behind junk that contains the literal uppercase word `ISA`. A file with a
  non-uppercase ISA identifier has non-uppercase identifiers throughout, which later steps
  must tolerate.
- The returned run **includes** the segment terminator and any trailing bytes
  (appended newlines, stray spaces, even a comment line) between it and `GS`.
  Splitting that run into ISA01–ISA16 + terminator + trailing junk is the next
  step.

Not caught here (Step 2's job): the element separator being alphanumeric or a
control byte, the separator colliding with the terminator, element widths, a
duplicated `ISA` identifier inside an otherwise-16-separator run.

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

`x12_tidy.envelope.isa.split_isa_line(run) -> IsaDecomposition` is the first slice:
recover the four X12 delimiters — element separator (`run[3]`), repetition
separator (`ISA11`, only for version `00403`+), component separator (value of
`ISA16`), segment terminator (one byte, by rule) — by splitting the run on the
element separator rather than reading any byte offset. See
[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)
for the walk-through, and the module docstring for the flow.

The split happens **once**. `IsaDecomposition` carries the sixteen raw element
values alongside the delimiters, and slice 2 consumes them directly rather than
splitting the run a second time.

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

`x12_tidy.envelope.isa.reconstruct_isa_line(decomposition) -> ReconstructedIsaLine` (also
reachable as `clean_isa_line(dirty)`, which runs Step 1 → slice 1 → slice 2 in
one call). See the module docstring in `isa/reconstruct.py` for the flow.
`ReconstructedIsaLine` *contains* the `IsaDecomposition` it was built from rather
than copying its fields out.

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
   separator = 105 bytes. The segment terminator is returned alongside (it is
   not one of the 105).

The sender's element, component, repetition **and segment** delimiters are all
**kept as-is** — which byte serves as a delimiter is the sender's choice, X12
does not dictate it, so any valid non-alphanumeric byte is conformant and is
preserved silently. A `\n` terminator stays `\n` and raises no finding. When
the sender omitted the terminator entirely (`isa.segment-terminator-stripped`,
fatal) x12-tidy refuses rather than guess `~` — a wrong terminator would break
the split of every following segment. Bytes that cannot be a legal delimiter (trailing
`\r\n` or spaces after the real terminator, an alphanumeric terminator) are a
separate matter, stripped or refused by slice 1.

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

**The round-trip acceptance test.** `tests/test_reconstruct.py`: for every
non-terminal corpus input, reconstruct, then re-parse the reconstruction through
the whole pipeline (re-wrapped with the terminator reconstruction preserved).
The reconstructed line is a **fixed point** — cleaning it again returns the
identical bytes and elements — and none of the codes reconstruction owns
(`isa.element-*`, `isa.leading-bytes`, `isa.trailing-*`,
`isa.segment-terminator-stripped`) reappears. Findings reconstruction
deliberately does **not** act on — value-level (`isa.version-unrecognized`,
`isa.isa11-not-standards-id`) — are out of scope for this phase and
legitimately survive a round trip.

**Scope boundary.** Reconstruction validates and repairs *structure* — widths,
delimiters, the terminator, the length. It does **not** judge element *values*:
whether ISA05 is a real qualifier, ISA09 a real date, ISA15 a valid usage
indicator, or whether ISA13 matches IEA02. That is envelope QA/QC's job, which
runs once a payload exists (below).

**Naming, resolved.** `clean_isa_line(dirty)` stays the ISA-line-only pipeline
entry point. The raw-bytes-in → cleansed-contents-out orchestrator, which
overloading that name would have obscured, was given its own name instead:
`clean_payload` (`x12_tidy.envelope.structure.clean_payload`) — chosen over
"interchange"/"transmission" and to avoid colliding with the internal
cleansed-body variable it assembles from.

**The whole-document cleanse — done.** Reconstruction produces a clean ISA
*line*; the tool returns cleansed *contents*. Built in pieces:

* **Segment split (`x12_tidy.envelope.structure.split_segments`) — done.** A mechanical
  transform. Take everything from `GS` onward, `strip()` whitespace *and the
  terminator* from the ends (dropping trailing whitespace after the final `IEA`
  and the terminator that closes it), split on the recovered segment terminator,
  and left-trim whitespace from each piece. The split is on the *segment
  terminator* only — an element separator is never a split point, so unused
  elements (`**`) stay inside their segment. A segment identifier is alphabetic and
  first, so leading whitespace is never segment content; the right-hand side of
  a piece is never touched (a space-padded final element is real data). Empty
  pieces (two terminators in a row) are kept here. **No diagnostics, no
  validation, no refusal** — this step canonicalises nothing and judges nothing.
* **Drop empty pieces (`x12_tidy.envelope.structure.drop_empty_segments`) — done.** The
  empty pieces two terminators in a row leave behind are not segments; this
  removes them. Still mechanical — no judgement about *why* the terminators were
  doubled.
* **Reassemble (`x12_tidy.envelope.structure.clean_payload`) — done.** Cleans the ISA
  line, splits and drops empties from the body, and rejoins everything on the
  sender's own segment terminator into one payload. Refuses exactly when the
  ISA line can't be recovered; still no per-segment repair or envelope
  judgement. See [Reassembling the
  Interchange](reassembling-the-interchange.md) for why doing the ISA-line
  location work twice is deliberate and free.

**Envelope QA/QC (`x12_tidy.envelope.qaqc.check_payload`) — done.** See [Auditing the
Envelope](auditing-the-envelope.md) for the full argument; summary follows.
Runs once a payload
exists, and unlike the ISA-reconstruction gate, `fatal` here never halts the
walk — it is a display/trust signal, and every check still runs to completion.
One pass over the segments (a small open-group/open-transaction-set stack)
covers: `ISA`/`IEA`, `GS`/`GE`, and `ST`/`SE` pairing and nesting; control-number
agreement and uniqueness (`ISA13`/`IEA02`, `GS06`/`GE02`, `ST02`/`SE02`);
segment/transaction-set/group counts (`SE01`, `GE01`, `IEA01`); the A5
identifier-shape gate; `ISA12`/`GS08` version agreement; `ISA15` usage-indicator
validity; `GS07` responsible-agency validity; and foreign content — a segment
with no structurally valid place to be, including a duplicated `IEA` once the
interchange is already closed. Deliberately not covered, no decision made yet:
`ISA05`/`ISA07` qualifiers, `ISA14`, `GS01`, `ST01` shape, date/time format,
`TA1`, `BIN`/`BDS`, and multiple interchanges in one file (`.segments` still
assumes exactly one). `x12_tidy.envelope.tidy.tidy()` is the whole-package entry point:
cleanse, then QA/QC, one combined diagnostic list.

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
  A short-ISA-line problem found while recovering is still `isa.separator-count-low`,
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
