# edi-linter design

The reference for *why* the linter is built the way it is. Mechanics live in
module docstrings; this document holds the decisions that span modules. It gains
one section per step as the project moves forward.

---

## 1. Philosophy: permissive parse, strict report

The linter exists because many real-world X12 senders violate the standard. The
audience is a developer who has received a bad file from a trading partner and
needs to know *exactly* what is non-conformant — so they can push back on the
sender or handle it deliberately.

So the linter does **not** fail fast on the first problem. It parses
permissively — locating the ISA segment, the delimiters, the structure even in a
malformed file — and emits a `Diagnostic` for **every** deviation it finds along
the way. Nothing is silently repaired: every recovery step that tolerates a
non-conformance also records it.

It does **not** rely on fixed byte offsets (e.g. "the segment terminator is at
offset 105"), because senders strip empty elements and every offset after that
point shifts.

Observed violations the linter must catch:

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

`edi_linter.isa.extract_isa_line(dirty) -> IsaLineResult`

Step 1's entire job is to return that byte run. It does **not** parse or
validate delimiters, elements, lengths, or the terminator — it only finds where
the ISA line begins and ends. See the module docstring for the step-by-step
flow.

Key points:

- The end of the ISA line is found by locating `GS` + element separator, not by
  trusting offset 105/106. Offset 106 is used only as a fast-path shortcut that
  yields the identical result.
- `isa_line.count(element_separator) < 16` is fatal. An ISA header has exactly
  16 element separators; a shorter run means either elements were dropped or the
  `GS` anchored on is a false match inside earlier data. This one check does
  double duty.
- The returned run **includes** the segment terminator and any trailing bytes
  (appended newlines, stray spaces) between it and `GS`. Splitting that run into
  ISA01–ISA16 + terminator + trailing junk is the next step.

Accepted limitation: if leading junk ends in `ISA` followed by a byte that also
works as the element separator, Step 1 anchors on the junk. The
`isa.leading-bytes` warning always fires in that case, and the next step's
element checks reject the result. A multi-candidate `ISA` anchor is a possible
later refinement.

### Recovery, and later steps

The recovery path and the decompose-and-validate step are drafted in scratch
(`recover_isa_line.py`) but not yet packaged. They are the next design
conversation.

---

## 3. Diagnostic codes

### The record

`edi_linter.diagnostics.Diagnostic(code, message, offset)`

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

`src/edi_linter/diagnostics/codes.py` — a `Code` enum plus a `META` dict of
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
| `edi-linter codes` / `codes --area isa` / `explain <code>` | developers at the terminal | rendered live from `codes.py`, writes nothing |

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

1. `edi-linter codes --area <area>` — check nothing already covers the
   situation; `edi-linter explain <code>` on anything close.
2. If nothing fits, add a `Code` member and a `META` row to `codes.py`.
3. Build. The generated views update; CI enforces consistency.
